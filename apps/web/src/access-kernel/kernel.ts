import { BaselineTransactions } from './baseline-store.js'
import type { BaselineRequest } from './baseline-state.js'
import type { ContextRequestIdentity } from './server-context.js'
import { completedBaseline } from './baseline-state.js'
import type { EntityType } from '../sync/types.js'
import { retryPlan } from '../sync/retry-policy.js'
import type { KernelDatabase } from './database.js'
import { readProjection, replayableStates, heldDependencyStates } from './projection.js'
import { contextKey, nextContextState, principalKey, validateVerifiedContext } from './context.js'
import {
  canonicalJson,
  entityCapability,
  operationIntact,
  requireCapability,
  validateCommand,
  validateResults,
} from './operations.js'
import type {
  CachePartition,
  ContextTicket,
  DeviceControl,
  DispatchBatch,
  LocalCommand,
  OperationDelivery,
  OperationEvent,
  OwnedOperation,
  VerificationAttempt,
  VerifiedAccessContext,
} from './types.js'

interface Dependencies {
  now(): number
  newId(): string
}
interface Authorized {
  control: DeviceControl
  context: VerifiedAccessContext
  partition: CachePartition
}

/** Isolated kernel with no credential storage or production wiring. Baseline entry
 * requires a supported verified context; the actual null-advertised server stays gated.
 */
export class AccessKernel {
  #ticket: ContextTicket | null = null
  #sequence = 0
  #baselineStarting = false
  constructor(
    private readonly db: KernelDatabase,
    private readonly dependencies: Dependencies = {
      now: () => Date.now(),
      newId: () => crypto.randomUUID(),
    },
  ) {}

  private tables() {
    return [
      this.db.deviceControl,
      this.db.accessContexts,
      this.db.cachePartitions,
      this.db.cacheRecords,
      this.db.operationJournal,
      this.db.operationDelivery,
      this.db.operationEvents,
    ]
  }
  private initial(): DeviceControl {
    return {
      key: 'device',
      generation: 0,
      tabAttemptId: null,
      activePartitionId: null,
      state: 'LOCKED',
      localSequence: 0,
      observedAt: this.dependencies.now(),
      dispatchAttemptId: null,
      dispatchScanAfter: 0,
    }
  }
  private live(ticket: ContextTicket): boolean {
    return this.#ticket !== null && canonicalJson(ticket) === canonicalJson(this.#ticket)
  }

  async beginVerification(tabAttemptId: string): Promise<VerificationAttempt> {
    if (!tabAttemptId.trim()) throw new Error('A new tab attempt is required')
    this.#sequence += 1
    this.#ticket = null // blank the local authorization boundary before any async work
    return this.db.transaction('rw', this.tables(), async () => {
      const control = (await this.db.deviceControl.get('device')) ?? this.initial()
      if (!Number.isSafeInteger(control.generation + 1)) throw new Error('Generation exhausted')
      control.generation += 1
      control.tabAttemptId = tabAttemptId
      control.state = nextContextState(control.state, 'verify')
      control.dispatchAttemptId = null
      await this.db.deviceControl.put(control)
      return { deviceGeneration: control.generation, tabAttemptId }
    })
  }

  async acceptVerifiedContext(attempt: VerificationAttempt, supplied: VerifiedAccessContext) {
    const sequence = this.#sequence
    const expectedTicket = this.#ticket ? structuredClone(this.#ticket) : null
    attempt = structuredClone(attempt)
    const context = structuredClone(supplied)
    validateVerifiedContext(context, this.dependencies.now())
    const result = await this.db.transaction('rw', this.tables(), async () => {
      const control = await this.db.deviceControl.get('device')
      if (
        !control ||
        control.state !== 'VERIFYING' ||
        control.generation !== attempt.deviceGeneration ||
        control.tabAttemptId !== attempt.tabAttemptId
      )
        throw new Error('Verification attempt fenced')
      const oldContext = control.activePartitionId
        ? await this.db.accessContexts.get(control.activePartitionId)
        : undefined
      const oldPartition = control.activePartitionId
        ? await this.db.cachePartitions.get(control.activePartitionId)
        : undefined
      const same =
        oldContext &&
        oldPartition &&
        oldPartition.status !== 'superseded' &&
        contextKey(oldContext.context) === contextKey(context)
      const partition: CachePartition = same
        ? oldPartition
        : {
            partitionId: this.dependencies.newId(),
            principalKey: principalKey(context.principal),
            locationId: context.selectedLocationId,
            authorizationEpoch: context.authorizationEpoch,
            policyRevision: context.policyRevision,
            status: 'staging',
            baselineComplete: false,
            cursor: null,
          }
      if (!same && oldPartition)
        await this.db.cachePartitions.put({ ...oldPartition, status: 'superseded' })
      if (!same) await this.db.cachePartitions.add(partition)
      await this.db.accessContexts.put({ partitionId: partition.partitionId, context })
      if (!same) control.dispatchScanAfter = 0
      control.activePartitionId = partition.partitionId
      control.state = nextContextState(
        control.state,
        completedBaseline(partition, context) ? 'verified_complete' : 'needs_baseline',
      )
      control.observedAt = this.dependencies.now()
      await this.db.deviceControl.put(control)
      const ticket: ContextTicket = {
        ...attempt,
        partitionId: partition.partitionId,
        principalKey: principalKey(context.principal),
        authorizationEpoch: context.authorizationEpoch,
      }
      return {
        ticket,
        state: control.state,
        baselineSupported: context.snapshotProtocol === 'baseline-v1',
      }
    })
    await this.installTicket(result.ticket, sequence, expectedTicket)
    return result
  }

  private async installTicket(
    ticket: ContextTicket,
    sequence: number,
    expected: ContextTicket | null,
  ): Promise<void> {
    const [current, partition, record] = await this.db.transaction(
      'r',
      [this.db.deviceControl, this.db.cachePartitions, this.db.accessContexts],
      () =>
        Promise.all([
          this.db.deviceControl.get('device'),
          this.db.cachePartitions.get(ticket.partitionId),
          this.db.accessContexts.get(ticket.partitionId),
        ]),
    )
    if (
      partition?.authorizationEpoch !== ticket.authorizationEpoch ||
      partition.principalKey !== ticket.principalKey ||
      partition.status === 'superseded' ||
      record?.context.authorizationEpoch !== ticket.authorizationEpoch ||
      principalKey(record.context.principal) !== ticket.principalKey ||
      this.#sequence !== sequence ||
      canonicalJson(this.#ticket) !== canonicalJson(expected) ||
      current?.generation !== ticket.deviceGeneration ||
      current.tabAttemptId !== ticket.tabAttemptId ||
      current.activePartitionId !== ticket.partitionId
    )
      throw new Error('Verification attempt or baseline partition fenced')
    this.#ticket = structuredClone(ticket)
  }
  private baselines() {
    return new BaselineTransactions(
      this.db,
      this.dependencies.now,
      this.dependencies.newId,
      (ticket) => this.live(ticket),
    )
  }
  private async baselineAdmission(ticket: ContextTicket) {
    if (!this.live(ticket)) throw new Error('No matching verified session')
    const record = await this.db.accessContexts.get(ticket.partitionId)
    if (!this.live(ticket) || record?.context.snapshotProtocol !== 'baseline-v1')
      throw new Error('Supported baseline advertisement required')
    return record.context
  }
  async beginBaseline(supplied: ContextTicket): Promise<ContextTicket> {
    const ticket = structuredClone(supplied)
    if (this.#baselineStarting) throw new Error('A baseline start is already pending')
    this.#baselineStarting = true
    try {
      await this.baselineAdmission(ticket)
      const sequence = ++this.#sequence
      const result = await this.baselines().begin(ticket)
      await this.installTicket(result, sequence, ticket)
      return result
    } finally {
      this.#baselineStarting = false
    }
  }
  async resumeBaseline(supplied: ContextTicket): Promise<void> {
    const ticket = structuredClone(supplied)
    await this.baselineAdmission(ticket)
    await this.baselines().resume(ticket)
    if (!this.live(ticket)) throw new Error('Baseline resume fenced')
  }
  async pendingBaseline(supplied: ContextTicket) {
    const ticket = structuredClone(supplied)
    await this.baselineAdmission(ticket)
    return this.baselines().pending(ticket)
  }
  async commitBaselinePage(
    ticket: ContextTicket,
    request: BaselineRequest,
    response: unknown,
    identity: ContextRequestIdentity,
    current: () => boolean,
  ) {
    await this.baselineAdmission(ticket)
    if (!current()) throw new Error('Baseline session fenced')
    const result = await this.baselines().commit(ticket, request, response, identity, current)
    if (!current() || !this.live(ticket)) throw new Error('Baseline session fenced')
    return result
  }
  async activateBaseline(
    supplied: ContextTicket,
    checkpoint: string,
    context: VerifiedAccessContext,
    current: () => boolean,
  ): Promise<void> {
    const ticket = structuredClone(supplied)
    await this.baselineAdmission(ticket)
    if (!current()) throw new Error('Baseline session fenced')
    const sequence = this.#sequence
    await this.baselines().activate(ticket, checkpoint, context, current)
    if (!current()) throw new Error('Baseline session fenced')
    await this.installTicket(ticket, sequence, ticket)
  }
  async retryBaseline(ticket: ContextTicket, request: BaselineRequest): Promise<void> {
    await this.baselineAdmission(ticket)
    await this.baselines().retry(ticket, request)
  }
  disableBaselineSession(ticket: ContextTicket, current: () => boolean): void {
    if (current() && this.live(ticket)) {
      this.#sequence += 1
      this.#ticket = null
    }
  }
  async holdBaseline(
    supplied: ContextTicket,
    request: BaselineRequest,
    reason: string,
    retryAt: number | null = null,
    current: () => boolean = () => true,
  ): Promise<boolean> {
    const ticket = structuredClone(supplied)
    if (!current() || !this.live(ticket)) return false
    return this.baselines().hold(ticket, request, reason, retryAt, current)
  }

  async lockContext(ticket: ContextTicket): Promise<void> {
    ticket = structuredClone(ticket)
    if (!this.live(ticket)) throw new Error('No matching verified session')
    this.#sequence += 1
    this.#ticket = null
    await this.db.transaction('rw', this.db.deviceControl, async () => {
      const control = await this.db.deviceControl.get('device')
      if (
        !control ||
        control.generation !== ticket.deviceGeneration ||
        control.tabAttemptId !== ticket.tabAttemptId ||
        control.activePartitionId !== ticket.partitionId
      )
        throw new Error('Logout context fenced')
      if (!Number.isSafeInteger(control.generation + 1)) throw new Error('Generation exhausted')
      await this.db.deviceControl.put({
        ...control,
        generation: control.generation + 1,
        state: 'LOCKED',
        tabAttemptId: null,
        dispatchAttemptId: null,
      })
    })
  }

  private async authorized(ticket: ContextTicket, online: boolean): Promise<Authorized | string> {
    const control = await this.db.deviceControl.get('device')
    if (
      !control ||
      control.generation !== ticket.deviceGeneration ||
      control.tabAttemptId !== ticket.tabAttemptId ||
      control.activePartitionId !== ticket.partitionId
    )
      return 'Context ticket fenced'
    const record = await this.db.accessContexts.get(ticket.partitionId)
    const partition = await this.db.cachePartitions.get(ticket.partitionId)
    if (
      !record ||
      !partition ||
      principalKey(record.context.principal) !== ticket.principalKey ||
      partition.principalKey !== ticket.principalKey ||
      record.context.authorizationEpoch !== ticket.authorizationEpoch ||
      partition.authorizationEpoch !== ticket.authorizationEpoch ||
      partition.locationId !== record.context.selectedLocationId ||
      partition.policyRevision !== record.context.policyRevision
    )
      return 'Context ticket metadata mismatch'
    const now = this.dependencies.now()
    if (
      !Number.isFinite(now) ||
      now < control.observedAt ||
      now >= Date.parse(record.context.offlineUntil)
    ) {
      await this.db.deviceControl.put({ ...control, state: 'LOCKED', dispatchAttemptId: null })
      return 'Context expired or clock moved backward; online verification required'
    }
    if (
      !completedBaseline(partition, record.context) ||
      !['READY', 'OFFLINE_READY'].includes(control.state)
    )
      return 'Completed baseline and ready context required'
    if (online && control.state !== 'READY') return 'Online READY context required'
    control.observedAt = now
    await this.db.deviceControl.put(control)
    return { control, context: record.context, partition }
  }

  private async run<T>(
    ticket: ContextTicket,
    online: boolean,
    action: (authorized: Authorized) => Promise<T>,
  ): Promise<T> {
    if (!this.live(ticket)) throw new Error('No matching verified session in this kernel instance')
    const outcome = await this.db.transaction('rw', this.tables(), async () => {
      const authorized = await this.authorized(ticket, online)
      if (typeof authorized === 'string') return { ok: false as const, error: authorized }
      return { ok: true as const, value: await action(authorized) }
    })
    if (!outcome.ok) throw new Error(outcome.error)
    if (!this.live(ticket)) throw new Error('Session changed while transaction completed')
    return outcome.value
  }

  async continueOffline(ticket: ContextTicket): Promise<void> {
    ticket = structuredClone(ticket)
    await this.run(ticket, false, async ({ control }) => {
      if (control.state === 'OFFLINE_READY') return
      await this.db.deviceControl.put({
        ...control,
        state: nextContextState(control.state, 'offline'),
      })
    })
  }

  async commitLocalCommand(ticket: ContextTicket, supplied: LocalCommand): Promise<string> {
    ticket = structuredClone(ticket)
    const command = structuredClone(supplied)
    return this.run(ticket, false, async ({ context, control }) => {
      const envelopeCanonical = validateCommand(command, context)
      const existing = await this.db.operationJournal.get(command.envelope.mutation_id)
      if (existing) {
        const localEvents = (
          await this.db.operationEvents.where('mutationId').equals(existing.mutationId).toArray()
        )
          .filter((event) => event.kind === 'local')
          .map((event) => event.details)
        if (
          existing.principalKey !== ticket.principalKey ||
          existing.locationId !== context.selectedLocationId ||
          existing.envelopeCanonical !== envelopeCanonical ||
          canonicalJson(existing.optimistic) !== canonicalJson(command.optimistic) ||
          canonicalJson(existing.dependsOn) !== canonicalJson(command.dependsOn) ||
          canonicalJson(localEvents) !== canonicalJson(command.localEvents)
        )
          throw new Error('Immutable operation ID collision')
        return existing.mutationId
      }
      for (const id of command.dependsOn) {
        const parent = await this.db.operationJournal.get(id)
        if (
          !parent ||
          parent.principalKey !== ticket.principalKey ||
          parent.locationId !== context.selectedLocationId
        )
          throw new Error('Dependency author or scope mismatch')
      }
      if (!Number.isSafeInteger(control.localSequence + 1))
        throw new Error('Local sequence exhausted')
      const operation: OwnedOperation = {
        mutationId: command.envelope.mutation_id,
        principalKey: ticket.principalKey,
        organizationId: context.principal.organizationId,
        locationId: context.selectedLocationId,
        entityType: command.envelope.entity_type,
        entityId: command.envelope.entity_id,
        authoredUnderEpoch: context.authorizationEpoch,
        localSequence: control.localSequence + 1,
        dependsOn: command.dependsOn,
        envelope: command.envelope,
        envelopeCanonical,
        optimistic: command.optimistic,
        createdAt: new Date(this.dependencies.now()).toISOString(),
      }
      await this.db.operationJournal.add(operation)
      await this.db.operationDelivery.add({
        principalKey: operation.principalKey,
        locationId: operation.locationId,
        entityType: operation.entityType,
        entityId: operation.entityId,
        localSequence: operation.localSequence,
        dispatchable: 1,
        unresolved: 1,
        blocked: 0,
        resultVersion: 0,
        mutationId: operation.mutationId,
        state: 'pending',
        attemptId: null,
        deviceGeneration: null,
        attempts: 0,
        retryAt: 0,
        result: null,
      })
      for (const details of command.localEvents)
        await this.event(operation.mutationId, 'local', null, details)
      await this.db.deviceControl.put({ ...control, localSequence: operation.localSequence })
      return operation.mutationId
    })
  }

  async readEntity(ticket: ContextTicket, entityType: EntityType, entityId: string) {
    ticket = structuredClone(ticket)
    return this.run(ticket, false, ({ context }) =>
      readProjection(this.db, ticket, context, entityType, entityId),
    )
  }

  async readOperation(ticket: ContextTicket, mutationId: string) {
    ticket = structuredClone(ticket)
    return this.run(ticket, false, async ({ context }) => {
      const operation = await this.db.operationJournal.get(mutationId)
      if (
        !operation ||
        operation.principalKey !== ticket.principalKey ||
        operation.locationId !== context.selectedLocationId
      )
        return undefined
      requireCapability(context, entityCapability(operation.entityType, 'read'))
      return {
        operation,
        delivery: await this.db.operationDelivery.get(mutationId),
        events: await this.db.operationEvents.where('mutationId').equals(mutationId).toArray(),
      }
    })
  }

  private async putDelivery(delivery: OperationDelivery): Promise<void> {
    await this.db.operationDelivery.put({
      ...delivery,
      dispatchable: replayableStates.has(delivery.state) || delivery.state === 'inflight' ? 1 : 0,
      unresolved: delivery.state === 'applied' ? 0 : 1,
      blocked: heldDependencyStates.has(delivery.state) ? 1 : 0,
      resultVersion:
        delivery.state === 'applied' && delivery.result?.status === 'applied'
          ? delivery.result.entity_version
          : 0,
    })
  }

  private async event(
    mutationId: string,
    kind: OperationEvent['kind'],
    attemptId: string | null,
    details: Record<string, unknown>,
  ): Promise<void> {
    await this.db.operationEvents.add({
      mutationId,
      kind,
      attemptId,
      occurredAt: new Date(this.dependencies.now()).toISOString(),
      details,
    })
  }

  async listDispatchable(ticket: ContextTicket, limit: number): Promise<DispatchBatch> {
    ticket = structuredClone(ticket)
    if (!Number.isSafeInteger(limit) || limit < 1 || limit > 100)
      throw new Error('Invalid dispatch limit')
    return this.run(ticket, true, async ({ context, control }) => {
      requireCapability(context, 'sync.push')
      if (control.dispatchAttemptId)
        throw new Error('A dispatcher already owns the current attempt')
      const attemptId = this.dependencies.newId()
      const operations: OwnedOperation[] = []
      // Scan at most one bounded metadata page, never the immutable lifetime journal.
      const candidates = (after: number) =>
        this.db.operationDelivery
          .where('[principalKey+locationId+dispatchable+localSequence]')
          .between(
            [ticket.principalKey, context.selectedLocationId, 1, after],
            [ticket.principalKey, context.selectedLocationId, 1, Number.MAX_SAFE_INTEGER],
            false,
            true,
          )
          .limit(100)
          .toArray()
      let page = await candidates(control.dispatchScanAfter ?? 0)
      if (!page.length && control.dispatchScanAfter) page = await candidates(0)
      let scanAfter = 0
      for (const delivery of page) {
        scanAfter = delivery.localSequence
        if (delivery.retryAt > this.dependencies.now()) continue
        if (delivery.state === 'inflight' && delivery.deviceGeneration !== ticket.deviceGeneration)
          delivery.state = 'awaiting_confirmation'
        if (!replayableStates.has(delivery.state)) continue
        const operation = await this.db.operationJournal.get(delivery.mutationId)
        if (
          !operation ||
          operation.principalKey !== ticket.principalKey ||
          operation.locationId !== context.selectedLocationId ||
          operation.entityType !== delivery.entityType ||
          operation.entityId !== delivery.entityId ||
          operation.localSequence !== delivery.localSequence
        )
          throw new Error('Invalid indexed operation delivery metadata')
        const aggregatePrefix = [
          ticket.principalKey,
          context.selectedLocationId,
          operation.entityType,
          operation.entityId,
          1,
        ]
        const first = await this.db.operationDelivery
          .where('[principalKey+locationId+entityType+entityId+unresolved+localSequence]')
          .between(
            [...aggregatePrefix, 0],
            [...aggregatePrefix, Number.MAX_SAFE_INTEGER],
            true,
            true,
          )
          .first()
        const earlier = first && first.mutationId !== operation.mutationId ? first.state : undefined
        let held: OperationDelivery['state'] | null = null
        if (!operationIntact(operation)) held = 'held_integrity'
        else if (!context.capabilities.includes(entityCapability(operation.entityType, 'write')))
          held = 'held_authorization'
        if (earlier && heldDependencyStates.has(earlier)) held = 'held_dependency'
        let dependenciesPending = false
        for (const dependencyId of operation.dependsOn) {
          const parent = await this.db.operationJournal.get(dependencyId)
          const state = await this.db.operationDelivery.get(dependencyId)
          if (
            !parent ||
            parent.principalKey !== operation.principalKey ||
            parent.locationId !== operation.locationId ||
            !state ||
            heldDependencyStates.has(state.state)
          )
            held = 'held_dependency'
          if (state?.state !== 'applied') dependenciesPending = true
        }
        if (held) {
          await this.putDelivery({ ...delivery, state: held })
          await this.event(operation.mutationId, 'held', attemptId, { reason: held })
          continue
        }
        // Earlier unresolved work blocks later work, including held work and backoff.
        if (dependenciesPending || earlier || operations.length >= limit) {
          await this.putDelivery(delivery)
          continue
        }
        await this.putDelivery({
          ...delivery,
          state: 'inflight',
          attemptId,
          deviceGeneration: ticket.deviceGeneration,
          attempts: delivery.attempts + 1,
        })
        await this.event(operation.mutationId, 'dispatch', attemptId, {
          principalKey: operation.principalKey,
          generation: ticket.deviceGeneration,
          envelopeCanonical: operation.envelopeCanonical,
        })
        operations.push(operation)
        if (operations.length === limit) break
      }
      await this.db.deviceControl.put({
        ...control,
        dispatchAttemptId: operations.length ? attemptId : null,
        dispatchScanAfter: page.length < 100 && operations.length < limit ? 0 : scanAfter,
      })
      return { ticket: structuredClone(ticket), attemptId, operations }
    })
  }

  private async validateBatch(
    ticket: ContextTicket,
    batch: DispatchBatch,
    control: DeviceControl,
  ): Promise<OwnedOperation[]> {
    if (
      canonicalJson(ticket) !== canonicalJson(batch.ticket) ||
      control.dispatchAttemptId !== batch.attemptId ||
      batch.operations.length === 0
    )
      throw new Error('Dispatch attempt fenced or mismatched')
    const operations: OwnedOperation[] = []
    const ids = new Set<string>()
    for (const captured of batch.operations) {
      const operation = await this.db.operationJournal.get(captured.mutationId)
      const delivery = await this.db.operationDelivery.get(captured.mutationId)
      if (
        !operation ||
        !operationIntact(operation) ||
        canonicalJson(operation) !== canonicalJson(captured) ||
        operation.principalKey !== ticket.principalKey ||
        ids.has(operation.mutationId) ||
        delivery?.state !== 'inflight' ||
        delivery.attemptId !== batch.attemptId ||
        delivery.deviceGeneration !== ticket.deviceGeneration
      )
        throw new Error('Invalid captured dispatch batch')
      ids.add(operation.mutationId)
      operations.push(operation)
    }
    const count = await this.db.operationDelivery
      .where('[attemptId+deviceGeneration+state]')
      .equals([batch.attemptId, ticket.deviceGeneration, 'inflight'])
      .count()
    if (count !== operations.length) throw new Error('Invalid incomplete dispatch batch')
    return operations
  }

  async applyPushResult(
    ticket: ContextTicket,
    suppliedBatch: DispatchBatch,
    suppliedResponse: unknown,
  ): Promise<void> {
    ticket = structuredClone(ticket)
    const batch = structuredClone(suppliedBatch)
    const response = structuredClone(suppliedResponse)
    const error = await this.run(ticket, true, async ({ control }) => {
      const operations = await this.validateBatch(ticket, batch, control)
      let results
      try {
        results = validateResults(operations, response)
      } catch {
        for (const operation of operations) {
          const delivery = (await this.db.operationDelivery.get(operation.mutationId))!
          await this.putDelivery({ ...delivery, state: 'held_integrity' })
          await this.event(operation.mutationId, 'held', batch.attemptId, {
            reason: 'invalid_acknowledgement',
          })
        }
        await this.db.deviceControl.put({ ...control, dispatchAttemptId: null })
        return 'Invalid acknowledgement; attempt held without acknowledging any operation'
      }
      for (const result of results) {
        const delivery = (await this.db.operationDelivery.get(result.mutation_id))!
        await this.putDelivery({
          ...delivery,
          state: result.status === 'applied' ? 'applied' : 'rejected',
          result,
        })
        await this.event(result.mutation_id, 'result', batch.attemptId, { result })
      }
      await this.db.deviceControl.put({ ...control, dispatchAttemptId: null })
      return null
    })
    if (error) throw new Error(error)
  }

  async deferDispatch(
    ticket: ContextTicket,
    suppliedBatch: DispatchBatch,
    reason: 'transient' | 'unauthorized' | 'forbidden',
  ): Promise<void> {
    ticket = structuredClone(ticket)
    const batch = structuredClone(suppliedBatch)
    await this.run(ticket, true, async ({ control }) => {
      const operations = await this.validateBatch(ticket, batch, control)
      for (const operation of operations) {
        const delivery = (await this.db.operationDelivery.get(operation.mutationId))!
        const plan = retryPlan(delivery.attempts - 1)
        const state =
          reason !== 'transient'
            ? 'held_authorization'
            : plan.exhausted
              ? 'held_retry'
              : 'retryable'
        await this.putDelivery({
          ...delivery,
          state,
          retryAt: this.dependencies.now() + plan.delayMs,
        })
        await this.event(
          operation.mutationId,
          reason === 'transient' ? 'retry' : 'held',
          batch.attemptId,
          { reason },
        )
      }
      await this.db.deviceControl.put({
        ...control,
        dispatchAttemptId: null,
        state:
          reason === 'unauthorized'
            ? 'LOCKED'
            : reason === 'forbidden'
              ? 'VERIFYING'
              : control.state,
      })
    })
  }
}

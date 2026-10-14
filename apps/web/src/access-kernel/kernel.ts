import { IncrementalTransactions } from './incremental-store.js'
import type { IncrementalRequest } from './incremental-state.js'
import {
  createAdmission,
  validateAdmission,
  type RememberedAdmission,
} from './session-admission.js'
import {
  entityPage,
  operationPage,
  issuePage,
  eventPage,
  type EntityPageOptions,
  type HistoryPageOptions,
} from './queries.js'
import { BaselineTransactions } from './baseline-store.js'
import type { BaselineRequest } from './baseline-state.js'
import type { ContextRequestIdentity } from './server-context.js'
import { completedBaseline } from './baseline-state.js'
import type { EntityType } from '../sync/types.js'
import { retryPlan } from '../sync/retry-policy.js'
import type { KernelDatabase } from './database.js'
import {
  readProjection,
  replayableStates,
  heldDependencyStates,
  hasConfirmedEntity,
  aggregateBoundary,
} from './projection.js'
import { contextKey, nextContextState, principalKey, validateVerifiedContext } from './context.js'
import {
  canonicalJson,
  entityCapability,
  operationIntact,
  operationProvenance,
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

  async beginVerification(
    tabAttemptId: string,
    current: () => boolean = () => true,
    suppliedOwner?: ContextTicket,
  ): Promise<VerificationAttempt> {
    const expectedOwner = suppliedOwner ? structuredClone(suppliedOwner) : undefined
    if (!current()) throw new Error('Session fenced')
    if (!tabAttemptId.trim()) throw new Error('A new tab attempt is required')
    this.#sequence += 1
    this.#ticket = null // blank the local authorization boundary before any async work
    return this.db.transaction('rw', this.tables(), async () => {
      if (!current()) throw new Error('Session fenced')
      const control = (await this.db.deviceControl.get('device')) ?? this.initial()
      if (
        expectedOwner &&
        (control.generation !== expectedOwner.deviceGeneration ||
          control.tabAttemptId !== expectedOwner.tabAttemptId ||
          control.activePartitionId !== expectedOwner.partitionId)
      )
        throw new Error('Verification expected owner fenced')
      if (!Number.isSafeInteger(control.generation + 1)) throw new Error('Generation exhausted')
      control.generation += 1
      control.tabAttemptId = tabAttemptId
      control.state = nextContextState(control.state, 'verify')
      control.dispatchAttemptId = null
      await this.db.deviceControl.put(control)
      if (!current()) throw new Error('Session fenced')
      return { deviceGeneration: control.generation, tabAttemptId }
    })
  }

  async acceptVerifiedContext(
    attempt: VerificationAttempt,
    supplied: VerifiedAccessContext,
    current: () => boolean = () => true,
  ) {
    if (!current()) throw new Error('Session fenced')
    const sequence = this.#sequence
    const expectedTicket = this.#ticket ? structuredClone(this.#ticket) : null
    attempt = structuredClone(attempt)
    const context = structuredClone(supplied)
    validateVerifiedContext(context, this.dependencies.now())
    const result = await this.db.transaction('rw', this.tables(), async () => {
      if (!current()) throw new Error('Session fenced')
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
      const ticket: ContextTicket = {
        ...attempt,
        partitionId: partition.partitionId,
        principalKey: principalKey(context.principal),
        authorizationEpoch: context.authorizationEpoch,
      }
      const complete = completedBaseline(partition, context)
      if (complete) this.rebindPartition(partition, ticket)
      if (!same && oldPartition)
        await this.db.cachePartitions.put({ ...oldPartition, status: 'superseded' })
      if (!same) await this.db.cachePartitions.add(partition)
      else await this.db.cachePartitions.put(partition)
      await this.db.accessContexts.put({ partitionId: partition.partitionId, context })
      if (!same) control.dispatchScanAfter = 0
      control.activePartitionId = partition.partitionId
      control.state = nextContextState(
        control.state,
        complete ? 'verified_complete' : 'needs_baseline',
      )
      control.observedAt = this.dependencies.now()
      await this.db.deviceControl.put(control)
      await this.holdRecoveryOperations(ticket, context)
      this.checkLease(context, control.observedAt)
      if (
        !current() ||
        this.#sequence !== sequence ||
        canonicalJson(this.#ticket) !== canonicalJson(expectedTicket)
      )
        throw new Error('Session fenced')
      return {
        ticket,
        state: control.state,
        baselineSupported: context.snapshotProtocol === 'baseline-v1',
      }
    })
    await this.installTicket(result.ticket, sequence, expectedTicket, current)
    return result
  }

  private async installTicket(
    ticket: ContextTicket,
    sequence: number,
    expected: ContextTicket | null,
    isCurrent: () => boolean = () => true,
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
      !isCurrent() ||
      !Number.isFinite(this.dependencies.now()) ||
      (current !== undefined && this.dependencies.now() < current.observedAt) ||
      (record !== undefined &&
        this.dependencies.now() >= Date.parse(record.context.offlineUntil)) ||
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
  private checkLease(context: VerifiedAccessContext, observedAt: number): void {
    const now = this.dependencies.now()
    if (!Number.isFinite(now) || now < observedAt || now >= Date.parse(context.offlineUntil))
      throw new Error('Session lease expired or clock moved backward')
  }

  private rebindPartition(partition: CachePartition, ticket: ContextTicket): void {
    if (partition.baseline)
      partition.baseline = { ...partition.baseline, owner: structuredClone(ticket) }
    if (partition.incremental)
      partition.incremental = { ...partition.incremental, owner: structuredClone(ticket) }
    if (partition.sessionAdmission)
      partition.sessionAdmission = { ...partition.sessionAdmission, owner: structuredClone(ticket) }
  }

  async rememberSession(
    ticket: ContextTicket,
    sessionBindingId: string,
    current: () => boolean = () => true,
  ): Promise<RememberedAdmission> {
    ticket = structuredClone(ticket)
    return this.run(
      ticket,
      true,
      async ({ context, partition }) => {
        const admission = createAdmission(ticket, context, sessionBindingId)
        await this.db.cachePartitions.put({ ...partition, sessionAdmission: admission })
        return admission
      },
      current,
    )
  }

  async resumeOffline(
    supplied: RememberedAdmission,
    newTabAttemptId: string,
    current: () => boolean = () => true,
  ) {
    const remembered = structuredClone(supplied)
    if (!current() || typeof newTabAttemptId !== 'string' || !newTabAttemptId.trim())
      throw new Error('Offline admission fenced')
    const sequence = ++this.#sequence
    this.#ticket = null
    const result = await this.db.transaction('rw', this.tables(), async () => {
      if (!current() || this.#sequence !== sequence) throw new Error('Offline admission fenced')
      const control = await this.db.deviceControl.get('device')
      const partitionId = remembered?.owner?.partitionId
      if (typeof partitionId !== 'string') throw new Error('Missing offline admission')
      const partition = await this.db.cachePartitions.get(partitionId)
      const record = await this.db.accessContexts.get(partitionId)
      if (!control || !partition || !record) throw new Error('Missing offline admission')
      const admission = validateAdmission(remembered, partition, record.context)
      if (
        canonicalJson(partition.sessionAdmission ?? null) !== canonicalJson(admission) ||
        control.generation !== admission.owner.deviceGeneration ||
        control.tabAttemptId !== admission.owner.tabAttemptId ||
        control.activePartitionId !== partitionId ||
        !['READY', 'OFFLINE_READY'].includes(control.state) ||
        !completedBaseline(partition, record.context) ||
        canonicalJson(partition.baseline?.owner) !== canonicalJson(admission.owner)
      )
        throw new Error('Offline admission owner or completed proof fenced')
      const now = this.dependencies.now()
      validateVerifiedContext(record.context, now)
      if (now < control.observedAt) throw new Error('Offline admission clock moved backward')
      if (!Number.isSafeInteger(control.generation + 1)) throw new Error('Generation exhausted')
      const ticket = {
        ...admission.owner,
        deviceGeneration: control.generation + 1,
        tabAttemptId: newTabAttemptId,
      }
      this.rebindPartition(partition, ticket)
      const nextAdmission = createAdmission(ticket, record.context, admission.sessionBindingId)
      partition.sessionAdmission = nextAdmission
      await this.db.cachePartitions.put(partition)
      await this.db.deviceControl.put({
        ...control,
        generation: ticket.deviceGeneration,
        tabAttemptId: newTabAttemptId,
        state: 'OFFLINE_READY',
        observedAt: now,
        dispatchAttemptId: null,
      })
      if (!current() || this.#sequence !== sequence) throw new Error('Offline admission fenced')
      this.checkLease(record.context, now)
      return { ticket, context: record.context, admission: nextAdmission }
    })
    await this.installTicket(result.ticket, sequence, null, current)
    return result
  }

  async inspectSession(ticket: ContextTicket, current: () => boolean = () => true) {
    return this.run(
      structuredClone(ticket),
      false,
      async ({ context, control }) => ({
        context,
        state: control.state,
        observedAt: control.observedAt,
      }),
      current,
    )
  }

  private async holdRecoveryOperations(
    ticket: ContextTicket,
    context: VerifiedAccessContext,
  ): Promise<void> {
    let after = 0
    while (true) {
      const page = await this.db.operationDelivery
        .where('[principalKey+locationId+localSequence]')
        .between(
          [ticket.principalKey, context.selectedLocationId, after],
          [ticket.principalKey, context.selectedLocationId, Number.MAX_SAFE_INTEGER],
          false,
          true,
        )
        .limit(100)
        .toArray()
      for (const delivery of page) {
        const operation = await this.db.operationJournal.get(delivery.mutationId)
        if (
          !operation ||
          operation.principalKey !== ticket.principalKey ||
          operation.locationId !== context.selectedLocationId
        )
          throw new Error('Invalid recovery operation metadata')
        let held: OperationDelivery['state'] | null = !operationProvenance(operation, context)
          ? 'held_recovery'
          : null
        if (!held && delivery.state !== 'held_recovery') {
          for (const id of operation.dependsOn) {
            const parent = await this.db.operationJournal.get(id)
            const parentDelivery = await this.db.operationDelivery.get(id)
            if (
              !parent ||
              !operationProvenance(parent, context) ||
              parentDelivery?.state === 'held_recovery' ||
              parentDelivery?.state === 'held_dependency'
            )
              held = 'held_dependency'
          }
        }
        if (held && held !== delivery.state) {
          await this.putDelivery({ ...delivery, state: held })
          await this.event(operation.mutationId, 'held', null, { reason: held })
        }
      }
      if (page.length < 100) break
      after = page[page.length - 1]!.localSequence
    }
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

  private incrementals() {
    return new IncrementalTransactions(this.db, this.dependencies.now, (ticket) =>
      this.live(ticket),
    )
  }
  async pendingIncremental(ticket: ContextTicket, current: () => boolean = () => true) {
    const result = await this.incrementals().pending(ticket, current)
    if (!current() || !this.live(ticket)) throw new Error('Incremental session fenced')
    return result
  }
  async commitIncrementalPage(
    ticket: ContextTicket,
    request: IncrementalRequest,
    response: unknown,
    identity: ContextRequestIdentity,
    current: () => boolean = () => true,
  ) {
    const result = await this.incrementals().commit(ticket, request, response, identity, current)
    if (!current() || !this.live(ticket)) throw new Error('Incremental session fenced')
    return result
  }
  async retryIncremental(
    ticket: ContextTicket,
    request: IncrementalRequest,
    current: () => boolean = () => true,
  ) {
    await this.incrementals().retry(ticket, request, current)
    if (!current() || !this.live(ticket)) throw new Error('Incremental session fenced')
  }
  async holdIncremental(
    ticket: ContextTicket,
    request: IncrementalRequest,
    reason: string,
    retryAt: number | null = null,
    current: () => boolean = () => true,
  ) {
    if (!current() || !this.live(ticket)) return false
    return this.incrementals().hold(ticket, request, reason, retryAt, current)
  }
  disableIncrementalSession(ticket: ContextTicket, current: () => boolean): void {
    this.disableBaselineSession(ticket, current)
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
      canonicalJson(partition.baseline?.owner) !== canonicalJson(ticket) ||
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
    current: () => boolean = () => true,
  ): Promise<T> {
    if (!current() || !this.live(ticket))
      throw new Error('Session fenced: no matching verified session in this kernel instance')
    const outcome = await this.db.transaction('rw', this.tables(), async () => {
      if (!current() || !this.live(ticket)) throw new Error('Session fenced')
      const authorized = await this.authorized(ticket, online)
      if (!current() || !this.live(ticket)) throw new Error('Session fenced')
      if (typeof authorized === 'string') return { ok: false as const, error: authorized }
      const value = await action(authorized)
      this.checkLease(authorized.context, authorized.control.observedAt)
      if (!current() || !this.live(ticket)) throw new Error('Session fenced')
      return { ok: true as const, value }
    })
    if (!outcome.ok) throw new Error(outcome.error)
    if (!current() || !this.live(ticket))
      throw new Error('Session fenced while transaction completed')
    return outcome.value
  }

  async continueOffline(ticket: ContextTicket, current: () => boolean = () => true): Promise<void> {
    ticket = structuredClone(ticket)
    await this.run(
      ticket,
      false,
      async ({ control }) => {
        if (control.state === 'OFFLINE_READY') return
        await this.db.deviceControl.put({
          ...control,
          state: nextContextState(control.state, 'offline'),
        })
      },
      current,
    )
  }

  async commitLocalCommand(
    ticket: ContextTicket,
    supplied: LocalCommand,
    current: () => boolean = () => true,
  ): Promise<string> {
    return (await this.commitLocalCommands(ticket, [supplied], current))[0]!
  }

  async commitLocalCommands(
    ticket: ContextTicket,
    supplied: readonly LocalCommand[],
    current: () => boolean = () => true,
  ): Promise<string[]> {
    ticket = structuredClone(ticket)
    if (!Array.isArray(supplied) || supplied.length < 1 || supplied.length > 10)
      throw new Error('Invalid grouped command limit')
    const commands = structuredClone(supplied)
    if (new Set(commands.map((command) => command.envelope.mutation_id)).size !== commands.length)
      throw new Error('Invalid grouped command limit or duplicate ID')
    return this.run(
      ticket,
      false,
      async (authorized) => {
        const ids: string[] = []
        for (const command of commands) {
          ids.push(await this.commitCommand(ticket, command, authorized))
        }
        return ids
      },
      current,
    )
  }

  private async commitCommand(
    ticket: ContextTicket,
    command: LocalCommand,
    { context, control }: Authorized,
  ): Promise<string> {
    const envelopeCanonical = validateCommand(command, context)
    const existing = await this.db.operationJournal.get(command.envelope.mutation_id)
    const dependencies = new Set(command.dependsOn)
    const references: [EntityType, unknown][] = []
    if (command.envelope.entity_type !== 'customer')
      references.push(['customer', command.optimistic.customer_id])
    if (command.envelope.entity_type === 'service_order')
      references.push(['bicycle', command.optimistic.bicycle_id])
    if (command.envelope.operation === 'update')
      references.push([command.envelope.entity_type, command.envelope.entity_id])
    for (const [entityType, entityId] of references) {
      if (typeof entityId !== 'string' || !entityId) continue
      const prefix = [ticket.principalKey, context.selectedLocationId, entityType, entityId]
      const predecessor = await this.db.operationJournal
        .where('[principalKey+locationId+entityType+entityId+localSequence]')
        .between(
          [...prefix, 0],
          [...prefix, existing?.localSequence ?? Number.MAX_SAFE_INTEGER],
          true,
          false,
        )
        .reverse()
        .first()
      if (predecessor) {
        const confirmed = await hasConfirmedEntity(
          this.db,
          ticket.partitionId,
          context,
          entityType,
          entityId,
        )
        const aggregate =
          entityType === command.envelope.entity_type && entityId === command.envelope.entity_id
        // A confirmed reference is independent of unrelated local edits. Exact-ID
        // retries retain only dependencies that were present when originally authored.
        if (
          confirmed &&
          (!aggregate || !operationProvenance(predecessor, context)) &&
          (!existing || !existing.dependsOn.includes(predecessor.mutationId))
        )
          continue
        dependencies.add(predecessor.mutationId)
      }
    }
    command.dependsOn = [...dependencies]
    if (existing) {
      const localEvents = (await eventPage(this.db, existing.mutationId, { limit: 100 })).items
        .filter((event) => event.kind === 'local')
        .map((event) => event.details)
      if (
        !operationProvenance(existing, context) ||
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
    if (command.envelope.operation === 'update') {
      const projection = await readProjection(
        this.db,
        ticket,
        context,
        command.envelope.entity_type,
        command.envelope.entity_id,
      )
      const current = projection?.optimistic ?? projection?.confirmed
      if (!current || current.version !== command.envelope.base_version)
        throw new Error('Local aggregate version changed')
    }
    for (const id of command.dependsOn) {
      const parent = await this.db.operationJournal.get(id)
      if (
        !parent ||
        parent.principalKey !== ticket.principalKey ||
        parent.locationId !== context.selectedLocationId ||
        !operationProvenance(parent, context)
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
      authoredDatasetIncarnation: context.datasetIncarnation,
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
    control.localSequence = operation.localSequence
    await this.db.deviceControl.put(control)
    return operation.mutationId
  }

  async readEntity(
    ticket: ContextTicket,
    entityType: EntityType,
    entityId: string,
    current: () => boolean = () => true,
  ) {
    ticket = structuredClone(ticket)
    return this.run(
      ticket,
      false,
      ({ context }) => readProjection(this.db, ticket, context, entityType, entityId),
      current,
    )
  }

  async readOperation(
    ticket: ContextTicket,
    mutationId: string,
    current: () => boolean = () => true,
  ) {
    ticket = structuredClone(ticket)
    return this.run(
      ticket,
      false,
      async ({ context }) => {
        const operation = await this.db.operationJournal.get(mutationId)
        if (
          !operation ||
          operation.principalKey !== ticket.principalKey ||
          operation.locationId !== context.selectedLocationId
        )
          return undefined
        requireCapability(context, entityCapability(operation.entityType, 'read'))
        const events = await eventPage(this.db, mutationId, { limit: 100 })
        return {
          operation,
          delivery: await this.db.operationDelivery.get(mutationId),
          events: events.items,
          eventsNextAfterSequence: events.nextAfterSequence,
        }
      },
      current,
    )
  }

  async listEntities(
    ticket: ContextTicket,
    entityType: EntityType,
    options: EntityPageOptions,
    current: () => boolean = () => true,
  ) {
    ticket = structuredClone(ticket)
    options = structuredClone(options)
    return this.run(
      ticket,
      false,
      ({ context }) => entityPage(this.db, ticket, context, entityType, options),
      current,
    )
  }
  async listIssues(
    ticket: ContextTicket,
    options: HistoryPageOptions,
    current: () => boolean = () => true,
  ) {
    ticket = structuredClone(ticket)
    options = structuredClone(options)
    return this.run(
      ticket,
      false,
      ({ context }) => issuePage(this.db, ticket, context, options),
      current,
    )
  }
  async listOperations(
    ticket: ContextTicket,
    options: HistoryPageOptions,
    current: () => boolean = () => true,
  ) {
    ticket = structuredClone(ticket)
    options = structuredClone(options)
    return this.run(
      ticket,
      false,
      ({ context }) => operationPage(this.db, ticket, context, options),
      current,
    )
  }
  async listOperationHistory(
    ticket: ContextTicket,
    entityType: EntityType,
    entityId: string,
    options: HistoryPageOptions,
    current: () => boolean = () => true,
  ) {
    ticket = structuredClone(ticket)
    options = structuredClone(options)
    return this.run(
      ticket,
      false,
      ({ context }) => operationPage(this.db, ticket, context, options, { entityType, entityId }),
      current,
    )
  }
  async listOperationEvents(
    ticket: ContextTicket,
    mutationId: string,
    options: HistoryPageOptions,
    current: () => boolean = () => true,
  ) {
    ticket = structuredClone(ticket)
    options = structuredClone(options)
    return this.run(
      ticket,
      false,
      async ({ context }) => {
        const operation = await this.db.operationJournal.get(mutationId)
        if (
          !operation ||
          operation.principalKey !== ticket.principalKey ||
          operation.locationId !== context.selectedLocationId
        )
          return { items: [], nextAfterSequence: null }
        requireCapability(context, entityCapability(operation.entityType, 'read'))
        return eventPage(this.db, mutationId, options)
      },
      current,
    )
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

  async listDispatchable(
    ticket: ContextTicket,
    limit: number,
    current: () => boolean = () => true,
  ): Promise<DispatchBatch> {
    ticket = structuredClone(ticket)
    if (!Number.isSafeInteger(limit) || limit < 1 || limit > 100)
      throw new Error('Invalid dispatch limit')
    return this.run(
      ticket,
      true,
      async ({ context, control }) => {
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
          if (
            delivery.state === 'inflight' &&
            delivery.deviceGeneration !== ticket.deviceGeneration
          )
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
          ]
          const confirmed = await hasConfirmedEntity(
            this.db,
            ticket.partitionId,
            context,
            operation.entityType,
            operation.entityId,
          )
          const first = await aggregateBoundary(
            this.db,
            context,
            aggregatePrefix,
            'unresolved',
            confirmed,
          )
          const earlier =
            first && first.mutationId !== operation.mutationId ? first.state : undefined
          let held: OperationDelivery['state'] | null = null
          if (!operationProvenance(operation, context)) held = 'held_recovery'
          else if (!operationIntact(operation)) held = 'held_integrity'
          else if (!context.capabilities.includes(entityCapability(operation.entityType, 'write')))
            held = 'held_authorization'
          if (earlier && heldDependencyStates.has(earlier)) held = 'held_dependency'
          let dependenciesPending = false
          for (const dependencyId of operation.dependsOn) {
            const parent = await this.db.operationJournal.get(dependencyId)
            const state = await this.db.operationDelivery.get(dependencyId)
            if (
              !parent ||
              !operationProvenance(parent, context) ||
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
      },
      current,
    )
  }

  private async validateBatch(
    ticket: ContextTicket,
    batch: DispatchBatch,
    control: DeviceControl,
    context: VerifiedAccessContext,
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
        !operationProvenance(operation, context) ||
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
    current: () => boolean = () => true,
  ): Promise<void> {
    ticket = structuredClone(ticket)
    const batch = structuredClone(suppliedBatch)
    const response = structuredClone(suppliedResponse)
    const error = await this.run(
      ticket,
      true,
      async ({ control, context }) => {
        const operations = await this.validateBatch(ticket, batch, control, context)
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
            state:
              result.status === 'applied'
                ? 'applied'
                : result.error_code === 'legacy_receipt_unverified'
                  ? 'held_recovery'
                  : ['receipt_integrity_conflict', 'receipt_proof_conflict'].includes(
                        result.error_code ?? '',
                      )
                    ? 'held_integrity'
                    : 'rejected',
            result,
          })
          await this.event(result.mutation_id, 'result', batch.attemptId, { result })
        }
        await this.db.deviceControl.put({ ...control, dispatchAttemptId: null })
        return null
      },
      current,
    )
    if (error) throw new Error(error)
  }

  async deferDispatch(
    ticket: ContextTicket,
    suppliedBatch: DispatchBatch,
    reason:
      'transient' | 'unauthorized' | 'forbidden' | 'upgrade' | 'context_changed' | 'integrity',
    current: () => boolean = () => true,
  ): Promise<void> {
    ticket = structuredClone(ticket)
    const batch = structuredClone(suppliedBatch)
    await this.run(
      ticket,
      true,
      async ({ control, context }) => {
        const operations = await this.validateBatch(ticket, batch, control, context)
        for (const operation of operations) {
          const delivery = (await this.db.operationDelivery.get(operation.mutationId))!
          const plan = retryPlan(delivery.attempts - 1)
          const state =
            reason !== 'transient'
              ? reason === 'integrity'
                ? 'held_integrity'
                : 'held_authorization'
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
              : reason === 'forbidden' || reason === 'context_changed'
                ? 'VERIFYING'
                : reason === 'upgrade' || reason === 'integrity'
                  ? 'HELD'
                  : control.state,
        })
      },
      current,
    )
  }
}

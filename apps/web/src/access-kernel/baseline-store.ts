import type { KernelDatabase } from './database.js'
import { contextKey, validateVerifiedContext } from './context.js'
import { canonicalJson, requireCapability } from './operations.js'
import {
  validateBaselineMetadata,
  type BaselineMetadata,
  type BaselineRequest,
} from './baseline-state.js'
import {
  validateBaselineResponse,
  validateBaselineRecord,
  type BaselineBinding,
  type BaselineRecord,
} from './baseline-wire.js'
import type { ContextRequestIdentity } from './server-context.js'
import type { CachePartition, ContextTicket, VerifiedAccessContext } from './types.js'

/** Durable protocol primitives. Ordinary entry/admission lives in AccessKernel;
 * the isolated qualification harness can exercise staging with actual null wire contexts.
 * No primitive permits activating a null-protocol context. No network inside transactions.
 */
export class BaselineTransactions {
  constructor(
    private readonly db: KernelDatabase,
    private readonly now: () => number,
    private readonly newId: () => string,
    private readonly isCurrent: (ticket: ContextTicket) => boolean = () => true,
  ) {}
  private tables() {
    return [
      this.db.deviceControl,
      this.db.cachePartitions,
      this.db.accessContexts,
      this.db.cacheRecords,
    ]
  }
  private async fenced(ticket: ContextTicket) {
    const control = await this.db.deviceControl.get('device')
    const partition = await this.db.cachePartitions.get(ticket.partitionId)
    const record = await this.db.accessContexts.get(ticket.partitionId)
    if (
      !control ||
      !partition ||
      !record ||
      control.generation !== ticket.deviceGeneration ||
      control.tabAttemptId !== ticket.tabAttemptId ||
      control.activePartitionId !== ticket.partitionId ||
      partition.status === 'superseded' ||
      partition.principalKey !== ticket.principalKey ||
      partition.authorizationEpoch !== ticket.authorizationEpoch ||
      record.context.authorizationEpoch !== ticket.authorizationEpoch ||
      partition.locationId !== record.context.selectedLocationId ||
      partition.policyRevision !== record.context.policyRevision ||
      !['BASELINE_REQUIRED', 'SNAPSHOTTING', 'CATCHING_UP', 'HELD', 'READY'].includes(control.state)
    )
      throw new Error('Baseline ticket fenced')
    validateVerifiedContext(record.context, this.now())
    if (this.now() < control.observedAt) throw new Error('Baseline clock moved backward')
    requireCapability(record.context, 'sync.pull')
    if (!this.isCurrent(ticket)) throw new Error('Baseline local ticket fenced')
    return { control, partition, context: record.context }
  }
  async begin(supplied: ContextTicket): Promise<ContextTicket> {
    const expected = structuredClone(supplied)
    return this.db.transaction('rw', this.tables(), async () => {
      const { control, partition, context } = await this.fenced(expected)
      const partitionId = this.newId(),
        requestId = this.newId()
      const ticket = { ...expected, partitionId }
      const startBody = canonicalJson({
        protocol: 1,
        selected_location_id: context.selectedLocationId,
        authorization_epoch: context.authorizationEpoch,
        request_id: requestId,
      })
      const baseline: BaselineMetadata = {
        format: 1,
        binding: contextKey(context),
        datasetIncarnation: context.datasetIncarnation,
        origin: ticket,
        owner: ticket,
        requestId,
        startBody,
        startResponse: null,
        baselineId: null,
        expiresAt: null,
        phase: 'start_pending',
        next: { kind: 'start', body: startBody },
        checkpoint: null,
        receipt: null,
        retryCount: 0,
        hold: null,
      }
      const fresh: CachePartition = {
        ...partition,
        partitionId,
        status: 'staging',
        baselineComplete: false,
        cursor: null,
        baseline,
      }
      validateBaselineMetadata(fresh, context)
      await this.db.cachePartitions.put({ ...partition, status: 'superseded' })
      await this.db.cachePartitions.add(fresh)
      await this.db.accessContexts.add({ partitionId, context })
      await this.db.deviceControl.put({
        ...control,
        activePartitionId: partitionId,
        state: 'SNAPSHOTTING',
        dispatchAttemptId: null,
        dispatchScanAfter: 0,
        observedAt: this.now(),
      })
      return ticket
    })
  }
  async pending(supplied: ContextTicket) {
    const ticket = structuredClone(supplied)
    return this.db.transaction('rw', this.tables(), async () => {
      const { partition, context } = await this.fenced(ticket)
      const baseline = validateBaselineMetadata(partition, context)
      if (canonicalJson(baseline.owner) !== canonicalJson(ticket))
        throw new Error('Baseline ownership fenced')
      return { context, baseline: structuredClone(baseline) }
    })
  }
  async resume(supplied: ContextTicket): Promise<void> {
    const ticket = structuredClone(supplied)
    await this.db.transaction('rw', this.tables(), async () => {
      const { control, partition, context } = await this.fenced(ticket)
      const baseline = validateBaselineMetadata(partition, context)
      if (baseline.phase === 'active' || !baseline.next)
        throw new Error('No incomplete baseline to resume')
      if (
        baseline.hold &&
        [
          'baseline_expired',
          'checkpoint_expired',
          'continuation_stale',
          'dataset_changed',
          'projection_too_large',
          'cursor_invalid',
          'unsupported_protocol',
          'invalid_response',
          'invalid_request',
        ].includes(baseline.hold.reason)
      )
        throw new Error('Fresh baseline required after terminal hold')
      // Local phase can lag a server-completed family after a lost response.
      // Replay the exact pending request; only authenticated server 410 proves expiry.
      // Only fresh verification changes ownership; a different bound context cannot resume.
      if (control.state !== 'BASELINE_REQUIRED')
        throw new Error('Fresh verification required to resume')
      await this.db.cachePartitions.put({
        ...partition,
        baseline: { ...baseline, owner: ticket, hold: null },
      })
      await this.db.deviceControl.put({
        ...control,
        state: ['catching_up', 'activation_pending'].includes(baseline.phase)
          ? 'CATCHING_UP'
          : 'SNAPSHOTTING',
        observedAt: this.now(),
      })
    })
  }
  async commit(
    supplied: ContextTicket,
    expectedRequest: BaselineRequest,
    suppliedResponse: unknown,
    suppliedIdentity: ContextRequestIdentity,
    current: () => boolean = () => true,
  ): Promise<'committed' | 'duplicate'> {
    const ticket = structuredClone(supplied),
      request = structuredClone(expectedRequest),
      response = structuredClone(suppliedResponse),
      identity = structuredClone(suppliedIdentity)
    return this.db.transaction('rw', this.tables(), async () => {
      const { control, partition, context } = await this.fenced(ticket)
      const baseline = validateBaselineMetadata(partition, context)
      if (!current()) throw new Error('Baseline session fenced')
      if (
        canonicalJson(baseline.owner) !== canonicalJson(ticket) ||
        identity.deviceGeneration !== ticket.deviceGeneration ||
        identity.tabAttemptId !== ticket.tabAttemptId ||
        identity.apiRealm !== context.principal.apiRealm ||
        identity.organizationId !== context.principal.organizationId ||
        identity.userId !== context.principal.userId ||
        identity.selectedLocationId !== context.selectedLocationId ||
        (identity.expectedAuthorizationEpoch !== undefined &&
          identity.expectedAuthorizationEpoch !== context.authorizationEpoch)
      )
        throw new Error('Baseline identity fenced')
      const body = JSON.parse(request.body) as { continuation?: string; checkpoint?: string }
      const binding: BaselineBinding = {
        context,
        identity,
        ...(baseline.baselineId ? { baselineId: baseline.baselineId } : {}),
        ...(body.continuation ? { predecessor: body.continuation } : {}),
      }
      if (canonicalJson(baseline.next) !== canonicalJson(request)) {
        if (
          request.kind !== 'start' &&
          request.kind !== 'activation' &&
          baseline.receipt?.kind === request.kind &&
          baseline.receipt.predecessor === body.continuation &&
          baseline.receipt.response ===
            canonicalJson(validateBaselineResponse(request.kind, response, binding, this.now()))
        )
          return 'duplicate'
        throw new Error('Stale baseline response')
      }
      if (baseline.hold) throw new Error('Baseline attempt held')
      if (request.kind === 'activation') throw new Error('Use separately fenced activation')
      let next: BaselineMetadata
      let records: BaselineRecord[] = []
      if (request.kind === 'start') {
        const value = validateBaselineResponse('start', response, binding, this.now())
        const startResponse = canonicalJson(value)
        if (new TextEncoder().encode(startResponse).length > 16384)
          throw new Error('Oversized baseline start evidence')
        next = {
          ...baseline,
          startResponse,
          baselineId: value.baseline_id,
          expiresAt: value.expires_at,
          phase: 'scan',
          next: {
            kind: 'scan',
            body: canonicalJson({ protocol: 1, continuation: value.continuation }),
          },
        }
      } else if (request.kind === 'scan') {
        const value = validateBaselineResponse('scan', response, binding, this.now())
        records = value.records
        next = {
          ...baseline,
          phase: value.phase === 'scan_complete' ? 'finalize_pending' : 'scan',
          next: {
            kind: value.phase === 'scan_complete' ? 'finalize' : 'scan',
            body: canonicalJson({ protocol: 1, continuation: value.continuation }),
          },
          receipt: {
            kind: request.kind,
            predecessor: value.predecessor,
            response: canonicalJson(value),
          },
        }
      } else if (request.kind === 'finalize') {
        const value = validateBaselineResponse('finalize', response, binding, this.now())
        next = {
          ...baseline,
          phase: 'catching_up',
          next: {
            kind: 'delta',
            body: canonicalJson({ protocol: 1, continuation: value.continuation }),
          },
          receipt: {
            kind: request.kind,
            predecessor: value.predecessor,
            response: canonicalJson(value),
          },
        }
      } else {
        const value = validateBaselineResponse('delta', response, binding, this.now())
        records = value.records
        next = {
          ...baseline,
          phase: value.phase === 'complete' ? 'activation_pending' : 'catching_up',
          checkpoint: value.phase === 'complete' ? value.continuation : null,
          next:
            value.phase === 'complete'
              ? {
                  kind: 'activation',
                  body: canonicalJson({ protocol: 1, checkpoint: value.continuation }),
                }
              : {
                  kind: 'delta',
                  body: canonicalJson({ protocol: 1, continuation: value.continuation }),
                },
          receipt: {
            kind: request.kind,
            predecessor: value.predecessor,
            response: canonicalJson(value),
          },
        }
      }
      // Entire page is validated before writes; every write and continuation shares this transaction.
      for (const rawRecord of records) {
        const record = validateBaselineRecord(rawRecord, context)
        const key: [string, string, string] = [
          ticket.partitionId,
          record.entity_type,
          record.entity_id,
        ]
        const old = await this.db.cacheRecords.get(key)
        if (
          old &&
          old.version === record.entity_version &&
          canonicalJson(old.payload) !== canonicalJson(record.payload)
        )
          throw new Error('Equal-version baseline contradiction')
        if (!old || old.version < record.entity_version)
          await this.db.cacheRecords.put({
            partitionId: ticket.partitionId,
            entityType: record.entity_type,
            entityId: record.entity_id,
            version: record.entity_version,
            payload: record.payload,
          })
      }
      const updated = { ...partition, baseline: { ...next, retryCount: 0 } }
      validateBaselineMetadata(updated, context)
      await this.db.cachePartitions.put(updated)
      await this.db.deviceControl.put({
        ...control,
        state: ['catching_up', 'activation_pending'].includes(next.phase)
          ? 'CATCHING_UP'
          : 'SNAPSHOTTING',
        observedAt: this.now(),
      })
      if (!current() || !this.isCurrent(ticket)) throw new Error('Baseline session fenced')
      return 'committed'
    })
  }
  async activate(
    supplied: ContextTicket,
    checkpoint: string,
    suppliedContext: VerifiedAccessContext,
    current: () => boolean = () => true,
  ): Promise<void> {
    const ticket = structuredClone(supplied),
      fresh = structuredClone(suppliedContext)
    validateVerifiedContext(fresh, this.now())
    if (fresh.snapshotProtocol !== 'baseline-v1')
      throw new Error('Supported baseline advertisement required')
    await this.db.transaction('rw', this.tables(), async () => {
      const { control, partition, context } = await this.fenced(ticket)
      const baseline = validateBaselineMetadata(partition, context)
      if (
        context.snapshotProtocol !== 'baseline-v1' ||
        contextKey(fresh) !== contextKey(context) ||
        canonicalJson(baseline.owner) !== canonicalJson(ticket) ||
        baseline.phase !== 'activation_pending' ||
        baseline.checkpoint !== checkpoint ||
        baseline.hold !== null ||
        baseline.next?.kind !== 'activation'
      )
        throw new Error('Activation fenced')
      const updated: CachePartition = {
        ...partition,
        status: 'active',
        baselineComplete: true,
        cursor: checkpoint,
        baseline: { ...baseline, phase: 'active', next: null },
      }
      validateBaselineMetadata(updated, fresh)
      await this.db.cachePartitions.put(updated)
      await this.db.accessContexts.put({ partitionId: ticket.partitionId, context: fresh })
      await this.db.deviceControl.put({ ...control, state: 'READY', observedAt: this.now() })
      if (!current() || !this.isCurrent(ticket)) throw new Error('Activation session fenced')
    })
  }
  async retry(supplied: ContextTicket, expected: BaselineRequest): Promise<void> {
    const ticket = structuredClone(supplied),
      request = structuredClone(expected)
    await this.db.transaction('rw', this.tables(), async () => {
      const { control, partition, context } = await this.fenced(ticket)
      const baseline = validateBaselineMetadata(partition, context)
      if (
        canonicalJson(baseline.owner) !== canonicalJson(ticket) ||
        canonicalJson(baseline.next) !== canonicalJson(request) ||
        !baseline.hold ||
        baseline.hold.retryAt === null ||
        baseline.hold.retryAt > this.now() ||
        ![
          'network_error',
          'baseline_in_progress',
          'baseline_capacity',
          'temporary_unavailable',
        ].includes(baseline.hold.reason)
      )
        throw new Error('Baseline retry is not eligible')
      await this.db.cachePartitions.put({ ...partition, baseline: { ...baseline, hold: null } })
      await this.db.deviceControl.put({
        ...control,
        state: ['catching_up', 'activation_pending'].includes(baseline.phase)
          ? 'CATCHING_UP'
          : 'SNAPSHOTTING',
        observedAt: this.now(),
      })
    })
  }
  async hold(
    supplied: ContextTicket,
    expected: BaselineRequest,
    reason: string,
    retryAt: number | null = null,
    current: () => boolean = () => true,
  ): Promise<boolean> {
    const ticket = structuredClone(supplied),
      request = structuredClone(expected)
    return this.db.transaction('rw', this.tables(), async () => {
      const { control, partition, context } = await this.fenced(ticket)
      const baseline = validateBaselineMetadata(partition, context)
      if (
        !current() ||
        canonicalJson(baseline.owner) !== canonicalJson(ticket) ||
        canonicalJson(baseline.next) !== canonicalJson(request)
      )
        return false
      const updated = {
        ...partition,
        baseline: {
          ...baseline,
          retryCount: baseline.retryCount + 1,
          hold: { reason, retryAt, attempts: baseline.retryCount + 1 },
        },
      }
      validateBaselineMetadata(updated, context)
      await this.db.cachePartitions.put(updated)
      await this.db.deviceControl.put({
        ...control,
        state: reason === 'invalid_session' ? 'LOCKED' : 'HELD',
        dispatchAttemptId: null,
      })
      if (!current() || !this.isCurrent(ticket)) throw new Error('Baseline hold fenced')
      return true
    })
  }
}

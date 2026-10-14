import type { KernelDatabase } from './database.js'
import { principalKey, validateVerifiedContext } from './context.js'
import { canonicalJson, requireCapability } from './operations.js'
import { validateBaselineMetadata } from './baseline-state.js'
import { validateBaselineRecord } from './baseline-wire.js'
import {
  initialIncrementalMetadata,
  validateIncrementalMetadata,
  validateIncrementalRequest,
  incrementalTransientReasons,
  type IncrementalPartition,
  type IncrementalRequest,
} from './incremental-state.js'
import { validateIncrementalResponse } from './incremental-wire.js'
import type { ContextRequestIdentity } from './server-context.js'
import type { ContextTicket, VerifiedAccessContext } from './types.js'

/** Every projection and cursor transition is one fenced transaction; no HTTP here. */
export class IncrementalTransactions {
  constructor(
    private readonly db: KernelDatabase,
    private readonly now: () => number,
    private readonly isCurrent: (ticket: ContextTicket) => boolean = () => true,
  ) {}
  private tables() {
    return [
      this.db.deviceControl,
      this.db.accessContexts,
      this.db.cachePartitions,
      this.db.cacheRecords,
    ]
  }
  private check(ticket: ContextTicket, current: () => boolean) {
    if (!current() || !this.isCurrent(ticket)) throw new Error('Incremental session fenced')
  }
  private finalFence(
    ticket: ContextTicket,
    current: () => boolean,
    context: VerifiedAccessContext,
    observedAt: number,
  ) {
    this.check(ticket, current)
    const now = this.now()
    validateVerifiedContext(context, now)
    if (!Number.isFinite(now) || now < observedAt)
      throw new Error('Incremental clock moved backward')
  }
  private async fenced(ticket: ContextTicket, current: () => boolean) {
    this.check(ticket, current)
    const control = await this.db.deviceControl.get('device'),
      partition = (await this.db.cachePartitions.get(ticket.partitionId)) as
        IncrementalPartition | undefined,
      record = await this.db.accessContexts.get(ticket.partitionId)
    if (
      !control ||
      !partition ||
      !record ||
      control.generation !== ticket.deviceGeneration ||
      control.tabAttemptId !== ticket.tabAttemptId ||
      control.activePartitionId !== ticket.partitionId ||
      !['READY', 'OFFLINE_READY', 'HELD'].includes(control.state) ||
      partition.status !== 'active' ||
      !partition.baselineComplete ||
      partition.principalKey !== ticket.principalKey ||
      principalKey(record.context.principal) !== ticket.principalKey ||
      partition.authorizationEpoch !== ticket.authorizationEpoch ||
      record.context.authorizationEpoch !== ticket.authorizationEpoch ||
      record.context.snapshotProtocol !== 'baseline-v1'
    )
      throw new Error('Incremental ticket fenced')
    const now = this.now()
    validateVerifiedContext(record.context, now)
    if (!Number.isFinite(now) || now < control.observedAt)
      throw new Error('Incremental clock moved backward')
    requireCapability(record.context, 'sync.pull')
    const baseline = validateBaselineMetadata(partition, record.context)
    if (
      baseline.phase !== 'active' ||
      baseline.hold !== null ||
      canonicalJson(baseline.owner) !== canonicalJson(ticket)
    )
      throw new Error('Incremental ownership fenced')
    this.check(ticket, current)
    return { control, partition, context: record.context }
  }
  async pending(supplied: ContextTicket, current: () => boolean = () => true) {
    const ticket = structuredClone(supplied)
    return this.db.transaction('rw', this.tables(), async () => {
      const { control, partition, context } = await this.fenced(ticket, current)
      if (!Object.hasOwn(partition, 'incremental')) {
        partition.incremental = initialIncrementalMetadata(partition, context)
        validateIncrementalMetadata(partition, context)
        await this.db.cachePartitions.put(partition)
      }
      const incremental = validateIncrementalMetadata(partition, context)
      this.finalFence(ticket, current, context, control.observedAt)
      return { context: structuredClone(context), incremental: structuredClone(incremental) }
    })
  }
  async commit(
    supplied: ContextTicket,
    expected: IncrementalRequest,
    suppliedResponse: unknown,
    suppliedIdentity: ContextRequestIdentity,
    current: () => boolean = () => true,
  ): Promise<'committed' | 'replayed'> {
    const ticket = structuredClone(supplied),
      request = structuredClone(expected),
      response = structuredClone(suppliedResponse),
      identity = structuredClone(suppliedIdentity)
    const predecessor = validateIncrementalRequest(request)
    return this.db.transaction('rw', this.tables(), async () => {
      const { control, partition, context } = await this.fenced(ticket, current)
      const incremental = validateIncrementalMetadata(partition, context)
      if (
        identity.deviceGeneration !== ticket.deviceGeneration ||
        identity.tabAttemptId !== ticket.tabAttemptId ||
        identity.apiRealm !== context.principal.apiRealm ||
        identity.organizationId !== context.principal.organizationId ||
        identity.userId !== context.principal.userId ||
        identity.selectedLocationId !== context.selectedLocationId ||
        !identity.sessionHandle ||
        (identity.expectedAuthorizationEpoch !== undefined &&
          identity.expectedAuthorizationEpoch !== context.authorizationEpoch)
      )
        throw new Error('Incremental identity fenced')
      const value = validateIncrementalResponse(response, { context, predecessor }),
        canonical = canonicalJson(value)
      if (canonicalJson(request) !== canonicalJson(incremental.next)) {
        if (
          incremental.receipt?.requestBody === request.body &&
          incremental.receipt.predecessor === predecessor &&
          incremental.receipt.response === canonical
        ) {
          this.finalFence(ticket, current, context, control.observedAt)
          return 'replayed'
        }
        throw new Error('Stale incremental response')
      }
      if (incremental.hold !== null) throw new Error('Incremental request held')
      if (!Number.isSafeInteger(incremental.sequence + 1))
        throw new Error('Incremental sequence exhausted')
      // Validate the entire envelope before writes. Projection, receipt and successor
      // share rollback on quota, contradiction or credential replacement.
      const records = value.records.map((raw) => validateBaselineRecord(raw, context))
      const versions = new Map<string, string>()
      for (const record of records) {
        const key = canonicalJson([record.entity_type, record.entity_id, record.entity_version]),
          payload = canonicalJson(record.payload)
        if (versions.has(key) && versions.get(key) !== payload)
          throw new Error('Equal-version incremental contradiction')
        versions.set(key, payload)
      }
      for (const record of records) {
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
          throw new Error('Equal-version incremental contradiction')
        if (!old || old.version < record.entity_version)
          await this.db.cacheRecords.put({
            partitionId: ticket.partitionId,
            entityType: record.entity_type,
            entityId: record.entity_id,
            version: record.entity_version,
            payload: record.payload,
          })
      }
      const updated: IncrementalPartition = {
        ...partition,
        cursor: value.continuation,
        incremental: {
          ...incremental,
          sequence: incremental.sequence + 1,
          phase: value.phase,
          next: {
            kind: 'delta',
            body: canonicalJson({ protocol: 1, continuation: value.continuation }),
          },
          receipt: { predecessor, requestBody: request.body, response: canonical },
          retryCount: 0,
          hold: null,
        },
      }
      validateBaselineMetadata(updated, context)
      await this.db.cachePartitions.put(updated)
      const observedAt = this.now()
      await this.db.deviceControl.put({ ...control, state: 'READY', observedAt })
      this.finalFence(ticket, current, context, Math.max(control.observedAt, observedAt))
      return 'committed'
    })
  }
  async retry(
    supplied: ContextTicket,
    expected: IncrementalRequest,
    current: () => boolean = () => true,
  ): Promise<void> {
    const ticket = structuredClone(supplied),
      request = structuredClone(expected)
    await this.db.transaction('rw', this.tables(), async () => {
      const { control, partition, context } = await this.fenced(ticket, current),
        incremental = validateIncrementalMetadata(partition, context)
      if (
        canonicalJson(incremental.next) !== canonicalJson(request) ||
        !incremental.hold ||
        incremental.hold.retryAt === null ||
        incremental.hold.retryAt > this.now() ||
        !(incrementalTransientReasons as readonly string[]).includes(incremental.hold.reason)
      )
        throw new Error('Incremental retry is not eligible')
      const updated: IncrementalPartition = {
        ...partition,
        incremental: { ...incremental, hold: null },
      }
      await this.db.cachePartitions.put(updated)
      const observedAt = this.now()
      await this.db.deviceControl.put({ ...control, state: 'READY', observedAt })
      this.finalFence(ticket, current, context, Math.max(control.observedAt, observedAt))
    })
  }
  async hold(
    supplied: ContextTicket,
    expected: IncrementalRequest,
    reason: string,
    retryAt: number | null = null,
    current: () => boolean = () => true,
  ): Promise<boolean> {
    const ticket = structuredClone(supplied),
      request = structuredClone(expected)
    return this.db.transaction('rw', this.tables(), async () => {
      const { control, partition, context } = await this.fenced(ticket, current),
        incremental = validateIncrementalMetadata(partition, context)
      if (canonicalJson(incremental.next) !== canonicalJson(request)) return false
      const updated: IncrementalPartition = {
        ...partition,
        incremental: {
          ...incremental,
          retryCount: incremental.retryCount + 1,
          hold: { reason, retryAt, attempts: incremental.retryCount + 1 },
        },
      }
      validateIncrementalMetadata(updated, context)
      await this.db.cachePartitions.put(updated)
      const observedAt = this.now()
      await this.db.deviceControl.put({
        ...control,
        state: reason === 'invalid_session' ? 'LOCKED' : 'HELD',
        dispatchAttemptId: null,
        observedAt,
      })
      this.finalFence(ticket, current, context, Math.max(control.observedAt, observedAt))
      return true
    })
  }
}

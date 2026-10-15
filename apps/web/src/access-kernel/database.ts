import type { Table } from 'dexie'
import type { BrandingSnapshot } from '../branding/cache.js'
import { OcwpDatabase } from '../local/database.js'
import type {
  AccessContextRecord,
  CachePartition,
  CacheRecord,
  DeviceControl,
  LocalMigrationState,
  OperationDelivery,
  OperationEvent,
  OwnedOperation,
} from './types.js'

/** Side-effect-free scoped factory. The legacy ocwp database is never opened here. */
export class KernelDatabase extends OcwpDatabase {
  brandingSnapshots!: Table<BrandingSnapshot, string>
  deviceControl!: Table<DeviceControl, string>
  accessContexts!: Table<AccessContextRecord, string>
  cachePartitions!: Table<CachePartition, string>
  cacheRecords!: Table<CacheRecord, [string, string, string]>
  operationJournal!: Table<OwnedOperation, string>
  operationDelivery!: Table<OperationDelivery, string>
  operationEvents!: Table<OperationEvent, number>
  localMigrationState!: Table<LocalMigrationState, string>

  constructor(name: string) {
    if (typeof name !== 'string' || !name.trim() || name === 'ocwp')
      throw new Error('A distinct authenticated database name is required')
    super(name)
    this.version(5)
      .stores({
        deviceControl: 'key',
        accessContexts: 'partitionId',
        cachePartitions: 'partitionId, principalKey',
        cacheRecords: '[partitionId+entityType+entityId], [partitionId+entityType]',
        operationJournal:
          'mutationId, [principalKey+locationId], localSequence, [principalKey+locationId+entityType+entityId]',
        operationDelivery:
          'mutationId, state, [principalKey+locationId+dispatchable+localSequence], [principalKey+locationId+entityType+entityId+unresolved+localSequence], [attemptId+deviceGeneration+state], [principalKey+locationId+entityType+entityId+dispatchable+localSequence], [principalKey+locationId+entityType+entityId+blocked+localSequence], [principalKey+locationId+entityType+entityId+resultVersion]',
        operationEvents: '++sequence, mutationId',
        localMigrationState: 'key',
      })
      .upgrade(async (transaction) => {
        const legacyStores = [
          'customers',
          'mutationQueue',
          'syncState',
          'conflicts',
          'bicycles',
          'serviceOrders',
          'serviceOrderEvents',
        ]
        const counts = await Promise.all(
          legacyStores.map((name) => transaction.table(name).count()),
        )
        await transaction.table('localMigrationState').add({
          key: 'identity-kernel-v5',
          protocol: 1,
          legacyPresent: counts.some((count) => count > 0),
          legacyAttribution: 'unknown',
        } satisfies LocalMigrationState)
      })
    // v6 reserves bounded, author-scoped pagination indices. No history is rewritten.
    this.version(6).stores({
      operationJournal:
        'mutationId, [principalKey+locationId], localSequence, [principalKey+locationId+entityType+entityId], [principalKey+locationId+localSequence], [principalKey+locationId+entityType+entityId+localSequence]',
      operationDelivery:
        'mutationId, state, [principalKey+locationId+entityType+state+localSequence], [principalKey+locationId+entityType+state+retryAt], [principalKey+locationId+localSequence], [principalKey+locationId+dispatchable+localSequence], [principalKey+locationId+entityType+entityId+unresolved+localSequence], [attemptId+deviceGeneration+state], [principalKey+locationId+entityType+entityId+dispatchable+localSequence], [principalKey+locationId+entityType+entityId+blocked+localSequence], [principalKey+locationId+entityType+entityId+resultVersion]',
      operationEvents: '++sequence, mutationId, [mutationId+sequence]',
    })
    // v7 adds one admitted shared-brand document per partition; existing bytes remain untouched.
    this.version(7).stores({ brandingSnapshots: 'partitionId, principalKey' })
    this.on('populate', (transaction) =>
      transaction
        .table('localMigrationState')
        .add({
          key: 'identity-kernel-v5',
          protocol: 1,
          legacyPresent: false,
          legacyAttribution: 'unknown',
        } satisfies LocalMigrationState)
        .then(() => undefined),
    )
    for (const table of [this.operationJournal, this.operationEvents]) {
      table.hook('updating', () => {
        throw new Error('Immutable operation history cannot be updated')
      })
      table.hook('deleting', () => {
        throw new Error('Immutable operation history cannot be deleted')
      })
    }
    // Dexie's default versionchange close is retained explicitly; never force-delete blockers.
    this.on('versionchange', () => this.close())
  }
}
export function createKernelDatabase(name: string): KernelDatabase {
  return new KernelDatabase(name)
}

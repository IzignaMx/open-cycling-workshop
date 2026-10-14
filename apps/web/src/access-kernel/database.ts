import type { Table } from 'dexie'
import { OcwpDatabase } from '../local/db.js'
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

/** Isolated factory only. No production import or schema activation is permitted yet. */
export class KernelDatabase extends OcwpDatabase {
  deviceControl!: Table<DeviceControl, string>
  accessContexts!: Table<AccessContextRecord, string>
  cachePartitions!: Table<CachePartition, string>
  cacheRecords!: Table<CacheRecord, [string, string, string]>
  operationJournal!: Table<OwnedOperation, string>
  operationDelivery!: Table<OperationDelivery, string>
  operationEvents!: Table<OperationEvent, number>
  localMigrationState!: Table<LocalMigrationState, string>

  constructor(name: string) {
    if (!name.trim() || name === 'ocwp')
      throw new Error('An isolated database name is required; production remains v4')
    super(name)
    this.version(5)
      .stores({
        deviceControl: 'key',
        accessContexts: 'partitionId',
        cachePartitions: 'partitionId, principalKey',
        cacheRecords: '[partitionId+entityType+entityId], [partitionId+entityType]',
        operationJournal:
          'mutationId, [principalKey+locationId], localSequence, [principalKey+locationId+entityType+entityId]',
        operationDelivery: 'mutationId, state',
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

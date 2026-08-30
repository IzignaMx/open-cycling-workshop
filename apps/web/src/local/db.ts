import Dexie, { type Table } from 'dexie'

import type { ConflictRecord, LocalCustomer, QueuedMutation, SyncStateRecord } from './types.js'

export class OcwpDatabase extends Dexie {
  customers!: Table<LocalCustomer, string>
  mutationQueue!: Table<QueuedMutation, string>
  syncState!: Table<SyncStateRecord, string>
  conflicts!: Table<ConflictRecord, string>

  constructor(name = 'ocwp') {
    super(name)
    this.version(1).stores({
      customers: 'customer_id, organization_id, location_id, display_name, updated_at',
      mutationQueue: 'mutation_id, state, organization_id, location_id, entity_type, queued_at',
      syncState: 'key',
      conflicts: 'mutation_id, entity_type, entity_id, recorded_at',
    })
    this.version(2).stores({
      customers: 'customer_id, organization_id, location_id, display_name, updated_at',
      mutationQueue: 'mutation_id, state, organization_id, location_id, entity_type, queued_at',
      syncState: 'key, scope_key, organization_id, location_id',
      conflicts: 'mutation_id, scope_key, organization_id, location_id, entity_type, entity_id, recorded_at',
    })
  }
}

export const db = new OcwpDatabase()

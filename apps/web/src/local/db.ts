import Dexie, { type Table } from 'dexie'

import type { PreferenceRecord } from '../personalization/repository.js'
import type { LocalBicycle } from './bicycle-types.js'
import type { LocalServiceOrder, LocalServiceOrderEvent } from './service-order-types.js'
import type { ConflictRecord, LocalCustomer, QueuedMutation, SyncStateRecord } from './types.js'

export class OcwpDatabase extends Dexie {
  presentationPreferences!: Table<PreferenceRecord, string>
  customers!: Table<LocalCustomer, string>
  mutationQueue!: Table<QueuedMutation, string>
  syncState!: Table<SyncStateRecord, string>
  conflicts!: Table<ConflictRecord, string>
  bicycles!: Table<LocalBicycle, string>
  serviceOrders!: Table<LocalServiceOrder, string>
  serviceOrderEvents!: Table<LocalServiceOrderEvent, string>

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
      conflicts:
        'mutation_id, scope_key, organization_id, location_id, entity_type, entity_id, recorded_at',
    })
    // Version 3 adds the Workshop Core stores. Unchanged stores are carried
    // over by Dexie; existing data (including the pending mutation queue)
    // is never touched by an index-only upgrade.
    this.version(3).stores({
      bicycles: 'bicycle_id, organization_id, location_id, customer_id, updated_at',
      serviceOrders: 'order_id, organization_id, location_id, customer_id, state, updated_at',
      serviceOrderEvents: 'event_id, order_id, organization_id, occurred_at',
    })
    // Additive personal presentation store: no operational rows or queued changes are rewritten.
    this.version(4).stores({ presentationPreferences: 'key' })
  }
}

export const db = new OcwpDatabase()

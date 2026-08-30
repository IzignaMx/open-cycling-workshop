import type { MutationEnvelope } from '../sync/types.js'

export interface LocalCustomer {
  customer_id: string
  organization_id: string
  location_id: string
  display_name: string
  email: string | null
  phone: string | null
  created_at: string
  updated_at: string
  version: number
}

export interface QueuedMutation extends MutationEnvelope {
  state: 'pending'
  queued_at: string
}

export interface SyncStateRecord {
  key: string
  scope_key: string
  organization_id: string
  location_id: string
  cursor: number
  updated_at: string
}

export interface ConflictRecord {
  mutation_id: string
  organization_id: string
  location_id: string
  scope_key: string
  entity_type: string
  entity_id: string
  reason: string
  recorded_at: string
}

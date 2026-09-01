import type { QueuedMutation } from './types.js'

export interface LocalBicycle {
  bicycle_id: string
  customer_id: string
  organization_id: string
  location_id: string
  brand: string
  model: string | null
  bicycle_type: string | null
  wheel_size: string | null
  notes: string | null
  created_at: string
  updated_at: string
  version: number
}

export type { QueuedMutation }

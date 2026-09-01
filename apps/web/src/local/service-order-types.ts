import type { QueuedMutation } from './types.js'

export type ServiceOrderState =
  | 'INTAKE'
  | 'DIAGNOSIS'
  | 'AUTHORIZED'
  | 'REJECTED'
  | 'IN_PROGRESS'
  | 'WAITING_FOR_PARTS'
  | 'READY'
  | 'CLOSED'
  | 'CANCELLED'

export interface LocalServiceOrder {
  order_id: string
  customer_id: string
  bicycle_id: string | null
  organization_id: string
  location_id: string
  state: ServiceOrderState
  reported_problem: string
  intake_condition: string | null
  accessories: string | null
  priority: string
  diagnosis: string | null
  created_at: string
  updated_at: string
  version: number
}

export interface LocalServiceOrderEvent {
  event_id: string
  order_id: string
  organization_id: string
  from_state: string
  to_state: string
  action: string
  actor_id: string
  note: string | null
  occurred_at: string
}

export type { QueuedMutation }

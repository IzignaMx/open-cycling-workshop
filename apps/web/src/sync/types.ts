export type EntityType = 'customer'
export type MutationOperation = 'create' | 'update'

export interface MutationEnvelope {
  mutation_id: string
  entity_type: EntityType
  entity_id: string
  operation: MutationOperation
  organization_id: string
  location_id: string
  base_version: number | null
  occurred_at: string
  payload: Record<string, unknown>
}

export interface AppliedMutationResult {
  mutation_id: string
  status: 'applied'
  entity_id: string
  entity_version: number
  error_code?: null
  error_message?: null
}

export interface ConflictMutationResult {
  mutation_id: string
  status: 'conflict'
  entity_id: string
  entity_version: null
  error_code: 'sync_conflict' | string
  error_message: string
}

export type MutationResult = AppliedMutationResult | ConflictMutationResult

export interface PushResponse {
  results: MutationResult[]
}

export interface ChangeItem {
  cursor: number
  entity_type: string
  entity_id: string
  operation?: string
  organization_id?: string
  location_id?: string
  entity_version?: number
  occurred_at?: string
  payload?: Record<string, unknown>
}

export interface ChangePage {
  items: ChangeItem[]
  next_cursor: number
  has_more: boolean
}

export interface SyncStore {
  listPending(limit: number): Promise<MutationEnvelope[]>
  markAcknowledged(mutationIds: string[]): Promise<void>
  recordConflicts(results: ConflictMutationResult[]): Promise<void>
  getCursor(): Promise<number>
  mergeAndAdvance(items: ChangeItem[], nextCursor: number): Promise<void>
}

export interface SyncTransport {
  push(mutations: MutationEnvelope[]): Promise<PushResponse>
  pull(cursor: number, locationId: string | null): Promise<ChangePage>
}

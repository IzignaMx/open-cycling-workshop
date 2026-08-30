// Generated from packages/api-client/openapi.json. Do not edit by hand.

export interface ChangeItemResponse {
  cursor: number
  entity_id: string
  entity_type: string
  entity_version: number
  location_id: string
  occurred_at: string
  operation: string
  organization_id: string
  payload: Record<string, unknown>
}

export interface ChangePageResponse {
  has_more: boolean
  items: Array<ChangeItemResponse>
  next_cursor: number
}

export interface CurrentUserResponse {
  capabilities: Array<string>
  display_name: string
  location_id: string | null
  organization_id: string
  user_id: string
}

export interface CustomerCreateRequest {
  customer_id?: string | null
  display_name: string
  email?: string | null
  location_id: string
  phone?: string | null
}

export interface CustomerResponse {
  created_at: string
  customer_id: string
  display_name: string
  email: string | null
  location_id: string
  organization_id: string
  phone: string | null
  updated_at: string
  version: number
}

export interface HTTPValidationError {
  detail?: Array<ValidationError>
}

export interface HealthReadyResponse {
  environment: string
  status?: string
}

export interface HealthUnavailableResponse {
  status?: string
}

export interface LoginRequest {
  organization_id: string
  password: string
  username: string
}

export interface LoginResponse {
  access_token: string
  token_type?: string
}

export interface MutationRequest {
  base_version?: number | null
  entity_id: string
  entity_type: string
  location_id: string
  mutation_id: string
  occurred_at: string
  operation: "create" | "update"
  organization_id: string
  payload: Record<string, unknown>
}

export interface MutationResultResponse {
  entity_id: string
  entity_version?: number | null
  error_code?: string | null
  error_message?: string | null
  mutation_id: string
  status: "applied" | "conflict"
}

export interface PushMutationsRequest {
  mutations: Array<MutationRequest>
}

export interface PushMutationsResponse {
  results: Array<MutationResultResponse>
}

export interface ValidationError {
  ctx?: Record<string, unknown>
  input?: unknown
  loc: Array<string | number>
  msg: string
  type: string
}

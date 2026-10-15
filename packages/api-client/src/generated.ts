// Generated from packages/api-client/openapi.json. Do not edit by hand.

export interface AccessContextResponse {
  account_location_id: string | null
  authorization_epoch: string
  capabilities: Array<string>
  dataset_incarnation: string
  offline_until: string
  policy_revision: "ocwp-access-baseline-2"
  principal: ContextPrincipal
  protocol: 1
  selected_location_id: string
  snapshot_protocol: "baseline-v1" | null
  verified_at: string
}

export interface ActivationRequest {
  checkpoint: string
  protocol: 1
}

export interface ActivationResponse {
  authorization_epoch: string
  baseline_id: string
  checkpoint: string
  context: AccessContextResponse
  protocol: 1
}

export interface BicycleCreateRequest {
  bicycle_id?: string | null
  bicycle_type?: string | null
  brand: string
  customer_id: string
  location_id: string
  model?: string | null
  notes?: string | null
  wheel_size?: string | null
}

export interface BicyclePayload {
  bicycle_id: string
  bicycle_type: string | null
  brand: string
  created_at: string
  customer_id: string
  location_id: string
  model: string | null
  notes: string | null
  organization_id: string
  updated_at: string
  version: number
  wheel_size: string | null
}

export interface BicycleRecord {
  entity_id: string
  entity_type: "bicycle"
  entity_version: number
  payload: BicyclePayload
}

export interface BicycleResponse {
  bicycle_id: string
  bicycle_type: string | null
  brand: string
  created_at: string
  customer_id: string
  location_id: string
  model: string | null
  notes: string | null
  organization_id: string
  updated_at: string
  version: number
  wheel_size: string | null
}

export interface BrandingLogoResponse {
  byte_count: number
  height: number
  mime_type: "image/png"
  png_base64: string | null
  sha256: string
  width: number
}

export interface BrandingProfileResponse {
  dataset_incarnation: string
  display_name: string
  location_id: string
  logo: BrandingLogoResponse | null
  logo_diagnostic: "asset_unavailable" | null
  logo_state: "none" | "available" | "unavailable"
  organization_id: string
  palette_id: "bosque" | "arcilla" | "tinta" | "cobalto" | "petroleo" | "indigo" | "malva" | "frambuesa" | "jade" | "lima" | "hielo" | "lavanda"
  schema_version: 1
  updated_at: string | null
  updated_by: string | null
  version: number
}

export interface BrandingPutRequest {
  display_name: string
  expected_version: number
  logo_png_base64: string | null
  palette_id: "bosque" | "arcilla" | "tinta" | "cobalto" | "petroleo" | "indigo" | "malva" | "frambuesa" | "jade" | "lima" | "hielo" | "lavanda"
}

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

export interface ChangePasswordRequest {
  current_password: string
  new_password: string
}

export interface Completion {
  authorization_epoch: string
  baseline_id: string | null
  checkpoint: string
}

export interface ContextPrincipal {
  api_realm: null
  organization_id: string
  user_id: string
}

export interface CreateLocationRequest {
  name: string
}

export interface CreateUserRequest {
  capabilities?: Array<string> | null
  display_name: string
  is_owner?: boolean
  location_id: string | null
  password: string
  role?: string | null
  username: string
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

export interface CustomerPayload {
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

export interface CustomerRecord {
  entity_id: string
  entity_type: "customer"
  entity_version: number
  payload: CustomerPayload
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

export interface DeltaPage {
  authorization_epoch: string
  baseline_id: string | null
  completion: Completion | null
  continuation: string
  page_id: string
  phase: "catching_up" | "complete"
  predecessor: string
  protocol: 1
  records: Array<unknown>
}

export interface FinalizeResponse {
  authorization_epoch: string
  baseline_id: string
  continuation: string
  predecessor: string
  protocol: 1
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

export interface LocationPage {
  items: Array<LocationResponse>
  next_cursor: string | null
}

export interface LocationResponse {
  location_id: string
  name: string
  organization_id: string
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

export interface MovementCreateRequest {
  kind: MovementKind
  movement_id: string
  note?: string | null
  order_id?: string | null
  product_id: string
  quantity: number
  reference_movement_id?: string | null
}

export type MovementKind = "ADJUST" | "RESERVE" | "RELEASE" | "CONSUME"

export interface MovementResponse {
  actor_id: string
  kind: MovementKind
  location_id: string
  movement_id: string
  note: string | null
  occurred_at: string
  order_id: string | null
  organization_id: string
  product_id: string
  quantity: number
  reference_movement_id: string | null
}

export interface MutationRequest {
  base_version?: number | null
  entity_id: string
  entity_type: "customer" | "bicycle" | "service_order"
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
  error_code?: "sync_conflict" | "legacy_receipt_unverified" | "receipt_integrity_conflict" | "receipt_proof_conflict" | null
  error_message?: string | null
  mutation_id: string
  status: "applied" | "conflict"
}

export interface OrderTransitionRequest {
  action: "start_diagnosis" | "authorize" | "reject" | "start_work" | "request_parts" | "resume_work" | "mark_ready" | "close" | "cancel"
  note?: string | null
}

export interface PageRequest {
  continuation: string
  protocol: 1
}

export interface PatchUserRequest {
  capabilities?: Array<string> | null
  display_name?: string
  expected_version: number
  is_active?: boolean
  is_owner?: boolean
  location_id?: string | null
  role?: string | null
}

export interface ProductCreateRequest {
  location_id: string
  name: string
  product_id?: string | null
  sku: string
  unit?: string
}

export interface ProductResponse {
  created_at: string
  location_id: string
  name: string
  organization_id: string
  product_id: string
  sku: string
  unit: string
  updated_at: string
  version: number
}

export interface PushMutationsRequest {
  mutations: Array<MutationRequest>
}

export interface PushMutationsResponse {
  results: Array<MutationResultResponse>
}

export interface ResetPasswordRequest {
  expected_version: number
  new_password: string
}

export interface RoleCatalogResponse {
  capabilities: Array<string>
  roles: Array<RoleResponse>
}

export interface RoleCatalogV2Response {
  capabilities: Array<string>
  catalog_version: 2
  legacy_wildcard_capabilities: Array<string>
  roles: Array<RoleResponse>
}

export interface RoleResponse {
  capabilities: Array<string>
  name: string
}

export interface ScanPage {
  authorization_epoch: string
  baseline_id: string
  continuation: string
  page_id: string
  phase: "scan" | "scan_complete"
  predecessor: string
  protocol: 1
  records: Array<unknown>
}

export interface ServiceOrderCreateRequest {
  accessories?: string | null
  bicycle_id?: string | null
  customer_id: string
  intake_condition?: string | null
  location_id: string
  order_id?: string | null
  priority?: string
  reported_problem: string
}

export interface ServiceOrderEventResponse {
  action: string
  actor_id: string
  event_id: string
  from_state: string
  note: string | null
  occurred_at: string
  order_id: string
  to_state: string
}

export interface ServiceOrderPayload {
  accessories: string | null
  bicycle_id: string | null
  created_at: string
  customer_id: string
  diagnosis: string | null
  intake_condition: string | null
  location_id: string
  order_id: string
  organization_id: string
  priority: string
  reported_problem: string
  state: "INTAKE" | "DIAGNOSIS" | "AUTHORIZED" | "REJECTED" | "IN_PROGRESS" | "WAITING_FOR_PARTS" | "READY" | "CLOSED" | "CANCELLED"
  updated_at: string
  version: number
}

export interface ServiceOrderRecord {
  entity_id: string
  entity_type: "service_order"
  entity_version: number
  payload: ServiceOrderPayload
}

export interface ServiceOrderResponse {
  accessories: string | null
  bicycle_id: string | null
  created_at: string
  customer_id: string
  diagnosis: string | null
  intake_condition: string | null
  location_id: string
  order_id: string
  organization_id: string
  priority: string
  reported_problem: string
  state: string
  updated_at: string
  version: number
}

export interface StartRequest {
  authorization_epoch: string
  protocol: 1
  request_id: string
  selected_location_id: string
}

export interface StartResponse {
  baseline_id: string
  context: AccessContextResponse
  continuation: string
  expires_at: string
  protocol: 1
}

export interface StockResponse {
  available_quantity: number
  location_id: string
  organization_id: string
  product_id: string
}

export interface UserPage {
  items: Array<UserResponse>
  next_cursor: string | null
}

export interface UserResponse {
  capabilities: Array<string>
  display_name: string
  is_active: boolean
  is_owner: boolean
  location_id: string | null
  organization_id: string
  user_id: string
  username: string
  version: number
}

export interface ValidationError {
  ctx?: Record<string, unknown>
  input?: unknown
  loc: Array<string | number>
  msg: string
  type: string
}

export interface VersionRequest {
  expected_version: number
}

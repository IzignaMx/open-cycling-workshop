import type { SessionUserSnapshot } from '../../auth/session.js'
export type {
  ChangePasswordRequest,
  CreateLocationRequest,
  CreateUserRequest,
  LocationPage,
  LocationResponse,
  PatchUserRequest,
  ResetPasswordRequest,
  RoleCatalogResponse,
  RoleResponse,
  UserPage,
  UserResponse,
  VersionRequest,
} from '@ocwp/api-client'
export interface AdministrationCapture {
  readonly token: string
  readonly user: SessionUserSnapshot
  readonly signal?: AbortSignal
  isCurrent(): boolean
}
export interface PageOptions {
  afterId?: string
  limit?: number
}
export interface UserPageOptions extends PageOptions {
  active?: boolean
}
export type OwnerHint = 'unknown' | 'owner' | 'non-owner'
export interface UserDraft {
  display_name: string
  location_id: string | null
  capabilities: string[]
  is_active: boolean
  is_owner: boolean
}
export type {
  CreateUserRequest as UserCreateInput,
  PatchUserRequest as UserPatch,
} from '@ocwp/api-client'

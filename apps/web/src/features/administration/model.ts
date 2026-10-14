import type { SessionUserSnapshot } from '../../auth/session.js'
import type {
  OwnerHint,
  PatchUserRequest,
  RoleCatalogResponse,
  UserDraft,
  UserPage,
  UserResponse,
} from './contracts.js'
export const codePointLength = (value: string): number => Array.from(value).length
export const normalizeUsername = (value: string): string => value.trim().toLowerCase()
export function validText(value: unknown, max: number, min = 1): value is string {
  return (
    typeof value === 'string' &&
    !value.includes('\0') &&
    codePointLength(value) >= min &&
    codePointLength(value) <= max
  )
}
export function validatePassword(value: string, current = false): boolean {
  return codePointLength(value) >= (current ? 1 : 12) && codePointLength(value) <= 1024
}
export function sameGrants(a: readonly string[], b: readonly string[]): boolean {
  return new Set(a).size === new Set(b).size && a.every((g) => b.includes(g))
}
export function matchingRole(
  grants: readonly string[],
  catalog: RoleCatalogResponse,
): string | null {
  return catalog.roles.find((role) => sameGrants(grants, role.capabilities))?.name ?? null
}
export function hasCapability(
  actor: SessionUserSnapshot,
  capability: string,
  catalog?: RoleCatalogResponse,
): boolean {
  return (
    actor.capabilities.includes(capability) ||
    (actor.capabilities.includes('*') && !!catalog?.capabilities.includes(capability))
  )
}
function concrete(grants: readonly string[], catalog: RoleCatalogResponse): string[] | null {
  if (grants.some((g) => g !== '*' && !catalog.capabilities.includes(g))) return null
  return grants.includes('*') ? [...catalog.capabilities] : [...grants]
}
export function canAdminister(
  actor: SessionUserSnapshot,
  target: UserResponse,
  proposed: UserDraft,
  owner: OwnerHint,
  catalog: RoleCatalogResponse,
): boolean {
  if (
    target.organization_id !== actor.organization_id ||
    ((target.is_owner || proposed.is_owner) && owner !== 'owner')
  )
    return false
  if (
    actor.location_id !== null &&
    (target.location_id !== actor.location_id || proposed.location_id !== actor.location_id)
  )
    return false
  const own = concrete(actor.capabilities, catalog),
    old = concrete(target.capabilities, catalog),
    next = concrete(proposed.capabilities, catalog)
  if (!own || !old || !next || proposed.capabilities.includes('*')) return false
  return (
    [...old, ...next].every((g) => own.includes(g)) &&
    (!proposed.is_owner ||
      (proposed.location_id === null && sameGrants(next, catalog.capabilities)))
  )
}
export function ownerHintFromPage(
  actor: SessionUserSnapshot,
  page: UserPage,
  filtered = false,
): OwnerHint {
  if (filtered) return 'unknown'
  const row = page.items.find(
    (item) => item.user_id === actor.user_id && item.organization_id === actor.organization_id,
  )
  if (
    !row ||
    !row.is_active ||
    row.location_id !== actor.location_id ||
    !sameGrants(row.capabilities, actor.capabilities)
  )
    return 'unknown'
  return row.is_owner ? 'owner' : 'non-owner'
}
export function validateUserDraft(draft: UserDraft, catalog?: RoleCatalogResponse): string[] {
  const fields: string[] = []
  if (!validText(draft.display_name.trim(), 200)) fields.push('display_name')
  if (draft.location_id !== null && !validText(draft.location_id, 36)) fields.push('location_id')
  if (
    draft.capabilities.length > 100 ||
    new Set(draft.capabilities).size !== draft.capabilities.length ||
    draft.capabilities.some(
      (g) => !validText(g, 128) || g === '*' || (catalog && !catalog.capabilities.includes(g)),
    )
  )
    fields.push('capabilities')
  if (
    draft.is_owner &&
    (draft.location_id !== null ||
      (catalog && !sameGrants(draft.capabilities, catalog.capabilities)))
  )
    fields.push('is_owner')
  return fields
}
export function minimalUserPatch(
  original: UserResponse,
  draft: UserDraft,
  catalog?: RoleCatalogResponse,
): PatchUserRequest | null {
  if (
    !Number.isSafeInteger(original.version) ||
    original.version < 1 ||
    validateUserDraft(draft, catalog).length
  )
    throw new Error('invalid_form')
  const patch: PatchUserRequest = { expected_version: original.version }
  const name = draft.display_name.trim()
  if (name !== original.display_name) patch.display_name = name
  if (draft.location_id !== original.location_id) patch.location_id = draft.location_id
  if (draft.is_active !== original.is_active) patch.is_active = draft.is_active
  if (draft.is_owner !== original.is_owner) patch.is_owner = draft.is_owner
  if (!sameGrants(draft.capabilities, original.capabilities))
    patch.capabilities = [...draft.capabilities]
  return Object.keys(patch).length === 1 ? null : patch
}
export function isSelfSecurityChange(
  actor: SessionUserSnapshot,
  target: UserResponse,
  patch: PatchUserRequest,
): boolean {
  if (actor.user_id !== target.user_id || actor.organization_id !== target.organization_id)
    return false
  return (
    (patch.is_active !== undefined && patch.is_active !== target.is_active) ||
    (patch.is_owner !== undefined && patch.is_owner !== target.is_owner) ||
    (Object.hasOwn(patch, 'location_id') && patch.location_id !== target.location_id) ||
    (patch.capabilities != null && !sameGrants(patch.capabilities, target.capabilities)) ||
    patch.role != null
  )
}

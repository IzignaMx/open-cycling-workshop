/** Immutable pre-branding wildcard semantics. Catalog growth never expands authority. */
export const LEGACY_WILDCARD_CAPABILITIES: readonly string[] = Object.freeze([
  'customers.read',
  'customers.write',
  'bicycles.read',
  'bicycles.write',
  'orders.read',
  'orders.write',
  'inventory.read',
  'inventory.write',
  'sync.pull',
  'sync.push',
  'users.read',
  'users.write',
  'users.grants.write',
  'users.sessions.revoke',
  'users.credentials.reset',
  'locations.read',
  'locations.create',
])
export function hasCapability(capabilities: readonly string[], required: string): boolean {
  return (
    capabilities.includes(required) ||
    (capabilities.includes('*') && LEGACY_WILDCARD_CAPABILITIES.includes(required))
  )
}

// Synthetic snapshots of the accepted pre-quote and quote-aware v2 catalogs.
// Keep the seventeen legacy wildcard literals independent of additions.
export const legacyCapabilities = [
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
]
export const oldCapabilities = [...legacyCapabilities, 'branding.read', 'branding.write']
export const quoteCapabilities = ['quotes.read', 'quotes.write', 'quotes.authorize']
const business = legacyCapabilities.slice(0, 10)
const without = (grants, excluded) => grants.filter((grant) => !excluded.includes(grant))
export function quoteCatalog(includeQuotes = true) {
  const capabilities = [...oldCapabilities, ...(includeQuotes ? quoteCapabilities : [])]
  return {
    catalog_version: 2,
    legacy_wildcard_capabilities: [...legacyCapabilities],
    capabilities,
    roles: [
      { name: 'Owner', capabilities: [...capabilities] },
      { name: 'Administrator', capabilities: without(oldCapabilities, ['locations.create']) },
      { name: 'Manager', capabilities: [...business, 'locations.read', 'branding.read'] },
      {
        name: 'Mechanic',
        capabilities: [
          ...without(business, ['customers.write', 'inventory.write']),
          'locations.read',
          'branding.read',
        ],
      },
      {
        name: 'Reception',
        capabilities: [
          ...without(business, ['inventory.write']),
          'locations.read',
          'branding.read',
        ],
      },
      {
        name: 'Sales',
        capabilities: [
          ...without(business, ['orders.write', 'inventory.write']),
          'locations.read',
          'branding.read',
        ],
      },
      {
        name: 'Viewer',
        capabilities: [
          'customers.read',
          'bicycles.read',
          'orders.read',
          'inventory.read',
          'sync.pull',
          'locations.read',
          'branding.read',
        ],
      },
      { name: 'TechnicalAdmin', capabilities: [] },
    ],
  }
}

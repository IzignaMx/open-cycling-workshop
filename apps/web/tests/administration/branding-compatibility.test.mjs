import test from 'node:test'
import assert from 'node:assert/strict'
import {
  hasCapability,
  canAdminister,
  minimalUserPatch,
  validateUserDraft,
} from '../../.tmp-administration/src/features/administration/model.js'
import { createAdministrationTransport } from '../../.tmp-administration/src/features/administration/transport.js'
const legacy = [
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
const catalog = {
  catalog_version: 2,
  legacy_wildcard_capabilities: legacy,
  capabilities: [...legacy, 'branding.read', 'branding.write'],
  roles: [{ name: 'Owner', capabilities: [...legacy, 'branding.read', 'branding.write'] }],
}
const owner = {
  user_id: 'a',
  organization_id: 'o',
  location_id: null,
  display_name: 'Owner',
  username: 'owner',
  capabilities: legacy,
  is_owner: true,
  is_active: true,
  version: 3,
}
test('wildcard authority is frozen and branding read/write are independent explicit literals', () => {
  for (const [grants, read, write] of [
    [['*'], false, false],
    [['*', 'branding.read'], true, false],
    [['*', 'branding.write'], false, true],
    [['branding.read', 'branding.write'], true, true],
    [[], false, false],
    [legacy, false, false],
  ]) {
    const actor = { ...owner, capabilities: grants }
    assert.equal(hasCapability(actor, 'branding.read', catalog), read)
    assert.equal(hasCapability(actor, 'branding.write', catalog), write)
  }
})
test('established concrete and wildcard owner edits preserve exact grants and minimal fields', () => {
  for (const capabilities of [legacy, ['*']]) {
    const original = { ...owner, capabilities },
      draft = { ...original, display_name: 'New name' }
    assert.deepEqual(validateUserDraft(draft, catalog, original), [])
    assert.deepEqual(minimalUserPatch(original, draft, catalog), {
      expected_version: 3,
      display_name: 'New name',
    })
    assert.equal(canAdminister(original, original, draft, 'owner', catalog), true)
    assert.equal(canAdminister(original, original, draft, 'owner', catalog, true), false)
  }
  assert.ok(validateUserDraft({ ...owner, display_name: 'New' }, catalog).includes('is_owner'))
})
test('missing catalog semantics and wildcard-only branding delegation fail closed', () => {
  const actor = { ...owner, capabilities: ['*'] },
    target = { ...owner, is_owner: false, capabilities: [] }
  assert.equal(
    canAdminister(actor, target, { ...target, capabilities: ['branding.read'] }, 'owner', catalog),
    false,
  )
  assert.equal(
    canAdminister(owner, owner, owner, 'owner', { capabilities: catalog.capabilities, roles: [] }),
    false,
  )
})
test('v2 catalog uses explicit same-origin route without changing admitted v1 realm', async () => {
  let called
  const transport = createAdministrationTransport({
    apiRealm: 'https://example.test/api/v1',
    fetch: async (url) => {
      called = url
      const r = new Response(JSON.stringify(catalog), {
        headers: { 'content-type': 'application/json', 'cache-control': 'no-store' },
      })
      Object.defineProperty(r, 'url', { value: url })
      return r
    },
  })
  const got = await transport.roles({ token: 'synthetic', user: owner, isCurrent: () => true })
  assert.equal(called, 'https://example.test/api/v2/admin/roles')
  assert.equal(got.catalog_version, 2)
})
test('owner preservation is unavailable to malformed incomplete historical owners', () => {
  const malformed = { ...owner, capabilities: ['users.write'] }
  const changed = { ...malformed, display_name: 'Changed' }
  assert.equal(canAdminister(owner, malformed, changed, 'owner', catalog), false)
  assert.ok(validateUserDraft(changed, catalog, malformed).includes('is_owner'))
})

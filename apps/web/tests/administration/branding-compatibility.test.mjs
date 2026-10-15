import test from 'node:test'
import assert from 'node:assert/strict'
import {
  hasCapability,
  canAdminister,
  minimalUserPatch,
  validateUserDraft,
  matchingRole,
} from '../../.tmp-administration/src/features/administration/model.js'
import { createAdministrationTransport } from '../../.tmp-administration/src/features/administration/transport.js'
import { oldCapabilities, quoteCapabilities, quoteCatalog } from './quote-catalog-fixture.mjs'
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

test('quote grants remain independent explicit literals outside frozen wildcard authority', () => {
  const current = quoteCatalog()
  for (let mask = 0; mask < 2 ** quoteCapabilities.length; mask++) {
    const explicit = quoteCapabilities.filter((_, index) => mask & (1 << index))
    for (const baseline of [[], legacy, oldCapabilities, ['*']]) {
      const actor = { ...owner, capabilities: [...baseline, ...explicit] }
      for (const grant of quoteCapabilities)
        assert.equal(hasCapability(actor, grant, current), explicit.includes(grant))
    }
  }
})

test('each quote grant requires independent delegation authority for both old and new snapshots', () => {
  const current = quoteCatalog()
  const target = { ...owner, user_id: 'other', is_owner: false, capabilities: [] }
  for (const grant of quoteCapabilities) {
    const proposed = { ...target, capabilities: [grant] }
    for (const held of quoteCapabilities) {
      const actor = { ...owner, capabilities: ['users.write', 'users.grants.write', held] }
      assert.equal(canAdminister(actor, target, proposed, 'owner', current), held === grant)
      assert.equal(canAdminister(actor, proposed, target, 'owner', current), held === grant)
    }
    assert.equal(canAdminister(owner, target, proposed, 'owner', current), false)
    assert.equal(canAdminister(owner, proposed, target, 'owner', current), false)
  }
})

test('quote-aware catalog preserves exact old owner grants through a name-only transport patch', async () => {
  const current = quoteCatalog()
  for (const capabilities of [legacy, oldCapabilities, ['*'], ['*', 'branding.write']]) {
    const original = { ...owner, capabilities: [...capabilities].reverse() }
    const before = structuredClone(original)
    const draft = { ...original, display_name: 'Updated owner' }
    assert.deepEqual(validateUserDraft(draft, current, original), [])
    assert.equal(canAdminister(original, original, draft, 'owner', current), true)
    const patch = minimalUserPatch(original, draft, current)
    assert.deepEqual(patch, { expected_version: 3, display_name: 'Updated owner' })
    const transport = createAdministrationTransport({
      apiRealm: 'https://example.test/api/v1',
      fetch: async (url, init) => {
        assert.equal(url, 'https://example.test/api/v1/admin/users/a')
        assert.equal(init.method, 'PATCH')
        assert.deepEqual(JSON.parse(init.body), patch)
        assert.equal(Object.hasOwn(JSON.parse(init.body), 'capabilities'), false)
        const response = new Response(JSON.stringify({ ...draft, version: 4 }), {
          headers: { 'content-type': 'application/json', 'cache-control': 'no-store' },
        })
        Object.defineProperty(response, 'url', { value: url })
        return response
      },
    })
    const result = await transport.updateUser(
      { token: 'synthetic', user: original, isCurrent: () => true },
      original.user_id,
      patch,
    )
    assert.deepEqual(result.capabilities, before.capabilities)
    assert.equal(result.location_id, before.location_id)
    assert.equal(result.is_owner, before.is_owner)
    assert.equal(result.is_active, before.is_active)
    assert.equal(result.version, before.version + 1)
    assert.deepEqual(original, before)
  }
})

test('old nineteen-literal catalog refuses quote-grant edits without dropping known or unknown grants', () => {
  const stale = quoteCatalog(false)
  const current = quoteCatalog()
  const actor = { ...owner, capabilities: current.capabilities }
  for (const grant of quoteCapabilities) {
    const original = { ...owner, is_owner: false, capabilities: ['orders.read', grant] }
    const before = structuredClone(original)
    for (const draft of [
      { ...original, display_name: 'Changed name' },
      { ...original, capabilities: ['orders.read'] },
    ]) {
      for (const acting of [actor, { ...owner, capabilities: oldCapabilities }])
        assert.equal(canAdminister(acting, original, draft, 'owner', stale), false)
      if (draft.capabilities.includes(grant)) {
        assert.ok(validateUserDraft(draft, stale, original).includes('capabilities'))
        assert.throws(() => minimalUserPatch(original, draft, stale), /invalid_form/)
      }
      assert.deepEqual(original, before)
    }
    assert.equal(canAdminister(actor, original, original, 'owner', current), true)
    assert.deepEqual(validateUserDraft(original, current, original), [])
  }
})

test('quote-aware explicit owner creation and replacement require all twenty-two grants', () => {
  const current = quoteCatalog()
  const oldOwner = { ...owner, capabilities: oldCapabilities }
  const fullOwner = { ...owner, capabilities: current.capabilities }
  const nonOwner = { ...oldOwner, is_owner: false }
  assert.equal(current.capabilities.length, 22)
  assert.equal(new Set(current.capabilities).size, 22)
  assert.ok(validateUserDraft(oldOwner, current).includes('is_owner'))
  assert.deepEqual(validateUserDraft(fullOwner, current), [])
  assert.equal(matchingRole(oldCapabilities, current), null)
  assert.equal(matchingRole(current.capabilities, current), 'Owner')
  assert.equal(canAdminister(fullOwner, oldOwner, oldOwner, 'owner', current, true), false)
  assert.equal(canAdminister(oldOwner, oldOwner, fullOwner, 'owner', current, true), false)
  assert.equal(canAdminister(fullOwner, oldOwner, fullOwner, 'owner', current, true), true)
  assert.ok(validateUserDraft(oldOwner, current, nonOwner).includes('is_owner'))
  assert.equal(canAdminister(fullOwner, nonOwner, oldOwner, 'owner', current), false)
  assert.equal(canAdminister(fullOwner, nonOwner, fullOwner, 'owner', current), true)
  assert.equal(canAdminister(oldOwner, nonOwner, fullOwner, 'owner', current), false)
  assert.equal(canAdminister(fullOwner, nonOwner, fullOwner, 'non-owner', current), false)
  assert.deepEqual(minimalUserPatch(nonOwner, fullOwner, current), {
    expected_version: 3,
    is_owner: true,
    capabilities: current.capabilities,
  })
  for (const grant of current.capabilities) {
    const incomplete = {
      ...fullOwner,
      capabilities: current.capabilities.filter((g) => g !== grant),
    }
    assert.ok(validateUserDraft(incomplete, current).includes('is_owner'))
    assert.equal(canAdminister(fullOwner, oldOwner, incomplete, 'owner', current, true), false)
    assert.equal(canAdminister(incomplete, oldOwner, fullOwner, 'owner', current, true), false)
  }
})

test('duplicate historical owner grants remain refused without frontend normalization', () => {
  const current = quoteCatalog()
  const original = { ...owner, capabilities: [...oldCapabilities, 'orders.read'] }
  const before = structuredClone(original)
  const draft = { ...original, display_name: 'Updated owner' }
  assert.ok(validateUserDraft(draft, current, original).includes('capabilities'))
  assert.throws(() => minimalUserPatch(original, draft, current), /invalid_form/)
  assert.deepEqual(original, before)
})

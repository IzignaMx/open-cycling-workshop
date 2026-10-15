import test from 'node:test'
import assert from 'node:assert/strict'
import {
  minimalUserPatch,
  ownerHintFromPage,
  canAdminister,
  isSelfSecurityChange,
  matchingRole,
  normalizeUsername,
  validatePassword,
} from '../../.tmp-administration/src/features/administration/model.js'
const actor = {
  user_id: 'a',
  organization_id: 'o',
  location_id: null,
  display_name: 'A',
  capabilities: ['users.write'],
}
const row = { ...actor, username: 'a', is_active: true, is_owner: false, version: 3 }
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
  roles: [{ name: 'TechnicalAdmin', capabilities: [] }],
}
test('minimal patch preserves explicit null and version without unchanged grants', () => {
  assert.deepEqual(minimalUserPatch(row, { ...row, display_name: ' B ' }), {
    expected_version: 3,
    display_name: 'B',
  })
  assert.equal(minimalUserPatch(row, row), null)
  assert.deepEqual(minimalUserPatch({ ...row, location_id: 'l' }, { ...row }), {
    expected_version: 3,
    location_id: null,
  })
  assert.equal(isSelfSecurityChange(actor, row, { expected_version: 3, display_name: 'B' }), false)
  assert.equal(isSelfSecurityChange(actor, row, { expected_version: 3, is_active: false }), true)
})
test('owner evidence requires unfiltered matching active scope and grants', () => {
  assert.equal(
    ownerHintFromPage(actor, { items: [{ ...row, is_owner: true }], next_cursor: null }),
    'owner',
  )
  assert.equal(
    ownerHintFromPage(actor, { items: [{ ...row, is_owner: true }], next_cursor: null }, true),
    'unknown',
  )
  assert.equal(
    ownerHintFromPage(actor, { items: [{ ...row, location_id: 'x' }], next_cursor: null }),
    'unknown',
  )
  assert.equal(canAdminister(actor, { ...row, is_owner: true }, row, 'unknown', catalog), false)
  assert.equal(
    canAdminister(actor, row, { ...row, capabilities: ['unknown'] }, 'non-owner', catalog),
    false,
  )
})
test('empty roles, normalization and Unicode password bounds', () => {
  assert.equal(matchingRole([], catalog), 'TechnicalAdmin')
  assert.equal(normalizeUsername(' USER '), 'user')
  assert.equal(validatePassword('😀'.repeat(12)), true)
  assert.equal(validatePassword('short'), false)
})
test('subordination checks old and new grants and both scopes', () => {
  assert.equal(canAdminister(actor, row, row, 'non-owner', catalog), true)
  assert.equal(
    canAdminister(actor, { ...row, capabilities: ['users.read'] }, row, 'non-owner', catalog),
    false,
  )
  const scoped = { ...actor, location_id: 'l' }
  assert.equal(
    canAdminister(scoped, row, { ...row, location_id: 'l' }, 'non-owner', catalog),
    false,
  )
  assert.equal(
    canAdminister(scoped, { ...row, location_id: 'l' }, row, 'non-owner', catalog),
    false,
  )
  assert.equal(
    canAdminister({ ...actor, capabilities: ['*'] }, row, row, 'non-owner', catalog),
    true,
  )
})
test('unknown and wildcard grants block edits instead of dropping them', () => {
  assert.throws(
    () =>
      minimalUserPatch(
        { ...row, capabilities: ['unknown'] },
        { ...row, capabilities: ['unknown'] },
        catalog,
      ),
    /invalid_form/,
  )
  assert.throws(() => minimalUserPatch({ ...row, version: Infinity }, row), /invalid_form/)
  assert.equal(matchingRole(['users.write'], catalog), null)
})

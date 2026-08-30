import test from 'node:test'
import assert from 'node:assert/strict'

import { SessionStore } from '../../.tmp-auth/src/auth/session.js'

class FakeStorage {
  values = new Map()
  getItem(key) { return this.values.get(key) ?? null }
  setItem(key, value) { this.values.set(key, value) }
  removeItem(key) { this.values.delete(key) }
}

test('SessionStore keeps the bearer token only in its supplied session-scoped storage', () => {
  const storage = new FakeStorage()
  const store = new SessionStore(storage)

  assert.equal(store.getToken(), null)
  store.setToken('token-1')
  assert.equal(store.getToken(), 'token-1')
  assert.equal(storage.values.size, 1)
  store.clear()
  assert.equal(store.getToken(), null)
  assert.equal(storage.values.size, 0)
})

test('buildLoginRequest trims identifiers without mutating the password', async () => {
  const { buildLoginRequest } = await import('../../.tmp-auth/src/auth/login-model.js')
  const request = buildLoginRequest({
    organizationId: '  org-1 ',
    username: '  ADMIN ',
    password: '  password with spaces  ',
  })

  assert.deepEqual(request, {
    organization_id: 'org-1',
    username: 'ADMIN',
    password: '  password with spaces  ',
  })
  assert.throws(() => buildLoginRequest({ organizationId: ' ', username: 'admin', password: 'x' }), /organization/i)
})

test('SessionStore restores the validated user scope together with the token and ignores corrupt snapshots', () => {
  const storage = new FakeStorage()
  const store = new SessionStore(storage)
  const user = {
    user_id: 'user-1',
    organization_id: 'org-1',
    location_id: 'loc-1',
    display_name: 'Admin',
    capabilities: ['customers.write'],
  }

  store.setToken('token-2')
  store.setUser(user)
  assert.deepEqual(store.getSnapshot(), { token: 'token-2', user })

  storage.values.set('ocwp.session.v2', '{broken')
  assert.equal(store.getSnapshot(), null)
})

test('session policy clears credentials only for authoritative authentication failures', async () => {
  const { shouldClearSessionAfterAuthError } = await import('../../.tmp-auth/src/auth/session-policy.js')
  assert.equal(shouldClearSessionAfterAuthError(401), true)
  assert.equal(shouldClearSessionAfterAuthError(403), true)
  assert.equal(shouldClearSessionAfterAuthError(500), false)
  assert.equal(shouldClearSessionAfterAuthError(null), false)
})

test('local capability checks are deny-by-default while wildcard admin can proceed', async () => {
  const { hasCapability } = await import('../../.tmp-auth/src/auth/capabilities.js')
  assert.equal(hasCapability([], 'customers.write'), false)
  assert.equal(hasCapability(['customers.read'], 'customers.write'), false)
  assert.equal(hasCapability(['customers.write'], 'customers.write'), true)
  assert.equal(hasCapability(['*'], 'customers.write'), true)
})

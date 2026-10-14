import test from 'node:test'
import assert from 'node:assert/strict'
import {
  contextKey,
  nextContextState,
  principalKey,
  validateVerifiedContext,
} from '../../.tmp-kernel/src/access-kernel/context.js'
import { canonicalJson, entityCapability } from '../../.tmp-kernel/src/access-kernel/operations.js'
const now = Date.parse('2026-10-14T10:00:00Z')
const valid = () => ({
  protocol: 1,
  principal: { apiRealm: 'https://example.test/api/v1', organizationId: 'org', userId: 'A' },
  accountLocationId: 'loc',
  selectedLocationId: 'loc',
  capabilities: ['customers.read'],
  authorizationEpoch: 'server-epoch',
  policyRevision: 'read-v1',
  verifiedAt: new Date(now).toISOString(),
  offlineUntil: new Date(now + 3_600_000).toISOString(),
  snapshotProtocol: null,
})

test('tuple encoding cannot collide on unconstrained delimiters', () => {
  assert.notEqual(
    principalKey({ apiRealm: 'x|y', organizationId: 'z', userId: 'q' }),
    principalKey({ apiRealm: 'x', organizationId: 'y|z', userId: 'q' }),
  )
  assert.equal(
    contextKey({ ...valid(), capabilities: ['b', 'a'] }),
    contextKey({ ...valid(), capabilities: ['a', 'b'] }),
  )
})
for (const [name, mutate] of [
  [
    'raw wildcard metadata',
    (value) => {
      value.capabilities = ['*']
    },
  ],
  [
    'duplicate capabilities',
    (value) => {
      value.capabilities = ['a', 'a']
    },
  ],
  [
    'unselected organization scope',
    (value) => {
      value.accountLocationId = null
      value.selectedLocationId = ''
    },
  ],
  [
    'outside account location',
    (value) => {
      value.selectedLocationId = 'foreign'
    },
  ],
  [
    'expired offline lease',
    (value) => {
      value.offlineUntil = value.verifiedAt
    },
  ],
  [
    'unbounded offline lease',
    (value) => {
      value.offlineUntil = new Date(now + 86_400_000).toISOString()
    },
  ],
  [
    'API URL carrying credentials',
    (value) => {
      value.principal.apiRealm = 'https://user:password@example.test/api/v1'
    },
  ],
  [
    'API URL carrying query',
    (value) => {
      value.principal.apiRealm += '?token=secret'
    },
  ],
  [
    'unsupported protocol',
    (value) => {
      value.protocol = 2
    },
  ],
])
  test(`context rejects ${name}`, () => {
    const value = valid()
    mutate(value)
    assert.throws(() => validateVerifiedContext(value, now))
  })

test('pure state machine has no login-to-ready or baseline activation shortcut', () => {
  assert.equal(nextContextState('LOCKED', 'verify'), 'VERIFYING')
  assert.equal(nextContextState('VERIFYING', 'needs_baseline'), 'BASELINE_REQUIRED')
  assert.throws(() => nextContextState('LOCKED', 'verified_complete'), /Invalid/)
  assert.throws(() => nextContextState('BASELINE_REQUIRED', 'verified_complete'), /Invalid/)
  assert.equal(nextContextState('VERIFYING', 'verified_complete'), 'READY')
  assert.equal(nextContextState('READY', 'offline'), 'OFFLINE_READY')
  assert.throws(() => nextContextState('LOCKED', 'offline'), /Invalid/)
})
test('canonical JSON rejects lossy serialization and unknown entities', () => {
  assert.equal(
    canonicalJson({ z: 1, a: { c: 2, b: 3 } }),
    canonicalJson({ a: { b: 3, c: 2 }, z: 1 }),
  )
  for (const value of [
    { omitted: undefined },
    { invalid: NaN },
    new Date(),
    [undefined],
    [Infinity],
    1n,
  ])
    assert.throws(() => canonicalJson(value), /Invalid JSON/)
  for (const entity of ['unknown', '__proto__', 'constructor', 'toString'])
    assert.throws(() => entityCapability(entity, 'read'), /Unknown/)
})

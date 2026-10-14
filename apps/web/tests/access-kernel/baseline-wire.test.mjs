import test from 'node:test'
import assert from 'node:assert/strict'
import {
  canonicalBaselineTimestamp,
  validateBaselineRequest,
  validateBaselineResponse,
} from '../../.tmp-kernel/src/access-kernel/baseline-wire.js'
const now = Date.parse('2026-10-14T10:00:00Z')
const baselineId = '0199ba00-0000-7000-8000-000000000001'
const identity = {
  apiRealm: 'https://example.test/api/v1',
  organizationId: 'org',
  userId: 'A',
  selectedLocationId: 'loc',
  deviceGeneration: 1,
  tabAttemptId: 'tab',
  sessionHandle: 'session',
}
const rawContext = () => ({
  protocol: 1,
  principal: { api_realm: null, organization_id: 'org', user_id: 'A' },
  account_location_id: 'loc',
  selected_location_id: 'loc',
  capabilities: ['customers.read', 'bicycles.read', 'orders.read'],
  authorization_epoch: 'a'.repeat(43),
  policy_revision: 'ocwp-access-baseline-2',
  dataset_incarnation: '0199ba00-0000-7000-8000-000000000001',
  verified_at: '2026-10-14T10:00:00Z',
  offline_until: '2026-10-14T11:00:00Z',
  snapshot_protocol: null,
})
const context = () => ({
  protocol: 1,
  principal: { apiRealm: identity.apiRealm, organizationId: 'org', userId: 'A' },
  accountLocationId: 'loc',
  selectedLocationId: 'loc',
  capabilities: rawContext().capabilities,
  authorizationEpoch: 'a'.repeat(43),
  policyRevision: 'ocwp-access-baseline-2',
  datasetIncarnation: '0199ba00-0000-7000-8000-000000000001',
  verifiedAt: '2026-10-14T10:00:00.000Z',
  offlineUntil: '2026-10-14T11:00:00.000Z',
  snapshotProtocol: null,
})
const binding = () => ({
  context: context(),
  identity,
  baselineId,
  predecessor: 'previous',
  checkpoint: 'next',
})
const payload = () => ({
  organization_id: 'org',
  location_id: 'loc',
  created_at: '2026-10-14T10:00:00.123456Z',
  updated_at: '2026-10-14T10:00:00.123457Z',
  version: 1,
  customer_id: 'customer',
  display_name: 'Long name'.repeat(1000),
  email: null,
  phone: null,
})
const record = () => ({
  entity_type: 'customer',
  entity_id: 'customer',
  entity_version: 1,
  payload: payload(),
})
const page = () => ({
  protocol: 1,
  baseline_id: baselineId,
  authorization_epoch: 'a'.repeat(43),
  page_id: 'page',
  predecessor: 'previous',
  records: [record()],
  phase: 'scan',
  continuation: 'next',
})
test('canonical timestamps retain microseconds and normalize equivalent offsets', () => {
  assert.equal(
    canonicalBaselineTimestamp('2026-10-14T12:00:00.123456+02:00'),
    canonicalBaselineTimestamp('2026-10-14T10:00:00.123456Z'),
  )
  assert.notEqual(
    canonicalBaselineTimestamp('2026-10-14T10:00:00.123456Z'),
    canonicalBaselineTimestamp('2026-10-14T10:00:00.123457Z'),
  )
  for (const v of [
    '2026-02-30T10:00:00Z',
    '2026-01-01T24:00:00Z',
    '2026-01-01T10:00:00+24:00',
    '2026-01-01',
    '0000-01-01T00:00:00Z',
    '2026-01-01T00:00:60Z',
  ])
    assert.throws(() => canonicalBaselineTimestamp(v))
})
test('full strict page permits long Text and retains spelling, Unicode codepoint IDs', () => {
  const v = page()
  v.records[0].entity_id = v.records[0].payload.customer_id = '🚲'.repeat(36)
  const result = validateBaselineResponse('scan', v, binding(), now)
  assert.equal(result.records[0].payload.display_name.length, 9000)
  assert.equal(result.records[0].entity_id, '🚲'.repeat(36))
  assert.ok(Object.isFrozen(result.records[0].payload))
})
for (const [name, mutate] of [
  ['extra envelope', (v) => (v.extra = true)],
  ['missing nullable', (v) => delete v.records[0].payload.email],
  ['foreign scope', (v) => (v.records[0].payload.location_id = 'elsewhere')],
  ['unsafe version', (v) => (v.records[0].entity_version = v.records[0].payload.version = 2 ** 53)],
  ['zero version', (v) => (v.records[0].entity_version = v.records[0].payload.version = 0)],
  ['string version', (v) => (v.records[0].entity_version = '1')],
  ['mismatched envelope', (v) => (v.records[0].payload.customer_id = 'other')],
  ['unknown payload field', (v) => (v.records[0].payload.extra = 'bad')],
  ['noncanonical UUID', (v) => (v.baseline_id = 'bad')],
  ['foreign baseline', (v) => (v.baseline_id = '0199ba00-0000-7000-8000-000000000002')],
  ['foreign epoch', (v) => (v.authorization_epoch = 'b'.repeat(43))],
  ['foreign predecessor', (v) => (v.predecessor = 'bad')],
  ['nonadvancing token', (v) => (v.continuation = v.predecessor)],
  ['unicode token', (v) => (v.continuation = 'é')],
  ['too long token', (v) => (v.continuation = 'a'.repeat(513))],
  ['missing token', (v) => delete v.continuation],
  ['oversized record list', (v) => (v.records = Array(101).fill(record()))],
  ['unsupported type', (v) => (v.records[0].entity_type = 'quote')],
  ['wrong phase', (v) => (v.phase = 'complete')],
  ['invalid timestamp', (v) => (v.records[0].payload.updated_at = '2026-02-30T10:00:00Z')],
])
  test(`rejects ${name}`, () => {
    const v = page()
    mutate(v)
    assert.throws(() => validateBaselineResponse('scan', v, binding(), now))
  })
test('read capability is literal and required', () => {
  const b = binding()
  b.context.capabilities = ['customers.write']
  assert.throws(() => validateBaselineResponse('scan', page(), b, now))
})
test('all three projections are closed with exact order states', () => {
  const v = page()
  const common = {
    organization_id: 'org',
    location_id: 'loc',
    created_at: payload().created_at,
    updated_at: payload().updated_at,
    version: 1,
  }
  v.records = [
    {
      entity_type: 'bicycle',
      entity_id: 'bike',
      entity_version: 1,
      payload: {
        ...common,
        bicycle_id: 'bike',
        customer_id: 'customer',
        brand: '',
        model: null,
        bicycle_type: null,
        wheel_size: null,
        notes: 'x'.repeat(5000),
      },
    },
    {
      entity_type: 'service_order',
      entity_id: 'order',
      entity_version: 1,
      payload: {
        ...common,
        order_id: 'order',
        customer_id: 'customer',
        bicycle_id: null,
        state: 'INTAKE',
        reported_problem: '',
        intake_condition: null,
        accessories: null,
        priority: '',
        diagnosis: null,
      },
    },
  ]
  for (const state of [
    'INTAKE',
    'DIAGNOSIS',
    'AUTHORIZED',
    'REJECTED',
    'IN_PROGRESS',
    'WAITING_FOR_PARTS',
    'READY',
    'CLOSED',
    'CANCELLED',
  ]) {
    v.records[1].payload.state = state
    assert.equal(validateBaselineResponse('scan', v, binding(), now).records.length, 2)
  }
  const wrongGrant = binding()
  wrongGrant.context.capabilities = ['bicycles.read', 'service_orders.read']
  assert.throws(() => validateBaselineResponse('scan', v, wrongGrant, now))
  const properGrant = binding()
  properGrant.context.capabilities = ['bicycles.read', 'orders.read']
  assert.equal(validateBaselineResponse('scan', v, properGrant, now).records.length, 2)
  v.records[1].payload.state = 'DONE'
  assert.throws(() => validateBaselineResponse('scan', v, binding(), now))
})
test('closed start/finalize/delta/activation bind exact context and completion', () => {
  const start = {
    protocol: 1,
    baseline_id: baselineId,
    context: rawContext(),
    continuation: 'next',
    expires_at: '2026-10-14T10:05:00Z',
  }
  assert.equal(
    validateBaselineResponse('start', start, binding(), now).context.snapshot_protocol,
    null,
  )
  const activation = {
    protocol: 1,
    baseline_id: baselineId,
    authorization_epoch: 'a'.repeat(43),
    checkpoint: 'next',
    context: rawContext(),
  }
  assert.equal(
    validateBaselineResponse('activation', activation, binding(), now).checkpoint,
    'next',
  )
  activation.context.capabilities = ['customers.read']
  assert.throws(() => validateBaselineResponse('activation', activation, binding(), now))
  const final = {
    protocol: 1,
    baseline_id: baselineId,
    authorization_epoch: 'a'.repeat(43),
    predecessor: 'previous',
    continuation: 'next',
  }
  assert.equal(validateBaselineResponse('finalize', final, binding(), now).continuation, 'next')
  const delta = {
    ...page(),
    phase: 'complete',
    completion: {
      baseline_id: baselineId,
      authorization_epoch: 'a'.repeat(43),
      checkpoint: 'next',
    },
  }
  assert.equal(validateBaselineResponse('delta', delta, binding(), now).phase, 'complete')
  delta.phase = 'catching_up'
  assert.throws(() => validateBaselineResponse('delta', delta, binding(), now))
  delta.completion = null
  assert.equal(validateBaselineResponse('delta', delta, binding(), now).completion, null)
  delta.baseline_id = null
  assert.throws(() => validateBaselineResponse('delta', delta, binding(), now))
})
test('request validation rejects unknown keys and enforces byte limit', () => {
  assert.deepEqual(validateBaselineRequest('scan', '{"protocol":1,"continuation":"opaque"}'), {
    protocol: 1,
    continuation: 'opaque',
  })
  for (const body of [
    'null',
    '{"protocol":true,"continuation":"x"}',
    '{"protocol":1,"continuation":"x","extra":1}',
    ' '.repeat(16385) + '{}',
  ])
    assert.throws(() => validateBaselineRequest('scan', body))
})
test('raw null remains null and cannot satisfy a fabricated supported-protocol context', () => {
  const start = {
    protocol: 1,
    baseline_id: baselineId,
    context: rawContext(),
    continuation: 'next',
    expires_at: '2026-10-14T10:05:00Z',
  }
  const b = binding()
  b.context.snapshotProtocol = 'baseline-v1'
  assert.throws(() => validateBaselineResponse('start', start, b, now))
  b.context.snapshotProtocol = null
  start.context.snapshot_protocol = 'baseline-v1'
  assert.throws(() => validateBaselineResponse('start', start, b, now))
})

test('validated original start keeps exact timestamp spelling at the 16KiB receipt boundary', () => {
  const value = {
    protocol: 1,
    baseline_id: baselineId,
    context: rawContext(),
    continuation: 'first',
    expires_at: '2026-10-14T10:05:00Z',
  }
  value.context.capabilities = ['customers.read', 'x.a']
  const size = new TextEncoder().encode(JSON.stringify(value)).length
  value.context.capabilities[1] += 'a'.repeat(16384 - size)
  const expected = binding()
  expected.context.capabilities = [...value.context.capabilities]
  const result = validateBaselineResponse('start', value, expected, now)
  assert.equal(new TextEncoder().encode(JSON.stringify(result)).length, 16384)
  assert.equal(result.expires_at, value.expires_at)
})

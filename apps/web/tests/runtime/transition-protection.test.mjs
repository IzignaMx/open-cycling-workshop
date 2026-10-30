import test from 'node:test'
import assert from 'node:assert/strict'
import { TransitionProtection } from '../../.tmp-runtime/src/runtime/transition-protection.js'
const scope = () => ({
  apiRealm: 'https://example.test',
  organizationId: 'org',
  userId: 'user',
  selectedLocationId: 'shop',
  datasetIncarnation: 'dataset',
  authorizationEpoch: 'epoch',
  policyRevision: 'policy',
  capabilities: ['orders.read', 'orders.write'],
  sessionBindingId: 'binding',
})
const unknown = { block: true, message: 'fixed unknown' }
const updated = { block: false, message: null }
function owner() {
  assert.equal(
    typeof TransitionProtection,
    'function',
    'transition protection owner is implemented',
  )
  return new TransitionProtection()
}
function ready() {
  const p = owner()
  p.startVisit()
  p.observeScope(scope())
  return p
}
test('transition protection requires fresh visit and admitted scope', () => {
  const p = owner()
  assert.equal(p.begin('a'), null)
  p.observeScope(scope())
  assert.equal(p.begin('a'), null)
  p.startVisit()
  assert.equal(p.begin('a'), null)
  p.observeScope(scope())
  assert.ok(p.begin('a'))
})
test('transition protection excludes synchronous duplicates and permits independent orders', () => {
  const p = ready()
  const t = p.begin('a')
  assert.ok(t)
  assert.equal(p.begin('a'), null)
  assert.ok(p.begin('b'))
  assert.equal(p.getSnapshot().states.size, 2)
  assert.equal(p.finish('a', {}, updated), false)
  assert.equal(p.finish('a', t, unknown), true)
  assert.equal(p.finish('a', t, updated), false)
  assert.equal(p.begin('a'), null)
})
test('transition protection capacity50 refuses51 without evicting unknown and releases only updated', () => {
  const p = ready()
  const ts = []
  for (let i = 0; i < 50; i++) ts.push(p.begin(String(i)))
  assert.ok(ts.every(Boolean))
  assert.equal(p.begin('51'), null)
  assert.equal(p.getSnapshot().states.size, 50)
  assert.ok(p.getSnapshot().notice)
  p.finish('0', ts[0], unknown)
  assert.equal(p.begin('51'), null)
  p.finish('1', ts[1], updated)
  assert.equal(p.getSnapshot().notice, null)
  assert.ok(p.begin('51'))
  assert.equal(p.begin('0'), null)
})
for (const field of [
  'apiRealm',
  'organizationId',
  'userId',
  'selectedLocationId',
  'datasetIncarnation',
  'authorizationEpoch',
  'policyRevision',
  'sessionBindingId',
  'capabilities',
])
  test(`transition protection scope ${field} mismatch denies without old identifiers`, () => {
    const p = ready()
    const token = p.begin('private-order')
    p.observeScope({ ...scope(), [field]: field === 'capabilities' ? ['orders.read'] : 'changed' })
    assert.equal(p.getSnapshot().states.size, 0)
    assert.ok(p.getSnapshot().notice)
    assert.equal(p.begin('new'), null)
    assert.equal(p.finish('private-order', token, updated), false)
    p.observeScope(scope())
    assert.equal(p.begin('new'), null)
  })
test('transition protection normalized capabilities and generation-only changes retain entry', () => {
  const p = ready()
  const t = p.begin('a')
  p.observeScope({
    ...scope(),
    capabilities: ['orders.write', 'orders.read', 'orders.read'],
    deviceGeneration: 999,
    tabAttemptId: 'new',
    verifiedAt: 'new',
    offlineUntil: 'new',
  })
  assert.equal(p.begin('a'), null)
  assert.equal(p.finish('a', t, unknown), true)
  assert.equal(p.getSnapshot().states.size, 1)
})
test('transition protection empty scope may rebind without a false denial', () => {
  const p = ready()
  p.observeScope({ ...scope(), userId: 'another' })
  assert.ok(p.begin('b'))
})
test('transition protection ended visit cannot be resurrected by scope observation', () => {
  const p = ready()
  const t = p.begin('a')
  p.endVisit()
  p.observeScope(scope())
  assert.equal(p.getSnapshot().states.size, 0)
  assert.equal(p.begin('a'), null)
  p.startVisit()
  p.observeScope(scope())
  const fresh = p.begin('a')
  assert.ok(fresh)
  assert.equal(p.finish('a', t, updated), false)
  assert.equal(p.begin('a'), null)
  assert.equal(p.finish('a', fresh, updated), true)
})
test('transition protection snapshots do not expose mutable admission state', () => {
  const p = ready()
  const t = p.begin('a')
  const s = p.getSnapshot()
  s.states.clear()
  assert.equal(p.begin('a'), null)
  p.finish('a', t, unknown)
  const state = p.getSnapshot().states.get('a')
  assert.throws(() => {
    state.feedback.block = false
  }, TypeError)
  assert.throws(() => {
    state.busy = true
  }, TypeError)
  assert.equal(p.begin('a'), null)
  assert.equal(p.getSnapshot().states.get('a').busy, false)
  assert.equal(p.getSnapshot().states.get('a').feedback.block, true)
})

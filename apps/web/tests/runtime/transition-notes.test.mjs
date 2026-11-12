import test from 'node:test'
import assert from 'node:assert/strict'
import { TransitionProtection } from '../../.tmp-runtime/src/runtime/transition-protection.js'
import { buildLocalOrderTransition } from '../../.tmp-runtime/src/features/orders/local-order.js'
const scope = (extra = {}) => ({
  apiRealm: 'https://test',
  organizationId: 'org',
  userId: 'user',
  selectedLocationId: 'loc',
  datasetIncarnation: 'inc',
  authorizationEpoch: 'epoch',
  policyRevision: 'policy',
  capabilities: ['orders.read', 'orders.write'],
  sessionBindingId: 'binding',
  ...extra,
})
function ready() {
  const p = new TransitionProtection()
  p.startVisit()
  p.observeScope(scope())
  return p
}
const updated = { block: false, message: null },
  unknown = { block: true, message: 'unknown' }
const build = (note) =>
  buildLocalOrderTransition(
    {
      order_id: 'order',
      organization_id: 'org',
      location_id: 'loc',
      state: 'IN_PROGRESS',
      version: 4,
    },
    'request_parts',
    { now: () => '2026-11-12T12:00:00Z', newId: () => crypto.randomUUID(), actorId: 'actor' },
    note,
  )
test('local transition note matches server Python whitespace collapse, preserving BOM', () => {
  const note = '\u0085 Se necesita\n  cadena\u001c '
  const r = build(note)
  assert.equal(r.event.note, 'Se necesita cadena')
  assert.equal(r.mutation.payload.transition.note, r.event.note)
  assert.equal(build('\u0085\u001c').event.note, null)
  assert.equal(build('\uFEFFNota\uFEFF').event.note, '\uFEFFNota\uFEFF')
})
test('new transition notes enforce HTTP codepoint bound and UTF8 storage admission', () => {
  assert.equal(build('🙂'.repeat(2000)).event.note, '🙂'.repeat(2000))
  for (const note of ['x'.repeat(2001), '\0', '\ud800']) assert.throws(() => build(note))
})
test('runtime note drafts stay per order, retain exact input and exclude edits while pending', () => {
  const p = ready(),
    token = p.getSnapshot().noteToken
  assert.equal(p.editNote('a', 'A\n  note', token), true)
  assert.equal(p.editNote('b', 'B', token), true)
  assert.equal(p.getSnapshot().notes.get('a'), 'A\n  note')
  assert.equal(p.hasUnsentNotes(), true)
  const attempt = p.begin('a')
  assert.ok(attempt)
  assert.equal(p.editNote('a', 'changed', token), false)
  assert.equal(p.begin('a'), null)
  assert.equal(p.getSnapshot().notes.get('b'), 'B')
  assert.equal(p.finish('a', attempt, unknown, false), true)
  assert.equal(p.getSnapshot().notes.get('a'), 'A\n  note')
  assert.equal(p.editNote('a', 'replay', token), false)
})
test('only matching committed attempts clear their note; unavailable view is still a local commit', () => {
  const p = ready(),
    token = p.getSnapshot().noteToken
  p.editNote('a', 'A', token)
  p.editNote('b', 'B', token)
  const attempt = p.begin('a')
  assert.equal(p.finish('a', {}, updated, true), false)
  assert.equal(p.getSnapshot().notes.get('a'), 'A')
  assert.equal(p.finish('a', attempt, unknown, true), true)
  assert.equal(p.getSnapshot().notes.has('a'), false)
  assert.equal(p.getSnapshot().notes.get('b'), 'B')
})
test('scope replacement and logout invalidate stale editors without leaking drafts', () => {
  const p = ready(),
    old = p.getSnapshot().noteToken
  p.editNote('a', 'private', old)
  p.observeScope(scope({ selectedLocationId: 'other' }))
  assert.equal(p.getSnapshot().notes.size, 0)
  assert.equal(p.editNote('a', 'stale', old), false)
  assert.equal(p.hasUnsentNotes(), false)
  p.editNote('b', 'new', p.getSnapshot().noteToken)
  p.endVisit()
  assert.equal(p.getSnapshot().notes.size, 0)
})
test('bounded draft storage preserves existing notes and permits explicit clearing', () => {
  const p = ready(),
    token = p.getSnapshot().noteToken
  for (let i = 0; i < 50; i++) assert.equal(p.editNote(String(i), 'note', token), true)
  assert.equal(p.editNote('51', 'extra', token), false)
  assert.equal(p.getSnapshot().notes.size, 50)
  assert.equal(p.editNote('0', '', token), true)
  assert.equal(p.editNote('51', 'extra', token), true)
  assert.equal(p.editNote('51', 'x'.repeat(4001), token), false)
  assert.equal(p.getSnapshot().notes.get('51'), 'extra')
})
test('invalid but bounded draft stays editable and cannot begin an operation', () => {
  const p = ready(),
    token = p.getSnapshot().noteToken
  assert.equal(p.editNote('a', 'x'.repeat(2001), token), true)
  assert.equal(p.begin('a'), null)
  assert.equal(p.editNote('a', 'fixed', token), true)
  assert.ok(p.begin('a'))
})

test('late old attempt cannot clear the same order draft in a newer visit', () => {
  const p = ready()
  p.editNote('a', 'Old', p.getSnapshot().noteToken)
  const oldAttempt = p.begin('a')
  p.startVisit()
  p.observeScope(scope())
  p.editNote('a', 'New', p.getSnapshot().noteToken)
  const newAttempt = p.begin('a')
  assert.equal(p.finish('a', oldAttempt, updated, true), false)
  assert.equal(p.getSnapshot().notes.get('a'), 'New')
  assert.equal(p.finish('a', newAttempt, updated, true), true)
  assert.equal(p.hasUnsentNotes(), false)
})

test('inflight scope replacement hides note bytes and preserves fail-closed transition protection', () => {
  const p = ready(),
    token = p.getSnapshot().noteToken
  p.editNote('a', 'Private scope A', token)
  const attempt = p.begin('a')
  p.observeScope(scope({ authorizationEpoch: 'replacement' }))
  assert.equal(p.getSnapshot().notes.size, 0)
  assert.ok(p.getSnapshot().notice)
  assert.equal(p.editNote('a', 'New', p.getSnapshot().noteToken), false)
  assert.equal(p.finish('a', attempt, updated, true), false)
})

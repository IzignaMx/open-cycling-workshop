import test from 'node:test'
import assert from 'node:assert/strict'
import { SessionViewGeneration } from '../../.tmp-auth/src/auth/view-generation.js'

const userA = { user_id: 'a', organization_id: 'org-a', location_id: 'site-a' }
const userB = { user_id: 'b', organization_id: 'org-b', location_id: 'site-b' }

for (const continuation of [
  'refreshConflicts',
  'customerCreated',
  'refreshWorkshopData',
  'sync401',
]) {
  test(`${continuation}: deferred completion cannot repopulate or clear a later session`, async () => {
    const guard = new SessionViewGeneration()
    let current = userA
    const ticket = guard.capture(current)
    let release
    const pending = new Promise((resolve) => {
      release = resolve
    })
    const view = []
    const completion = pending.then(() => {
      if (guard.isCurrent(ticket, current)) view.push('stale A')
    })
    guard.advance()
    current = null
    guard.advance()
    current = userB
    release()
    await completion
    assert.deepEqual(view, [])
  })
}

test('same-user logout and login also invalidates older work; ordinary refresh stays valid', () => {
  const guard = new SessionViewGeneration()
  const ticket = guard.capture(userA)
  assert.equal(guard.isCurrent(ticket, { ...userA }), true)
  guard.advance()
  guard.advance()
  assert.equal(guard.isCurrent(ticket, userA), false)
  assert.equal(guard.isCurrent(guard.capture(userA), { ...userA, location_id: 'other' }), false)
})

import test from 'node:test'
import assert from 'node:assert/strict'
import { setup, command, context, completedBaseline } from './client-fixture.mjs'

test('bounded entity and history pages do not materialize foreign users journals', async (t) => {
  const { db, kernel } = await setup(t)
  const a = await completedBaseline(db, kernel)
  for (let i = 0; i < 4; i++) await kernel.commitLocalCommand(a, command(`a${i}`, `a${i}`))
  const b = await completedBaseline(db, kernel, context('B'))
  await kernel.commitLocalCommand(b, command('foreign', 'foreign'))
  const ticket = await completedBaseline(db, kernel)
  let foreignReads = 0
  db.operationJournal.hook('reading', (row) => {
    if (row.principalKey === b.principalKey) foreignReads++
    return row
  })
  const first = await kernel.listEntities(ticket, 'customer', { limit: 2 })
  assert.deepEqual(
    first.items.map((x) => x.entityId),
    ['a0', 'a1'],
  )
  const next = await kernel.listEntities(ticket, 'customer', {
    limit: 2,
    afterId: first.nextAfterId,
  })
  assert.deepEqual(
    next.items.map((x) => x.entityId),
    ['a2', 'a3'],
  )
  assert.equal(next.nextAfterId, null)
  const history = await kernel.listOperations(ticket, { limit: 2 })
  assert.equal(history.items.length, 2)
  assert.equal(foreignReads, 0)
  await assert.rejects(kernel.listEntities(ticket, 'customer', { limit: 101 }), /limit/)
})

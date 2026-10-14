import test from 'node:test'
import assert from 'node:assert/strict'
import { setup, command, context, completedBaseline } from '../access-kernel/client-fixture.mjs'
import { WorkshopRepositories } from '../../.tmp-runtime/src/runtime/repositories.js'
const issueStates = [
  'awaiting_confirmation',
  'held_authorization',
  'held_dependency',
  'held_integrity',
  'held_recovery',
  'held_retry',
  'rejected',
]
function session(ticket, value = context()) {
  return {
    ticket,
    context: value,
    identity: {
      apiRealm: value.principal.apiRealm,
      organizationId: value.principal.organizationId,
      userId: value.principal.userId,
      selectedLocationId: value.selectedLocationId,
      deviceGeneration: ticket.deviceGeneration,
      tabAttemptId: ticket.tabAttemptId,
      sessionHandle: 'binding',
    },
    bearerToken: 'synthetic',
    isCurrent: () => true,
  }
}
async function seed(db, kernel, ticket, id, state) {
  await kernel.commitLocalCommand(ticket, command(id, id))
  await db.operationDelivery.update(id, {
    state,
    dispatchable: 0,
    unresolved: state === 'applied' ? 0 : 1,
    blocked: state.startsWith('held_') || state === 'rejected' ? 1 : 0,
  })
}

test('issues after more than fifty applied operations are returned without reading applied history', async (t) => {
  const { db, kernel } = await setup(t),
    ticket = await completedBaseline(db, kernel)
  for (let i = 0; i < 75; i++) await seed(db, kernel, ticket, `applied-${i}`, 'applied')
  for (const state of issueStates) await seed(db, kernel, ticket, state, state)
  let appliedReads = 0,
    journalReads = 0
  db.operationJournal.hook('reading', (row) => {
    journalReads++
    if (row.mutationId.startsWith('applied-')) appliedReads++
    return row
  })
  const page = await new WorkshopRepositories(kernel).issues(session(ticket))
  assert.deepEqual(
    page.items.map((row) => row.delivery.state),
    issueStates,
  )
  assert.equal(page.hasIssues, true)
  assert.equal(page.nextAfterSequence, null)
  assert.equal(appliedReads, 0)
  assert.equal(journalReads, issueStates.length)
})

test('issue pages are author/read scoped, bounded and retain global hasIssues on an empty later page', async (t) => {
  const { db, kernel } = await setup(t),
    ticket = await completedBaseline(db, kernel)
  for (let i = 0; i < 53; i++) await seed(db, kernel, ticket, `issue-${i}`, 'held_recovery')
  const template = (await db.operationDelivery.toArray())[0]
  for (let i = 0; i < 120; i++) {
    await db.operationDelivery.put({
      ...template,
      mutationId: `hidden-order-${i}`,
      entityType: 'service_order',
      localSequence: 1000 + i,
    })
    await db.operationDelivery.put({
      ...template,
      mutationId: `foreign-author-${i}`,
      principalKey: 'foreign',
      localSequence: 2000 + i,
    })
    await db.operationDelivery.put({
      ...template,
      mutationId: `unknown-state-${i}`,
      state: 'unknown_future_state',
      localSequence: 3000 + i,
    })
  }
  let hiddenReads = 0,
    metadataReads = 0,
    originalReads = 0
  db.operationDelivery.hook('reading', (row) => {
    metadataReads++
    if (
      row.mutationId.startsWith('hidden-') ||
      row.mutationId.startsWith('foreign-') ||
      row.mutationId.startsWith('unknown-')
    )
      hiddenReads++
    return row
  })
  db.operationJournal.hook('reading', (row) => {
    originalReads++
    return row
  })
  const repositories = new WorkshopRepositories(kernel)
  const first = await repositories.issues(session(ticket))
  assert.equal(first.items.length, 50)
  assert.equal(first.hasIssues, true)
  assert.ok(first.nextAfterSequence)
  assert.equal(hiddenReads, 0)
  assert.equal(originalReads, 50)
  assert.ok(metadataReads <= 60, `metadata read count ${metadataReads}`)
  const next = await repositories.issues(session(ticket), first.nextAfterSequence)
  assert.equal(next.items.length, 3)
  assert.equal(next.nextAfterSequence, null)
  assert.equal(next.hasIssues, true)
  const empty = await repositories.issues(session(ticket), Number.MAX_SAFE_INTEGER)
  assert.deepEqual(empty.items, [])
  assert.equal(empty.hasIssues, true)
  await db.operationDelivery.bulkDelete(
    Array.from({ length: 120 }, (_, i) => [
      `hidden-order-${i}`,
      `foreign-author-${i}`,
      `unknown-state-${i}`,
    ]).flat(),
  )
  const b = await completedBaseline(db, kernel, context('B'))
  const foreign = await repositories.issues(session(b, context('B')))
  assert.deepEqual(foreign.items, [])
  assert.equal(foreign.hasIssues, false)
  const noRead = context('A', { capabilities: ['customers.write', 'sync.push'] })
  const lockedRead = await completedBaseline(db, kernel, noRead)
  const denied = await repositories.issues(session(lockedRead, noRead))
  assert.deepEqual(denied.items, [])
  assert.equal(denied.hasIssues, false)
})

test('issue status distinguishes pending retry from synchronized and uses earliest bounded retry index', async (t) => {
  const { db, kernel } = await setup(t),
    ticket = await completedBaseline(db, kernel)
  await seed(db, kernel, ticket, 'later-local-first', 'retryable')
  await seed(db, kernel, ticket, 'earlier-local-second', 'retryable')
  await db.operationDelivery.update('later-local-first', { retryAt: 9000 })
  await db.operationDelivery.update('earlier-local-second', { retryAt: 3000 })
  const page = await new WorkshopRepositories(kernel).issues(session(ticket))
  assert.equal(page.hasIssues, false)
  assert.equal(page.hasPending, true)
  assert.equal(page.nextRetryAt, 3000)
})

test('the production issue panel wires an accessible next-page action and global issue state', async () => {
  const { readFile } = await import('node:fs/promises')
  const app = await readFile(new URL('../../src/App.tsx', import.meta.url), 'utf8')
  assert.match(app, /onClick=\{\(\) => void runtime\.loadIssues\(state\.issueAfter!\)\}/)
  assert.match(app, />\s*Más incidencias\s*</)
  assert.match(app, /hasIssues=\{state\.hasIssues\}/)
})

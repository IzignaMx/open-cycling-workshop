import test from 'node:test'
import assert from 'node:assert/strict'
import {
  setup,
  context,
  completedBaseline,
  NOW,
} from '../../tests/access-kernel/client-fixture.mjs'
import { snapshotSource, revalidateSource } from './source.mjs'

async function fixture(t) {
  const { db, kernel } = await setup(t)
  const value = context()
  const ticket = await completedBaseline(db, kernel, value)
  await kernel.rememberSession(ticket, 'binding-A')
  const scope = {
    ...value.principal,
    selectedLocationId: value.selectedLocationId,
    datasetIncarnation: value.datasetIncarnation,
    authorizationEpoch: value.authorizationEpoch,
    policyRevision: value.policyRevision,
    capabilities: value.capabilities,
    sessionBindingId: 'binding-A',
  }
  const checkpointId = crypto.randomUUID(),
    generation = crypto.randomUUID()
  await kernel.checkpointCapture(ticket, { kind: 'enroll', checkpointId, generation, scope })
  await kernel.checkpointCapture(ticket, {
    kind: 'save',
    checkpointId,
    generation,
    scope,
    channel: 'customer',
    expectedRevision: 0,
    content: {
      channel: 'customer',
      draft: { displayName: ' Private\n', email: '', phone: ' 123 ' },
    },
  })
  return {
    db,
    kernel,
    options: { db, ticket, scope, checkpointId, now: NOW, isCurrent: () => true },
  }
}
async function bytes(db) {
  return JSON.stringify(await Promise.all(db.tables.map((table) => table.toArray())))
}
test('read-only snapshot preserves exact content and returns opaque witness', async (t) => {
  const { db, options } = await fixture(t)
  const before = await bytes(db)
  const result = await snapshotSource(options)
  assert.equal(result.kind, 'snapshot')
  assert.equal(result.bundle.kind, 'inert-capture-custody')
  assert.deepEqual(
    result.bundle.contents[0],
    await db.captureDraftContents.get([options.checkpointId, 'customer']),
  )
  assert.equal(JSON.stringify(result.witness), '{}')
  assert.deepEqual(await revalidateSource(options, result.witness), {
    kind: 'source_unchanged_at_check',
  })
  assert.equal(await bytes(db), before)
  assert.equal(JSON.stringify(result.bundle).includes('binding-A'), false)
})
test('edits, metadata changes and late writes invalidate an observation', async (t) => {
  const { db, options } = await fixture(t)
  const result = await snapshotSource(options)
  await db.deviceControl.update('device', { dispatchScanAfter: 1 })
  assert.deepEqual(await revalidateSource(options, result.witness), { kind: 'source_changed' })
  assert.equal((await revalidateSource(options, {})).kind, 'refused')
})
for (const table of ['operationJournal', 'operationDelivery', 'operationEvents']) {
  test(`refuses any ${table} including orphan or applied history`, async (t) => {
    const { db, options } = await fixture(t)
    await db[table].add({ mutationId: 'old', state: 'applied' })
    const before = await bytes(db)
    assert.equal((await snapshotSource(options)).reason, 'history_present')
    assert.equal(await bytes(db), before)
  })
}
for (const change of [
  'protected',
  'unsupported',
  'missing',
  'expired',
  'clock',
  'scope',
  'owner',
  'current',
  'empty',
]) {
  test(`refuses ${change} without changing source`, async (t) => {
    const { db, options } = await fixture(t)
    if (change === 'protected') {
      const head = await db.captureCheckpoints.get(options.checkpointId)
      head.customer.state = 'PROTECTED'
      head.customer.attemptId = crypto.randomUUID()
      await db.captureCheckpoints.put(head)
    }
    if (change === 'unsupported')
      await db.captureDraftContents.update([options.checkpointId, 'customer'], { format: 2 })
    if (change === 'missing')
      await db.captureDraftContents.delete([options.checkpointId, 'customer'])
    if (change === 'expired') options.now += 86_400_000
    if (change === 'clock') options.now -= 1
    if (change === 'scope') options.scope = { ...options.scope, userId: 'other' }
    if (change === 'owner') options.ticket = { ...options.ticket, tabAttemptId: 'other' }
    if (change === 'current') options.isCurrent = () => false
    if (change === 'empty') {
      const head = await db.captureCheckpoints.get(options.checkpointId)
      head.customer = { ...head.order }
      await db.captureCheckpoints.put(head)
      await db.captureDraftContents.delete([options.checkpointId, 'customer'])
    }
    const before = await bytes(db)
    assert.equal((await snapshotSource(options)).kind, 'refused')
    assert.equal(await bytes(db), before)
  })
}

test('all reads share one readonly transaction and loss of current provenance refuses', async (t) => {
  const { db, options } = await fixture(t)
  const transactions = new Set()
  let current = true
  options.isCurrent = () => current
  const observed = (row) => {
    const transaction = db.constructor.currentTransaction
    assert.equal(transaction.mode, 'readonly')
    transactions.add(transaction)
    return row
  }
  for (const table of [
    db.deviceControl,
    db.accessContexts,
    db.cachePartitions,
    db.captureCheckpoints,
    db.captureDraftContents,
  ])
    table.hook('reading', observed)
  assert.equal((await snapshotSource(options)).kind, 'snapshot')
  assert.equal(transactions.size, 1)
  const revoke = (row) => {
    current = false
    return row
  }
  db.captureDraftContents.hook('reading', revoke)
  assert.equal((await snapshotSource(options)).kind, 'refused')
})
for (const part of ['checkpoint', 'control', 'context', 'partition']) {
  test(`opaque witness detects full ${part} change`, async (t) => {
    const { db, options } = await fixture(t)
    const snapshot = await snapshotSource(options)
    if (part === 'checkpoint') {
      const head = await db.captureCheckpoints.get(options.checkpointId)
      head.order.revision++
      await db.captureCheckpoints.put(head)
    }
    if (part === 'control') await db.deviceControl.update('device', { dispatchScanAfter: 12 })
    if (part === 'context')
      await db.accessContexts.update(options.ticket.partitionId, {
        'context.offlineUntil': new Date(NOW + 3_500_000).toISOString(),
      })
    if (part === 'partition')
      await db.cachePartitions.update(options.ticket.partitionId, { syntheticExtra: 'changed' })
    assert.deepEqual(await revalidateSource(options, snapshot.witness), { kind: 'source_changed' })
    assert.equal(JSON.stringify(snapshot.witness), '{}')
  })
}
test('bounded draft inspection refuses extra rows and unavailable storage', async (t) => {
  const { db, options } = await fixture(t)
  const original = await db.captureDraftContents.get([options.checkpointId, 'customer'])
  for (const channel of ['unexpected', 'another'])
    await db.captureDraftContents.put({ ...original, channel })
  assert.equal((await snapshotSource(options)).reason, 'capacity')
  db.close()
  assert.equal((await snapshotSource(options)).kind, 'refused')
})
test('nested transaction and witness from another database are refused', async (t) => {
  const { db, options } = await fixture(t)
  const snapshot = await snapshotSource(options)
  assert.equal(
    (await db.transaction('r', db.captureCheckpoints, () => snapshotSource(options))).reason,
    'nested_transaction',
  )
  const other = await fixture(t)
  assert.equal((await revalidateSource(other.options, snapshot.witness)).reason, 'witness')
})

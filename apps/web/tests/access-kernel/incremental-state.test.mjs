import 'fake-indexeddb/auto'
import test from 'node:test'
import assert from 'node:assert/strict'
import { createKernelDatabase } from '../../.tmp-kernel/src/access-kernel/database.js'
import { IncrementalTransactions } from '../../.tmp-kernel/src/access-kernel/incremental-store.js'
import { completedBaseline } from '../../.tmp-kernel/src/access-kernel/baseline-state.js'
import { BaselineTransactions } from '../../.tmp-kernel/src/access-kernel/baseline-store.js'
import { completedMetadata } from './baseline-fixture.mjs'
import { principalKey, contextKey } from '../../.tmp-kernel/src/access-kernel/context.js'
const NOW = Date.parse('2026-10-14T10:00:00Z')
const context = {
  protocol: 1,
  principal: { apiRealm: 'https://example.test/api/v1', organizationId: 'org', userId: 'A' },
  accountLocationId: 'loc',
  selectedLocationId: 'loc',
  capabilities: ['sync.pull', 'customers.read'],
  authorizationEpoch: 'a'.repeat(43),
  policyRevision: 'ocwp-access-baseline-2',
  datasetIncarnation: '0199ba00-0000-7000-8000-000000000001',
  verifiedAt: new Date(NOW).toISOString(),
  offlineUntil: new Date(NOW + 3600000).toISOString(),
  snapshotProtocol: 'baseline-v1',
}
const ticket = {
  deviceGeneration: 1,
  tabAttemptId: 'tab',
  partitionId: 'partition',
  principalKey: principalKey(context.principal),
  authorizationEpoch: context.authorizationEpoch,
}
const identity = {
  ...context.principal,
  selectedLocationId: 'loc',
  deviceGeneration: 1,
  tabAttemptId: 'tab',
  sessionHandle: 'session',
  expectedAuthorizationEpoch: context.authorizationEpoch,
}
function row(version = 1, name = 'Original') {
  return {
    entity_type: 'customer',
    entity_id: 'customer',
    entity_version: version,
    payload: {
      organization_id: 'org',
      location_id: 'loc',
      customer_id: 'customer',
      version,
      created_at: '2026-10-14T09:00:00Z',
      updated_at: '2026-10-14T09:00:00Z',
      display_name: name,
      email: null,
      phone: null,
    },
  }
}
function page(predecessor = 'initial', continuation = 'next', phase = 'complete', records = []) {
  return {
    protocol: 1,
    baseline_id: null,
    authorization_epoch: context.authorizationEpoch,
    page_id: crypto.randomUUID(),
    predecessor,
    continuation,
    records,
    phase,
    completion:
      phase === 'complete'
        ? {
            baseline_id: null,
            authorization_epoch: context.authorizationEpoch,
            checkpoint: continuation,
          }
        : null,
  }
}
async function setup(t) {
  const db = createKernelDatabase(`incremental-${crypto.randomUUID()}`)
  await db.open()
  t.after(async () => {
    db.close()
    await db.delete()
  })
  await db.deviceControl.put({
    key: 'device',
    generation: 1,
    tabAttemptId: 'tab',
    activePartitionId: 'partition',
    state: 'READY',
    observedAt: NOW,
    localSequence: 0,
    dispatchAttemptId: null,
    dispatchScanAfter: 0,
  })
  await db.accessContexts.put({ partitionId: 'partition', context })
  await db.cachePartitions.put({
    partitionId: 'partition',
    principalKey: ticket.principalKey,
    locationId: 'loc',
    authorizationEpoch: context.authorizationEpoch,
    policyRevision: context.policyRevision,
    status: 'active',
    baselineComplete: true,
    cursor: 'initial',
    baseline: completedMetadata(ticket, context, 'initial'),
  })
  const store = new IncrementalTransactions(
    db,
    () => NOW,
    () => true,
  )
  return { db, store, ticket, identity }
}
async function next(f, response, current = () => true) {
  return f.store.commit(
    ticket,
    (await f.store.pending(ticket)).incremental.next,
    response,
    identity,
    current,
  )
}

test('initial checkpoint creates bounded anchored metadata without changing initial proof', async (t) => {
  const f = await setup(t),
    before = await f.db.cachePartitions.get('partition')
  const { incremental } = await f.store.pending(ticket)
  assert.equal(incremental.initialCheckpoint, 'initial')
  assert.equal(incremental.binding, contextKey(context))
  assert.equal(incremental.sequence, 0)
  assert.equal(incremental.receipt, null)
  assert.equal(JSON.parse(incremental.next.body).continuation, 'initial')
  assert.deepEqual((await f.db.cachePartitions.get('partition')).baseline, before.baseline)
})
test('partial and complete pages advance latest durable cursor atomically without reactivation', async (t) => {
  const f = await setup(t)
  const initial = (await f.db.cachePartitions.get('partition')).baseline
  await next(f, page('initial', 'partial', 'catching_up', [row(2)]))
  let p = await f.db.cachePartitions.get('partition')
  assert.equal(p.cursor, 'partial')
  assert.equal(p.incremental.phase, 'catching_up')
  assert.equal(completedBaseline(p, context), true)
  assert.equal((await f.db.deviceControl.get('device')).state, 'READY')
  await next(f, page('partial', 'complete', 'complete', [row(1)]))
  p = await f.db.cachePartitions.get('partition')
  assert.equal(p.cursor, 'complete')
  assert.equal(p.incremental.sequence, 2)
  assert.deepEqual(p.baseline, initial)
  assert.equal((await f.db.cacheRecords.get(['partition', 'customer', 'customer'])).version, 2)
  assert.equal(completedBaseline(p, context), true)
})
test('only latest exact replay is idempotent and earlier response cannot rewind', async (t) => {
  const f = await setup(t),
    request = (await f.store.pending(ticket)).incremental.next,
    response = page()
  assert.equal(await f.store.commit(ticket, request, response, identity), 'committed')
  const before = await f.db.cachePartitions.get('partition')
  assert.equal(await f.store.commit(ticket, request, response, identity), 'replayed')
  assert.deepEqual(await f.db.cachePartitions.get('partition'), before)
  await assert.rejects(
    f.store.commit(ticket, request, { ...response, page_id: 'changed' }, identity),
    /Stale/,
  )
  await next(f, page('next', 'third'))
  await assert.rejects(f.store.commit(ticket, request, response, identity), /Stale/)
})
for (const mode of ['mixed-scope', 'contradiction', 'quota', 'stale-session'])
  test(`${mode} rolls back whole page and successor`, async (t) => {
    const f = await setup(t)
    await f.store.pending(ticket)
    const before = await f.db.cachePartitions.get('partition')
    let current = true
    let records = [row()]
    if (mode === 'mixed-scope')
      records.push({ ...row(2), payload: { ...row(2).payload, location_id: 'foreign' } })
    if (mode === 'contradiction') records = [row(2), row(2, 'Changed')]
    const fail = () => {
      if (mode === 'quota') throw new DOMException('Full', 'QuotaExceededError')
      if (mode === 'stale-session') current = false
    }
    f.db.cachePartitions.hook('updating', fail)
    await assert.rejects(next(f, page('initial', 'next', 'complete', records), () => current))
    f.db.cachePartitions.hook('updating').unsubscribe(fail)
    assert.deepEqual(await f.db.cachePartitions.get('partition'), before)
    assert.equal(await f.db.cacheRecords.count(), 0)
  })
for (const mode of [
  'format',
  'cursor',
  'owner',
  'epoch',
  'incarnation',
  'anchor',
  'phase',
  'receipt',
  'sequence',
  'extra',
])
  test(`corrupt ${mode} cannot authorize completion`, async (t) => {
    const f = await setup(t)
    await next(f, page())
    const p = await f.db.cachePartitions.get('partition')
    if (mode === 'format') p.incremental.format = 2
    if (mode === 'cursor') p.cursor = 'invented'
    if (mode === 'owner') p.incremental.owner.tabAttemptId = 'stale'
    if (mode === 'epoch') p.authorizationEpoch = 'other'
    if (mode === 'incarnation')
      p.incremental.datasetIncarnation = '0199ba00-0000-7000-8000-000000000002'
    if (mode === 'anchor') p.incremental.initialCheckpoint = 'unrelated'
    if (mode === 'phase') p.incremental.phase = 'catching_up'
    if (mode === 'receipt') p.incremental.receipt.response = '{}'
    if (mode === 'sequence') p.incremental.sequence = 0
    if (mode === 'extra') p.incremental.extra = true
    assert.equal(completedBaseline(p, context), false)
  })
test('terminal expiry requires new private baseline and preserves all old journal history', async (t) => {
  const f = await setup(t)
  await next(f, page())
  const expected = (await f.store.pending(ticket)).incremental.next
  await f.db.operationJournal.put({ mutationId: 'original', raw: 'unchanged' })
  await f.db.operationEvents.add({ mutationId: 'original', kind: 'local', raw: 'unchanged' })
  await f.db.operationDelivery.put({ mutationId: 'original', state: 'pending' })
  const histories = async () => [
    await f.db.operationJournal.toArray(),
    await f.db.operationEvents.toArray(),
    await f.db.operationDelivery.toArray(),
  ]
  const before = await histories()
  await f.store.hold(ticket, expected, 'checkpoint_expired', null)
  const old = await f.db.cachePartitions.get('partition')
  assert.equal(completedBaseline(old, context), false)
  const fresh = await new BaselineTransactions(
    f.db,
    () => NOW,
    () => crypto.randomUUID(),
  ).begin(ticket)
  assert.equal((await f.db.cachePartitions.get(fresh.partitionId)).incremental, undefined)
  assert.equal((await f.db.cachePartitions.get(fresh.partitionId)).cursor, null)
  assert.deepEqual(await histories(), before)
  assert.equal((await f.db.cachePartitions.get('partition')).cursor, 'next')
})
test('stale hold cannot affect winning successor or device state', async (t) => {
  const f = await setup(t),
    expected = (await f.store.pending(ticket)).incremental.next
  await next(f, page())
  const before = await f.db.cachePartitions.get('partition')
  assert.equal(await f.store.hold(ticket, expected, 'invalid_response'), false)
  assert.deepEqual(await f.db.cachePartitions.get('partition'), before)
  assert.equal((await f.db.deviceControl.get('device')).state, 'READY')
})

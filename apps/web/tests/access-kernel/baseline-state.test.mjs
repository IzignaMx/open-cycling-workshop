import 'fake-indexeddb/auto'
import test from 'node:test'
import assert from 'node:assert/strict'
import { createKernelDatabase } from '../../.tmp-kernel/src/access-kernel/database.js'
import { AccessKernel } from '../../.tmp-kernel/src/access-kernel/kernel.js'

const NOW = Date.parse('2026-10-14T10:00:00Z')
const context = {
  protocol: 1,
  principal: { apiRealm: 'https://example.test/api/v1', organizationId: 'org', userId: 'A' },
  accountLocationId: 'loc',
  selectedLocationId: 'loc',
  capabilities: ['sync.pull', 'customers.read'],
  authorizationEpoch: 'epoch'.padEnd(43, '_'),
  policyRevision: 'ocwp-access-baseline-2',
  datasetIncarnation: '0199ba00-0000-7000-8000-000000000001',
  verifiedAt: new Date(NOW).toISOString(),
  offlineUntil: new Date(NOW + 3600000).toISOString(),
  snapshotProtocol: 'baseline-v1',
}
async function setup(t) {
  const db = createKernelDatabase(`baseline-test-${crypto.randomUUID()}`)
  await db.open()
  t.after(async () => {
    db.close()
    await db.delete()
  })
  const kernel = new AccessKernel(db, { now: () => NOW, newId: () => crypto.randomUUID() })
  const result = await kernel.acceptVerifiedContext(
    await kernel.beginVerification('first'),
    context,
  )
  return { db, kernel, ticket: result.ticket }
}
test('ordinary active reuse rejects old v5 flags without completion metadata, preserving rows', async (t) => {
  const { db, kernel, ticket } = await setup(t)
  await db.cachePartitions.update(ticket.partitionId, {
    status: 'active',
    baselineComplete: true,
    cursor: 'old',
  })
  const before = await db.cachePartitions.toArray()
  const accepted = await kernel.acceptVerifiedContext(
    await kernel.beginVerification('reload'),
    context,
  )
  assert.equal(accepted.state, 'BASELINE_REQUIRED')
  await assert.rejects(kernel.readEntity(accepted.ticket, 'customer', 'customer'))
  assert.deepEqual(await db.cachePartitions.toArray(), before)
})
test('ordinary read rejects null context even with active flags and ready control', async (t) => {
  const { db, kernel, ticket } = await setup(t)
  await db.cachePartitions.update(ticket.partitionId, {
    status: 'active',
    baselineComplete: true,
    cursor: 'old',
  })
  await db.accessContexts.put({
    partitionId: ticket.partitionId,
    context: { ...context, snapshotProtocol: null },
  })
  await db.deviceControl.update('device', { state: 'READY' })
  await assert.rejects(kernel.readEntity(ticket, 'customer', 'customer'))
})

test('start persists exact request and empty fresh partition before transport, no journal changes', async (t) => {
  const { db, kernel, ticket } = await setup(t)
  const before = await db.operationJournal.toArray()
  const next = await kernel.beginBaseline(ticket)
  assert.notEqual(next.partitionId, ticket.partitionId)
  const partition = await db.cachePartitions.get(next.partitionId)
  assert.equal(partition.baseline.phase, 'start_pending')
  assert.equal(partition.baseline.datasetIncarnation, context.datasetIncarnation)
  assert.equal(partition.baseline.next.body, partition.baseline.startBody)
  assert.equal(JSON.parse(partition.baseline.startBody).request_id, partition.baseline.requestId)
  assert.equal((await db.cachePartitions.get(ticket.partitionId)).status, 'superseded')
  assert.deepEqual(await db.operationJournal.toArray(), before)
  assert.equal(await db.cacheRecords.count(), 0)
})

import { BaselineTransactions } from '../../.tmp-kernel/src/access-kernel/baseline-store.js'
import { completedMetadata } from './baseline-fixture.mjs'
import { canonicalJson } from '../../.tmp-kernel/src/access-kernel/operations.js'
const protocolContext = {
  ...context,
  snapshotProtocol: null,
  policyRevision: 'ocwp-access-baseline-2',
  datasetIncarnation: '0199ba00-0000-7000-8000-000000000001',
  authorizationEpoch: 'a'.repeat(43),
}
function wireContext(value = protocolContext) {
  return {
    protocol: 1,
    principal: { api_realm: null, organization_id: 'org', user_id: 'A' },
    account_location_id: 'loc',
    selected_location_id: 'loc',
    capabilities: value.capabilities,
    authorization_epoch: value.authorizationEpoch,
    policy_revision: value.policyRevision,
    dataset_incarnation: value.datasetIncarnation,
    verified_at: value.verifiedAt,
    offline_until: value.offlineUntil,
    snapshot_protocol: value.snapshotProtocol,
  }
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
async function staged(t) {
  const { db, kernel } = await setup(t)
  const accepted = await kernel.acceptVerifiedContext(
    await kernel.beginVerification('qualification'),
    protocolContext,
  )
  const store = new BaselineTransactions(
    db,
    () => NOW,
    () => crypto.randomUUID(),
  )
  const ticket = await store.begin(accepted.ticket)
  const identity = {
    ...protocolContext.principal,
    selectedLocationId: 'loc',
    deviceGeneration: ticket.deviceGeneration,
    tabAttemptId: ticket.tabAttemptId,
    sessionHandle: 'session',
    expectedAuthorizationEpoch: protocolContext.authorizationEpoch,
  }
  const start = {
    protocol: 1,
    baseline_id: '00000000-0000-0000-0000-000000000010',
    context: wireContext(),
    continuation: 'scan-0',
    expires_at: '2026-10-14T10:30:00Z',
  }
  const request = (await store.pending(ticket)).baseline.next
  await store.commit(ticket, request, start, identity)
  return { db, kernel, store, ticket, identity, start, startRequest: request }
}
function page(start, predecessor, continuation, records = [], phase = 'scan') {
  return {
    protocol: 1,
    baseline_id: start.baseline_id,
    authorization_epoch: protocolContext.authorizationEpoch,
    page_id: crypto.randomUUID(),
    predecessor,
    records,
    phase,
    continuation,
  }
}
async function commitNext(f, response) {
  return f.store.commit(
    f.ticket,
    (await f.store.pending(f.ticket)).baseline.next,
    response,
    f.identity,
  )
}
test('qualification staging atomically merges version dominance and rejects equal-version contradiction', async (t) => {
  const f = await staged(t)
  await commitNext(f, page(f.start, 'scan-0', 'scan-1', [row(3), row(2)]))
  const before = await f.db.cachePartitions.get(f.ticket.partitionId)
  await assert.rejects(
    commitNext(f, page(f.start, 'scan-1', 'scan-2', [row(4), row(4, 'Contradiction')])),
    /contradiction/,
  )
  assert.deepEqual(await f.db.cachePartitions.get(f.ticket.partitionId), before)
  assert.equal(
    (await f.db.cacheRecords.get([f.ticket.partitionId, 'customer', 'customer'])).version,
    3,
  )
})
test('exact latest page replay is no-op; late original or changed start cannot rewind progress', async (t) => {
  const f = await staged(t)
  const request = (await f.store.pending(f.ticket)).baseline.next
  const response = page(f.start, 'scan-0', 'scan-1', [row()])
  await f.store.commit(f.ticket, request, response, f.identity)
  const before = await f.db.cachePartitions.get(f.ticket.partitionId)
  assert.equal(await f.store.commit(f.ticket, request, response, f.identity), 'duplicate')
  await assert.rejects(
    f.store.commit(f.ticket, request, { ...response, continuation: 'other' }, f.identity),
    /Stale/,
  )
  await assert.rejects(f.store.commit(f.ticket, f.startRequest, f.start, f.identity), /Stale/)
  await assert.rejects(
    f.store.commit(
      f.ticket,
      f.startRequest,
      { ...f.start, expires_at: '2027-01-01T00:00:00Z' },
      f.identity,
    ),
    /Stale/,
  )
  assert.deepEqual(await f.db.cachePartitions.get(f.ticket.partitionId), before)
})
test('scan/finalize/delta completion retains private staging and null activation fails', async (t) => {
  const f = await staged(t)
  await commitNext(f, page(f.start, 'scan-0', 'finalize-0', [row(3)], 'scan_complete'))
  await commitNext(f, {
    protocol: 1,
    baseline_id: f.start.baseline_id,
    authorization_epoch: protocolContext.authorizationEpoch,
    predecessor: 'finalize-0',
    continuation: 'delta-0',
  })
  await commitNext(f, {
    ...page(f.start, 'delta-0', 'checkpoint-0', [row(2)], 'complete'),
    completion: {
      baseline_id: f.start.baseline_id,
      authorization_epoch: protocolContext.authorizationEpoch,
      checkpoint: 'checkpoint-0',
    },
  })
  const partition = await f.db.cachePartitions.get(f.ticket.partitionId)
  assert.equal(partition.baseline.phase, 'activation_pending')
  assert.equal(partition.baselineComplete, false)
  assert.equal(partition.cursor, null)
  await assert.rejects(f.store.activate(f.ticket, 'checkpoint-0', protocolContext), /advertisement/)
  assert.equal(
    (await f.db.cacheRecords.get([f.ticket.partitionId, 'customer', 'customer'])).version,
    3,
  )
})
test('reload resumes exact pending continuation only after fresh equivalent verification', async (t) => {
  const f = await staged(t)
  await commitNext(f, page(f.start, 'scan-0', 'scan-1', [row()]))
  const original = (await f.store.pending(f.ticket)).baseline
  const kernel = new AccessKernel(f.db, { now: () => NOW, newId: () => crypto.randomUUID() })
  const accepted = await kernel.acceptVerifiedContext(
    await kernel.beginVerification('reload'),
    protocolContext,
  )
  await f.store.resume(accepted.ticket)
  const resumed = (await f.store.pending(accepted.ticket)).baseline
  assert.equal(resumed.requestId, original.requestId)
  assert.deepEqual(resumed.next, original.next)
  assert.deepEqual(resumed.origin, original.origin)
  assert.deepEqual(resumed.owner, accepted.ticket)
  await assert.rejects(f.store.pending(f.ticket), /fenced/)
})
test('fresh abandoned attempts get distinct empty partitions; stale hold cannot affect winner', async (t) => {
  const f = await staged(t)
  await commitNext(f, page(f.start, 'scan-0', 'scan-1', [row()]))
  const oldRequest = (await f.store.pending(f.ticket)).baseline.next
  const winner = await f.store.begin(f.ticket)
  await assert.rejects(f.store.hold(f.ticket, oldRequest, 'invalid_response'), /fenced/)
  assert.equal((await f.db.deviceControl.get('device')).activePartitionId, winner.partitionId)
  assert.equal((await f.db.deviceControl.get('device')).state, 'SNAPSHOTTING')
  assert.equal(
    await f.db.cacheRecords
      .where('[partitionId+entityType]')
      .equals([winner.partitionId, 'customer'])
      .count(),
    0,
  )
  assert.equal(await f.db.cacheRecords.count(), 1)
})
test('quota abort rolls back record and continuation with no journal changes', async (t) => {
  const f = await staged(t)
  const before = await f.db.cachePartitions.get(f.ticket.partitionId)
  const fail = () => {
    throw new DOMException('Full', 'QuotaExceededError')
  }
  f.db.cachePartitions.hook('updating', fail)
  await assert.rejects(commitNext(f, page(f.start, 'scan-0', 'scan-1', [row()])), /Full/)
  f.db.cachePartitions.hook('updating').unsubscribe(fail)
  assert.deepEqual(await f.db.cachePartitions.get(f.ticket.partitionId), before)
  assert.equal(await f.db.cacheRecords.count(), 0)
  assert.equal(await f.db.operationJournal.count(), 0)
})
for (const corrupt of ['format', 'checkpoint', 'phase', 'accountLocationId'])
  test(`ordinary reuse rejects contradictory completed proof: ${corrupt}`, async (t) => {
    const { db, kernel, ticket } = await setup(t)
    const baseline = completedMetadata(ticket, context, 'checkpoint')
    if (corrupt === 'format') baseline.format = 99
    if (corrupt === 'checkpoint') baseline.checkpoint = 'different'
    if (corrupt === 'phase') baseline.phase = 'scan'
    if (corrupt === 'accountLocationId') {
      const response = JSON.parse(baseline.startResponse)
      response.context.account_location_id = null
      baseline.startResponse = canonicalJson(response)
    }
    await db.cachePartitions.update(ticket.partitionId, {
      status: 'active',
      baselineComplete: true,
      cursor: 'checkpoint',
      baseline,
    })
    const accepted = await kernel.acceptVerifiedContext(
      await kernel.beginVerification('reload'),
      context,
    )
    assert.equal(accepted.state, 'BASELINE_REQUIRED')
    await assert.rejects(kernel.readEntity(accepted.ticket, 'customer', 'customer'))
  })
test('concurrent same-instance starts refuse the second without invalidating committed winner', async (t) => {
  const { kernel, ticket } = await setup(t)
  const first = kernel.beginBaseline(ticket)
  await assert.rejects(kernel.beginBaseline(ticket), /pending/)
  const winner = await first
  assert.equal((await kernel.pendingBaseline(winner)).baseline.phase, 'start_pending')
})

test('older same-generation begin finishing last cannot replace the newer partition ticket', async (t) => {
  const { db, kernel, ticket } = await setup(t)
  const original = BaselineTransactions.prototype.begin
  let committed, release
  const ready = new Promise((resolve) => {
    committed = resolve
  })
  const pause = new Promise((resolve) => {
    release = resolve
  })
  BaselineTransactions.prototype.begin = async function (value) {
    const result = await original.call(this, value)
    committed(result)
    await pause
    return result
  }
  t.after(() => {
    BaselineTransactions.prototype.begin = original
  })
  const old = kernel.beginBaseline(ticket)
  const first = await ready
  BaselineTransactions.prototype.begin = original
  const raw = new BaselineTransactions(
    db,
    () => NOW,
    () => crypto.randomUUID(),
  )
  const winner = await raw.begin(first)
  // Force the newer completion handoff before releasing the older completion.
  await kernel.installTicket(winner, 2, ticket)
  release()
  await assert.rejects(old, /fenced/)
  assert.equal((await kernel.pendingBaseline(winner)).baseline.phase, 'start_pending')
  assert.equal((await db.deviceControl.get('device')).activePartitionId, winner.partitionId)
})
test('delayed activation completion cannot replace a newer same-generation baseline', async (t) => {
  const { db, kernel, ticket } = await setup(t)
  const baseline = completedMetadata(ticket, context, 'checkpoint')
  baseline.phase = 'activation_pending'
  baseline.next = {
    kind: 'activation',
    body: canonicalJson({ protocol: 1, checkpoint: 'checkpoint' }),
  }
  await db.cachePartitions.update(ticket.partitionId, {
    baseline,
    status: 'staging',
    baselineComplete: false,
    cursor: null,
  })
  await db.deviceControl.update('device', { state: 'CATCHING_UP' })
  const original = BaselineTransactions.prototype.activate
  let committed, release
  const ready = new Promise((resolve) => {
      committed = resolve
    }),
    pause = new Promise((resolve) => {
      release = resolve
    })
  BaselineTransactions.prototype.activate = async function (...args) {
    await original.apply(this, args)
    committed()
    await pause
  }
  t.after(() => {
    BaselineTransactions.prototype.activate = original
  })
  const old = kernel.activateBaseline(ticket, 'checkpoint', context, () => true)
  await ready
  const winner = await kernel.beginBaseline(ticket)
  release()
  await assert.rejects(old, /fenced/)
  assert.equal((await kernel.pendingBaseline(winner)).baseline.phase, 'start_pending')
})
test('same-author verification cannot resume an expired or terminal failed baseline', async (t) => {
  const f = await staged(t)
  const request = (await f.store.pending(f.ticket)).baseline.next
  await f.store.hold(f.ticket, request, 'baseline_expired')
  const accepted = await f.kernel.acceptVerifiedContext(
    await f.kernel.beginVerification('renew'),
    protocolContext,
  )
  await assert.rejects(f.store.resume(accepted.ticket), /Fresh baseline/)
  assert.equal(
    (await f.db.cachePartitions.get(f.ticket.partitionId)).baseline.requestId,
    JSON.parse(f.startRequest.body).request_id,
  )
})
test('credentials becoming stale inside a page transaction rolls back cache and continuation', async (t) => {
  const f = await staged(t)
  const before = await f.db.cachePartitions.get(f.ticket.partitionId)
  let current = true
  const stale = () => {
    current = false
  }
  f.db.cacheRecords.hook('creating', stale)
  await assert.rejects(
    f.store.commit(
      f.ticket,
      (await f.store.pending(f.ticket)).baseline.next,
      page(f.start, 'scan-0', 'scan-1', [row()]),
      f.identity,
      () => current,
    ),
    /session fenced/,
  )
  f.db.cacheRecords.hook('creating').unsubscribe(stale)
  assert.deepEqual(await f.db.cachePartitions.get(f.ticket.partitionId), before)
  assert.equal(await f.db.cacheRecords.count(), 0)
})

const proofCorruptions = {
  receipt_protocol: (b) => {
    const r = JSON.parse(b.receipt.response)
    r.protocol = 99
    b.receipt.response = canonicalJson(r)
  },
  receipt_missing_records: (b) => {
    const r = JSON.parse(b.receipt.response)
    delete r.records
    b.receipt.response = canonicalJson(r)
  },
  receipt_foreign_record: (b) => {
    const r = JSON.parse(b.receipt.response)
    r.records = [{ ...row(), payload: { ...row().payload, organization_id: 'foreign' } }]
    b.receipt.response = canonicalJson(r)
  },
  receipt_extra_key: (b) => {
    const r = JSON.parse(b.receipt.response)
    r.unexpected = true
    b.receipt.response = canonicalJson(r)
  },
  start_context_protocol: (b) => {
    const r = JSON.parse(b.startResponse)
    r.context.protocol = 99
    b.startResponse = canonicalJson(r)
  },
  start_foreign_realm: (b) => {
    const r = JSON.parse(b.startResponse)
    r.context.principal.api_realm = 'https://foreign.example'
    b.startResponse = canonicalJson(r)
  },
  invalid_baseline_uuid: (b) => {
    b.baselineId = 'not-uuid'
    const r = JSON.parse(b.startResponse)
    r.baseline_id = b.baselineId
    b.startResponse = canonicalJson(r)
    const p = JSON.parse(b.receipt.response)
    p.baseline_id = b.baselineId
    p.completion.baseline_id = b.baselineId
    b.receipt.response = canonicalJson(p)
  },
}
for (const [name, corrupt] of Object.entries(proofCorruptions))
  test(`corrupt retained proof blocks read/dispatch/offline/reuse: ${name}`, async (t) => {
    const { db, kernel, ticket } = await setup(t)
    const baseline = completedMetadata(ticket, context, 'checkpoint')
    corrupt(baseline)
    await db.cachePartitions.update(ticket.partitionId, {
      baseline,
      status: 'active',
      baselineComplete: true,
      cursor: 'checkpoint',
    })
    await db.deviceControl.update('device', { state: 'READY' })
    await db.operationJournal.add({ mutationId: 'preserved', original: { private: true } })
    await db.operationDelivery.add({ mutationId: 'preserved', state: 'pending' })
    await db.operationEvents.add({ mutationId: 'preserved', details: { retained: true } })
    const history = async () => [
      await db.operationJournal.toArray(),
      await db.operationDelivery.toArray(),
      await db.operationEvents.toArray(),
    ]
    const before = await history()
    await assert.rejects(kernel.readEntity(ticket, 'customer', 'customer'))
    await assert.rejects(kernel.listDispatchable(ticket, 1))
    await assert.rejects(kernel.continueOffline(ticket))
    const accepted = await kernel.acceptVerifiedContext(
      await kernel.beginVerification('reverify'),
      context,
    )
    assert.equal(accepted.state, 'BASELINE_REQUIRED')
    assert.deepEqual(await history(), before)
  })

test('hold transaction rolls back if captured session changes while committing', async (t) => {
  const f = await staged(t)
  const before = await f.db.cachePartitions.get(f.ticket.partitionId)
  const control = await f.db.deviceControl.get('device')
  let current = true
  const stale = () => {
    current = false
  }
  f.db.cachePartitions.hook('updating', stale)
  await assert.rejects(
    f.store.hold(f.ticket, before.baseline.next, 'invalid_response', null, () => current),
    /fenced/,
  )
  f.db.cachePartitions.hook('updating').unsubscribe(stale)
  assert.deepEqual(await f.db.cachePartitions.get(f.ticket.partitionId), before)
  assert.deepEqual(await f.db.deviceControl.get('device'), control)
})
test('failed-hold local disable is exact-ticket fenced and cannot disable a newer partition', async (t) => {
  const { kernel, ticket } = await setup(t)
  const winner = await kernel.beginBaseline(ticket)
  kernel.disableBaselineSession(ticket, () => true)
  assert.equal((await kernel.pendingBaseline(winner)).baseline.phase, 'start_pending')
  kernel.disableBaselineSession(winner, () => true)
  await assert.rejects(kernel.pendingBaseline(winner), /session/)
})
test('equal version preserves microseconds and rejects a one-microsecond contradiction atomically', async (t) => {
  const f = await staged(t)
  const original = row()
  original.payload.updated_at = '2026-10-14T09:00:00.123456Z'
  await commitNext(f, page(f.start, 'scan-0', 'scan-1', [original]))
  const equivalent = row()
  equivalent.payload.updated_at = '2026-10-14T10:00:00.123456+01:00'
  await commitNext(f, page(f.start, 'scan-1', 'scan-2', [equivalent]))
  const before = await f.db.cachePartitions.get(f.ticket.partitionId)
  const different = row()
  different.payload.updated_at = '2026-10-14T09:00:00.123457Z'
  await assert.rejects(
    commitNext(f, page(f.start, 'scan-2', 'scan-3', [different])),
    /contradiction/,
  )
  assert.deepEqual(await f.db.cachePartitions.get(f.ticket.partitionId), before)
})

test('actual server start deadline is authoritative when family creation follows context verification', async (t) => {
  const { db, kernel, ticket } = await setup(t)
  const baseline = completedMetadata(ticket, context, 'checkpoint')
  const original = JSON.parse(baseline.startResponse)
  // Actual FastAPI output differs by 35 microseconds: the server samples family
  // created_at after context.verified_at, so a client-inferred 30m maximum is wrong.
  original.context.verified_at = '2026-10-14T14:46:04.944988Z'
  original.context.offline_until = '2026-10-14T22:46:04Z'
  original.expires_at = '2026-10-14T15:16:04.945023Z'
  baseline.startResponse = canonicalJson(original)
  baseline.expiresAt = original.expires_at
  await db.cachePartitions.update(ticket.partitionId, {
    baseline,
    status: 'active',
    baselineComplete: true,
    cursor: 'checkpoint',
  })
  const accepted = await kernel.acceptVerifiedContext(
    await kernel.beginVerification('reverify'),
    context,
  )
  assert.equal(accepted.state, 'READY')
})

test('near-one-MiB valid page is not rejected by expanding canonical zero-fraction timestamps', async (t) => {
  const f = await staged(t)
  const response = page(f.start, 'scan-0', 'scan-1', [row(1, '')])
  const budget = 1048570
  const bytes = new TextEncoder().encode(JSON.stringify(response)).length
  response.records[0].payload.display_name = 'x'.repeat(budget - bytes)
  assert.equal(new TextEncoder().encode(JSON.stringify(response)).length, budget)
  await commitNext(f, response)
  assert.equal(
    (await f.db.cacheRecords.get([f.ticket.partitionId, 'customer', 'customer'])).payload
      .display_name.length,
    budget - bytes,
  )
})

test('latest receipt duplicate requires original wire spelling even when timestamps represent same instant', async (t) => {
  const f = await staged(t)
  const request = (await f.store.pending(f.ticket)).baseline.next
  const response = page(f.start, 'scan-0', 'scan-1', [row()])
  await f.store.commit(f.ticket, request, response, f.identity)
  const changed = structuredClone(response)
  changed.records[0].payload.updated_at = '2026-10-14T09:00:00.000000Z'
  await assert.rejects(f.store.commit(f.ticket, request, changed, f.identity), /Stale/)
  assert.equal(await f.store.commit(f.ticket, request, response, f.identity), 'duplicate')
})

test('quota and transaction-abort storage holds resume unchanged staging only after fresh verification', async (t) => {
  for (const reason of ['storage_full', 'storage_aborted']) {
    const f = await staged(t)
    const original = (await f.store.pending(f.ticket)).baseline
    await f.store.hold(f.ticket, original.next, reason)
    await assert.rejects(f.store.resume(f.ticket), /Fresh verification/)
    const accepted = await f.kernel.acceptVerifiedContext(
      await f.kernel.beginVerification(`recover-${reason}`),
      protocolContext,
    )
    await f.store.resume(accepted.ticket)
    const recovered = (await f.store.pending(accepted.ticket)).baseline
    assert.deepEqual(recovered.next, original.next)
    assert.equal(recovered.requestId, original.requestId)
    assert.deepEqual(recovered.origin, original.origin)
    assert.equal(recovered.hold, null)
  }
})

test('reload after baseline deadline preserves last delta request for a server-completed lost response', async (t) => {
  const f = await staged(t)
  await commitNext(f, page(f.start, 'scan-0', 'finalize-0', [], 'scan_complete'))
  await commitNext(f, {
    protocol: 1,
    baseline_id: f.start.baseline_id,
    authorization_epoch: protocolContext.authorizationEpoch,
    predecessor: 'finalize-0',
    continuation: 'delta-0',
  })
  const lastRequest = (await f.store.pending(f.ticket)).baseline.next
  // The server may have completed delta-0 before its baseline deadline while its
  // response was lost. Only the server knows that phase and retained family expiry.
  const later = NOW + 31 * 60 * 1000
  const renewed = {
    ...protocolContext,
    verifiedAt: new Date(later).toISOString(),
    offlineUntil: new Date(later + 3600000).toISOString(),
  }
  const kernel = new AccessKernel(f.db, { now: () => later, newId: () => crypto.randomUUID() })
  const accepted = await kernel.acceptVerifiedContext(
    await kernel.beginVerification('resume-lost-complete'),
    renewed,
  )
  const store = new BaselineTransactions(
    f.db,
    () => later,
    () => crypto.randomUUID(),
  )
  await store.resume(accepted.ticket)
  assert.deepEqual((await store.pending(accepted.ticket)).baseline.next, lastRequest)
  const identity = {
    ...f.identity,
    deviceGeneration: accepted.ticket.deviceGeneration,
    tabAttemptId: accepted.ticket.tabAttemptId,
    sessionHandle: 'renewed-session',
  }
  await store.commit(
    accepted.ticket,
    lastRequest,
    {
      ...page(f.start, 'delta-0', 'checkpoint-replay', [], 'complete'),
      completion: {
        baseline_id: f.start.baseline_id,
        authorization_epoch: protocolContext.authorizationEpoch,
        checkpoint: 'checkpoint-replay',
      },
    },
    identity,
  )
  assert.equal((await store.pending(accepted.ticket)).baseline.phase, 'activation_pending')
})

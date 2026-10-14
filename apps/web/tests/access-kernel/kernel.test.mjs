import 'fake-indexeddb/auto'
import test from 'node:test'
import assert from 'node:assert/strict'
import { createKernelDatabase } from '../../.tmp-kernel/src/access-kernel/database.js'
import { AccessKernel } from '../../.tmp-kernel/src/access-kernel/kernel.js'
import { principalKey } from '../../.tmp-kernel/src/access-kernel/context.js'

const NOW = Date.parse('2026-10-14T10:00:00.000Z')
function context(userId = 'A', overrides = {}) {
  return {
    protocol: 1,
    principal: { apiRealm: 'https://workshop.example/api/v1', organizationId: 'org', userId },
    accountLocationId: 'loc',
    selectedLocationId: 'loc',
    capabilities: ['customers.read', 'customers.write', 'sync.push'],
    authorizationEpoch: `${userId}-epoch`,
    policyRevision: 'read-v1',
    verifiedAt: new Date(NOW).toISOString(),
    offlineUntil: new Date(NOW + 3_600_000).toISOString(),
    snapshotProtocol: 'baseline-v1',
    ...overrides,
  }
}
function command(id = 'operation-A', entityId = 'customer-shared') {
  return {
    envelope: {
      mutation_id: id,
      entity_type: 'customer',
      entity_id: entityId,
      operation: 'create',
      organization_id: 'org',
      location_id: 'loc',
      base_version: null,
      occurred_at: new Date(NOW).toISOString(),
      payload: { display_name: 'Private A', unknown: { retained: true } },
    },
    optimistic: {
      customer_id: entityId,
      organization_id: 'org',
      location_id: 'loc',
      version: 1,
      display_name: 'Private A',
    },
    dependsOn: [],
    localEvents: [{ action: 'local-evidence', detail: { retained: true } }],
  }
}
async function setup(t) {
  const db = createKernelDatabase(`kernel-test-${crypto.randomUUID()}`)
  let now = NOW
  const kernel = new AccessKernel(db, { now: () => now, newId: () => crypto.randomUUID() })
  t.after(async () => {
    db.close()
    await db.delete()
  })
  await db.open()
  return {
    db,
    kernel,
    setNow(value) {
      now = value
    },
  }
}
async function verified(kernel, value = context()) {
  const attempt = await kernel.beginVerification(crypto.randomUUID())
  return kernel.acceptVerifiedContext(attempt, value)
}
// No production activation API exists. This is a trusted test fixture representing
// a baseline completed by the future authoritative integration, never a login.
async function completedBaseline(db, kernel, value = context()) {
  const initial = await verified(kernel, value)
  await db.cachePartitions.update(initial.ticket.partitionId, {
    baselineComplete: true,
    status: 'active',
    cursor: 'opaque-fixture-checkpoint',
  })
  const accepted = await verified(kernel, value)
  assert.equal(accepted.state, 'READY')
  return accepted.ticket
}

test('fresh verified context is blocked; no legacy data or queue is adopted', async (t) => {
  const { db, kernel } = await setup(t)
  await db.mutationQueue.put({
    ...command().envelope,
    state: 'pending',
    queued_at: 'legacy',
    unknown_author: 'A',
  })
  await db.customers.put(command().optimistic)
  const result = await verified(kernel)
  assert.equal(result.state, 'BASELINE_REQUIRED')
  await assert.rejects(
    kernel.readEntity(result.ticket, 'customer', 'customer-shared'),
    /baseline|ready/i,
  )
  await assert.rejects(kernel.listDispatchable(result.ticket, 10), /baseline|ready/i)
  assert.equal(await db.operationJournal.count(), 0)
  assert.equal(await db.mutationQueue.count(), 1)
})

test('same-scope A/B queues, overlays, conflicts and local evidence stay separate', async (t) => {
  const { db, kernel } = await setup(t)
  const a = await completedBaseline(db, kernel)
  const original = command()
  await kernel.commitLocalCommand(a, original)
  original.envelope.payload.display_name = 'caller mutation'
  assert.equal(
    (await kernel.readEntity(a, 'customer', 'customer-shared')).optimistic.display_name,
    'Private A',
  )
  const b = await completedBaseline(db, kernel, context('B'))
  assert.equal(await kernel.readEntity(b, 'customer', 'customer-shared'), undefined)
  assert.deepEqual((await kernel.listDispatchable(b, 10)).operations, [])
  assert.deepEqual(await kernel.readOperation(b, 'operation-A'), undefined)
  assert.equal(
    (await db.operationJournal.get('operation-A')).envelope.payload.display_name,
    'Private A',
  )
  await assert.rejects(kernel.commitLocalCommand(a, command('late-A')), /fenced|session/i)
  assert.equal(await db.operationJournal.get('late-A'), undefined)
})

test('lost ACK and fenced old results retain the original ID and full envelope', async (t) => {
  const { db, kernel } = await setup(t)
  let a = await completedBaseline(db, kernel)
  await kernel.commitLocalCommand(a, command())
  const first = await kernel.listDispatchable(a, 10)
  assert.equal(first.operations.length, 1)
  const before = await db.operationJournal.get('operation-A')
  const accepted = await verified(kernel)
  a = accepted.ticket
  await assert.rejects(
    kernel.applyPushResult(first.ticket, first, {
      results: [
        {
          mutation_id: 'operation-A',
          entity_id: 'customer-shared',
          status: 'applied',
          entity_version: 1,
        },
      ],
    }),
    /fenced|session/i,
  )
  const second = await kernel.listDispatchable(a, 10)
  assert.deepEqual(second.operations[0].envelope, first.operations[0].envelope)
  await kernel.applyPushResult(a, second, {
    results: [
      {
        mutation_id: 'operation-A',
        entity_id: 'customer-shared',
        status: 'applied',
        entity_version: 1,
      },
    ],
  })
  assert.equal((await db.operationDelivery.get('operation-A')).state, 'applied')
  assert.deepEqual(await db.operationJournal.get('operation-A'), before)
})

test('conflicts retain immutable full journal and events across reopen; independent work progresses', async (t) => {
  const { db, kernel } = await setup(t)
  const ticket = await completedBaseline(db, kernel)
  await kernel.commitLocalCommand(ticket, command())
  const child = command('dependent', 'other-customer')
  child.dependsOn = ['operation-A']
  await kernel.commitLocalCommand(ticket, child)
  await kernel.commitLocalCommand(ticket, command('independent', 'third-customer'))
  const batch = await kernel.listDispatchable(ticket, 10)
  assert.deepEqual(
    batch.operations.map((row) => row.mutationId),
    ['operation-A', 'independent'],
  )
  await kernel.applyPushResult(ticket, batch, {
    results: batch.operations.map((row) =>
      row.mutationId === 'operation-A'
        ? {
            mutation_id: row.mutationId,
            entity_id: row.entityId,
            status: 'conflict',
            entity_version: null,
            error_code: 'sync_conflict',
            error_message: 'stale base',
          }
        : {
            mutation_id: row.mutationId,
            entity_id: row.entityId,
            status: 'applied',
            entity_version: 1,
          },
    ),
  })
  await kernel.listDispatchable(ticket, 10)
  assert.equal((await db.operationDelivery.get('dependent')).state, 'held_dependency')
  const evidence = await kernel.readOperation(ticket, 'operation-A')
  assert.deepEqual(evidence.operation.envelope, command().envelope)
  assert.equal(evidence.delivery.state, 'rejected')
  assert.ok(evidence.events.some((row) => row.kind === 'local'))
  assert.ok(evidence.events.some((row) => row.kind === 'result'))
  db.close()
  await db.open()
  assert.deepEqual(await kernel.readOperation(ticket, 'operation-A'), evidence)
})

for (const [name, mutate] of [
  [
    'wrong entity',
    (rows) => {
      rows[0].entity_id = 'foreign'
    },
  ],
  [
    'unrequested ID',
    (rows) => {
      rows[0].mutation_id = 'unknown'
    },
  ],
  [
    'duplicate results',
    (rows) => {
      rows.push({ ...rows[0] })
    },
  ],
  [
    'invalid version',
    (rows) => {
      rows[0].entity_version = 0
    },
  ],
  [
    'fractional version',
    (rows) => {
      rows[0].entity_version = 1.5
    },
  ],
  [
    'invalid status',
    (rows) => {
      rows[0].status = 'ignored'
    },
  ],
  [
    'missing result',
    (rows) => {
      rows.pop()
    },
  ],
])
  test(`corrupt ACK (${name}) acknowledges nothing and holds the attempt`, async (t) => {
    const { db, kernel } = await setup(t)
    const ticket = await completedBaseline(db, kernel)
    await kernel.commitLocalCommand(ticket, command())
    await kernel.commitLocalCommand(ticket, command('independent', 'other'))
    const batch = await kernel.listDispatchable(ticket, 10)
    const rows = batch.operations.map((op) => ({
      mutation_id: op.mutationId,
      entity_id: op.entityId,
      status: 'applied',
      entity_version: 1,
    }))
    mutate(rows)
    await assert.rejects(
      kernel.applyPushResult(ticket, batch, { results: rows }),
      /invalid|mismatch/i,
    )
    assert.deepEqual(
      (await db.operationDelivery.toArray()).map((row) => row.state),
      ['held_integrity', 'held_integrity'],
    )
    assert.equal(await db.operationJournal.count(), 2)
  })

test('read-only/write-only/grant changes and unknown entities deny by default', async (t) => {
  const { db, kernel } = await setup(t)
  const ticket = await completedBaseline(
    db,
    kernel,
    context('A', { capabilities: ['customers.write', 'sync.push'] }),
  )
  await kernel.commitLocalCommand(ticket, command())
  await assert.rejects(kernel.readEntity(ticket, 'customer', 'customer-shared'), /capability/i)
  await assert.rejects(kernel.readOperation(ticket, 'operation-A'), /capability/i)
  await assert.rejects(
    kernel.readEntity(ticket, 'unknown', 'customer-shared'),
    /entity|capability/i,
  )
  const changed = await verified(
    kernel,
    context('A', { authorizationEpoch: 'revoked', capabilities: ['sync.push'] }),
  )
  assert.equal(changed.state, 'BASELINE_REQUIRED')
  await assert.rejects(kernel.listDispatchable(changed.ticket, 10), /baseline|ready/i)
  assert.equal(
    (await db.operationJournal.get('operation-A')).principalKey,
    principalKey(context().principal),
  )
})

test('offline continuation expires, rejects clock rollback and cannot resume from stored ticket on reload', async (t) => {
  const { db, kernel, setNow } = await setup(t)
  const ticket = await completedBaseline(db, kernel)
  await kernel.continueOffline(ticket)
  await kernel.commitLocalCommand(ticket, command())
  await assert.rejects(kernel.listDispatchable(ticket, 10), /online|ready/i)
  const reloaded = new AccessKernel(db, { now: () => NOW, newId: () => crypto.randomUUID() })
  await assert.rejects(reloaded.readEntity(ticket, 'customer', 'customer-shared'), /session/i)
  setNow(NOW - 1)
  await assert.rejects(kernel.readEntity(ticket, 'customer', 'customer-shared'), /clock|expired/i)
  setNow(NOW + 3_600_000)
  await assert.rejects(kernel.commitLocalCommand(ticket, command('expired')), /clock|expired/i)
})

test('stale logout cannot lock a newer principal in another tab', async (t) => {
  const { db, kernel } = await setup(t)
  const a = await completedBaseline(db, kernel)
  const secondTab = new AccessKernel(db, { now: () => NOW, newId: () => crypto.randomUUID() })
  const b = await completedBaseline(db, secondTab, context('B'))
  await assert.rejects(kernel.lockContext(a), /fenced|session/i)
  await secondTab.commitLocalCommand(b, command('B'))
  assert.equal(
    (await db.operationJournal.get('B')).principalKey,
    principalKey(context('B').principal),
  )
})

test('delayed command queued behind a winning identity switch cannot partially commit', async (t) => {
  const { db, kernel } = await setup(t)
  const a = await completedBaseline(db, kernel)
  // IDB readwrite transactions serialize on shared deviceControl, not a pre-await React check.
  const barrier = db.transaction('rw', db.deviceControl, async () => {
    const device = await db.deviceControl.get('device')
    await db.deviceControl.put({
      ...device,
      generation: device.generation + 1,
      state: 'VERIFYING',
      tabAttemptId: 'other-tab',
    })
  })
  const delayed = kernel.commitLocalCommand(a, command('delayed'))
  await barrier
  await assert.rejects(delayed, /fenced/i)
  assert.equal(await db.operationJournal.count(), 0)
  assert.equal(await db.operationDelivery.count(), 0)
  assert.equal(await db.operationEvents.count(), 0)
})

test('commit and conflict recording roll back atomically on storage failure', async (t) => {
  const { db, kernel } = await setup(t)
  const ticket = await completedBaseline(db, kernel)
  const failEvent = () => {
    throw new DOMException('simulated quota', 'QuotaExceededError')
  }
  db.operationEvents.hook('creating', failEvent)
  await assert.rejects(kernel.commitLocalCommand(ticket, command()), /quota/)
  assert.equal(await db.operationJournal.count(), 0)
  assert.equal(await db.operationDelivery.count(), 0)
  assert.equal((await db.deviceControl.get('device')).localSequence, 0)
  db.operationEvents.hook('creating').unsubscribe(failEvent)
  await kernel.commitLocalCommand(ticket, command())
  const batch = await kernel.listDispatchable(ticket, 10)
  db.operationEvents.hook('creating', failEvent)
  await assert.rejects(
    kernel.applyPushResult(ticket, batch, {
      results: [
        {
          mutation_id: 'operation-A',
          entity_id: 'customer-shared',
          status: 'conflict',
          entity_version: null,
          error_code: 'sync_conflict',
          error_message: 'kept',
        },
      ],
    }),
    /quota/,
  )
  assert.equal((await db.operationDelivery.get('operation-A')).state, 'inflight')
  assert.equal(
    (await db.operationJournal.get('operation-A')).envelope.payload.display_name,
    'Private A',
  )
  db.operationEvents.hook('creating').unsubscribe(failEvent)
})

test('journal and local evidence reject updates/deletion through the database adapter', async (t) => {
  const { db, kernel } = await setup(t)
  const ticket = await completedBaseline(db, kernel)
  await kernel.commitLocalCommand(ticket, command())
  await assert.rejects(
    db.operationJournal.update('operation-A', { envelope: command('different').envelope }),
    /immutable/i,
  )
  await assert.rejects(db.operationJournal.delete('operation-A'), /immutable/i)
  const event = (await db.operationEvents.toArray())[0]
  await assert.rejects(db.operationEvents.update(event.sequence, { details: {} }), /immutable/i)
  await assert.rejects(db.operationEvents.delete(event.sequence), /immutable/i)
})

test('two dispatchers cannot claim the same generation concurrently', async (t) => {
  const { db, kernel } = await setup(t)
  const ticket = await completedBaseline(db, kernel)
  await kernel.commitLocalCommand(ticket, command())
  const results = await Promise.allSettled([
    kernel.listDispatchable(ticket, 10),
    kernel.listDispatchable(ticket, 10),
  ])
  assert.equal(results.filter((result) => result.status === 'fulfilled').length, 1)
  assert.equal(results.filter((result) => result.status === 'rejected').length, 1)
  assert.equal((await db.operationDelivery.get('operation-A')).attempts, 1)
})

test('same-epoch lease renewal keeps the partition/cursor; changed grants never reuse it', async (t) => {
  const { db, kernel } = await setup(t)
  const original = await completedBaseline(db, kernel)
  const renewed = await verified(
    kernel,
    context('A', { offlineUntil: new Date(NOW + 7_200_000).toISOString() }),
  )
  assert.equal(renewed.ticket.partitionId, original.partitionId)
  assert.equal(
    (await db.cachePartitions.get(original.partitionId)).cursor,
    'opaque-fixture-checkpoint',
  )
  const changed = await verified(kernel, context('A', { capabilities: ['customers.read'] }))
  assert.equal(changed.state, 'BASELINE_REQUIRED')
  assert.notEqual(changed.ticket.partitionId, original.partitionId)
  assert.equal((await db.cachePartitions.get(changed.ticket.partitionId)).cursor, null)
  const oldAgain = await verified(kernel, context())
  assert.equal(oldAgain.state, 'BASELINE_REQUIRED')
  assert.notEqual(oldAgain.ticket.partitionId, original.partitionId)
})

test('author realm and workshop switches cannot retarget unchanged pending operations', async (t) => {
  const { db, kernel } = await setup(t)
  const original = await completedBaseline(db, kernel)
  await kernel.commitLocalCommand(original, command())
  for (const value of [
    context('A', {
      principal: { ...context().principal, apiRealm: 'https://other.example/api/v1' },
    }),
    context('A', { accountLocationId: 'other', selectedLocationId: 'other' }),
  ]) {
    const switched = await completedBaseline(db, kernel, value)
    assert.deepEqual((await kernel.listDispatchable(switched, 10)).operations, [])
    assert.equal(await kernel.readOperation(switched, 'operation-A'), undefined)
  }
  assert.deepEqual((await db.operationJournal.get('operation-A')).envelope, command().envelope)
})

test('held earlier work blocks the same aggregate without blocking independent aggregates', async (t) => {
  const { db, kernel } = await setup(t)
  const ticket = await completedBaseline(db, kernel)
  await kernel.commitLocalCommand(ticket, command())
  await kernel.commitLocalCommand(ticket, command('same-aggregate'))
  await kernel.commitLocalCommand(ticket, command('independent', 'other'))
  await db.operationDelivery.update('operation-A', { state: 'held_integrity' })
  const batch = await kernel.listDispatchable(ticket, 10)
  assert.deepEqual(
    batch.operations.map((operation) => operation.mutationId),
    ['independent'],
  )
  assert.equal((await db.operationDelivery.get('same-aggregate')).state, 'held_dependency')
})

test('same-ID retry cannot silently replace local event evidence', async (t) => {
  const { db, kernel } = await setup(t)
  const ticket = await completedBaseline(db, kernel)
  await kernel.commitLocalCommand(ticket, command())
  await kernel.commitLocalCommand(ticket, command())
  const changed = command()
  changed.localEvents = [{ action: 'replaced' }]
  await assert.rejects(kernel.commitLocalCommand(ticket, changed), /collision|immutable/i)
  assert.equal(await db.operationEvents.count(), 1)
})

for (const reason of ['unauthorized', 'forbidden'])
  test(`${reason} holds work and stops dispatch without false acknowledgement`, async (t) => {
    const { db, kernel } = await setup(t)
    const ticket = await completedBaseline(db, kernel)
    await kernel.commitLocalCommand(ticket, command())
    const batch = await kernel.listDispatchable(ticket, 10)
    await kernel.deferDispatch(ticket, batch, reason)
    assert.equal((await db.operationDelivery.get('operation-A')).state, 'held_authorization')
    assert.equal((await db.operationDelivery.get('operation-A')).result, null)
    await assert.rejects(kernel.listDispatchable(ticket, 10), /ready/i)
    assert.deepEqual((await db.operationJournal.get('operation-A')).envelope, command().envelope)
  })

test('transient retry obeys backoff and reuses the exact envelope/ID', async (t) => {
  const { db, kernel, setNow } = await setup(t)
  const ticket = await completedBaseline(db, kernel)
  await kernel.commitLocalCommand(ticket, command())
  const first = await kernel.listDispatchable(ticket, 10)
  await kernel.deferDispatch(ticket, first, 'transient')
  assert.deepEqual((await kernel.listDispatchable(ticket, 10)).operations, [])
  setNow(NOW + 2000)
  const retry = await kernel.listDispatchable(ticket, 10)
  assert.deepEqual(retry.operations, first.operations)
  assert.equal((await db.operationDelivery.get('operation-A')).attempts, 2)
})

test('in-flight repository arguments are captured before the first asynchronous boundary', async (t) => {
  const { db, kernel } = await setup(t)
  const ticket = await completedBaseline(db, kernel)
  const suppliedTicket = structuredClone(ticket)
  const pending = kernel.commitLocalCommand(suppliedTicket, command())
  suppliedTicket.principalKey = 'foreign-after-call'
  await pending
  assert.equal((await db.operationJournal.get('operation-A')).principalKey, ticket.principalKey)
})

test('confirmed projections are partitioned and their payload scope/version is validated', async (t) => {
  const { db, kernel } = await setup(t)
  const a = await completedBaseline(db, kernel)
  const payload = command().optimistic
  await db.cacheRecords.add({
    partitionId: a.partitionId,
    entityType: 'customer',
    entityId: 'customer-shared',
    version: 1,
    payload,
  })
  assert.deepEqual((await kernel.readEntity(a, 'customer', 'customer-shared')).confirmed, payload)
  await db.cacheRecords.update([a.partitionId, 'customer', 'customer-shared'], { version: 2 })
  await assert.rejects(kernel.readEntity(a, 'customer', 'customer-shared'), /version|integrity/i)
  await db.cacheRecords.update([a.partitionId, 'customer', 'customer-shared'], {
    version: 1,
    payload: { ...payload, location_id: 'foreign' },
  })
  await assert.rejects(kernel.readEntity(a, 'customer', 'customer-shared'), /scope/i)
  const b = await completedBaseline(db, kernel, context('B'))
  assert.equal(await kernel.readEntity(b, 'customer', 'customer-shared'), undefined)
})

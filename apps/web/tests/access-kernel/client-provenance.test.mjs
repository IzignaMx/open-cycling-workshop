import test from 'node:test'
import assert from 'node:assert/strict'
import { setup, command, context, completedBaseline } from './client-fixture.mjs'

test('new incarnation recovery holds pending, uncertain and applied overlays without rewriting history', async (t) => {
  const { db, kernel } = await setup(t)
  const old = await completedBaseline(db, kernel)
  for (const id of ['pending', 'uncertain', 'applied'])
    await kernel.commitLocalCommand(old, command(id, id))
  await db.operationDelivery.update('uncertain', { state: 'awaiting_confirmation' })
  await db.operationDelivery.update('applied', {
    state: 'applied',
    dispatchable: 0,
    unresolved: 0,
    resultVersion: 1,
    result: { mutation_id: 'applied', entity_id: 'applied', status: 'applied', entity_version: 1 },
  })
  const original = await db.operationJournal.toArray()
  const ticket = await completedBaseline(
    db,
    kernel,
    context('A', { datasetIncarnation: '0199ba00-0000-7000-8000-000000000002' }),
  )
  for (const id of ['pending', 'uncertain', 'applied']) {
    assert.equal(await kernel.readEntity(ticket, 'customer', id), undefined)
    assert.equal((await kernel.readOperation(ticket, id)).delivery.state, 'held_recovery')
  }
  assert.deepEqual(await db.operationJournal.toArray(), original)
  assert.deepEqual((await kernel.listDispatchable(ticket, 10)).operations, [])
  await kernel.commitLocalCommand(ticket, command('fresh', 'fresh'))
  assert.equal((await kernel.listDispatchable(ticket, 10)).operations[0].mutationId, 'fresh')
})

test('group commit is atomic and captured-current checks run before transaction resolves', async (t) => {
  const { db, kernel } = await setup(t)
  const ticket = await completedBaseline(db, kernel)
  const second = command('second', 'second')
  second.dependsOn = ['first']
  let current = true
  const switchSession = () => {
    current = false
  }
  db.operationEvents.hook('creating', switchSession)
  await assert.rejects(
    kernel.commitLocalCommands(ticket, [command('first', 'first'), second], () => current),
    /fenced/,
  )
  assert.equal(await db.operationJournal.count(), 0)
  db.operationEvents.hook('creating').unsubscribe(switchSession)
  assert.deepEqual(await kernel.commitLocalCommands(ticket, [command('first', 'first'), second]), [
    'first',
    'second',
  ])
  assert.equal(
    (await db.operationJournal.get('first')).authoredDatasetIncarnation,
    context().datasetIncarnation,
  )
})

for (const action of ['dispatch', 'ack', 'defer'])
  test(`${action} stale captured callback rolls transaction back`, async (t) => {
    const { db, kernel } = await setup(t)
    const ticket = await completedBaseline(db, kernel)
    await kernel.commitLocalCommand(ticket, command())
    const batch = action === 'dispatch' ? null : await kernel.listDispatchable(ticket, 10)
    let current = true
    const switchSession = () => {
      current = false
    }
    db.operationEvents.hook('creating', switchSession)
    const before = await db.operationDelivery.toArray()
    const call =
      action === 'dispatch'
        ? kernel.listDispatchable(ticket, 10, () => current)
        : action === 'ack'
          ? kernel.applyPushResult(
              ticket,
              batch,
              {
                results: [
                  {
                    mutation_id: 'operation-A',
                    entity_id: 'customer-shared',
                    status: 'applied',
                    entity_version: 1,
                  },
                ],
              },
              () => current,
            )
          : kernel.deferDispatch(ticket, batch, 'transient', () => current)
    await assert.rejects(call, /fenced/)
    assert.deepEqual(await db.operationDelivery.toArray(), before)
  })

test('missing incarnation remains recovery-only, and cannot become a new command dependency', async (t) => {
  const { db, kernel } = await setup(t)
  let ticket = await completedBaseline(db, kernel)
  await kernel.commitLocalCommand(ticket, command('source', 'source'))
  const row = await db.operationJournal.get('source')
  delete row.authoredDatasetIncarnation
  row.mutationId = 'missing'
  row.entityId = 'missing'
  row.envelope = { ...row.envelope, mutation_id: 'missing', entity_id: 'missing' }
  const { canonicalJson } = await import('../../.tmp-kernel/src/access-kernel/operations.js')
  row.envelopeCanonical = canonicalJson(row.envelope)
  row.optimistic.customer_id = 'missing'
  row.localSequence = 2
  await db.operationJournal.add(row)
  const delivery = await db.operationDelivery.get('source')
  await db.operationDelivery.add({
    ...delivery,
    mutationId: 'missing',
    entityId: 'missing',
    localSequence: 2,
  })
  await db.deviceControl.update('device', { localSequence: 2 })
  ticket = await completedBaseline(db, kernel)
  assert.equal((await kernel.readOperation(ticket, 'missing')).delivery.state, 'held_recovery')
  assert.equal(await kernel.readEntity(ticket, 'customer', 'missing'), undefined)
  const next = command('dependent', 'dependent')
  next.dependsOn = ['missing']
  await assert.rejects(kernel.commitLocalCommand(ticket, next), /Dependency/)
  assert.equal((await db.operationJournal.get('missing')).authoredDatasetIncarnation, undefined)
})

test('grouped intake resolves reference and aggregate dependencies in the same transaction', async (t) => {
  const { db, kernel } = await setup(t)
  const ticket = await completedBaseline(
    db,
    kernel,
    context('A', {
      capabilities: [
        'customers.read',
        'customers.write',
        'bicycles.read',
        'bicycles.write',
        'orders.read',
        'orders.write',
        'sync.push',
      ],
    }),
  )
  const customer = command('customer-create', 'customer-id')
  const bicycle = command('bicycle-create', 'bicycle-id')
  bicycle.envelope.entity_type = 'bicycle'
  bicycle.optimistic = {
    bicycle_id: 'bicycle-id',
    customer_id: 'customer-id',
    organization_id: 'org',
    location_id: 'loc',
    version: 1,
  }
  bicycle.envelope.payload = { customer_id: 'customer-id' }
  const order = command('order-create', 'order-id')
  order.envelope.entity_type = 'service_order'
  order.optimistic = {
    order_id: 'order-id',
    customer_id: 'customer-id',
    bicycle_id: 'bicycle-id',
    organization_id: 'org',
    location_id: 'loc',
    version: 1,
  }
  order.envelope.payload = { customer_id: 'customer-id', bicycle_id: 'bicycle-id' }
  await kernel.commitLocalCommands(ticket, [customer, bicycle, order])
  assert.deepEqual((await db.operationJournal.get('bicycle-create')).dependsOn, ['customer-create'])
  assert.deepEqual((await db.operationJournal.get('order-create')).dependsOn, [
    'customer-create',
    'bicycle-create',
  ])
  const update = structuredClone(order)
  update.envelope.mutation_id = 'order-update'
  update.envelope.operation = 'update'
  update.envelope.base_version = 1
  update.optimistic.version = 2
  await kernel.commitLocalCommand(ticket, update)
  assert.ok((await db.operationJournal.get('order-update')).dependsOn.includes('order-create'))
  await kernel.commitLocalCommands(ticket, [customer, bicycle, order])
  assert.equal(await db.operationJournal.count(), 4)
})

test('exact nine-field wire command rejects QueuedMutation delivery metadata', async (t) => {
  const { db, kernel } = await setup(t)
  const ticket = await completedBaseline(db, kernel)
  const old = command()
  old.envelope.state = 'pending'
  await assert.rejects(kernel.commitLocalCommand(ticket, old), /wire envelope/)
})

test('stale update draft fails before appending an alternative aggregate version', async (t) => {
  const { db, kernel } = await setup(t)
  const ticket = await completedBaseline(db, kernel)
  await kernel.commitLocalCommand(ticket, command('create', 'aggregate'))
  const update = command('first-update', 'aggregate')
  update.envelope.operation = 'update'
  update.envelope.base_version = 1
  update.optimistic.version = 2
  await kernel.commitLocalCommand(ticket, update)
  const stale = structuredClone(update)
  stale.envelope.mutation_id = 'stale-update'
  await assert.rejects(kernel.commitLocalCommand(ticket, stale), /version changed/)
  assert.equal(await db.operationJournal.count(), 2)
})

for (const [code, state] of [
  ['legacy_receipt_unverified', 'held_recovery'],
  ['receipt_integrity_conflict', 'held_integrity'],
  ['receipt_proof_conflict', 'held_integrity'],
])
  test(`bound receipt ${code} remains an explicit immutable recovery state`, async (t) => {
    const { db, kernel } = await setup(t)
    const ticket = await completedBaseline(db, kernel)
    await kernel.commitLocalCommand(ticket, command())
    const original = await db.operationJournal.get('operation-A')
    const batch = await kernel.listDispatchable(ticket, 10)
    await kernel.applyPushResult(ticket, batch, {
      results: [
        {
          mutation_id: 'operation-A',
          entity_id: 'customer-shared',
          status: 'conflict',
          entity_version: null,
          error_code: code,
          error_message: 'retained receipt refusal',
        },
      ],
    })
    assert.equal((await db.operationDelivery.get('operation-A')).state, state)
    assert.deepEqual(await db.operationJournal.get('operation-A'), original)
    assert.equal(await kernel.readEntity(ticket, 'customer', 'customer-shared'), undefined)
  })

test('lease expiry during local transaction aborts all staged command records', async (t) => {
  const { db, kernel, setNow } = await setup(t)
  const ticket = await completedBaseline(db, kernel)
  const expire = () => setNow(Date.parse(context().offlineUntil))
  db.operationEvents.hook('creating', expire)
  await assert.rejects(kernel.commitLocalCommand(ticket, command()), /expired|lease/)
  assert.equal(await db.operationJournal.count(), 0)
  assert.equal(await db.operationDelivery.count(), 0)
})

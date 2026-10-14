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

for (const mode of ['confirmed', 'unconfirmed', 'explicit-old-dependency'])
  test(`restored ${mode} prerequisite never adopts old-incarnation history`, async (t) => {
    const { db, kernel } = await setup(t)
    const grants = [
      'customers.read',
      'customers.write',
      'bicycles.read',
      'bicycles.write',
      'sync.push',
    ]
    const originalTicket = await completedBaseline(
      db,
      kernel,
      context('A', { capabilities: grants }),
    )
    const customer = command('original-customer-create', 'restored-customer')
    await kernel.commitLocalCommand(originalTicket, customer)
    const batch = await kernel.listDispatchable(originalTicket, 10)
    await kernel.applyPushResult(originalTicket, batch, {
      results: [
        {
          mutation_id: 'original-customer-create',
          entity_id: 'restored-customer',
          status: 'applied',
          entity_version: 1,
        },
      ],
    })
    const original = await db.operationJournal.get('original-customer-create')
    const freshContext = context('A', {
      capabilities: grants,
      datasetIncarnation: '0199ba00-0000-7000-8000-000000000002',
    })
    const ticket = await completedBaseline(db, kernel, freshContext)
    if (mode !== 'unconfirmed')
      await db.cacheRecords.add({
        partitionId: ticket.partitionId,
        entityType: 'customer',
        entityId: 'restored-customer',
        version: 1,
        payload: customer.optimistic,
      })
    const bicycle = command('new-bicycle-create', 'new-bicycle')
    bicycle.envelope.entity_type = 'bicycle'
    bicycle.envelope.payload = { customer_id: 'restored-customer' }
    bicycle.optimistic = {
      bicycle_id: 'new-bicycle',
      customer_id: 'restored-customer',
      organization_id: 'org',
      location_id: 'loc',
      version: 1,
    }
    if (mode === 'explicit-old-dependency') bicycle.dependsOn = ['original-customer-create']
    if (mode === 'confirmed') {
      await kernel.commitLocalCommand(ticket, bicycle)
      const fresh = await db.operationJournal.get('new-bicycle-create')
      assert.deepEqual(fresh.dependsOn, [])
      assert.equal(fresh.authoredDatasetIncarnation, freshContext.datasetIncarnation)
      assert.equal(
        (await kernel.readEntity(ticket, 'bicycle', 'new-bicycle')).optimistic.bicycle_id,
        'new-bicycle',
      )
      assert.deepEqual(
        (await kernel.listDispatchable(ticket, 10)).operations.map((row) => row.mutationId),
        ['new-bicycle-create'],
      )
      await kernel.commitLocalCommand(ticket, bicycle)
    } else {
      await assert.rejects(
        kernel.commitLocalCommand(ticket, bicycle),
        /Dependency author or scope mismatch/,
      )
      assert.equal(await db.operationJournal.get('new-bicycle-create'), undefined)
    }
    assert.deepEqual(await db.operationJournal.get('original-customer-create'), original)
    assert.equal(
      (await db.operationDelivery.get('original-customer-create')).state,
      'held_recovery',
    )
  })

test('fresh same-entity update uses restored confirmed aggregate while old history stays held', async (t) => {
  const { db, kernel } = await setup(t)
  const first = await completedBaseline(db, kernel)
  const old = command('old-create', 'restored-aggregate')
  await kernel.commitLocalCommand(first, old)
  const ticket = await completedBaseline(
    db,
    kernel,
    context('A', { datasetIncarnation: '0199ba00-0000-7000-8000-000000000002' }),
  )
  await db.cacheRecords.add({
    partitionId: ticket.partitionId,
    entityType: 'customer',
    entityId: 'restored-aggregate',
    version: 1,
    payload: old.optimistic,
  })
  const fresh = command('fresh-update', 'restored-aggregate')
  fresh.envelope.operation = 'update'
  fresh.envelope.base_version = 1
  fresh.optimistic.version = 2
  fresh.optimistic.display_name = 'Independent current update'
  await kernel.commitLocalCommand(ticket, fresh)
  assert.deepEqual((await db.operationJournal.get('fresh-update')).dependsOn, [])
  assert.equal(
    (await kernel.readEntity(ticket, 'customer', 'restored-aggregate')).optimistic.display_name,
    'Independent current update',
  )
  assert.deepEqual(
    (await kernel.listDispatchable(ticket, 10)).operations.map((row) => row.mutationId),
    ['fresh-update'],
  )
  assert.equal((await db.operationDelivery.get('old-create')).state, 'held_recovery')
})

test('confirmed reference ignores unrelated rejected same-incarnation edits while exact retries preserve genuine create dependencies', async (t) => {
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
        'sync.push',
      ],
    }),
  )
  const customer = command('customer-create', 'confirmed-customer')
  await kernel.commitLocalCommand(ticket, customer)
  const bicycle = command('dependent-bicycle', 'dependent-bicycle')
  bicycle.envelope.entity_type = 'bicycle'
  bicycle.envelope.payload = { customer_id: 'confirmed-customer' }
  bicycle.optimistic = {
    bicycle_id: 'dependent-bicycle',
    customer_id: 'confirmed-customer',
    organization_id: 'org',
    location_id: 'loc',
    version: 1,
  }
  await kernel.commitLocalCommand(ticket, bicycle)
  assert.deepEqual((await db.operationJournal.get('dependent-bicycle')).dependsOn, [
    'customer-create',
  ])
  const batch = await kernel.listDispatchable(ticket, 1)
  await kernel.applyPushResult(ticket, batch, {
    results: [
      {
        mutation_id: 'customer-create',
        entity_id: 'confirmed-customer',
        status: 'applied',
        entity_version: 1,
      },
    ],
  })
  await db.cacheRecords.add({
    partitionId: ticket.partitionId,
    entityType: 'customer',
    entityId: 'confirmed-customer',
    version: 1,
    payload: customer.optimistic,
  })
  await kernel.commitLocalCommand(ticket, bicycle)
  assert.deepEqual((await db.operationJournal.get('dependent-bicycle')).dependsOn, [
    'customer-create',
  ])
  const update = command('rejected-customer-update', 'confirmed-customer')
  update.envelope.operation = 'update'
  update.envelope.base_version = 1
  update.optimistic.version = 2
  await kernel.commitLocalCommand(ticket, update)
  const pending = await kernel.listDispatchable(ticket, 10)
  await kernel.applyPushResult(ticket, pending, {
    results: pending.operations.map((op) => ({
      mutation_id: op.mutationId,
      entity_id: op.entityId,
      status: 'conflict',
      entity_version: null,
      error_code: 'sync_conflict',
      error_message: 'rejected',
    })),
  })
  const fresh = structuredClone(bicycle)
  fresh.envelope.mutation_id = 'independent-bicycle'
  fresh.envelope.entity_id = 'independent-bicycle'
  fresh.optimistic.bicycle_id = 'independent-bicycle'
  await kernel.commitLocalCommand(ticket, fresh)
  assert.deepEqual((await db.operationJournal.get('independent-bicycle')).dependsOn, [])
  assert.deepEqual(
    (await kernel.listDispatchable(ticket, 10)).operations.map((row) => row.mutationId),
    ['independent-bicycle'],
  )
})

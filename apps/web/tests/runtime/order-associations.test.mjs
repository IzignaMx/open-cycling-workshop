import test from 'node:test'
import assert from 'node:assert/strict'
import { setup, login, api, response, until } from './runtime-fixture.mjs'
async function fixture(t) {
  const f = setup(t)
  await login(f.runtime)
  f.env.online = false
  await f.runtime.offline()
  await f.runtime.createOrder({
    customerId: 'historical-A',
    reportedProblem: 'Frenos',
    intakeCondition: null,
    accessories: null,
    priority: 'normal',
    brand: 'Trek',
    model: 'FX',
  })
  return { ...f, order: f.runtime.getSnapshot().orders[0] }
}
test('saved order reads exact customer and bicycle locally without new writes or network', async (t) => {
  const f = await fixture(t)
  const before = await f.database.operationJournal.toArray()
  const network = f.server.calls.length
  await f.runtime.loadOrderAssociations(f.order.order_id)
  const result = f.runtime.getSnapshot().orderAssociations
  assert.equal(result.status, 'ready')
  assert.equal(result.orderId, f.order.order_id)
  assert.deepEqual(result.customer, { status: 'available', id: 'historical-A', name: 'Private A' })
  assert.deepEqual(result.bicycle, {
    status: 'available',
    id: f.order.bicycle_id,
    brand: 'Trek',
    model: 'FX',
  })
  assert.deepEqual(await f.database.operationJournal.toArray(), before)
  assert.equal(f.server.calls.length, network)
})
test('refresh invalidates association snapshot and delayed old lookup cannot republish', async (t) => {
  const f = await fixture(t)
  const original = f.runtime.repositories.orderAssociations.bind(f.runtime.repositories)
  let release, entered
  const wait = new Promise((r) => {
      release = r
    }),
    started = new Promise((r) => {
      entered = r
    })
  t.mock.method(f.runtime.repositories, 'orderAssociations', async (...args) => {
    const x = await original(...args)
    entered()
    await wait
    return x
  })
  const pending = f.runtime.loadOrderAssociations(f.order.order_id)
  await started
  await f.runtime.refresh('service_order')
  release()
  await pending
  assert.equal(f.runtime.getSnapshot().orderAssociations, null)
})
test('a failed read is generic and safely retryable', async (t) => {
  const f = await fixture(t)
  const original = f.runtime.repositories.orderAssociations.bind(f.runtime.repositories)
  t.mock.method(f.runtime.repositories, 'orderAssociations', async () => {
    throw Error('private database path')
  })
  await f.runtime.loadOrderAssociations(f.order.order_id)
  assert.equal(f.runtime.getSnapshot().orderAssociations.status, 'failed')
  assert.doesNotMatch(JSON.stringify(f.runtime.getSnapshot().orderAssociations), /private database/)
  f.runtime.repositories.orderAssociations = original
  await f.runtime.loadOrderAssociations(f.order.order_id)
  assert.equal(f.runtime.getSnapshot().orderAssociations.status, 'ready')
})

test('absent versus unavailable bicycle is explicit and blocked projections are not revealed', async (t) => {
  const f = await fixture(t)
  const read = f.runtime.kernel.readEntity.bind(f.runtime.kernel)
  t.mock.method(f.runtime.kernel, 'readEntity', async (...args) =>
    args[1] === 'bicycle' ? undefined : read(...args),
  )
  await f.runtime.loadOrderAssociations(f.order.order_id)
  assert.deepEqual(f.runtime.getSnapshot().orderAssociations.bicycle, { status: 'unavailable' })
  f.runtime.kernel.readEntity = async (...args) =>
    args[1] === 'bicycle'
      ? { blocked: true, optimistic: { brand: 'Blocked secret' } }
      : read(...args)
  await f.runtime.loadOrderAssociations(f.order.order_id)
  assert.deepEqual(f.runtime.getSnapshot().orderAssociations.bicycle, { status: 'unavailable' })
  f.runtime.kernel.readEntity = read
  await f.runtime.createOrder({
    customerId: 'historical-A',
    reportedProblem: 'Sin bicicleta',
    intakeCondition: null,
    accessories: null,
    priority: 'normal',
    brand: null,
    model: null,
  })
  const id = f.runtime
    .getSnapshot()
    .orders.find((o) => o.reported_problem === 'Sin bicicleta').order_id
  await f.runtime.loadOrderAssociations(id)
  assert.deepEqual(f.runtime.getSnapshot().orderAssociations.bicycle, { status: 'none' })
})
test('double click is one flight and logout fences old completion', async (t) => {
  const f = await fixture(t)
  const original = f.runtime.repositories.orderAssociations.bind(f.runtime.repositories)
  let release,
    entered,
    calls = 0
  const gate = new Promise((r) => {
      release = r
    }),
    started = new Promise((r) => {
      entered = r
    })
  t.mock.method(f.runtime.repositories, 'orderAssociations', async (...args) => {
    calls++
    const result = await original(...args)
    entered()
    await gate
    return result
  })
  const first = f.runtime.loadOrderAssociations(f.order.order_id)
  await started
  await f.runtime.loadOrderAssociations(f.order.order_id)
  assert.equal(calls, 1)
  await f.runtime.logout()
  release()
  await first
  assert.equal(f.runtime.getSnapshot().orderAssociations, null)
})
test('readback reloads admitted local associations without persisting presentation or replay', async (t) => {
  const f = await fixture(t)
  await f.runtime.loadOrderAssociations(f.order.order_id)
  const before = await f.database.operationJournal.toArray()
  f.runtime.dispose()
  const second = setup(t, { name: f.name, storage: f.storage, online: false })
  await second.runtime.start()
  assert.equal(second.runtime.getSnapshot().orderAssociations, null)
  await second.runtime.loadOrderAssociations(f.order.order_id)
  assert.equal(second.runtime.getSnapshot().orderAssociations.bicycle.brand, 'Trek')
  assert.deepEqual(await second.database.operationJournal.toArray(), before)
  assert.equal(second.server.calls.length, 0)
})
for (const denied of ['customers.read', 'bicycles.read'])
  test(`independent ${denied} denial avoids both lookup and data disclosure`, async (t) => {
    const original = api()
    const server = {
      fetch: async (url, init) => {
        const data = await (await original.fetch(url, init)).json()
        const context = new URL(url).pathname.endsWith('/auth/context') ? data : data.context
        if (context?.capabilities)
          context.capabilities = context.capabilities.filter((c) => c !== denied)
        if (denied === 'customers.read' && Array.isArray(data.records))
          data.records = data.records.filter((row) => row.entity_type !== 'customer')
        return response(url, data)
      },
    }
    const f = setup(t, { server })
    f.runtime.scheduleSync = () => {}
    await f.runtime.login({ organization_id: 'org', username: 'A', password: 'synthetic' })
    await until(() => f.runtime.getSnapshot().phase === 'ready', 'restricted ready')
    await f.runtime.createOrder({
      customerId: 'historical-A',
      reportedProblem: 'Restricted',
      intakeCondition: null,
      accessories: null,
      priority: 'normal',
      brand: 'Hidden brand',
      model: 'Hidden model',
    })
    const id = f.runtime.getSnapshot().orders[0].order_id,
      reads = []
    const read = f.runtime.kernel.readEntity.bind(f.runtime.kernel)
    t.mock.method(f.runtime.kernel, 'readEntity', (...args) => {
      reads.push(args[1])
      return read(...args)
    })
    await f.runtime.loadOrderAssociations(id)
    const association = denied === 'customers.read' ? 'customer' : 'bicycle'
    assert.deepEqual(f.runtime.getSnapshot().orderAssociations[association], {
      status: 'restricted',
    })
    assert.equal(reads.includes(association), false)
  })
test('revoked read grant clears already displayed associated identity', async (t) => {
  const original = api()
  let revoked = false
  const server = {
    fetch: async (url, init) => {
      const data = await (await original.fetch(url, init)).json()
      const context = new URL(url).pathname.endsWith('/auth/context') ? data : data.context
      if (revoked && context?.capabilities)
        context.capabilities = context.capabilities.filter(
          (c) => !['customers.read', 'bicycles.read'].includes(c),
        )
      return response(url, data)
    },
  }
  const f = setup(t, { server })
  f.runtime.scheduleSync = () => {}
  await login(f.runtime)
  await f.runtime.createOrder({
    customerId: 'historical-A',
    reportedProblem: 'Revoke',
    intakeCondition: null,
    accessories: null,
    priority: 'normal',
    brand: 'Trek',
    model: 'FX',
  })
  await f.runtime.loadOrderAssociations(f.runtime.getSnapshot().orders[0].order_id)
  assert.equal(f.runtime.getSnapshot().orderAssociations.customer.name, 'Private A')
  revoked = true
  await f.runtime.retryVerification()
  assert.equal(f.runtime.getSnapshot().orderAssociations, null)
})
test('changed relationship during lookup cannot publish old associated identity', async (t) => {
  const f = await fixture(t)
  const read = f.runtime.kernel.readEntity.bind(f.runtime.kernel)
  let orderReads = 0
  t.mock.method(f.runtime.kernel, 'readEntity', async (...args) => {
    const result = await read(...args)
    if (args[1] === 'service_order' && ++orderReads === 2)
      return { ...result, optimistic: { ...result.optimistic, customer_id: 'other' } }
    return result
  })
  await f.runtime.loadOrderAssociations(f.order.order_id)
  assert.deepEqual(f.runtime.getSnapshot().orderAssociations, {
    orderId: f.order.order_id,
    status: 'failed',
  })
})
test('unknown order cannot cause arbitrary customer or bicycle lookup', async (t) => {
  const f = await fixture(t)
  let calls = 0
  t.mock.method(f.runtime.repositories, 'orderAssociations', async () => {
    calls++
    return null
  })
  await f.runtime.loadOrderAssociations('unknown-order')
  assert.equal(calls, 0)
  assert.equal(f.runtime.getSnapshot().orderAssociations, null)
})

test('actual App wires the readback action and independent visibility gates', async (t) => {
  const { appHarness } = await import('./capture-component-host.mjs')
  const f = await fixture(t)
  const app = appHarness(f.runtime, { layoutEffects: true })
  const nodes = (node) =>
    !node || typeof node !== 'object'
      ? []
      : [node, ...[node.props?.children].flat(Infinity).flatMap(nodes)]
  const list = nodes(app.render()).find((node) => node.type?.name === 'OrderList')
  assert.equal(list.props.canReadCustomerInfo, true)
  assert.equal(list.props.canReadBicycleInfo, true)
  await list.props.onAssociations(f.order.order_id)
  const updated = nodes(app.render()).find((node) => node.type?.name === 'OrderList')
  assert.equal(updated.props.associations.customer.name, 'Private A')
  updated.props.onCloseAssociations(f.order.order_id)
  const remounted = appHarness(f.runtime, { layoutEffects: true })
  assert.equal(
    nodes(remounted.render()).find((node) => node.type?.name === 'OrderList').props.associations,
    null,
  )
})

test('explicit close fences a pending result and later reopening is a fresh read', async (t) => {
  const f = await fixture(t)
  const original = f.runtime.repositories.orderAssociations.bind(f.runtime.repositories)
  let release,
    entered,
    calls = 0
  const gate = new Promise((r) => {
      release = r
    }),
    started = new Promise((r) => {
      entered = r
    })
  t.mock.method(f.runtime.repositories, 'orderAssociations', async (...args) => {
    calls++
    const result = await original(...args)
    entered()
    await gate
    return result
  })
  const first = f.runtime.loadOrderAssociations(f.order.order_id)
  await started
  f.runtime.closeOrderAssociations(f.order.order_id)
  assert.equal(f.runtime.getSnapshot().orderAssociations, null)
  release()
  await first
  assert.equal(f.runtime.getSnapshot().orderAssociations, null)
  await f.runtime.loadOrderAssociations(f.order.order_id)
  assert.equal(calls, 2)
  assert.equal(f.runtime.getSnapshot().orderAssociations.status, 'ready')
})

test('a later order request replaces pending identity without cross-order leakage', async (t) => {
  const f = await fixture(t)
  await f.runtime.createOrder({
    customerId: 'historical-A',
    reportedProblem: 'Second',
    intakeCondition: null,
    accessories: null,
    priority: 'normal',
    brand: null,
    model: null,
  })
  const second = f.runtime
    .getSnapshot()
    .orders.find((o) => o.reported_problem === 'Second').order_id
  const original = f.runtime.repositories.orderAssociations.bind(f.runtime.repositories)
  let release, entered
  const gate = new Promise((r) => {
      release = r
    }),
    started = new Promise((r) => {
      entered = r
    })
  t.mock.method(f.runtime.repositories, 'orderAssociations', async (...args) => {
    const result = await original(...args)
    if (args[1] === f.order.order_id) {
      entered()
      await gate
    }
    return result
  })
  const first = f.runtime.loadOrderAssociations(f.order.order_id)
  await started
  await f.runtime.loadOrderAssociations(second)
  assert.equal(f.runtime.getSnapshot().orderAssociations.orderId, second)
  release()
  await first
  assert.equal(f.runtime.getSnapshot().orderAssociations.orderId, second)
  assert.deepEqual(f.runtime.getSnapshot().orderAssociations.bicycle, { status: 'none' })
})

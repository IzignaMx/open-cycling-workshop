import test from 'node:test'
import assert from 'node:assert/strict'
import { setup, login, api, response } from './runtime-fixture.mjs'

async function fixture(t, server) {
  const f = setup(t, server ? { server } : {})
  await login(f.runtime)
  f.env.online = false
  await f.runtime.offline()
  await f.runtime.createOrder({
    customerId: 'historical-A',
    reportedProblem: 'History test',
    intakeCondition: null,
    accessories: null,
    priority: 'normal',
    brand: null,
    model: null,
  })
  const order = f.runtime.getSnapshot().orders[0]
  await f.runtime.transition(order.order_id, 'start_diagnosis')
  return { ...f, order }
}

test('history annotates actual local operations without persisting provenance, surviving offline reload', async (t) => {
  const f = await fixture(t)
  const original = await f.database.operationEvents.toArray()
  const local = original.find((row) => row.kind === 'local').details
  assert.deepEqual(f.runtime.getSnapshot().events, [{ ...local, recordSource: 'local' }])
  f.runtime.dispose()
  const reloaded = setup(t, { name: f.name, storage: f.storage, online: false })
  await reloaded.runtime.start()
  await reloaded.runtime.timeline(f.order.order_id)
  assert.deepEqual(reloaded.runtime.getSnapshot().events, [{ ...local, recordSource: 'local' }])
  assert.deepEqual(await reloaded.database.operationEvents.toArray(), original)
  assert.equal(reloaded.server.calls.length, 0)
  assert.match(reloaded.runtime.getSnapshot().timelineMessage, /Sin conexión/)
})

for (const state of ['applied', 'rejected', 'held_dependency']) {
  test(`history is local record provenance rather than acceptance or pending status: ${state}`, async (t) => {
    const f = await fixture(t)
    const local = (await f.database.operationEvents.toArray()).find((row) => row.kind === 'local')
    await f.database.operationDelivery.update(local.mutationId, {
      state,
      dispatchable: 0,
      unresolved: state === 'applied' ? 0 : 1,
    })
    await f.runtime.timeline(f.order.order_id)
    assert.equal(f.runtime.getSnapshot().events[0].recordSource, 'local')
    assert.equal(f.runtime.getSnapshot().events[0].actor_id, 'A')
    assert.equal(f.runtime.getSnapshot().events[0].occurred_at, local.details.occurred_at)
  })
}

test('history preserves local-wins ID collisions, distinct duplicate-looking IDs, original lexical order and source immutability', async (t) => {
  const base = api()
  let remote = []
  const server = {
    calls: base.calls,
    fetch: async (url, init) =>
      new URL(url).pathname.endsWith('/events') ? response(url, remote) : base.fetch(url, init),
  }
  const f = await fixture(t, server)
  const local = f.runtime.getSnapshot().events[0]
  const wire = { ...local }
  delete wire.organization_id
  delete wire.recordSource
  remote = [
    { ...wire, actor_id: 'server-collision', occurred_at: '2026-01-01T00:00:00Z' },
    {
      ...wire,
      event_id: 'remote-duplicate',
      actor_id: 'B',
      occurred_at: '2026-10-14T05:00:00-06:00',
    },
  ]
  const original = await f.database.operationEvents.toArray()
  f.env.online = true
  await f.runtime.timeline(f.order.order_id)
  const events = f.runtime.getSnapshot().events
  assert.equal(events.length, 2)
  assert.deepEqual(
    events.map((row) => [row.event_id, row.recordSource, row.actor_id]),
    [
      ['remote-duplicate', 'server', 'B'],
      [local.event_id, 'local', 'A'],
    ],
  )
  assert.deepEqual(await f.database.operationEvents.toArray(), original)
  assert.equal(remote[0].actor_id, 'server-collision')
  assert.equal(remote[1].recordSource, undefined)
})

test('history malformed local dates do not crash sort or trust a persisted source claim', async (t) => {
  const f = await fixture(t)
  const original = (await f.database.operationEvents.toArray()).find((row) => row.kind === 'local')
  await f.runtime.transition(f.order.order_id, 'authorize')
  const read = f.runtime.repositories.localTimeline.bind(f.runtime.repositories)
  f.runtime.repositories.localTimeline = async (...args) => {
    const result = await read(...args)
    return {
      ...result,
      events: result.events.map((row) =>
        row.event_id === original.details.event_id
          ? { ...row, occurred_at: null, actor_id: {}, recordSource: 'server' }
          : row,
      ),
    }
  }
  await f.runtime.timeline(f.order.order_id)
  assert.equal(f.runtime.getSnapshot().events.length, 2)
  assert.equal(f.runtime.getSnapshot().events[0].occurred_at, null)
  assert.equal(f.runtime.getSnapshot().events[0].recordSource, 'local')
  assert.deepEqual(f.runtime.getSnapshot().events[0].actor_id, {})
})

test('history cannot read an unauthorized order or publish delayed local events after replacement', async (t) => {
  const f = await fixture(t)
  let reads = 0
  const original = f.runtime.repositories.localTimeline.bind(f.runtime.repositories)
  f.runtime.repositories.localTimeline = async (...args) => {
    reads++
    return original(...args)
  }
  await f.runtime.timeline('not-in-authorized-working-set')
  assert.equal(reads, 0)
  let release, entered
  const gate = new Promise((resolve) => {
    release = resolve
  })
  const reached = new Promise((resolve) => {
    entered = resolve
  })
  f.runtime.repositories.localTimeline = async (...args) => {
    const result = await original(...args)
    entered()
    await gate
    return result
  }
  const pending = f.runtime.timeline(f.order.order_id)
  await reached
  f.env.online = true
  await login(f.runtime, 'B')
  release()
  await pending
  assert.deepEqual(f.runtime.getSnapshot().events, [])
})

test('history keeps bounded partial and remote-unavailable notices without changing provenance', async (t) => {
  const base = api()
  let unavailable = false
  const server = {
    calls: base.calls,
    fetch: async (url, init) => {
      if (!new URL(url).pathname.endsWith('/events')) return base.fetch(url, init)
      if (unavailable) throw new Error('Synthetic remote failure')
      return response(url, [])
    },
  }
  const f = await fixture(t, server)
  const read = f.runtime.repositories.localTimeline.bind(f.runtime.repositories)
  f.runtime.repositories.localTimeline = async (...args) => ({
    ...(await read(...args)),
    partial: true,
  })
  f.env.online = true
  await f.runtime.timeline(f.order.order_id)
  assert.equal(
    f.runtime.getSnapshot().timelineMessage,
    'Historial del servidor y página local parcial.',
  )
  assert.equal(f.runtime.getSnapshot().events[0].recordSource, 'local')
  unavailable = true
  await f.runtime.timeline(f.order.order_id)
  assert.match(f.runtime.getSnapshot().timelineMessage, /Se muestra solo el historial local/)
  assert.equal(f.runtime.getSnapshot().events[0].recordSource, 'local')
})

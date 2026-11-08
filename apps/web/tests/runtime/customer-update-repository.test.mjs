import test from 'node:test'
import assert from 'node:assert/strict'
import { setup, login, api, response } from './runtime-fixture.mjs'

async function ready(t) {
  const f = setup(t)
  f.runtime.scheduleSync = () => {}
  await login(f.runtime)
  f.env.online = false
  return f
}
const edit = (extra = {}) => ({
  customerId: 'historical-A',
  baseVersion: 1,
  displayName: 'Edited',
  email: 'new@example.test',
  phone: '123',
  ...extra,
})

test('repository updates admitted existing customer offline through durable journal', async (t) => {
  const f = await ready(t)
  const source = f.runtime.requireActive()
  assert.equal(typeof f.runtime.repositories.updateCustomer, 'function')
  const before = await f.runtime.repositories.editableCustomer(source, 'historical-A')
  const outcome = await f.runtime.repositories.updateCustomer(source, edit())
  assert.equal(outcome.status, 'committed')
  assert.equal(outcome.entity.created_at, before.created_at)
  assert.equal(outcome.entity.version, 2)
  const journal = await f.database.operationJournal.toArray()
  assert.equal(journal.length, 1)
  assert.equal(journal[0].envelope.operation, 'update')
  assert.equal(journal[0].envelope.base_version, 1)
  assert.equal(journal[0].entityId, 'historical-A')
  assert.equal(
    (await f.runtime.repositories.editableCustomer(source, 'historical-A')).display_name,
    'Edited',
  )
  const delivery = await f.database.operationDelivery.get(journal[0].mutationId)
  assert.equal(delivery.state, 'pending')
})

for (const [label, input, reason] of [
  ['stale base', edit({ baseVersion: 2 }), 'changed'],
  ['missing customer', edit({ customerId: 'not-in-scope' }), 'unavailable'],
  ['blank name', edit({ displayName: '\u0085' }), 'validation'],
  ['long name', edit({ displayName: 'x'.repeat(201) }), 'validation'],
  ['invalid email', edit({ email: 'x@localhost' }), 'validation'],
  ['long phone', edit({ phone: '1'.repeat(65) }), 'validation'],
]) {
  test(`repository refuses ${label} without durable side effects`, async (t) => {
    const f = await ready(t)
    const source = f.runtime.requireActive()
    const before = await f.runtime.repositories.editableCustomer(source, 'historical-A')
    const result = await f.runtime.repositories.updateCustomer(source, input)
    assert.equal(result.status, 'not_saved')
    assert.equal(result.reason, reason)
    assert.equal(await f.database.operationJournal.count(), 0)
    assert.deepEqual(await f.runtime.repositories.editableCustomer(source, 'historical-A'), before)
  })
}

test('simultaneous submissions with the same base append only once; repeated stale submit is refused', async (t) => {
  const f = await ready(t)
  const source = f.runtime.requireActive()
  const results = await Promise.allSettled([
    f.runtime.repositories.updateCustomer(source, edit({ displayName: 'First' })),
    f.runtime.repositories.updateCustomer(source, edit({ displayName: 'Second' })),
  ])
  assert.equal(
    results.filter((r) => r.status === 'fulfilled' && r.value.status === 'committed').length,
    1,
  )
  assert.equal(
    results.filter((r) => r.status === 'rejected' || r.value.status === 'not_saved').length,
    1,
  )
  assert.equal(await f.database.operationJournal.count(), 1)
  assert.deepEqual(await f.runtime.repositories.updateCustomer(source, edit()), {
    status: 'not_saved',
    reason: 'changed',
  })
  assert.equal(await f.database.operationJournal.count(), 1)
})

test('offline create then edits retain ordered immutable dependency chain and contact clearing', async (t) => {
  const f = await ready(t)
  const source = f.runtime.requireActive()
  const created = await f.runtime.repositories.createCustomer(source, { displayName: 'Created' })
  const customerId = created.entity.customer_id
  const first = await f.runtime.repositories.updateCustomer(source, edit({ customerId }))
  const second = await f.runtime.repositories.updateCustomer(
    source,
    edit({ customerId, baseVersion: 2, email: '', phone: '' }),
  )
  assert.equal(first.entity.version, 2)
  assert.equal(second.entity.version, 3)
  assert.equal(second.entity.email, null)
  assert.equal(second.entity.phone, null)
  const rows = (await f.database.operationJournal.toArray()).sort(
    (a, b) => a.localSequence - b.localSequence,
  )
  assert.equal(rows.length, 3)
  assert.deepEqual(rows[1].dependsOn, [rows[0].mutationId])
  assert.deepEqual(rows[2].dependsOn, [rows[1].mutationId])
  assert.equal(rows[0].optimistic.display_name, 'Created')
  assert.equal(rows[1].optimistic.email, 'new@example.test')
})

test('repository freezes mutable submitted values before asynchronous lookup', async (t) => {
  const f = await ready(t)
  const source = f.runtime.requireActive()
  const input = edit()
  const pending = f.runtime.repositories.updateCustomer(source, input)
  input.displayName = 'Late private mutation'
  input.customerId = 'other'
  const result = await pending
  assert.equal(result.status, 'committed')
  assert.equal(result.entity.display_name, 'Edited')
  assert.equal(result.entity.customer_id, 'historical-A')
})

test('stale scope after asynchronous read cannot append an update', async (t) => {
  const f = await ready(t)
  const source = f.runtime.requireActive()
  const original = f.runtime.repositories.editableCustomer.bind(f.runtime.repositories)
  f.runtime.repositories.editableCustomer = async (...args) => {
    const result = await original(...args)
    await f.runtime.logout()
    return result
  }
  await assert.rejects(() => f.runtime.repositories.updateCustomer(source, edit()))
  assert.equal(await f.database.operationJournal.count(), 0)
  await assert.rejects(() => original(source, 'historical-A'))
})

test('a customer retained by a different account cannot be read or edited', async (t) => {
  const f = await ready(t)
  const first = f.runtime.requireActive()
  const created = await f.runtime.repositories.createCustomer(first, {
    displayName: 'Private owner A',
  })
  await f.runtime.logout()
  f.env.online = true
  await login(f.runtime, 'B')
  const second = f.runtime.requireActive()
  assert.equal(
    await f.runtime.repositories.editableCustomer(second, created.entity.customer_id),
    null,
  )
  assert.deepEqual(
    await f.runtime.repositories.updateCustomer(
      second,
      edit({ customerId: created.entity.customer_id }),
    ),
    { status: 'not_saved', reason: 'unavailable' },
  )
  assert.equal(await f.database.operationJournal.count(), 1)
})

test('committed edit survives offline controller restart without duplicate mutation', async (t) => {
  const f = await ready(t)
  await f.runtime.repositories.updateCustomer(f.runtime.requireActive(), edit())
  const before = await f.database.operationJournal.toArray()
  f.runtime.dispose()
  const second = setup(t, { name: f.name, storage: f.storage, online: false })
  second.runtime.scheduleSync = () => {}
  await second.runtime.start()
  assert.equal(second.runtime.getSnapshot().phase, 'ready')
  assert.equal(
    (
      await second.runtime.repositories.editableCustomer(
        second.runtime.requireActive(),
        'historical-A',
      )
    ).display_name,
    'Edited',
  )
  assert.deepEqual(await second.database.operationJournal.toArray(), before)
})

test('customers.read without write capability cannot append an edit', async (t) => {
  const server = api(),
    fetch = server.fetch
  server.fetch = async (url, init) => {
    const raw = await fetch(url, init),
      body = await raw.json(),
      value = body.context ?? body
    if (Array.isArray(value.capabilities))
      value.capabilities = value.capabilities.filter((c) => c !== 'customers.write')
    return response(url, body)
  }
  const f = setup(t, { server })
  f.runtime.scheduleSync = () => {}
  await login(f.runtime)
  const source = f.runtime.requireActive()
  assert.equal(
    (await f.runtime.repositories.editableCustomer(source, 'historical-A')).display_name,
    'Private A',
  )
  const results = await Promise.allSettled([f.runtime.repositories.updateCustomer(source, edit())])
  assert.ok(results[0].status === 'rejected' || results[0].value.status === 'not_saved')
  assert.equal(await f.database.operationJournal.count(), 0)
})

for (const field of ['displayName', 'email', 'phone']) {
  test(`unrepresentable ${field} is a closed validation refusal with zero writes`, async (t) => {
    const f = await ready(t)
    for (const value of ['\0', '\ud800', '\udfff']) {
      const result = await f.runtime.repositories.updateCustomer(
        f.runtime.requireActive(),
        edit({
          [field]: field === 'email' ? `a${value}@b.test` : `a${value}`,
        }),
      )
      assert.deepEqual(result, {
        status: 'not_saved',
        reason: 'validation',
        code: 'customer_text_invalid',
      })
    }
    assert.equal(await f.database.operationJournal.count(), 0)
  })
}

test('customer edit preserves valid astral Unicode without truncation', async (t) => {
  const f = await ready(t)
  const result = await f.runtime.repositories.updateCustomer(
    f.runtime.requireActive(),
    edit({ displayName: '😀'.repeat(200), phone: '🚲' }),
  )
  assert.equal(result.status, 'committed')
  assert.equal(result.entity.display_name, '😀'.repeat(200))
  assert.equal(result.entity.phone, '🚲')
})

for (const state of ['rejected', 'held_dependency', 'held_recovery']) {
  test(`known ${state} customer work refuses editing without hiding its retained issue`, async (t) => {
    const f = await ready(t)
    const source = f.runtime.requireActive()
    await f.runtime.repositories.updateCustomer(source, edit())
    const [operation] = await f.database.operationJournal.toArray()
    await f.database.operationDelivery.update(operation.mutationId, {
      state,
      blocked: 1,
      dispatchable: 0,
      unresolved: 1,
    })
    assert.equal(await f.runtime.repositories.editableCustomer(source, 'historical-A'), null)
    assert.deepEqual(await f.runtime.repositories.updateCustomer(source, edit()), {
      status: 'not_saved',
      reason: 'unavailable',
    })
    assert.equal(await f.database.operationJournal.count(), 1)
    const issues = await f.runtime.repositories.issues(source)
    assert.equal(issues.hasIssues, true)
    assert.equal(issues.items[0].operation.mutationId, operation.mutationId)
  })
}

test('conflict discovered after edit read cannot overwrite or dispatch through blocked history', async (t) => {
  const f = await ready(t)
  const source = f.runtime.requireActive()
  await f.runtime.repositories.updateCustomer(source, edit())
  const [operation] = await f.database.operationJournal.toArray()
  const original = f.runtime.repositories.editableCustomer.bind(f.runtime.repositories)
  f.runtime.repositories.editableCustomer = async (...args) => {
    const row = await original(...args)
    await f.database.operationDelivery.update(operation.mutationId, {
      state: 'rejected',
      blocked: 1,
      dispatchable: 0,
      unresolved: 1,
    })
    return row
  }
  const [result] = await Promise.allSettled([
    f.runtime.repositories.updateCustomer(
      source,
      edit({ baseVersion: 2, displayName: 'Late edit' }),
    ),
  ])
  assert.ok(result.status === 'rejected' || result.value.status === 'not_saved')
  assert.equal(await f.database.operationJournal.count(), 1)
  assert.deepEqual((await f.runtime.kernel.listDispatchable(source.ticket, 10)).operations, [])
  const projection = await f.runtime.kernel.readEntity(source.ticket, 'customer', 'historical-A')
  assert.equal(projection.blocked, true)
  assert.equal(projection.confirmed.display_name, 'Private A')
  assert.equal(projection.optimistic, undefined)
})

test('equal confirmed and optimistic versions cannot bypass a newly blocked customer at commit', async (t) => {
  const f = await ready(t)
  const source = f.runtime.requireActive()
  await f.runtime.repositories.updateCustomer(source, edit())
  const [operation] = await f.database.operationJournal.toArray()
  const key = [source.ticket.partitionId, 'customer', 'historical-A']
  const cached = await f.database.cacheRecords.get(key)
  await f.database.cacheRecords.put({
    ...cached,
    version: 2,
    payload: { ...cached.payload, version: 2, display_name: 'Remote version two' },
  })
  const original = f.runtime.repositories.editableCustomer.bind(f.runtime.repositories)
  f.runtime.repositories.editableCustomer = async (...args) => {
    const row = await original(...args)
    assert.equal(row.version, 2)
    await f.database.operationDelivery.update(operation.mutationId, {
      state: 'rejected',
      blocked: 1,
      dispatchable: 0,
      unresolved: 1,
    })
    return row
  }
  const [result] = await Promise.allSettled([
    f.runtime.repositories.updateCustomer(
      source,
      edit({ baseVersion: 2, displayName: 'Must not append' }),
    ),
  ])
  assert.ok(result.status === 'rejected' || result.value.status === 'not_saved')
  assert.equal(await f.database.operationJournal.count(), 1)
  assert.deepEqual((await f.runtime.kernel.listDispatchable(source.ticket, 10)).operations, [])
  assert.equal((await f.database.cacheRecords.get(key)).payload.display_name, 'Remote version two')
  assert.equal(
    await f.runtime.kernel.commitLocalCommand(source.ticket, {
      envelope: operation.envelope,
      optimistic: operation.optimistic,
      dependsOn: operation.dependsOn,
      localEvents: [],
    }),
    operation.mutationId,
    'exact-ID replay remains an immutable no-op',
  )
  assert.equal(await f.database.operationJournal.count(), 1)
})

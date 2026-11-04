import test from 'node:test'
import assert from 'node:assert/strict'
import { setup, login, until } from './runtime-fixture.mjs'

// Actual-controller/fake-IDB restart, not browser reload/power-loss proof.
// Retains the existing synthetic sessionStorage fixture and database name. Does
// not persist a speculative draft, add production code or replay any mutation.
for (const online of [false, true]) {
  test(`unsubmitted capture survives same-binding controller restart online=${online}`, async (t) => {
    const first = setup(t)
    first.runtime.scheduleSync = () => {}
    await login(first.runtime)
    // A real existing persisted command proves the reopened database is not empty.
    assert.deepEqual(await first.runtime.createCustomer({ displayName: 'Previously saved' }), {
      status: 'saved',
    })
    const capture = first.runtime.getSnapshot().capture
    const customer = { displayName: 'Unsubmitted draft', email: 'draft@example.test', phone: '555' }
    const order = {
      customerId: 'historical-A',
      priority: 'high',
      reportedProblem: 'Unsubmitted brake',
      intakeCondition: 'Wet',
      accessories: 'Lamp',
      withBicycle: false,
      brand: 'Hidden brand',
      model: 'Hidden model',
    }
    for (const [field, value] of Object.entries(customer))
      first.runtime.editCaptureCustomer(capture.viewToken, field, value)
    for (const [field, value] of Object.entries(order))
      first.runtime.editCaptureOrder(capture.viewToken, field, value)
    await until(
      () =>
        ['customer', 'order'].every((ch) =>
          first.runtime.getSnapshot().capture[ch].recoveryMessage?.startsWith('Borrador guardado'),
        ),
      'draft acknowledgement',
    )
    const session = first.runtime.sessionStore.getSnapshot()
    const before = await first.database.operationJournal.toArray()
    assert.equal(before.length, 1)
    assert.equal(first.runtime.hasUnsentCaptures(), true)
    first.runtime.dispose()
    const second = setup(t, { name: first.name, storage: first.storage, online })
    second.runtime.scheduleSync = () => {}
    await second.runtime.start()
    await until(
      () => second.runtime.getSnapshot().phase === 'ready',
      'same retained binding did not regain verified READY',
    )
    assert.equal(second.runtime.sessionStore.getSnapshot().bindingId, session.bindingId)
    assert.deepEqual(
      await second.database.operationJournal.toArray(),
      before,
      'unsent restore must not generate/replay mutations',
    )
    assert.ok(
      second.runtime.getSnapshot().customers.some((row) => row.display_name === 'Previously saved'),
    )
    const restored = second.runtime.getSnapshot().capture
    assert.deepEqual(
      { customer: restored.customer.draft, order: restored.order.draft },
      { customer, order },
      'only unsubmitted input should be recoverable in the same admitted scope',
    )
  })
}

for (const kind of ['customer', 'order']) {
  for (const status of ['unknown', 'pending']) {
    test(`${kind} ${status} admission survives same-binding controller restart`, async (t) => {
      const first = setup(t)
      first.runtime.scheduleSync = () => {}
      await login(first.runtime)
      const method = kind === 'customer' ? 'createCustomer' : 'createOrder'
      const submit = kind === 'customer' ? 'submitCaptureCustomer' : 'submitCaptureOrder'
      let calls = 0,
        release
      const waiting = new Promise((resolve) => {
        release = resolve
      })
      first.runtime.repositories[method] = async () => {
        calls++
        if (status === 'pending') await waiting
        throw new Error('synthetic-prewrite-unknown')
      }
      function fill(runtime) {
        const view = runtime.getSnapshot().capture.viewToken
        runtime.editCaptureCustomer(view, 'displayName', 'Uncertain customer')
        runtime.editCaptureOrder(view, 'customerId', 'historical-A')
        runtime.editCaptureOrder(view, 'reportedProblem', 'Uncertain problem')
        return view
      }
      const completion = first.runtime[submit](fill(first.runtime))
      if (status === 'unknown') await completion
      await until(() => calls === 1, 'protected repository dispatch')
      assert.equal(calls, 1)
      const before = await first.database.operationJournal.toArray()
      first.runtime.dispose()
      try {
        const second = setup(t, { name: first.name, storage: first.storage, online: false })
        second.runtime.scheduleSync = () => {}
        await second.runtime.start()
        assert.equal(second.runtime.getSnapshot().phase, 'ready')
        second.runtime.repositories[method] = async () => {
          calls++
          throw new Error('synthetic-prewrite-unknown')
        }
        await second.runtime[submit](fill(second.runtime))
        assert.deepEqual(await second.database.operationJournal.toArray(), before)
        assert.equal(
          calls,
          1,
          'retained binding must not silently reopen unresolved capture admission',
        )
      } finally {
        release()
        await completion
      }
    })
  }
}

test('cancellation masks capture before the first synchronous recovery notification', async (t) => {
  const f = setup(t)
  f.runtime.scheduleSync = () => {}
  await login(f.runtime)
  const view = f.runtime.getSnapshot().capture.viewToken
  f.runtime.editCaptureCustomer(view, 'displayName', 'private-cancel-value')
  let first = true,
    observed
  const off = f.runtime.subscribe(() => {
    if (first) {
      first = false
      observed = f.runtime.getSnapshot().capture
      f.runtime.editCaptureCustomer(view, 'phone', 'stale-event')
    }
  })
  const pending = f.runtime.reconnect()
  off()
  await pending
  assert.equal(observed, null, 'first cancellation notification cannot expose old capture')
  assert.equal(f.runtime.getSnapshot().capture.customer.draft.phone, '')
})

test('failed logout purge exposes a content-free warning in actual locked App branch', async (t) => {
  const { appHarness } = await import('./capture-component-host.mjs')
  const f = setup(t)
  f.runtime.scheduleSync = () => {}
  await login(f.runtime)
  f.runtime.editCaptureCustomer(
    f.runtime.getSnapshot().capture.viewToken,
    'displayName',
    'private-cleanup-value',
  )
  await until(() =>
    f.runtime.getSnapshot().capture.customer.recoveryMessage?.startsWith('Borrador guardado'),
  )
  const remove = f.database.captureDraftContents.bulkDelete.bind(f.database.captureDraftContents)
  f.database.captureDraftContents.bulkDelete = async () => {
    throw new Error('synthetic deletion failure')
  }
  await f.runtime.logout()
  await new Promise((resolve) => setTimeout(resolve, 20))
  const tree = appHarness(f.runtime).render()
  const rendered = JSON.stringify(tree)
  assert.match(rendered, /No se pudo confirmar la eliminación de los borradores locales/)
  assert.equal(rendered.includes('private-cleanup-value'), false)
  assert.equal(f.runtime.getSnapshot().capture, null)
  f.database.captureDraftContents.bulkDelete = remove
})

test('voluntary same-workshop discard cannot restore the discarded input after reload', async (t) => {
  const { api, response } = await import('./runtime-fixture.mjs')
  const server = api(),
    original = server.fetch
  server.fetch = async (url, init) => {
    if (new URL(url).pathname.endsWith('/locations'))
      return response(url, {
        items: [{ location_id: 'loc', organization_id: 'org', name: 'Selected workshop' }],
        next_cursor: null,
      })
    const body = await (await original(url, init)).json()
    if (Object.hasOwn(body, 'user_id')) {
      body.location_id = null
      body.capabilities.push('locations.read')
    }
    const context = body.context ?? body
    if (Object.hasOwn(context, 'account_location_id')) {
      context.account_location_id = null
      context.capabilities.push('locations.read')
    }
    return response(url, body)
  }
  const first = setup(t, { server })
  first.runtime.scheduleSync = () => {}
  await first.runtime.login({ organization_id: 'org', username: 'A', password: 'synthetic' })
  await until(() => first.runtime.getSnapshot().locations.length > 0, 'selector loaded')
  await first.runtime.selectWorkshop('loc')
  await until(() => first.runtime.getSnapshot().capture !== null, 'selected ready')
  first.runtime.editCaptureCustomer(
    first.runtime.getSnapshot().capture.viewToken,
    'displayName',
    'discard-this-private-input',
  )
  await until(() =>
    first.runtime.getSnapshot().capture.customer.recoveryMessage?.startsWith('Borrador guardado'),
  )
  await first.runtime.changeWorkshop()
  await first.runtime.selectWorkshop('loc')
  assert.equal(first.runtime.getSnapshot().capture.customer.draft.displayName, '')
  first.runtime.dispose()
  const second = setup(t, { name: first.name, storage: first.storage, online: false })
  second.runtime.scheduleSync = () => {}
  await second.runtime.start()
  assert.equal(second.runtime.getSnapshot().capture.customer.draft.displayName, '')
  assert.equal(await second.database.captureDraftContents.count(), 0)
})

for (const [field, value, message] of [
  ['displayName', 'a'.repeat(201), 'El nombre no puede superar 200 caracteres'],
  ['email', 'a'.repeat(309) + '@example.com', 'El correo no puede superar 320 caracteres'],
  ['phone', '1'.repeat(65), 'El teléfono no puede superar 64 caracteres'],
  ['email', 'İ'.repeat(308) + '@example.com', 'El correo no puede superar 320 caracteres'],
]) {
  test(`invalid customer ${field} (${value.length}) remains recoverable then saves corrected intent once`, async (t) => {
    const first = setup(t)
    first.runtime.scheduleSync = () => {}
    await login(first.runtime)
    const view = first.runtime.getSnapshot().capture.viewToken
    first.runtime.editCaptureCustomer(view, 'displayName', 'Synthetic draft')
    first.runtime.editCaptureCustomer(view, field, value)
    const draft = { ...first.runtime.getSnapshot().capture.customer.draft }
    await first.runtime.submitCaptureCustomer(view)
    const rejected = first.runtime.getSnapshot().capture.customer
    assert.equal(await first.database.operationJournal.count(), 0)
    assert.deepEqual(rejected.draft, draft)
    assert.equal(rejected.dirty, true)
    assert.equal(rejected.blocked, false)
    assert.equal(rejected.busy, false)
    assert.equal(rejected.message, message)
    await until(
      () =>
        first.runtime
          .getSnapshot()
          .capture.customer.recoveryMessage?.startsWith('Borrador guardado'),
      'invalid draft persisted after protection release',
    )
    first.runtime.dispose()
    const second = setup(t, { name: first.name, storage: first.storage, online: false })
    second.runtime.scheduleSync = () => {}
    await second.runtime.start()
    await until(
      () => second.runtime.getSnapshot().phase === 'ready',
      'ready after invalid draft reload',
    )
    const restored = second.runtime.getSnapshot().capture
    assert.deepEqual(restored.customer.draft, draft)
    assert.equal(restored.customer.blocked, false)
    assert.equal(await second.database.operationJournal.count(), 0)
    const corrected = { displayName: 'Corrected synthetic', email: 'ok@example.test', phone: '123' }
    for (const [key, input] of Object.entries(corrected))
      second.runtime.editCaptureCustomer(restored.viewToken, key, input)
    await second.runtime.submitCaptureCustomer(restored.viewToken)
    const journal = await second.database.operationJournal.toArray()
    assert.equal(journal.length, 1)
    assert.equal(second.runtime.getSnapshot().capture.customer.dirty, false)
    assert.equal(second.runtime.getSnapshot().capture.customer.blocked, false)
  })
}

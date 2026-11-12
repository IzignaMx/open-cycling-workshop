import test from 'node:test'
import assert from 'node:assert/strict'
import { setup, login, until } from './runtime-fixture.mjs'
test('actual retained runtime preserves unsupported draft, explains version boundary and refuses submission', async (t) => {
  const first = setup(t)
  first.runtime.scheduleSync = () => {}
  await login(first.runtime)
  const capture = first.runtime.getSnapshot().capture
  first.runtime.editCaptureOrder(capture.viewToken, 'customerId', 'historical-A')
  first.runtime.editCaptureOrder(
    capture.viewToken,
    'reportedProblem',
    'Private unsupported symptom',
  )
  await until(
    () =>
      first.runtime.getSnapshot().capture.order.recoveryMessage?.startsWith('Borrador guardado'),
    'draft persisted',
  )
  const row = (await first.database.captureDraftContents.toArray()).find(
    (x) => x.channel === 'order',
  )
  const future = { ...row, format: 2, draft: { ...row.draft, existingBicycleId: 'future-id' } }
  await first.database.captureDraftContents.put(future)
  const journal = await first.database.operationJournal.toArray()
  first.runtime.dispose()
  const second = setup(t, { name: first.name, storage: first.storage, online: false })
  await second.runtime.start()
  const restored = second.runtime.getSnapshot().capture
  assert.equal(restored.order.blocked, true)
  assert.equal(
    second.runtime.hasUnsentCaptures(),
    true,
    'opaque retained draft still requires explicit leave confirmation',
  )
  assert.match(restored.order.recoveryMessage, /versión compatible/)
  assert.equal(restored.order.draft.reportedProblem, '')
  assert.equal(JSON.stringify(second.runtime.getSnapshot()).includes('future-id'), false)
  await second.runtime.submitCaptureOrder(restored.viewToken)
  assert.deepEqual(
    await second.database.captureDraftContents.get([row.checkpointId, 'order']),
    future,
  )
  assert.deepEqual(await second.database.operationJournal.toArray(), journal)
  assert.equal(second.server.calls.length, 0)
  const { appHarness } = await import('./capture-component-host.mjs')
  const previousWindow = globalThis.window,
    previousDocument = globalThis.document
  let confirmed = false,
    prompts = 0
  globalThis.window = {
    confirm: () => {
      prompts++
      return confirmed
    },
  }
  globalThis.document = { querySelector: () => null }
  t.after(() => {
    globalThis.window = previousWindow
    globalThis.document = previousDocument
  })
  const app = appHarness(second.runtime, { layoutEffects: true })
  app.render()
  assert.equal(app.logoutGuard()(), false)
  assert.equal(prompts, 1)
  assert.deepEqual(
    await second.database.captureDraftContents.get([row.checkpointId, 'order']),
    future,
  )
  assert.equal(second.runtime.hasUnsentCaptures(), true)
  confirmed = true
  assert.equal(app.logoutGuard()(), true)
  assert.equal(prompts, 2)
  await second.runtime.logout()
  await until(() => second.runtime.getSnapshot().phase === 'locked', 'logout completed')
  for (let i = 0; i < 100 && (await second.database.captureDraftContents.count()) !== 0; i++)
    await new Promise((resolve) => setTimeout(resolve, 10))
  assert.equal(await second.database.captureDraftContents.count(), 0)
})

for (const stale of [false, true])
  test(`unsupported draft explicit workshop discard respects generation (stale=${stale})`, async (t) => {
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
    await until(() => first.runtime.getSnapshot().locations.length > 0)
    await first.runtime.selectWorkshop('loc')
    await until(() => first.runtime.getSnapshot().capture !== null)
    first.runtime.editCaptureCustomer(
      first.runtime.getSnapshot().capture.viewToken,
      'displayName',
      'Private future customer',
    )
    await until(() =>
      first.runtime.getSnapshot().capture.customer.recoveryMessage?.startsWith('Borrador guardado'),
    )
    const row = (await first.database.captureDraftContents.toArray()).find(
      (x) => x.channel === 'customer',
    )
    const future = { ...row, format: 2, draft: { future: 'opaque' } }
    await first.database.captureDraftContents.put(future)
    first.runtime.dispose()
    const second = setup(t, { name: first.name, storage: first.storage, server, online: false })
    second.runtime.scheduleSync = () => {}
    await second.runtime.start()
    assert.equal(second.runtime.hasUnsentCaptures(), true)
    const current = { ...future, generation: stale ? crypto.randomUUID() : future.generation }
    if (stale) {
      await second.database.captureCheckpoints.update(row.checkpointId, {
        generation: current.generation,
      })
      await second.database.captureDraftContents.put(current)
    }
    await second.runtime.changeWorkshop()
    if (stale) {
      assert.deepEqual(
        await second.database.captureDraftContents.get([row.checkpointId, 'customer']),
        current,
      )
      assert.match(second.runtime.getSnapshot().captureRecoveryNotice, /No se pudo confirmar/)
    } else {
      assert.equal(await second.database.captureDraftContents.count(), 0)
      const checkpoint = await second.database.captureCheckpoints.get(row.checkpointId)
      assert.notEqual(checkpoint.generation, row.generation)
      assert.equal(checkpoint.closed, false)
      await second.runtime.selectWorkshop('loc')
      assert.equal(second.runtime.getSnapshot().capture.customer.draft.displayName, '')
      assert.equal(second.runtime.hasUnsentCaptures(), false)
    }
  })

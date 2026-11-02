import test from 'node:test'
import assert from 'node:assert/strict'
import { setup, login, until } from './runtime-fixture.mjs'

// Real controller/kernel/repositories with fake IndexedDB. Injection throws before
// a selected actual table write; no saved outcome or native IDB event is fabricated.
async function ready(t, options) {
  const f = setup(t, options)
  f.runtime.scheduleSync = () => {}
  await login(f.runtime)
  return f
}
const view = (f) => f.runtime.getSnapshot().capture.viewToken
function fill(f, kind = 'customer') {
  if (kind === 'customer') f.runtime.editCaptureCustomer(view(f), 'displayName', 'Private unsent')
  else {
    f.runtime.editCaptureOrder(view(f), 'customerId', 'historical-A')
    f.runtime.editCaptureOrder(view(f), 'priority', 'high')
    f.runtime.editCaptureOrder(view(f), 'reportedProblem', 'Brake')
  }
}
async function savedDraft(f, kind = 'customer') {
  await until(
    () => f.runtime.getSnapshot().capture[kind].recoveryMessage?.startsWith('Borrador guardado'),
    'checkpoint acknowledgement',
  )
}
function countCreates(f, kind = 'customer') {
  const method = kind === 'customer' ? 'createCustomer' : 'createOrder',
    original = f.runtime.repositories[method].bind(f.runtime.repositories)
  let calls = 0
  f.runtime.repositories[method] = async (...args) => {
    calls++
    return original(...args)
  }
  return () => calls
}
async function reopen(t, f, storage = f.storage) {
  f.runtime.dispose()
  const next = setup(t, { name: f.name, storage, online: false })
  next.runtime.scheduleSync = () => {}
  await next.runtime.start()
  assert.equal(next.runtime.getSnapshot().phase, 'ready')
  return next
}
for (const kind of ['customer', 'order']) {
  const submit = kind === 'customer' ? 'submitCaptureCustomer' : 'submitCaptureOrder'
  test(`${kind}: actual autosave quota stops repository dispatch`, async (t) => {
    const f = await ready(t),
      calls = countCreates(f, kind),
      original = f.database.captureDraftContents.put.bind(f.database.captureDraftContents)
    f.database.captureDraftContents.put = async () => {
      throw new DOMException('synthetic quota', 'QuotaExceededError')
    }
    fill(f, kind)
    await f.runtime[submit](view(f))
    assert.equal(calls(), 0)
    assert.equal(await f.database.operationJournal.count(), 0)
    assert.equal(f.runtime.getSnapshot().capture[kind].blocked, true)
    f.database.captureDraftContents.put = original
  })
  test(`${kind}: actual protect write quota stops dispatch and preserves draft`, async (t) => {
    const f = await ready(t),
      calls = countCreates(f, kind)
    fill(f, kind)
    await savedDraft(f, kind)
    const original = f.database.captureCheckpoints.put.bind(f.database.captureCheckpoints)
    f.database.captureCheckpoints.put = async (row, ...args) => {
      if (row[kind].state === 'PROTECTED')
        throw new DOMException('synthetic quota', 'QuotaExceededError')
      return original(row, ...args)
    }
    await f.runtime[submit](view(f))
    assert.equal(calls(), 0)
    assert.equal(await f.database.operationJournal.count(), 0)
    assert.equal((await f.database.captureCheckpoints.toArray())[0][kind].state, 'UNSENT')
    assert.equal(await f.database.captureDraftContents.count(), 1)
    f.database.captureCheckpoints.put = original
  })
  test(`${kind}: committed business command with failed settlement reloads protected, never replays`, async (t) => {
    const f = await ready(t),
      calls = countCreates(f, kind)
    fill(f, kind)
    await savedDraft(f, kind)
    const original = f.database.captureCheckpoints.put.bind(f.database.captureCheckpoints)
    let protectedOnce = false
    f.database.captureCheckpoints.put = async (row, ...args) => {
      if (row[kind].state === 'PROTECTED') protectedOnce = true
      else if (protectedOnce) throw new DOMException('synthetic quota', 'QuotaExceededError')
      return original(row, ...args)
    }
    await f.runtime[submit](view(f))
    assert.equal(calls(), 1)
    assert.ok((await f.database.operationJournal.count()) > 0)
    assert.match(f.runtime.getSnapshot().capture[kind].recoveryMessage, /se guardó localmente/)
    const before = await f.database.operationJournal.toArray()
    f.database.captureCheckpoints.put = original
    const next = await reopen(t, f),
      nextCalls = countCreates(next, kind)
    fill(next, kind)
    await next.runtime[submit](view(next))
    assert.equal(nextCalls(), 0)
    assert.equal(next.runtime.getSnapshot().capture[kind].blocked, true)
    assert.deepEqual(await next.database.operationJournal.toArray(), before)
  })
}
test('positive protect followed by authority mask does not invoke repository or rearm checkpoint', async (t) => {
  const f = await ready(t),
    calls = countCreates(f)
  fill(f)
  await savedDraft(f)
  const original = f.runtime.kernel.checkpointCapture.bind(f.runtime.kernel)
  let reconnect
  f.runtime.kernel.checkpointCapture = async (...args) => {
    const result = await original(...args)
    if (args[1].kind === 'protect' && result.kind === 'ack') reconnect = f.runtime.reconnect()
    return result
  }
  await f.runtime.submitCaptureCustomer(view(f))
  await reconnect
  assert.equal(calls(), 0)
  assert.equal(await f.database.operationJournal.count(), 0)
  assert.equal((await f.database.captureCheckpoints.toArray())[0].customer.state, 'PROTECTED')
  assert.equal(f.runtime.getSnapshot().capture.customer.blocked, true)
})
test('logout purges content and closes checkpoint; disposal alone keeps reloadable content', async (t) => {
  const f = await ready(t)
  fill(f)
  await savedDraft(f)
  const next = await reopen(t, f)
  assert.equal(await next.database.captureDraftContents.count(), 1)
  assert.equal(next.runtime.getSnapshot().capture.customer.draft.displayName, 'Private unsent')
  await next.runtime.logout()
  await new Promise((resolve) => setImmediate(resolve))
  assert.equal(await next.database.captureDraftContents.count(), 0)
  assert.equal((await next.database.captureCheckpoints.toArray())[0].closed, true)
})
test('clean retained order selection remains clean after successful submission and reload', async (t) => {
  const f = await ready(t)
  fill(f, 'order')
  await f.runtime.submitCaptureOrder(view(f))
  assert.ok((await f.database.operationJournal.count()) > 0, 'real order command committed')
  assert.equal(f.runtime.getSnapshot().capture.order.dirty, false)
  const next = await reopen(t, f)
  assert.equal(next.runtime.getSnapshot().capture.order.draft.customerId, 'historical-A')
  assert.equal(next.runtime.getSnapshot().capture.order.draft.priority, 'high')
  assert.equal(next.runtime.getSnapshot().capture.order.draft.reportedProblem, '')
  assert.equal(next.runtime.getSnapshot().capture.order.dirty, false)
})
test('legacy retained session without checkpoint hint stays read-ready but capture fails closed', async (t) => {
  const f = await ready(t)
  f.storage.removeItem('ocwp.capture-checkpoint.v1')
  const next = await reopen(t, f),
    calls = countCreates(next)
  fill(next)
  await next.runtime.submitCaptureCustomer(view(next))
  assert.equal(calls(), 0)
  assert.equal(next.runtime.getSnapshot().capture.customer.blocked, true)
  assert.equal(next.runtime.getSnapshot().customers.length > 0, true)
})
test('pre-submit cloned hint observes shared completion and cannot restore submitted draft', async (t) => {
  const f = await ready(t)
  fill(f)
  await savedDraft(f)
  const clone = f.storage.clone()
  await f.runtime.submitCaptureCustomer(view(f))
  const before = await f.database.operationJournal.toArray()
  assert.equal(before.length, 1)
  const next = await reopen(t, f, clone)
  assert.equal(next.runtime.getSnapshot().capture.customer.draft.displayName, '')
  assert.deepEqual(await next.database.operationJournal.toArray(), before)
  assert.equal(await next.database.captureCheckpoints.count(), 1)
})

test('logout before recovery hydration still purges acknowledged private content', async (t) => {
  const first = setup(t)
  first.runtime.scheduleSync = () => {}
  await login(first.runtime)
  first.runtime.editCaptureCustomer(
    first.runtime.getSnapshot().capture.viewToken,
    'displayName',
    'private-prehydration',
  )
  await until(() =>
    first.runtime.getSnapshot().capture.customer.recoveryMessage?.startsWith('Borrador guardado'),
  )
  assert.equal(await first.database.captureDraftContents.count(), 1)
  first.runtime.dispose()
  const second = setup(t, { name: first.name, storage: first.storage, online: false })
  // The locked newly constructed runtime has never loaded the checkpoint head.
  assert.equal(second.runtime.getSnapshot().phase, 'locked')
  await second.runtime.logout()
  for (let i = 0; i < 100 && (await second.database.captureDraftContents.count()); i++)
    await new Promise(setImmediate)
  assert.equal(await second.database.captureDraftContents.count(), 0)
})

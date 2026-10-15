import 'fake-indexeddb/auto'
import test from 'node:test'
import assert from 'node:assert/strict'
import { WorkshopController } from '../../.tmp-runtime/src/runtime/controller.js'
import { createKernelDatabase } from '../../.tmp-runtime/src/access-kernel/database.js'
const realm = 'https://account.test/api/v1'
const user = {
  user_id: 'A',
  organization_id: 'org',
  location_id: null,
  display_name: 'A',
  capabilities: [],
}
function response(url, value, status = 200) {
  const result = new Response(JSON.stringify(value), {
    status,
    headers: { 'content-type': 'application/json', 'cache-control': 'no-store' },
  })
  Object.defineProperty(result, 'url', { value: url })
  return result
}
function setup(t, handler = async (url) => response(url, user), online = false) {
  const values = new Map(),
    calls = []
  const runtime = new WorkshopController({
    apiRealm: realm,
    storage: {
      getItem: (k) => values.get(k) ?? null,
      setItem: (k, v) => values.set(k, v),
      removeItem: (k) => values.delete(k),
    },
    database: createKernelDatabase('account-' + crypto.randomUUID()),
    fetch: (url, init) => {
      calls.push(url)
      return handler(url, init)
    },
    online: () => online,
    factory: indexedDB,
  })
  runtime.sessionStore.setToken('synthetic-token')
  runtime.sessionStore.setUser(user)
  t.after(() => runtime.dispose())
  return { runtime, calls }
}
test('account-only explicit verification admits empty grants without touching kernel or requiring navigator online', async (t) => {
  const { runtime, calls } = setup(t)
  runtime.kernel.beginVerification = () => {
    throw new Error('must not enter kernel')
  }
  await runtime.verifyAccount()
  assert.equal(runtime.getAccountSnapshot().phase, 'connected')
  assert.deepEqual(runtime.getAccountSnapshot().user, user)
  assert.equal(runtime.getSnapshot().phase, 'locked')
  assert.deepEqual(calls, [realm + '/auth/me'])
  assert.equal(JSON.stringify(runtime.getAccountSnapshot()).includes('synthetic-token'), false)
  assert.equal(runtime.captureAccount().isCurrent(), true)
})
test('selector/no-active offline invalidates account captures and synchronously notifies', async (t) => {
  const { runtime } = setup(t)
  await runtime.verifyAccount()
  const capture = runtime.captureAccount()
  let notified = false
  runtime.subscribeAccount(() => {
    notified = true
  })
  const pending = runtime.offline()
  assert.equal(capture.isCurrent(), false)
  assert.equal(capture.signal.aborted, true)
  assert.equal(runtime.getAccountSnapshot().user, null)
  assert.equal(notified, true)
  await pending
})
test('same-token metadata replacement fences capture; stale 401 cannot clear replacement', async (t) => {
  let resolve
  const { runtime } = setup(
    t,
    (url) =>
      new Promise((r) => {
        resolve = (status) => r(response(url, {}, status))
      }),
  )
  const pending = runtime.verifyAccount()
  runtime.sessionStore.setUser({ ...user, display_name: 'Replacement' })
  resolve(401)
  await pending
  assert.equal(runtime.sessionStore.getSnapshot().user.display_name, 'Replacement')
  assert.notEqual(runtime.getAccountSnapshot().phase, 'connected')
})
test('account-only self command has dedicated one-use handle and stale completion cannot log out replacement', async (t) => {
  const { runtime } = setup(t)
  await runtime.verifyAccount()
  const original = runtime.captureAccount()
  const suspended = await runtime.suspendAccountCommand(original)
  assert.equal(original.isCurrent(), false)
  assert.equal(suspended.isCurrent(), true)
  assert.equal(runtime.getAccountSnapshot().phase, 'suspended')
  runtime.sessionStore.setToken('replacement-token')
  runtime.sessionStore.setUser({ ...user, user_id: 'B' })
  await runtime.completeAccountCommand(suspended, 'success')
  assert.equal(runtime.sessionStore.getSnapshot().token, 'replacement-token')
})
test('uncertain self command remains locked and requires fresh connected verification', async (t) => {
  const { runtime } = setup(t)
  await runtime.verifyAccount()
  const capture = await runtime.suspendAccountCommand(runtime.captureAccount())
  await runtime.completeAccountCommand(capture, 'uncertain')
  assert.equal(capture.isCurrent(), false)
  assert.equal(runtime.getSnapshot().phase, 'held')
  assert.equal(runtime.getAccountSnapshot().phase, 'unverified')
  assert.throws(() => runtime.captureAccount())
  await runtime.verifyAccount()
  assert.equal(runtime.getAccountSnapshot().phase, 'connected')
})

test('fresh empty-grant login and reload do not require an operational kernel', async (t) => {
  const { runtime } = setup(
    t,
    async (url) =>
      response(
        url,
        url.endsWith('/auth/login') ? { access_token: 'new-token', token_type: 'bearer' } : user,
      ),
    true,
  )
  runtime.kernel.beginVerification = () => {
    throw new Error('must not enter kernel')
  }
  await runtime.login({ organization_id: 'org', username: 'A', password: 'synthetic-only' })
  assert.equal(runtime.getAccountSnapshot().phase, 'connected')
  assert.equal(runtime.getSnapshot().phase, 'selector')
  assert.equal(runtime.getSnapshot().context, null)
  assert.equal(runtime.sessionStore.getSnapshot().admission, null)
  await runtime.start()
  assert.equal(runtime.getAccountSnapshot().phase, 'connected')
  assert.equal(runtime.getSnapshot().phase, 'selector')
})

test('dispose synchronously notifies account subscribers and aborts all transient captures', async (t) => {
  const { runtime } = setup(t)
  await runtime.verifyAccount()
  const capture = runtime.captureAccount()
  let phase
  runtime.subscribeAccount(() => {
    phase = runtime.getAccountSnapshot().phase
  })
  runtime.dispose()
  assert.equal(phase, 'unverified')
  assert.equal(capture.signal.aborted, true)
  assert.equal(capture.isCurrent(), false)
  await runtime.verifyAccount()
  assert.throws(() => runtime.captureAccount())
})

test('account verification deadline clears authority and retains physical single-flight until abort-ignoring fetch settles', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  let finish, signal
  const { runtime, calls } = setup(t, (url, init) => {
    signal = init.signal
    return new Promise((resolve) => {
      finish = () => resolve(response(url, user))
    })
  })
  const pending = runtime.verifyAccount()
  t.mock.timers.tick(10000)
  await pending
  assert.equal(signal.aborted, true)
  assert.equal(runtime.getAccountSnapshot().phase, 'unverified')
  await runtime.verifyAccount()
  assert.equal(calls.length, 1)
  finish()
  await new Promise((resolve) => setImmediate(resolve))
  assert.equal(runtime.getAccountSnapshot().phase, 'unverified')
})

test('self command success consumes handle once, clears token and never permits reuse', async (t) => {
  const { runtime } = setup(t)
  await runtime.verifyAccount()
  const handle = await runtime.suspendAccountCommand(runtime.captureAccount())
  await runtime.completeAccountCommand(handle, 'success')
  assert.equal(handle.isCurrent(), false)
  assert.equal(handle.signal.aborted, true)
  assert.equal(runtime.sessionStore.getSnapshot(), null)
  await assert.rejects(runtime.suspendAccountCommand(handle))
})

test('compatibility revoke uses suspended lifecycle and clears only matching401 session', async (t) => {
  const { runtime, calls } = setup(t, async (url) => {
    if (url.endsWith('/auth/logout-all')) {
      assert.equal(runtime.getAccountSnapshot().phase, 'suspended')
      assert.equal(runtime.getSnapshot().phase, 'held')
      return response(url, {}, 401)
    }
    return response(url, user)
  })
  await runtime.verifyAccount()
  await runtime.revoke()
  assert.equal(calls.filter((url) => url.endsWith('/auth/logout-all')).length, 1)
  assert.equal(runtime.sessionStore.getSnapshot(), null)
  assert.equal(runtime.getSnapshot().phase, 'locked')
})

for (const status of [200, 401, 403]) {
  test(`account verification cannot publish late ${status} after session metadata A-B-A`, async (t) => {
    let finish
    const { runtime } = setup(
      t,
      (url) =>
        new Promise((resolve) => {
          finish = () => resolve(response(url, user, status))
        }),
    )
    const pending = runtime.verifyAccount()
    const before = structuredClone(runtime.sessionStore.getSnapshot())
    runtime.sessionStore.setUser({ ...user, display_name: 'replacement' })
    runtime.sessionStore.setUser(user)
    finish()
    await pending
    assert.deepEqual(runtime.sessionStore.getSnapshot(), before)
    assert.notEqual(runtime.getAccountSnapshot().phase, 'connected')
    assert.notEqual(
      runtime.getAccountSnapshot().phase,
      'verifying',
      'explicit retry must stay reachable',
    )
  })
}

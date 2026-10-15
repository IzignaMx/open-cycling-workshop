import 'fake-indexeddb/auto'
import test from 'node:test'
import assert from 'node:assert/strict'
import { WorkshopController } from '../../.tmp-runtime/src/runtime/controller.js'
import { InventoryController } from '../../.tmp-inventory/src/features/inventory/controller.js'
import { InventoryHttpError } from '../../.tmp-inventory/src/features/inventory/contracts.js'
import { createKernelDatabase } from '../../.tmp-runtime/src/access-kernel/database.js'

const realm = 'https://connected-read.test/api/v1'
const NOW = Date.parse('2026-10-15T00:00:00Z')
const user = {
  user_id: 'reader',
  organization_id: 'org',
  location_id: 'loc',
  display_name: 'Reader',
  capabilities: ['inventory.read'],
}
const wire = (account = user, patch = {}) => ({
  protocol: 1,
  principal: {
    api_realm: null,
    organization_id: account.organization_id,
    user_id: account.user_id,
  },
  account_location_id: account.location_id,
  selected_location_id: account.location_id ?? 'loc',
  capabilities: account.capabilities,
  authorization_epoch: 'a'.repeat(43),
  policy_revision: 'ocwp-access-baseline-2',
  dataset_incarnation: '0199ba00-0000-7000-8000-000000000001',
  verified_at: new Date(NOW).toISOString(),
  offline_until: new Date(NOW + 3600000).toISOString(),
  snapshot_protocol: null,
  ...patch,
})
function response(url, body, status = 200, headers = {}) {
  const result = new Response(typeof body === 'string' ? body : JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json', 'cache-control': 'no-store', ...headers },
  })
  Object.defineProperty(result, 'url', { value: String(url) })
  return result
}
function setup(t, { account = user, handle, directory, now = NOW, online = true } = {}) {
  const values = new Map(),
    calls = [],
    env = { now, online, account }
  const runtime = new WorkshopController({
    apiRealm: realm,
    storage: {
      getItem: (key) => values.get(key) ?? null,
      setItem: (key, value) => values.set(key, value),
      removeItem: (key) => values.delete(key),
    },
    database: createKernelDatabase('connected-read-' + crypto.randomUUID()),
    factory: indexedDB,
    now: () => env.now,
    online: () => env.online,
    fetch: function (url, init) {
      calls.push({ url: String(url), init, receiver: this })
      if (String(url).endsWith('/auth/me')) return Promise.resolve(response(url, env.account))
      if (String(url).includes('/locations?') && directory) return directory(url, init)
      if (String(url).includes('/locations?'))
        return Promise.resolve(
          response(url, {
            items: [
              { location_id: 'loc', organization_id: 'org', name: 'Workshop' },
              { location_id: 'loc2', organization_id: 'org', name: 'Other workshop' },
            ],
            next_cursor: null,
          }),
        )
      return handle ? handle(url, init, env) : Promise.resolve(response(url, wire(env.account)))
    },
  })
  runtime.sessionStore.setToken('synthetic-reader-token')
  runtime.sessionStore.setUser(account)
  t.after(() => runtime.dispose())
  return { runtime, calls, env, values }
}
async function admitted(t, options) {
  const state = setup(t, options)
  await state.runtime.verifyAccount()
  return state
}
const turn = () => new Promise((resolve) => setImmediate(resolve))

for (const protocol of [null, 'baseline-v1']) {
  test(`account-only context ${protocol} is metadata only and binds the fetch receiver`, async (t) => {
    const { runtime, calls } = await admitted(t, {
      online: false,
      handle: async (url) => response(url, wire(user, { snapshot_protocol: protocol })),
    })
    runtime.kernel.beginVerification = () =>
      assert.fail('no kernel verification for account-only read')
    runtime.kernel.acceptVerifiedContext = () => assert.fail('no durable context adoption')
    runtime.kernel.inspectSession = () => assert.fail('no invented operational owner')
    runtime.invalidateBrandingAccount = () => assert.fail('no branding authority dependency')
    assert.throws(() => runtime.connectedReads.capture())
    await runtime.connectedReads.verify()
    const snapshot = runtime.connectedReads.getSnapshot(),
      capture = runtime.connectedReads.capture()
    assert.equal(snapshot.phase, 'ready')
    assert.equal(snapshot.context.snapshotProtocol, protocol)
    assert.equal(capture.isCurrent(), true)
    assert.equal(Object.isFrozen(capture), true)
    assert.equal(Object.isFrozen(capture.context), true)
    assert.equal(Object.isFrozen(capture.context.principal), true)
    assert.equal(Object.isFrozen(capture.context.capabilities), true)
    assert.equal(runtime.getSnapshot().context, null)
    assert.equal(runtime.sessionStore.getSnapshot().admission, null)
    assert.equal(JSON.stringify(snapshot).includes('synthetic-reader-token'), false)
    assert.deepEqual(
      calls.map(({ url }) => new URL(url).pathname),
      ['/api/v1/auth/me', '/api/v1/auth/context'],
    )
    const sent = calls.at(-1)
    assert.equal(sent.receiver, globalThis)
    assert.equal(sent.init.method, 'GET')
    assert.equal(sent.init.cache, 'no-store')
    assert.equal(sent.init.redirect, 'error')
    assert.equal(sent.init.credentials, 'omit')
    assert.equal(sent.init.referrerPolicy, 'no-referrer')
    assert.equal(sent.init.headers['X-OCWP-Write-Protocol'], undefined)
    assert.equal(sent.init.signal instanceof AbortSignal, true)
    assert.equal(await runtime.database.accessContexts.count(), 0)
  })
}

test('unverified stored metadata never produces an authority capture or context request', async (t) => {
  const { runtime, calls } = setup(t)
  await runtime.connectedReads.verify()
  assert.equal(runtime.connectedReads.getSnapshot().phase, 'unavailable')
  assert.throws(() => runtime.connectedReads.capture())
  assert.equal(calls.length, 0)
})

test('organization-wide locations.read chooses only the runtime bounded directory without sync', async (t) => {
  const account = { ...user, location_id: null, capabilities: ['inventory.read', 'locations.read'] }
  const { runtime, calls } = setup(t, { account })
  runtime.kernel.beginVerification = () => assert.fail('directory selection must not enter kernel')
  await runtime.start()
  await runtime.connectedReads.verify()
  assert.match(runtime.connectedReads.getSnapshot().message, /taller/i)
  await runtime.loadLocations()
  await runtime.connectedReads.verify('arbitrary')
  assert.equal(calls.filter(({ url }) => url.includes('/auth/context')).length, 0)
  await runtime.connectedReads.verify('loc')
  assert.equal(runtime.connectedReads.getSnapshot().phase, 'ready')
  assert.equal(runtime.connectedReads.capture().context.selectedLocationId, 'loc')
  assert.equal(runtime.getSnapshot().selectedLocationId, null)
  assert.equal(runtime.sessionStore.getSnapshot().admission, null)
})

test('organization-wide inventory-only account cannot fetch directory or supply an arbitrary scope', async (t) => {
  const { runtime, calls } = setup(t, { account: { ...user, location_id: null } })
  await runtime.start()
  await runtime.loadLocations()
  await runtime.connectedReads.verify('loc')
  assert.equal(runtime.connectedReads.getSnapshot().phase, 'unavailable')
  assert.equal(
    calls.some(({ url }) => /\/locations|\/auth\/context/.test(url)),
    false,
  )
})

test('bound account cannot override its workshop', async (t) => {
  const { runtime, calls } = await admitted(t)
  await runtime.connectedReads.verify('loc2')
  assert.equal(runtime.connectedReads.getSnapshot().context, null)
  assert.equal(
    calls.some(({ url }) => url.includes('/auth/context')),
    false,
  )
})

for (const action of ['offline', 'logout', 'dispose', 'clear', 'invalidateAccount']) {
  test(`${action} synchronously clears protected context and aborts captures`, async (t) => {
    const { runtime } = await admitted(t)
    await runtime.connectedReads.verify()
    const capture = runtime.connectedReads.capture()
    let cleared = false
    runtime.connectedReads.subscribe(() => {
      cleared ||= runtime.connectedReads.getSnapshot().context === null
    })
    const pending = action === 'clear' ? runtime.connectedReads.clear() : runtime[action]()
    assert.equal(cleared, true)
    assert.equal(runtime.connectedReads.getSnapshot().context, null)
    assert.equal(capture.signal.aborted, true)
    assert.equal(capture.isCurrent(), false)
    await pending
  })
}

for (const status of [401, 403]) {
  test(`current ${status} invalidates before missing headers or a stalled body`, async (t) => {
    let cancel = false
    const { runtime } = await admitted(t, {
      handle: async (url) => {
        const result = new Response(
          new ReadableStream({
            cancel() {
              cancel = true
            },
          }),
          { status },
        )
        Object.defineProperty(result, 'url', { value: String(url) })
        return result
      },
    })
    await runtime.connectedReads.verify()
    assert.equal(runtime.connectedReads.getSnapshot().context, null)
    assert.equal(runtime.getAccountSnapshot().phase, 'unverified')
    assert.equal(cancel, true)
    if (status === 401) assert.equal(runtime.sessionStore.getSnapshot(), null)
    else assert.equal(runtime.getSnapshot().phase, 'held')
  })
}

test('metadata and token A-B-A replacements synchronously invalidate captures', async (t) => {
  const { runtime } = await admitted(t)
  await runtime.connectedReads.verify()
  const capture = runtime.connectedReads.capture()
  runtime.sessionStore.setUser({ ...user, display_name: 'B' })
  assert.equal(runtime.connectedReads.getSnapshot().context, null)
  runtime.sessionStore.setUser(user)
  assert.equal(capture.isCurrent(), false)
  await runtime.verifyAccount()
  await runtime.connectedReads.verify()
  const next = runtime.connectedReads.capture()
  runtime.sessionStore.setToken('token-B')
  runtime.sessionStore.setUser(user)
  runtime.sessionStore.setToken('synthetic-reader-token')
  runtime.sessionStore.setUser(user)
  assert.equal(next.isCurrent(), false)
})

for (const result of [200, 401, 403, 'error']) {
  test(`late ${result} from account A-B-A cannot publish or invalidate fresh A`, async (t) => {
    let finish,
      pendingRequest = true
    const { runtime } = await admitted(t, {
      handle: (url) => {
        if (!pendingRequest) return Promise.resolve(response(url, wire()))
        return new Promise((resolve, reject) => {
          finish = () =>
            result === 'error'
              ? reject(new Error('private failure'))
              : resolve(response(url, result === 200 ? wire() : {}, result))
        })
      },
    })
    const pending = runtime.connectedReads.verify()
    await turn()
    runtime.sessionStore.setUser({ ...user, user_id: 'B' })
    runtime.sessionStore.setUser(user)
    await runtime.verifyAccount()
    pendingRequest = false
    await runtime.connectedReads.verify()
    const fresh = runtime.connectedReads.capture()
    finish()
    await pending
    assert.equal(fresh.isCurrent(), true)
    assert.equal(runtime.connectedReads.capture().generation, fresh.generation)
    assert.equal(runtime.sessionStore.getSnapshot().user.user_id, 'reader')
  })
}

test('only genuine current facade captures can refuse authority', async (t) => {
  const { runtime } = await admitted(t)
  await runtime.connectedReads.verify()
  const old = runtime.connectedReads.capture()
  await runtime.connectedReads.verify()
  const fresh = runtime.connectedReads.capture()
  runtime.connectedReads.refuse(old, 401)
  runtime.connectedReads.refuse({ ...fresh }, 401)
  assert.equal(fresh.isCurrent(), true)
  runtime.connectedReads.refuse(fresh, 403)
  assert.equal(fresh.isCurrent(), false)
  assert.equal(runtime.getSnapshot().phase, 'held')
})

test('account-only idle timer truncates server microseconds and never creates offline permission', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const { runtime, env } = await admitted(t, {
    handle: async (url) =>
      response(url, wire(user, { offline_until: '2026-10-15T00:00:00.010999Z' })),
  })
  await runtime.connectedReads.verify()
  const capture = runtime.connectedReads.capture()
  env.now += 9
  t.mock.timers.tick(9)
  assert.equal(capture.isCurrent(), true)
  env.now += 1
  t.mock.timers.tick(1)
  assert.equal(runtime.connectedReads.getSnapshot().context, null)
  assert.equal(capture.signal.aborted, true)
  assert.equal(runtime.getSnapshot().context, null)
})

for (const invalid of ['expired', 'rollback', 'nonfinite']) {
  test(`checkLease clears account-only ${invalid} synchronously before its no-active return`, async (t) => {
    const { runtime, env } = await admitted(t)
    await runtime.connectedReads.verify()
    const capture = runtime.connectedReads.capture()
    env.now = invalid === 'expired' ? NOW + 3600000 : invalid === 'rollback' ? NOW - 1 : NaN
    const pending = runtime.checkLease()
    assert.equal(runtime.connectedReads.getSnapshot().context, null)
    assert.equal(capture.isCurrent(), false)
    await pending
  })
}

test('each currentness observation advances rollback fence', async (t) => {
  const { runtime, env } = await admitted(t)
  await runtime.connectedReads.verify()
  const capture = runtime.connectedReads.capture()
  env.now += 1000
  assert.equal(capture.isCurrent(), true)
  env.now -= 1
  assert.equal(capture.isCurrent(), false)
  assert.equal(runtime.connectedReads.getSnapshot().context, null)
})

for (const stalled of ['fetch', 'body']) {
  test(`ten-second deadline bounds ${stalled} and abort-ignoring late responses`, async (t) => {
    t.mock.timers.enable({ apis: ['setTimeout'] })
    let finish, signal
    const { runtime } = await admitted(t, {
      handle: (url, init) => {
        signal = init.signal
        if (stalled === 'fetch')
          return new Promise((resolve) => {
            finish = () => resolve(response(url, wire()))
          })
        const result = new Response(new ReadableStream(), {
          headers: { 'content-type': 'application/json', 'cache-control': 'no-store' },
        })
        Object.defineProperty(result, 'url', { value: String(url) })
        return Promise.resolve(result)
      },
    })
    const pending = runtime.connectedReads.verify()
    await turn()
    t.mock.timers.tick(10000)
    await pending
    assert.equal(signal.aborted, true)
    assert.equal(runtime.connectedReads.getSnapshot().phase, 'unavailable')
    finish?.()
    await turn()
    assert.equal(runtime.connectedReads.getSnapshot().context, null)
  })
}

for (const patch of [
  { principal: { api_realm: null, organization_id: 'foreign', user_id: 'reader' } },
  { selected_location_id: 'other' },
  { account_location_id: null },
  { capabilities: ['inventory.read', 'inventory.write'] },
  { authorization_epoch: 'bad' },
  { dataset_incarnation: 'bad' },
  { offline_until: '2026-10-14T23:59:59Z' },
]) {
  test(`strict context conversion and authority equality reject ${Object.keys(patch)[0]}`, async (t) => {
    const { runtime } = await admitted(t, {
      handle: async (url) => response(url, wire(user, patch)),
    })
    await runtime.connectedReads.verify()
    assert.equal(runtime.connectedReads.getSnapshot().context, null)
    assert.throws(() => runtime.connectedReads.capture())
  })
}

for (const variant of [
  'missing-no-store',
  'wrong-mime',
  'redirect',
  'wrong-url',
  'oversized',
  'malformed-json',
]) {
  test(`context rejects ${variant} without publishing private bytes`, async (t) => {
    const { runtime } = await admitted(t, {
      handle: async (url) => {
        const result = response(
          url,
          variant === 'oversized' ? 'x'.repeat(16385) : variant === 'malformed-json' ? '{' : wire(),
        )
        if (variant === 'missing-no-store') result.headers.delete('cache-control')
        if (variant === 'wrong-mime') result.headers.set('content-type', 'text/html')
        if (variant === 'redirect') Object.defineProperty(result, 'redirected', { value: true })
        if (variant === 'wrong-url') return response(realm + '/foreign', wire())
        return result
      },
    })
    await runtime.connectedReads.verify()
    assert.equal(runtime.connectedReads.getSnapshot().phase, 'unavailable')
    assert.equal(runtime.connectedReads.getSnapshot().context, null)
  })
}

for (const outcome of [200, 401, 403, 'error']) {
  test(`workshop A-B-A fences late context ${outcome}`, async (t) => {
    const account = {
      ...user,
      location_id: null,
      capabilities: ['inventory.read', 'locations.read'],
    }
    let finish,
      blocked = true
    const { runtime } = setup(t, {
      account,
      handle: (url) => {
        const location = new URL(url).searchParams.get('selected_location_id')
        if (blocked)
          return new Promise((resolve, reject) => {
            finish = () =>
              outcome === 'error'
                ? reject(new Error('private'))
                : resolve(
                    response(
                      url,
                      outcome === 200 ? wire(account, { selected_location_id: location }) : {},
                      outcome,
                    ),
                  )
          })
        return Promise.resolve(response(url, wire(account, { selected_location_id: location })))
      },
    })
    await runtime.start()
    await runtime.loadLocations()
    const pending = runtime.connectedReads.verify('loc')
    await turn()
    blocked = false
    await runtime.connectedReads.verify('loc2')
    await runtime.connectedReads.verify('loc')
    const fresh = runtime.connectedReads.capture()
    finish()
    await pending
    assert.equal(fresh.isCurrent(), true)
    assert.equal(fresh.context.selectedLocationId, 'loc')
  })
}

async function operational(t) {
  const account = { ...user, capabilities: ['inventory.read', 'sync.pull'] }
  const baselineId = '0199ba00-0000-7000-8000-000000000002'
  const state = setup(t, {
    account,
    handle: async (url, init, env) => {
      const path = new URL(url).pathname,
        body = init.body ? JSON.parse(init.body) : null
      const context = wire(account, {
        snapshot_protocol: 'baseline-v1',
        ...(env.contextPatch ?? {}),
      })
      if (path.endsWith('/auth/login'))
        return response(url, { access_token: 'operational-token', token_type: 'bearer' })
      if (path.endsWith('/auth/context')) return response(url, context)
      if (path.endsWith('/baselines/start'))
        return response(url, {
          protocol: 1,
          baseline_id: baselineId,
          context,
          continuation: 'scan',
          expires_at: new Date(NOW + 1800000).toISOString(),
        })
      if (path.endsWith('/baselines/page'))
        return response(url, {
          protocol: 1,
          baseline_id: baselineId,
          authorization_epoch: context.authorization_epoch,
          page_id: 'page',
          predecessor: body.continuation,
          records: [],
          phase: 'scan_complete',
          continuation: 'finalize',
        })
      if (path.endsWith('/baselines/finalize'))
        return response(url, {
          protocol: 1,
          baseline_id: baselineId,
          authorization_epoch: context.authorization_epoch,
          predecessor: body.continuation,
          continuation: 'delta',
        })
      if (path.endsWith('/deltas/page'))
        return response(url, {
          protocol: 1,
          baseline_id: body.continuation === 'delta' ? baselineId : null,
          authorization_epoch: context.authorization_epoch,
          page_id: 'delta-page',
          predecessor: body.continuation,
          records: [],
          phase: 'complete',
          continuation: 'checkpoint',
          completion: {
            baseline_id: body.continuation === 'delta' ? baselineId : null,
            authorization_epoch: context.authorization_epoch,
            checkpoint: 'checkpoint',
          },
        })
      if (path.endsWith('/validate-activation'))
        return response(url, {
          protocol: 1,
          baseline_id: baselineId,
          authorization_epoch: context.authorization_epoch,
          checkpoint: body.checkpoint,
          context,
        })
      throw new Error('Unexpected operational fixture endpoint')
    },
  })
  // Start the real observer from an empty session. Starting from the seeded
  // account here would begin a first baseline immediately before login's second.
  state.runtime.sessionStore.clear()
  await state.runtime.start()
  await state.runtime.login({
    organization_id: 'org',
    username: 'reader',
    password: 'synthetic-only',
  })
  for (let i = 0; i < 200 && state.runtime.getSnapshot().phase === 'baseline'; i++)
    await new Promise((resolve) => setTimeout(resolve, 5))
  assert.equal(state.runtime.getSnapshot().phase, 'ready', state.runtime.getSnapshot().message)
  // Stop the existing routine sync scheduler without admitting any new read authority.
  await state.runtime.offline()
  await state.runtime.verifyAccount()
  return state
}

test('operational context validates the real kernel owner before and after response and on check', async (t) => {
  const { runtime } = await operational(t)
  const inspect = runtime.kernel.inspectSession.bind(runtime.kernel),
    tickets = []
  runtime.kernel.inspectSession = async (ticket, current) => {
    tickets.push(structuredClone(ticket))
    return inspect(ticket, current)
  }
  await runtime.connectedReads.verify()
  assert.equal(runtime.connectedReads.getSnapshot().phase, 'ready')
  assert.equal(tickets.length, 2)
  const admission = runtime.sessionStore.getSnapshot().admission
  assert.deepEqual(tickets[0], admission.owner)
  assert.deepEqual(tickets[1], admission.owner)
  await runtime.connectedReads.check()
  assert.equal(tickets.length, 3)
  const capture = runtime.connectedReads.capture()
  await runtime.database.deviceControl.update('device', {
    generation: admission.owner.deviceGeneration + 1,
  })
  await runtime.connectedReads.check()
  assert.equal(capture.isCurrent(), false)
  assert.equal(runtime.connectedReads.getSnapshot().context, null)
  assert.equal(runtime.getSnapshot().phase, 'held')
})

for (const field of ['authorization_epoch', 'dataset_incarnation']) {
  test(`operational ${field} mismatch cannot adopt new authority`, async (t) => {
    const { runtime, env } = await operational(t)
    const prior = runtime.getSnapshot().context
    env.contextPatch = {
      [field]:
        field === 'authorization_epoch' ? 'b'.repeat(43) : '0199ba00-0000-7000-8000-000000000099',
    }
    await runtime.connectedReads.verify()
    assert.equal(runtime.connectedReads.getSnapshot().context, null)
    assert.throws(() => runtime.connectedReads.capture())
    const stored = await runtime.database.accessContexts.toArray()
    assert.equal(stored[0].context.authorizationEpoch, prior.authorizationEpoch)
    assert.equal(stored[0].context.datasetIncarnation, prior.datasetIncarnation)
  })
}

for (const outcome of [200, 401, 403]) {
  test(`suspended deadline timer cannot admit late ${outcome} after ten seconds`, async (t) => {
    t.mock.timers.enable({ apis: ['setTimeout'] })
    let finish
    const { runtime, env } = await admitted(t, {
      handle: (url) =>
        new Promise((resolve) => {
          finish = () => resolve(response(url, outcome === 200 ? wire() : {}, outcome))
        }),
    })
    const pending = runtime.connectedReads.verify()
    await turn()
    env.now += 10001
    finish()
    await pending
    assert.equal(runtime.connectedReads.getSnapshot().phase, 'unavailable')
    assert.equal(runtime.connectedReads.getSnapshot().context, null)
    assert.equal(runtime.getAccountSnapshot().phase, 'connected')
    assert.notEqual(runtime.sessionStore.getSnapshot(), null)
  })
}

test('known operational epoch change holds the operational view instead of retaining old authority', async (t) => {
  const { runtime, env } = await operational(t)
  env.contextPatch = { authorization_epoch: 'b'.repeat(43) }
  await runtime.connectedReads.verify()
  assert.equal(runtime.getSnapshot().phase, 'held')
  assert.equal(runtime.getAccountSnapshot().phase, 'unverified')
})

test('explicit verification recovers after suspended timer expiry with a new server lease', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const { runtime, env } = await admitted(t, {
    handle: async (url, _init, env) =>
      response(
        url,
        wire(user, {
          verified_at: new Date(env.now).toISOString(),
          offline_until: new Date(env.now + 1000).toISOString(),
        }),
      ),
  })
  await runtime.connectedReads.verify()
  const old = runtime.connectedReads.capture()
  env.now += 1001
  await runtime.connectedReads.verify()
  assert.equal(old.isCurrent(), false)
  assert.equal(runtime.connectedReads.getSnapshot().phase, 'ready')
  assert.equal(
    runtime.connectedReads.getSnapshot().context.verifiedAt,
    new Date(env.now).toISOString(),
  )
})

test('account invalidation closes authority before notifying connected-read subscribers', async (t) => {
  const { runtime } = await admitted(t)
  await runtime.connectedReads.verify()
  let recaptured = false
  runtime.connectedReads.subscribe(() => {
    try {
      runtime.captureAccount()
      recaptured = true
    } catch {
      /* expected closed boundary */
    }
  })
  runtime.invalidateAccount()
  assert.equal(recaptured, false)
})

test('late directory response after session A-B-A cannot authorize a connected selection', async (t) => {
  const account = { ...user, location_id: null, capabilities: ['inventory.read', 'locations.read'] }
  let finish
  const { runtime, calls } = setup(t, {
    account,
    directory: (url) =>
      new Promise((resolve) => {
        finish = () =>
          resolve(
            response(url, {
              items: [{ location_id: 'loc', organization_id: 'org', name: 'Old directory' }],
              next_cursor: null,
            }),
          )
      }),
  })
  await runtime.start()
  const pending = runtime.loadLocations()
  await turn()
  runtime.sessionStore.setUser({ ...account, display_name: 'B' })
  runtime.sessionStore.setUser(account)
  await runtime.verifyAccount()
  finish()
  await pending
  assert.deepEqual(runtime.getSnapshot().locations, [])
  await runtime.connectedReads.verify('loc')
  assert.equal(
    calls.some(({ url }) => url.includes('/auth/context')),
    false,
  )
})

test('sync.pull alone cannot dispatch a location-directory request', async (t) => {
  const account = { ...user, location_id: null, capabilities: ['inventory.read', 'sync.pull'] }
  const { runtime, calls } = setup(t, {
    account,
    handle: async (url) => {
      if (String(url).endsWith('/auth/login'))
        return response(url, { access_token: 'synthetic-sync-token', token_type: 'bearer' })
      throw new Error('Unexpected request')
    },
  })
  await runtime.login({ organization_id: 'org', username: 'reader', password: 'synthetic-only' })
  assert.equal(runtime.getSnapshot().phase, 'selector')
  await runtime.loadLocations()
  assert.equal(
    calls.some(({ url }) => url.includes('/locations?')),
    false,
  )
  assert.deepEqual(runtime.getSnapshot().locations, [])
})

// Committed durable ownership must be checked even before its observer notification.
for (const outcome of ['success', 401, 403, 500]) {
  test(`inventory checks durable operational ownership before publishing ${outcome}`, async (t) => {
    const { runtime } = await operational(t)
    await runtime.connectedReads.verify()
    let finish, dispatched
    const entered = new Promise((resolve) => {
      dispatched = resolve
    })
    const inventory = new InventoryController(
      runtime,
      {
        catalog: () => {
          dispatched()
          return new Promise((resolve, reject) => {
            finish = () =>
              outcome === 'success'
                ? resolve([{ product_id: 'protected', name: 'protected product' }])
                : reject(
                    new InventoryHttpError(
                      outcome === 401
                        ? 'invalid_session'
                        : outcome === 403
                          ? 'capability_denied'
                          : 'unavailable',
                      outcome,
                    ),
                  )
          })
        },
      },
      () => NOW,
    )
    t.after(() => inventory.dispose())
    const pending = inventory.loadCatalog()
    await entered
    const owner = runtime.sessionStore.getSnapshot().admission.owner
    await runtime.database.deviceControl.update('device', {
      generation: owner.deviceGeneration + 1,
    })
    finish()
    await pending
    assert.equal(inventory.getSnapshot().catalog.value, null)
    assert.notEqual(
      runtime.sessionStore.getSnapshot(),
      null,
      'obsolete refusal must not log out account',
    )
    assert.equal(runtime.connectedReads.getSnapshot().context, null)
  })
}
test('inventory checks committed operational owner before any request dispatch', async (t) => {
  const { runtime } = await operational(t)
  await runtime.connectedReads.verify()
  let calls = 0
  const inventory = new InventoryController(
    runtime,
    {
      catalog: async () => {
        calls++
        return []
      },
    },
    () => NOW,
  )
  t.after(() => inventory.dispose())
  const owner = runtime.sessionStore.getSnapshot().admission.owner
  await runtime.database.deviceControl.update('device', { generation: owner.deviceGeneration + 1 })
  await inventory.loadCatalog()
  assert.equal(calls, 0)
  assert.equal(inventory.getSnapshot().catalog.value, null)
})

test('organization-wide connected reader refreshes authorized directory after explicit 403 reverification', async (t) => {
  const account = { ...user, location_id: null, capabilities: ['inventory.read', 'locations.read'] }
  const { runtime, calls } = setup(t, { account })
  await runtime.start()
  await runtime.loadLocations()
  await runtime.connectedReads.verify('loc')
  assert.equal(runtime.connectedReads.getSnapshot().phase, 'ready')
  runtime.connectedReads.refuse(runtime.connectedReads.capture(), 403)
  assert.equal(runtime.getSnapshot().phase, 'held')
  const before = calls.length
  await runtime.loadLocations()
  assert.equal(calls.length, before, 'held unverified account cannot fetch a directory')
  await runtime.verifyAccount()
  await runtime.loadLocations()
  assert.equal(runtime.getSnapshot().locations.length, 2)
  await runtime.connectedReads.verify('loc')
  assert.equal(runtime.connectedReads.getSnapshot().phase, 'ready')
  assert.equal(
    calls.some(({ url }) => /baselines|deltas/.test(url)),
    false,
  )
  assert.equal(runtime.sessionStore.getSnapshot().admission, null)
})

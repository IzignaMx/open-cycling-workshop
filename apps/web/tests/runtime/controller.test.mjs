import 'fake-indexeddb/auto'
import test from 'node:test'
import assert from 'node:assert/strict'
import { WorkshopController } from '../../.tmp-runtime/src/runtime/controller.js'
import { createKernelDatabase } from '../../.tmp-runtime/src/access-kernel/database.js'
class Storage {
  values = new Map()
  getItem(k) {
    return this.values.get(k) ?? null
  }
  setItem(k, v) {
    this.values.set(k, v)
  }
  removeItem(k) {
    this.values.delete(k)
  }
  clone() {
    const s = new Storage()
    s.values = new Map(this.values)
    return s
  }
}
const NOW = Date.parse('2026-10-14T10:00:00Z'),
  realm = 'https://runtime.test/api/v1',
  epoch = 'a'.repeat(43),
  incarnation = '0199ba00-0000-7000-8000-000000000001',
  baselineId = '0199ba00-0000-7000-8000-000000000002'
const response = (url, body) => {
  const r = new Response(JSON.stringify(body), {
    headers: { 'content-type': 'application/json', 'cache-control': 'no-store' },
  })
  Object.defineProperty(r, 'url', { value: url })
  return r
}
const user = (id = 'A') => ({
  user_id: id,
  organization_id: 'org',
  location_id: 'loc',
  display_name: id,
  capabilities: [
    'customers.read',
    'customers.write',
    'orders.read',
    'orders.write',
    'bicycles.read',
    'bicycles.write',
    'sync.push',
    'sync.pull',
  ],
})
const wire = (id = 'A') => ({
  protocol: 1,
  principal: { api_realm: null, organization_id: 'org', user_id: id },
  account_location_id: 'loc',
  selected_location_id: 'loc',
  capabilities: user(id).capabilities,
  authorization_epoch: epoch,
  policy_revision: 'ocwp-access-baseline-2',
  dataset_incarnation: incarnation,
  verified_at: new Date(NOW).toISOString(),
  offline_until: new Date(NOW + 3600000).toISOString(),
  snapshot_protocol: 'baseline-v1',
})
const customer = (id) => ({
  entity_type: 'customer',
  entity_id: 'historical-' + id,
  entity_version: 1,
  payload: {
    customer_id: 'historical-' + id,
    organization_id: 'org',
    location_id: 'loc',
    display_name: 'Private ' + id,
    email: null,
    phone: null,
    created_at: new Date(NOW).toISOString(),
    updated_at: new Date(NOW).toISOString(),
    version: 1,
  },
})
function api() {
  let delta = 0
  const calls = []
  return {
    calls,
    fetch: async (url, init) => {
      const path = new URL(url).pathname,
        body = init.body ? JSON.parse(init.body) : null,
        id = init.headers.Authorization?.replace('Bearer token-', '') ?? 'A'
      calls.push(path)
      let value
      if (path.endsWith('/auth/login'))
        value = { access_token: 'token-' + body.username, token_type: 'bearer' }
      else if (path.endsWith('/auth/me')) value = user(id)
      else if (path.endsWith('/auth/context')) value = wire(id)
      else if (path.endsWith('/baselines/start'))
        value = {
          protocol: 1,
          baseline_id: baselineId,
          context: wire(id),
          continuation: 'scan',
          expires_at: new Date(NOW + 1800000).toISOString(),
        }
      else if (path.endsWith('/baselines/page'))
        value = {
          protocol: 1,
          baseline_id: baselineId,
          authorization_epoch: epoch,
          page_id: 'page',
          predecessor: body.continuation,
          records: [customer(id)],
          phase: 'scan_complete',
          continuation: 'finalize',
        }
      else if (path.endsWith('/baselines/finalize'))
        value = {
          protocol: 1,
          baseline_id: baselineId,
          authorization_epoch: epoch,
          predecessor: body.continuation,
          continuation: 'delta',
        }
      else if (path.endsWith('/deltas/page')) {
        const initial = body.continuation === 'delta',
          checkpoint = initial ? 'checkpoint' : `checkpoint-${++delta}`
        value = {
          protocol: 1,
          baseline_id: initial ? baselineId : null,
          authorization_epoch: epoch,
          page_id: 'delta-page-' + delta,
          predecessor: body.continuation,
          records: [],
          phase: 'complete',
          continuation: checkpoint,
          completion: {
            baseline_id: initial ? baselineId : null,
            authorization_epoch: epoch,
            checkpoint,
          },
        }
      } else if (path.endsWith('/validate-activation'))
        value = {
          protocol: 1,
          baseline_id: baselineId,
          authorization_epoch: epoch,
          checkpoint: body.checkpoint,
          context: wire(id),
        }
      else throw new Error('Unexpected endpoint ' + path)
      return response(url, value)
    },
  }
}
async function until(fn, description) {
  for (let i = 0; i < 100; i++) {
    if (fn()) return
    await new Promise((r) => setTimeout(r, 10))
  }
  assert.fail(description)
}
function setup(
  t,
  {
    storage = new Storage(),
    name = 'runtime-' + crypto.randomUUID(),
    server = api(),
    online = true,
    now = NOW,
    apiRealm = realm,
  } = {},
) {
  const env = { online, now },
    database = createKernelDatabase(name),
    runtime = new WorkshopController({
      apiRealm,
      storage,
      database,
      fetch: server.fetch,
      online: () => env.online,
      now: () => env.now,
      factory: indexedDB,
    })
  t.after(() => runtime.dispose())
  return { runtime, storage, database, server, env, name }
}
async function login(runtime, id = 'A') {
  await runtime.login({ organization_id: 'org', username: id, password: 'synthetic' })
  await until(
    () => ['ready', 'held'].includes(runtime.getSnapshot().phase),
    'baseline did not finish',
  )
  assert.equal(runtime.getSnapshot().phase, 'ready', runtime.getSnapshot().message)
  await until(
    () => runtime.getSnapshot().customers.some((row) => row.display_name === 'Private ' + id),
    'initial visible page did not finish',
  )
}
test('production composition requires real parsed pages, isolated DB and offline same-session reload', async (t) => {
  const first = setup(t)
  await first.runtime.start()
  assert.equal(first.runtime.getSnapshot().customers.length, 0)
  await login(first.runtime)
  assert.equal(first.runtime.getSnapshot().customers[0].display_name, 'Private A')
  assert.ok(first.server.calls.includes('/api/v1/auth/context'))
  assert.ok(first.server.calls.includes('/api/v1/sync/baselines/validate-activation'))
  const saved = first.storage.getItem('ocwp.session.v2')
  assert.ok(JSON.parse(saved).admission.datasetIncarnation)
  assert.ok(!JSON.stringify(await first.database.accessContexts.toArray()).includes('token-A'))
  first.runtime.dispose()
  const second = setup(t, { name: first.name, storage: first.storage, online: false })
  await second.runtime.start()
  assert.equal(second.runtime.getSnapshot().phase, 'ready', second.runtime.getSnapshot().message)
  assert.equal(second.runtime.getSnapshot().customers[0].display_name, 'Private A')
  assert.equal(second.server.calls.length, 0)
})
test('logout blanks synchronously; A/B replacement cannot restore older view', async (t) => {
  const f = setup(t)
  await login(f.runtime)
  const pending = f.runtime.logout()
  assert.equal(f.runtime.getSnapshot().customers.length, 0)
  assert.equal(f.runtime.getSnapshot().user, null)
  await pending
  await login(f.runtime, 'B')
  assert.deepEqual(
    f.runtime.getSnapshot().customers.map((x) => x.display_name),
    ['Private B'],
  )
})
test('visible lease rollback blanks immediately and does not wait for another repository access', async (t) => {
  const f = setup(t)
  await login(f.runtime)
  f.env.now = NOW - 1
  const pending = f.runtime.checkLease()
  assert.equal(f.runtime.getSnapshot().phase, 'held')
  assert.equal(f.runtime.getSnapshot().customers.length, 0)
  await pending
})
test('cloned online reload loses exact owner CAS without verification tug-of-war', async (t) => {
  const first = setup(t)
  await login(first.runtime)
  const cloned = first.storage.clone()
  first.runtime.dispose()
  const a = setup(t, { name: first.name, storage: first.storage }),
    b = setup(t, { name: first.name, storage: cloned })
  await Promise.all([a.runtime.start(), b.runtime.start()])
  await until(() => [a, b].some((f) => f.runtime.getSnapshot().phase === 'ready'), 'no winning tab')
  const phases = [a.runtime.getSnapshot().phase, b.runtime.getSnapshot().phase].sort()
  assert.deepEqual(phases, ['held', 'ready'])
  const loser = [a, b].find((f) => f.runtime.getSnapshot().phase === 'held')
  const before = loser.server.calls.length
  await loser.runtime.checkLease()
  assert.equal(loser.server.calls.length, before)
})

test('live durable takeover blanks the previous tab without stealing the new session back', async (t) => {
  const first = setup(t)
  await first.runtime.start()
  await login(first.runtime)
  const second = setup(t, { name: first.name })
  await second.runtime.start()
  await login(second.runtime, 'B')
  await until(
    () => first.runtime.getSnapshot().phase === 'held',
    'old tab did not observe takeover',
  )
  assert.equal(first.runtime.getSnapshot().customers.length, 0)
  await first.runtime.checkLease()
  assert.equal(second.runtime.getSnapshot().phase, 'ready')
  assert.deepEqual(
    second.runtime.getSnapshot().customers.map((row) => row.display_name),
    ['Private B'],
  )
})

test('late context verification from A cannot reinstall data after B completes', async (t) => {
  const server = api()
  let release, reached
  const barrier = new Promise((resolve) => {
    reached = resolve
  })
  const original = server.fetch
  server.fetch = async (url, init) => {
    if (
      new URL(url).pathname.endsWith('/auth/context') &&
      init.headers.Authorization === 'Bearer token-A'
    ) {
      reached()
      await new Promise((resolve) => {
        release = resolve
      })
    }
    return original(url, init)
  }
  const f = setup(t, { server })
  const pending = f.runtime.login({ organization_id: 'org', username: 'A', password: 'synthetic' })
  await barrier
  await login(f.runtime, 'B')
  release()
  await pending
  assert.equal(f.runtime.getSnapshot().user.user_id, 'B')
  assert.deepEqual(
    f.runtime.getSnapshot().customers.map((row) => row.display_name),
    ['Private B'],
  )
})

for (const outcome of ['network_error', 'late_ack'])
  test(`disconnect during captured push preserves usable offline session: ${outcome}`, async (t) => {
    const server = api(),
      original = server.fetch
    let reached, release, settled
    const barrier = new Promise((resolve) => {
        reached = resolve
      }),
      completed = new Promise((resolve) => {
        settled = resolve
      })
    const sent = []
    server.fetch = async (url, init) => {
      if (new URL(url).pathname.endsWith('/sync/mutations')) {
        const mutations = JSON.parse(init.body).mutations
        sent.push(mutations.map((row) => row.mutation_id))
        reached()
        await new Promise((resolve) => {
          release = resolve
        })
        settled()
        if (outcome === 'network_error') throw new Error('Network lost')
        return response(url, {
          results: mutations.map((row) => ({
            mutation_id: row.mutation_id,
            entity_id: row.entity_id,
            status: 'applied',
            entity_version: 1,
            error_code: null,
            error_message: null,
          })),
        })
      }
      return original(url, init)
    }
    const f = setup(t, { server: { ...server, fetch: (...args) => server.fetch(...args) } })
    await f.runtime.start()
    await login(f.runtime)
    await until(() => f.runtime.getSnapshot().sync === 'synced', 'initial sync did not finish')
    await f.runtime.createCustomer({ displayName: 'Uncertain customer' })
    await barrier
    f.env.online = false
    await f.runtime.offline()
    release()
    await completed
    await new Promise((resolve) => setTimeout(resolve, 20))
    assert.equal(f.runtime.getSnapshot().phase, 'ready', f.runtime.getSnapshot().message)
    assert.equal(f.runtime.getSnapshot().sync, 'offline')
    assert.equal((await f.database.operationDelivery.toArray())[0].state, 'inflight')
    await f.runtime.createCustomer({ displayName: 'Still works offline' })
    assert.equal(await f.database.operationJournal.count(), 2)
    assert.equal(sent.length, 1)
    const originals = await f.database.operationJournal.toArray()
    const receipts = new Map(),
      effects = new Map()
    if (outcome === 'late_ack') {
      receipts.set(originals[0].mutationId, true)
      effects.set(originals[0].mutationId, 1)
    }
    server.fetch = async (url, init) => {
      if (new URL(url).pathname.endsWith('/sync/mutations')) {
        const mutations = JSON.parse(init.body).mutations
        sent.push(mutations.map((row) => row.mutation_id))
        return response(url, {
          results: mutations.map((row) => {
            if (!receipts.has(row.mutation_id)) {
              receipts.set(row.mutation_id, true)
              effects.set(row.mutation_id, (effects.get(row.mutation_id) ?? 0) + 1)
            }
            return {
              mutation_id: row.mutation_id,
              entity_id: row.entity_id,
              status: 'applied',
              entity_version: 1,
              error_code: null,
              error_message: null,
            }
          }),
        })
      }
      return original(url, init)
    }
    // Controller captured the original fetch function, so dispatch through the mutable test handler.
    f.env.online = true
    await f.runtime.reconnect()
    await until(() => f.runtime.getSnapshot().sync === 'synced', 'reconnect did not finish')
    assert.deepEqual(await f.database.operationJournal.toArray(), originals)
    assert.ok(
      (await f.database.operationDelivery.toArray()).every((row) => row.state === 'applied'),
    )
    assert.equal(effects.size, 2)
    assert.ok([...effects.values()].every((count) => count === 1))
  })

test('push backoff is not reported as all work synchronized', async (t) => {
  const server = api(),
    original = server.fetch
  let pushes = 0
  server.fetch = async (url, init) => {
    if (new URL(url).pathname.endsWith('/sync/mutations')) {
      pushes++
      throw new Error('Temporary network loss')
    }
    return original(url, init)
  }
  const f = setup(t, { server })
  await login(f.runtime)
  await until(() => f.runtime.getSnapshot().sync === 'synced', 'initial sync did not finish')
  await f.runtime.createCustomer({ displayName: 'Still local' })
  await until(() => f.runtime.getSnapshot().sync === 'error', 'first push did not fail')
  f.env.now += 1000
  await f.runtime.sync()
  assert.equal(pushes, 1)
  assert.equal((await f.database.operationDelivery.toArray())[0].state, 'retryable')
  assert.notEqual(f.runtime.getSnapshot().sync, 'synced')
})

test('late recovery issue remains visible and global conflict survives an empty later page', async (t) => {
  const f = setup(t)
  await login(f.runtime)
  f.env.online = false
  await f.runtime.offline()
  for (let i = 0; i < 51; i++) await f.runtime.createCustomer({ displayName: `Retained ${i}` })
  const rows = (await f.database.operationDelivery.toArray()).sort(
    (a, b) => a.localSequence - b.localSequence,
  )
  for (const [index, row] of rows.entries())
    await f.database.operationDelivery.put({
      ...row,
      state: index === 50 ? 'held_recovery' : 'applied',
      dispatchable: 0,
      blocked: index === 50 ? 1 : 0,
      unresolved: index === 50 ? 1 : 0,
    })
  await f.runtime.refresh()
  assert.equal(f.runtime.getSnapshot().issues.length, 1)
  assert.equal(f.runtime.getSnapshot().issues[0].mutationId, rows[50].mutationId)
  assert.equal(f.runtime.getSnapshot().hasIssues, true)
  f.env.online = true
  await f.runtime.reconnect()
  await until(
    () => f.runtime.getSnapshot().sync === 'conflict',
    'recovery issue was not reflected in sync status',
  )
  await f.runtime.loadIssues(Number.MAX_SAFE_INTEGER)
  assert.deepEqual(f.runtime.getSnapshot().issues, [])
  assert.equal(f.runtime.getSnapshot().hasIssues, true)
  assert.equal(f.runtime.getSnapshot().sync, 'conflict')
})

test('local writes without sync.push permission remain honestly pending', async (t) => {
  const server = api(),
    original = server.fetch
  server.fetch = async (url, init) => {
    const raw = await original(url, init),
      body = await raw.json()
    const value = body.context ?? body
    if (Array.isArray(value.capabilities))
      value.capabilities = value.capabilities.filter((capability) => capability !== 'sync.push')
    return response(url, body)
  }
  const f = setup(t, { server })
  await login(f.runtime)
  await until(() => f.runtime.getSnapshot().sync === 'synced', 'initial read sync did not finish')
  await f.runtime.createCustomer({ displayName: 'Pending local-only authorization' })
  await until(
    () => f.runtime.getSnapshot().sync === 'local' && f.runtime.getSnapshot().hasPending,
    'local pending status not published',
  )
  assert.ok(!f.server.calls.some((path) => path.endsWith('/sync/mutations')))
  assert.equal((await f.database.operationDelivery.toArray())[0].state, 'pending')
})

async function retainedReload(t) {
  const first = setup(t)
  await first.runtime.start()
  await login(first.runtime)
  first.env.online = false
  await first.runtime.offline()
  await first.runtime.createCustomer({ displayName: 'Retained offline work' })
  const evidence = {
    journal: await first.database.operationJournal.toArray(),
    delivery: await first.database.operationDelivery.toArray(),
    control: await first.database.deviceControl.get('device'),
    context: first.runtime.getSnapshot().context,
    session: first.runtime.sessionStore.getSnapshot(),
  }
  first.runtime.dispose()
  return { first, evidence }
}

test('online-hint reload with unreachable me admits exact retained offline work without extending lease', async (t) => {
  const { first, evidence } = await retainedReload(t)
  const calls = []
  const second = setup(t, {
    name: first.name,
    storage: first.storage,
    online: true,
    server: {
      fetch: async (url) => {
        calls.push(new URL(url).pathname)
        throw new TypeError('offline')
      },
    },
  })
  await second.runtime.start()
  assert.equal(second.runtime.getSnapshot().phase, 'ready', second.runtime.getSnapshot().message)
  assert.equal(second.runtime.getSnapshot().sync, 'offline')
  assert.deepEqual(second.runtime.getSnapshot().context, evidence.context)
  const control = await second.database.deviceControl.get('device')
  assert.equal(control.generation, evidence.control.generation + 1)
  assert.equal(control.state, 'OFFLINE_READY')
  assert.equal(control.activePartitionId, evidence.control.activePartitionId)
  assert.equal(second.runtime.sessionStore.getSnapshot().bindingId, evidence.session.bindingId)
  assert.deepEqual(await second.database.operationJournal.toArray(), evidence.journal)
  assert.deepEqual(await second.database.operationDelivery.toArray(), evidence.delivery)
  assert.deepEqual(calls, ['/api/v1/auth/me'])
  await second.runtime.createCustomer({ displayName: 'Additional work while hint remains online' })
  await new Promise((resolve) => setTimeout(resolve, 30))
  assert.equal(second.runtime.getSnapshot().phase, 'ready')
  assert.equal(second.runtime.getSnapshot().sync, 'offline')
  assert.equal((await second.database.operationJournal.toArray()).length, 2)
  assert.deepEqual(calls, ['/api/v1/auth/me'])
  await second.runtime.createOrder({
    customerId: 'historical-A',
    reportedProblem: 'Offline intake',
    intakeCondition: null,
    accessories: null,
    priority: 'normal',
    brand: 'Offline bicycle',
    model: null,
  })
  const order = second.runtime.getSnapshot().orders[0]
  await second.runtime.transition(order.order_id, 'start_diagnosis')
  await new Promise((resolve) => setTimeout(resolve, 30))
  assert.equal(second.runtime.getSnapshot().phase, 'ready')
  assert.equal(second.runtime.getSnapshot().sync, 'offline')
  assert.equal((await second.database.operationJournal.toArray()).length, 5)
  assert.equal(second.runtime.getSnapshot().orders[0].state, 'DIAGNOSIS')
  assert.equal(calls.filter((path) => path.endsWith('/auth/me')).length, 1)
  assert.equal(
    calls.some((path) => path.includes('/sync/')),
    false,
  )
})

for (const status of [401, 403, 409, 500]) {
  test(`reachable HTTP ${status} with interrupted body never resumes offline or leaves reusable admission`, async (t) => {
    const { first } = await retainedReload(t)
    const server = {
      fetch: async (url) => {
        const result = new Response(
          new ReadableStream({
            start(controller) {
              controller.error(new TypeError('interrupted'))
            },
          }),
          {
            status,
            headers: { 'content-type': 'application/json', 'cache-control': 'no-store' },
          },
        )
        Object.defineProperty(result, 'url', { value: url })
        return result
      },
    }
    const second = setup(t, { name: first.name, storage: first.storage, server })
    let resumed = 0
    const original = second.runtime.kernel.resumeOffline.bind(second.runtime.kernel)
    second.runtime.kernel.resumeOffline = (...args) => {
      resumed++
      return original(...args)
    }
    await second.runtime.start()
    assert.equal(second.runtime.getSnapshot().phase, 'held')
    assert.equal(resumed, 0)
    second.runtime.dispose()
    const third = setup(t, { name: first.name, storage: first.storage, online: false })
    await third.runtime.start()
    assert.notEqual(third.runtime.getSnapshot().phase, 'ready')
  })
}

for (const mode of [
  'malformed',
  'different_principal',
  'malformed_json',
  'wrong_url',
  'wrong_headers',
]) {
  test(`reachable ${mode} me fails closed and cannot fall back on a later offline reload`, async (t) => {
    const { first } = await retainedReload(t)
    const server = {
      fetch: async (url) => {
        if (mode === 'malformed') return response(url, { broken: true })
        if (mode === 'different_principal') return response(url, user('B'))
        if (mode === 'wrong_url') return response('https://other.test/api/v1/auth/me', user())
        const raw = mode === 'malformed_json' ? '{broken' : JSON.stringify(user())
        const value = new Response(raw, {
          headers: {
            'content-type': 'application/json',
            'cache-control': mode === 'wrong_headers' ? 'public' : 'no-store',
          },
        })
        Object.defineProperty(value, 'url', { value: url })
        return value
      },
    }
    const second = setup(t, { name: first.name, storage: first.storage, server })
    await second.runtime.start()
    assert.equal(second.runtime.getSnapshot().phase, 'held')
    second.runtime.dispose()
    const third = setup(t, { name: first.name, storage: first.storage, online: false })
    await third.runtime.start()
    assert.notEqual(third.runtime.getSnapshot().phase, 'ready')
  })
}

for (const now of [NOW - 1, NOW + 3600000]) {
  test(`unreachable online-hint reload retains clock/lease denial at ${now}`, async (t) => {
    const { first, evidence } = await retainedReload(t)
    const second = setup(t, {
      name: first.name,
      storage: first.storage,
      now,
      server: {
        fetch: async () => {
          throw new TypeError('offline')
        },
      },
    })
    await second.runtime.start()
    assert.equal(second.runtime.getSnapshot().phase, 'held')
    assert.deepEqual(await second.database.operationJournal.toArray(), evidence.journal)
  })
}

for (const outcome of ['network', 'denial', 'success']) {
  test(`late ${outcome} preflight cannot reclaim another tab owner`, async (t) => {
    const { first, evidence } = await retainedReload(t)
    let reached, release
    const barrier = new Promise((resolve) => {
      reached = resolve
    })
    const second = setup(t, {
      name: first.name,
      storage: first.storage,
      server: {
        fetch: async (url) => {
          reached()
          await new Promise((resolve) => {
            release = resolve
          })
          if (outcome === 'network') throw new TypeError('offline')
          if (outcome === 'success') return response(url, user())
          const denied = new Response('{}', {
            status: 401,
            headers: { 'content-type': 'application/json', 'cache-control': 'no-store' },
          })
          Object.defineProperty(denied, 'url', { value: url })
          return denied
        },
      },
    })
    const pending = second.runtime.start()
    await barrier
    const winner = setup(t, { name: first.name })
    await winner.runtime.start()
    await login(winner.runtime, 'B')
    const owner = await winner.database.deviceControl.get('device')
    release()
    await pending
    assert.equal(second.runtime.getSnapshot().phase, 'held')
    const after = await winner.database.deviceControl.get('device')
    assert.equal(after.generation, owner.generation)
    assert.equal(after.tabAttemptId, owner.tabAttemptId)
    assert.equal(after.activePartitionId, owner.activePartitionId)
    assert.equal(winner.runtime.getSnapshot().phase, 'ready')
    assert.deepEqual(await winner.database.operationJournal.toArray(), evidence.journal)
  })
}

for (const mode of ['realm', 'user', 'organization', 'account_location']) {
  for (const online of [true, false]) {
    test(`retained admission cannot cross changed ${mode} with online hint ${online}`, async (t) => {
      const { first, evidence } = await retainedReload(t)
      if (mode !== 'realm') {
        const saved = JSON.parse(first.storage.getItem('ocwp.session.v2'))
        saved.user[
          mode === 'user' ? 'user_id' : mode === 'organization' ? 'organization_id' : 'location_id'
        ] = 'changed'
        first.storage.setItem('ocwp.session.v2', JSON.stringify(saved))
      }
      const calls = []
      const second = setup(t, {
        name: first.name,
        storage: first.storage,
        online,
        server: {
          fetch: async (url) => {
            calls.push(url)
            throw new TypeError('offline')
          },
        },
        apiRealm: mode === 'realm' ? 'https://other.test/api/v1' : realm,
      })
      await second.runtime.start()
      assert.equal(second.runtime.getSnapshot().phase, 'held')
      assert.deepEqual(await second.database.deviceControl.get('device'), evidence.control)
      assert.deepEqual(await second.database.operationJournal.toArray(), evidence.journal)
      assert.deepEqual(calls, [])
    })
  }
}

for (const mode of ['user', 'admission']) {
  test(`same token/binding ${mode} replacement during unreachable preflight cannot be admitted`, async (t) => {
    const { first, evidence } = await retainedReload(t)
    let reached, release
    const barrier = new Promise((resolve) => {
      reached = resolve
    })
    const second = setup(t, {
      name: first.name,
      storage: first.storage,
      server: {
        fetch: async () => {
          reached()
          await new Promise((resolve) => {
            release = resolve
          })
          throw new TypeError('offline')
        },
      },
    })
    const pending = second.runtime.start()
    await barrier
    const changed = JSON.parse(first.storage.getItem('ocwp.session.v2'))
    if (mode === 'user') changed.user.user_id = 'B'
    else changed.admission.owner.tabAttemptId = 'replaced'
    first.storage.setItem('ocwp.session.v2', JSON.stringify(changed))
    release()
    await pending
    assert.notEqual(second.runtime.getSnapshot().phase, 'ready')
    assert.deepEqual(await second.database.operationJournal.toArray(), evidence.journal)
  })
}

test('reachable reload verifies me once and then the authoritative context', async (t) => {
  const { first } = await retainedReload(t)
  const second = setup(t, { name: first.name, storage: first.storage })
  await second.runtime.start()
  assert.equal(second.runtime.getSnapshot().phase, 'ready', second.runtime.getSnapshot().message)
  assert.equal(second.server.calls.filter((path) => path.endsWith('/auth/me')).length, 1)
  assert.ok(second.server.calls.includes('/api/v1/auth/context'))
})

test('a context network failure after successful me cannot resume pre-verification admission', async (t) => {
  const { first } = await retainedReload(t)
  const server = api(),
    original = server.fetch
  server.fetch = async (url, init) => {
    if (new URL(url).pathname.endsWith('/auth/context')) throw new TypeError('offline after me')
    return original(url, init)
  }
  const second = setup(t, { name: first.name, storage: first.storage, server })
  let resumed = false
  const resume = second.runtime.kernel.resumeOffline.bind(second.runtime.kernel)
  second.runtime.kernel.resumeOffline = (...args) => {
    resumed = true
    return resume(...args)
  }
  await second.runtime.start()
  assert.equal(second.runtime.getSnapshot().phase, 'held')
  assert.equal(resumed, false)
  second.runtime.dispose()
  const third = setup(t, { name: first.name, storage: first.storage, online: false })
  await third.runtime.start()
  assert.equal(third.runtime.getSnapshot().phase, 'held')
})

test('two cloned unreachable reloads claim exactly one owner', async (t) => {
  const { first, evidence } = await retainedReload(t)
  const server = {
    fetch: async () => {
      throw new TypeError('offline')
    },
  }
  const a = setup(t, { name: first.name, storage: first.storage, server }),
    b = setup(t, { name: first.name, storage: first.storage.clone(), server })
  await Promise.all([a.runtime.start(), b.runtime.start()])
  assert.deepEqual([a.runtime.getSnapshot().phase, b.runtime.getSnapshot().phase].sort(), [
    'held',
    'ready',
  ])
  assert.equal(
    (await a.database.deviceControl.get('device')).generation,
    evidence.control.generation + 1,
  )
  assert.deepEqual(await a.database.operationJournal.toArray(), evidence.journal)
})

test('lease expiring during unreachable preflight cannot renew its original deadline', async (t) => {
  const { first, evidence } = await retainedReload(t)
  let reached, release
  const barrier = new Promise((resolve) => {
    reached = resolve
  })
  const second = setup(t, {
    name: first.name,
    storage: first.storage,
    server: {
      fetch: async () => {
        reached()
        await new Promise((resolve) => {
          release = resolve
        })
        throw new TypeError('offline')
      },
    },
  })
  const pending = second.runtime.start()
  await barrier
  second.env.now = NOW + 3600000
  release()
  await pending
  assert.equal(second.runtime.getSnapshot().phase, 'held')
  assert.deepEqual(await second.database.deviceControl.get('device'), evidence.control)
  assert.deepEqual(await second.database.operationJournal.toArray(), evidence.journal)
})

test('organization-wide account keeps null account scope and its concrete selected workshop offline', async (t) => {
  const server = api(),
    original = server.fetch
  server.fetch = async (url, init) => {
    if (new URL(url).pathname.endsWith('/locations'))
      return response(url, {
        items: [{ location_id: 'loc', organization_id: 'org', name: 'Selected workshop' }],
        next_cursor: null,
      })
    const body = await (await original(url, init)).json()
    if (Object.hasOwn(body, 'user_id')) body.location_id = null
    const context = body.context ?? body
    if (Object.hasOwn(context, 'account_location_id')) context.account_location_id = null
    return response(url, body)
  }
  const first = setup(t, { server })
  await first.runtime.start()
  await first.runtime.login({ organization_id: 'org', username: 'A', password: 'synthetic' })
  assert.equal(first.runtime.getSnapshot().phase, 'selector')
  await first.runtime.selectWorkshop('loc')
  await until(
    () => first.runtime.getSnapshot().phase === 'ready',
    'selected baseline did not finish',
  )
  first.runtime.dispose()
  const second = setup(t, {
    name: first.name,
    storage: first.storage,
    server: {
      fetch: async () => {
        throw new TypeError('offline')
      },
    },
  })
  await second.runtime.start()
  assert.equal(second.runtime.getSnapshot().phase, 'ready', second.runtime.getSnapshot().message)
  assert.equal(second.runtime.getSnapshot().user.location_id, null)
  assert.equal(second.runtime.getSnapshot().context.accountLocationId, null)
  assert.equal(second.runtime.getSnapshot().context.selectedLocationId, 'loc')
})

test('same-token metadata replacement during awaited offline claim is not blanked by its stale catch', async (t) => {
  const { first, evidence } = await retainedReload(t)
  const second = setup(t, { name: first.name, storage: first.storage, online: false })
  let reached, release
  const barrier = new Promise((resolve) => {
    reached = resolve
  })
  const resume = second.runtime.kernel.resumeOffline.bind(second.runtime.kernel)
  second.runtime.kernel.resumeOffline = async (...args) => {
    reached()
    await new Promise((resolve) => {
      release = resolve
    })
    return resume(...args)
  }
  let held = 0
  const hold = second.runtime.held.bind(second.runtime)
  second.runtime.held = (...args) => {
    held++
    return hold(...args)
  }
  const pending = second.runtime.start()
  await barrier
  const replacement = JSON.parse(first.storage.getItem('ocwp.session.v2'))
  replacement.user.user_id = 'B'
  first.storage.setItem('ocwp.session.v2', JSON.stringify(replacement))
  release()
  await pending
  assert.equal(held, 0)
  assert.equal(second.runtime.sessionStore.getSnapshot().user.user_id, 'B')
  assert.deepEqual(await second.database.deviceControl.get('device'), evidence.control)
})

test('interrupted successful me body may resume only the unchanged previously verified lease', async (t) => {
  const { first, evidence } = await retainedReload(t)
  const second = setup(t, {
    name: first.name,
    storage: first.storage,
    server: {
      fetch: async (url) => {
        const value = new Response(
          new ReadableStream({
            start(controller) {
              controller.error(new TypeError('connection lost'))
            },
          }),
          {
            status: 200,
            headers: { 'content-type': 'application/json', 'cache-control': 'no-store' },
          },
        )
        Object.defineProperty(value, 'url', { value: url })
        return value
      },
    },
  })
  await second.runtime.start()
  assert.equal(second.runtime.getSnapshot().phase, 'ready', second.runtime.getSnapshot().message)
  assert.equal(second.runtime.getSnapshot().sync, 'offline')
  assert.deepEqual(second.runtime.getSnapshot().context, evidence.context)
  assert.deepEqual(await second.database.operationJournal.toArray(), evidence.journal)
  assert.deepEqual(await second.database.operationDelivery.toArray(), evidence.delivery)
})

for (const mode of ['user', 'admission']) {
  test(`exact refreshed snapshot survives late ${mode} replacement before ready publication`, async (t) => {
    const { first } = await retainedReload(t)
    const second = setup(t, {
      name: first.name,
      storage: first.storage,
      server: {
        fetch: async () => {
          throw new TypeError('offline')
        },
      },
    })
    const remember = second.runtime.sessionStore.remember.bind(second.runtime.sessionStore)
    second.runtime.sessionStore.remember = (...args) => {
      remember(...args)
      queueMicrotask(() => {
        const changed = JSON.parse(first.storage.getItem('ocwp.session.v2'))
        if (mode === 'user') changed.user.user_id = 'B'
        else changed.admission.owner.tabAttemptId = 'replaced'
        first.storage.setItem('ocwp.session.v2', JSON.stringify(changed))
      })
    }
    await second.runtime.start()
    assert.notEqual(second.runtime.getSnapshot().phase, 'ready')
    assert.equal(second.runtime.getSnapshot().customers.length, 0)
  })
}

test('deliberate sync after fallback remains real verification and holds unreachable retry without losing history', async (t) => {
  const { first, evidence } = await retainedReload(t)
  let calls = 0
  const second = setup(t, {
    name: first.name,
    storage: first.storage,
    server: {
      fetch: async () => {
        calls++
        throw new TypeError('offline')
      },
    },
  })
  await second.runtime.start()
  assert.equal(second.runtime.getSnapshot().phase, 'ready')
  assert.equal(second.runtime.getSnapshot().sync, 'offline')
  await second.runtime.sync()
  assert.equal(calls, 2)
  assert.equal(second.runtime.getSnapshot().phase, 'held')
  assert.equal(second.runtime.getSnapshot().customers.length, 0)
  assert.match(second.runtime.getSnapshot().message, /verificar la sesión/)
  assert.notEqual(second.runtime.getSnapshot().sync, 'synced')
  assert.deepEqual(await second.database.operationJournal.toArray(), evidence.journal)
  assert.deepEqual(await second.database.operationDelivery.toArray(), evidence.delivery)
  const retained = await second.database.accessContexts.get(evidence.control.activePartitionId)
  assert.deepEqual(retained.context, evidence.context)
  assert.equal(
    (await second.database.deviceControl.get('device')).activePartitionId,
    evidence.control.activePartitionId,
  )
  second.runtime.dispose()
  const third = setup(t, { name: first.name, storage: first.storage, online: false })
  await third.runtime.start()
  assert.equal(third.runtime.getSnapshot().phase, 'held')
  assert.deepEqual(await third.database.operationJournal.toArray(), evidence.journal)
})

test('offline reload automatically verifies and dispatches retained work when network returns without an online event', async (t) => {
  const { first, evidence } = await retainedReload(t)
  let reachable = false
  const server = first.server
  const calls = []
  const second = setup(t, {
    name: first.name,
    storage: first.storage,
    online: true,
    server: {
      fetch: async (url, init) => {
        const path = new URL(url).pathname
        calls.push(path)
        if (!reachable) throw new TypeError('unreachable')
        if (path.endsWith('/sync/mutations')) {
          return response(url, {
            results: JSON.parse(init.body).mutations.map((row) => ({
              mutation_id: row.mutation_id,
              entity_id: row.entity_id,
              status: 'applied',
              entity_version: 1,
              error_code: null,
              error_message: null,
            })),
          })
        }
        return server.fetch(url, init)
      },
    },
  })
  await second.runtime.start()
  assert.equal(second.runtime.getSnapshot().sync, 'offline')
  reachable = true
  // No reconnect/sync call and no online event: the browser hint stayed true.
  for (let i = 0; i < 175 && second.runtime.getSnapshot().sync !== 'synced'; i++)
    await new Promise((resolve) => setTimeout(resolve, 20))
  assert.equal(second.runtime.getSnapshot().sync, 'synced', JSON.stringify(calls))
  assert.deepEqual(await second.database.operationJournal.toArray(), evidence.journal)
  assert.equal((await second.database.operationDelivery.toArray())[0].state, 'applied')
  assert.deepEqual(calls.slice(0, 4), [
    '/api/v1/auth/me',
    '/api/v1/auth/me',
    '/api/v1/auth/context',
    '/api/v1/sync/mutations',
  ])
})

async function settleProbe() {
  for (let i = 0; i < 100; i++) await new Promise(setImmediate)
}
for (const mode of ['401', '403', 'malformed', 'principal'])
  test(`automatic probe ${mode} invalidates the expected offline owner without another me or dispatch`, async (t) => {
    const { first, evidence } = await retainedReload(t)
    let calls = 0
    t.mock.timers.enable({ apis: ['setTimeout'] })
    const second = setup(t, {
      name: first.name,
      storage: first.storage,
      online: false,
      server: {
        fetch: async (url) => {
          calls++
          assert.ok(url.endsWith('/auth/me'))
          if (mode === 'malformed') return response(url, {})
          if (mode === 'principal') return response(url, user('other'))
          const r = new Response(null, {
            status: Number(mode),
            headers: {
              'content-type': 'application/json',
              'cache-control': 'no-store',
            },
          })
          Object.defineProperty(r, 'url', { value: url })
          return r
        },
      },
    })
    await second.runtime.start()
    const owner = await second.database.deviceControl.get('device')
    t.mock.timers.tick(2000)
    await settleProbe()
    assert.equal(calls, 1)
    assert.equal(second.runtime.getSnapshot().phase, 'held')
    assert.deepEqual(await second.database.operationJournal.toArray(), evidence.journal)
    assert.deepEqual(await second.database.operationDelivery.toArray(), evidence.delivery)
    assert.ok((await second.database.deviceControl.get('device')).generation > owner.generation)
    second.runtime.dispose()
    const third = setup(t, { name: first.name, storage: first.storage, online: false })
    await third.runtime.start()
    assert.equal(third.runtime.getSnapshot().phase, 'held')
  })

test('unreachable automatic probes preserve exact owner, admission, deadline and pending work', async (t) => {
  const { first, evidence } = await retainedReload(t)
  let calls = 0
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const second = setup(t, {
    name: first.name,
    storage: first.storage,
    online: false,
    server: {
      fetch: async () => {
        calls++
        throw new TypeError('unreachable')
      },
    },
  })
  await second.runtime.start()
  const session = structuredClone(second.runtime.sessionStore.getSnapshot())
  const owner = await second.database.deviceControl.get('device')
  for (const delay of [2000, 4000, 8000]) {
    t.mock.timers.tick(delay)
    await settleProbe()
  }
  assert.equal(calls, 3)
  assert.equal(second.runtime.getSnapshot().phase, 'ready')
  assert.equal(second.runtime.getSnapshot().sync, 'offline')
  assert.deepEqual(await second.database.deviceControl.get('device'), owner)
  assert.deepEqual(second.runtime.sessionStore.getSnapshot(), session)
  assert.deepEqual(second.runtime.getSnapshot().context, evidence.context)
  assert.deepEqual(await second.database.operationJournal.toArray(), evidence.journal)
  assert.deepEqual(await second.database.operationDelivery.toArray(), evidence.delivery)
})

for (const change of ['logout', 'metadata', 'takeover', 'expiry', 'rollback'])
  test(`late automatic probe cannot reactivate after ${change}`, async (t) => {
    const { first, evidence } = await retainedReload(t)
    let release,
      calls = 0,
      signal
    t.mock.timers.enable({ apis: ['setTimeout'] })
    const second = setup(t, {
      name: first.name,
      storage: first.storage,
      online: false,
      server: {
        fetch: async (url, init) => {
          calls++
          signal = init.signal
          await new Promise((resolve) => {
            release = resolve
          })
          return response(url, user())
        },
      },
    })
    await second.runtime.start()
    t.mock.timers.tick(2000)
    await settleProbe()
    assert.equal(calls, 1)
    if (change === 'logout') await second.runtime.logout()
    if (change === 'metadata')
      second.runtime.sessionStore.setUser({ ...user(), display_name: 'replacement' })
    if (change === 'takeover')
      await second.runtime.kernel.beginVerification('other-tab', () => true)
    if (change === 'expiry') second.env.now = NOW + 3600000
    if (change === 'rollback') second.env.now = NOW - 1
    const session = structuredClone(second.runtime.sessionStore.getSnapshot())
    release()
    await settleProbe()
    assert.equal(calls, 1)
    assert.deepEqual(second.runtime.sessionStore.getSnapshot(), session)
    assert.notEqual(second.runtime.getSnapshot().sync, 'synced')
    assert.deepEqual(await second.database.operationJournal.toArray(), evidence.journal)
    assert.deepEqual(await second.database.operationDelivery.toArray(), evidence.delivery)
    if (change !== 'metadata') assert.notEqual(second.runtime.getSnapshot().phase, 'ready')
    if (change === 'logout') assert.equal(signal.aborted, true)
  })

for (const changedAuthority of [false, true])
  test(`successful automatic verification overrides stale false hint before ${changedAuthority ? 'new baseline' : 'equivalent context'} dispatch`, async (t) => {
    const { first, evidence } = await retainedReload(t)
    const calls = []
    t.mock.timers.enable({ apis: ['setTimeout'] })
    const second = setup(t, {
      name: first.name,
      storage: first.storage,
      online: false,
      server: {
        fetch: async (url, init) => {
          const path = new URL(url).pathname
          calls.push(path)
          if (path.endsWith('/sync/mutations'))
            return response(url, {
              results: JSON.parse(init.body).mutations.map((row) => ({
                mutation_id: row.mutation_id,
                entity_id: row.entity_id,
                status: 'applied',
                entity_version: 1,
                error_code: null,
                error_message: null,
              })),
            })
          const original = await first.server.fetch(url, init)
          if (!changedAuthority) return original
          const body = JSON.stringify(await original.json())
            .replaceAll(epoch, 'b'.repeat(43))
            .replaceAll(baselineId, '0199ba00-0000-7000-8000-000000000003')
          return response(url, JSON.parse(body))
        },
      },
    })
    await second.runtime.start()
    t.mock.timers.tick(2000)
    for (let i = 0; i < 20; i++) {
      await settleProbe()
      t.mock.timers.tick(0)
      if (second.runtime.getSnapshot().sync === 'synced') break
    }
    assert.equal(second.env.online, false)
    assert.equal(second.runtime.getSnapshot().phase, 'ready')
    assert.equal(second.runtime.getSnapshot().sync, 'synced', JSON.stringify(calls))
    assert.equal((await second.database.operationDelivery.toArray())[0].state, 'applied')
    assert.deepEqual(await second.database.operationJournal.toArray(), evidence.journal)
    assert.ok(calls.indexOf('/api/v1/auth/context') < calls.indexOf('/api/v1/sync/mutations'))
    assert.equal(calls.includes('/api/v1/sync/baselines/start'), changedAuthority)
  })

test('duplicate offline notifications preserve the probe backoff and original admission', async (t) => {
  const { first } = await retainedReload(t)
  let calls = 0
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const second = setup(t, {
    name: first.name,
    storage: first.storage,
    online: false,
    server: {
      fetch: async () => {
        calls++
        throw new TypeError('unreachable')
      },
    },
  })
  await second.runtime.start()
  const session = structuredClone(second.runtime.sessionStore.getSnapshot())
  t.mock.timers.tick(1000)
  await second.runtime.offline()
  t.mock.timers.tick(1000)
  await settleProbe()
  assert.equal(calls, 1)
  t.mock.timers.tick(2000)
  await second.runtime.offline()
  await settleProbe()
  assert.equal(calls, 1)
  t.mock.timers.tick(2000)
  await settleProbe()
  assert.equal(calls, 2)
  assert.deepEqual(second.runtime.sessionStore.getSnapshot(), session)
})

test('automatic account-scope change cannot silently select a different workshop', async (t) => {
  const { first, evidence } = await retainedReload(t)
  t.mock.timers.enable({ apis: ['setTimeout'] })
  let calls = 0
  const second = setup(t, {
    name: first.name,
    storage: first.storage,
    online: false,
    server: {
      fetch: async (url) => {
        calls++
        return response(url, { ...user(), location_id: 'other' })
      },
    },
  })
  await second.runtime.start()
  t.mock.timers.tick(2000)
  await settleProbe()
  assert.equal(calls, 1)
  assert.equal(second.runtime.getSnapshot().phase, 'held')
  assert.equal(second.runtime.getSnapshot().selectedLocationId, null)
  assert.deepEqual(await second.database.operationJournal.toArray(), evidence.journal)
})

for (const replacement of ['user', 'admission'])
  test(`online source cannot start a probe after same-token ${replacement} replacement`, async (t) => {
    const first = setup(t)
    await first.runtime.start()
    await login(first.runtime)
    await until(() => first.runtime.getSnapshot().sync === 'synced', 'initial sync')
    const before = first.server.calls.length
    if (replacement === 'user')
      first.runtime.sessionStore.setUser({ ...user(), organization_id: 'foreign' })
    else {
      const session = first.runtime.sessionStore.getSnapshot()
      first.runtime.sessionStore.remember(
        { ...session.admission, datasetIncarnation: '0199ba00-0000-7000-8000-000000000009' },
        session.token,
      )
    }
    first.env.online = false
    await first.runtime.offline()
    await new Promise((resolve) => setTimeout(resolve, 2100))
    await settleProbe()
    assert.equal(first.server.calls.length, before)
  })

for (const change of ['user', 'admission'])
  test(`automatic verification preserves exact ${change} snapshot through post-remember publication`, async (t) => {
    const { first } = await retainedReload(t)
    t.mock.timers.enable({ apis: ['setTimeout'] })
    const second = setup(t, {
      name: first.name,
      storage: first.storage,
      online: false,
      server: first.server,
    })
    await second.runtime.start()
    const remember = second.runtime.sessionStore.remember.bind(second.runtime.sessionStore)
    second.runtime.sessionStore.remember = (...args) => {
      remember(...args)
      queueMicrotask(() => {
        const replacement = JSON.parse(first.storage.getItem('ocwp.session.v2'))
        if (change === 'user') replacement.user = user('B')
        else replacement.admission.owner.tabAttemptId = 'replacement'
        first.storage.setItem('ocwp.session.v2', JSON.stringify(replacement))
      })
    }
    t.mock.timers.tick(2000)
    await settleProbe()
    assert.notEqual(second.runtime.getSnapshot().phase, 'ready')
    assert.equal(second.runtime.getSnapshot().customers.length, 0)
    if (change === 'user') assert.equal(second.runtime.sessionStore.getSnapshot().user.user_id, 'B')
    else
      assert.equal(
        second.runtime.sessionStore.getSnapshot().admission.owner.tabAttemptId,
        'replacement',
      )
  })

test('changed-authority baseline network failure under false hint cannot resurrect old offline admission', async (t) => {
  const { first, evidence } = await retainedReload(t)
  const calls = []
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const second = setup(t, {
    name: first.name,
    storage: first.storage,
    online: false,
    server: {
      fetch: async (url, init) => {
        calls.push(new URL(url).pathname)
        if (url.endsWith('/sync/baselines/start')) throw new TypeError('unreachable')
        const original = await first.server.fetch(url, init)
        return response(
          url,
          JSON.parse(JSON.stringify(await original.json()).replaceAll(epoch, 'b'.repeat(43))),
        )
      },
    },
  })
  await second.runtime.start()
  t.mock.timers.tick(2000)
  await settleProbe()
  assert.equal(second.runtime.getSnapshot().phase, 'baseline')
  second.env.now += 3000
  t.mock.timers.tick(3000)
  await settleProbe()
  assert.equal(second.runtime.getSnapshot().phase, 'held')
  assert.deepEqual(calls, [
    '/api/v1/auth/me',
    '/api/v1/auth/context',
    '/api/v1/sync/baselines/start',
  ])
  assert.deepEqual(await second.database.operationJournal.toArray(), evidence.journal)
  second.runtime.dispose()
  const third = setup(t, { name: first.name, storage: first.storage, online: false })
  await third.runtime.start()
  assert.equal(third.runtime.getSnapshot().phase, 'held')
})

test('native reconnect cancels a pending probe and its late completion cannot verify the new owner again', async (t) => {
  const { first, evidence } = await retainedReload(t)
  let release,
    probeSignal,
    me = 0
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const second = setup(t, {
    name: first.name,
    storage: first.storage,
    online: false,
    server: {
      fetch: async (url, init) => {
        if (url.endsWith('/auth/me') && ++me === 1) {
          probeSignal = init.signal
          await new Promise((resolve) => {
            release = resolve
          })
        }
        return first.server.fetch(url, init)
      },
    },
  })
  await second.runtime.start()
  t.mock.timers.tick(2000)
  await settleProbe()
  assert.equal(me, 1)
  second.env.online = true
  await second.runtime.reconnect()
  assert.equal(probeSignal.aborted, true)
  const owner = await second.database.deviceControl.get('device')
  release()
  await settleProbe()
  assert.equal(me, 2)
  assert.deepEqual(await second.database.deviceControl.get('device'), owner)
  assert.equal(second.runtime.getSnapshot().phase, 'ready')
  assert.deepEqual(await second.database.operationJournal.toArray(), evidence.journal)
})

test('disconnect during preference copy retains offline admission and probes without destructive automatic sync', async (t) => {
  const { first, evidence } = await retainedReload(t)
  let reachable = true
  const calls = []
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const second = setup(t, {
    name: first.name,
    storage: first.storage,
    online: false,
    server: {
      fetch: async (url, init) => {
        calls.push(new URL(url).pathname)
        if (!reachable) throw new TypeError('unreachable')
        return first.server.fetch(url, init)
      },
    },
  })
  await second.runtime.start()
  let reached,
    release,
    once = false
  const barrier = new Promise((resolve) => {
    reached = resolve
  })
  second.runtime.options.factory = {
    open(name) {
      if (once) return indexedDB.open(name)
      once = true
      const request = { transaction: { abort() {} } }
      queueMicrotask(() => {
        request.onupgradeneeded()
        release = () => request.onerror()
        reached()
      })
      return request
    },
  }
  second.env.online = true
  t.mock.timers.tick(2000)
  await barrier
  reachable = false
  await second.runtime.offline()
  assert.equal(second.runtime.getSnapshot().sync, 'offline')
  release()
  await settleProbe()
  t.mock.timers.tick(0)
  await settleProbe()
  assert.equal(second.runtime.getSnapshot().phase, 'ready')
  assert.equal(second.runtime.getSnapshot().sync, 'offline')
  assert.deepEqual(calls, ['/api/v1/auth/me', '/api/v1/auth/context'])
  const session = structuredClone(second.runtime.sessionStore.getSnapshot())
  t.mock.timers.tick(2000)
  await settleProbe()
  assert.deepEqual(calls, ['/api/v1/auth/me', '/api/v1/auth/context', '/api/v1/auth/me'])
  assert.equal(second.runtime.getSnapshot().phase, 'ready')
  assert.equal(second.runtime.getSnapshot().sync, 'offline')
  assert.deepEqual(second.runtime.sessionStore.getSnapshot(), session)
  assert.deepEqual(await second.database.operationJournal.toArray(), evidence.journal)
})

test('organization-wide account retains concrete workshop through automatic revalidation', async (t) => {
  const server = api(),
    original = server.fetch
  server.fetch = async (url, init) => {
    if (new URL(url).pathname.endsWith('/locations'))
      return response(url, {
        items: [{ location_id: 'loc', organization_id: 'org', name: 'Selected workshop' }],
        next_cursor: null,
      })
    const body = await (await original(url, init)).json()
    if (Object.hasOwn(body, 'user_id')) body.location_id = null
    const context = body.context ?? body
    if (Object.hasOwn(context, 'account_location_id')) context.account_location_id = null
    return response(url, body)
  }
  const first = setup(t, { server })
  await first.runtime.start()
  await first.runtime.login({ organization_id: 'org', username: 'A', password: 'synthetic' })
  assert.equal(first.runtime.getSnapshot().phase, 'selector')
  await first.runtime.selectWorkshop('loc')
  await until(() => first.runtime.getSnapshot().sync === 'synced', 'initial selected sync')
  first.env.online = false
  await first.runtime.offline()
  first.runtime.dispose()
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const second = setup(t, { name: first.name, storage: first.storage, server, online: false })
  await second.runtime.start()
  t.mock.timers.tick(2000)
  for (let i = 0; i < 20; i++) {
    await settleProbe()
    t.mock.timers.tick(0)
    if (second.runtime.getSnapshot().sync === 'synced') break
  }
  assert.equal(second.runtime.getSnapshot().sync, 'synced')
  assert.equal(second.runtime.getSnapshot().user.location_id, null)
  assert.equal(second.runtime.getSnapshot().context.accountLocationId, null)
  assert.equal(second.runtime.getSnapshot().context.selectedLocationId, 'loc')
})

test('account refresh and name-only rebind preserve live operational owner and admission', async (t) => {
  const f = setup(t)
  await login(f.runtime)
  const before = f.runtime.getSnapshot(),
    saved = f.runtime.sessionStore.getSnapshot()
  await f.runtime.verifyAccount()
  assert.equal(f.runtime.getSnapshot().identityKey, before.identityKey)
  assert.deepEqual(f.runtime.sessionStore.getSnapshot().admission, saved.admission)
  const capture = f.runtime.captureAccount()
  f.runtime.updateAccountName(capture, 'New display name')
  assert.equal(f.runtime.getSnapshot().user.display_name, 'New display name')
  assert.deepEqual(f.runtime.sessionStore.getSnapshot().admission, saved.admission)
  await f.runtime.refresh()
  assert.equal(f.runtime.getSnapshot().phase, 'ready')
  assert.equal(f.runtime.getSnapshot().identityKey, before.identityKey)
})

test('self-command lock failure sends no command and leaves operational data blank', async (t) => {
  const f = setup(t)
  await login(f.runtime)
  await f.runtime.verifyAccount()
  const capture = f.runtime.captureAccount()
  f.runtime.kernel.lockContext = async () => {
    throw new Error('synthetic storage failure')
  }
  let dispatched = false
  await assert.rejects(async () => {
    await f.runtime.suspendAccountCommand(capture)
    dispatched = true
  })
  assert.equal(dispatched, false)
  assert.deepEqual(f.runtime.getSnapshot().customers, [])
  assert.notEqual(f.runtime.getSnapshot().phase, 'ready')
  assert.equal(capture.isCurrent(), false)
})

test('replacement login during self lock invalidates dedicated command before dispatch', async (t) => {
  const f = setup(t)
  await login(f.runtime)
  await f.runtime.verifyAccount()
  const lock = f.runtime.kernel.lockContext.bind(f.runtime.kernel)
  let release
  f.runtime.kernel.lockContext = async (ticket) => {
    await lock(ticket)
    await new Promise((r) => {
      release = r
    })
  }
  const pending = f.runtime.suspendAccountCommand(f.runtime.captureAccount())
  await until(() => !!release, 'lock did not suspend')
  await login(f.runtime, 'B')
  release()
  await assert.rejects(pending)
  assert.equal(f.runtime.getSnapshot().user.user_id, 'B')
  assert.equal(f.runtime.getSnapshot().phase, 'ready')
})

test('cross-account transition to account-only identity locks previous owner and removes old data', async (t) => {
  const server = api(),
    original = server.fetch
  server.fetch = async (url, init) => {
    if (url.endsWith('/auth/me') && init.headers.Authorization === 'Bearer token-B')
      return response(url, { ...user('B'), capabilities: [] })
    return original(url, init)
  }
  const f = setup(t, { server })
  await login(f.runtime)
  const oldAdmission = f.runtime.sessionStore.getSnapshot().admission
  await f.runtime.login({ organization_id: 'org', username: 'B', password: 'synthetic' })
  assert.equal(f.runtime.getSnapshot().phase, 'selector')
  assert.equal(f.runtime.getSnapshot().context, null)
  assert.deepEqual(f.runtime.getSnapshot().customers, [])
  assert.equal(f.runtime.getAccountSnapshot().user.user_id, 'B')
  assert.equal(f.runtime.sessionStore.getSnapshot().admission, null)
  const control = await f.database.deviceControl.get('device')
  assert.equal(control.state, 'LOCKED')
  assert.ok(control.generation > oldAdmission.owner.deviceGeneration)
})

test('connected account authority change retires old offline admission without opening operational scope', async (t) => {
  const server = api(),
    original = server.fetch
  let changed = false
  server.fetch = async (url, init) =>
    changed && url.endsWith('/auth/me')
      ? response(url, { ...user(), capabilities: [] })
      : original(url, init)
  const f = setup(t, { server })
  await login(f.runtime)
  changed = true
  await f.runtime.verifyAccount()
  assert.equal(f.runtime.getAccountSnapshot().phase, 'connected')
  assert.deepEqual(f.runtime.getAccountSnapshot().user.capabilities, [])
  assert.equal(f.runtime.getSnapshot().phase, 'held')
  assert.deepEqual(f.runtime.getSnapshot().customers, [])
  assert.equal(f.runtime.sessionStore.getSnapshot().admission, null)
  assert.equal((await f.database.deviceControl.get('device')).state, 'LOCKED')
})

test('offline during changed-authority lock cannot establish fresh connected account', async (t) => {
  const server = api(),
    original = server.fetch
  let changed = false
  server.fetch = async (url, init) =>
    changed && url.endsWith('/auth/me')
      ? response(url, { ...user(), capabilities: [] })
      : original(url, init)
  const f = setup(t, { server })
  await login(f.runtime)
  changed = true
  const lock = f.runtime.kernel.lockContext.bind(f.runtime.kernel)
  let release
  f.runtime.kernel.lockContext = async (ticket) => {
    await lock(ticket)
    await new Promise((r) => {
      release = r
    })
  }
  const pending = f.runtime.verifyAccount()
  await until(() => !!release, 'authority change did not lock')
  await f.runtime.offline()
  release()
  await pending
  assert.notEqual(f.runtime.getAccountSnapshot().phase, 'connected')
  assert.throws(() => f.runtime.captureAccount())
})

test('account verification cannot rebind a previously stale operational source after same-token authority replacement', async (t) => {
  const server = api(),
    original = server.fetch
  let changed = false
  server.fetch = async (url, init) =>
    changed && url.endsWith('/auth/me')
      ? response(url, { ...user(), capabilities: [] })
      : original(url, init)
  const f = setup(t, { server })
  await login(f.runtime)
  changed = true
  f.runtime.sessionStore.setUser({ ...user(), capabilities: [] })
  await f.runtime.verifyAccount()
  assert.notEqual(f.runtime.getSnapshot().phase, 'ready')
  assert.notEqual(f.runtime.getAccountSnapshot().phase, 'connected')
  assert.deepEqual(f.runtime.getSnapshot().customers, [])
})
function brandedApi(grants = ['branding.read'], handle) {
  const server = api(),
    original = server.fetch
  server.fetch = async (url, init) => {
    if (url.endsWith('/branding')) {
      server.calls.push(new URL(url).pathname)
      if (handle) return handle(url, init)
      return response(url, {
        schema_version: 1,
        organization_id: 'org',
        location_id: 'loc',
        dataset_incarnation: incarnation,
        version: 1,
        display_name: 'Shared workshop',
        palette_id: 'arcilla',
        logo_state: 'none',
        logo: null,
        logo_diagnostic: null,
        updated_at: new Date(NOW).toISOString(),
        updated_by: 'A',
      })
    }
    const value = await (await original(url, init)).json()
    if (Array.isArray(value.capabilities)) value.capabilities.push(...grants)
    if (value.context?.capabilities) value.context.capabilities.push(...grants)
    return response(url, value)
  }
  return server
}
test('admitted runtime fetches shared brand and reloads exact cache offline without new journal entries', async (t) => {
  const first = setup(t, { server: brandedApi() })
  await login(first.runtime)
  await until(
    () => first.runtime.branding.getSnapshot().profile?.version === 1,
    'branding not published',
  )
  assert.equal(first.runtime.branding.getSnapshot().profile.display_name, 'Shared workshop')
  assert.equal(await first.database.brandingSnapshots.count(), 1)
  assert.equal(await first.database.operationJournal.count(), 0)
  first.runtime.dispose()
  const second = setup(t, {
    name: first.name,
    storage: first.storage,
    online: false,
    server: brandedApi(),
  })
  await second.runtime.start()
  await until(
    () => second.runtime.branding.getSnapshot().profile?.version === 1,
    'offline branding not restored',
  )
  assert.equal(second.runtime.branding.getSnapshot().cached, true)
  assert.equal(second.server.calls.length, 0)
  const logout = second.runtime.logout()
  assert.equal(second.runtime.branding.getSnapshot().profile, null)
  await logout
})
test('runtime read requires explicit literal, and held lease hides previously accepted branding', async (t) => {
  for (const grants of [[], ['branding.write']]) {
    const f = setup(t, { server: brandedApi(grants) })
    await login(f.runtime)
    assert.equal(f.runtime.branding.getSnapshot().profile, null)
    assert.equal(
      f.server.calls.some((path) => path.endsWith('/branding')),
      false,
    )
    f.runtime.dispose()
  }
  const f = setup(t, { server: brandedApi() })
  await login(f.runtime)
  await until(() => f.runtime.branding.getSnapshot().profile !== null, 'branding not published')
  f.env.now = NOW + 3600000
  await f.runtime.checkLease()
  assert.equal(f.runtime.branding.getSnapshot().profile, null)
  assert.equal(f.runtime.getSnapshot().phase, 'held')
})
test('late branding body after logout cannot publish or acquire a new cache admission', async (t) => {
  let release,
    started = false
  const f = setup(t, {
    server: brandedApi(['branding.read'], (url) => {
      started = true
      return new Promise((resolve) => {
        release = () =>
          resolve(
            response(url, {
              schema_version: 1,
              organization_id: 'org',
              location_id: 'loc',
              dataset_incarnation: incarnation,
              version: 0,
              display_name: 'Taller',
              palette_id: 'bosque',
              logo_state: 'none',
              logo: null,
              logo_diagnostic: null,
              updated_at: null,
              updated_by: null,
            }),
          )
      })
    }),
  })
  await login(f.runtime)
  await until(() => started, 'branding request absent')
  await f.runtime.logout()
  release()
  await new Promise((resolve) => setTimeout(resolve, 20))
  assert.equal(f.runtime.branding.getSnapshot().profile, null)
  assert.equal(await f.database.brandingSnapshots.count(), 0)
})
test('current editor403 retires operational branding admission and cannot republish cached bytes offline', async (t) => {
  const f = setup(t, { server: brandedApi() })
  await login(f.runtime)
  await until(() => f.runtime.branding.getSnapshot().profile !== null, 'brand missing')
  await f.runtime.verifyAccount()
  const captured = f.runtime.captureAccount()
  f.runtime.invalidateBrandingAccount(captured, 403)
  assert.equal(f.runtime.getSnapshot().phase, 'held')
  assert.equal(f.runtime.branding.getSnapshot().profile, null)
  await f.runtime.offline()
  await f.runtime.branding.refresh(true)
  assert.equal(f.runtime.branding.getSnapshot().profile, null)
  await new Promise((resolve) => setTimeout(resolve, 10))
  f.runtime.dispose()
  const reload = setup(t, { name: f.name, storage: f.storage, online: false, server: brandedApi() })
  await reload.runtime.start()
  await reload.runtime.branding.refresh(true)
  assert.notEqual(reload.runtime.getSnapshot().phase, 'ready')
  assert.equal(reload.runtime.branding.getSnapshot().profile, null)
})

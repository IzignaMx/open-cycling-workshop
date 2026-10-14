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
  } = {},
) {
  const env = { online, now },
    database = createKernelDatabase(name),
    runtime = new WorkshopController({
      apiRealm: realm,
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

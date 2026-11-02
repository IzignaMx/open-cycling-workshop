import 'fake-indexeddb/auto'
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

export {
  Storage,
  NOW,
  realm,
  epoch,
  incarnation,
  baselineId,
  response,
  user,
  wire,
  customer,
  api,
  until,
  setup,
  login,
}

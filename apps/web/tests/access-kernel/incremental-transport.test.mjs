import test from 'node:test'
import assert from 'node:assert/strict'
import {
  createIncrementalTransport,
  IncrementalTransportError,
} from '../../.tmp-kernel/src/access-kernel/incremental-transport.js'
const now = Date.parse('2026-10-14T10:00:00Z'),
  realm = 'https://example.test/api/v1'
const context = {
  protocol: 1,
  principal: { apiRealm: realm, organizationId: 'org', userId: 'A' },
  accountLocationId: 'loc',
  selectedLocationId: 'loc',
  capabilities: ['customers.read', 'sync.pull'],
  authorizationEpoch: 'a'.repeat(43),
  policyRevision: 'ocwp-access-baseline-2',
  datasetIncarnation: '0199ba00-0000-7000-8000-000000000001',
  verifiedAt: new Date(now).toISOString(),
  offlineUntil: new Date(now + 3600000).toISOString(),
  snapshotProtocol: 'baseline-v1',
}
const identity = {
  ...context.principal,
  selectedLocationId: 'loc',
  deviceGeneration: 1,
  tabAttemptId: 'tab',
  sessionHandle: 'session',
}
const page = () => ({
  protocol: 1,
  baseline_id: null,
  authorization_epoch: context.authorizationEpoch,
  predecessor: 'old',
  continuation: 'new',
  page_id: 'page',
  records: [],
  phase: 'complete',
  completion: {
    baseline_id: null,
    authorization_epoch: context.authorizationEpoch,
    checkpoint: 'new',
  },
})
const request = () => ({
  body: '{"continuation":"old","protocol":1}',
  identity: { ...identity },
  bearerToken: 'token-A',
  isCurrent: () => true,
  binding: { context: structuredClone(context), predecessor: 'old' },
})
function response(body = page(), status = 200) {
  const r = new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json', 'cache-control': 'no-store' },
  })
  Object.defineProperty(r, 'url', { value: `${realm}/sync/deltas/page`, configurable: true })
  return r
}
const setup = (fetch) => createIncrementalTransport({ apiRealm: realm, fetch, now: () => now })
test('incremental transport captures exact credential/body/authority before await and hardens destination', async () => {
  let finish, seen
  const t = setup((url, init) => {
      seen = { url, init }
      return new Promise((r) => {
        finish = r
      })
    }),
    input = request(),
    pending = t.request(input)
  input.bearerToken = 'token-B'
  input.identity.userId = 'B'
  input.binding.context.principal.userId = 'B'
  input.body = 'changed'
  finish(response())
  assert.equal((await pending).continuation, 'new')
  assert.equal(seen.init.headers.Authorization, 'Bearer token-A')
  assert.equal(seen.init.body, '{"continuation":"old","protocol":1}')
  assert.equal(seen.url, `${realm}/sync/deltas/page`)
  for (const [key, value] of Object.entries({
    cache: 'no-store',
    redirect: 'error',
    credentials: 'omit',
    referrerPolicy: 'no-referrer',
  }))
    assert.equal(seen.init[key], value)
})
for (const change of [
  (r) => {
    r.binding.predecessor = 'other'
  },
  (r) => {
    r.identity.apiRealm = 'https://evil.test'
  },
  (r) => {
    r.binding.context.snapshotProtocol = null
  },
])
  test('invalid input emits no request', async () => {
    let calls = 0
    const t = setup(async () => {
        calls++
        return response()
      }),
      r = request()
    change(r)
    await assert.rejects(t.request(r))
    assert.equal(calls, 0)
  })
test('stale response cancels body and cannot publish', async () => {
  let finish,
    cancelled = false
  const t = setup(
      () =>
        new Promise((r) => {
          finish = r
        }),
    ),
    pending = t.request(request())
  t.invalidate()
  const r = response()
  Object.defineProperty(r, 'body', {
    value: new ReadableStream({
      cancel() {
        cancelled = true
      },
    }),
  })
  finish(r)
  await assert.rejects(pending, (e) => e.code === 'stale_request')
  assert.equal(cancelled, true)
})
test('null incremental parser cannot silently accept initial baseline responses', async () => {
  const p = page()
  p.baseline_id = '00000000-0000-0000-0000-000000000001'
  await assert.rejects(
    setup(async () => response(p)).request(request()),
    (e) => e.code === 'invalid_response',
  )
})
test('closed status paired errors expose only fixed code and bounded retry metadata', async () => {
  const body = {
    error: {
      code: 'checkpoint_expired',
      message: 'PRIVATE',
      details: { secret: 'PRIVATE' },
      request_id: 'trace',
    },
  }
  await assert.rejects(
    setup(async () => response(body, 410)).request(request()),
    (e) =>
      e instanceof IncrementalTransportError &&
      e.code === 'checkpoint_expired' &&
      !JSON.stringify(e).includes('PRIVATE'),
  )
  for (const b of [
    { ...body, extra: true },
    { error: { ...body.error, extra: true } },
    { error: { ...body.error, code: 'network_error' } },
  ])
    await assert.rejects(
      setup(async () => response(b, 410)).request(request()),
      (e) => e.code === 'invalid_response',
    )
})
test('oversized streamed response is rejected and canceled before parsing', async () => {
  let cancelled = false
  const r = response()
  Object.defineProperty(r, 'body', {
    value: new ReadableStream({
      start(c) {
        c.enqueue(new Uint8Array(1048577))
      },
      cancel() {
        cancelled = true
      },
    }),
  })
  await assert.rejects(
    setup(async () => r).request(request()),
    (e) => e.code === 'invalid_response',
  )
  assert.equal(cancelled, true)
})

test('unrecognized validation detail shape is not treated as a typed request refusal', async () => {
  await assert.rejects(
    setup(async () => response({ detail: [{ secret: 'PRIVATE' }] }, 422)).request(request()),
    (error) => error.code === 'invalid_response',
  )
})

test('unexpected successful status is rejected instead of treated as the page contract', async () => {
  await assert.rejects(
    setup(async () => response(page(), 201)).request(request()),
    (error) => error.code === 'invalid_response',
  )
})

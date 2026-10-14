import test from 'node:test'
import assert from 'node:assert/strict'
import {
  createBaselineTransport,
  readBoundedBaselineJson,
  BaselineTransportError,
} from '../../.tmp-kernel/src/access-kernel/baseline-transport.js'
const encoder = new TextEncoder()
const realm = 'https://example.test/api/v1',
  now = Date.parse('2026-10-14T10:00:00Z'),
  baselineId = '0199ba00-0000-7000-8000-000000000001'
const identity = () => ({
  apiRealm: realm,
  organizationId: 'org',
  userId: 'A',
  selectedLocationId: 'loc',
  deviceGeneration: 1,
  tabAttemptId: 'tab',
  sessionHandle: 'session-A',
})
const context = () => ({
  protocol: 1,
  principal: { apiRealm: realm, organizationId: 'org', userId: 'A' },
  accountLocationId: 'loc',
  selectedLocationId: 'loc',
  capabilities: ['customers.read'],
  authorizationEpoch: 'a'.repeat(43),
  policyRevision: 'ocwp-access-baseline-2',
  datasetIncarnation: '0199ba00-0000-7000-8000-000000000001',
  verifiedAt: '2026-10-14T10:00:00.000Z',
  offlineUntil: '2026-10-14T11:00:00.000Z',
  snapshotProtocol: null,
})
const body = () => ({
  protocol: 1,
  baseline_id: baselineId,
  authorization_epoch: 'a'.repeat(43),
  predecessor: 'previous',
  continuation: 'next',
})
function response(bytes = encoder.encode(JSON.stringify(body())), overrides = {}) {
  const r = new Response(bytes, {
    headers: { 'content-type': 'application/json', 'cache-control': 'no-store' },
  })
  Object.defineProperty(r, 'url', { value: `${realm}/sync/baselines/finalize`, configurable: true })
  return Object.assign(r, overrides)
}
function request(overrides = {}) {
  const i = identity()
  return {
    kind: 'finalize',
    body: '{"protocol":1,"continuation":"previous"}',
    identity: i,
    bearerToken: 'token-A',
    isCurrent: () => true,
    binding: { identity: i, context: context(), baselineId, predecessor: 'previous' },
    ...overrides,
  }
}
const setup = (fetch) => createBaselineTransport({ apiRealm: realm, fetch, now: () => now })
test('captured exact URL, bearer and request use hardened fetch options', async () => {
  let seen
  const result = await setup(async (url, options) => {
    seen = { url, options }
    return response()
  }).request(request())
  assert.equal(result.continuation, 'next')
  assert.equal(seen.url, `${realm}/sync/baselines/finalize`)
  assert.deepEqual(seen.options, {
    method: 'POST',
    headers: {
      Authorization: 'Bearer token-A',
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    body: '{"protocol":1,"continuation":"previous"}',
    cache: 'no-store',
    redirect: 'error',
    credentials: 'omit',
    referrerPolicy: 'no-referrer',
  })
})
test('body, bearer, identity and binding are copied before first await', async () => {
  let finish
  const r = request()
  const adapter = setup(async () => new Promise((resolve) => (finish = resolve)))
  const pending = adapter.request(r)
  r.bearerToken = 'token-B'
  r.identity.userId = 'B'
  r.binding.context.principal.userId = 'B'
  r.body = 'bad'
  finish(response())
  assert.equal((await pending).continuation, 'next')
})
test('changed current identity and explicit invalidation reject late results', async () => {
  for (const mode of ['current', 'invalidate']) {
    let finish,
      current = true
    const adapter = setup(async () => new Promise((resolve) => (finish = resolve)))
    const pending = adapter.request(request({ isCurrent: () => current }))
    if (mode === 'current') current = false
    else adapter.invalidate()
    finish(response())
    await assert.rejects(
      pending,
      (e) => e instanceof BaselineTransportError && e.code === 'stale_request',
    )
  }
})
test('wrong request binding is rejected before fetch', async () => {
  let calls = 0
  const adapter = setup(async () => {
    calls++
    return response()
  })
  const r = request()
  r.binding.predecessor = 'other'
  await assert.rejects(adapter.request(r))
  assert.equal(calls, 0)
})
test('fatal decoder handles split multibyte UTF8 and rejects malformed/truncated input', async () => {
  const bytes = encoder.encode('{"value":"🚲"}')
  const stream = new ReadableStream({
    start(c) {
      for (const byte of bytes) c.enqueue(Uint8Array.of(byte))
      c.close()
    },
  })
  assert.deepEqual(await readBoundedBaselineJson(new Response(stream)), { value: '🚲' })
  for (const bytes of [
    Uint8Array.of(0xff),
    Uint8Array.of(0x22, 0xf0, 0x9f),
    encoder.encode('{invalid'),
  ])
    await assert.rejects(readBoundedBaselineJson(new Response(bytes)))
})
for (const length of [null, '1', '1048577'])
  test(`stream cap enforces dishonest/missing Content-Length ${length}`, async () => {
    let cancelled = false
    const stream = new ReadableStream({
      start(c) {
        c.enqueue(new Uint8Array(600000))
        c.enqueue(new Uint8Array(600000))
      },
      cancel() {
        cancelled = true
      },
    })
    const headers = new Headers()
    if (length !== null) headers.set('content-length', length)
    await assert.rejects(readBoundedBaselineJson(new Response(stream, { headers })))
    assert.equal(cancelled, true)
  })
test('exact byte limit accepts envelope at cap and rejects extra byte', async () => {
  const at = '"' + 'x'.repeat(1048574) + '"'
  assert.equal((await readBoundedBaselineJson(new Response(at))).length, 1048574)
  await assert.rejects(readBoundedBaselineJson(new Response(at + ' ')))
})
for (const [name, change] of [
  ['redirect', (r) => Object.defineProperty(r, 'redirected', { value: true })],
  ['foreign URL', (r) => Object.defineProperty(r, 'url', { value: 'https://evil.test' })],
  ['missing no-store', (r) => r.headers.delete('cache-control')],
  ['wrong content-type', (r) => r.headers.set('content-type', 'text/html')],
])
  test(`rejects ${name}`, async () => {
    const r = response()
    change(r)
    await assert.rejects(setup(async () => r).request(request()))
  })
test('classified bounded server errors never expose raw detail', async () => {
  for (const [status, code] of [
    [409, 'baseline_in_progress'],
    [429, 'baseline_capacity'],
    [503, 'temporary_unavailable'],
    [410, 'checkpoint_expired'],
    [401, 'invalid_session'],
    [403, 'capability_denied'],
    [409, 'context_changed'],
    [413, 'projection_too_large'],
    [422, 'cursor_invalid'],
  ]) {
    const r = new Response(
      JSON.stringify({
        error: {
          code,
          message: 'PRIVATE',
          details: { secret: 'PRIVATE' },
          request_id: 'private-id',
        },
      }),
      {
        status,
        headers: {
          'content-type': 'application/json',
          'cache-control': 'no-store',
          'retry-after': '2',
        },
      },
    )
    Object.defineProperty(r, 'url', {
      value: `${realm}/sync/baselines/finalize`,
      configurable: true,
    })
    await assert.rejects(
      setup(async () => r).request(request()),
      (error) =>
        error.code === code &&
        error.status === status &&
        !JSON.stringify(error).includes('PRIVATE') &&
        error.retryAfterMs === 2000,
    )
  }
})
test('unknown or mismatched error codes fail closed; network messages are sanitized', async () => {
  for (const [status, value] of [
    [409, { error: { code: 'temporary_unavailable' } }],
    [503, { error: { code: 'private-internal' } }],
  ]) {
    const r = new Response(JSON.stringify(value), {
      status,
      headers: { 'content-type': 'application/json', 'cache-control': 'no-store' },
    })
    Object.defineProperty(r, 'url', {
      value: `${realm}/sync/baselines/finalize`,
      configurable: true,
    })
    await assert.rejects(
      setup(async () => r).request(request()),
      (e) => e.code === 'invalid_response',
    )
  }
  await assert.rejects(
    setup(async () => {
      throw new Error('token-A PRIVATE')
    }).request(request()),
    (e) => e.code === 'network_error' && !e.message.includes('PRIVATE'),
  )
})
test('HTTPException and validation errors classify by safe status without raw reflection', async () => {
  for (const [status, value, code] of [
    [401, { detail: 'Not authenticated' }, 'invalid_session'],
    [403, { detail: 'Forbidden' }, 'capability_denied'],
    [
      422,
      { detail: [{ loc: ['body'], msg: 'Invalid request value', type: 'missing' }] },
      'invalid_request',
    ],
  ]) {
    const r = new Response(JSON.stringify(value), {
      status,
      headers: { 'content-type': 'application/json', 'cache-control': 'no-store' },
    })
    Object.defineProperty(r, 'url', {
      value: `${realm}/sync/baselines/finalize`,
      configurable: true,
    })
    await assert.rejects(setup(async () => r).request(request()), (e) => e.code === code)
  }
})
test('oversized error bodies are bounded too', async () => {
  const r = new Response('x'.repeat(1048577), {
    status: 503,
    headers: { 'content-type': 'application/json', 'cache-control': 'no-store' },
  })
  Object.defineProperty(r, 'url', { value: `${realm}/sync/baselines/finalize`, configurable: true })
  await assert.rejects(
    setup(async () => r).request(request()),
    (e) => e.code === 'invalid_response',
  )
})
test('identity capture includes only defined routing fields and stays immutable', async () => {
  let captured
  const r = request({
    isCurrent: (value) => {
      captured = value
      return true
    },
  })
  r.identity.extra = 'not-routing'
  await setup(async () => response()).request(r)
  assert.equal(captured.extra, undefined)
  assert.ok(Object.isFrozen(captured))
})
test('invalid request kinds and invalid identity fields never dispatch', async () => {
  for (const mutate of [
    (r) => (r.kind = 'unknown'),
    (r) => (r.identity.sessionHandle = 1),
    (r) => (r.identity.tabAttemptId = 1),
    (r) => (r.identity.organizationId = ''),
    (r) => (r.bearerToken = 'a b'),
  ]) {
    let calls = 0
    const r = request()
    mutate(r)
    await assert.rejects(
      setup(async () => {
        calls++
        return response()
      }).request(r),
    )
    assert.equal(calls, 0)
  }
})
test('rejecting headers cancels the response stream', async () => {
  let cancelled = false
  const stream = new ReadableStream({
    cancel() {
      cancelled = true
    },
  })
  const r = new Response(stream, { headers: { 'content-type': 'text/html' } })
  Object.defineProperty(r, 'url', { value: `${realm}/sync/baselines/finalize` })
  await assert.rejects(setup(async () => r).request(request()))
  assert.equal(cancelled, true)
})
test('error response requires no-store as required by server middleware', async () => {
  const r = new Response('{"error":{"code":"baseline_capacity"}}', {
    status: 429,
    headers: { 'content-type': 'application/json' },
  })
  Object.defineProperty(r, 'url', { value: `${realm}/sync/baselines/finalize` })
  await assert.rejects(
    setup(async () => r).request(request()),
    (e) => e.code === 'invalid_response',
  )
})
test('Retry-After is bounded and malformed/negative values ignored', async () => {
  for (const [retry, expected] of [
    ['999999', 999999000],
    ['1800', 1800000],
    ['-1', null],
    ['garbage', null],
    ['Wed, 14 Oct 2026 10:00:05 GMT', 5000],
  ]) {
    const r = new Response('{"error":{"code":"baseline_capacity"}}', {
      status: 429,
      headers: {
        'content-type': 'application/json',
        'cache-control': 'no-store',
        'retry-after': retry,
      },
    })
    Object.defineProperty(r, 'url', { value: `${realm}/sync/baselines/finalize` })
    await assert.rejects(
      setup(async () => r).request(request()),
      (e) => e.code === 'baseline_capacity' && e.retryAfterMs === expected,
    )
  }
})
test('new overlapping request invalidates earlier request even with same identity', async () => {
  let first
  let calls = 0
  const adapter = setup(async () =>
    ++calls === 1 ? new Promise((resolve) => (first = resolve)) : response(),
  )
  const older = adapter.request(request())
  assert.equal((await adapter.request(request())).continuation, 'next')
  first(response())
  await assert.rejects(older, (e) => e.code === 'stale_request')
})
test('stream network interruption is retryable without exposing stream exception', async () => {
  const stream = new ReadableStream({
    start(controller) {
      controller.error(new Error('PRIVATE token-A'))
    },
  })
  const r = new Response(stream, {
    headers: { 'content-type': 'application/json', 'cache-control': 'no-store' },
  })
  Object.defineProperty(r, 'url', { value: `${realm}/sync/baselines/finalize` })
  await assert.rejects(
    setup(async () => r).request(request()),
    (error) => error.code === 'network_error' && !error.message.includes('PRIVATE'),
  )
})
test('throwing current-state callback cannot leak exceptions', async () => {
  await assert.rejects(
    setup(async () => response()).request(
      request({
        isCurrent: () => {
          throw new Error('PRIVATE')
        },
      }),
    ),
    (error) => error instanceof BaselineTransportError && !error.message.includes('PRIVATE'),
  )
})

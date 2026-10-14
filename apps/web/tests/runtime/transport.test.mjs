import test from 'node:test'
import assert from 'node:assert/strict'
import {
  createRuntimeTransport,
  RuntimeHttpError,
} from '../../.tmp-runtime/src/runtime/transport.js'
const realm = 'https://example.test/api/v1'
const response = (url, value, status = 200) => {
  const r = new Response(status === 204 ? null : JSON.stringify(value), {
    status,
    headers: { 'content-type': 'application/json', 'cache-control': 'no-store' },
  })
  Object.defineProperty(r, 'url', { value: url })
  return r
}
const auth = { token: 'captured-token', isCurrent: () => true }
test('auth, location and history reads bound bytes before parsing with captured token and safe routing', async () => {
  const calls = []
  const transport = createRuntimeTransport({
    apiRealm: realm,
    fetch: async (url, init) => {
      calls.push({ url, init })
      return response(url, {
        user_id: 'u',
        organization_id: 'o',
        location_id: 'l',
        display_name: 'User',
        capabilities: ['customers.read'],
      })
    },
  })
  assert.equal((await transport.me(auth)).user_id, 'u')
  assert.equal(calls[0].init.headers.Authorization, 'Bearer captured-token')
  assert.equal(calls[0].init.headers['X-OCWP-Write-Protocol'], undefined)
  assert.equal(calls[0].init.credentials, 'omit')
  assert.equal(calls[0].init.redirect, 'error')
  for (const method of ['me', 'locations', 'timeline']) {
    let parsed = false
    const t = createRuntimeTransport({
      apiRealm: realm,
      fetch: async (url) => {
        const r = response(url, { padding: 'x'.repeat(300000) })
        r.json = () => {
          parsed = true
          throw new Error('must not call json')
        }
        return r
      },
    })
    await assert.rejects(
      t[method](auth, 'o', 'order'),
      (e) => e instanceof RuntimeHttpError && e.code === 'invalid_response',
    )
    assert.equal(parsed, false)
  }
})
test('location pagination rejects foreign scope, duplicate and contradictory continuation', async () => {
  for (const body of [
    { items: [{ location_id: 'l', organization_id: 'foreign', name: 'Wrong' }], next_cursor: null },
    { items: [], next_cursor: 'l' },
    { items: [{ location_id: 'l', organization_id: 'o', name: 'One' }], next_cursor: 'different' },
  ]) {
    const t = createRuntimeTransport({ apiRealm: realm, fetch: async (url) => response(url, body) })
    await assert.rejects(t.locations(auth, 'o'), RuntimeHttpError)
  }
})
test('server timeline is scoped by captured URL and adds verified organization only after validation', async () => {
  const event = {
    event_id: 'e',
    order_id: 'order',
    actor_id: 'u',
    from_state: 'INTAKE',
    to_state: 'DIAGNOSIS',
    action: 'diagnose',
    note: null,
    occurred_at: '2026-10-14T10:00:00Z',
  }
  const t = createRuntimeTransport({
    apiRealm: realm,
    fetch: async (url) => response(url, [event]),
  })
  assert.deepEqual(await t.timeline(auth, 'o', 'order'), [{ ...event, organization_id: 'o' }])
  await assert.rejects(t.timeline(auth, 'o', 'other'), RuntimeHttpError)
})
test('logout-all sends captured protocol 1 and token with safe routing and accepts no-body success', async () => {
  const calls = []
  const t = createRuntimeTransport({
    apiRealm: realm,
    fetch: async (url, init) => {
      calls.push({ url, init })
      return response(url, null, 204)
    },
  })
  await t.revoke(auth)
  assert.ok(calls[0].init.signal instanceof AbortSignal)
  assert.deepEqual(calls, [
    {
      url: `${realm}/auth/logout-all`,
      init: {
        signal: calls[0].init.signal,
        method: 'POST',
        headers: {
          Accept: 'application/json',
          Authorization: 'Bearer captured-token',
          'X-OCWP-Write-Protocol': '1',
          'Content-Type': 'application/json',
        },
        body: '{}',
        credentials: 'omit',
        redirect: 'error',
        cache: 'no-store',
        referrerPolicy: 'no-referrer',
      },
    },
  ])
})
test('logout-all refuses stale dispatch and ignores success after captured session changes', async () => {
  let current = false
  let calls = 0
  const source = { token: auth.token, isCurrent: () => current }
  const t = createRuntimeTransport({
    apiRealm: realm,
    fetch: async (url) => {
      calls += 1
      current = false
      return response(url, null, 204)
    },
  })
  const isStale = (e) => e instanceof RuntimeHttpError && e.code === 'stale_request'
  await assert.rejects(t.revoke(source), isStale)
  assert.equal(calls, 0)
  current = true
  await assert.rejects(t.revoke(source), isStale)
  assert.equal(calls, 1)
})
test('stale login responses never escape and login does not declare a write protocol', async () => {
  let current = true
  const stale = createRuntimeTransport({
    apiRealm: realm,
    fetch: async (url, init) => {
      assert.equal(init.headers['X-OCWP-Write-Protocol'], undefined)
      current = false
      return response(url, { access_token: 'secret', token_type: 'bearer' })
    },
  })
  await assert.rejects(
    stale.login({ organization_id: 'o', username: 'u', password: 'private' }, () => current),
    (e) =>
      e instanceof RuntimeHttpError && e.code === 'stale_request' && !e.message.includes('secret'),
  )
})

test('received refusal statuses cannot become a network failure through an interrupted body', async () => {
  for (const [status, code] of [
    [401, 'invalid_session'],
    [403, 'capability_denied'],
    [409, 'invalid_response'],
    [500, 'invalid_response'],
    [200, 'network_error'],
  ]) {
    const transport = createRuntimeTransport({
      apiRealm: realm,
      fetch: async (url) => {
        const r = new Response(
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
        Object.defineProperty(r, 'url', { value: url })
        return r
      },
    })
    await assert.rejects(
      transport.me(auth),
      (error) => error instanceof RuntimeHttpError && error.code === code,
    )
  }
})

test('probe captures AbortSignal and refuses an already aborted request before bearer dispatch', async () => {
  const abort = new AbortController()
  let calls = 0
  const transport = createRuntimeTransport({
    apiRealm: realm,
    fetch: async (url, init) => {
      calls++
      assert.equal(init.signal, abort.signal)
      abort.abort()
      return response(url, {})
    },
  })
  const source = { ...auth, signal: abort.signal }
  await assert.rejects(transport.me(source), (e) => e.code === 'stale_request')
  await assert.rejects(transport.me(source), (e) => e.code === 'stale_request')
  assert.equal(calls, 1)
})
for (const mode of ['401', '403', '409', 'headers', 'oversized'])
  test(
    `probe preserves terminal ${mode} even when body cancellation never settles`,
    { timeout: 1000 },
    async () => {
      let canceled = 0
      const transport = createRuntimeTransport({
        apiRealm: realm,
        fetch: async (url) => {
          const r = new Response(
            new ReadableStream({
              start(controller) {
                if (mode === 'oversized') controller.enqueue(new Uint8Array(20000))
              },
              cancel() {
                canceled++
                return new Promise(() => {})
              },
            }),
            {
              status: /^\d+$/.test(mode) ? Number(mode) : 200,
              headers: {
                'content-type': mode === 'headers' ? 'text/plain' : 'application/json',
                'cache-control': 'no-store',
              },
            },
          )
          Object.defineProperty(r, 'url', { value: url })
          return r
        },
      })
      await assert.rejects(
        transport.me({ ...auth, signal: new AbortController().signal }),
        (e) =>
          e.code ===
          (mode === '401'
            ? 'invalid_session'
            : mode === '403'
              ? 'capability_denied'
              : 'invalid_response'),
      )
      assert.equal(canceled, 1)
    },
  )
test(
  'probe deadline aborts body consumption without turning it into parsed authority',
  { timeout: 1000 },
  async () => {
    const abort = new AbortController()
    let reading,
      canceled = 0
    const started = new Promise((resolve) => {
      reading = resolve
    })
    const transport = createRuntimeTransport({
      apiRealm: realm,
      fetch: async (url) => {
        const r = new Response(
          new ReadableStream({
            pull() {
              reading()
            },
            cancel() {
              canceled++
              return new Promise(() => {})
            },
          }),
          { headers: { 'content-type': 'application/json', 'cache-control': 'no-store' } },
        )
        Object.defineProperty(r, 'url', { value: url })
        return r
      },
    })
    const promise = transport.me({ ...auth, signal: abort.signal })
    await started
    abort.abort()
    await assert.rejects(promise, (e) => ['network_error', 'stale_request'].includes(e.code))
    assert.equal(canceled, 1)
  },
)

test('logout-all rejects bodyless success without no-store', async () => {
  const transport = createRuntimeTransport({
    apiRealm: realm,
    fetch: async (url) => {
      const result = response(url, null, 204)
      result.headers.delete('cache-control')
      return result
    },
  })
  await assert.rejects(transport.revoke(auth), (error) => error.code === 'invalid_response')
})

test('logout-all deadline bounds even an abort-ignoring fetch and aborts the capture signal', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  let signal, finish
  const transport = createRuntimeTransport({
    apiRealm: realm,
    fetch: (url, init) => {
      signal = init.signal
      return new Promise((resolve) => {
        finish = () => resolve(response(url, null, 204))
      })
    },
  })
  const pending = transport.revoke(auth)
  const rejection = assert.rejects(pending, (error) => error.code === 'network_error')
  t.mock.timers.tick(10000)
  await rejection
  assert.equal(signal.aborted, true)
  finish()
})

test('logout-all rejects unexpected200 even with valid JSON and no-store', async () => {
  const transport = createRuntimeTransport({
    apiRealm: realm,
    fetch: async (url) => response(url, {}, 200),
  })
  await assert.rejects(transport.revoke(auth), (error) => error.code === 'invalid_response')
})

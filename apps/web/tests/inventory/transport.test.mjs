import test from 'node:test'
import assert from 'node:assert/strict'
import { createInventoryTransport } from '../../.tmp-inventory/src/features/inventory/transport.js'
const context = {
  principal: { organizationId: 'org' },
  selectedLocationId: 'loc',
  offlineUntil: new Date(Date.now() + 60000).toISOString(),
}
const source = {
  token: 'synthetic',
  context,
  apiRealm: 'https://test.example/api/v1',
  signal: new AbortController().signal,
  isCurrent: () => true,
}
const stock = {
  product_id: 'part',
  organization_id: 'org',
  location_id: 'loc',
  available_quantity: -3,
}
function response(url, raw = JSON.stringify(stock), options = {}) {
  const r = new Response(raw, {
    headers: { 'content-type': 'application/json', 'cache-control': 'private, no-store' },
    ...options,
  })
  Object.defineProperty(r, 'url', { value: url })
  return r
}
const factory = (fetch) => createInventoryTransport({ apiRealm: source.apiRealm, fetch })
test('receiver-bound private GETs only, correct URLs and no writer protocol', async () => {
  const requests = []
  const http = factory(function (url, init) {
    assert.equal(this, globalThis)
    requests.push({ url, init })
    return Promise.resolve(
      response(
        url,
        url.includes('/stock')
          ? JSON.stringify(stock)
          : url.includes('/movements')
            ? '{"items":[],"next_cursor":null}'
            : '[]',
      ),
    )
  })
  await http.catalog(source, 50)
  await http.stock(source, 'part')
  await http.movements(source, 'part')
  assert.deepEqual(
    requests.map((r) => r.url),
    [
      'https://test.example/api/v1/inventory/products?location_id=loc&limit=50&offset=50',
      'https://test.example/api/v1/inventory/products/part/stock',
      'https://test.example/api/v1/inventory/products/part/movements?limit=50',
    ],
  )
  for (const { init } of requests) {
    assert.equal(init.method, 'GET')
    assert.equal(init.cache, 'no-store')
    assert.equal(init.credentials, 'omit')
    assert.equal(init.redirect, 'error')
    assert.equal(init.referrerPolicy, 'no-referrer')
    assert.equal(init.headers['X-OCWP-Write-Protocol'], undefined)
  }
})
test('401/403 win before invalid URL, MIME, cache headers and stalled body; no private error details', async () => {
  for (const status of [401, 403]) {
    const http = factory(async () => new Response(new ReadableStream(), { status }))
    await assert.rejects(
      http.stock(source, 'part'),
      (e) => e.status === status && !e.message.includes('synthetic'),
    )
  }
})
test('bad headers, bytes, redirect, scope and malformed numeric responses fail closed', async () => {
  for (const make of [
    (url) =>
      response(url, JSON.stringify(stock), {
        headers: { 'content-type': 'text/html', 'cache-control': 'no-store' },
      }),
    (url) =>
      response(url, JSON.stringify(stock), { headers: { 'content-type': 'application/json' } }),
    (url) =>
      response(url, JSON.stringify(stock), {
        headers: { 'content-type': 'application/jsonfoo', 'cache-control': 'no-store' },
      }),
    (url) => response(url, ' '.repeat(1024 * 1024) + '{}'),
    (url) => response(url, new Uint8Array([0xff])),
    (url) => response(url + '/other'),
    (url) => response(url, JSON.stringify({ ...stock, product_id: 'other' })),
    (url) => response(url, JSON.stringify(stock).replace('-3', '1e-999')),
  ])
    await assert.rejects(
      factory(async (url) => make(url)).stock(source, 'part'),
      (e) => e.code === 'invalid_response',
    )
})
test('stale late success and late refusal cannot publish; abort returns without cooperative fetch', async () => {
  for (const status of [200, 401, 403]) {
    let current = true
    const http = factory(async (url) => {
      current = false
      return response(url, JSON.stringify(stock), { status })
    })
    await assert.rejects(
      http.stock({ ...source, isCurrent: () => current }, 'part'),
      (e) => e.code === 'stale_request',
    )
  }
  const abort = new AbortController()
  const pending = factory(() => new Promise(() => {})).stock(
    { ...source, signal: abort.signal },
    'part',
  )
  abort.abort()
  await assert.rejects(pending, (e) => e.code === 'stale_request')
})
test('deadline bounds fetch and body despite noncooperative network; no retries', async () => {
  const original = globalThis.setTimeout
  let calls = 0
  globalThis.setTimeout = (fn, ms, ...args) => original(fn, ms === 10000 ? 5 : ms, ...args)
  try {
    for (const fetch of [
      () => {
        calls++
        return new Promise(() => {})
      },
      async (url) => {
        calls++
        return response(url, new ReadableStream())
      },
    ])
      await assert.rejects(factory(fetch).stock(source, 'part'), (e) => e.code === 'network_error')
    assert.equal(calls, 2)
  } finally {
    globalThis.setTimeout = original
  }
})
test('stock unsupported safe range reported explicitly and server/network failures are safe', async () => {
  await assert.rejects(
    factory(async (url) =>
      response(url, JSON.stringify(stock).replace('-3', '9007199254740992')),
    ).stock(source, 'part'),
    (e) => e.code === 'unsupported_quantity',
  )
  await assert.rejects(
    factory(async (url) => response(url, 'private secret', { status: 503 })).stock(source, 'part'),
    (e) => e.code === 'unavailable' && !e.message.includes('private secret'),
  )
  await assert.rejects(
    factory(async () => {
      throw Error('private secret')
    }).stock(source, 'part'),
    (e) => e.code === 'network_error' && !e.message.includes('private secret'),
  )
})

test('aborted noncooperative fetch cancels a late response body', async () => {
  let resolve,
    canceled = false
  const abort = new AbortController()
  const pending = factory(
    () =>
      new Promise((r) => {
        resolve = r
      }),
  ).stock({ ...source, signal: abort.signal }, 'part')
  abort.abort()
  await assert.rejects(pending, (e) => e.code === 'stale_request')
  resolve(
    response(
      'https://test.example/api/v1/inventory/products/part/stock',
      new ReadableStream({
        cancel() {
          canceled = true
        },
      }),
    ),
  )
  await new Promise((r) => setTimeout(r, 0))
  assert.equal(canceled, true)
})
test('context expiry shortens the finite deadline without relying on cooperative fetch', async () => {
  const original = globalThis.setTimeout
  let duration
  globalThis.setTimeout = (fn, ms, ...args) => {
    duration = ms
    return original(fn, 0, ...args)
  }
  try {
    await assert.rejects(
      factory(() => new Promise(() => {})).stock(
        {
          ...source,
          context: { ...source.context, offlineUntil: new Date(Date.now() + 100).toISOString() },
        },
        'part',
      ),
      (e) => e.code === 'stale_request',
    )
    assert.ok(duration <= 100)
  } finally {
    globalThis.setTimeout = original
  }
})

for (const phase of ['fetch', 'body']) {
  for (const outcome of [200, 401, 403]) {
    if (phase === 'body' && outcome !== 200) continue
    test(`suspended deadline timer cannot accept overdue ${phase} outcome ${outcome}`, async (t) => {
      const start = Date.now()
      t.mock.timers.enable({ apis: ['setTimeout', 'Date'], now: start })
      let finish
      const pending = factory((url) =>
        phase === 'fetch'
          ? new Promise((resolve) => {
              finish = () => resolve(response(url, JSON.stringify(stock), { status: outcome }))
            })
          : Promise.resolve(
              response(
                url,
                new ReadableStream({
                  start(controller) {
                    finish = () => {
                      controller.enqueue(new TextEncoder().encode(JSON.stringify(stock)))
                      controller.close()
                    }
                  },
                }),
              ),
            ),
      ).stock(
        { ...source, context: { ...context, offlineUntil: new Date(start + 60000).toISOString() } },
        'part',
      )
      await Promise.resolve()
      t.mock.timers.setTime(start + 10001)
      finish()
      await assert.rejects(
        pending,
        (error) => error.code === 'stale_request' && error.status === null,
      )
    })
  }
}

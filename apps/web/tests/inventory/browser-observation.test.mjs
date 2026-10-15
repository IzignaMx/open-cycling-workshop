import assert from 'node:assert/strict'
import test from 'node:test'
import {
  isUnexpectedApiWrite,
  observeInventoryContext,
} from '../../e2e/helpers/inventory-observation.mjs'

const origin = 'http://127.0.0.1:5173'
const location = 'synthetic-location'
const contextUrl = `${origin}/api/v1/auth/context?selected_location_id=${location}`
const body = {
  selected_location_id: location,
  offline_until: '2026-10-15T15:33:03.123456Z',
  snapshot_protocol: null,
}

test('only the exact POST delta page is exempted from the write observer', () => {
  assert.equal(isUnexpectedApiWrite('POST', `${origin}/api/v1/sync/deltas/page`), false)
  assert.equal(isUnexpectedApiWrite('POST', `${origin}/api/v1/sync/deltas/page?x=1`), false)
  for (const path of [
    '/api/v1/sync/mutations',
    '/api/v1/sync/deltas/page/',
    '/api/v1/sync/deltas/page-other',
    '/api/v1/sync/deltas%2fpage',
    '/api/v1/customers?next=/api/v1/sync/deltas/page',
    '/api/v1/inventory/products',
    '/api/v1/inventory/movements',
    '/api/v1/auth/logout',
    '/api/v1/auth/login',
    '/api/v1/admin/users/synthetic/revoke-sessions',
    '/api/v1/sync/baselines/start',
    '/api/v1/unknown',
  ])
    assert.equal(isUnexpectedApiWrite('POST', origin + path), true, path)
  for (const method of ['PUT', 'PATCH', 'DELETE'])
    assert.equal(isUnexpectedApiWrite(method, `${origin}/api/v1/sync/deltas/page`), true)
  for (const method of ['GET', 'HEAD', 'OPTIONS'])
    assert.equal(isUnexpectedApiWrite(method, `${origin}/api/v1/inventory/products`), false)
  assert.equal(isUnexpectedApiWrite('POST', `${origin}/unrelated`), false)
})

function harness() {
  let predicate, resolve, reject
  const response = new Promise((yes, no) => {
    resolve = yes
    reject = no
  })
  return {
    page: {
      url: () => origin + '/',
      waitForResponse: (matches) => {
        predicate = matches
        return response
      },
    },
    emit(candidate) {
      assert.ok(predicate, 'observation must be installed before action')
      if (predicate(candidate)) resolve(candidate)
    },
    reject,
  }
}
function candidate(overrides = {}) {
  return {
    url: () => contextUrl,
    status: () => 200,
    request: () => ({ method: () => 'GET' }),
    json: async () => structuredClone(body),
    ...overrides,
  }
}

test('context body is consumed while the action is still running, before later readiness', async () => {
  const h = harness()
  let available = true,
    reads = 0,
    ready = false
  const result = await observeInventoryContext(h.page, location, async () => {
    h.emit(
      candidate({
        json: async () => {
          reads++
          assert.ok(available, 'body is no longer available after readiness')
          return body
        },
      }),
    )
    await new Promise((resolve) => setImmediate(resolve))
    available = false
    ready = true
  })
  assert.equal(ready, true)
  assert.equal(reads, 1)
  assert.deepEqual(result, { expiresAt: Date.parse(body.offline_until), snapshotProtocol: null })
})

test('observation accepts only a successful GET for the same origin and selected scope', async () => {
  const h = harness()
  let ignoredReads = 0
  const wrong = [
    { url: () => contextUrl.replace(origin, 'https://other.example') },
    { url: () => contextUrl.replace(location, 'other-location') },
    { url: () => contextUrl + '&selected_location_id=other-location' },
    { url: () => `${origin}/api/v1/auth/context-other?selected_location_id=${location}` },
    { request: () => ({ method: () => 'POST' }) },
    { status: () => 401 },
    { status: () => 403 },
    { status: () => 500 },
  ]
  const result = await observeInventoryContext(h.page, location, async () => {
    for (const overrides of wrong)
      h.emit(
        candidate({
          json: async () => {
            ignoredReads++
            return body
          },
          ...overrides,
        }),
      )
    h.emit(candidate({ json: async () => ({ ...body, snapshot_protocol: 'baseline-v1' }) }))
  })
  assert.equal(ignoredReads, 0)
  assert.equal(result.snapshotProtocol, 'baseline-v1')
})

test('missing body and malformed JSON reject once without fallback, retry or fabricated expiry', async () => {
  for (const message of ['body unavailable', 'invalid JSON']) {
    const h = harness()
    let reads = 0
    await assert.rejects(
      observeInventoryContext(h.page, location, async () => {
        h.emit(
          candidate({
            json: async () => {
              reads++
              throw new Error(message)
            },
          }),
        )
      }),
      new RegExp(message),
    )
    assert.equal(reads, 1)
  }
})

test('observation retains action and response failure instead of reporting success', async () => {
  const h = harness()
  await assert.rejects(
    observeInventoryContext(h.page, location, async () => {
      h.emit(candidate())
      throw new Error('action failed')
    }),
    /action failed/,
  )
  const failed = harness()
  await assert.rejects(
    observeInventoryContext(failed.page, location, async () => {
      failed.reject(new Error('response failed'))
    }),
    /response failed/,
  )
})

test('invalid expiry, scope or snapshot protocol fail closed without returning body fields', async () => {
  for (const invalid of [
    { offline_until: null },
    { offline_until: 'not-an-instant' },
    { selected_location_id: 'another-location' },
    { snapshot_protocol: 'future-protocol' },
  ]) {
    const h = harness()
    await assert.rejects(
      observeInventoryContext(h.page, location, async () => {
        h.emit(candidate({ json: async () => ({ ...body, ...invalid }) }))
      }),
      /^Error: Invalid inventory context observation$/,
    )
  }
})

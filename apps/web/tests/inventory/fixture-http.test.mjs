import assert from 'node:assert/strict'
import test from 'node:test'
import { fixtureHttp } from '../../e2e/helpers/inventory-http.mjs'

const origin = 'http://127.0.0.1:5173'
const path = '/api/v1/inventory/products/00000000-0000-7000-8000-000001000100/stock'
const safeError = /^Error: Inventory fixture HTTP failed$/

test('fixture boundary only permits fixed same-origin loopback paths before fetch', async () => {
  let requests = 0
  const fetcher = async () => {
    requests++
    return new Response('{}')
  }
  for (const [base, url, method] of [
    ['https://example.com', 'https://example.com' + path, 'GET'],
    [origin, 'http://localhost:5173' + path, 'GET'],
    [origin, origin + path + '?private=value', 'GET'],
    [origin, origin + '/api/v1/customers', 'POST'],
    [origin, origin + path, 'POST'],
    [origin, 'http://user:private@127.0.0.1:5173' + path, 'GET'],
  ])
    await assert.rejects(fixtureHttp(base, url, { method }, fetcher), safeError)
  assert.equal(requests, 0)
})

test('native failure is generic with no cause, request headers or private response', async () => {
  const privateValue = 'environment-only-canary-used-by-report-test'
  await assert.rejects(
    fixtureHttp(origin, origin + path, { headers: { Authorization: privateValue } }, async () => {
      throw new Error(privateValue)
    }),
    (error) => error.message === 'Inventory fixture HTTP failed' && error.cause === undefined,
  )
})

test('bounded response exposes only allowlisted forwarding headers and disables redirects', async () => {
  const result = await fixtureHttp(
    origin,
    origin + path,
    { headers: { Authorization: 'synthetic', Cookie: 'unforwarded' } },
    async (url, init) => {
      assert.equal(url, origin + path)
      assert.equal(init.redirect, 'error')
      assert.equal(init.headers.get('authorization'), 'synthetic')
      assert.equal(init.headers.get('cookie'), null)
      assert.ok(init.signal)
      return new Response('{"available_quantity":148}', {
        headers: {
          'Content-Type': 'application/json',
          'Cache-Control': 'no-store',
          'Set-Cookie': 'private',
        },
      })
    },
  )
  assert.equal(result.status, 200)
  assert.equal(result.body, '{"available_quantity":148}')
  assert.deepEqual(result.headers, {
    'content-type': 'application/json',
    'cache-control': 'no-store',
  })
  await assert.rejects(
    fixtureHttp(origin, origin + path, {}, async () => new Response('x'.repeat(1_048_577))),
    safeError,
  )
})

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
test('no-body logout response succeeds and stale responses never escape', async () => {
  let current = true
  const t = createRuntimeTransport({
    apiRealm: realm,
    fetch: async (url) => response(url, null, 204),
  })
  await t.revoke(auth)
  const stale = createRuntimeTransport({
    apiRealm: realm,
    fetch: async (url) => {
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

import test from 'node:test'
import assert from 'node:assert/strict'

import { ApiClient } from '../.tmp-test/client.js'

test('auth methods use the canonical endpoints and bearer token only after login', async () => {
  const calls = []
  const responses = [
    new Response(JSON.stringify({ access_token: 'session-token', token_type: 'bearer' }), {
      status: 200,
      headers: { 'content-type': 'application/json' },
    }),
    new Response(
      JSON.stringify({
        user_id: 'user-1',
        organization_id: 'org-1',
        location_id: 'loc-1',
        display_name: 'Admin',
        capabilities: ['customers.read'],
      }),
      { status: 200, headers: { 'content-type': 'application/json' } },
    ),
    new Response(null, { status: 204 }),
  ]
  let token = null
  const client = new ApiClient({
    baseUrl: 'https://example.test/',
    tokenProvider: () => token,
    fetcher: async (url, init) => {
      calls.push({ url: String(url), init })
      return responses.shift()
    },
  })

  const login = await client.login({
    organization_id: 'org-1',
    username: 'admin',
    password: 'very long password',
  })
  token = login.access_token
  const me = await client.me()
  await client.logoutAll()

  assert.equal(me.user_id, 'user-1')
  assert.equal(calls[0].url, 'https://example.test/api/v1/auth/login')
  assert.equal(new Headers(calls[0].init.headers).has('Authorization'), false)
  assert.equal(calls[1].url, 'https://example.test/api/v1/auth/me')
  assert.equal(new Headers(calls[1].init.headers).get('Authorization'), 'Bearer session-token')
  assert.equal(calls[2].url, 'https://example.test/api/v1/auth/logout-all')
})

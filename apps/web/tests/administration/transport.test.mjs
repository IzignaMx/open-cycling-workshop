import test from 'node:test'
import assert from 'node:assert/strict'
import { createAdministrationTransport } from '../../.tmp-administration/src/features/administration/transport.js'
const apiRealm = 'https://example.test/api/v1'
const user = {
  user_id: 'a',
  organization_id: 'o',
  location_id: null,
  display_name: 'A',
  capabilities: ['users.read'],
}
const capture = { token: 'captured', user, isCurrent: () => true }
const response = (url, value, status = 200, store = 'no-store') => {
  const r = new Response(status === 204 ? null : JSON.stringify(value), {
    status,
    headers: { 'content-type': 'application/json', 'cache-control': store },
  })
  Object.defineProperty(r, 'url', { value: url })
  return r
}
test('bodyless commands require no-store and protocol1', async () => {
  let init
  const t = createAdministrationTransport({
    apiRealm,
    fetch: async (url, i) => {
      init = i
      return response(url, null, 204)
    },
  })
  await t.logoutAll(capture)
  assert.equal(init.headers['X-OCWP-Write-Protocol'], '1')
  assert.equal(init.cache, 'no-store')
  const bad = createAdministrationTransport({
    apiRealm,
    fetch: async (url) => response(url, null, 204, 'public'),
  })
  await assert.rejects(bad.logoutAll(capture), (e) => e.code === 'invalid_response')
})
test('pages reject cross-organization and duplicate rows; stale refusals stay stale', async () => {
  const row = { ...user, username: 'a', version: 1, is_owner: false, is_active: true }
  for (const items of [[{ ...row, organization_id: 'other' }], [row, row]]) {
    const t = createAdministrationTransport({
      apiRealm,
      fetch: async (url) => response(url, { items, next_cursor: null }),
    })
    await assert.rejects(t.users(capture), (e) => e.code === 'invalid_response')
  }
  let current = true
  const t = createAdministrationTransport({
    apiRealm,
    fetch: async (url) => {
      current = false
      return response(url, { detail: 'secret' }, 401)
    },
  })
  await assert.rejects(
    t.users({ ...capture, isCurrent: () => current }),
    (e) => e.code === 'stale_request',
  )
})
test('only known error identifiers escape response body', async () => {
  const t = createAdministrationTransport({
    apiRealm,
    fetch: async (url) =>
      response(url, { error: { code: 'stale_user_version', message: 'SECRET' } }, 409),
  })
  await assert.rejects(
    t.users(capture),
    (e) => e.code === 'stale_user_version' && !e.message.includes('SECRET'),
  )
})
test('each command uses exact routes, methods, status and captured versions', async () => {
  const row = { ...user, username: 'a', version: 2, is_owner: false, is_active: true }
  const calls = []
  const t = createAdministrationTransport({
    apiRealm,
    fetch: async (url, init) => {
      calls.push([url, init])
      if (url.endsWith('/locations'))
        return response(url, { location_id: 'l', organization_id: 'o', name: 'Shop' }, 201)
      if (url.includes('/auth/')) return response(url, null, 204)
      return response(url, row, init.method === 'POST' && url.endsWith('/users') ? 201 : 200)
    },
  })
  await t.createUser(capture, {
    username: ' A ',
    display_name: 'A',
    password: 'twelve-chars!',
    location_id: null,
    capabilities: [],
  })
  await t.updateUser(capture, 'a', { expected_version: 1, display_name: 'B' })
  await t.resetPassword(capture, 'a', { expected_version: 1, new_password: 'twelve-chars!' })
  await t.revokeSessions(capture, 'a', { expected_version: 1 })
  await t.createLocation(capture, { name: 'Shop' })
  await t.changePassword(capture, { current_password: 'old', new_password: 'twelve-chars!' })
  assert.deepEqual(
    calls.map(([url]) => url.replace(apiRealm, '')),
    [
      '/admin/users',
      '/admin/users/a',
      '/admin/users/a/reset-password',
      '/admin/users/a/revoke-sessions',
      '/locations',
      '/auth/change-password',
    ],
  )
  assert.equal(calls[1][1].method, 'PATCH')
  assert.equal(JSON.parse(calls[0][1].body).username, 'a')
  for (const [, init] of calls) {
    assert.equal(init.headers['X-OCWP-Write-Protocol'], '1')
    assert.equal(init.credentials, 'omit')
    assert.equal(init.redirect, 'error')
    assert.equal(init.referrerPolicy, 'no-referrer')
  }
})
test('bounded IDs are encoded without a fictitious server alphabet', async () => {
  const id = 'a/b?c#d'
  const row = { ...user, user_id: id, username: 'a', version: 2, is_owner: false, is_active: true }
  let called
  const t = createAdministrationTransport({
    apiRealm,
    fetch: async (url) => {
      called = url
      return response(url, row)
    },
  })
  await t.revokeSessions(capture, id, { expected_version: 1 })
  assert.equal(called, apiRealm + '/admin/users/a%2Fb%3Fc%23d/revoke-sessions')
})
test('validation errors only expose allowlisted field identifiers', async () => {
  const t = createAdministrationTransport({
    apiRealm,
    fetch: async (url) =>
      response(
        url,
        {
          detail: [
            {
              loc: ['body', 'new_password'],
              input: 'SECRET',
              msg: 'SECRET',
              ctx: { secret: 'SECRET' },
            },
            { loc: ['body', 'SECRET'] },
          ],
        },
        422,
      ),
  })
  await assert.rejects(
    t.logoutAll(capture),
    (e) =>
      e.code === 'validation_error' &&
      JSON.stringify(e.fields) === '["new_password"]' &&
      !JSON.stringify(e).includes('SECRET'),
  )
})
test('catalog validates concrete snapshots and accepts empty TechnicalAdmin', async () => {
  const t = createAdministrationTransport({
    apiRealm,
    fetch: async (url) =>
      response(url, {
        capabilities: ['users.read'],
        roles: [{ name: 'TechnicalAdmin', capabilities: [] }],
      }),
  })
  assert.deepEqual((await t.roles(capture)).roles[0].capabilities, [])
  for (const value of [
    { capabilities: ['*'], roles: [] },
    { capabilities: ['users.read'], roles: [{ name: 'X', capabilities: ['unknown'] }] },
  ]) {
    const bad = createAdministrationTransport({
      apiRealm,
      fetch: async (url) => response(url, value),
    })
    await assert.rejects(bad.roles(capture))
  }
})
test('page options, scope and continuation are validated', async () => {
  let calls = 0
  const t = createAdministrationTransport({
    apiRealm,
    fetch: async (url) => {
      calls++
      return response(url, {
        items: [{ location_id: 'z', organization_id: 'o', name: 'Z' }],
        next_cursor: 'z',
      })
    },
  })
  await assert.rejects(t.locations(capture, { limit: 201 }), (e) => e.code === 'invalid_request')
  assert.equal(calls, 0)
  await assert.rejects(t.locations(capture), (e) => e.code === 'invalid_response')
  await assert.rejects(
    t.locations({ ...capture, user: { ...user, location_id: 'l' } }, { limit: 1 }),
    (e) => e.code === 'invalid_response',
  )
  assert.equal((await t.locations(capture, { limit: 1 })).next_cursor, 'z')
})
test('late body completion cannot publish over replacement admission', async () => {
  let release,
    current = true
  const gate = new Promise((r) => (release = r))
  const t = createAdministrationTransport({
    apiRealm,
    fetch: async (url) => {
      const body = new ReadableStream({
        async start(controller) {
          await gate
          controller.enqueue(
            new TextEncoder().encode(JSON.stringify({ items: [], next_cursor: null })),
          )
          controller.close()
        },
      })
      const r = new Response(body, {
        headers: { 'content-type': 'application/json', 'cache-control': 'no-store' },
      })
      Object.defineProperty(r, 'url', { value: url })
      return r
    },
  })
  const pending = t.users({ ...capture, isCurrent: () => current })
  await new Promise((r) => setTimeout(r, 0))
  current = false
  release()
  await assert.rejects(pending, (e) => e.code === 'stale_request')
})
test('malformed current authentication refusals remain refusals', async () => {
  for (const status of [401, 403]) {
    const t = createAdministrationTransport({
      apiRealm,
      fetch: async (url) => {
        const r = new Response('{', {
          status,
          headers: { 'content-type': 'application/json', 'cache-control': 'no-store' },
        })
        Object.defineProperty(r, 'url', { value: url })
        return r
      },
    })
    await assert.rejects(
      t.users(capture),
      (e) => e.code === (status === 401 ? 'invalid_session' : 'capability_denied'),
    )
  }
})
test('URL normalization cannot redirect a target segment into another endpoint', async () => {
  let calls = 0
  const t = createAdministrationTransport({
    apiRealm,
    fetch: async () => {
      calls++
      throw Error('unexpected')
    },
  })
  await assert.rejects(
    t.revokeSessions(capture, '..', { expected_version: 1 }),
    (e) => e.code === 'invalid_request',
  )
  assert.equal(calls, 0)
})
test('oversized streamed bodies and mismatched success statuses fail closed', async () => {
  const huge = createAdministrationTransport({
    apiRealm,
    fetch: async (url) => response(url, { padding: 'x'.repeat(1048577) }),
  })
  await assert.rejects(huge.roles(capture), (e) => e.code === 'invalid_response')
  const wrong = createAdministrationTransport({
    apiRealm,
    fetch: async (url) => response(url, { items: [], next_cursor: null }, 201),
  })
  await assert.rejects(wrong.users(capture), (e) => e.code === 'invalid_response')
})
test('commands capture serialized input and authority before awaiting transport', async () => {
  let finish, body
  const pendingResponse = new Promise((resolve) => (finish = resolve))
  const row = { ...user, username: 'a', version: 2, is_owner: false, is_active: true }
  const t = createAdministrationTransport({
    apiRealm,
    fetch: async (url, init) => {
      body = init.body
      await pendingResponse
      return response(url, row)
    },
  })
  const patch = { expected_version: 1, capabilities: [] }
  const principal = { ...user, capabilities: [...user.capabilities] }
  const pending = t.updateUser({ ...capture, user: principal }, 'a', patch)
  patch.expected_version = 999
  patch.capabilities.push('injected')
  principal.organization_id = 'different'
  finish()
  await pending
  assert.deepEqual(JSON.parse(body), { expected_version: 1, capabilities: [] })
})
test('upgrade errors remain distinct from target version conflicts', async () => {
  const t = createAdministrationTransport({
    apiRealm,
    fetch: async (url) =>
      response(url, { error: { code: 'client_upgrade_required', message: 'ignored' } }, 409),
  })
  await assert.rejects(
    t.logoutAll(capture),
    (e) => e.code === 'client_upgrade_required' && e.message.includes('Actualiza'),
  )
})
test('timeout is bounded even when fetch ignores its abort signal', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  let finish
  const transport = createAdministrationTransport({
    apiRealm,
    fetch: () => new Promise((resolve) => (finish = resolve)),
  })
  const pending = transport.users(capture)
  const rejected = assert.rejects(pending, (e) => e.code === 'network_error')
  t.mock.timers.tick(10000)
  await rejected
  finish(response(apiRealm + '/admin/users?limit=50', { items: [], next_cursor: null }))
  await Promise.resolve()
})
for (const status of [401, 403]) {
  test(`received current ${status} remains a refusal when its body never settles`, async (t) => {
    t.mock.timers.enable({ apis: ['setTimeout'] })
    const transport = createAdministrationTransport({
      apiRealm,
      fetch: async (url) => {
        const r = new Response(new ReadableStream({ start() {}, cancel() {} }), {
          status,
          headers: { 'content-type': 'application/json', 'cache-control': 'no-store' },
        })
        Object.defineProperty(r, 'url', { value: url })
        return r
      },
    })
    const pending = transport.users(capture)
    await Promise.resolve()
    await Promise.resolve()
    t.mock.timers.tick(10000)
    await assert.rejects(
      pending,
      (e) =>
        e.status === status &&
        e.code === (status === 401 ? 'invalid_session' : 'capability_denied'),
    )
  })
  test(`received current ${status} remains a refusal without JSON or cache headers`, async () => {
    const transport = createAdministrationTransport({
      apiRealm,
      fetch: async (url) => {
        const r = new Response('<html>untrusted text</html>', { status })
        Object.defineProperty(r, 'url', { value: url })
        return r
      },
    })
    await assert.rejects(
      transport.users(capture),
      (e) =>
        e.status === status &&
        e.code === (status === 401 ? 'invalid_session' : 'capability_denied') &&
        !e.message.includes('untrusted'),
    )
  })
}

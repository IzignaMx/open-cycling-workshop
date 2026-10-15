import test from 'node:test'
import assert from 'node:assert/strict'
import { createAdministrationTransport } from '../../.tmp-administration/src/features/administration/transport.js'
import {
  canAdminister,
  validateUserDraft,
} from '../../.tmp-administration/src/features/administration/model.js'
import { oldCapabilities, quoteCapabilities, quoteCatalog } from './quote-catalog-fixture.mjs'
const legacy = [
  'customers.read',
  'customers.write',
  'bicycles.read',
  'bicycles.write',
  'orders.read',
  'orders.write',
  'inventory.read',
  'inventory.write',
  'sync.pull',
  'sync.push',
  'users.read',
  'users.write',
  'users.grants.write',
  'users.sessions.revoke',
  'users.credentials.reset',
  'locations.read',
  'locations.create',
]
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
        catalog_version: 2,
        legacy_wildcard_capabilities: legacy,
        capabilities: [...legacy, 'branding.read', 'branding.write'],
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
test('native fetch-compatible receiver is preserved for every connected administration request', async () => {
  const calls = []
  const transport = createAdministrationTransport({
    apiRealm,
    fetch: function (url, init) {
      // Browsers reject an options object as the receiver of unbound window.fetch.
      if (this !== globalThis) throw new TypeError('Illegal invocation')
      calls.push(url)
      const value = url.endsWith('/admin/roles')
        ? {
            catalog_version: 2,
            legacy_wildcard_capabilities: legacy,
            capabilities: [...legacy, 'branding.read', 'branding.write'],
            roles: [{ name: 'TechnicalAdmin', capabilities: [] }],
          }
        : { items: [], next_cursor: null }
      return Promise.resolve(response(url, value, init.method === 'POST' ? 204 : 200))
    },
  })
  await transport.roles(capture)
  await transport.users(capture)
  await transport.locations(capture)
  await transport.logoutAll(capture)
  assert.equal(calls.length, 4)
})

test('fresh twenty-two and stale nineteen literal catalogs retain the v2 transport shape', async () => {
  const old = quoteCatalog(false)
  for (const includeQuotes of [false, true]) {
    const catalog = quoteCatalog(includeQuotes)
    const before = structuredClone(catalog)
    const calls = []
    const transport = createAdministrationTransport({
      apiRealm,
      fetch: async (url, init) => {
        calls.push([url, init])
        return response(url, catalog)
      },
    })
    const parsed = await transport.roles(capture)
    assert.deepEqual(parsed, before)
    assert.deepEqual(catalog, before)
    assert.equal(parsed.catalog_version, 2)
    assert.equal(parsed.capabilities.length, includeQuotes ? 22 : 19)
    assert.deepEqual(parsed.legacy_wildcard_capabilities, legacy)
    assert.deepEqual(
      parsed.roles.filter((role) => role.name !== 'Owner'),
      old.roles.filter((role) => role.name !== 'Owner'),
    )
    assert.deepEqual(
      parsed.roles.find((role) => role.name === 'Owner').capabilities,
      parsed.capabilities,
    )
    assert.deepEqual(parsed.roles.find((role) => role.name === 'TechnicalAdmin').capabilities, [])
    assert.equal(calls.length, 1)
    const [url, init] = calls[0]
    assert.equal(url, 'https://example.test/api/v2/admin/roles')
    assert.equal(init.method, 'GET')
    assert.equal(init.cache, 'no-store')
    assert.equal(init.credentials, 'omit')
    assert.equal(init.redirect, 'error')
    assert.equal(init.referrerPolicy, 'no-referrer')
    assert.equal(init.headers.Authorization, 'Bearer captured')
    assert.equal(Object.hasOwn(init.headers, 'X-OCWP-Write-Protocol'), false)
    const actor = { ...user, capabilities: quoteCatalog().capabilities }
    for (const grant of quoteCapabilities) {
      const target = {
        ...user,
        username: 'a',
        is_active: true,
        is_owner: false,
        version: 1,
        capabilities: [grant],
      }
      assert.equal(validateUserDraft(target, parsed).length === 0, includeQuotes)
      assert.equal(canAdminister(actor, target, target, 'owner', parsed), includeQuotes)
    }
  }
})

test('full current owner creation and explicit replacement transmit every grant on unchanged v1 routes', async () => {
  const catalog = quoteCatalog()
  const capabilities = [...catalog.capabilities].reverse()
  const fullOwner = {
    ...user,
    username: 'a',
    capabilities,
    version: 4,
    is_owner: true,
    is_active: true,
  }
  const source = { ...capture, user: fullOwner }
  const create = {
    username: 'a',
    display_name: 'A',
    password: 'synthetic-password',
    location_id: null,
    capabilities,
    is_owner: true,
  }
  const replace = { expected_version: 3, capabilities }
  const before = structuredClone({ create, replace })
  const calls = []
  const transport = createAdministrationTransport({
    apiRealm,
    fetch: async (url, init) => {
      calls.push([url, init])
      return response(url, fullOwner, init.method === 'POST' ? 201 : 200)
    },
  })
  assert.deepEqual(await transport.createUser(source, create), fullOwner)
  assert.deepEqual(await transport.updateUser(source, user.user_id, replace), fullOwner)
  assert.deepEqual(
    calls.map(([url, init]) => [url, init.method]),
    [
      [`${apiRealm}/admin/users`, 'POST'],
      [`${apiRealm}/admin/users/a`, 'PATCH'],
    ],
  )
  assert.deepEqual(JSON.parse(calls[0][1].body), create)
  assert.deepEqual(JSON.parse(calls[1][1].body), replace)
  assert.deepEqual({ create, replace }, before)
  for (const [, init] of calls) {
    assert.equal(init.headers['X-OCWP-Write-Protocol'], '1')
    assert.equal(init.cache, 'no-store')
    assert.equal(Object.hasOwn(JSON.parse(init.body), 'role'), false)
  }
})

const invalidQuoteCatalogs = [
  ['legacy catalog version', (catalog) => (catalog.catalog_version = 1)],
  ['unnegotiated catalog version', (catalog) => (catalog.catalog_version = 3)],
  ['missing wildcard snapshot', (catalog) => delete catalog.legacy_wildcard_capabilities],
  ['additional top-level field', (catalog) => (catalog.unknown = true)],
  ['duplicate catalog grant', (catalog) => catalog.capabilities.push('quotes.read')],
  ['non-string catalog grant', (catalog) => catalog.capabilities.push(null)],
  ['wildcard in concrete catalog', (catalog) => catalog.capabilities.push('*')],
  ['missing legacy catalog grant', (catalog) => catalog.capabilities.shift()],
  ['narrowed legacy wildcard', (catalog) => catalog.legacy_wildcard_capabilities.pop()],
  [
    'duplicate legacy wildcard grant',
    (catalog) => catalog.legacy_wildcard_capabilities.push('orders.read'),
  ],
  ...['branding.read', ...quoteCapabilities].map((grant) => [
    `widened legacy wildcard with ${grant}`,
    (catalog) => catalog.legacy_wildcard_capabilities.push(grant),
  ]),
  ['duplicate role grant', (catalog) => catalog.roles[0].capabilities.push('quotes.write')],
  ['wildcard role grant', (catalog) => catalog.roles[0].capabilities.push('*')],
  ['unknown role grant', (catalog) => catalog.roles[0].capabilities.push('quotes.unknown')],
  [
    'quote role grants outside stale catalog',
    (catalog) => (catalog.capabilities = [...oldCapabilities]),
  ],
  ['duplicate role name', (catalog) => catalog.roles.push({ ...catalog.roles[0] })],
  ['additional role field', (catalog) => (catalog.roles[0].unknown = true)],
]
for (const [reason, mutate] of invalidQuoteCatalogs) {
  test(`quote catalog parsing fails closed for ${reason}`, async () => {
    const malformed = quoteCatalog()
    mutate(malformed)
    const before = structuredClone(malformed)
    const transport = createAdministrationTransport({
      apiRealm,
      fetch: async (url) => response(url, malformed),
    })
    await assert.rejects(transport.roles(capture), (error) => error.code === 'invalid_response')
    assert.deepEqual(malformed, before)
  })
}

test('quote-aware user parsing refuses duplicate historical grants without rewriting the snapshot', async () => {
  const row = {
    ...user,
    username: 'a',
    capabilities: [...oldCapabilities, 'orders.read'],
    version: 4,
    is_owner: true,
    is_active: true,
  }
  const before = structuredClone(row)
  const transport = createAdministrationTransport({
    apiRealm,
    fetch: async (url) => response(url, { items: [row], next_cursor: null }),
  })
  await assert.rejects(transport.users(capture), (error) => error.code === 'invalid_response')
  assert.deepEqual(row, before)
})

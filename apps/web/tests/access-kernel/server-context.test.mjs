import test from 'node:test'
import assert from 'node:assert/strict'
import { createServerContextAdapter } from '../../.tmp-kernel/src/access-kernel/server-context.js'
const now = Date.parse('2026-10-14T10:00:00Z')
const realm = 'https://example.test/api/v1'
const identity = () => ({
  apiRealm: realm,
  organizationId: 'org',
  userId: 'A',
  selectedLocationId: 'loc',
  deviceGeneration: 1,
  tabAttemptId: 'attempt',
  sessionHandle: 'session-A',
})
const wire = () => ({
  protocol: 1,
  principal: { api_realm: null, organization_id: 'org', user_id: 'A' },
  account_location_id: 'loc',
  selected_location_id: 'loc',
  capabilities: ['customers.read'],
  authorization_epoch: 'a'.repeat(43),
  policy_revision: 'ocwp-access-baseline-1',
  verified_at: new Date(now).toISOString(),
  offline_until: new Date(now + 3600000).toISOString(),
  snapshot_protocol: null,
})
function response(body = wire(), options = {}) {
  return {
    ok: true,
    status: 200,
    redirected: false,
    url: `${realm}/auth/context?selected_location_id=loc`,
    headers: new Headers({ 'content-type': 'application/json', 'cache-control': 'no-store' }),
    json: async () => body,
    ...options,
  }
}
function setup(fetch = async () => response(), clock = () => now) {
  return createServerContextAdapter({ apiRealm: realm, fetch, now: clock })
}
const request = (adapter, overrides = {}) =>
  adapter.verify({
    identity: identity(),
    bearerToken: 'captured-token-A',
    isCurrent: () => true,
    ...overrides,
  })
test('null server realm binds to configured realm and null snapshot never activates', async () => {
  const result = await request(setup())
  assert.equal(result.state, 'BASELINE_REQUIRED')
  assert.equal(result.context.principal.apiRealm, realm)
  assert.deepEqual(result.context.capabilities, ['customers.read'])
  assert.equal(result.context.snapshotProtocol, null)
  assert.ok(Object.isFrozen(result.context.capabilities))
  assert.ok(!JSON.stringify(result).includes('captured-token'))
})
for (const [name, mutate] of [
  [
    'extra wire field',
    (v) => {
      v.role = 'owner'
    },
  ],
  [
    'missing nullable field',
    (v) => {
      delete v.account_location_id
    },
  ],
  [
    'extra principal field',
    (v) => {
      v.principal.role = 'owner'
    },
  ],
  [
    'realm injection',
    (v) => {
      v.principal.api_realm = realm
    },
  ],
  [
    'user mismatch',
    (v) => {
      v.principal.user_id = 'B'
    },
  ],
  [
    'organization mismatch',
    (v) => {
      v.principal.organization_id = 'foreign'
    },
  ],
  [
    'location mismatch',
    (v) => {
      v.selected_location_id = 'foreign'
    },
  ],
  [
    'account scope mismatch',
    (v) => {
      v.account_location_id = 'foreign'
    },
  ],
  [
    'missing principal',
    (v) => {
      v.principal = null
    },
  ],
  [
    'invalid protocol',
    (v) => {
      v.protocol = '1'
    },
  ],
  [
    'future policy',
    (v) => {
      v.policy_revision = 'future'
    },
  ],
  [
    'premature activation',
    (v) => {
      v.snapshot_protocol = 'baseline-v1'
    },
  ],
  [
    'wildcard',
    (v) => {
      v.capabilities = ['*']
    },
  ],
  [
    'duplicate grant',
    (v) => {
      v.capabilities = ['orders.read', 'orders.read']
    },
  ],
  [
    'wrong grant type',
    (v) => {
      v.capabilities = [false]
    },
  ],
  [
    'empty epoch',
    (v) => {
      v.authorization_epoch = ''
    },
  ],
  [
    'future clock',
    (v) => {
      v.verified_at = new Date(now + 1).toISOString()
    },
  ],
  [
    'expired lease',
    (v) => {
      v.offline_until = new Date(now).toISOString()
    },
  ],
  [
    'unbounded lease',
    (v) => {
      v.offline_until = new Date(now + 28800001).toISOString()
    },
  ],
  [
    'normalized bad date',
    (v) => {
      v.verified_at = '2026-02-30T00:00:00Z'
    },
  ],
  [
    'ambiguous local date',
    (v) => {
      v.verified_at = '2026-10-14T10:00:00'
    },
  ],
])
  test(`fails closed: ${name}`, async () => {
    const body = wire()
    mutate(body)
    await assert.rejects(
      request(setup(async () => response(body))),
      /Server context verification failed/,
    )
  })
test('empty, write-only and asymmetric literal grants are never expanded', async () => {
  for (const capabilities of [[], ['orders.write'], ['sync.pull', 'customers.read']]) {
    const body = { ...wire(), capabilities, account_location_id: null }
    const result = await request(setup(async () => response(body)))
    assert.deepEqual(result.context.capabilities, capabilities)
  }
})
test('checks expected epoch without computing authority from client claims', async () => {
  await assert.rejects(
    request(setup(), { identity: { ...identity(), expectedAuthorizationEpoch: 'b'.repeat(43) } }),
  )
})
test('captures token, identity and configured destination before async work', async () => {
  let release
  const barrier = new Promise((resolve) => {
    release = resolve
  })
  let observed
  const adapter = setup(async (url, init) => {
    observed = { url, init }
    await barrier
    return response()
  })
  const input = { identity: identity(), bearerToken: 'captured-token-A', isCurrent: () => true }
  const pending = adapter.verify(input)
  input.identity.userId = 'B'
  input.bearerToken = 'new-token-B'
  release()
  const result = await pending
  assert.equal(result.identity.userId, 'A')
  assert.equal(observed.init.headers.Authorization, 'Bearer captured-token-A')
  assert.equal(observed.url, `${realm}/auth/context?selected_location_id=loc`)
  for (const [key, value] of Object.entries({
    cache: 'no-store',
    redirect: 'error',
    credentials: 'omit',
    referrerPolicy: 'no-referrer',
  }))
    assert.equal(observed.init[key], value)
})
test('late response cannot supersede a newer request, even same generation', async () => {
  let release
  const barrier = new Promise((resolve) => {
    release = resolve
  })
  let calls = 0
  const adapter = setup(async () => {
    if (++calls === 1) await barrier
    return response()
  })
  const old = request(adapter)
  assert.equal((await request(adapter)).state, 'BASELINE_REQUIRED')
  release()
  await assert.rejects(old)
})
for (const boundary of ['fetch', 'body'])
  for (const field of [
    'deviceGeneration',
    'tabAttemptId',
    'sessionHandle',
    'userId',
    'apiRealm',
    'organizationId',
    'selectedLocationId',
    'expectedAuthorizationEpoch',
  ])
    test(`rejects changed ${field} during ${boundary}`, async () => {
      const active = { ...identity(), expectedAuthorizationEpoch: 'a'.repeat(43) }
      let release
      const barrier = new Promise((resolve) => {
        release = resolve
      })
      const adapter = setup(async () => {
        if (boundary === 'fetch') await barrier
        return response(wire(), {
          json: async () => {
            if (boundary === 'body') await barrier
            return wire()
          },
        })
      })
      const pending = request(adapter, {
        identity: active,
        isCurrent: (captured) =>
          Object.keys(captured).every((key) => captured[key] === active[key]),
      })
      await Promise.resolve()
      active[field] = field === 'deviceGeneration' ? 2 : 'changed'
      release()
      await assert.rejects(pending)
    })
test('invalidation rejects pending verification', async () => {
  let release
  const barrier = new Promise((resolve) => {
    release = resolve
  })
  const adapter = setup(async () => {
    await barrier
    return response()
  })
  const pending = request(adapter)
  adapter.invalidate()
  release()
  await assert.rejects(pending)
})
for (const options of [
  { redirected: true },
  { url: 'https://foreign.test' },
  { ok: false, status: 401 },
  { headers: new Headers({ 'content-type': 'application/json' }) },
  { headers: new Headers({ 'content-type': 'text/html', 'cache-control': 'no-store' }) },
])
  test('rejects unsafe transport response', async () => {
    await assert.rejects(request(setup(async () => response(wire(), options))))
  })
test('sanitizes transport failures containing sensitive information', async () => {
  await assert.rejects(
    request(
      setup(async () => {
        throw new Error('captured-token-A')
      }),
    ),
    { message: 'Server context verification failed' },
  )
})
test('rejects clock rollback and expiry while reading body', async () => {
  for (const finish of [now - 1, now + 3600000, NaN]) {
    let ticks = 0
    await assert.rejects(request(setup(undefined, () => (++ticks === 1 ? now : finish))))
  }
})
test('microsecond expiry truncates conservatively and UTC offset is accepted', async () => {
  const body = {
    ...wire(),
    verified_at: '2026-10-14T10:00:00.000000+00:00',
    offline_until: '2026-10-14T10:01:00.123999Z',
  }
  assert.equal(
    (await request(setup(async () => response(body)))).context.offlineUntil,
    '2026-10-14T10:01:00.123Z',
  )
})
for (const badRealm of [
  `${realm}/`,
  `${realm}?token=x`,
  'https://user:password@example.test/api/v1',
  'https://EXAMPLE.test/api/v1',
  'javascript:alert(1)',
])
  test('rejects noncanonical configured realm', () => {
    assert.throws(() => createServerContextAdapter({ apiRealm: badRealm, fetch, now: () => now }))
  })
test('mismatched configured realm never sends credentials', async () => {
  let sent = false
  await assert.rejects(
    request(
      setup(async () => {
        sent = true
        return response()
      }),
      { identity: { ...identity(), apiRealm: 'https://other.test/api/v1' } },
    ),
  )
  assert.equal(sent, false)
})

test('sanitizes an injected clock failure', async () => {
  await assert.rejects(
    request(
      setup(undefined, () => {
        throw new Error('sensitive clock detail')
      }),
    ),
    { message: 'Server context verification failed' },
  )
})

test('actual administration concrete multi-segment grants survive literally', async () => {
  // Literal capabilities emitted by the actual FastAPI seeded administration identity.
  const capabilities = [
    'bicycles.read',
    'bicycles.write',
    'customers.read',
    'customers.write',
    'inventory.read',
    'inventory.write',
    'locations.create',
    'locations.read',
    'orders.read',
    'orders.write',
    'sync.pull',
    'sync.push',
    'users.credentials.reset',
    'users.grants.write',
    'users.read',
    'users.sessions.revoke',
    'users.write',
  ]
  const result = await request(setup(async () => response({ ...wire(), capabilities })))
  assert.deepEqual(result.context.capabilities, capabilities)
  assert.equal(result.context.snapshotProtocol, null)
  assert.equal(result.state, 'BASELINE_REQUIRED')
})
for (const grant of ['users..read', 'users.credentials.*', '.users.read', 'users.read.', 'users'])
  test(`concrete grant grammar rejects ${grant}`, async () => {
    await assert.rejects(request(setup(async () => response({ ...wire(), capabilities: [grant] }))))
  })

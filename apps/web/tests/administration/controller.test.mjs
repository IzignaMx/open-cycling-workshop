import assert from 'node:assert/strict'
import test from 'node:test'
import { AdministrationHttpError } from '../../.tmp-administration/src/features/administration/transport.js'
import { AdministrationController } from '../../.tmp-administration/src/features/administration/controller.js'

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
const catalog = {
  catalog_version: 2,
  legacy_wildcard_capabilities: legacy,
  capabilities: [...legacy, 'branding.read', 'branding.write'],
  roles: [],
}
const actor = {
  user_id: 'actor',
  organization_id: 'org',
  location_id: null,
  display_name: 'Actor',
  capabilities: ['users.read', 'locations.read', 'locations.create'],
}
function setup(http = {}, user = actor) {
  let state = { phase: 'connected', user, generation: 1, message: null },
    listeners = new Set(),
    current = true
  const capture = {
    token: 'synthetic',
    user,
    apiRealm: 'http://localhost/api',
    signal: new AbortController().signal,
    isCurrent: () => current,
  }
  const runtime = {
    getAccountSnapshot: () => state,
    subscribeAccount: (fn) => {
      listeners.add(fn)
      return () => listeners.delete(fn)
    },
    verifyAccount: async () => {},
    captureAccount: () => capture,
    invalidateAccount: (source) => {
      if (source) assert.equal(source, capture)
      invalidate()
    },
    suspendAccountCommand: async (source) => {
      assert.equal(source, capture)
      return capture
    },
    completeAccountCommand: async (source) => {
      assert.equal(source, capture)
      invalidate()
    },
    logout: async () => invalidate(),
  }
  const invalidate = () => {
    current = false
    state = { phase: 'unverified', user: null, generation: 2, message: null }
    for (const fn of listeners) fn()
  }
  const transport = {
    users: async () => ({ items: [], next_cursor: null }),
    roles: async () => catalog,
    locations: async () => ({ items: [], next_cursor: null }),
    ...http,
  }
  return {
    controller: new AdministrationController(runtime, transport),
    invalidate,
    capture,
    runtime,
  }
}
const row = {
  user_id: 'other',
  organization_id: 'org',
  location_id: null,
  username: 'other',
  display_name: 'Other',
  capabilities: [],
  is_active: true,
  is_owner: false,
  version: 1,
}
test('stale directory result cannot repopulate invalidated account', async () => {
  let resolve
  const pending = new Promise((r) => (resolve = r))
  const { controller, invalidate } = setup({ users: () => pending })
  const read = controller.loadUsers()
  invalidate()
  resolve({ items: [row], next_cursor: null })
  await read
  assert.deepEqual(controller.getSnapshot().users, [])
  controller.dispose()
})
test('latest directory page wins independently of request order', async () => {
  const answers = []
  const { controller } = setup({ users: () => new Promise((r) => answers.push(r)) })
  const first = controller.loadUsers()
  const second = controller.loadUsers({ afterId: 'cursor' })
  answers[1]({ items: [row], next_cursor: null })
  await second
  answers[0]({ items: [], next_cursor: null })
  await first
  assert.equal(controller.getSnapshot().users[0].user_id, 'other')
  controller.dispose()
})
test('lost create response stays unconfirmed with no automatic retry', async () => {
  let calls = 0
  const { controller } = setup({
    createLocation: async () => {
      calls++
      throw new Error('synthetic private server input')
    },
  })
  await controller.createLocation('New')
  assert.equal(calls, 1)
  assert.equal(controller.getSnapshot().result, 'uncertain')
  assert.ok(!JSON.stringify(controller.getSnapshot()).includes('synthetic private'))
  controller.dispose()
})
test('duplicate command submits share no second dispatch', async () => {
  let resolve,
    calls = 0
  const { controller } = setup({
    createLocation: () => {
      calls++
      return new Promise((r) => (resolve = r))
    },
  })
  const first = controller.createLocation('New')
  const second = controller.createLocation('New')
  assert.equal(calls, 1)
  resolve({ location_id: 'loc', organization_id: 'org', name: 'New' })
  await Promise.all([first, second])
  controller.dispose()
})
test('owner continuation is single-flight until its bounded page settles', async () => {
  let calls = 0,
    resolve
  const { controller } = setup({
    users: () => {
      calls++
      return new Promise((r) => (resolve = r))
    },
  })
  const first = controller.continueOwnerLookup(),
    second = controller.continueOwnerLookup()
  assert.equal(calls, 1)
  resolve({ items: [], next_cursor: null })
  await Promise.all([first, second])
  controller.dispose()
})
test('inconsistent current self-row revokes previously established owner hints', async () => {
  let count = 0
  const self = { ...row, user_id: actor.user_id, capabilities: actor.capabilities, is_owner: true }
  const { controller } = setup({
    users: async () => ({ items: [{ ...self, is_active: count++ === 0 }], next_cursor: null }),
  })
  await controller.loadUsers()
  assert.equal(controller.getSnapshot().ownerHint, 'owner')
  await controller.loadUsers()
  assert.equal(controller.getSnapshot().ownerHint, 'unknown')
  assert.equal(controller.getSnapshot().account.phase, 'unverified')
  controller.dispose()
})
test('self commands return the opaque runtime handle rather than a derived transport wrapper', async () => {
  let calls = 0
  const { controller } = setup({
    logoutAll: async () => {
      calls++
    },
  })
  await controller.logoutAll()
  assert.equal(calls, 1)
  assert.equal(controller.getSnapshot().account.phase, 'unverified')
  controller.dispose()
})
test('late 401 after account invalidation cannot clear or publish into replacement account', async () => {
  let reject
  const { controller, invalidate, runtime } = setup({
    users: () => new Promise((_, r) => (reject = r)),
  })
  let invalidations = 0
  runtime.invalidateAccount = () => invalidations++
  const pending = controller.loadUsers()
  invalidate()
  reject(new AdministrationHttpError('invalid_session', 401))
  await pending
  assert.equal(invalidations, 0)
  assert.equal(controller.getSnapshot().message, null)
  controller.dispose()
})
test('dedicated suspended self handle survives intentional feature reset before dispatch', async () => {
  let dispatched = null,
    completed = null
  const { controller, runtime, capture, invalidate } = setup({
    logoutAll: async (source) => {
      dispatched = source
    },
  })
  const suspended = { ...capture, signal: new AbortController().signal, isCurrent: () => true }
  runtime.suspendAccountCommand = async (source) => {
    assert.equal(source, capture)
    invalidate()
    return suspended
  }
  runtime.completeAccountCommand = async (source, outcome) => {
    assert.equal(source, suspended)
    completed = outcome
  }
  await controller.logoutAll()
  assert.equal(dispatched, suspended)
  assert.equal(completed, 'success')
  controller.dispose()
})
test('lock failure sends no self command and exposes no error inputs', async () => {
  let dispatched = 0
  const { controller, runtime } = setup({ logoutAll: async () => dispatched++ })
  runtime.suspendAccountCommand = async () => {
    throw new Error('private lock diagnostic')
  }
  await controller.logoutAll()
  assert.equal(dispatched, 0)
  assert.ok(!JSON.stringify(controller.getSnapshot()).includes('private lock'))
  controller.dispose()
})
test('credential commands never place passwords in observable snapshots', async () => {
  const { controller } = setup({
    changePassword: async () => {
      throw new Error('private-new-password')
    },
  })
  await controller.changePassword('private-current-password', 'private-new-password')
  const serialized = JSON.stringify(controller.getSnapshot())
  assert.ok(!serialized.includes('private-'))
  controller.dispose()
})
for (const status of [401, 403])
  test(`current ${status} invalidates via exact runtime handle for reads and commands`, async () => {
    for (const command of [false, true]) {
      const error = new AdministrationHttpError(
        status === 401 ? 'invalid_session' : 'capability_denied',
        status,
      )
      const { controller } = setup(
        command
          ? {
              createLocation: async () => {
                throw error
              },
            }
          : {
              users: async () => {
                throw error
              },
            },
      )
      await (command ? controller.createLocation('Name') : controller.loadUsers())
      assert.equal(controller.getSnapshot().account.phase, 'unverified')
      controller.dispose()
    }
  })
test('local logout honors injected dirty-form decision', async () => {
  const { runtime } = setup()
  let logouts = 0
  runtime.logout = async () => {
    logouts++
  }
  const controller = new AdministrationController(runtime, undefined, () => false)
  await controller.logout()
  assert.equal(logouts, 0)
  controller.dispose()
})
test('owner lookup refuses inconsistent self even before directory exhaustion', async () => {
  const self = {
    ...row,
    user_id: actor.user_id,
    capabilities: actor.capabilities,
    is_active: false,
  }
  const { controller } = setup({ users: async () => ({ items: [self], next_cursor: 'later' }) })
  await controller.continueOwnerLookup()
  assert.equal(controller.getSnapshot().account.phase, 'unverified')
  controller.dispose()
})
test('matching suspended 401 clears the session instead of retaining a refused token', async () => {
  let invalidated = null,
    completed = null
  const { controller, runtime, capture } = setup({
    logoutAll: async () => {
      throw new AdministrationHttpError('invalid_session', 401)
    },
  })
  runtime.invalidateAccount = (source, reason) => {
    assert.equal(source, capture)
    invalidated = reason
  }
  runtime.completeAccountCommand = async (_source, outcome) => {
    completed = outcome
  }
  await controller.logoutAll()
  assert.equal(invalidated, 'invalid_session')
  assert.equal(completed, null)
  controller.dispose()
})
const writer = {
  ...actor,
  capabilities: [...actor.capabilities, 'users.write', 'users.grants.write'],
}
const createInput = {
  username: 'new',
  display_name: 'New',
  location_id: null,
  capabilities: [],
  password: 'synthetic-password',
}
async function writerSetup(http = {}) {
  const env = setup({ roles: async () => catalog, ...http }, writer)
  await env.controller.loadCatalog()
  return env
}
test('only the exact successful current create and update return confirmed receipts', async () => {
  const { controller } = await writerSetup({
    createUser: async () => row,
    updateUser: async () => ({ ...row, version: 2 }),
  })
  assert.equal(await controller.createUser(createInput), 'confirmed')
  assert.equal(
    await controller.updateUser(row, { expected_version: 1, display_name: 'Changed' }),
    'confirmed',
  )
  controller.dispose()
})
test('stale success and duplicate submit never return a confirmed receipt', async () => {
  let resolve,
    calls = 0
  const { controller, invalidate } = await writerSetup({
    createUser: () => {
      calls++
      return new Promise((r) => (resolve = r))
    },
  })
  const first = controller.createUser(createInput)
  assert.equal(await controller.createUser(createInput), undefined)
  assert.equal(calls, 1)
  invalidate()
  resolve(row)
  assert.equal(await first, undefined)
  controller.dispose()
})
test('refused uncertain and unauthorized creates never return confirmed receipts', async () => {
  for (const failure of [
    new AdministrationHttpError('stale_user_version', 409),
    new AdministrationHttpError('capability_denied', 403),
    new Error('unconfirmed'),
  ]) {
    const { controller } = await writerSetup({
      createUser: async () => {
        throw failure
      },
    })
    assert.equal(await controller.createUser(createInput), undefined)
    controller.dispose()
  }
  let calls = 0
  const { controller } = setup({
    createUser: async () => {
      calls++
      return row
    },
  })
  assert.equal(await controller.createUser(createInput), undefined)
  assert.equal(calls, 0)
  controller.dispose()
})
test('success-publication and busy-cleanup invalidation suppress the receipt', async () => {
  for (const when of ['success', 'cleanup']) {
    const { controller, invalidate } = await writerSetup({ createUser: async () => row })
    const unsubscribe = controller.subscribe(() => {
      const snapshot = controller.getSnapshot()
      if (snapshot.result === 'success' && (when === 'success' || !snapshot.busy)) invalidate()
    })
    assert.equal(await controller.createUser(createInput), undefined)
    unsubscribe()
    controller.dispose()
  }
})
test('self closure and name rebind invalidation never produce form receipts', async () => {
  const { controller, runtime, invalidate } = await writerSetup({
    logoutAll: async () => {},
    updateUser: async () => ({ ...row, user_id: writer.user_id, version: 2 }),
  })
  runtime.updateAccountName = () => invalidate()
  assert.equal(
    await controller.updateUser(
      { ...row, user_id: writer.user_id },
      { expected_version: 1, display_name: 'Changed' },
    ),
    undefined,
  )
  controller.dispose()
  const self = setup({ logoutAll: async () => {} })
  assert.equal(await self.controller.logoutAll(), undefined)
  self.controller.dispose()
})

test('programmatic role selections become explicit v2 grants before legacy transport', async () => {
  let sent
  const { controller } = await writerSetup({
    roles: async () => ({ ...catalog, roles: [{ name: 'Viewer', capabilities: ['users.read'] }] }),
    createUser: async (_source, input) => {
      sent = input
      return row
    },
  })
  const input = { ...createInput }
  delete input.capabilities
  assert.equal(await controller.createUser({ ...input, role: 'Viewer' }), 'confirmed')
  assert.deepEqual(sent.capabilities, ['users.read'])
  assert.equal(Object.hasOwn(sent, 'role'), false)
  controller.dispose()
})

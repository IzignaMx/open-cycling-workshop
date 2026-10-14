import assert from 'node:assert/strict'
import test from 'node:test'
import { AdministrationHttpError } from '../../.tmp-administration/src/features/administration/transport.js'
import { AdministrationController } from '../../.tmp-administration/src/features/administration/controller.js'

const actor = {
  user_id: 'actor',
  organization_id: 'org',
  location_id: null,
  display_name: 'Actor',
  capabilities: ['users.read', 'locations.read', 'locations.create'],
}
function setup(http = {}) {
  let state = { phase: 'connected', user: actor, generation: 1, message: null },
    listeners = new Set(),
    current = true
  const capture = {
    token: 'synthetic',
    user: actor,
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
    roles: async () => ({ capabilities: [], roles: [] }),
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

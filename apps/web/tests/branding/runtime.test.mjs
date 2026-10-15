import test from 'node:test'
import assert from 'node:assert/strict'
import { BrandingDisplayController } from '../../.tmp-branding/src/features/branding/runtime.js'
import { BrandingHttpError } from '../../.tmp-branding/src/features/branding/transport.js'
const profile = {
  organization_id: 'org',
  location_id: 'loc',
  dataset_incarnation: 'incarnation',
  version: 1,
  logo_state: 'none',
}
function setup(overrides = {}) {
  let current = true,
    online = true,
    valid = true,
    stored = profile,
    readCalls = 0,
    writeCalls = 0,
    refusal = null
  const source = () =>
    current
      ? {
          token: 'synthetic',
          organizationId: 'org',
          locationId: 'loc',
          datasetIncarnation: 'incarnation',
          ticket: {},
          context: { capabilities: ['branding.read'] },
          binding: 'binding-' + online,
          online,
          isCurrent: () => current,
        }
      : null
  const env = {
    capture: source,
    validate: async () => valid,
    now: () => 100,
    repository: {
      read: async () => stored,
      write: async (_ticket, _ctx, value) => {
        writeCalls++
        stored = value
        return true
      },
    },
    transport: {
      read: async () => {
        readCalls++
        return profile
      },
    },
    refused: (_source, status) => {
      refusal = status
    },
    ...overrides,
  }
  const controller = new BrandingDisplayController(env)
  return {
    controller,
    env,
    deny: () => {
      current = false
      controller.clear()
    },
    offline: () => {
      online = false
      controller.reconcile()
    },
    invalidate: () => {
      valid = false
    },
    counts: () => ({ readCalls, writeCalls, refusal }),
  }
}
test('offline reads require runtime admission, never network; invalidation synchronously hides', async () => {
  const env = setup()
  env.offline()
  await new Promise((r) => setTimeout(r, 0))
  assert.equal(env.controller.getSnapshot().profile.version, 1)
  assert.equal(env.counts().readCalls, 0)
  env.deny()
  assert.equal(env.controller.getSnapshot().profile, null)
})
test('late success after logout cannot persist or display and refresh is single flight', async () => {
  let release
  const env = setup({
    transport: {
      read: () =>
        new Promise((r) => {
          release = r
        }),
    },
  })
  const first = env.controller.refresh(true)
  await new Promise((r) => setTimeout(r, 0))
  await env.controller.refresh(true)
  env.deny()
  release({ ...profile, version: 2 })
  await first
  assert.equal(env.counts().writeCalls, 0)
  assert.equal(env.controller.getSnapshot().profile, null)
})
test('current refusal hides cached bytes and routes exact admission invalidation', async () => {
  for (const status of [401, 403]) {
    const env = setup({
      transport: {
        read: async () => {
          throw new BrandingHttpError('denied', status)
        },
      },
    })
    await env.controller.refresh(true)
    assert.equal(env.controller.getSnapshot().profile, null)
    assert.equal(env.counts().refusal, status)
  }
})
test('quota failure applies verified memory only and reports unavailable offline persistence', async () => {
  const env = setup({
    repository: {
      read: async () => null,
      write: async () => {
        throw new Error('quota')
      },
    },
  })
  await env.controller.refresh(true)
  assert.equal(env.controller.getSnapshot().profile.version, 1)
  assert.equal(env.controller.getSnapshot().cacheError, true)
})
test('damaged or unavailable cache does not prevent a fresh verified network read', async () => {
  const env = setup({
    repository: {
      read: async () => {
        throw new Error('damaged')
      },
      write: async () => {
        throw new Error('quota')
      },
    },
  })
  await env.controller.refresh(true)
  assert.equal(env.counts().readCalls, 1)
  assert.equal(env.controller.getSnapshot().profile.version, 1)
  assert.equal(env.controller.getSnapshot().cacheError, true)
})
test('an invalidated admitted owner cannot retain previously rendered branding', async () => {
  const env = setup()
  await env.controller.refresh(true)
  env.invalidate()
  await env.controller.refresh(true)
  assert.equal(env.controller.getSnapshot().profile, null)
})
test('cache quota error cannot let conflicting same-version content replace accepted memory', async () => {
  let value = { ...profile, display_name: 'First' }
  const env = setup({
    repository: {
      read: async () => null,
      write: async () => {
        throw Error('quota')
      },
    },
    transport: { read: async () => value },
  })
  await env.controller.refresh(true)
  value = { ...value, display_name: 'Conflicting' }
  await env.controller.refresh(true)
  assert.equal(env.controller.getSnapshot().profile.display_name, 'First')
})
test('older refresh paused after cache write cannot regress a newer confirmed profile', async () => {
  let release,
    reached,
    validations = 0
  const gate = new Promise((resolve) => {
    release = resolve
  })
  const entered = new Promise((resolve) => {
    reached = resolve
  })
  const env = setup({
    validate: async () => {
      if (++validations === 3) {
        reached()
        await gate
      }
      return true
    },
    repository: { read: async () => null, write: async () => true },
  })
  const older = env.controller.refresh(true)
  await entered
  await env.controller.confirmed({ ...profile, version: 2 })
  assert.equal(env.controller.getSnapshot().profile.version, 2)
  release()
  await older
  assert.equal(env.controller.getSnapshot().profile.version, 2)
})

test('forced requests coalesce into one freshly admitted trailing read with a finite budget', async () => {
  let release, entered, complete
  const gate = new Promise((resolve) => {
    release = resolve
  })
  const started = new Promise((resolve) => {
    entered = resolve
  })
  const finished = new Promise((resolve) => {
    complete = resolve
  })
  const times = []
  let now = 100,
    validations = 0
  const env = setup({
    now: () => now,
    validate: async () => {
      validations++
      return true
    },
    repository: {
      read: async (_ticket, _context, at) => {
        times.push(at)
        if (times.length === 1) {
          entered()
          await gate
          return null
        }
        // Further requests during the trailing flight cannot create a loop.
        for (let i = 0; i < 10; i++) void env.controller.refresh(true)
        return profile
      },
      write: async () => {
        assert.fail('offline write')
      },
    },
  })
  env.controller.subscribe(() => {
    // Consumer notifications must not turn the trailing request into a loop.
    if (env.controller.getSnapshot().loading || env.controller.getSnapshot().cached)
      void env.controller.refresh(true)
    if (env.controller.getSnapshot().cached && !env.controller.getSnapshot().loading) complete()
  })
  env.offline()
  await started
  for (let i = 0; i < 10; i++) await env.controller.refresh(true)
  now = 200
  release()
  await finished
  assert.deepEqual(times, [100, 200])
  assert.equal(validations, 2)
  assert.equal(env.counts().readCalls, 0)
})

for (const invalidation of ['clear', 'invalid admission', 'stale source']) {
  test(`queued force cannot survive ${invalidation}`, async () => {
    let release, entered
    const gate = new Promise((resolve) => {
      release = resolve
    })
    const started = new Promise((resolve) => {
      entered = resolve
    })
    let reads = 0,
      validations = 0,
      live = true
    const env = setup({
      validate: async () => ++validations === 1 || invalidation !== 'invalid admission',
      repository: {
        read: async () => {
          reads++
          entered()
          await gate
          return null
        },
        write: async () => {
          assert.fail('offline write')
        },
      },
    })
    const capture = env.env.capture
    env.env.capture = () => ({ ...capture(), online: false, isCurrent: () => live })
    const first = env.controller.refresh(true)
    await started
    await env.controller.refresh(true)
    if (invalidation === 'clear') env.deny()
    if (invalidation === 'stale source') live = false
    release()
    await first
    // A queued attempt validates before reading; invalid admission clears it.
    await Promise.resolve()
    assert.equal(reads, 1)
    assert.equal(env.controller.getSnapshot().profile, null)
  })
}

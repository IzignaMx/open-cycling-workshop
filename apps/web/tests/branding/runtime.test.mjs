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
  assert.notEqual(env.controller.getSnapshot().refreshSuggested, true)
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

test('completed local events coalesce during original and trailing offline reads without null loops', async () => {
  let reads = 0
  const release = [],
    entered = []
  const gates = [0, 1].map(
    (_, i) =>
      new Promise((resolve) => {
        release[i] = resolve
      }),
  )
  const started = [0, 1].map(
    (_, i) =>
      new Promise((resolve) => {
        entered[i] = resolve
      }),
  )
  const f = setup({
    repository: {
      read: async () => {
        const i = reads++
        if (i < 2) {
          entered[i]()
          await gates[i]
        }
        return null
      },
      write: async () => assert.fail('offline write'),
    },
  })
  f.offline()
  await started[0]
  for (let i = 0; i < 20; i++) f.controller.refreshOfflineAfterLocalActivity()
  release[0]()
  await started[1]
  for (let i = 0; i < 20; i++) f.controller.refreshOfflineAfterLocalActivity()
  release[1]()
  for (let i = 0; i < 10; i++) await new Promise((resolve) => setTimeout(resolve, 0))
  assert.equal(reads, 3, 'one owed read per flight; final null cannot self-enqueue')
  assert.equal(f.controller.getSnapshot().profile, null)
  assert.equal(f.counts().readCalls, 0)
})

test('local event never initiates online transport or a cache read with an already accepted profile', async () => {
  const f = setup()
  for (let i = 0; i < 20; i++) f.controller.refreshOfflineAfterLocalActivity()
  await Promise.resolve()
  assert.equal(f.counts().readCalls, 0)
  f.offline()
  await new Promise((resolve) => setTimeout(resolve, 0))
  assert.equal(f.controller.getSnapshot().cached, true)
  for (let i = 0; i < 20; i++) f.controller.refreshOfflineAfterLocalActivity()
  assert.equal(f.counts().readCalls, 0)
})

for (const edge of ['clear', 'takeover', 'invalid admission', 'online'])
  test(`owed offline activity refresh is discarded after ${edge}`, async () => {
    let release,
      entered,
      reads = 0,
      validations = 0,
      live = true,
      online = false,
      binding = 'same'
    const gate = new Promise((resolve) => {
        release = resolve
      }),
      started = new Promise((resolve) => {
        entered = resolve
      })
    const f = setup({
      capture: () =>
        live
          ? {
              online,
              binding,
              isCurrent: () => live,
              ticket: {},
              context: { capabilities: ['branding.read'] },
            }
          : null,
      validate: async () => ++validations === 1 || edge !== 'invalid admission',
      repository: {
        read: async () => {
          reads++
          entered()
          await gate
          return null
        },
        write: async () => assert.fail('offline write'),
      },
    })
    const first = f.controller.refresh(true)
    await started
    for (let i = 0; i < 10; i++) f.controller.refreshOfflineAfterLocalActivity()
    if (edge === 'clear') {
      live = false
      f.controller.clear()
    }
    if (edge === 'takeover') binding = 'new-owner'
    if (edge === 'online') online = true
    release()
    await first
    await new Promise((resolve) => setTimeout(resolve, 0))
    assert.equal(reads, 1)
    assert.equal(f.counts().readCalls, 0, 'owed local refresh cannot become an online fetch')
  })

const recoveryMessage =
  'No se pudo confirmar la marca compartida para esta vista. Puedes volver a consultarla.'
function brandingGate() {
  let release
  const promise = new Promise((resolve) => {
    release = resolve
  })
  return { promise, release }
}
const brandingTurn = () => new Promise((resolve) => setImmediate(resolve))

test('manual branding recovery reports refusal without retrying and clears after explicit success', async () => {
  let accepted = false,
    writes = 0,
    pending = null,
    entered = null
  const f = setup({
    repository: {
      read: async () => null,
      write: async () => {
        writes++
        entered?.release()
        if (pending) await pending.promise
        return accepted
      },
    },
  })
  assert.equal(f.controller.getSnapshot().refreshSuggested, false)
  await f.controller.refresh(true)
  assert.equal(f.controller.getSnapshot().refreshSuggested, true)
  assert.equal(f.controller.getSnapshot().message, recoveryMessage)
  assert.equal(f.controller.getSnapshot().profile, null)
  assert.equal(f.controller.getSnapshot().cacheError, false)
  await brandingTurn()
  await brandingTurn()
  assert.equal(f.counts().readCalls, 1)
  assert.equal(writes, 1, 'a refused write must not trigger an automatic request')

  pending = brandingGate()
  entered = brandingGate()
  const repeated = f.controller.refresh(true)
  await entered.promise
  assert.equal(f.controller.getSnapshot().loading, true)
  assert.equal(f.controller.getSnapshot().refreshSuggested, true)
  assert.equal(f.controller.getSnapshot().message, recoveryMessage)
  pending.release()
  await repeated
  assert.equal(f.controller.getSnapshot().loading, false)
  assert.equal(f.controller.getSnapshot().profile, null)
  assert.equal(f.controller.getSnapshot().refreshSuggested, true)
  assert.equal(writes, 2)

  accepted = true
  pending = null
  await f.controller.refresh(true)
  assert.equal(f.controller.getSnapshot().profile, profile)
  assert.equal(f.controller.getSnapshot().refreshSuggested, false)
  assert.equal(f.controller.getSnapshot().message, null)
  assert.equal(f.controller.getSnapshot().cacheError, false)
  await brandingTurn()
  assert.equal(f.counts().readCalls, 3)
  assert.equal(writes, 3)
})

test('manual branding recovery never replaces an accepted cached profile with a refused response', async () => {
  const f = setup({ repository: { read: async () => profile, write: async () => false } })
  await f.controller.refresh(true)
  assert.equal(f.controller.getSnapshot().profile, profile)
  assert.equal(f.controller.getSnapshot().cached, true)
  assert.notEqual(f.controller.getSnapshot().refreshSuggested, true)
  assert.equal(f.controller.getSnapshot().message, null)
  assert.equal(f.controller.getSnapshot().cacheError, false)
})

test('manual branding recovery preserves previously accepted memory when its refresh is refused', async () => {
  let accepted = true,
    value = profile
  const f = setup({
    repository: { read: async () => null, write: async () => accepted },
    transport: { read: async () => value },
  })
  await f.controller.refresh(true)
  const before = f.controller.getSnapshot()
  accepted = false
  value = { ...profile, version: 2 }
  await f.controller.refresh(true)
  assert.equal(f.controller.getSnapshot().profile, before.profile)
  assert.equal(f.controller.getSnapshot().cached, before.cached)
  assert.equal(f.controller.getSnapshot().message, before.message)
  assert.equal(f.controller.getSnapshot().cacheError, false)
  assert.notEqual(f.controller.getSnapshot().refreshSuggested, true)
})

for (const edge of ['logout', 'takeover']) {
  test(`manual branding recovery cannot publish a delayed refusal after ${edge}`, async () => {
    const pending = brandingGate(),
      entered = brandingGate()
    let binding = 'owner-A'
    const f = setup({
      repository: {
        read: async () => null,
        write: async () => {
          entered.release()
          await pending.promise
          return false
        },
      },
    })
    const capture = f.env.capture
    f.env.capture = () => {
      const source = capture()
      return source ? { ...source, binding } : null
    }
    const first = f.controller.refresh(true)
    await entered.promise
    if (edge === 'logout') f.deny()
    else binding = 'owner-B'
    pending.release()
    await first
    assert.equal(f.controller.getSnapshot().profile, null)
    assert.equal(f.controller.getSnapshot().message, null)
    assert.equal(f.controller.getSnapshot().cacheError, false)
    assert.notEqual(f.controller.getSnapshot().refreshSuggested, true)
  })
}

test('manual branding recovery revalidates admission after the refused write before suggesting refresh', async () => {
  let validations = 0
  const f = setup({
    validate: async () => ++validations < 3,
    repository: { read: async () => null, write: async () => false },
  })
  await f.controller.refresh(true)
  assert.equal(validations, 3)
  assert.equal(f.controller.getSnapshot().profile, null)
  assert.equal(f.controller.getSnapshot().message, null)
  assert.equal(f.controller.getSnapshot().cacheError, false)
  assert.notEqual(f.controller.getSnapshot().refreshSuggested, true)
})

test('manual branding recovery cannot overwrite a newer confirmation while the old write is pending', async () => {
  const pending = brandingGate(),
    entered = brandingGate(),
    newer = { ...profile, version: 2 }
  const f = setup({
    repository: {
      read: async () => null,
      write: async (_ticket, _context, value) => {
        if (value.version === 2) return true
        entered.release()
        await pending.promise
        return false
      },
    },
  })
  const old = f.controller.refresh(true)
  await entered.promise
  await f.controller.confirmed(newer)
  pending.release()
  await old
  assert.equal(f.controller.getSnapshot().profile, newer)
  assert.equal(f.controller.getSnapshot().message, null)
  assert.equal(f.controller.getSnapshot().cacheError, false)
  assert.notEqual(f.controller.getSnapshot().refreshSuggested, true)
})

test('manual branding recovery rechecks accepted memory after its own awaited admission validation', async (t) => {
  const pending = brandingGate(),
    newer = { ...profile, version: 2 }
  t.after(() => pending.release())
  let validations = 0
  const f = setup({
    validate: async () => {
      if (++validations === 3) await pending.promise
      return true
    },
    repository: {
      read: async () => null,
      write: async (_ticket, _context, value) => value.version === 2,
    },
  })
  const old = f.controller.refresh(true)
  await brandingTurn()
  assert.equal(validations, 3, 'refused write must revalidate before publishing its notice')
  await f.controller.confirmed(newer)
  pending.release()
  await old
  assert.equal(f.controller.getSnapshot().profile, newer)
  assert.equal(f.controller.getSnapshot().message, null)
  assert.equal(f.controller.getSnapshot().cacheError, false)
  assert.notEqual(f.controller.getSnapshot().refreshSuggested, true)
})

test('manual branding recovery cannot misclassify admission-validation failure as a quota exception', async () => {
  let validations = 0
  const f = setup({
    validate: async () => {
      if (++validations === 3) throw new Error('synthetic validation failure')
      return true
    },
    repository: { read: async () => null, write: async () => false },
  })
  await f.controller.refresh(true)
  assert.equal(validations, 3)
  assert.equal(f.controller.getSnapshot().profile, null)
  assert.equal(f.controller.getSnapshot().cacheError, false)
  assert.notEqual(f.controller.getSnapshot().refreshSuggested, true)
})

test('manual branding recovery notice clears when a fresh read admits an existing cached profile', async () => {
  let cached = null
  const f = setup({ repository: { read: async () => cached, write: async () => false } })
  await f.controller.refresh(true)
  assert.equal(f.controller.getSnapshot().refreshSuggested, true)
  cached = profile
  await f.controller.refresh(true)
  assert.equal(f.controller.getSnapshot().profile, profile)
  assert.equal(f.controller.getSnapshot().cached, true)
  assert.equal(f.controller.getSnapshot().refreshSuggested, false)
  assert.notEqual(f.controller.getSnapshot().message, recoveryMessage)
  assert.equal(f.controller.getSnapshot().cacheError, false)
})

test('manual branding recovery notice is cleared by logout, admission refusal and offline binding replacement', async () => {
  for (const edge of ['logout', 'invalid admission', 'offline']) {
    const f = setup({ repository: { read: async () => null, write: async () => false } })
    await f.controller.refresh(true)
    assert.equal(f.controller.getSnapshot().refreshSuggested, true)
    if (edge === 'logout') f.deny()
    if (edge === 'invalid admission') {
      f.invalidate()
      await f.controller.refresh(true)
    }
    if (edge === 'offline') {
      f.offline()
      await brandingTurn()
    }
    assert.equal(f.controller.getSnapshot().profile, null, edge)
    assert.equal(f.controller.getSnapshot().refreshSuggested, false, edge)
    assert.notEqual(f.controller.getSnapshot().message, recoveryMessage, edge)
    assert.equal(f.counts().readCalls, 1, edge)
  }
})

test('manual branding recovery rechecks the exact source after its awaited admission validation', async (t) => {
  for (const edge of ['logout', 'takeover']) {
    const pending = brandingGate()
    t.after(() => pending.release())
    let validations = 0,
      binding = 'owner-A'
    const f = setup({
      validate: async () => {
        if (++validations === 3) await pending.promise
        return true
      },
      repository: { read: async () => null, write: async () => false },
    })
    const capture = f.env.capture
    f.env.capture = () => {
      const source = capture()
      return source ? { ...source, binding } : null
    }
    const old = f.controller.refresh(true)
    await brandingTurn()
    assert.equal(validations, 3, edge)
    if (edge === 'logout') f.deny()
    else binding = 'owner-B'
    pending.release()
    await old
    assert.equal(f.controller.getSnapshot().profile, null, edge)
    assert.equal(f.controller.getSnapshot().message, null, edge)
    assert.equal(f.controller.getSnapshot().cacheError, false, edge)
    assert.notEqual(f.controller.getSnapshot().refreshSuggested, true, edge)
  }
})

test('manual branding recovery preserves a prior cache diagnostic through refusal and later cached admission', async () => {
  let readable = false
  const f = setup({
    repository: {
      read: async () => {
        if (!readable) throw new Error('synthetic cache read failure')
        return profile
      },
      write: async () => false,
    },
  })
  await f.controller.refresh(true)
  const cacheDiagnostic = 'No se pudo consultar la copia local de la marca.'
  assert.equal(f.controller.getSnapshot().refreshSuggested, true)
  assert.equal(f.controller.getSnapshot().profile, null)
  assert.equal(f.controller.getSnapshot().cacheError, true)
  assert.equal(f.controller.getSnapshot().message, cacheDiagnostic)

  readable = true
  await f.controller.refresh(true)
  assert.equal(f.controller.getSnapshot().profile, profile)
  assert.equal(f.controller.getSnapshot().cached, true)
  assert.equal(f.controller.getSnapshot().refreshSuggested, false)
  assert.equal(f.controller.getSnapshot().cacheError, true)
  assert.equal(f.controller.getSnapshot().message, cacheDiagnostic)
})

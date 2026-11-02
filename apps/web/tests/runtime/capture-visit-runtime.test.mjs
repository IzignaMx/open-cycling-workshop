import test from 'node:test'
import assert from 'node:assert/strict'
import { setup, login, api, response, user, until } from './runtime-fixture.mjs'

const channels = [
  {
    kind: 'customer',
    edit: 'editCaptureCustomer',
    submit: 'submitCaptureCustomer',
    repository: 'createCustomer',
    fields: { displayName: 'private-capture-draft', email: 'private@example.test', phone: '555' },
  },
  {
    kind: 'order',
    edit: 'editCaptureOrder',
    submit: 'submitCaptureOrder',
    repository: 'createOrder',
    fields: {
      customerId: 'historical-A',
      reportedProblem: 'private-capture-draft',
      intakeCondition: 'wet',
      accessories: 'lamp',
      priority: 'high',
      withBicycle: true,
      brand: 'private-brand',
      model: 'private-model',
    },
  },
]
const token = (f) => f.runtime.getSnapshot().capture.viewToken
function fill(f, channel) {
  for (const [field, value] of Object.entries(channel.fields))
    f.runtime[channel.edit](token(f), field, value)
}
async function ready(t, options) {
  const f = setup(t, options)
  f.runtime.scheduleSync = () => {}
  await login(f.runtime)
  return f
}
function observeMask(t, f) {
  const masked = []
  t.after(
    f.runtime.subscribe(() => {
      const snapshot = f.runtime.getSnapshot()
      if (snapshot.phase !== 'ready') masked.push(snapshot)
    }),
  )
  return () => {
    assert.ok(masked.length > 0)
    for (const snapshot of masked) {
      assert.equal(snapshot.capture, null)
      assert.equal(JSON.stringify(snapshot).includes('private-capture-draft'), false)
      assert.equal(JSON.stringify(snapshot).includes('private-brand'), false)
    }
  }
}
function barrier(f, channel, committed = false) {
  let release,
    reached,
    calls = 0
  const waiting = new Promise((resolve) => {
    release = resolve
  })
  const entered = new Promise((resolve) => {
    reached = resolve
  })
  const original = f.runtime.repositories[channel.repository].bind(f.runtime.repositories)
  f.runtime.repositories[channel.repository] = async (...args) => {
    calls++
    if (calls !== 1) throw new Error('second-capture-canary')
    const result = committed ? await original(...args) : null
    reached()
    await waiting
    if (committed) return result
    throw new Error('unknown-before-write-canary')
  }
  return { release, entered, calls: () => calls }
}
for (const channel of channels) {
  test(`capture runtime ${channel.kind}: reconnect masks private values, keeps draft, rejects old handlers`, async (t) => {
    const f = await ready(t)
    fill(f, channel)
    const oldView = token(f),
      checkMask = observeMask(t, f)
    let calls = 0
    f.runtime.repositories[channel.repository] = async () => {
      calls++
      throw new Error('unexpected dispatch')
    }
    const pending = f.runtime.reconnect()
    assert.equal(f.runtime.getSnapshot().capture, null)
    assert.equal(f.runtime.hasUnsentCaptures(), true)
    f.runtime[channel.edit](oldView, Object.keys(channel.fields)[0], 'late-old')
    await f.runtime[channel.submit](oldView)
    await pending
    const capture = f.runtime.getSnapshot().capture
    assert.deepEqual(capture[channel.kind].draft, channel.fields)
    assert.notEqual(token(f), oldView)
    await f.runtime[channel.submit](oldView)
    assert.equal(calls, 0)
    checkMask()
  })
  test(`capture runtime ${channel.kind}: real refresh hold and retry retain protected draft without exposure`, async (t) => {
    const f = await ready(t)
    fill(f, channel)
    const checkMask = observeMask(t, f),
      original = f.runtime.repositories.page.bind(f.runtime.repositories)
    f.runtime.repositories.page = async () => {
      throw new Error('private-read-canary')
    }
    assert.equal(await f.runtime.refresh(), false)
    assert.equal(f.runtime.getSnapshot().phase, 'held')
    assert.equal(f.runtime.getSnapshot().capture, null)
    assert.equal(f.runtime.hasUnsentCaptures(), true)
    f.runtime.repositories.page = original
    await f.runtime.retryVerification()
    await until(() => f.runtime.getSnapshot().phase === 'ready', 'retry baseline did not finish')
    assert.equal(f.runtime.getSnapshot().phase, 'ready')
    assert.deepEqual(f.runtime.getSnapshot().capture[channel.kind].draft, channel.fields)
    checkMask()
  })
  for (const operation of ['reconnect', 'logout'])
    test(`capture runtime ${channel.kind}: reentrant ${operation} before dispatch calls no repository`, async (t) => {
      const f = await ready(t)
      fill(f, channel)
      let calls = 0,
        change = null
      f.runtime.repositories[channel.repository] = async () => {
        calls++
        throw new Error('must not dispatch')
      }
      const unsubscribe = f.runtime.subscribe(() => {
        if (!change && f.runtime.getSnapshot().capture?.[channel.kind].busy) {
          change = Promise.resolve()
          change = f.runtime[operation]()
        }
      })
      try {
        await f.runtime[channel.submit](token(f))
        assert.ok(change)
        await change
        assert.equal(calls, 0)
        assert.equal(await f.database.operationJournal.count(), 0)
        if (operation === 'reconnect') {
          assert.deepEqual(f.runtime.getSnapshot().capture[channel.kind].draft, channel.fields)
          assert.equal(f.runtime.getSnapshot().capture[channel.kind].busy, false)
        } else {
          assert.equal(f.runtime.getSnapshot().capture, null)
          assert.equal(f.runtime.hasUnsentCaptures(), false)
        }
      } finally {
        unsubscribe()
      }
    })
  test(`capture runtime ${channel.kind}: committed old receipt cannot mutate new explicit login draft or protection`, async (t) => {
    const f = await ready(t)
    fill(f, channel)
    const held = barrier(f, channel, true),
      first = f.runtime[channel.submit](token(f))
    try {
      await held.entered
      const before = await f.database.operationJournal.toArray()
      assert.ok(before.length > 0)
      await f.runtime.logout()
      await login(f.runtime)
      fill(f, channel)
      await f.runtime[channel.submit](token(f))
      const replacement = f.runtime.getSnapshot().capture
      assert.equal(replacement[channel.kind].blocked, true)
      held.release()
      await first
      assert.deepEqual(f.runtime.getSnapshot().capture, replacement)
      assert.deepEqual(await f.database.operationJournal.toArray(), before)
      assert.equal(held.calls(), 2)
    } finally {
      held.release()
      await first
    }
  })
  test(`capture runtime ${channel.kind}: unknown cannot be cleared by invalid selection or same-scope retry`, async (t) => {
    const f = await ready(t)
    fill(f, channel)
    let calls = 0
    f.runtime.repositories[channel.repository] = async () => {
      calls++
      throw new Error('unknown')
    }
    await f.runtime[channel.submit](token(f))
    await f.runtime.selectWorkshop('not-authorized')
    await f.runtime.reconnect()
    await until(
      () => f.runtime.getSnapshot().phase === 'ready',
      'reconnect baseline did not finish',
    )
    await f.runtime[channel.submit](token(f))
    assert.equal(calls, 1)
    assert.equal(f.runtime.getSnapshot().capture[channel.kind].blocked, true)
  })
}
function mutableScopeServer() {
  const original = api()
  const state = { changed: false }
  return {
    state,
    fetch: async (url, init) => {
      const data = await (await original.fetch(url, init)).json()
      if (state.changed) {
        const context = new URL(url).pathname.endsWith('/auth/context') ? data : data.context
        if (context?.capabilities)
          context.capabilities = context.capabilities.filter((value) => value !== 'bicycles.write')
      }
      return response(url, data)
    },
  }
}
for (const protection of ['unsent', 'pending', 'unknown'])
  test(`capture runtime semantic mismatch ${protection}: irreversibly purges values with correct capture-only policy`, async (t) => {
    const server = mutableScopeServer(),
      f = await ready(t, { server }),
      channel = channels[0]
    fill(f, channel)
    const held = protection === 'unsent' ? null : barrier(f, channel)
    const first = held ? f.runtime.submitCaptureCustomer(token(f)) : null
    try {
      if (held) await held.entered
      if (protection === 'unknown') {
        held.release()
        await first
      }
      const journal = await f.database.operationJournal.toArray()
      server.state.changed = true
      await f.runtime.reconnect()
      await until(
        () => f.runtime.getSnapshot().phase === 'ready',
        'reconnect baseline did not finish',
      )
      assert.equal(f.runtime.getSnapshot().phase, 'ready')
      let capture = f.runtime.getSnapshot().capture
      assert.equal(capture.customer.draft.displayName, '')
      assert.equal(capture.order.draft.customerId, '')
      assert.equal(capture.customer.blocked, protection !== 'unsent')
      assert.equal(capture.order.blocked, protection !== 'unsent')
      assert.equal(
        capture.notice,
        protection === 'unsent'
          ? 'Los formularios anteriores no están disponibles en este contexto.'
          : 'Hay una captura pendiente de confirmar de la visita anterior. No la repitas; las nuevas capturas están bloqueadas en esta visita.',
      )
      if (held) {
        held.release()
        await first
      }
      server.state.changed = false
      await f.runtime.reconnect()
      await until(
        () => f.runtime.getSnapshot().phase === 'ready',
        'reconnect baseline did not finish',
      )
      capture = f.runtime.getSnapshot().capture
      assert.equal(capture.customer.draft.displayName, '')
      assert.equal(capture.customer.blocked, protection !== 'unsent')
      if (held) {
        await f.runtime.submitCaptureCustomer(token(f))
        assert.equal(held.calls(), 1)
      }
      assert.deepEqual(await f.database.operationJournal.toArray(), journal)
      // Capture-only policy does not revoke the unchanged low-level API's authority.
      assert.deepEqual(
        await f.runtime.createOrder({
          customerId: 'historical-A',
          reportedProblem: 'independent authorized order',
          intakeCondition: null,
          accessories: null,
          priority: 'normal',
          brand: null,
          model: null,
        }),
        { status: 'saved' },
      )
    } finally {
      if (held) {
        held.release()
        await first
      }
    }
  })
test('capture runtime automatic account-principal invalidation closes without a voluntary confirmation', async (t) => {
  const source = api()
  let changed = false
  const server = {
    fetch: async (url, init) =>
      new URL(url).pathname.endsWith('/auth/me') && changed
        ? response(url, user('B'))
        : source.fetch(url, init),
  }
  const f = await ready(t, { server })
  fill(f, channels[0])
  fill(f, channels[1])
  const old = token(f),
    checkMask = observeMask(t, f)
  changed = true
  await f.runtime.verifyAccount()
  assert.equal(f.runtime.getSnapshot().phase, 'locked')
  assert.equal(f.runtime.getSnapshot().capture, null)
  assert.equal(f.runtime.hasUnsentCaptures(), false)
  assert.equal(f.runtime.sessionStore.getToken(), null)
  await f.runtime.submitCaptureCustomer(old)
  assert.equal(await f.database.operationJournal.count(), 0)
  checkMask()
})

test('capture runtime temporary security-command suspension masks but retains same-scope input', async (t) => {
  const f = await ready(t)
  fill(f, channels[0])
  fill(f, channels[1])
  const checkMask = observeMask(t, f)
  await f.runtime.verifyAccount()
  const handle = await f.runtime.suspendAccountCommand(f.runtime.captureAccount())
  assert.equal(f.runtime.getSnapshot().phase, 'held')
  assert.equal(f.runtime.getSnapshot().capture, null)
  assert.equal(f.runtime.hasUnsentCaptures(), true)
  await f.runtime.completeAccountCommand(handle, 'uncertain')
  assert.equal(f.runtime.getSnapshot().capture, null)
  assert.equal(f.runtime.hasUnsentCaptures(), true)
  await f.runtime.retryVerification()
  await until(
    () => f.runtime.getSnapshot().phase === 'ready',
    'suspended visit baseline did not finish',
  )
  assert.deepEqual(f.runtime.getSnapshot().capture.customer.draft, channels[0].fields)
  assert.deepEqual(f.runtime.getSnapshot().capture.order.draft, channels[1].fields)
  checkMask()
})

test('capture runtime intermediate authority rebind retains uncertainty masked until verified mismatch denial', async (t) => {
  const original = api()
  let changed = false
  const server = {
    fetch: async (url, init) => {
      const data = await (await original.fetch(url, init)).json()
      if (changed) {
        if (Array.isArray(data.capabilities))
          data.capabilities = data.capabilities.filter((value) => value !== 'bicycles.write')
        if (data.context?.capabilities)
          data.context.capabilities = data.context.capabilities.filter(
            (value) => value !== 'bicycles.write',
          )
      }
      return response(url, data)
    },
  }
  const f = await ready(t, { server })
  fill(f, channels[0])
  let calls = 0
  f.runtime.repositories.createCustomer = async () => {
    calls++
    throw new Error('unknown')
  }
  await f.runtime.submitCaptureCustomer(token(f))
  const checkMask = observeMask(t, f)
  changed = true
  await f.runtime.verifyAccount()
  assert.equal(f.runtime.getSnapshot().phase, 'held')
  assert.equal(f.runtime.getSnapshot().capture, null)
  assert.equal(f.runtime.hasUnsentCaptures(), true)
  await f.runtime.retryVerification()
  await until(
    () => f.runtime.getSnapshot().phase === 'ready',
    'new authority baseline did not finish',
  )
  assert.equal(f.runtime.getSnapshot().capture.customer.draft.displayName, '')
  assert.equal(f.runtime.getSnapshot().capture.customer.blocked, true)
  assert.equal(f.runtime.getSnapshot().capture.order.blocked, true)
  await f.runtime.submitCaptureCustomer(token(f))
  assert.equal(calls, 1)
  checkMask()
})

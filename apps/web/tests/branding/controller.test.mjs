import test from 'node:test'
import assert from 'node:assert/strict'
import { BrandingEditorController } from '../../.tmp-branding/src/features/branding/controller.js'
import { BrandingHttpError } from '../../.tmp-branding/src/features/branding/transport.js'
const row = {
  organization_id: 'org',
  location_id: 'loc',
  dataset_incarnation: 'incarnation',
  version: 1,
}
const payload = {
  expected_version: 0,
  display_name: 'New',
  palette_id: 'bosque',
  logo_png_base64: null,
}
function setup(transport = {}, capabilities = ['branding.read', 'branding.write']) {
  let current = true,
    listeners = new Set(),
    state = {
      phase: 'connected',
      user: { user_id: 'actor', organization_id: 'org', location_id: null, capabilities },
      generation: 1,
    },
    confirmed = 0
  const capture = {
    token: 'synthetic',
    user: state.user,
    apiRealm: 'https://example.test/api/v1',
    signal: new AbortController().signal,
    isCurrent: () => current,
  }
  const invalidate = () => {
    current = false
    state = { phase: 'unverified', user: null, generation: 2 }
    for (const listener of listeners) listener()
  }
  const runtime = {
    getAccountSnapshot: () => state,
    subscribeAccount: (listener) => {
      listeners.add(listener)
      return () => listeners.delete(listener)
    },
    captureAccount: () => {
      if (!current) throw Error()
      return capture
    },
    verifyAccount: async () => {},
    invalidateBrandingAccount: (source) => {
      assert.equal(source, capture)
      invalidate()
    },
    branding: {
      confirmed: async () => {
        confirmed++
      },
      clear: () => {},
    },
  }
  const controller = new BrandingEditorController(runtime, {
    read: async () => row,
    save: async () => row,
    ...transport,
  })
  return { controller, invalidate, confirmed: () => confirmed }
}
test('branding grants do not imply each other or derive from wildcard', async () => {
  for (const capabilities of [[], ['*'], ['branding.read']]) {
    let calls = 0
    const env = setup(
      {
        save: async () => {
          calls++
          return row
        },
      },
      capabilities,
    )
    assert.equal(await env.controller.save('loc', payload), undefined)
    assert.equal(calls, 0)
    env.controller.dispose()
  }
  const write = setup({}, ['branding.write'])
  await write.controller.load('loc')
  assert.equal(write.controller.getSnapshot().profile, null)
  assert.equal((await write.controller.save('loc', payload)).version, 1)
  assert.equal(write.confirmed(), 0)
  assert.equal(write.controller.getSnapshot().profile, null)
  write.controller.dispose()
})
test('late read after invalidation cannot restore directory or profile', async () => {
  let release
  const env = setup({ read: () => new Promise((r) => (release = r)) })
  const loading = env.controller.load('loc')
  env.invalidate()
  release(row)
  await loading
  assert.equal(env.controller.getSnapshot().profile, null)
  env.controller.dispose()
})
test('CAS conflict and lost response preserve immutable expected version with no resend', async () => {
  for (const error of [new BrandingHttpError('stale_branding_version', 409), new Error('lost')]) {
    let calls = 0,
      received
    const env = setup({
      save: async (_s, input) => {
        calls++
        received = input
        throw error
      },
    })
    await env.controller.save('loc', payload)
    assert.equal(calls, 1)
    assert.equal(received.expected_version, 0)
    assert.equal(env.controller.getSnapshot().result, error.status === 409 ? 'error' : 'uncertain')
    env.controller.dispose()
  }
})
test('duplicate save and later account invalidation cannot confirm prior success', async () => {
  let release,
    calls = 0
  const env = setup({
    save: () => {
      calls++
      return new Promise((r) => (release = r))
    },
  })
  const saving = env.controller.save('loc', payload)
  assert.equal(await env.controller.save('loc', payload), undefined)
  assert.equal(calls, 1)
  env.invalidate()
  release(row)
  assert.equal(await saving, undefined)
  assert.equal(env.confirmed(), 0)
  env.controller.dispose()
})
test('current denial invalidates only captured account and clears profile', async () => {
  for (const status of [401, 403]) {
    const env = setup({
      read: async () => {
        throw new BrandingHttpError('denied', status)
      },
    })
    await env.controller.load('loc')
    assert.equal(env.controller.getSnapshot().account.phase, 'unverified')
    env.controller.dispose()
  }
})

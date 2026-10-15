import assert from 'node:assert/strict'
import test from 'node:test'
import vm from 'node:vm'
import * as observation from '../../e2e/helpers/inventory-observation.mjs'
const { isUnexpectedApiWrite, observeInventoryContext } = observation

const origin = 'http://127.0.0.1:5173'
const location = 'synthetic-location'
const contextUrl = `${origin}/api/v1/auth/context?selected_location_id=${location}`
const body = {
  selected_location_id: location,
  offline_until: '2026-10-15T15:33:03.123456Z',
  snapshot_protocol: null,
  private_canary: 'must-never-cross-page-observation',
}
const expected = { expiresAt: Date.parse(body.offline_until), snapshotProtocol: null }
const failure = /^Error: Invalid inventory context observation$/
function deferred() {
  let resolve, reject
  const promise = new Promise((yes, no) => {
    resolve = yes
    reject = no
  })
  return { promise, resolve, reject }
}
function response(data = body, options = {}) {
  const result = new Response(typeof data === 'string' ? data : JSON.stringify(data), {
    status: 200,
    headers: { 'content-type': 'application/json' },
    ...options,
  })
  Object.defineProperties(result, {
    url: { value: options.url ?? contextUrl },
    redirected: { value: options.redirected ?? false },
  })
  return result
}
async function harness(serve = async () => response()) {
  const requests = [],
    scripts = []
  let cdpCalls = 0
  const nativeFetch = function (...args) {
    requests.push({ args, receiver: this })
    return serve(...args)
  }
  const scope = {
    fetch: nativeFetch,
    location: new URL(origin + '/'),
    URL,
    Request,
    TextDecoder,
    Uint8Array,
    AbortController,
  }
  scope.window = scope
  const context = vm.createContext(scope)
  const page = {
    url: () => origin + '/',
    addInitScript: async (fn) => {
      scripts.push(fn)
    },
    evaluate: async (fn, arg) => {
      scope.__argument = arg
      try {
        const value = await vm.runInContext(`(${fn.toString()})(__argument)`, context)
        return value === undefined ? value : JSON.parse(JSON.stringify(value))
      } finally {
        delete scope.__argument
      }
    },
    waitForResponse: async () => {
      cdpCalls++
      return {
        json: async () => {
          throw new Error('CDP body unavailable at response arrival')
        },
      }
    },
  }
  // The runtime captures the installed wrapper before bootstrap. CDP stays
  // unavailable even though the real Fetch Response remains readable in-page.
  await observation.installInventoryContextObserver(page)
  for (const script of scripts) vm.runInContext(`(${script.toString()})()`, context)
  const capturedFetch = scope.fetch.bind(scope)
  return {
    page,
    scope,
    nativeFetch,
    requests,
    scripts,
    fetch: capturedFetch,
    cdpCalls: () => cdpCalls,
    disposed: () => {
      assert.equal(scope.fetch, nativeFetch)
      assert.equal(scope.__ocwpInventoryContextObservation, undefined)
    },
  }
}

test('only the exact POST delta page is exempted from the write observer', () => {
  assert.equal(isUnexpectedApiWrite('POST', `${origin}/api/v1/sync/deltas/page`), false)
  assert.equal(isUnexpectedApiWrite('POST', `${origin}/api/v1/sync/deltas/page?x=1`), false)
  for (const path of [
    '/api/v1/sync/mutations',
    '/api/v1/sync/deltas/page/',
    '/api/v1/sync/deltas/page-other',
    '/api/v1/sync/deltas%2fpage',
    '/api/v1/customers?next=/api/v1/sync/deltas/page',
    '/api/v1/inventory/products',
    '/api/v1/inventory/movements',
    '/api/v1/auth/logout',
    '/api/v1/auth/login',
    '/api/v1/admin/users/synthetic/revoke-sessions',
    '/api/v1/sync/baselines/start',
    '/api/v1/unknown',
  ])
    assert.equal(isUnexpectedApiWrite('POST', origin + path), true, path)
  for (const method of ['PUT', 'PATCH', 'DELETE'])
    assert.equal(isUnexpectedApiWrite(method, `${origin}/api/v1/sync/deltas/page`), true)
  for (const method of ['GET', 'HEAD', 'OPTIONS'])
    assert.equal(isUnexpectedApiWrite(method, `${origin}/api/v1/inventory/products`), false)
  assert.equal(isUnexpectedApiWrite('POST', `${origin}/unrelated`), false)
})

test('page-owned clone observes actual expiry with CDP unavailable and complete action readiness', async () => {
  const original = response()
  const h = await harness(async () => original)
  let ready = false
  const init = { method: 'GET', signal: new AbortController().signal }
  const result = await observeInventoryContext(h.page, location, async () => {
    assert.equal(await h.fetch(contextUrl, init), original)
    assert.deepEqual(await original.json(), body)
    await new Promise((resolve) => setImmediate(resolve))
    ready = true
  })
  assert.equal(ready, true)
  assert.deepEqual(result, expected)
  assert.equal(h.cdpCalls(), 0)
  assert.equal(h.requests.length, 1)
  assert.equal(h.requests[0].args[0], contextUrl)
  assert.equal(h.requests[0].args[1], init)
  assert.equal(h.requests[0].receiver, h.scope)
  h.disposed()
})

test('only matching requests initiated while armed can supply the observation', async () => {
  const pending = deferred()
  let count = 0,
    ignoredClones = 0
  const h = await harness(async () => {
    if (++count === 1) return pending.promise
    const value = response({ ...body, snapshot_protocol: 'baseline-v1' })
    if (count < 8)
      value.clone = () => {
        ignoredClones++
        throw new Error('wrong match')
      }
    return value
  })
  const early = h.fetch(contextUrl)
  const result = await observeInventoryContext(h.page, location, async () => {
    pending.resolve(response())
    await early
    for (const [url, init] of [
      [contextUrl.replace(origin, 'https://other.example')],
      [contextUrl.replace(location, 'other-location')],
      [contextUrl + '&selected_location_id=other-location'],
      [contextUrl.replace('/context?', '/context-other?')],
      [contextUrl, { method: 'POST' }],
      [contextUrl.replace('/context?', '/context/?')],
    ])
      await h.fetch(url, init)
    await h.fetch(new Request(contextUrl))
  })
  assert.equal(ignoredClones, 0)
  assert.equal(result.snapshotProtocol, 'baseline-v1')
  assert.equal(h.requests.length, 8)
  h.disposed()
})

test('missing and ambiguous matching requests fail closed instead of choosing a lease', async () => {
  for (const count of [0, 2]) {
    const h = await harness()
    await assert.rejects(
      observeInventoryContext(h.page, location, async () => {
        await Promise.all(Array.from({ length: count }, () => h.fetch(contextUrl)))
      }),
      failure,
    )
    assert.equal(h.requests.length, count)
    h.disposed()
  }
})

test('unacceptable response status, redirect, URL, body and stream fail with fixed safe error', async () => {
  const cases = [
    () => response(body, { status: 401 }),
    () => response(body, { status: 403 }),
    () => response(body, { status: 500 }),
    () => response(body, { redirected: true }),
    () => response(body, { url: contextUrl + '&other=1' }),
    () => response('private malformed body'),
    () => {
      const r = response()
      r.clone = () => new Response(null)
      return r
    },
    () => response({ ...body, offline_until: null }),
    () => response({ ...body, offline_until: 'private-invalid-time' }),
    () => response({ ...body, selected_location_id: 'private-wrong-scope' }),
    () => response({ ...body, snapshot_protocol: 'private-future-protocol' }),
    () => response({ ...body, private_canary: 'x'.repeat(16384) }),
    () => {
      const r = response()
      r.clone = () => {
        throw new Error('private clone error')
      }
      return r
    },
    () => {
      const r = response()
      r.clone = () =>
        new Response(
          new ReadableStream({
            start(controller) {
              controller.error(new Error('private stream error'))
            },
          }),
        )
      return r
    },
  ]
  for (const create of cases) {
    const h = await harness(async () => create())
    await assert.rejects(
      observeInventoryContext(h.page, location, async () => {
        await h.fetch(contextUrl)
      }),
      failure,
    )
    assert.equal(h.requests.length, 1)
    assert.equal(h.cdpCalls(), 0)
    h.disposed()
  }
})

test('fetch rejection and action failure preserve original errors while disposing observation', async () => {
  const fetchError = new Error('actual fetch failure')
  const h = await harness(async () => {
    throw fetchError
  })
  await assert.rejects(
    observeInventoryContext(h.page, location, async () => {
      await assert.rejects(h.fetch(contextUrl), (error) => error === fetchError)
    }),
    failure,
  )
  h.disposed()
  const synchronous = await harness(() => {
    throw fetchError
  })
  await assert.rejects(
    observeInventoryContext(synchronous.page, location, async () => {
      assert.throws(
        () => synchronous.fetch(contextUrl),
        (error) => error === fetchError,
      )
    }),
    failure,
  )
  synchronous.disposed()
  const actionError = new Error('actual action failure')
  const failed = await harness()
  await assert.rejects(
    observeInventoryContext(failed.page, location, async () => {
      await failed.fetch(contextUrl)
      throw actionError
    }),
    (error) => error === actionError,
  )
  failed.disposed()
})

test('a stalled clone does not delay app Response and is canceled on action failure', async () => {
  let canceled = 0
  const original = response()
  original.clone = () =>
    new Response(
      new ReadableStream({
        cancel() {
          canceled++
        },
      }),
    )
  const h = await harness(async () => original)
  const error = new Error('action refuses stalled observation')
  await assert.rejects(
    observeInventoryContext(h.page, location, async () => {
      assert.equal(await h.fetch(contextUrl), original)
      assert.deepEqual(await original.json(), body)
      throw error
    }),
    (actual) => actual === error,
  )
  await new Promise((resolve) => setImmediate(resolve))
  assert.equal(canceled, 1)
  h.disposed()
})

test('late completion cannot resurrect disposed state or satisfy another action', async () => {
  const pending = deferred()
  let clones = 0
  const original = response()
  original.clone = () => {
    clones++
    return response()
  }
  const h = await harness(() => pending.promise)
  let late
  await assert.rejects(
    observeInventoryContext(h.page, location, async () => {
      late = h.fetch(contextUrl)
      throw new Error('stop action')
    }),
    /stop action/,
  )
  pending.resolve(original)
  assert.equal(await late, original)
  assert.equal(clones, 0)
  h.disposed()
  await assert.rejects(
    observeInventoryContext(h.page, location, async () => {
      assert.fail('disposed observer must not start another action')
    }),
    failure,
  )
  assert.equal(h.requests.length, 1)
})

test('cleanup preserves a later fetch owner while captured wrapper becomes inert', async () => {
  const h = await harness()
  const replacement = async () => response()
  await observeInventoryContext(h.page, location, async () => {
    await h.fetch(contextUrl)
    h.scope.fetch = replacement
  })
  assert.equal(h.scope.fetch, replacement)
  assert.equal(h.scope.__ocwpInventoryContextObservation, undefined)
  const original = await h.fetch(contextUrl)
  assert.deepEqual(await original.json(), body)
  assert.equal(h.requests.length, 2)
})

test('cleanup errors fail an otherwise successful observation without hiding an action error', async () => {
  for (const actionFails of [false, true]) {
    const h = await harness()
    const evaluate = h.page.evaluate
    h.page.evaluate = async (fn, arg) => {
      if (fn.toString().includes('?.dispose()')) throw new Error('private cleanup detail')
      return evaluate(fn, arg)
    }
    const actionError = new Error('original action error')
    await assert.rejects(
      observeInventoryContext(h.page, location, async () => {
        await h.fetch(contextUrl)
        if (actionFails) throw actionError
      }),
      actionFails
        ? (error) => error === actionError
        : /^Error: Inventory context observation cleanup failed$/,
    )
    h.scope.__ocwpInventoryContextObservation.dispose()
    h.disposed()
  }
})

test('exact byte bound accepts 16 KiB and rejects larger or invalid UTF-8 without retry', async () => {
  const text = JSON.stringify(body)
  const padded = text + ' '.repeat(16384 - Buffer.byteLength(text))
  const accepted = await harness(async () => response(padded))
  assert.deepEqual(
    await observeInventoryContext(accepted.page, location, async () => {
      await accepted.fetch(contextUrl)
    }),
    expected,
  )
  accepted.disposed()
  for (const payload of [padded + ' ', new Uint8Array([0xff, 0xfe])]) {
    const original = response()
    original.clone = () => new Response(payload)
    const h = await harness(async () => original)
    await assert.rejects(
      observeInventoryContext(h.page, location, async () => {
        assert.equal(await h.fetch(contextUrl), original)
      }),
      failure,
    )
    assert.equal(h.requests.length, 1)
    h.disposed()
  }
})

test('a second matching request after first clone completion is still ambiguous', async () => {
  const h = await harness()
  await assert.rejects(
    observeInventoryContext(h.page, location, async () => {
      await h.fetch(contextUrl)
      await new Promise((resolve) => setImmediate(resolve))
      await h.fetch(contextUrl)
    }),
    failure,
  )
  assert.equal(h.requests.length, 2)
  h.disposed()
})

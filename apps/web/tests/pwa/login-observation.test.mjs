import assert from 'node:assert/strict'
import test from 'node:test'
import vm from 'node:vm'
import { installLoginObserver, observeLogin } from '../../e2e/helpers/login-observation.mjs'

const origin = 'http://127.0.0.1:5175'
const loginUrl = `${origin}/api/v1/auth/login`
const issued = 'synthetic-issued-canary'
const body = {
  token_type: 'bearer',
  access_token: issued,
  private_canary: 'never-return-this-body',
}
const expected = { bodyValidated: true, issuedMatchesStored: true }
const failure = /^Error: Invalid login observation$/
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
    headers: { 'content-type': 'application/json', 'cache-control': 'no-store' },
    ...options,
  })
  Object.defineProperties(result, {
    url: { value: options.url ?? loginUrl },
    redirected: { value: options.redirected ?? false },
  })
  return result
}
async function harness(serve = async () => response(), documentOrigin = origin) {
  const requests = [],
    scripts = []
  let cdpReads = 0,
    stored = null,
    storageFailure = null
  const nativeFetch = function (...args) {
    requests.push({ args, receiver: this })
    return serve(...args)
  }
  const scope = {
    fetch: nativeFetch,
    location: new URL(documentOrigin + '/'),
    URL,
    Request,
    TextDecoder,
    Uint8Array,
    AbortController,
    sessionStorage: {
      getItem: (key) => {
        assert.equal(key, 'ocwp.session.v2')
        if (storageFailure) throw storageFailure
        return stored
      },
    },
  }
  scope.window = scope
  scope.top = scope
  const context = vm.createContext(scope)
  const page = {
    addInitScript: async (fn, arg) => scripts.push({ fn, arg }),
    evaluate: async (fn, arg) => {
      scope.__argument = arg
      try {
        const value = await vm.runInContext(`(${fn.toString()})(__argument)`, context)
        return value === undefined ? value : JSON.parse(JSON.stringify(value))
      } finally {
        delete scope.__argument
      }
    },
    waitForResponse: async () => ({
      status: () => 200,
      json: async () => {
        cdpReads++
        throw new Error('Network.getResponseBody unavailable')
      },
    }),
  }
  await installLoginObserver(page, origin)
  for (const { fn, arg } of scripts) {
    scope.__initArgument = arg
    vm.runInContext(`(${fn.toString()})(__initArgument)`, context)
    delete scope.__initArgument
  }
  const capturedFetch = scope.fetch.bind(scope)
  return {
    page,
    scope,
    nativeFetch,
    requests,
    scripts,
    fetch: capturedFetch,
    setStored: (value = JSON.stringify({ token: issued })) => {
      stored = value
    },
    failStorage: () => {
      storageFailure = new Error('private storage failure')
    },
    cdpReads: () => cdpReads,
    disposed: () => {
      assert.equal(scope.fetch, nativeFetch)
      assert.equal(scope.__ocwpLoginObservation, undefined)
    },
  }
}
const post = { method: 'POST' }

test('real response clone proves issued-token equality despite unavailable CDP body', async () => {
  const original = response()
  const h = await harness(async () => original)
  // A deliberately unavailable CDP body is the old failing operation, not a
  // fabricated application response or a storage fallback for absent bytes.
  await assert.rejects((await h.page.waitForResponse()).json(), /Network.getResponseBody/)
  let ready = false
  const init = { method: 'POST', signal: new AbortController().signal, body: 'synthetic-login' }
  const result = await observeLogin(h.page, async () => {
    assert.equal(await h.fetch(loginUrl, init), original)
    assert.deepEqual(await original.json(), body)
    h.setStored()
    await new Promise((resolve) => setImmediate(resolve))
    ready = true
  })
  assert.equal(ready, true)
  assert.deepEqual(result, expected)
  assert.deepEqual(Object.keys(result).sort(), ['bodyValidated', 'issuedMatchesStored'])
  assert.equal(JSON.stringify(result).includes(issued), false)
  assert.equal(JSON.stringify(result).includes(body.private_canary), false)
  assert.equal(h.cdpReads(), 1, 'observer performs no CDP body read')
  assert.equal(h.requests.length, 1)
  assert.equal(h.requests[0].args[0], loginUrl)
  assert.equal(h.requests[0].args[1], init)
  assert.equal(h.requests[0].receiver, h.scope)
  h.disposed()
})

test('completed clone does not bypass later application readiness', async () => {
  const h = await harness(),
    action = deferred(),
    fetched = deferred()
  let settled = false
  const pending = observeLogin(h.page, async () => {
    await h.fetch(loginUrl, post)
    h.setStored()
    fetched.resolve()
    await action.promise
  }).then((value) => {
    settled = true
    return value
  })
  await fetched.promise
  await new Promise((resolve) => setImmediate(resolve))
  assert.equal(settled, false)
  action.resolve()
  assert.deepEqual(await pending, expected)
  h.disposed()
})

test('missing or duplicated matching login requests fail closed', async () => {
  for (const count of [0, 2]) {
    const h = await harness()
    h.setStored()
    await assert.rejects(
      observeLogin(h.page, async () => {
        await Promise.all(Array.from({ length: count }, () => h.fetch(loginUrl, post)))
      }),
      failure,
    )
    assert.equal(h.requests.length, count)
    h.disposed()
  }
})

test('exact URL and effective method exclude lookalikes while preserving Request overrides', async () => {
  let ignoredClones = 0
  const ignored = [
    [loginUrl.replace(origin, 'https://elsewhere.example'), post],
    [loginUrl + '?extra=1', post],
    [loginUrl + '#fragment', post],
    [loginUrl + '/', post],
    [loginUrl + '-other', post],
    [loginUrl, { method: 'GET' }],
    [loginUrl, { method: 'PUT' }],
    [new Request(loginUrl, { method: 'POST' }), { method: 'GET' }],
  ]
  let count = 0
  const h = await harness(async () => {
    const value = response()
    if (++count <= ignored.length)
      value.clone = () => {
        ignoredClones++
        throw new Error('wrong request captured')
      }
    return value
  })
  const result = await observeLogin(h.page, async () => {
    for (const args of ignored) await h.fetch(...args)
    await h.fetch(new Request(loginUrl), { method: 'post' })
    h.setStored()
  })
  assert.deepEqual(result, expected)
  assert.equal(ignoredClones, 0)
  assert.equal(h.requests.length, ignored.length + 1)
  h.disposed()
})

test('an earlier request cannot adopt a subsequently armed observation', async () => {
  const earlier = deferred()
  let calls = 0,
    clones = 0
  const stale = response()
  stale.clone = () => {
    clones++
    throw new Error('earlier request was captured')
  }
  const h = await harness(() => (++calls === 1 ? earlier.promise : Promise.resolve(response())))
  const pending = h.fetch(loginUrl, post)
  const result = await observeLogin(h.page, async () => {
    earlier.resolve(stale)
    assert.equal(await pending, stale)
    await h.fetch(loginUrl, post)
    h.setStored()
  })
  assert.deepEqual(result, expected)
  assert.equal(clones, 0)
  h.disposed()
})

test('invalid status, redirect or response URL cannot supply issued-token evidence', async () => {
  for (const options of [
    { status: 401 },
    { status: 403 },
    { status: 500 },
    { redirected: true },
    { url: loginUrl + '?other=1' },
    { url: loginUrl.replace(origin, 'https://elsewhere.example') },
  ]) {
    const h = await harness(async () => response(body, options))
    h.setStored()
    await assert.rejects(
      observeLogin(h.page, async () => {
        await h.fetch(loginUrl, post)
      }),
      failure,
    )
    assert.equal(h.requests.length, 1)
    h.disposed()
  }
})

test('malformed or invalid bearer body fails even if storage already contains the expected token', async () => {
  const invalidBodies = [
    'private malformed response',
    null,
    [],
    {},
    { token_type: 'other', access_token: issued },
    { token_type: 'bearer' },
    { token_type: 'bearer', access_token: null },
    { token_type: 'bearer', access_token: 123 },
    { token_type: 'bearer', access_token: '' },
    { token_type: 'bearer', access_token: 'two tokens' },
    { token_type: 'bearer', access_token: 'x'.repeat(16385) },
  ]
  for (const value of invalidBodies) {
    const h = await harness(async () => response(value))
    h.setStored()
    await assert.rejects(
      observeLogin(h.page, async () => {
        await h.fetch(loginUrl, post)
      }),
      failure,
    )
    assert.equal(h.requests.length, 1)
    h.disposed()
  }
})

test('missing body, clone failure and stream errors stay sanitized', async () => {
  for (const clone of [
    () => new Response(null),
    () => {
      throw new Error('private clone failure')
    },
    () =>
      new Response(
        new ReadableStream({
          start(controller) {
            controller.error(new Error('private stream failure'))
          },
        }),
      ),
  ]) {
    const original = response()
    original.clone = clone
    const h = await harness(async () => original)
    h.setStored()
    await assert.rejects(
      observeLogin(h.page, async () => {
        assert.equal(await h.fetch(loginUrl, post), original)
      }),
      failure,
    )
    h.disposed()
  }
})

test('exact 32 KiB bound is accepted while larger and invalid UTF-8 bodies are refused', async () => {
  const text = JSON.stringify(body)
  const padded = text + ' '.repeat(32768 - Buffer.byteLength(text))
  const accepted = await harness(async () => response(padded))
  assert.deepEqual(
    await observeLogin(accepted.page, async () => {
      await accepted.fetch(loginUrl, post)
      accepted.setStored()
    }),
    expected,
  )
  accepted.disposed()
  for (const payload of [padded + ' ', new Uint8Array([0xff, 0xfe])]) {
    const original = response()
    original.clone = () => new Response(payload)
    const h = await harness(async () => original)
    await assert.rejects(
      observeLogin(h.page, async () => {
        await h.fetch(loginUrl, post)
      }),
      failure,
    )
    assert.equal(h.requests.length, 1)
    h.disposed()
  }
})

test('maximum valid token remains closure-only', async () => {
  const token = 'x'.repeat(16384)
  const h = await harness(async () => response({ token_type: 'bearer', access_token: token }))
  assert.deepEqual(
    await observeLogin(h.page, async () => {
      await h.fetch(loginUrl, post)
      h.setStored(JSON.stringify({ token }))
    }),
    expected,
  )
  h.disposed()
})

test('independently observed token mismatch returns false instead of accepting storage', async () => {
  const h = await harness()
  const result = await observeLogin(h.page, async () => {
    await h.fetch(loginUrl, post)
    h.setStored(JSON.stringify({ token: 'different-private-canary' }))
  })
  assert.deepEqual(result, { bodyValidated: true, issuedMatchesStored: false })
  assert.equal(JSON.stringify(result).includes('canary'), false)
  h.disposed()
})

test('missing, malformed, wrong-shaped and inaccessible session storage cannot imply equality', async () => {
  for (const stored of [
    null,
    'private invalid JSON',
    '{}',
    '{"token":null}',
    '{"token":12}',
    '["token"]',
    'throw',
  ]) {
    const h = await harness()
    const result = await observeLogin(h.page, async () => {
      await h.fetch(loginUrl, post)
      if (stored === 'throw') h.failStorage()
      else h.setStored(stored)
    })
    assert.deepEqual(result, { bodyValidated: true, issuedMatchesStored: false })
    h.disposed()
  }
})

test('fetch rejection preserves application failure and cannot become successful evidence', async () => {
  const error = new Error('actual fetch failed')
  for (const synchronous of [false, true]) {
    const h = await harness(() => {
      if (synchronous) throw error
      return Promise.reject(error)
    })
    await assert.rejects(
      observeLogin(h.page, async () => {
        if (synchronous)
          assert.throws(
            () => h.fetch(loginUrl, post),
            (value) => value === error,
          )
        else await assert.rejects(h.fetch(loginUrl, post), (value) => value === error)
      }),
      failure,
    )
    h.disposed()
  }
})

test('action failure stays primary and cancels a stalled clone without delaying the original', async () => {
  let cancelled = 0
  const original = response()
  original.clone = () =>
    new Response(
      new ReadableStream({
        cancel() {
          cancelled++
        },
      }),
    )
  const h = await harness(async () => original)
  const error = new Error('actual action failed')
  await assert.rejects(
    observeLogin(h.page, async () => {
      assert.equal(await h.fetch(loginUrl, post), original)
      assert.deepEqual(await original.json(), body)
      throw error
    }),
    (value) => value === error,
  )
  await new Promise((resolve) => setImmediate(resolve))
  assert.equal(cancelled, 1)
  h.disposed()
})

test('late completion cannot revive disposed state or satisfy a second action', async () => {
  const pending = deferred()
  let clones = 0,
    late
  const original = response()
  original.clone = () => {
    clones++
    return response()
  }
  const h = await harness(() => pending.promise)
  await assert.rejects(
    observeLogin(h.page, async () => {
      late = h.fetch(loginUrl, post)
      throw new Error('stop action')
    }),
    /stop action/,
  )
  pending.resolve(original)
  assert.equal(await late, original)
  assert.equal(clones, 0)
  h.disposed()
  await assert.rejects(
    observeLogin(h.page, async () => {
      assert.fail('disposed observer reused')
    }),
    failure,
  )
  assert.equal(h.requests.length, 1)
})

test('a second matching request after first clone completion remains ambiguous', async () => {
  const h = await harness()
  await assert.rejects(
    observeLogin(h.page, async () => {
      await h.fetch(loginUrl, post)
      await new Promise((resolve) => setImmediate(resolve))
      await h.fetch(loginUrl, post)
      h.setStored()
    }),
    failure,
  )
  assert.equal(h.requests.length, 2)
  h.disposed()
})

test('cleanup respects a later fetch owner and leaves a bound wrapper inert', async () => {
  const h = await harness()
  const replacement = async () => response()
  assert.deepEqual(
    await observeLogin(h.page, async () => {
      await h.fetch(loginUrl, post)
      h.setStored()
      h.scope.fetch = replacement
    }),
    expected,
  )
  assert.equal(h.scope.fetch, replacement)
  assert.equal(h.scope.__ocwpLoginObservation, undefined)
  assert.deepEqual(await (await h.fetch(loginUrl, post)).json(), body)
  assert.equal(h.requests.length, 2)
})

test('cleanup failure cannot pass or mask an earlier action error', async () => {
  for (const actionFails of [false, true]) {
    const h = await harness(),
      evaluate = h.page.evaluate
    h.page.evaluate = async (fn, arg) => {
      if (fn.toString().includes('?.dispose()')) throw new Error('private cleanup failure')
      return evaluate(fn, arg)
    }
    const error = new Error('original action failed')
    await assert.rejects(
      observeLogin(h.page, async () => {
        await h.fetch(loginUrl, post)
        h.setStored()
        if (actionFails) throw error
      }),
      actionFails ? (value) => value === error : /^Error: Login observation cleanup failed$/,
    )
    h.scope.__ocwpLoginObservation.dispose()
    h.disposed()
  }
})

test('observation cannot be armed twice in the same document', async () => {
  const h = await harness()
  await h.page.evaluate(() => window.__ocwpLoginObservation.arm())
  await assert.rejects(
    h.page.evaluate(() => window.__ocwpLoginObservation.arm()),
    failure,
  )
  h.scope.__ocwpLoginObservation.dispose()
  h.disposed()
})

test('init observer is scoped to the destination main frame', async () => {
  const h = await harness()
  h.scope.__ocwpLoginObservation.dispose()
  h.scope.top = {}
  const context = vm.createContext(h.scope)
  for (const { fn, arg } of h.scripts) {
    h.scope.__initArgument = arg
    vm.runInContext(`(${fn.toString()})(__initArgument)`, context)
    delete h.scope.__initArgument
  }
  assert.equal(h.scope.fetch, h.nativeFetch)
  assert.equal(h.scope.__ocwpLoginObservation, undefined)
})

test('wrong destination origin installs nothing and prevents action or waiter registration', async () => {
  const h = await harness(undefined, 'http://127.0.0.1:5173')
  assert.equal(h.scope.fetch, h.nativeFetch)
  assert.equal(h.scope.__ocwpLoginObservation, undefined)
  let actions = 0,
    waiters = 0
  await assert.rejects(
    observeLogin(h.page, async () => {
      actions++
      waiters++
      await h.page.waitForResponse()
    }),
    failure,
  )
  assert.equal(actions, 0)
  assert.equal(waiters, 0)
  assert.equal(h.requests.length, 0)
  h.disposed()
})

test('missing observer refuses before starting the action or its response waiter', async () => {
  const h = await harness()
  h.scope.__ocwpLoginObservation.dispose()
  let actions = 0,
    waiters = 0
  await assert.rejects(
    observeLogin(h.page, async () => {
      actions++
      waiters++
      await h.page.waitForResponse()
    }),
    failure,
  )
  assert.equal(actions, 0)
  assert.equal(waiters, 0)
  assert.equal(h.requests.length, 0)
  h.disposed()
})

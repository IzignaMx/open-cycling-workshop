import test from 'node:test'
import assert from 'node:assert/strict'
import { InventoryController } from '../../.tmp-inventory/src/features/inventory/controller.js'
import { InventoryHttpError } from '../../.tmp-inventory/src/features/inventory/contracts.js'
const turn = () => new Promise((resolve) => setImmediate(resolve))
const product = (id = 'a') => ({ product_id: id, name: id, sku: id, unit: 'pieza' })
const deferred = () => {
  let resolve, reject
  const promise = new Promise((a, b) => {
    resolve = a
    reject = b
  })
  return { promise, resolve, reject }
}
function setup(overrides = {}, capabilities = ['inventory.read']) {
  const listeners = new Set(),
    accountListeners = new Set()
  let generation = 1,
    phase = 'ready',
    context = {
      principal: { organizationId: 'org', userId: 'actor' },
      selectedLocationId: 'loc',
      capabilities,
    },
    account = {
      phase: 'connected',
      generation: 1,
      user: { user_id: 'actor', organization_id: 'org', location_id: 'loc', capabilities },
    },
    calls = { catalog: 0, stock: 0, movements: 0, refusal: 0, verify: 0 }
  const access = {
    getSnapshot: () => ({
      phase,
      context: phase === 'ready' ? context : null,
      generation,
      message: null,
    }),
    subscribe: (l) => {
      listeners.add(l)
      return () => listeners.delete(l)
    },
    capture: () => {
      if (phase !== 'ready') throw Error('unverified')
      const captured = generation
      return {
        token: 'secret',
        context,
        generation,
        user: account.user,
        apiRealm: 'https://test.example/api/v1',
        signal: new AbortController().signal,
        isCurrent: () => generation === captured && phase === 'ready',
      }
    },
    check: async () => {},
    verify: async () => {
      calls.verify++
      phase = 'ready'
      generation++
      for (const l of listeners) l()
    },
    refuse: () => {
      calls.refusal++
      change('unavailable')
    },
    clear: () => change('unverified'),
  }
  const runtime = {
    connectedReads: access,
    getAccountSnapshot: () => account,
    subscribeAccount: (l) => {
      accountListeners.add(l)
      return () => accountListeners.delete(l)
    },
    verifyAccount: async () => {},
    getSnapshot: () => ({ user: account.user, locations: [], nextLocation: null }),
    subscribe: () => () => {},
    loadLocations: async () => {},
  }
  const transport = {
    catalog: async () => {
      calls.catalog++
      return [product('a'), product('b')]
    },
    stock: async (_s, id) => {
      calls.stock++
      return { product_id: id, available_quantity: -7 }
    },
    movements: async () => {
      calls.movements++
      return { items: [], next_cursor: null }
    },
    ...overrides,
  }
  const controller = new InventoryController(runtime, transport, () => 1000)
  function change(next = 'ready', newContext = context) {
    phase = next
    context = newContext
    generation++
    for (const l of listeners) l()
  }
  return { controller, calls, change, access, runtime }
}

test('manual catalog retry repeats only the failed offset without verification or automatic work', async () => {
  const offsets = []
  const retry = deferred()
  const env = setup({
    catalog: async (_source, offset) => {
      offsets.push(offset)
      if (offsets.length === 2) throw new InventoryHttpError('unavailable', 503)
      if (offsets.length === 3) return retry.promise
      return [product()]
    },
  })
  await env.controller.retryCatalog()
  assert.deepEqual(offsets, [])
  await env.controller.enter()
  await env.controller.loadCatalog(50)
  assert.equal(env.controller.getSnapshot().catalog.phase, 'error')
  assert.equal(env.controller.getSnapshot().catalog.value, null)
  await turn()
  assert.deepEqual(offsets, [0, 50])
  const pending = env.controller.retryCatalog()
  await env.controller.retryCatalog()
  await turn()
  assert.deepEqual(offsets, [0, 50, 50])
  assert.equal(env.controller.getSnapshot().catalog.phase, 'loading')
  retry.resolve([product('page-two')])
  await pending
  assert.equal(env.controller.getSnapshot().offset, 50)
  assert.equal(env.controller.getSnapshot().catalog.value[0].product_id, 'page-two')
  await env.controller.retryCatalog()
  assert.deepEqual(offsets, [0, 50, 50])
  assert.equal(env.calls.verify, 1)
  env.controller.dispose()
})

for (const initial of [true, false]) {
  test(`manual history retry retains its ${initial ? 'initial' : 'older'} boundary and independent stock`, async () => {
    const requests = []
    let fail = initial
    const retry = deferred()
    let hold = false
    const env = setup({
      movements: async (_source, id, before) => {
        requests.push([id, before])
        if (fail) throw new InventoryHttpError('network_error')
        if (hold) return retry.promise
        return { items: [], next_cursor: 'older-page' }
      },
    })
    await env.controller.retryHistory()
    assert.deepEqual(requests, [])
    await env.controller.enter()
    await env.controller.selectProduct('a')
    if (!initial) {
      fail = true
      await env.controller.older()
    }
    const before = initial ? undefined : 'older-page'
    const stock = env.controller.getSnapshot().stock
    const selected = env.controller.getSnapshot().product
    assert.equal(env.controller.getSnapshot().history.phase, 'error')
    assert.equal(env.controller.getSnapshot().historyBefore, before ?? null)
    assert.equal(env.controller.getSnapshot().history.value, null)
    const failedCount = requests.length
    await turn()
    assert.equal(requests.length, failedCount)
    fail = false
    hold = true
    const pending = env.controller.retryHistory()
    await env.controller.retryHistory()
    await turn()
    assert.equal(requests.length, failedCount + 1)
    assert.deepEqual(requests.at(-1), ['a', before])
    retry.resolve({ items: [{ movement_id: 'recovered' }], next_cursor: null })
    await pending
    assert.equal(env.controller.getSnapshot().history.value.items[0].movement_id, 'recovered')
    assert.equal(env.controller.getSnapshot().stock, stock)
    assert.equal(env.controller.getSnapshot().product, selected)
    assert.equal(env.calls.stock, 1)
    await env.controller.retryHistory()
    assert.equal(requests.length, failedCount + 1)
    hold = false
    await env.controller.newest()
    assert.deepEqual(requests.at(-1), ['a', undefined])
    assert.equal(env.calls.verify, 1)
    env.controller.dispose()
  })
}

for (const kind of ['catalog', 'history']) {
  test(`manual ${kind} retry checks current ownership before dispatch and never verifies access`, async () => {
    let reads = 0
    const env = setup({
      [kind === 'catalog' ? 'catalog' : 'movements']: async () => {
        reads++
        throw new InventoryHttpError('unavailable', 503)
      },
    })
    await env.controller.enter()
    if (kind === 'history') await env.controller.selectProduct('a')
    assert.equal(reads, 1)
    env.access.check = async () => env.change('unavailable')
    await env.controller[kind === 'catalog' ? 'retryCatalog' : 'retryHistory']()
    assert.equal(reads, 1)
    assert.equal(env.controller.getSnapshot()[kind].phase, 'idle')
    await env.controller[kind === 'catalog' ? 'retryCatalog' : 'retryHistory']()
    assert.equal(reads, 1)
    assert.equal(env.calls.verify, 1)
    env.controller.dispose()
  })
  test(`manual ${kind} retry leaves authority refusals unchanged without a status code`, async () => {
    for (const code of ['invalid_session', 'capability_denied']) {
      let reads = 0
      const env = setup({
        [kind === 'catalog' ? 'catalog' : 'movements']: async () => {
          reads++
          throw new InventoryHttpError(code)
        },
      })
      await env.controller.enter()
      if (kind === 'history') await env.controller.selectProduct('a')
      const refused = env.controller.getSnapshot()
      assert.equal(refused[kind].error, code)
      await env.controller[kind === 'catalog' ? 'retryCatalog' : 'retryHistory']()
      assert.equal(reads, 1)
      assert.equal(env.controller.getSnapshot(), refused)
      assert.equal(env.calls.verify, 1)
      env.controller.dispose()
    }
  })
}

test('manual catalog retry does not republish a denied-capability snapshot', async () => {
  const env = setup({}, ['inventory.write'])
  await env.controller.enter()
  const denied = env.controller.getSnapshot()
  assert.equal(denied.catalog.error, 'capability_denied')
  await env.controller.retryCatalog()
  assert.equal(env.controller.getSnapshot(), denied)
  assert.equal(env.calls.catalog, 0)
  assert.equal(env.calls.verify, 1)
  env.controller.dispose()
})

for (const status of [401, 403]) {
  test(`manual history retry handles current ${status} refusal and ignores it after product replacement`, async () => {
    for (const stale of [false, true]) {
      const response = deferred()
      let reads = 0
      const env = setup({
        movements: async () => {
          reads++
          if (reads === 1) throw new InventoryHttpError('unavailable', 503)
          if (reads === 2) return response.promise
          return { items: [{ movement_id: 'replacement' }], next_cursor: null }
        },
      })
      await env.controller.enter()
      await env.controller.selectProduct('a')
      const pending = env.controller.retryHistory()
      await turn()
      if (stale) await env.controller.selectProduct('b')
      response.reject(
        new InventoryHttpError(status === 401 ? 'invalid_session' : 'capability_denied', status),
      )
      await pending
      assert.equal(env.calls.refusal, stale ? 0 : 1)
      assert.equal(env.controller.getSnapshot().product?.product_id ?? null, stale ? 'b' : null)
      assert.equal(env.controller.getSnapshot().history.phase, stale ? 'ready' : 'idle')
      const after = reads
      await env.controller.retryHistory()
      assert.equal(reads, after)
      env.controller.dispose()
    }
  })
}
test('explicit entry only, current read grant and separate stock/history requests', async () => {
  const env = setup()
  assert.equal(env.calls.catalog, 0)
  await env.controller.enter()
  assert.equal(env.calls.catalog, 1)
  await env.controller.selectProduct('a')
  assert.equal(env.calls.stock, 1)
  assert.equal(env.calls.movements, 1)
  assert.equal(env.controller.getSnapshot().stock.value.available_quantity, -7)
  assert.equal(env.controller.getSnapshot().history.phase, 'ready')
  assert.equal(JSON.stringify(env.controller.getSnapshot()).includes('secret'), false)
  env.controller.dispose()
  const denied = setup({}, ['inventory.write'])
  await denied.controller.enter()
  assert.equal(denied.calls.catalog, 0)
  assert.equal(denied.controller.getSnapshot().catalog.error, 'capability_denied')
  denied.controller.dispose()
})
test('product A-B-A fences both stale success and refusal even if abort ignored', async () => {
  for (const refuse of [false, true]) {
    const pending = deferred()
    let calls = 0
    const env = setup({
      stock: async (_s, id) =>
        ++calls === 1 ? pending.promise : { product_id: id, available_quantity: calls },
    })
    await env.controller.enter()
    const first = env.controller.selectProduct('a')
    await turn() // Ensure the noncooperative first request was actually dispatched.
    await env.controller.selectProduct('b')
    await env.controller.selectProduct('a')
    if (refuse) pending.reject(new InventoryHttpError('invalid_session', 401))
    else pending.resolve({ available_quantity: 999 })
    await first
    assert.equal(env.controller.getSnapshot().stock.value.available_quantity, 3)
    assert.equal(env.calls.refusal, 0)
    env.controller.dispose()
  }
})
test('scope/account A-B-A, expiry, offline and disposal clear protected results and suppress late errors', async () => {
  for (const ending of ['scope', 'unavailable', 'dispose']) {
    for (const refuse of [false, true]) {
      const pending = deferred()
      const env = setup({ catalog: () => pending.promise })
      const loading = env.controller.loadCatalog()
      await turn()
      if (ending === 'dispose') env.controller.dispose()
      else if (ending === 'scope') {
        env.change('ready', {
          principal: { organizationId: 'org', userId: 'other' },
          selectedLocationId: 'b',
          capabilities: ['inventory.read'],
        })
        env.change()
      } else env.change('unavailable')
      if (refuse) pending.reject(new InventoryHttpError('capability_denied', 403))
      else pending.resolve([product()])
      await loading
      assert.equal(env.controller.getSnapshot().catalog.value, null)
      assert.equal(env.calls.refusal, 0)
      env.controller.dispose()
    }
  }
})
test('catalog and movement paging replace one page; stock refresh failure clears only stock', async () => {
  let fail = false,
    before
  const env = setup({
    stock: async () => {
      if (fail) throw new InventoryHttpError('unsupported_quantity')
      return { available_quantity: 5 }
    },
    movements: async (_s, _p, b) => {
      before = b
      return { items: [{ movement_id: b ?? 'first' }], next_cursor: b ? null : 'next' }
    },
  })
  await env.controller.enter()
  await env.controller.selectProduct('a')
  const received = env.controller.getSnapshot().history.receivedAt
  fail = true
  await env.controller.refreshStock()
  assert.equal(env.controller.getSnapshot().stock.value, null)
  assert.equal(env.controller.getSnapshot().stock.error, 'unsupported_quantity')
  assert.equal(env.controller.getSnapshot().history.receivedAt, received)
  await env.controller.older()
  assert.equal(before, 'next')
  assert.equal(env.controller.getSnapshot().history.value.items.length, 1)
  await env.controller.newest()
  assert.equal(before, undefined)
  await env.controller.loadCatalog(50)
  assert.equal(env.controller.getSnapshot().product, null)
  assert.equal(env.controller.getSnapshot().stock.value, null)
  env.controller.dispose()
})
test('current refusal goes to runtime exactly once; unsupported response is never retry', async () => {
  const env = setup({
    stock: async () => {
      throw new InventoryHttpError('capability_denied', 403)
    },
  })
  await env.controller.enter()
  await env.controller.selectProduct('a')
  assert.equal(env.calls.refusal, 1)
  assert.equal(env.controller.getSnapshot().product, null)
  env.controller.dispose()
})

test('pre-verification account A-B-A cannot continue under a replacement generation', async () => {
  const env = setup(),
    pending = deferred()
  let account = {
    ...env.runtime.getAccountSnapshot(),
    phase: 'unverified',
    user: null,
    generation: 20,
  }
  env.runtime.getAccountSnapshot = () => account
  env.runtime.verifyAccount = () => {
    account = { ...account, phase: 'verifying', generation: 21 }
    return pending.promise
  }
  const entering = env.controller.enter()
  account = {
    phase: 'connected',
    generation: 23,
    user: { user_id: 'actor', organization_id: 'org' },
  }
  pending.resolve()
  await entering
  assert.equal(env.calls.verify, 0)
  assert.equal(env.calls.catalog, 0)
  env.controller.dispose()
})
test('own synchronous verification generation is accepted and scope selection clears before new submit', async () => {
  const env = setup(),
    pending = deferred(),
    user = env.runtime.getAccountSnapshot().user
  let account = {
    ...env.runtime.getAccountSnapshot(),
    phase: 'unverified',
    user: null,
    generation: 20,
  }
  env.runtime.getAccountSnapshot = () => account
  env.runtime.verifyAccount = () => {
    account = { ...account, phase: 'verifying', generation: 21 }
    return pending.promise
  }
  const entering = env.controller.enter()
  account = { phase: 'connected', generation: 21, user }
  pending.resolve()
  await entering
  assert.equal(env.calls.catalog, 1)
  await env.controller.selectProduct('a')
  env.controller.clearSelection()
  assert.equal(env.controller.getSnapshot().catalog.value, null)
  assert.equal(env.controller.getSnapshot().stock.value, null)
  assert.equal(env.controller.getSnapshot().access.phase, 'unverified')
  env.controller.dispose()
})

test('stock and history complete independently while later same-kind errors are obsolete', async () => {
  const firstStock = deferred(),
    history = deferred()
  let calls = 0
  const env = setup({
    stock: () => (++calls === 1 ? firstStock.promise : Promise.resolve({ available_quantity: 8 })),
    movements: () => history.promise,
  })
  await env.controller.enter()
  const selecting = env.controller.selectProduct('a')
  await turn()
  await env.controller.refreshStock()
  assert.equal(env.controller.getSnapshot().stock.value.available_quantity, 8)
  assert.equal(env.controller.getSnapshot().history.phase, 'loading')
  firstStock.reject(new InventoryHttpError('invalid_session', 401))
  history.resolve({ items: [{ movement_id: 'honest-consume' }], next_cursor: null })
  await selecting
  assert.equal(env.calls.refusal, 0)
  assert.equal(env.controller.getSnapshot().stock.value.available_quantity, 8)
  assert.equal(env.controller.getSnapshot().history.value.items[0].movement_id, 'honest-consume')
  env.controller.dispose()
})
test('late context verification cannot start a catalog on a newer context or cleared scope', async () => {
  for (const clear of [false, true]) {
    const pending = deferred(),
      env = setup()
    env.access.verify = () => pending.promise
    const entering = env.controller.enter()
    await Promise.resolve()
    if (clear) env.controller.clearSelection()
    else env.change()
    pending.resolve()
    await entering
    assert.equal(env.calls.catalog, 0)
    env.controller.dispose()
  }
})

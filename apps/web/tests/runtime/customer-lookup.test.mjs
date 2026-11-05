import test from 'node:test'
import assert from 'node:assert/strict'
import { setup, login, until, api, response, NOW, incarnation } from './runtime-fixture.mjs'
async function ready(t) {
  const f = setup(t)
  f.runtime.scheduleSync = () => {}
  await login(f.runtime)
  return f
}
const token = (f) => f.runtime.getSnapshot().capture.viewToken
const state = (f) => f.runtime.getSnapshot().customerLookup
async function seed(f) {
  for (let i = 0; i < 60; i++)
    await f.runtime.createCustomer({ displayName: i === 59 ? 'Needle distant' : 'Ordinary ' + i })
  await f.runtime.refresh('customer')
}
test('explicit name search scans one admitted page at a time beyond the current browse page', async (t) => {
  const f = await ready(t)
  await seed(f)
  assert.equal(state(f)?.query, '')
  const before = await f.database.operationJournal.toArray()
  let reads = 0
  const original = f.runtime.repositories.page.bind(f.runtime.repositories)
  f.runtime.repositories.page = (...args) => {
    reads++
    return original(...args)
  }
  f.runtime.editCustomerQuery(token(f), 'NEEDLE')
  await f.runtime.searchCustomers(token(f), 'restart')
  assert.equal(reads, 1)
  assert.equal(state(f).matches.length, 0)
  assert.ok(state(f).nextAfterId)
  assert.equal(state(f).pages, 1)
  await f.runtime.searchCustomers(token(f), 'continue')
  assert.equal(reads, 2)
  assert.equal(state(f).matches.length, 1)
  assert.equal(state(f).matches[0].display_name, 'Needle distant')
  assert.equal(state(f).nextAfterId, null)
  assert.equal(f.runtime.getSnapshot().capture.order.draft.customerId, '')
  assert.deepEqual(await f.database.operationJournal.toArray(), before)
  const selected = state(f).matches[0]
  f.runtime.editCaptureOrder(token(f), 'customerId', selected.customer_id)
  await until(() => state(f).selection.status === 'available', 'selected resolved')
  f.runtime.editCustomerQuery(token(f), 'no match')
  await f.runtime.searchCustomers(token(f), 'restart')
  assert.equal(state(f).selection.customer.customer_id, selected.customer_id)
  assert.equal(f.runtime.getSnapshot().capture.order.draft.customerId, selected.customer_id)
})
test('query edit fences delayed actual page results and double search stays single flight', async (t) => {
  const f = await ready(t)
  assert.equal(state(f)?.query, '')
  let release
  const gate = new Promise((r) => {
    release = r
  })
  let calls = 0
  const original = f.runtime.repositories.page.bind(f.runtime.repositories)
  f.runtime.repositories.page = async (...args) => {
    calls++
    const result = await original(...args)
    await gate
    return result
  }
  f.runtime.editCustomerQuery(token(f), 'Private')
  const pending = f.runtime.searchCustomers(token(f), 'restart')
  await until(() => calls === 1, 'read started')
  await f.runtime.searchCustomers(token(f), 'restart')
  f.runtime.editCustomerQuery(token(f), 'other')
  release()
  await pending
  assert.equal(calls, 1)
  assert.deepEqual(state(f).matches, [])
  assert.equal(state(f).query, 'other')
})
test('masked lookup drops all labels and a late current-grant selected read cannot republish', async (t) => {
  const f = await ready(t)
  assert.equal(state(f)?.query, '')
  let release
  const gate = new Promise((r) => {
    release = r
  })
  const original = f.runtime.repositories.selectedCustomer.bind(f.runtime.repositories)
  f.runtime.repositories.selectedCustomer = async (...args) => {
    const value = await original(...args)
    await gate
    return value
  }
  f.runtime.editCaptureOrder(token(f), 'customerId', 'historical-A')
  await f.runtime.logout()
  release()
  await new Promise((r) => setImmediate(r))
  assert.equal(f.runtime.getSnapshot().customerLookup, null)
  assert.equal(JSON.stringify(f.runtime.getSnapshot()).includes('Private A'), false)
})
test('query bounds read nothing and unavailable current selection preserves draft without command', async (t) => {
  const f = await ready(t)
  assert.equal(state(f)?.query, '')
  let reads = 0
  const original = f.runtime.repositories.page.bind(f.runtime.repositories)
  f.runtime.repositories.page = (...args) => {
    reads++
    return original(...args)
  }
  for (const query of [' ', 'x'.repeat(201)]) {
    f.runtime.editCustomerQuery(token(f), query)
    await f.runtime.searchCustomers(token(f), 'restart')
  }
  assert.equal(reads, 0)
  f.runtime.editCaptureOrder(token(f), 'customerId', 'missing-customer')
  f.runtime.editCaptureOrder(token(f), 'reportedProblem', 'Keep this draft')
  await until(() => state(f).selection.status === 'unavailable', 'missing selection')
  await f.runtime.submitCaptureOrder(token(f))
  assert.equal(await f.database.operationJournal.count(), 0)
  assert.equal(f.runtime.getSnapshot().capture.order.draft.customerId, 'missing-customer')
  assert.equal(f.runtime.getSnapshot().capture.order.draft.reportedProblem, 'Keep this draft')
  f.runtime.editCaptureOrder(token(f), 'customerId', 'historical-A')
  await until(() => state(f).selection.status === 'available', 'valid replacement')
  await f.runtime.submitCaptureOrder(token(f))
  assert.equal(await f.database.operationJournal.count(), 1)
})

test('actual order form does not submit a pending lookup selection', async (t) => {
  const f = await ready(t)
  const { mount } = await import('./capture-component-host.mjs')
  let submitted = 0
  const capture = {
    ...f.runtime.getSnapshot().capture.order,
    draft: {
      ...f.runtime.getSnapshot().capture.order.draft,
      customerId: 'historical-A',
      reportedProblem: 'Keep',
    },
  }
  const form = mount('../../src/features/orders/OrderQuickIntake.tsx', 'OrderQuickIntake', {
    capture,
    customers: [{ customer_id: 'historical-A', display_name: 'Private A' }],
    lookup: {
      query: '',
      searching: false,
      matches: [],
      nextAfterId: null,
      pages: 0,
      busy: true,
      message: null,
      selection: { id: 'historical-A', status: 'pending', customer: null },
    },
    onEdit() {},
    onSubmit: async () => {
      submitted++
    },
  })
  await form.submit()
  assert.equal(submitted, 0)
})

for (const nativeEvent of [
  { isComposing: true, keyCode: 13 },
  { isComposing: false, keyCode: 229 },
  { isComposing: true, keyCode: 229 },
]) {
  test(`lookup leaves composition Enter to the input method ${JSON.stringify(nativeEvent)}`, async (t) => {
    const f = await ready(t)
    const { mount } = await import('./capture-component-host.mjs')
    const capture = f.runtime.getSnapshot().capture.order
    let searches = 0,
      submits = 0,
      edits = 0
    let lookup = { ...state(f), query: '山田' }
    const props = () => ({
      capture,
      customers: [],
      lookup,
      onEdit() {
        edits++
      },
      onQuery() {
        edits++
      },
      onSearch: async (action) => {
        assert.equal(action, 'restart')
        searches++
      },
      onSubmit: async () => {
        submits++
      },
    })
    const form = mount('../../src/features/orders/OrderQuickIntake.tsx', 'OrderQuickIntake', props)
    for (const busy of [false, true]) {
      lookup = { ...lookup, busy }
      form.setProps(props)
      assert.equal(form.press('Buscar cliente por nombre', 'Enter', nativeEvent), false)
      assert.equal(searches, 0)
      assert.equal(submits, 0)
      assert.equal(edits, 0)
      assert.equal(form.value('Buscar cliente por nombre'), '山田')
      assert.equal(form.value('Cliente'), capture.draft.customerId)
      assert.equal(form.value('Problema reportado'), capture.draft.reportedProblem)
    }
    assert.equal(form.press('Buscar cliente por nombre', 'Enter'), true)
    assert.equal(searches, 0, 'ordinary Enter while busy still suppresses form submission')
    lookup = { ...lookup, busy: false }
    form.setProps(props)
    assert.equal(form.press('Buscar cliente por nombre', 'ArrowDown'), false)
    assert.equal(searches, 0)
    assert.equal(form.press('Buscar cliente por nombre', 'Enter'), true)
    assert.equal(searches, 1, 'ordinary Enter after composition starts one explicit lookup')
    assert.equal(submits, 0)
    assert.equal(edits, 0)
  })
}

test('busy subscriber masking prevents even starting the captured page read', async (t) => {
  const f = await ready(t)
  let notifications = 0
  t.mock.method(f.runtime.branding, 'refreshOfflineAfterLocalActivity', () => {
    notifications++
  })
  let reads = 0,
    masked = false,
    logout
  const original = f.runtime.repositories.page.bind(f.runtime.repositories)
  f.runtime.repositories.page = (...args) => {
    reads++
    return original(...args)
  }
  t.after(
    f.runtime.subscribe(() => {
      if (!masked && state(f)?.busy) {
        masked = true
        logout = f.runtime.logout()
      }
    }),
  )
  f.runtime.editCustomerQuery(token(f), 'Private')
  await f.runtime.searchCustomers(token(f), 'restart')
  await logout
  assert.equal(masked, true)
  assert.equal(reads, 0)
  assert.equal(notifications, 0)
})
test('failed selected read is explicit and query edits never retry it implicitly', async (t) => {
  const f = await ready(t)
  let reads = 0
  const original = f.runtime.repositories.selectedCustomer.bind(f.runtime.repositories)
  f.runtime.repositories.selectedCustomer = async () => {
    reads++
    throw new Error('private-error-canary')
  }
  f.runtime.editCaptureOrder(token(f), 'customerId', 'historical-A')
  await until(() => !state(f).busy, 'failed pin settled')
  assert.equal(state(f).selection.status, 'failed')
  assert.equal(state(f).selection.customer, null)
  assert.equal(JSON.stringify(state(f)).includes('private-error-canary'), false)
  f.runtime.editCustomerQuery(token(f), 'changed')
  await new Promise((r) => setImmediate(r))
  assert.equal(reads, 1)
  f.runtime.repositories.selectedCustomer = original
  await f.runtime.retryCustomerSelection(token(f))
  assert.equal(state(f).selection.status, 'available')
})

test('lookup form identifies same-name choices across pages and treats empty search as partial', async (t) => {
  const f = await ready(t)
  const { mount } = await import('./capture-component-host.mjs')
  let searches = 0,
    submits = 0
  let lookup = {
    query: 'Same',
    searching: true,
    matches: [],
    pages: 1,
    nextAfterId: 'cursor',
    busy: false,
    message: null,
    selection: { id: '', status: 'none', customer: null },
  }
  const form = mount('../../src/features/orders/OrderQuickIntake.tsx', 'OrderQuickIntake', () => ({
    capture: f.runtime.getSnapshot().capture.order,
    customers: [],
    lookup,
    onEdit() {},
    onQuery() {},
    onSearch: async () => {
      searches++
    },
    onSubmit: async () => {
      submits++
    },
  }))
  assert.equal(form.text().includes('Primero registra'), false)
  assert.match(form.text(), /Quedan páginas locales/)
  assert.equal(form.press('Buscar cliente por nombre', 'Enter'), true)
  assert.equal(searches, 1)
  assert.equal(submits, 0)
  for (const id of ['id-first', 'id-second']) {
    lookup = { ...lookup, matches: [{ customer_id: id, display_name: 'Same' }] }
    form.setProps(() => ({
      capture: f.runtime.getSnapshot().capture.order,
      customers: [],
      lookup,
      onEdit() {},
      onSubmit: async () => {
        submits++
      },
    }))
    assert.ok(form.optionLabels('Cliente').includes(`Same · ${id}`))
  }
})

test('selection ABA rejects the original pending pin receipt', async (t) => {
  const f = await ready(t)
  let release,
    calls = 0
  const gate = new Promise((r) => {
    release = r
  })
  const original = f.runtime.repositories.selectedCustomer.bind(f.runtime.repositories)
  f.runtime.repositories.selectedCustomer = async (...args) => {
    calls++
    const result = await original(...args)
    if (calls === 1) await gate
    return result
  }
  f.runtime.editCaptureOrder(token(f), 'customerId', 'historical-A')
  await until(() => calls === 1, 'pin read held')
  f.runtime.editCustomerQuery(token(f), 'Private')
  assert.equal(calls, 1)
  f.runtime.editCaptureOrder(token(f), 'customerId', 'missing')
  f.runtime.editCaptureOrder(token(f), 'customerId', 'historical-A')
  release()
  await until(() => state(f).selection.status === 'available', 'latest ABA pin resolved')
  assert.equal(calls, 2)
  assert.equal(state(f).selection.customer.customer_id, 'historical-A')
})
test('same-scope reverify erases query but rehydrates selected label through current read', async (t) => {
  const f = await ready(t)
  f.runtime.editCaptureOrder(token(f), 'customerId', 'historical-A')
  await until(() => state(f).selection.status === 'available', 'first pin')
  f.runtime.editCustomerQuery(token(f), 'Private')
  await f.runtime.searchCustomers(token(f), 'restart')
  assert.equal(state(f).matches.length, 1)
  await f.runtime.retryVerification()
  await until(() => state(f)?.selection.status === 'available', 'fresh READY pin')
  assert.equal(state(f).query, '')
  assert.deepEqual(state(f).matches, [])
  assert.equal(f.runtime.getSnapshot().capture.order.draft.customerId, 'historical-A')
  assert.equal(state(f).selection.customer.display_name, 'Private A')
})
test('lookup lowercases without accent folding and does not adopt the first match', async (t) => {
  const f = await ready(t)
  f.runtime.editCustomerQuery(token(f), 'PRIVATE')
  await f.runtime.searchCustomers(token(f), 'restart')
  assert.equal(state(f).matches.length, 1)
  f.runtime.editCustomerQuery(token(f), 'PRÍVATE')
  await f.runtime.searchCustomers(token(f), 'restart')
  assert.equal(state(f).matches.length, 0)
  assert.equal(f.runtime.getSnapshot().capture.order.draft.customerId, '')
})
test('available selected pin keeps form usable when the browse page is empty', async (t) => {
  const f = await ready(t)
  const { mount } = await import('./capture-component-host.mjs')
  let submitted = 0
  const capture = {
    ...f.runtime.getSnapshot().capture.order,
    draft: {
      ...f.runtime.getSnapshot().capture.order.draft,
      customerId: 'historical-A',
      reportedProblem: 'Keep',
    },
  }
  const form = mount('../../src/features/orders/OrderQuickIntake.tsx', 'OrderQuickIntake', {
    capture,
    customers: [],
    lookup: {
      query: '',
      searching: false,
      matches: [],
      nextAfterId: null,
      pages: 0,
      busy: false,
      message: null,
      selection: {
        id: 'historical-A',
        status: 'available',
        customer: { customer_id: 'historical-A', display_name: 'Private A' },
      },
    },
    onEdit() {},
    onSubmit: async () => {
      submitted++
    },
  })
  assert.equal(form.disabled(), false)
  assert.ok(form.optionLabels('Cliente').includes('Private A'))
  await form.submit()
  assert.equal(submitted, 1)
})

test('typing during a selected read keeps the same pin eligible without extra I/O', async (t) => {
  const f = await ready(t)
  let release,
    calls = 0
  const gate = new Promise((r) => {
    release = r
  })
  const original = f.runtime.repositories.selectedCustomer.bind(f.runtime.repositories)
  f.runtime.repositories.selectedCustomer = async (...args) => {
    calls++
    const result = await original(...args)
    await gate
    return result
  }
  f.runtime.editCaptureOrder(token(f), 'customerId', 'historical-A')
  await until(() => calls === 1, 'pin held')
  f.runtime.editCustomerQuery(token(f), 'typed while checking')
  release()
  await until(() => !state(f).busy, 'pin settled')
  assert.equal(calls, 1)
  assert.equal(state(f).selection.status, 'available')
  assert.equal(state(f).selection.customer.customer_id, 'historical-A')
})

test('current read-grant loss clears query results and selected labels', async (t) => {
  const original = api()
  let revoked = false
  const server = {
    fetch: async (url, init) => {
      const r = await original.fetch(url, init)
      const data = await r.json()
      if (revoked) {
        const context = new URL(url).pathname.endsWith('/auth/context') ? data : data.context
        if (context?.capabilities)
          context.capabilities = context.capabilities.filter((x) => x !== 'customers.read')
      }
      return response(url, data)
    },
  }
  const f = setup(t, { server })
  f.runtime.scheduleSync = () => {}
  await login(f.runtime)
  f.runtime.editCaptureOrder(token(f), 'customerId', 'historical-A')
  await until(() => state(f)?.selection.status === 'available', 'authorized pin')
  f.runtime.editCustomerQuery(token(f), 'Private')
  await f.runtime.searchCustomers(token(f), 'restart')
  assert.equal(state(f).matches.length, 1)
  revoked = true
  await f.runtime.retryVerification()
  assert.equal(state(f), null)
  assert.equal(JSON.stringify(f.runtime.getSnapshot()).includes('Private A'), false)
})

function isLogoDigest(args) {
  const value = args[1]
  const bytes = ArrayBuffer.isView(value)
    ? new Uint8Array(value.buffer, value.byteOffset, value.byteLength)
    : new Uint8Array(value)
  return [137, 80, 78, 71, 13, 10, 26, 10].every((byte, index) => bytes[index] === byte)
}
function brandedApi(grants = ['branding.read'], handle) {
  const server = api(),
    original = server.fetch
  server.fetch = async (url, init) => {
    if (url.endsWith('/branding')) {
      server.calls.push(new URL(url).pathname)
      if (handle) return handle(url, init)
      return response(url, {
        schema_version: 1,
        organization_id: 'org',
        location_id: 'loc',
        dataset_incarnation: incarnation,
        version: 1,
        display_name: 'Shared workshop',
        palette_id: 'arcilla',
        logo_state: 'none',
        logo: null,
        logo_diagnostic: null,
        updated_at: new Date(NOW).toISOString(),
        updated_by: 'A',
      })
    }
    const value = await (await original(url, init)).json()
    if (Array.isArray(value.capabilities)) value.capabilities.push(...grants)
    if (value.context?.capabilities) value.context.capabilities.push(...grants)
    return response(url, value)
  }
  return server
}
for (const activity of ['lookup', 'control'])
  test(`offline branding remains available after ${activity} activity across bounded logo reads`, async (t) => {
    const { withLogo } = await import('../branding/fixture.mjs')
    const f = setup(t, {
      server: brandedApi(['branding.read'], (url) =>
        response(url, withLogo({ display_name: 'Shared workshop' })),
      ),
    })
    f.runtime.scheduleSync = () => {}
    await login(f.runtime)
    await until(() => f.runtime.branding.getSnapshot().profile !== null, 'initial brand')
    const snapshots = await f.database.brandingSnapshots.toArray()
    const digest = crypto.subtle.digest.bind(crypto.subtle)
    let releaseFirst,
      releaseSecond,
      firstEntered,
      secondEntered,
      calls = 0
    const firstGate = new Promise((resolve) => {
        releaseFirst = resolve
      }),
      secondGate = new Promise((resolve) => {
        releaseSecond = resolve
      })
    const firstStarted = new Promise((resolve) => {
        firstEntered = resolve
      }),
      secondStarted = new Promise((resolve) => {
        secondEntered = resolve
      })
    t.after(() => {
      releaseFirst()
      releaseSecond()
    })
    t.mock.method(crypto.subtle, 'digest', async (...args) => {
      if (isLogoDigest(args)) {
        calls++
        if (calls === 1) {
          firstEntered()
          await firstGate
        }
        if (calls === 2) {
          secondEntered()
          await secondGate
        }
      }
      return digest(...args)
    })
    f.env.online = false
    await f.runtime.offline()
    await firstStarted
    f.env.now = NOW + 10
    const view = f.runtime.getSnapshot().capture.viewToken
    f.runtime.editCustomerQuery(view, 'Private')
    if (activity === 'lookup') await f.runtime.searchCustomers(view, 'restart')
    // One genuine explicit refresh queued behind the held first read.
    void f.runtime.branding.refresh(true)
    releaseFirst()
    if (activity === 'control') {
      releaseSecond()
      await until(() => !f.runtime.branding.getSnapshot().loading, 'control completion')
      assert.equal(f.runtime.branding.getSnapshot().profile?.display_name, 'Shared workshop')
      assert.equal(f.runtime.branding.getSnapshot().cached, true)
      return
    }
    await secondStarted
    f.env.now = NOW + 20
    if (activity === 'lookup') await f.runtime.searchCustomers(view, 'restart')
    releaseSecond()
    await until(() => !f.runtime.branding.getSnapshot().loading, 'final cache read')
    assert.equal(f.runtime.getSnapshot().phase, 'ready')
    assert.equal((await f.database.operationJournal.toArray()).length, 0)
    if (activity === 'lookup')
      assert.deepEqual(await f.database.brandingSnapshots.toArray(), snapshots)
    assert.equal(f.runtime.branding.getSnapshot().profile?.display_name, 'Shared workshop')
    assert.equal(f.runtime.branding.getSnapshot().cached, true)
    if (activity === 'lookup')
      assert.deepEqual(await f.database.brandingSnapshots.toArray(), snapshots)
  })

for (const cancellation of ['query', 'logout', 'publish'])
  test(`resolved lookup activity notifies branding only with current source after ${cancellation}`, async (t) => {
    const f = await ready(t)
    let notifications = 0
    t.mock.method(f.runtime.branding, 'refreshOfflineAfterLocalActivity', () => {
      notifications++
    })
    let release
    const gate = new Promise((resolve) => {
      release = resolve
    })
    const original = f.runtime.repositories.page.bind(f.runtime.repositories)
    let entered = false
    f.runtime.repositories.page = async (...args) => {
      const result = await original(...args)
      entered = true
      await gate
      return result
    }
    const view = token(f)
    f.runtime.editCustomerQuery(view, 'Private')
    const pending = f.runtime.searchCustomers(view, 'restart')
    await until(() => entered, 'actual read completed')
    if (cancellation === 'query') f.runtime.editCustomerQuery(view, 'Other')
    if (cancellation === 'logout') await f.runtime.logout()
    let unsubscribe = () => {}
    if (cancellation === 'publish')
      unsubscribe = f.runtime.subscribe(() => {
        if (f.runtime.getSnapshot().customerLookup?.busy === false) {
          unsubscribe()
          void f.runtime.logout()
        }
      })
    release()
    await pending
    unsubscribe()
    assert.equal(notifications, cancellation === 'query' ? 1 : 0)
  })

test('selected null receipt notifies activity once but query typing and thrown reads do not', async (t) => {
  const f = await ready(t)
  f.runtime.editCaptureOrder(token(f), 'customerId', 'missing-selected')
  await until(
    () =>
      state(f).selection.status === 'unavailable' &&
      f.runtime.getSnapshot().capture.order.recoveryMessage ===
        'Borrador guardado para recuperar al recargar esta sesión.',
    'initial read and actual draft checkpoint settled',
  )
  let notifications = 0
  t.mock.method(f.runtime.branding, 'refreshOfflineAfterLocalActivity', () => {
    notifications++
  })
  await f.runtime.retryCustomerSelection(token(f))
  assert.equal(notifications, 1)
  f.runtime.editCustomerQuery(token(f), 'Private')
  assert.equal(notifications, 1)
  t.mock.method(f.runtime.repositories, 'selectedCustomer', async () => {
    throw new Error('synthetic read failure')
  })
  await f.runtime.retryCustomerSelection(token(f))
  assert.equal(notifications, 1)
})

test('resolved page then failed selected refresh still signals one activity event', async (t) => {
  const f = await ready(t)
  f.runtime.editCaptureOrder(token(f), 'customerId', 'historical-A')
  await until(() => state(f).selection.status === 'available', 'initial pin')
  let notifications = 0
  t.mock.method(f.runtime.branding, 'refreshOfflineAfterLocalActivity', () => {
    notifications++
  })
  t.mock.method(f.runtime.repositories, 'selectedCustomer', async () => {
    throw new Error('synthetic pin failure')
  })
  f.runtime.editCustomerQuery(token(f), 'Private')
  await f.runtime.searchCustomers(token(f), 'restart')
  assert.equal(notifications, 1)
  assert.equal(state(f).selection.status, 'failed')
})

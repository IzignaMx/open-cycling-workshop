import test from 'node:test'
import assert from 'node:assert/strict'
import { setup, login, api, response, until } from './runtime-fixture.mjs'
const CUSTOMER_ID = '0199ba00-0000-7000-8000-000000000099'
const view = (f) => f.runtime.getSnapshot().capture.viewToken
async function ready(t) {
  const base = api()
  const server = {
    fetch: async (url, init) => {
      const r = await base.fetch(url, init)
      return response(
        url,
        JSON.parse(JSON.stringify(await r.json()).replaceAll('historical-A', CUSTOMER_ID)),
      )
    },
  }
  const f = setup(t, { server })
  f.runtime.scheduleSync = () => {}
  await login(f.runtime)
  await f.runtime.openCustomerEdit(view(f), CUSTOMER_ID)
  assert.ok(f.runtime.getSnapshot().customerEdit.draft)
  return f
}
test('existing customer save preserves entity id and journals one update', async (t) => {
  const f = await ready(t)
  const v = view(f)
  f.runtime.editExistingCustomer(v, 'displayName', 'Edited')
  await f.runtime.submitCustomerEdit(v)
  assert.equal(f.runtime.getSnapshot().customerEdit.draft, null)
  const journal = await f.runtime.database.operationJournal.toArray()
  assert.equal(journal.length, 1)
  assert.equal(journal[0].envelope.operation, 'update')
  assert.equal(journal[0].envelope.base_version, 1)
  assert.equal(journal[0].entityId, CUSTOMER_ID)
})
test('dirty replacement is refused and cancel needs explicit discard', async (t) => {
  const f = await ready(t)
  const v = view(f)
  f.runtime.editExistingCustomer(v, 'phone', '555')
  await f.runtime.openCustomerEdit(v, 'missing')
  assert.equal(f.runtime.getSnapshot().customerEdit.draft.phone, '555')
  f.runtime.cancelCustomerEdit(v)
  assert.ok(f.runtime.getSnapshot().customerEdit.draft)
  f.runtime.cancelCustomerEdit(v, true)
  assert.equal(f.runtime.getSnapshot().customerEdit.draft, null)
})
test('unknown update cannot be repeated or cancelled and old view cannot write', async (t) => {
  const f = await ready(t)
  const v = view(f)
  f.runtime.editExistingCustomer(v, 'phone', '555')
  let calls = 0
  f.runtime.repositories.updateCustomer = async () => {
    calls++
    throw new Error('unknown')
  }
  await f.runtime.submitCustomerEdit(v)
  await f.runtime.submitCustomerEdit(v)
  f.runtime.cancelCustomerEdit(v, true)
  assert.equal(calls, 1)
  assert.equal(f.runtime.getSnapshot().customerEdit.blocked, true)
  await f.runtime.logout()
  f.runtime.editExistingCustomer(v, 'phone', 'leak')
  await f.runtime.submitCustomerEdit(v)
  assert.equal(f.runtime.getSnapshot().customerEdit, null)
  assert.equal(calls, 1)
})
test('known version mismatch retains fields without rebasing or overwriting', async (t) => {
  const f = await ready(t)
  const v = view(f)
  f.runtime.editExistingCustomer(v, 'phone', '555')
  f.runtime.repositories.updateCustomer = async () => ({ status: 'not_saved', reason: 'changed' })
  await f.runtime.submitCustomerEdit(v)
  const edit = f.runtime.getSnapshot().customerEdit
  assert.equal(edit.draft.phone, '555')
  assert.equal(edit.draft.baseVersion, 1)
  assert.match(edit.message, /cambió/)
  assert.equal((await f.runtime.database.operationJournal.toArray()).length, 0)
})
test('unsent customer edit is memory-only and absent after same-session reload', async (t) => {
  const f = await ready(t)
  const v = view(f)
  f.runtime.editExistingCustomer(v, 'phone', 'reload-555')
  await new Promise((resolve) => setTimeout(resolve, 30))
  for (const table of f.database.tables)
    assert.equal(JSON.stringify(await table.toArray()).includes('reload-555'), false, table.name)
  assert.equal(JSON.stringify([...f.storage.values]).includes('reload-555'), false)
  f.runtime.dispose()
  const restored = setup(t, { name: f.name, storage: f.storage, server: f.server, online: false })
  restored.runtime.scheduleSync = () => {}
  await restored.runtime.start()
  await until(() => restored.runtime.getSnapshot().phase === 'ready', 'reload not ready')
  const edit = restored.runtime.getSnapshot().customerEdit
  assert.equal(edit.draft, null)
  assert.equal(edit.dirty, false)
  assert.equal((await restored.database.operationJournal.toArray()).length, 0)
})
test('pending update is single-flight and logout masks stale completion', async (t) => {
  const f = await ready(t)
  const v = view(f)
  f.runtime.editExistingCustomer(v, 'phone', 'single')
  let release, entered
  const reached = new Promise((r) => (entered = r))
  let calls = 0
  f.runtime.repositories.updateCustomer = async () => {
    calls++
    entered()
    await new Promise((r) => (release = r))
    return { status: 'not_saved', reason: 'write_failure' }
  }
  const saving = f.runtime.submitCustomerEdit(v)
  await reached
  await f.runtime.submitCustomerEdit(v)
  f.runtime.editExistingCustomer(v, 'phone', 'lost')
  assert.equal(f.runtime.getSnapshot().customerEdit.draft.phone, 'single')
  await f.runtime.logout()
  release()
  await saving
  assert.equal(calls, 1)
  assert.equal(f.runtime.getSnapshot().customerEdit, null)
})
test('late edit read cannot replace edits entered while it was pending', async (t) => {
  const f = await ready(t)
  const v = view(f)
  let release
  const old = f.runtime.repositories.editableCustomer.bind(f.runtime.repositories)
  f.runtime.repositories.editableCustomer = async (...args) => {
    const c = await old(...args)
    await new Promise((r) => (release = r))
    return c
  }
  const opening = f.runtime.openCustomerEdit(v, CUSTOMER_ID)
  await until(() => !!release, 'read did not start')
  f.runtime.editExistingCustomer(v, 'phone', 'kept')
  release()
  await opening
  assert.equal(f.runtime.getSnapshot().customerEdit.draft.phone, 'kept')
})
test('committed update with lost acknowledgement survives reload without draft or replay', async (t) => {
  const f = await ready(t)
  const v = view(f)
  f.runtime.editExistingCustomer(v, 'phone', 'unknown-reload')
  const update = f.runtime.repositories.updateCustomer.bind(f.runtime.repositories)
  f.runtime.repositories.updateCustomer = async (...args) => {
    const result = await update(...args)
    assert.equal(result.status, 'committed')
    throw new Error('lost acknowledgement')
  }
  await f.runtime.submitCustomerEdit(v)
  f.runtime.dispose()
  const restored = setup(t, { name: f.name, storage: f.storage, server: f.server, online: false })
  restored.runtime.scheduleSync = () => {}
  await restored.runtime.start()
  await until(() => restored.runtime.getSnapshot().phase === 'ready', 'reload not ready')
  assert.equal(restored.runtime.getSnapshot().customerEdit.draft, null)
  let calls = 0
  restored.runtime.repositories.updateCustomer = async () => {
    calls++
    throw new Error('unexpected')
  }
  await restored.runtime.submitCustomerEdit(view(restored))
  assert.equal(calls, 0)
  assert.equal((await restored.database.operationJournal.toArray()).length, 1)
})

test('network re-admission clears memory-only edit and rejects stale handlers', async (t) => {
  const f = await ready(t)
  const oldView = view(f)
  f.runtime.editExistingCustomer(oldView, 'phone', 'interrupted-private-edit')
  await f.runtime.reconnect()
  await until(() => f.runtime.getSnapshot().phase === 'ready', 'not readmitted')
  assert.equal(f.runtime.getSnapshot().customerEdit.draft, null)
  f.runtime.editExistingCustomer(oldView, 'phone', 'stale')
  await f.runtime.submitCustomerEdit(oldView)
  assert.equal((await f.database.operationJournal.toArray()).length, 0)
})

test('customer list preserves exact standalone name text beside its accessible edit action', async (t) => {
  const f = await ready(t)
  const { appHarness } = await import('./capture-component-host.mjs')
  const React = await import('react')
  const { renderToStaticMarkup } = await import('react-dom/server')
  const nodes = (node) =>
    !node || typeof node !== 'object'
      ? []
      : [node, ...[node.props?.children].flat(Infinity).flatMap(nodes)]
  const tree = appHarness(f.runtime).render()
  const list = nodes(tree).find(
    (node) => node.type === 'ul' && node.props['aria-label'] === 'Clientes locales',
  )
  assert.ok(list)
  function native(node) {
    if (node === null || node === undefined || typeof node !== 'object') return node
    if (Array.isArray(node)) return node.map(native)
    const { children, ...props } = node.props
    return React.createElement(
      typeof node.type === 'string' ? node.type : 'button',
      props,
      native(children),
    )
  }
  const html = renderToStaticMarkup(native(list))
  // Exact text locators need a distinct element containing only the customer name,
  // not the enclosing list item's combined "Private AEditar" text.
  assert.match(html, /<([a-z][a-z0-9]*)[^>]*>Private A<\/\1>/)
  const edit = nodes(list).find((node) => node.props?.['aria-label'] === 'Editar cliente Private A')
  assert.ok(edit)
  assert.equal(edit.props.children, 'Editar')
  const calls = []
  f.runtime.openCustomerEdit = async (...args) => {
    calls.push(args)
  }
  edit.props.onClick()
  assert.deepEqual(calls, [[view(f), CUSTOMER_ID]])
})

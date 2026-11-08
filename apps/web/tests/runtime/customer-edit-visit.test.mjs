import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync, existsSync } from 'node:fs'
import ts from 'typescript'
const path = new URL('../../src/runtime/customer-edit-visit.ts', import.meta.url)
const module = { exports: {} }
if (existsSync(path))
  new Function(
    'module',
    'exports',
    ts.transpileModule(readFileSync(path, 'utf8'), {
      compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
    }).outputText,
  )(module, module.exports)
const { CustomerEditVisit } = module.exports
const customer = {
  customer_id: 'c1',
  version: 3,
  display_name: 'Original',
  email: null,
  phone: '123',
}
function fresh() {
  assert.equal(typeof CustomerEditVisit, 'function')
  const owner = new CustomerEditVisit()
  owner.observeScope('scope')
  return owner
}
test('edit owns original version, immutable snapshots and current fields', () => {
  const owner = fresh()
  owner.open(customer)
  owner.edit('displayName', 'Changed')
  const s = owner.snapshot()
  assert.equal(s.draft.baseVersion, 3)
  assert.equal(s.dirty, true)
  assert.ok(Object.isFrozen(s.draft))
  assert.equal(owner.open({ ...customer, customer_id: 'c2' }), false)
})
test('one pending submission refuses edit, cancel and selection replacement', () => {
  const owner = fresh()
  owner.open(customer)
  owner.edit('phone', '456')
  const attempt = owner.begin()
  assert.ok(attempt)
  assert.equal(owner.begin(), null)
  assert.equal(owner.edit('phone', '789'), false)
  assert.equal(owner.cancel(), false)
  assert.equal(owner.open(customer), false)
  owner.finish(attempt.token, { status: 'not_saved', message: 'retry', blockSubmission: false })
  assert.equal(owner.snapshot().draft.phone, '456')
  assert.ok(owner.begin())
})
test('unknown stays protected during same-screen scope observation and refuses cancel', () => {
  const owner = fresh()
  owner.open(customer)
  owner.edit('phone', '456')
  const attempt = owner.begin()
  owner.finish(attempt.token, { status: 'unknown', message: 'verify', blockSubmission: true })
  owner.observeScope('scope')
  assert.equal(owner.begin(), null)
  assert.equal(owner.cancel(), false)
  assert.equal(owner.snapshot().draft.phone, '456')
})
test('saved clears draft, stale completion cannot clear newer scope', () => {
  const owner = fresh()
  owner.open(customer)
  owner.edit('phone', '456')
  const attempt = owner.begin()
  owner.observeScope('new scope')
  assert.equal(owner.snapshot().draft, null)
  assert.equal(
    owner.finish(attempt.token, { status: 'saved', message: null, blockSubmission: false }),
    false,
  )
})
test('clean cancel and explicit dirty discard; no silent replacement', () => {
  const owner = fresh()
  owner.open(customer)
  assert.equal(owner.cancel(), true)
  owner.open(customer)
  owner.edit('email', 'a@example.test')
  assert.equal(owner.cancel(), false)
  assert.equal(owner.cancel(true), true)
  assert.equal(owner.snapshot().draft, null)
})

test('editor renders accessible labels, status and disabled protected controls', async () => {
  const React = await import('react')
  const { renderToStaticMarkup } = await import('react-dom/server')
  const { createRequire } = await import('node:module')
  const require = createRequire(import.meta.url)
  const code = ts.transpileModule(
    readFileSync(new URL('../../src/features/customers/CustomerEdit.tsx', import.meta.url), 'utf8'),
    {
      compilerOptions: {
        jsx: ts.JsxEmit.ReactJSX,
        module: ts.ModuleKind.CommonJS,
        target: ts.ScriptTarget.ES2022,
      },
    },
  ).outputText
  const m = { exports: {} }
  new Function('require', 'module', 'exports', code)(
    (name) =>
      name === '@ocwp/ui'
        ? { Button: (props) => React.createElement('button', props) }
        : require(name),
    m,
    m.exports,
  )
  const owner = fresh()
  owner.open(customer)
  const astralName = '😀'.repeat(200)
  owner.edit('displayName', astralName)
  owner.edit('phone', 'changed')
  const pending = owner.begin()
  owner.finish(pending.token, {
    status: 'unknown',
    message: 'No lo repitas',
    blockSubmission: true,
  })
  const html = renderToStaticMarkup(
    React.createElement(m.exports.CustomerEdit, {
      edit: owner.snapshot(),
      onEdit() {},
      async onSubmit() {},
      onCancel() {},
    }),
  )
  assert.doesNotMatch(html, /maxlength/i)
  assert.ok(html.includes(`value="${astralName}"`))
  assert.equal(owner.snapshot().draft.displayName, astralName)
  assert.match(html, /fieldset disabled/)
  assert.match(html, /aria-describedby="customer-edit-status customer-edit-lifetime"/)
  assert.match(html, /data-dirty="true"/)
  assert.match(html, /No lo repitas/)
  assert.match(html, /Se pierde al recargar/)
  assert.match(html, /no se recupera después/)
  for (const label of ['Nombre', 'Correo', 'Teléfono']) assert.match(html, new RegExp(label))
  assert.match(html, /type="email"/)
  assert.match(html, /type="tel"/)
})
test('memory-only editor has no hydration API that could restore unsent fields', () => {
  const owner = fresh()
  assert.equal('hydrate' in owner, false)
})

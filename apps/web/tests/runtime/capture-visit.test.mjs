import assert from 'node:assert/strict'
import { readFileSync, existsSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import test from 'node:test'
import ts from 'typescript'

function load(path) {
  const output = ts.transpileModule(readFileSync(path, 'utf8'), {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS },
  }).outputText
  const module = { exports: {} }
  new Function('require', 'module', 'exports', output)(
    (name) => load(resolve(dirname(path), name.replace(/\.js$/, '.ts'))),
    module,
    module.exports,
  )
  return module.exports
}
const source = fileURLToPath(new URL('../../src/runtime/capture-visit.ts', import.meta.url))
const { CaptureVisit } = existsSync(source) ? load(source) : {}
const scope = {
  apiRealm: 'realm',
  organizationId: 'org',
  userId: 'user',
  selectedLocationId: 'location',
  datasetIncarnation: 'dataset',
  authorizationEpoch: 'epoch',
  policyRevision: 'policy',
  capabilities: ['customers.write', 'orders.write'],
  sessionBindingId: 'binding',
}
const saved = { status: 'saved', message: null, blockSubmission: false }
const notSaved = { status: 'not_saved', message: 'No se guardó', blockSubmission: false }
const unknown = { status: 'unknown', message: 'No se pudo confirmar', blockSubmission: true }
const customer = { displayName: 'Name', email: 'a@example.test', phone: '555' }
const order = {
  customerId: 'customer',
  priority: 'high',
  reportedProblem: 'brake',
  intakeCondition: 'wet',
  accessories: 'lamp',
  withBicycle: true,
  brand: 'brand',
  model: 'model',
}
function fresh() {
  assert.equal(typeof CaptureVisit, 'function', 'pure CaptureVisit must exist')
  const owner = new CaptureVisit()
  assert.equal(owner.getSnapshot(), null)
  owner.observeScope(scope)
  owner.activateView()
  return owner
}
function view(owner) {
  return owner.getSnapshot().viewToken
}
function fill(owner, kind) {
  for (const [field, value] of Object.entries(kind === 'customer' ? customer : order))
    owner[kind === 'customer' ? 'editCustomer' : 'editOrder'](view(owner), field, value)
}
for (const kind of ['customer', 'order']) {
  test(`${kind}: current fields and detached immutable snapshots`, () => {
    const owner = fresh()
    fill(owner, kind)
    const snapshot = owner.getSnapshot(),
      draft = snapshot[kind].draft
    assert.deepEqual(draft, kind === 'customer' ? customer : order)
    assert.ok(Object.isFrozen(snapshot))
    assert.ok(Object.isFrozen(snapshot[kind]))
    assert.ok(Object.isFrozen(draft))
    assert.ok(Object.isFrozen(snapshot.viewToken))
    assert.throws(() => {
      draft[kind === 'customer' ? 'displayName' : 'brand'] = 'mutated'
    }, TypeError)
    assert.notEqual(owner.getSnapshot()[kind].draft, draft)
    assert.equal(owner.hasUnsent(), true)
  })
  test(`${kind}: same-scope mask hides private values but attempts settle`, () => {
    const owner = fresh()
    fill(owner, kind)
    const oldView = view(owner),
      attempt = owner.begin(oldView, kind)
    assert.ok(attempt)
    assert.ok(Object.isFrozen(attempt.input))
    owner.suspendView()
    assert.equal(owner.getSnapshot(), null)
    assert.equal(owner.hasUnsent(), true)
    assert.equal(owner.isCurrentView(oldView), false)
    assert.equal(owner.finish(attempt.token, saved), true)
    owner.observeScope({ ...scope, capabilities: [...scope.capabilities].reverse() })
    owner.activateView()
    assert.notEqual(view(owner), oldView)
    assert.equal(owner.getSnapshot()[kind].busy, false)
    assert.equal(owner.getSnapshot()[kind].dirty, false)
    assert.equal(owner.finish(attempt.token, unknown), false)
    assert.equal(owner.begin(oldView, kind), null)
  })
  test(`${kind}: busy exclusion and unknown latch survive mask and edits`, () => {
    const owner = fresh()
    fill(owner, kind)
    const attempt = owner.begin(view(owner), kind)
    assert.equal(owner.begin(view(owner), kind), null)
    owner.suspendView()
    owner.observeScope(scope)
    owner.activateView()
    assert.equal(owner.begin(view(owner), kind), null)
    assert.equal(owner.finish(attempt.token, unknown), true)
    for (const field of Object.keys(kind === 'customer' ? customer : order))
      owner[kind === 'customer' ? 'editCustomer' : 'editOrder'](
        view(owner),
        field,
        field === 'priority' ? 'normal' : field === 'withBicycle' ? false : '',
      )
    assert.equal(owner.getSnapshot()[kind].blocked, true)
    assert.equal(owner.getSnapshot()[kind].dirty, true)
    assert.equal(owner.begin(view(owner), kind), null)
  })
  test(`${kind}: not_saved preserves every input and permits explicit next attempt`, () => {
    const owner = fresh()
    fill(owner, kind)
    const first = owner.begin(view(owner), kind)
    assert.equal(owner.finish(first.token, notSaved), true)
    assert.deepEqual(owner.getSnapshot()[kind].draft, kind === 'customer' ? customer : order)
    const next = owner.begin(view(owner), kind)
    assert.ok(next)
    assert.notEqual(next.token, first.token)
    assert.equal(owner.finish(first.token, saved), false)
    assert.equal(owner.getSnapshot()[kind].busy, true)
  })
  for (const mode of ['same-value', 'ABA'])
    test(`${kind}: ${mode} newer revision retains full draft on older saved`, () => {
      const owner = fresh()
      fill(owner, kind)
      const first = owner.begin(view(owner), kind),
        field = kind === 'customer' ? 'displayName' : 'reportedProblem'
      const edit = owner[kind === 'customer' ? 'editCustomer' : 'editOrder'].bind(owner)
      if (mode === 'ABA') edit(view(owner), field, 'intermediate')
      edit(view(owner), field, (kind === 'customer' ? customer : order)[field])
      owner.finish(first.token, saved)
      assert.deepEqual(owner.getSnapshot()[kind].draft, kind === 'customer' ? customer : order)
      assert.equal(
        owner.getSnapshot()[kind].message,
        'El envío anterior se guardó localmente. El formulario actual sigue sin guardar.',
      )
    })
  test(`${kind}: old visit settlement cannot alter new busy attempt`, () => {
    const owner = fresh()
    fill(owner, kind)
    const first = owner.begin(view(owner), kind),
      oldView = view(owner)
    owner.endVisit()
    assert.equal(owner.getSnapshot(), null)
    assert.equal(owner.hasUnsent(), false)
    owner.observeScope(scope)
    owner.activateView()
    assert.equal(owner.begin(view(owner), kind), null)
    owner.startVisit()
    owner.observeScope(scope)
    owner.activateView()
    fill(owner, kind)
    const next = owner.begin(view(owner), kind)
    assert.equal(owner.finish(first.token, saved), false)
    assert.equal(owner.isCurrentView(oldView), false)
    assert.equal(owner.getSnapshot()[kind].busy, true)
    assert.equal(owner.finish(next.token, saved), true)
  })
}
for (const field of Object.keys(scope))
  test(`scope ${field}: unsent-only mismatch purges irreversibly with fixed notice`, () => {
    const owner = fresh()
    fill(owner, 'customer')
    fill(owner, 'order')
    const oldView = view(owner)
    owner.observeScope({
      ...scope,
      [field]: field === 'capabilities' ? ['customers.write'] : 'different',
    })
    owner.activateView()
    assert.equal(owner.getSnapshot().customer.draft.displayName, '')
    assert.equal(owner.getSnapshot().order.draft.customerId, '')
    assert.equal(
      owner.getSnapshot().notice,
      'Los formularios anteriores no están disponibles en este contexto.',
    )
    assert.equal(owner.isCurrentView(oldView), false)
    owner.observeScope(scope)
    owner.activateView()
    assert.equal(owner.getSnapshot().customer.draft.displayName, '')
    assert.ok(owner.begin(view(owner), 'customer'))
  })
for (const state of ['pending', 'unknown'])
  test(`${state} semantic mismatch leaves sticky capture-only denial`, () => {
    const owner = fresh()
    fill(owner, 'customer')
    const attempt = owner.begin(view(owner), 'customer')
    if (state === 'unknown') owner.finish(attempt.token, unknown)
    owner.observeScope({ ...scope, userId: 'different' })
    owner.activateView()
    assert.equal(owner.getSnapshot().customer.draft.displayName, '')
    assert.equal(
      owner.getSnapshot().notice,
      'Hay una captura pendiente de confirmar de la visita anterior. No la repitas; las nuevas capturas están bloqueadas en esta visita.',
    )
    assert.equal(owner.hasUnsent(), true)
    owner.observeScope(scope)
    owner.activateView()
    assert.equal(owner.begin(view(owner), 'customer'), null)
    assert.equal(owner.begin(view(owner), 'order'), null)
    assert.equal(owner.finish(attempt.token, saved), false)
  })
test('capability duplicates/order do not change scope; both form channels stay independent', () => {
  const owner = fresh()
  fill(owner, 'customer')
  fill(owner, 'order')
  const first = owner.begin(view(owner), 'customer')
  owner.observeScope({
    ...scope,
    capabilities: ['orders.write', 'customers.write', 'orders.write'],
  })
  assert.ok(owner.begin(view(owner), 'order'))
  assert.equal(owner.finish(first.token, unknown), true)
  assert.equal(owner.getSnapshot().order.busy, true)
})
test('saved order keeps clean selected defaults and masked renewals do not reset them', () => {
  const owner = fresh()
  fill(owner, 'order')
  const attempt = owner.begin(view(owner), 'order')
  owner.finish(attempt.token, saved)
  owner.suspendView()
  owner.observeScope(scope)
  owner.activateView()
  assert.equal(owner.getSnapshot().order.draft.customerId, 'customer')
  assert.equal(owner.getSnapshot().order.draft.priority, 'high')
  assert.equal(owner.getSnapshot().order.draft.withBicycle, false)
  assert.equal(owner.getSnapshot().order.draft.brand, '')
  assert.equal(owner.hasUnsent(), false)
  owner.observeScope({ ...scope, authorizationEpoch: 'new' })
  owner.activateView()
  assert.equal(owner.getSnapshot().order.draft.customerId, '')
  assert.equal(owner.getSnapshot().notice, null)
})
test('suspended/foreign views cannot edit; invalid runtime fields and types are refused', () => {
  const owner = fresh(),
    token = view(owner)
  assert.equal(owner.editCustomer({}, 'displayName', 'private'), false)
  assert.equal(owner.editCustomer(token, '__proto__', 'bad'), false)
  assert.equal(owner.editOrder(token, 'withBicycle', 'wrong'), false)
  owner.suspendView()
  assert.equal(owner.editCustomer(token, 'displayName', 'late'), false)
  owner.activateView()
  assert.equal(owner.getSnapshot().customer.draft.displayName, '')
})

for (const kind of ['customer', 'order']) {
  test(`${kind}: clearing newer fields keeps revision fence without a dirty-history latch`, () => {
    const owner = fresh()
    fill(owner, kind)
    const attempt = owner.begin(view(owner), kind)
    for (const field of Object.keys(kind === 'customer' ? customer : order))
      owner[kind === 'customer' ? 'editCustomer' : 'editOrder'](
        view(owner),
        field,
        field === 'priority' ? 'normal' : field === 'withBicycle' ? false : '',
      )
    assert.equal(owner.hasUnsent(), true)
    owner.finish(attempt.token, saved)
    assert.equal(owner.getSnapshot()[kind].dirty, false)
    assert.equal(owner.hasUnsent(), false)
    assert.equal(
      owner.getSnapshot()[kind].message,
      'El envío anterior se guardó localmente. El formulario actual sigue sin guardar.',
    )
  })
  test(`${kind}: every field advances revision and captured input remains immutable`, () => {
    for (const [field, value] of Object.entries(kind === 'customer' ? customer : order)) {
      const owner = fresh()
      fill(owner, kind)
      const attempt = owner.begin(view(owner), kind)
      owner[kind === 'customer' ? 'editCustomer' : 'editOrder'](view(owner), field, value)
      owner.finish(attempt.token, saved)
      assert.deepEqual(owner.getSnapshot()[kind].draft, kind === 'customer' ? customer : order)
      assert.deepEqual(attempt.input, kind === 'customer' ? customer : order)
      assert.equal(
        owner.getSnapshot()[kind].message,
        'El envío anterior se guardó localmente. El formulario actual sigue sin guardar.',
      )
    }
  })
  test(`${kind}: explicit later save resets only the newer attempt`, () => {
    const owner = fresh()
    fill(owner, kind)
    const attempt = owner.begin(view(owner), kind)
    const field = kind === 'customer' ? 'displayName' : 'reportedProblem'
    owner[kind === 'customer' ? 'editCustomer' : 'editOrder'](view(owner), field, 'second')
    owner.finish(attempt.token, saved)
    const next = owner.begin(view(owner), kind)
    assert.equal(next.input[field], 'second')
    assert.equal(owner.finish(next.token, saved), true)
    assert.equal(owner.getSnapshot()[kind].dirty, false)
    assert.equal(owner.finish(next.token, unknown), false)
    assert.equal(owner.getSnapshot()[kind].blocked, false)
  })
}
test('newer order receipt preserves old retained-default baseline and hidden bicycle fields', () => {
  const owner = fresh()
  fill(owner, 'order')
  const attempt = owner.begin(view(owner), 'order')
  owner.editOrder(view(owner), 'withBicycle', false)
  owner.finish(attempt.token, saved)
  assert.equal(owner.getSnapshot().order.draft.brand, 'brand')
  assert.equal(owner.getSnapshot().order.draft.model, 'model')
  for (const field of ['reportedProblem', 'intakeCondition', 'accessories', 'brand', 'model'])
    owner.editOrder(view(owner), field, '')
  assert.equal(
    owner.getSnapshot().order.dirty,
    true,
    'stale save did not adopt submitted selection as clean',
  )
})
test('no values, feedback or pending attempts remain after closed visit renewal', () => {
  const owner = fresh()
  fill(owner, 'customer')
  fill(owner, 'order')
  const attempt = owner.begin(view(owner), 'order')
  owner.endVisit()
  owner.observeScope(scope)
  owner.activateView()
  const snapshot = owner.getSnapshot()
  assert.equal(snapshot.customer.draft.displayName, '')
  assert.equal(snapshot.order.draft.customerId, '')
  assert.equal(snapshot.order.busy, false)
  assert.equal(snapshot.order.message, null)
  assert.equal(owner.finish(attempt.token, saved), false)
  assert.equal(owner.isCurrentView(view(owner)), false)
})

test('closed empty presentation remains blocked but does not invent unsent work', () => {
  const owner = fresh()
  fill(owner, 'customer')
  fill(owner, 'order')
  const oldView = view(owner),
    oldAttempt = owner.begin(oldView, 'customer')
  owner.endVisit()
  owner.observeScope(scope)
  owner.activateView()
  const snapshot = owner.getSnapshot()
  assert.equal(owner.hasUnsent(), false)
  assert.equal(snapshot.customer.dirty, false)
  assert.equal(snapshot.order.dirty, false)
  assert.equal(snapshot.customer.blocked, true)
  assert.equal(snapshot.order.blocked, true)
  assert.equal(owner.begin(snapshot.viewToken, 'customer'), null)
  assert.equal(owner.begin(snapshot.viewToken, 'order'), null)
  assert.equal(owner.editCustomer(oldView, 'displayName', 'old'), false)
  assert.equal(owner.editOrder(snapshot.viewToken, 'brand', 'closed'), false)
  assert.equal(owner.finish(oldAttempt.token, saved), false)
})

test('closed empty visit notice does not falsely claim a pending or unknown capture', () => {
  const owner = fresh()
  owner.endVisit()
  owner.observeScope(scope)
  owner.activateView()
  const snapshot = owner.getSnapshot()
  assert.equal(owner.hasUnsent(), false)
  for (const kind of ['customer', 'order']) {
    assert.equal(snapshot[kind].blocked, true)
    assert.equal(snapshot[kind].busy, false)
    assert.equal(snapshot[kind].dirty, false)
    assert.equal(snapshot[kind].message, null)
  }
  assert.doesNotMatch(snapshot.notice, /pendiente|confirmar/i)
  assert.equal(
    snapshot.notice,
    'Las capturas no están disponibles en esta visita. Inicia una nueva sesión para continuar.',
  )
})

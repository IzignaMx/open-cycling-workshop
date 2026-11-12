import test from 'node:test'
import assert from 'node:assert/strict'
import { setup, login } from './runtime-fixture.mjs'
async function fixture(t) {
  const f = setup(t)
  await login(f.runtime)
  f.env.online = false
  await f.runtime.offline()
  for (const problem of ['Frenos', 'Cambio'])
    await f.runtime.createOrder({
      customerId: 'historical-A',
      reportedProblem: problem,
      intakeCondition: null,
      accessories: null,
      priority: 'normal',
      brand: null,
      model: null,
    })
  return {
    ...f,
    a: f.runtime.getSnapshot().orders.find((o) => o.reported_problem === 'Frenos').order_id,
    b: f.runtime.getSnapshot().orders.find((o) => o.reported_problem === 'Cambio').order_id,
  }
}
function edit(f, id, note, token = f.runtime.getSnapshot().transitionProtection.noteToken) {
  f.runtime.editTransitionNote(id, note, token)
}
test('actual offline transition captures one exact note, blocks duplicates, and retains saved note across reload', async (t) => {
  const f = await fixture(t)
  edit(f, f.a, '\u0085Falta\n  cadena\u001c')
  edit(f, f.b, 'Otra orden')
  assert.equal(f.runtime.hasUnsentTransitionNotes(), true)
  assert.equal(f.runtime.hasUnsentCaptures(), true)
  const original = f.runtime.repositories.transition.bind(f.runtime.repositories)
  let release, entered
  const barrier = new Promise((r) => (entered = r)),
    gate = new Promise((r) => (release = r))
  t.after(() => release())
  t.mock.method(f.runtime.repositories, 'transition', async (...args) => {
    entered()
    await gate
    return original(...args)
  })
  const first = f.runtime.transition(f.a, 'start_diagnosis')
  await barrier
  edit(f, f.a, 'Texto nuevo')
  assert.equal(
    f.runtime.getSnapshot().transitionProtection.notes.get(f.a),
    '\u0085Falta\n  cadena\u001c',
  )
  assert.deepEqual(await f.runtime.transition(f.a, 'cancel'), { status: 'unknown' })
  release()
  assert.deepEqual(await first, { status: 'committed', view: 'updated' })
  const snapshot = f.runtime.getSnapshot()
  assert.equal(snapshot.transitionProtection.notes.has(f.a), false)
  assert.equal(snapshot.transitionProtection.notes.get(f.b), 'Otra orden')
  assert.equal(snapshot.events.find((e) => e.order_id === f.a).note, 'Falta cadena')
  const journal = await f.database.operationJournal.toArray(),
    changes = journal.filter((r) => r.envelope.operation === 'update')
  assert.equal(changes.length, 1)
  assert.equal(changes[0].envelope.payload.transition.note, 'Falta cadena')
  f.runtime.dispose()
  const second = setup(t, { name: f.name, storage: f.storage, online: false })
  await second.runtime.start()
  await second.runtime.timeline(f.a)
  assert.equal(
    second.runtime.getSnapshot().events.find((e) => e.order_id === f.a).note,
    'Falta cadena',
  )
  assert.equal(second.runtime.getSnapshot().transitionProtection.notes.size, 0)
  assert.equal(second.server.calls.length, 0)
  assert.deepEqual(await second.database.operationJournal.toArray(), journal)
})
test('unknown postcommit outcome retains disabled note without replaying the saved change', async (t) => {
  const f = await fixture(t)
  edit(f, f.a, 'Verificar resultado')
  const original = f.runtime.repositories.transition.bind(f.runtime.repositories)
  t.mock.method(f.runtime.repositories, 'transition', async (...args) => {
    await original(...args)
    throw Error('synthetic lost reply')
  })
  assert.deepEqual(await f.runtime.transition(f.a, 'start_diagnosis'), { status: 'unknown' })
  assert.equal(f.runtime.getSnapshot().transitionProtection.notes.get(f.a), 'Verificar resultado')
  assert.equal(f.runtime.getSnapshot().transitionProtection.states.get(f.a).feedback.block, true)
  const journal = await f.database.operationJournal.toArray()
  assert.deepEqual(await f.runtime.transition(f.a, 'cancel'), { status: 'unknown' })
  assert.deepEqual(await f.database.operationJournal.toArray(), journal)
})
test('committed outcome with unavailable view clears note but retains existing no-repeat protection', async (t) => {
  const f = await fixture(t)
  edit(f, f.a, 'Guardar una vez')
  t.mock.method(f.runtime, 'refresh', async () => false)
  assert.deepEqual(await f.runtime.transition(f.a, 'start_diagnosis'), {
    status: 'committed',
    view: 'unavailable',
  })
  assert.equal(f.runtime.getSnapshot().transitionProtection.notes.has(f.a), false)
  assert.equal(f.runtime.getSnapshot().transitionProtection.states.get(f.a).feedback.block, true)
})
test('actual refresh/pagination preserves notes, while logout/new login rejects old editor token', async (t) => {
  const f = await fixture(t),
    old = f.runtime.getSnapshot().transitionProtection.noteToken
  edit(f, f.a, 'Privado A')
  await f.runtime.refresh('customer')
  await f.runtime.refresh('service_order')
  assert.equal(f.runtime.getSnapshot().transitionProtection.notes.get(f.a), 'Privado A')
  await f.runtime.logout()
  assert.equal(f.runtime.getSnapshot().transitionProtection.notes.size, 0)
  f.env.online = true
  await login(f.runtime, 'B')
  f.env.online = false
  await f.runtime.offline()
  await f.runtime.createOrder({
    customerId: 'historical-B',
    reportedProblem: 'Nueva orden',
    intakeCondition: null,
    accessories: null,
    priority: 'normal',
    brand: null,
    model: null,
  })
  const id = f.runtime.getSnapshot().orders[0].order_id
  edit(f, id, 'Viejo callback', old)
  assert.equal(f.runtime.getSnapshot().transitionProtection.notes.size, 0)
  edit(f, id, 'Nota B')
  assert.equal(f.runtime.getSnapshot().transitionProtection.notes.get(id), 'Nota B')
})
test('invalid note never journals and remains correctable; unknown order cannot acquire draft', async (t) => {
  const f = await fixture(t)
  edit(f, 'other-order', 'nope')
  assert.equal(f.runtime.getSnapshot().transitionProtection.notes.size, 0)
  edit(f, f.a, 'x'.repeat(2001))
  const before = await f.database.operationJournal.toArray()
  assert.deepEqual(await f.runtime.transition(f.a, 'start_diagnosis'), { status: 'unknown' })
  assert.deepEqual(await f.database.operationJournal.toArray(), before)
  edit(f, f.a, 'Correcta')
  assert.deepEqual(await f.runtime.transition(f.a, 'start_diagnosis'), {
    status: 'committed',
    view: 'updated',
  })
})

test('actual App wires note edits and its departure guard to the same runtime owner', async (t) => {
  const { appHarness } = await import('./capture-component-host.mjs')
  const f = await fixture(t)
  const previousWindow = globalThis.window,
    previousDocument = globalThis.document
  let prompts = 0
  globalThis.window = {
    confirm: () => {
      prompts++
      return false
    },
  }
  globalThis.document = { querySelector: () => null }
  t.after(() => {
    globalThis.window = previousWindow
    globalThis.document = previousDocument
  })
  const app = appHarness(f.runtime, { layoutEffects: true })
  const nodes = (node) =>
    !node || typeof node !== 'object'
      ? []
      : [node, ...[node.props?.children].flat(Infinity).flatMap(nodes)]
  const list = nodes(app.render()).find((node) => node.type?.name === 'OrderList')
  assert.equal(typeof list.props.onNote, 'function')
  list.props.onNote(f.a, 'Nota desde la vista')
  assert.equal(f.runtime.getSnapshot().transitionProtection.notes.get(f.a), 'Nota desde la vista')
  assert.equal(app.logoutGuard()(), false)
  assert.equal(prompts, 1)
  list.props.onNote(f.a, '')
  assert.equal(app.logoutGuard()(), true)
  assert.equal(prompts, 1)
})

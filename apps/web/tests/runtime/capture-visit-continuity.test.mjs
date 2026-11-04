import test from 'node:test'
import assert from 'node:assert/strict'
import { setup, login, until } from './runtime-fixture.mjs'
import { observeCaptureMounts } from './capture-component-host.mjs'

// Actual integration seam: actual controller reconnect, real App branching,
// actual capture callbacks and instrumented repository boundary; simulated hook host
// and reconciliation. No claim about native React scheduling, DOM or PWA.
const kinds = [
  {
    name: 'customer',
    component: 'CustomerQuickCreate',
    method: 'createCustomer',
    fields: { Nombre: 'Draft Ana', Correo: 'ana@example.test', Teléfono: '555' },
  },
  {
    name: 'order',
    component: 'OrderQuickIntake',
    method: 'createOrder',
    fields: {
      Cliente: 'historical-A',
      'Problema reportado': 'Draft brake',
      'Condición al recibir': 'Wet',
      Accesorios: 'Lamp',
      Prioridad: 'high',
      'Agregar bicicleta': true,
      Marca: 'Draft brand',
      Modelo: 'Draft model',
    },
  },
]
async function prepare(t, kind) {
  const f = setup(t)
  f.runtime.scheduleSync = () => {}
  await login(f.runtime)
  const view = observeCaptureMounts(f.runtime)
  t.after(view.dispose)
  const form = () => view.forms.get(kind.component)
  const fill = () => {
    for (const [label, value] of Object.entries(kind.fields)) form().edit(label, value)
  }
  fill()
  if (kind.name === 'order')
    await until(
      () => f.runtime.getSnapshot().customerLookup?.selection.status === 'available',
      'current customer pin available',
    )
  return { ...f, view, form, fill }
}
async function reconnect(f) {
  const prior = f.form()
  const pending = f.runtime.reconnect()
  assert.equal(f.runtime.getSnapshot().phase, 'verifying')
  assert.equal(f.view.forms.size, 0, 'actual App removes capture children while verifying')
  await pending
  assert.equal(f.runtime.getSnapshot().phase, 'ready')
  assert.notEqual(
    f.form(),
    prior,
    'simulated reconciler instantiated a new component after actual branch removal',
  )
}
for (const kind of kinds) {
  test(`capture visit ${kind.name}: entered draft survives actual same-scope reconnect`, async (t) => {
    const f = await prepare(t, kind)
    await reconnect(f)
    const observed = {}
    for (const label of Object.keys(kind.fields)) {
      if (['Marca', 'Modelo'].includes(label)) continue
      observed[label] = f.form().value(label)
    }
    if (kind.name === 'order') {
      // Reveal the now-hidden fields only after observing the checkbox itself.
      f.form().edit('Agregar bicicleta', true)
      observed.Marca = f.form().value('Marca')
      observed.Modelo = f.form().value('Modelo')
    }
    assert.deepEqual(observed, kind.fields, 'all current fields survive same-visit verification')
  })
  test(`capture visit ${kind.name}: unknown admission remains closed across actual reconnect`, async (t) => {
    const f = await prepare(t, kind)
    let calls = 0
    f.runtime.repositories[kind.method] = async () => {
      calls++
      throw new Error('synthetic-unknown-before-write')
    }
    await f.form().submit()
    assert.equal(calls, 1)
    assert.equal(f.form().disabled(), true)
    await reconnect(f)
    // Re-entering demonstrates the new form gate permits a repeated attempt;
    // this fixture claims no first-attempt commit or persisted duplicate.
    f.fill()
    await f.form().submit()
    assert.equal(calls, 1, 'same-visit unknown must not admit a second repository invocation')
  })
  test(`capture visit ${kind.name}: pending admission remains closed across actual reconnect`, async (t) => {
    const f = await prepare(t, kind)
    let calls = 0,
      release
    const waiting = new Promise((resolve) => {
      release = resolve
    })
    f.runtime.repositories[kind.method] = async () => {
      calls++
      if (calls === 1) await waiting
      throw new Error('synthetic-unknown-before-write')
    }
    const first = f.form().submit()
    try {
      await until(() => calls === 1, 'protected repository invocation')
      assert.equal(calls, 1)
      await reconnect(f)
      f.fill()
      await f.form().submit()
      assert.equal(calls, 1, 'same-visit pending must not admit a second repository invocation')
    } finally {
      release()
      await first
    }
  })
}

test('capture visit order: clean retained customer and priority survive actual reconnect', async (t) => {
  const kind = kinds[1]
  const f = await prepare(t, kind)
  // Actual repository/kernel save: no controlled saved result at this boundary.
  await f.form().submit()
  assert.equal(f.form().message(), 'Orden guardada localmente')
  assert.equal(f.form().dirty(), false)
  const retained = { Cliente: f.form().value('Cliente'), Prioridad: f.form().value('Prioridad') }
  assert.deepEqual(retained, { Cliente: 'historical-A', Prioridad: 'high' })
  await reconnect(f)
  assert.deepEqual(
    { Cliente: f.form().value('Cliente'), Prioridad: f.form().value('Prioridad') },
    retained,
  )
})

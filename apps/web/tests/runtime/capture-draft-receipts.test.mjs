import assert from 'node:assert/strict'
import test from 'node:test'
import { mount } from './capture-component-host.mjs'
import { setup, login, until } from './runtime-fixture.mjs'

async function fixture(kind, t) {
  const { runtime } = setup(t)
  runtime.scheduleSync = () => {}
  await login(runtime)
  let resolveResult, rejectResult
  const pending = new Promise((resolve, reject) => {
    resolveResult = resolve
    rejectResult = reject
  })
  const calls = []
  const callback = (_source, input) => {
    calls.push(input)
    return pending
  }
  runtime.repositories[kind === 'customer' ? 'createCustomer' : 'createOrder'] = callback
  const view = runtime.getSnapshot().capture.viewToken
  const form =
    kind === 'customer'
      ? mount(
          '../../src/features/customers/CustomerQuickCreate.tsx',
          'CustomerQuickCreate',
          () => ({
            capture: runtime.getSnapshot().capture.customer,
            onEdit: (field, value) => runtime.editCaptureCustomer(view, field, value),
            onSubmit: () => runtime.submitCaptureCustomer(view),
          }),
        )
      : mount('../../src/features/orders/OrderQuickIntake.tsx', 'OrderQuickIntake', () => ({
          capture: runtime.getSnapshot().capture.order,
          customers: [
            { customer_id: 'one', display_name: 'One' },
            { customer_id: 'two', display_name: 'Two' },
          ],
          onEdit: (field, value) => runtime.editCaptureOrder(view, field, value),
          onSubmit: () => runtime.submitCaptureOrder(view),
        }))
  const fields =
    kind === 'customer'
      ? { Nombre: 'Ana', Correo: 'ana@example.test', Teléfono: '111' }
      : {
          Cliente: 'one',
          'Problema reportado': 'Freno',
          'Condición al recibir': 'Sucio',
          Accesorios: 'Luz',
          Prioridad: 'high',
          'Agregar bicicleta': true,
          Marca: 'Marca',
          Modelo: 'Modelo',
        }
  for (const [label, value] of Object.entries(fields)) form.edit(label, value)
  return { form, fields, calls, resolveResult, rejectResult }
}

for (const kind of ['customer', 'order']) {
  const labels =
    kind === 'customer'
      ? ['Nombre', 'Correo', 'Teléfono']
      : [
          'Cliente',
          'Problema reportado',
          'Condición al recibir',
          'Accesorios',
          'Prioridad',
          'Agregar bicicleta',
          'Marca',
          'Modelo',
        ]
  for (const label of labels) {
    test(`${kind}: delayed saved receipt preserves newer ${label} edit and entire current draft`, async (t) => {
      const f = await fixture(kind, t)
      const completion = f.form.submitTwiceBeforeRender()
      assert.equal(
        f.form.disabled(),
        true,
        'busy guard closes synchronously before durable protection',
      )
      await until(() => f.calls.length === 1, 'protected repository invocation')
      assert.equal(f.calls.length, 1, 'same-render reentry admits one invocation')
      const value =
        label === 'Agregar bicicleta'
          ? false
          : label === 'Cliente'
            ? 'two'
            : label === 'Prioridad'
              ? 'urgent'
              : 'newer'
      f.form.edit(label, value)
      await until(() => f.calls.length === 1, 'protected repository invocation')
      f.resolveResult({ status: 'saved' })
      await completion
      assert.equal(f.form.value(label), value)
      for (const [other, old] of Object.entries(f.fields)) {
        if (
          other === label ||
          (label === 'Agregar bicicleta' && ['Marca', 'Modelo'].includes(other))
        )
          continue
        assert.equal(f.form.value(other), old, `${other} retained`)
      }
      assert.equal(f.form.dirty(), true)
      assert.match(f.form.message(), /envío anterior.*guard.*formulario actual.*sin guardar/i)
      assert.equal(f.form.disabled(), false)
    })
  }
  for (const mode of ['ABA', 'same-value']) {
    test(`${kind}: ${mode} interaction is not acknowledged by an older receipt`, async (t) => {
      const f = await fixture(kind, t),
        label = kind === 'customer' ? 'Nombre' : 'Problema reportado'
      const completion = f.form.submit()
      if (mode === 'ABA') f.form.edit(label, 'intermediate')
      f.form.edit(label, f.fields[label])
      await until(() => f.calls.length === 1, 'protected repository invocation')
      f.resolveResult({ status: 'saved' })
      await completion
      assert.equal(f.form.value(label), f.fields[label])
      assert.match(f.form.message(), /formulario actual.*sin guardar/i)
    })
  }
  test(`${kind}: unchanged submitted draft resets on saved`, async (t) => {
    const f = await fixture(kind, t),
      completion = f.form.submit()
    await until(() => f.calls.length === 1, 'protected repository invocation')
    f.resolveResult({ status: 'saved' })
    await completion
    assert.equal(f.form.dirty(), false)
    assert.equal(f.form.value(kind === 'customer' ? 'Nombre' : 'Problema reportado'), '')
    if (kind === 'order') {
      assert.equal(f.form.value('Cliente'), 'one')
      assert.equal(f.form.value('Prioridad'), 'high')
    }
  })
  for (const outcome of ['not_saved', 'unknown']) {
    test(`${kind}: ${outcome} preserves newer draft and unknown remains latched after editing`, async (t) => {
      const f = await fixture(kind, t),
        label = kind === 'customer' ? 'Nombre' : 'Problema reportado',
        completion = f.form.submit()
      f.form.edit(label, 'newer')
      await until(() => f.calls.length === 1, 'protected repository invocation')
      if (outcome === 'unknown') f.rejectResult(new Error('private-canary'))
      else f.resolveResult({ status: 'not_saved', reason: 'quota' })
      await completion
      assert.equal(f.form.value(label), 'newer')
      assert.equal(f.form.message().includes('private-canary'), false)
      f.form.edit(label, 'later')
      await f.form.submit()
      assert.equal(f.calls.length, outcome === 'unknown' ? 1 : 2)
      assert.equal(f.form.disabled(), outcome === 'unknown')
    })
  }
}

for (const kind of ['customer', 'order']) {
  test(`${kind}: next explicit submission sends retained newer values and resets its own draft`, async (t) => {
    const f = await fixture(kind, t),
      label = kind === 'customer' ? 'Nombre' : 'Problema reportado'
    const completion = f.form.submit()
    f.form.edit(label, 'New draft')
    await until(() => f.calls.length === 1, 'protected repository invocation')
    f.resolveResult({ status: 'saved' })
    await completion
    assert.equal(
      f.calls[0][kind === 'customer' ? 'displayName' : 'reportedProblem'],
      f.fields[label],
    )
    await f.form.submit()
    assert.equal(f.calls.length, 2)
    assert.equal(f.calls[1][kind === 'customer' ? 'displayName' : 'reportedProblem'], 'New draft')
    assert.equal(f.form.dirty(), false)
  })
  test(`${kind}: unknown remains dirty and blocked after every field is cleared`, async (t) => {
    const f = await fixture(kind, t),
      completion = f.form.submit()
    await until(() => f.calls.length === 1, 'protected repository invocation')
    f.rejectResult(new Error('unknown'))
    await completion
    for (const label of Object.keys(f.fields)) {
      if (label === 'Agregar bicicleta') continue
      f.form.edit(label, label === 'Prioridad' ? 'normal' : '')
    }
    if (kind === 'order') f.form.edit('Agregar bicicleta', false)
    assert.equal(f.form.dirty(), true)
    await f.form.submit()
    assert.equal(f.calls.length, 1)
    assert.equal(f.form.disabled(), true)
  })
}

test('order: older receipt cannot adopt submitted selection as the new clean baseline', async (t) => {
  const f = await fixture('order', t),
    completion = f.form.submit()
  f.form.edit('Problema reportado', 'newer')
  f.resolveResult({ status: 'saved' })
  await completion
  for (const label of [
    'Problema reportado',
    'Condición al recibir',
    'Accesorios',
    'Marca',
    'Modelo',
  ])
    f.form.edit(label, '')
  f.form.edit('Agregar bicicleta', false)
  assert.equal(f.form.value('Cliente'), 'one')
  assert.equal(f.form.value('Prioridad'), 'high')
  assert.equal(f.form.dirty(), true, 'submitted selection was not adopted by the stale receipt')
})

test('order: hidden bicycle fields survive checkbox edits during saved receipt', async (t) => {
  const f = await fixture('order', t),
    completion = f.form.submit()
  f.form.edit('Agregar bicicleta', false)
  f.resolveResult({ status: 'saved' })
  await completion
  f.form.edit('Agregar bicicleta', true)
  assert.equal(f.form.value('Marca'), 'Marca')
  assert.equal(f.form.value('Modelo'), 'Modelo')
})

for (const kind of ['customer', 'order']) {
  test(`${kind}: intentionally emptied draft is clean after older saved receipt`, async (t) => {
    const f = await fixture(kind, t),
      completion = f.form.submit()
    for (const label of Object.keys(f.fields)) {
      if (label === 'Agregar bicicleta') continue
      f.form.edit(label, label === 'Prioridad' ? 'normal' : '')
    }
    if (kind === 'order') f.form.edit('Agregar bicicleta', false)
    assert.equal(f.form.dirty(), true, 'pending submission still guards navigation')
    await until(() => f.calls.length === 1, 'protected repository invocation')
    f.resolveResult({ status: 'saved' })
    await completion
    assert.equal(f.form.dirty(), false, 'edit revision is not a historical dirty latch')
    assert.equal(f.form.disabled(), false)
  })
}

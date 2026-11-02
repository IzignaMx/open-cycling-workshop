import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import test from 'node:test'
import ts from 'typescript'

// Unit-only deterministic hook host: executes the actual component and handlers.
// It does not model React scheduling, DOM events, focus, accessibility or PWA storage.
function mount(componentPath, exportName, props) {
  const slots = []
  let cursor = 0
  const hooks = {
    useState(initial) {
      const index = cursor++
      if (!(index in slots)) slots[index] = typeof initial === 'function' ? initial() : initial
      return [
        slots[index],
        (value) => {
          slots[index] = typeof value === 'function' ? value(slots[index]) : value
        },
      ]
    },
    useRef(initial) {
      const index = cursor++
      if (!(index in slots)) slots[index] = { current: initial }
      return slots[index]
    },
  }
  const cache = new Map()
  function load(path) {
    if (cache.has(path)) return cache.get(path)
    const output = ts.transpileModule(readFileSync(path, 'utf8'), {
      compilerOptions: {
        target: ts.ScriptTarget.ES2022,
        module: ts.ModuleKind.CommonJS,
        jsx: ts.JsxEmit.ReactJSX,
      },
    }).outputText
    const module = { exports: {} }
    cache.set(path, module.exports)
    const nativeRequire = createRequire(path)
    const require = (name) => {
      if (name === 'react') return hooks
      if (name === 'react/jsx-runtime') return { jsx: element, jsxs: element }
      if (name === '@ocwp/ui') return { Button: 'button' }
      if (name.startsWith('.')) return load(resolve(dirname(path), name.replace(/\.js$/, '.ts')))
      return nativeRequire(name)
    }
    new Function('require', 'module', 'exports', output)(require, module, module.exports)
    return module.exports
  }
  function element(type, props) {
    return { type, props }
  }
  const Component = load(fileURLToPath(new URL(componentPath, import.meta.url)))[exportName]
  let tree
  function render() {
    cursor = 0
    tree = Component(props)
    return tree
  }
  function nodes(node) {
    if (!node || typeof node !== 'object') return []
    return [node, ...[node.props?.children].flat(Infinity).flatMap((child) => nodes(child))]
  }
  function control(label) {
    const wrapper = nodes(tree).find(
      (node) =>
        node.type === 'label' &&
        nodes(node).some((child) => child.type === 'span' && child.props.children === label),
    )
    assert.ok(wrapper, `label ${label} exists`)
    return nodes(wrapper).find((node) => ['input', 'select', 'textarea'].includes(node.type))
  }
  render()
  return {
    edit(label, value) {
      const input = control(label)
      input.props.onChange({ currentTarget: { value, checked: value } })
      render()
    },
    value(label) {
      const input = control(label)
      return input.props.type === 'checkbox' ? input.props.checked : input.props.value
    },
    async submit() {
      const pending = tree.props.onSubmit({ preventDefault() {} })
      render()
      await pending
      render()
    },
    async submitTwiceBeforeRender() {
      const submit = tree.props.onSubmit
      const event = { preventDefault() {} }
      const first = submit(event)
      const second = submit(event)
      render()
      await Promise.all([first, second])
      render()
    },
    dirty() {
      return tree.props['data-dirty']
    },
    message() {
      return nodes(tree).find((node) => node.props?.role === 'status').props.children
    },
    disabled() {
      return nodes(tree).find((node) => node.type === 'button').props.disabled
    },
  }
}
function fixture(kind) {
  let resolveResult, rejectResult
  const pending = new Promise((resolve, reject) => {
    resolveResult = resolve
    rejectResult = reject
  })
  const calls = []
  const callback = (input) => {
    calls.push(input)
    return pending
  }
  const form =
    kind === 'customer'
      ? mount('../../src/features/customers/CustomerQuickCreate.tsx', 'CustomerQuickCreate', {
          onCreate: callback,
        })
      : mount('../../src/features/orders/OrderQuickIntake.tsx', 'OrderQuickIntake', {
          customers: [
            { customer_id: 'one', display_name: 'One' },
            { customer_id: 'two', display_name: 'Two' },
          ],
          onCreateOrder: callback,
        })
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
    test(`${kind}: delayed saved receipt preserves newer ${label} edit and entire current draft`, async () => {
      const f = fixture(kind)
      const completion = f.form.submitTwiceBeforeRender()
      assert.equal(f.calls.length, 1, 'busy reentry is refused synchronously')
      const value =
        label === 'Agregar bicicleta'
          ? false
          : label === 'Cliente'
            ? 'two'
            : label === 'Prioridad'
              ? 'urgent'
              : 'newer'
      f.form.edit(label, value)
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
    test(`${kind}: ${mode} interaction is not acknowledged by an older receipt`, async () => {
      const f = fixture(kind),
        label = kind === 'customer' ? 'Nombre' : 'Problema reportado'
      const completion = f.form.submit()
      if (mode === 'ABA') f.form.edit(label, 'intermediate')
      f.form.edit(label, f.fields[label])
      f.resolveResult({ status: 'saved' })
      await completion
      assert.equal(f.form.value(label), f.fields[label])
      assert.match(f.form.message(), /formulario actual.*sin guardar/i)
    })
  }
  test(`${kind}: unchanged submitted draft resets on saved`, async () => {
    const f = fixture(kind),
      completion = f.form.submit()
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
    test(`${kind}: ${outcome} preserves newer draft and unknown remains latched after editing`, async () => {
      const f = fixture(kind),
        label = kind === 'customer' ? 'Nombre' : 'Problema reportado',
        completion = f.form.submit()
      f.form.edit(label, 'newer')
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
  test(`${kind}: next explicit submission sends retained newer values and resets its own draft`, async () => {
    const f = fixture(kind),
      label = kind === 'customer' ? 'Nombre' : 'Problema reportado'
    const completion = f.form.submit()
    f.form.edit(label, 'New draft')
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
  test(`${kind}: unknown remains dirty and blocked after every field is cleared`, async () => {
    const f = fixture(kind),
      completion = f.form.submit()
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

test('order: older receipt cannot adopt submitted selection as the new clean baseline', async () => {
  const f = fixture('order'),
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

test('order: hidden bicycle fields survive checkbox edits during saved receipt', async () => {
  const f = fixture('order'),
    completion = f.form.submit()
  f.form.edit('Agregar bicicleta', false)
  f.resolveResult({ status: 'saved' })
  await completion
  f.form.edit('Agregar bicicleta', true)
  assert.equal(f.form.value('Marca'), 'Marca')
  assert.equal(f.form.value('Modelo'), 'Modelo')
})

for (const kind of ['customer', 'order']) {
  test(`${kind}: intentionally emptied draft is clean after older saved receipt`, async () => {
    const f = fixture(kind),
      completion = f.form.submit()
    for (const label of Object.keys(f.fields)) {
      if (label === 'Agregar bicicleta') continue
      f.form.edit(label, label === 'Prioridad' ? 'normal' : '')
    }
    if (kind === 'order') f.form.edit('Agregar bicicleta', false)
    assert.equal(f.form.dirty(), true, 'pending submission still guards navigation')
    f.resolveResult({ status: 'saved' })
    await completion
    assert.equal(f.form.dirty(), false, 'edit revision is not a historical dirty latch')
    assert.equal(f.form.disabled(), false)
  })
}

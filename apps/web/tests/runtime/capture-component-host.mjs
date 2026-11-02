import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'

// Unit-only deterministic hook host: executes the actual component and handlers.
// It does not model React scheduling, DOM events, focus, accessibility or PWA storage.
export function mount(componentPath, exportName, props) {
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
    tree = Component(typeof props === 'function' ? props() : props)
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
    setProps(next) {
      props = next
      render()
    },
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

// App branch evaluation is real; effects, child rendering and reconciliation are
// simulated. This proves callback/state ownership only, NOT native React or DOM.
export function appHarness(runtime, { layoutEffects = false } = {}) {
  let logoutGuard = null
  const output = ts.transpileModule(
    readFileSync(new URL('../../src/App.tsx', import.meta.url), 'utf8'),
    {
      compilerOptions: {
        target: ts.ScriptTarget.ES2022,
        module: ts.ModuleKind.CommonJS,
        jsx: ts.JsxEmit.ReactJSX,
      },
    },
  ).outputText
  const element = (type, props, key) => ({ type, props, key })
  const require = (name) => {
    if (name === 'react')
      return {
        useSyncExternalStore: (_subscribe, get) => get(),
        useEffect() {},
        useLayoutEffect(effect) {
          if (layoutEffects) effect()
        },
        useMemo: (make) => make(),
      }
    if (name === 'react/jsx-runtime') return { jsx: element, jsxs: element }
    if (name.endsWith('.css')) return {}
    if (name.endsWith('/draft-state.js')) {
      const compiled = ts.transpileModule(
        readFileSync(new URL('../../src/features/draft-state.ts', import.meta.url), 'utf8'),
        {
          compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS },
        },
      ).outputText
      const draftModule = { exports: {} }
      new Function('module', 'exports', compiled)(draftModule, draftModule.exports)
      return draftModule.exports
    }
    if (name.endsWith('/administration/controller.js'))
      return {
        AdministrationController: class {
          setLogoutGuard(guard) {
            logoutGuard = guard
          }
        },
      }
    return new Proxy(
      {},
      {
        get: (_target, key) => {
          const stub = function () {}
          Object.defineProperty(stub, 'name', { value: key })
          return stub
        },
      },
    )
  }
  const module = { exports: {} }
  new Function('require', 'module', 'exports', output)(require, module, module.exports)
  return { render: () => module.exports.App({ runtime }), logoutGuard: () => logoutGuard }
}

export function observeCaptureMounts(runtime) {
  const app = appHarness(runtime)
  const forms = new Map()
  const phases = []
  let key
  function children(node) {
    if (!node || typeof node !== 'object') return []
    return [node, ...[node.props?.children].flat(Infinity).flatMap(children)]
  }
  function reconcile() {
    const tree = app.render()
    const phase = runtime.getSnapshot().phase
    phases.push(phase)
    if (key !== tree.key) forms.clear()
    key = tree.key
    const captures = children(tree).filter((node) =>
      ['CustomerQuickCreate', 'OrderQuickIntake'].includes(node.type?.name),
    )
    for (const name of forms.keys())
      if (!captures.some((node) => node.type.name === name)) forms.delete(name)
    for (const node of captures) {
      const name = node.type.name
      if (forms.has(name)) {
        forms.get(name).setProps(node.props)
        continue
      }
      const path =
        name === 'CustomerQuickCreate'
          ? '../../src/features/customers/CustomerQuickCreate.tsx'
          : '../../src/features/orders/OrderQuickIntake.tsx'
      forms.set(name, mount(path, name, node.props))
    }
  }
  const unsubscribe = runtime.subscribe(reconcile)
  reconcile()
  return { forms, phases, dispose: unsubscribe }
}

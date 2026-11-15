import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import ts from 'typescript'

const require = createRequire(import.meta.url)
const source = readFileSync(
  new URL('../../../../packages/ui/src/Button.tsx', import.meta.url),
  'utf8',
)
const output = ts.transpileModule(source, {
  compilerOptions: {
    target: ts.ScriptTarget.ES2022,
    module: ts.ModuleKind.CommonJS,
    jsx: ts.JsxEmit.ReactJSX,
  },
}).outputText
const exports = {}
new Function('require', 'exports', output)(require, exports)

test('shared Button changes semantic colors atomically and only transitions shadow', () => {
  const node = exports.Button({ children: 'Primeras órdenes' })
  const classes = node.props.className.split(/\s+/)
  assert.deepEqual(
    classes.filter((name) => name.startsWith('transition')),
    ['transition-shadow'],
  )
  for (const token of [
    'bg-[var(--ocwp-color-accent)]',
    'text-[var(--ocwp-color-on-accent)]',
    'hover:bg-[var(--ocwp-color-accent-strong)]',
    'focus-visible:outline-[var(--ocwp-color-focus)]',
  ])
    assert.ok(classes.includes(token), token)
  assert.equal(node.type, 'button')
  assert.equal(node.props.children, 'Primeras órdenes')
  assert.equal(node.props.type, 'button')
  assert.equal(node.props.disabled, false)
})

test('shadow-only correction preserves Button activation and disabled semantics', () => {
  const onClick = () => {}
  const node = exports.Button({
    children: 'Guardar',
    type: 'submit',
    disabled: true,
    'aria-label': 'Guardar cambio',
    onClick,
  })
  assert.equal(node.props.type, 'submit')
  assert.equal(node.props.disabled, true)
  assert.equal(node.props['aria-label'], 'Guardar cambio')
  assert.equal(node.props.onClick, onClick)
})

import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'

// Real React server rendering; no mocked hooks or JSX. This cannot prove
// browser focus, reconciliation or client error-boundary containment.
function load(relative) {
  const path = fileURLToPath(new URL(relative, import.meta.url))
  const cache = new Map()
  function compile(path) {
    if (cache.has(path)) return cache.get(path)
    const output = ts.transpileModule(readFileSync(path, 'utf8'), {
      compilerOptions: {
        target: ts.ScriptTarget.ES2022,
        module: ts.ModuleKind.CommonJS,
        jsx: ts.JsxEmit.ReactJSX,
      },
    }).outputText
    const module = { exports: {} }
    const nativeRequire = createRequire(path)
    const require = (name) =>
      name.startsWith('.')
        ? compile(resolve(dirname(path), name.replace(/\.js$/, '.ts')))
        : nativeRequire(name)
    new Function('require', 'module', 'exports', output)(require, module, module.exports)
    cache.set(path, module.exports)
    return module.exports
  }
  return compile(path)
}
const { ModuleInformation } = load('../../src/features/module-information/ModuleInformation.tsx')
const { officialModuleReference: fixture } = load(
  '../../src/features/module-information/reference.ts',
)

const render = (reference = fixture) =>
  renderToStaticMarkup(createElement(ModuleInformation, { reference }))

test('operators can inspect the exact reference scope without an installation or authority claim', () => {
  const html = render()
  assert.match(html, /<summary[^>]*>Información del módulo integrado<\/summary>/)
  assert.match(html, /org\.ocwp\.module-information/)
  assert.match(html, /AGPL-3\.0-only/)
  for (const label of ['Permisos solicitados', 'Datos operativos', 'Secretos', 'Destinos de red'])
    assert.ok(html.includes(`<dt>${label}</dt><dd>Ninguno</dd>`), label)
  assert.match(html, /Importación explícita al compilar/)
  assert.match(html, /Solo en línea; esta referencia no ejecuta operaciones/)
  assert.match(html, /no instala módulos ni concede permisos/)
  assert.match(html, /no certifica compatibilidad ni proporciona aislamiento/)
  assert.doesNotMatch(html, /<button|<input|<form|<a\s|<script/)
})

test('a build without the descriptor reports omission rather than installation state', () => {
  const html = render(null)
  assert.match(html, /Esta compilación no incluye la referencia/)
  assert.doesNotMatch(html, /<dt>|Instalar|Activar|Desinstalar/)
})

test('source-owned display text is escaped by real React rendering', () => {
  const html = render({ ...fixture, name: '<img src=x onerror=alert(1)>' })
  assert.match(html, /&lt;img src=x onerror=alert\(1\)&gt;/)
  assert.doesNotMatch(html, /<img/)
})

test('the one built-in descriptor declares no authority or data and is immutable', () => {
  assert.deepEqual(fixture.permissions, [])
  assert.deepEqual(fixture.data, [])
  assert.deepEqual(fixture.secrets, [])
  assert.deepEqual(fixture.network, [])
  assert.equal(fixture.operationalMode, 'online-only')
  assert.equal(fixture.composition, 'explicit-build-import')
  assert.ok(Object.isFrozen(fixture))
  for (const list of [fixture.permissions, fixture.data, fixture.secrets, fixture.network])
    assert.ok(Object.isFrozen(list))
})

test('summary target contract follows the actual supported workshop density and host focus tokens', () => {
  const require = createRequire(import.meta.url)
  const postcss = createRequire(require.resolve('vite/package.json'))('postcss')
  const { DEFAULT_PREFERENCES, validatePreferences } = load(
    '../../src/personalization/preferences.ts',
  )
  const preferences = validatePreferences({ ...DEFAULT_PREFERENCES, density: 'workshop' })
  assert.equal(preferences.valid, true)
  const css = postcss.parse(
    readFileSync(
      new URL('../../src/features/module-information/module-information.css', import.meta.url),
      'utf8',
    ),
  )
  const declarations = (selector) => {
    const values = {}
    css.walkRules(selector, (rule) =>
      rule.walkDecls((declaration) => {
        values[declaration.prop] = declaration.value
      }),
    )
    return values
  }
  assert.equal(declarations('.module-information summary')['min-height'], '44px')
  assert.equal(
    declarations(`[data-density='${preferences.preferences.density}'] .module-information summary`)[
      'min-height'
    ],
    '56px',
  )
  assert.equal(
    declarations('.module-information summary:focus-visible').outline,
    '3px solid var(--ocwp-color-focus, Highlight)',
  )
})

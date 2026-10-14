import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
const source = (name) =>
  readFileSync(new URL(`../../src/features/administration/${name}`, import.meta.url), 'utf8')
test('administration requires explicit verified entry and separates account from workshop', () => {
  const text = source('AdministrationPanel.tsx')
  assert.match(text, /Verificar acceso a administración/)
  assert.match(text, /Ámbito asignado a la cuenta/)
  assert.match(text, /Taller operativo seleccionado/)
  assert.match(text, /account.phase === 'connected'/)
  assert.match(text, /key={snapshot.generation}/)
})
test('credential controls clear synchronously before dispatch and on invalidation', () => {
  const text = source('SessionPanel.tsx') + source('UserForm.tsx') + source('UsersPanel.tsx')
  assert.match(text, /takeSecret/)
  assert.doesNotMatch(text, /useState[^\n]*(?:password|Password|contraseña)/)
  const helpers = source('controls.tsx')
  assert.match(helpers, /input.value = ''/)
  assert.match(helpers, /controller.subscribe/)
  assert.match(helpers, /useLayoutEffect/)
})
test('forms use current catalog, minimal patch and subordinate authorization', () => {
  const text = source('UserForm.tsx') + source('UsersPanel.tsx')
  assert.match(text, /minimalUserPatch/)
  assert.match(text, /canAdminister/)
  assert.match(text, /catalog.roles.map/)
  assert.match(text, /catalog.capabilities.map/)
  assert.match(text, /Confirmo el cambio de seguridad/)
  assert.match(text, /Descartar/)
})

test('explicit editor reopen remounts drafts and captures immutable reviewed versions', () => {
  const text = source('UsersPanel.tsx')
  assert.match(text, /setEditorInstance\(\(previous\) => previous \+ 1\)/)
  assert.match(text, /structuredClone\(next.row\)/)
  assert.match(text, /key={`edit-\$\{editorInstance\}`}/)
  assert.match(text, /returnFocus.current\?\.focus\(\)/)
})

test('directory pagination is explicit and filters refresh the matching result set', () => {
  const text = source('UsersPanel.tsx')
  assert.match(text, /setCursors\(\[\]\)/)
  assert.match(text, /refresh\(event.currentTarget.value\)/)
  assert.match(text, /Página anterior de usuarios/)
  assert.match(source('LocationsPanel.tsx'), /Página anterior de ubicaciones/)
  assert.match(source('UserForm.tsx'), /Array.from\(normalized\).length > 160/)
})

test('directory history stops at 64 pages without silently dropping previous cursors', () => {
  for (const file of ['UsersPanel.tsx', 'LocationsPanel.tsx']) {
    const text = source(file)
    assert.match(text, /const MAX_DIRECTORY_PAGES = 64/)
    assert.match(text, /disabled={snapshot.busy \|\| cursors.length >= MAX_DIRECTORY_PAGES - 1}/)
    assert.match(text, /previous.length < MAX_DIRECTORY_PAGES - 1/)
    assert.match(text, /Límite de 64 páginas/)
  }
})

test('role journeys select the exact accessible combobox instead of wrapped option label text', () => {
  const text = readFileSync(new URL('../../e2e/administration.spec.ts', import.meta.url), 'utf8')
  assert.equal(/getByLabel\('Rol'/.test(text), false)
  assert.equal(
    [...text.matchAll(/getByRole\('combobox', \{ name: 'Rol', exact: true \}\)\.selectOption/g)]
      .length,
    3,
  )
  assert.match(text, /selectOption\('TechnicalAdmin'\)/)
  assert.equal([...text.matchAll(/selectOption\('Viewer'\)/g)].length, 2)
})

test('workshop metrics and compact header reflow intrinsically at narrow available widths', () => {
  const css = readFileSync(new URL('../../src/styles.css', import.meta.url), 'utf8')
  const metrics = [...css.matchAll(/\.workshop-metrics\s*\{([^}]+)\}/g)].map((match) => match[1])
  assert.ok(
    metrics.some((rule) => /repeat\(auto-fit, minmax\(min\(100%, 12rem\), 1fr\)\)/.test(rule)),
  )
  assert.ok(metrics.every((rule) => !/grid-template-columns:\s*repeat\([24],/.test(rule)))
  const compact = css
    .split('@media (max-width: 1023px) {')[1]
    .split('@media (max-width: 639px) {')[0]
  assert.match(compact, /\.workshop-navigation\s*\{[^}]*display: flex;[^}]*flex-wrap: wrap;/s)
  assert.match(compact, /\.workshop-navigation\s*\{[^}]*flex-direction: row;/s)
  assert.match(compact, /\.workshop-identity\s*\{[^}]*flex: 1 1 13rem;/s)
  assert.match(compact, /repeat\(auto-fit, minmax\(min\(100%, 9rem\), 1fr\)\)/)
  assert.match(compact, /\.settings-trigger\s*\{[^}]*max-width: 100%;/s)
  assert.doesNotMatch(css, /zoom\s*:/)
})

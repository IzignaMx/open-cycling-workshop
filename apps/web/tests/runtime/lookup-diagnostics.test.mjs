import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import ts from 'typescript'
const source = readFileSync(
  new URL('../../e2e/helpers/lookup-diagnostics.ts', import.meta.url),
  'utf8',
)
const module = { exports: {} }
new Function(
  'module',
  'exports',
  ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText,
)(module, module.exports)
const { lookupDiagnostic } = module.exports
const expectedIds = Array.from({ length: 51 }, (_, i) => `synthetic-${i}`)
const input = {
  stage: 'page_two',
  phase: 'READY',
  expectedIds,
  admittedIds: expectedIds,
  optionIds: ['', expectedIds[50]],
  targetId: expectedIds[50],
  targetNameMatches: true,
  query: 'synthetic name',
  expectedQuery: 'synthetic name',
  status:
    '1 coincidencias en esta página. 2 páginas revisadas. Fin de los registros disponibles localmente; puede haber clientes no descargados.',
  selectedId: '',
}
test('diagnostic reports actual admitted membership and completed second page without identifiers', () => {
  const result = lookupDiagnostic(input)
  assert.equal(result.baselineExact, true)
  assert.equal(result.targetAdmitted, true)
  assert.equal(result.targetNameMatches, true)
  assert.equal(result.pages, 2)
  assert.equal(result.targetOption, true)
  assert.equal(result.queryMatches, true)
  assert.equal(result.status, 'exhausted')
  assert.equal(result.selectionEmpty, true)
  const encoded = JSON.stringify(result)
  for (const value of [...expectedIds, input.query, input.status])
    assert.equal(encoded.includes(value), false)
})
test('diagnostic rejects unrecognized strings, bounds counts and never leaks arbitrary canaries', () => {
  const canary = 'PRIVATE-CANARY-contact-token-query'
  const result = lookupDiagnostic({
    ...input,
    stage: canary,
    phase: canary,
    status: canary,
    query: canary,
    admittedIds: Array(5000).fill(canary),
    optionIds: Array(5000).fill(canary),
    selectedId: canary,
  })
  assert.equal(result.stage, 'unknown')
  assert.equal(result.phase, 'unknown')
  assert.equal(result.status, 'unknown')
  assert.equal(result.baselineCount, 52)
  assert.equal(result.optionCount, 52)
  assert.equal(result.optionOverflow, true)
  assert.equal(result.targetAdmitted, false)
  assert.equal(result.baselineExact, false)
  assert.equal(result.queryMatches, false)
  assert.equal(JSON.stringify(result).includes(canary), false)
  assert.ok(JSON.stringify(result).length < 1024)
})
test('diagnostic separates bounded refusal, progress and missing admission from exhaustion', () => {
  const refused = lookupDiagnostic({
    ...input,
    status: 'No se pudo consultar la lista local. Vuelve a intentarlo.',
    admittedIds: expectedIds.slice(0, 50),
    optionIds: [''],
  })
  assert.equal(refused.status, 'read_failed')
  assert.equal(refused.targetAdmitted, false)
  assert.equal(refused.baselineExact, false)
  assert.equal(refused.targetOption, false)
  assert.equal(
    lookupDiagnostic({ ...input, status: 'Consultando clientes locales…' }).status,
    'busy',
  )
})

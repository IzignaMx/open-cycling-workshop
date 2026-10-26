import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import ts from 'typescript'
import { expect } from '@playwright/test'

// Execute the checked-in helper, not a parallel copy of its control flow.
export function checkedInOpenBranding() {
  const source = ts.createSourceFile(
    'branding.spec.ts',
    readFileSync(new URL('../../e2e/branding.spec.ts', import.meta.url), 'utf8'),
    ts.ScriptTarget.Latest,
    true,
  )
  const helper = source.statements.find(
    (statement) => ts.isFunctionDeclaration(statement) && statement.name?.text === 'openBranding',
  )
  assert.ok(helper, 'the branding journey must use its checked-in helper')
  const javascript = ts.transpileModule(helper.getText(source), {
    compilerOptions: { target: ts.ScriptTarget.ES2022 },
  }).outputText
  return vm.runInNewContext(`${javascript}\nopenBranding`, { expect })
}

import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import ts from 'typescript'
const source = (file) =>
  readFileSync(new URL(`../../src/features/administration/${file}`, import.meta.url), 'utf8')
const compiled = ts.transpileModule(source('draft-revision.ts'), {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext },
}).outputText
const { isConfirmedDraftRevision } = await import(
  `data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`
)
test('only exact confirmed submitted revision clears a draft', () => {
  assert.equal(isConfirmedDraftRevision('confirmed', 2, 2), true)
  assert.equal(isConfirmedDraftRevision('confirmed', 2, 3), false)
  for (const receipt of [undefined, null, 'refused', 'uncertain', 'stale', 'success']) {
    assert.equal(isConfirmedDraftRevision(receipt, 2, 2), false)
  }
})
test('retained forms fence receipts by local revision, current generation and mount', () => {
  for (const file of ['UserForm.tsx', 'LocationsPanel.tsx', 'UsersPanel.tsx']) {
    const text = source(file)
    assert.match(text, /isConfirmedDraftRevision\(/)
    assert.match(text, /revision.current\+\+/)
    assert.match(text, /controller.getSnapshot\(\).generation === submittedGeneration/)
    assert.match(text, /form.current/)
    assert.doesNotMatch(text, /snapshot.result\s*===\s*['"]success/)
  }
})
test('self password submit does not mark unresolved work clean', () => {
  const submit = source('SessionPanel.tsx').split('onSubmit=')[1].split('      >')[0]
  assert.match(submit, /controller.changePassword/)
  assert.doesNotMatch(submit, /setDirty\(false\)/)
})

test('newer user security review interaction advances the pending receipt revision', () => {
  const review = source('UserForm.tsx').split('{security && (')[1]
  assert.match(review, /markEdited\(\)[\s\S]*setReviewed\(event.currentTarget.checked\)/)
  assert.equal(isConfirmedDraftRevision('confirmed', 8, 9), false)
})

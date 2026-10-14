import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import ts from 'typescript'

const source = readFileSync(new URL('../../src/features/draft-state.ts', import.meta.url), 'utf8')
const compiled = ts.transpileModule(source, {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext },
}).outputText
const { hasCustomerDraft, hasOrderDraft, hasUnsentForms } = await import(
  `data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`
)
const blankCustomer = { displayName: '', email: '', phone: '' }
const blankOrder = {
  customerId: '',
  priority: 'normal',
  reportedProblem: '',
  intakeCondition: '',
  accessories: '',
  withBicycle: false,
  brand: '',
  model: '',
}

test('saved customer reset is clean; every current unsent contact field remains dirty', () => {
  assert.equal(hasCustomerDraft(blankCustomer), false)
  for (const field of Object.keys(blankCustomer)) {
    assert.equal(hasCustomerDraft({ ...blankCustomer, [field]: 'unsent' }), true)
  }
  const edited = { ...blankCustomer, displayName: 'unsent' }
  assert.equal(hasCustomerDraft(edited), true)
  assert.equal(hasCustomerDraft({ ...edited, displayName: '' }), false)
})
test('order baseline preserves saved customer and priority but detects each pending model change', () => {
  assert.equal(hasOrderDraft(blankOrder), false)
  const savedSelection = { customerId: 'customer-1', priority: 'high' }
  const resetAfterSave = { ...blankOrder, ...savedSelection }
  assert.equal(hasOrderDraft(resetAfterSave, savedSelection), false)
  for (const field of Object.keys(blankOrder)) {
    assert.equal(
      hasOrderDraft(
        { ...resetAfterSave, [field]: field === 'withBicycle' ? true : 'changed' },
        savedSelection,
      ),
      true,
    )
  }
  // A failed submission never advances the clean baseline.
  assert.equal(
    hasOrderDraft({ ...resetAfterSave, reportedProblem: 'failed draft' }, savedSelection),
    true,
  )
})
test('guard observes current mounted markers instead of past input or search activity', () => {
  let pending = false
  const root = {
    querySelector(selector) {
      assert.match(selector, /data-dirty="true"/)
      return pending ? {} : null
    },
  }
  assert.equal(hasUnsentForms(root), false)
  pending = true
  assert.equal(hasUnsentForms(root), true)
  pending = false
  assert.equal(hasUnsentForms(root), false)
})
test('production composition guards selector transitions and removes the irreversible input latch', () => {
  const app = readFileSync(new URL('../../src/App.tsx', import.meta.url), 'utf8')
  assert.doesNotMatch(app, /operationalDirty|onInputCapture/)
  assert.match(app, /leaveWorkshop\(\(\) => runtime.selectWorkshop\(location.location_id\)\)/)
  assert.match(app, /hasUnsentForms\(document\)/)
})

import test from 'node:test'
import assert from 'node:assert/strict'
import * as feedback from '../../.tmp-runtime/src/features/capture-feedback.js'

test('capture presentation accepts closed outcomes, never raw rejected errors', () => {
  assert.equal(typeof feedback.captureFeedback, 'function')
  for (const error of [
    new Error('private-canary'),
    new DOMException('private-canary', 'QuotaExceededError'),
    { name: 'QuotaExceededError', inner: new Error('private-canary') },
  ]) {
    const result = feedback.captureFeedback({ kind: 'rejected', error })
    assert.equal(result.status, 'unknown')
    assert.equal(result.blockSubmission, true)
    assert.equal(result.message.includes('private-canary'), false)
  }
  assert.deepEqual(feedback.captureFeedback({ kind: 'resolved', value: { status: 'saved' } }), {
    status: 'saved',
    message: null,
    blockSubmission: false,
  })
  for (const value of [
    undefined,
    null,
    [],
    { status: 'saved', message: 'private-canary' },
    { status: 'not_saved', reason: 'quota', extra: true },
    { status: 'not_saved', reason: 'validation', code: 'private-canary' },
  ]) {
    assert.equal(feedback.captureFeedback({ kind: 'resolved', value }).status, 'unknown')
  }
  const quota = feedback.captureFeedback({
    kind: 'resolved',
    value: { status: 'not_saved', reason: 'quota' },
  })
  assert.equal(quota.status, 'not_saved')
  assert.equal(quota.blockSubmission, false)
  assert.match(quota.message, /sin borrar los datos/)
})

test('capture submission guard is synchronous and unknown remains latched independent of draft fields', () => {
  assert.equal(typeof feedback.CaptureSubmissionGate, 'function')
  const gate = new feedback.CaptureSubmissionGate()
  assert.equal(gate.begin(), true)
  assert.equal(gate.begin(), false)
  gate.finish({ status: 'not_saved', message: 'safe', blockSubmission: false })
  assert.equal(gate.begin(), true)
  gate.finish({ status: 'unknown', message: 'safe', blockSubmission: true })
  assert.equal(gate.blocked, true)
  assert.equal(gate.begin(), false)
  gate.finish({ status: 'saved', message: null, blockSubmission: false })
  assert.equal(gate.blocked, true)
  assert.equal(gate.begin(), false)
})

test('capture fixed validation messages and hostile result objects do not expose input', () => {
  assert.equal(typeof feedback.captureFeedback, 'function')
  const codes = [
    'customer_name_required',
    'order_problem_required',
    'priority_invalid',
    'bicycle_brand_required',
  ]
  for (const code of codes) {
    const result = feedback.captureFeedback({
      kind: 'resolved',
      value: { status: 'not_saved', reason: 'validation', code },
    })
    assert.equal(result.status, 'not_saved')
    assert.equal(result.blockSubmission, false)
  }
  const hostile = Object.defineProperty({}, 'status', {
    enumerable: true,
    get() {
      throw new Error('private-canary')
    },
  })
  assert.equal(feedback.captureFeedback({ kind: 'resolved', value: hostile }).status, 'unknown')
})

test('capture presentation rejects unknown nonenumerable and symbol fields', () => {
  const hidden = Object.defineProperty({ status: 'saved' }, 'unrecognized', {
    value: 'private-canary',
  })
  const symbol = { status: 'saved', [Symbol('unrecognized')]: 'private-canary' }
  for (const value of [hidden, symbol]) {
    assert.equal(feedback.captureFeedback({ kind: 'resolved', value }).status, 'unknown')
  }
})

import test from 'node:test'
import assert from 'node:assert/strict'

import {
  ORDER_STATE_LABELS,
  TRANSITION_ACTION_LABELS,
  normalizeOrderIntake,
} from '../../.tmp-orders/src/features/orders/order-model.js'

test('normalizeOrderIntake collapses text and validates the problem', () => {
  const result = normalizeOrderIntake({
    customerId: 'customer-1',
    reportedProblem: '  Cadena   saltando ',
    intakeCondition: '  Rayado  leve ',
    accessories: ' Canasto, luz ',
    priority: 'high',
    brand: '  Trek   Marlin ',
    model: ' 7 ',
  })

  assert.equal(result.reportedProblem, 'Cadena saltando')
  assert.equal(result.intakeCondition, 'Rayado leve')
  assert.equal(result.accessories, 'Canasto, luz')
  assert.equal(result.priority, 'high')
  assert.equal(result.brand, 'Trek Marlin')
  assert.equal(result.model, '7')
})

test('normalizeOrderIntake defaults priority and empties optionals to null', () => {
  const result = normalizeOrderIntake({
    customerId: 'customer-1',
    reportedProblem: 'Frenos',
  })

  assert.equal(result.priority, 'normal')
  assert.equal(result.intakeCondition, null)
  assert.equal(result.accessories, null)
  assert.equal(result.brand, null)
  assert.equal(result.model, null)
})

test('normalizeOrderIntake rejects a blank problem and unknown priorities', () => {
  assert.throws(
    () => normalizeOrderIntake({ customerId: 'customer-1', reportedProblem: '   ' }),
    /problema/i,
  )
  assert.throws(
    () =>
      normalizeOrderIntake({
        customerId: 'customer-1',
        reportedProblem: 'Frenos',
        priority: 'urgentisimo',
      }),
    /prioridad/i,
  )
})

test('state labels exist for every order state without relying on color', () => {
  for (const state of [
    'INTAKE',
    'DIAGNOSIS',
    'AUTHORIZED',
    'REJECTED',
    'IN_PROGRESS',
    'WAITING_FOR_PARTS',
    'READY',
    'CLOSED',
    'CANCELLED',
  ]) {
    assert.ok(ORDER_STATE_LABELS[state], state)
    assert.equal(typeof ORDER_STATE_LABELS[state], 'string')
  }
})

test('transition labels exist for every action', () => {
  for (const action of [
    'start_diagnosis',
    'authorize',
    'reject',
    'start_work',
    'request_parts',
    'resume_work',
    'mark_ready',
    'close',
    'cancel',
  ]) {
    assert.ok(TRANSITION_ACTION_LABELS[action], action)
  }
})

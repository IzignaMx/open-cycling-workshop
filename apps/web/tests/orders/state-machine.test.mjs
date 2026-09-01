import test from 'node:test'
import assert from 'node:assert/strict'

import {
  ORDER_TRANSITIONS,
  legalTransition,
  orderActionsFor,
} from '../../.tmp-sync/src/features/orders/state-machine.js'

test('mirror matches the server-authoritative happy path', () => {
  assert.equal(legalTransition('INTAKE', 'start_diagnosis'), 'DIAGNOSIS')
  assert.equal(legalTransition('DIAGNOSIS', 'authorize'), 'AUTHORIZED')
  assert.equal(legalTransition('DIAGNOSIS', 'reject'), 'REJECTED')
  assert.equal(legalTransition('AUTHORIZED', 'start_work'), 'IN_PROGRESS')
  assert.equal(legalTransition('IN_PROGRESS', 'request_parts'), 'WAITING_FOR_PARTS')
  assert.equal(legalTransition('WAITING_FOR_PARTS', 'resume_work'), 'IN_PROGRESS')
  assert.equal(legalTransition('IN_PROGRESS', 'mark_ready'), 'READY')
  assert.equal(legalTransition('READY', 'close'), 'CLOSED')
})

test('cancel is legal from every pre-READY state only', () => {
  for (const state of [
    'INTAKE',
    'DIAGNOSIS',
    'AUTHORIZED',
    'REJECTED',
    'IN_PROGRESS',
    'WAITING_FOR_PARTS',
  ]) {
    assert.equal(legalTransition(state, 'cancel'), 'CANCELLED', state)
  }
  assert.equal(legalTransition('READY', 'cancel'), null)
  assert.equal(legalTransition('CLOSED', 'cancel'), null)
  assert.equal(legalTransition('CANCELLED', 'cancel'), null)
})

test('illegal transitions return null instead of throwing', () => {
  assert.equal(legalTransition('INTAKE', 'mark_ready'), null)
  assert.equal(legalTransition('INTAKE', 'close'), null)
  assert.equal(legalTransition('DIAGNOSIS', 'start_work'), null)
  assert.equal(legalTransition('AUTHORIZED', 'authorize'), null)
  assert.equal(legalTransition('IN_PROGRESS', 'start_work'), null)
  assert.equal(legalTransition('WAITING_FOR_PARTS', 'mark_ready'), null)
  assert.equal(legalTransition('CLOSED', 'close'), null)
})

test('unknown actions have no legal transition', () => {
  assert.equal(legalTransition('INTAKE', 'explode'), null)
})

test('orderActionsFor exposes only legal actions per state', () => {
  assert.deepEqual(orderActionsFor('INTAKE'), ['start_diagnosis', 'cancel'])
  assert.deepEqual(orderActionsFor('IN_PROGRESS'), ['request_parts', 'mark_ready', 'cancel'])
  assert.deepEqual(orderActionsFor('CLOSED'), [])
  assert.ok(Object.keys(ORDER_TRANSITIONS).length >= 9)
})

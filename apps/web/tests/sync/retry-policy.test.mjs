import test from 'node:test'
import assert from 'node:assert/strict'

import { retryPlan } from '../../.tmp-sync/src/sync/retry-policy.js'

test('retry plan grows exponentially from a short base delay', () => {
  assert.deepEqual(retryPlan(0), { delayMs: 2_000, exhausted: false })
  assert.deepEqual(retryPlan(1), { delayMs: 4_000, exhausted: false })
  assert.deepEqual(retryPlan(2), { delayMs: 8_000, exhausted: false })
  assert.deepEqual(retryPlan(3), { delayMs: 16_000, exhausted: false })
})

test('retry plan delay is capped so backoff stays bounded', () => {
  assert.deepEqual(retryPlan(4), { delayMs: 30_000, exhausted: false })
  assert.deepEqual(retryPlan(5), { delayMs: 30_000, exhausted: false })
})

test('retry plan is exhausted after the attempt budget and never loops forever', () => {
  assert.equal(retryPlan(7).exhausted, false)
  assert.deepEqual(retryPlan(8), { delayMs: 30_000, exhausted: true })
  assert.deepEqual(retryPlan(50), { delayMs: 30_000, exhausted: true })
})

test('retry plan tolerates invalid attempt counts without throwing', () => {
  assert.deepEqual(retryPlan(-3), { delayMs: 2_000, exhausted: false })
  assert.deepEqual(retryPlan(2.9), { delayMs: 8_000, exhausted: false })
})

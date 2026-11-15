import test from 'node:test'
import assert from 'node:assert/strict'
import { crashFixture, validCrashFixture, protectedId } from './crash-fixture.mjs'
import { captureFixture } from './fixture.mjs'
import {
  CAPTURE_TTL_MS,
  validCheckpoint,
} from '../../.tmp-kernel/src/access-kernel/capture-checkpoint.js'
import { canonicalJson } from '../../.tmp-kernel/src/access-kernel/operations.js'
const now = Date.parse('2026-11-15T12:00:00Z')
const make = () => crashFixture(now, CAPTURE_TTL_MS, canonicalJson)
const valid = (data) => validCrashFixture(data, validCheckpoint)
test('crash fixture preserves existing UNSENT controls and adds a distinct valid PROTECTED checkpoint without payload', () => {
  const data = make()
  const { protectedCheckpoint, ...original } = data
  assert.deepEqual(original, captureFixture(now, CAPTURE_TTL_MS, canonicalJson))
  assert.ok(valid(data))
  assert.ok(validCheckpoint(protectedCheckpoint))
  assert.equal(protectedCheckpoint.checkpointId, protectedId)
  assert.notEqual(protectedId, data.checkpoint.checkpointId)
  assert.equal(protectedCheckpoint.order.contentExpiresAt, now + CAPTURE_TTL_MS)
  assert.equal(protectedCheckpoint.order.state, 'PROTECTED')
  assert.equal(protectedCheckpoint.customer.state, 'EMPTY')
})
for (const [name, mutate] of [
  [
    'absent protected attempt',
    (d) => {
      d.protectedCheckpoint.order.attemptId = null
    },
  ],
  [
    'rearmed protected channel',
    (d) => {
      d.protectedCheckpoint.order.state = 'UNSENT'
      d.protectedCheckpoint.order.attemptId = null
    },
  ],
  [
    'extended protected TTL',
    (d) => {
      d.protectedCheckpoint.order.contentExpiresAt += 1
    },
  ],
  [
    'shared checkpoint identity',
    (d) => {
      d.protectedCheckpoint.checkpointId = d.checkpoint.checkpointId
    },
  ],
  [
    'protected payload supplied',
    (d) => {
      d.future.checkpointId = protectedId
    },
  ],
  [
    'UNSENT mislabeled protected',
    (d) => {
      d.checkpoint.order.state = 'PROTECTED'
      d.checkpoint.order.attemptId = d.protectedCheckpoint.order.attemptId
    },
  ],
])
  test(`crash fixture refuses ${name}`, () => {
    const data = make()
    mutate(data)
    assert.equal(valid(data), false)
  })

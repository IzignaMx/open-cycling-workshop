import test from 'node:test'
import assert from 'node:assert/strict'
import { captureFixture, witnessId } from './fixture.mjs'
import {
  validCheckpoint,
  validContent,
  preservableUnsupportedContent,
  CAPTURE_TTL_MS,
} from '../../.tmp-kernel/src/access-kernel/capture-checkpoint.js'
import {
  canonicalJson,
  operationIntact,
  validateCommand,
} from '../../.tmp-kernel/src/access-kernel/operations.js'
const now = Date.parse('2026-11-13T12:00:00Z')
const data = captureFixture(now, CAPTURE_TTL_MS, canonicalJson)
test('native App fixture has exact valid v1 checkpoint and customer', () => {
  assert.ok(validCheckpoint(data.checkpoint))
  assert.ok(validContent(data.customer))
  assert.equal(data.checkpoint.closed, false)
})
test('future payload has supported lifecycle envelope and exact checkpoint match', () => {
  assert.equal(validContent(data.future), false)
  assert.ok(preservableUnsupportedContent(data.future))
  for (const content of [data.customer, data.future]) {
    for (const field of ['checkpointId', 'generation'])
      assert.equal(content[field], data.checkpoint[field])
    const channel = data.checkpoint[content.channel]
    assert.equal(channel.state, 'UNSENT')
    assert.equal(channel.revision, content.revision)
    assert.equal(channel.contentStartedAt, content.firstPersistedAt)
    assert.equal(channel.contentExpiresAt, content.expiresAt)
    assert.equal(content.expiresAt, now + CAPTURE_TTL_MS)
  }
})
test('expired orphan is a valid v1 maintenance witness sorting after the target', () => {
  assert.ok(validContent(data.witness))
  assert.equal(data.witness.checkpointId, witnessId)
  assert.ok(witnessId > data.checkpoint.checkpointId)
  assert.ok(data.witness.expiresAt < now)
})
test('journal sentinel is an intact existing-schema command with valid projection', () => {
  const journal = data.journal
  assert.ok(operationIntact(journal))
  assert.equal(journal.localSequence, 1)
  assert.equal(journal.createdAt, journal.envelope.occurred_at)
  const context = {
    principal: { organizationId: journal.organizationId },
    selectedLocationId: journal.locationId,
    capabilities: ['customers.write'],
  }
  assert.equal(
    validateCommand(
      {
        envelope: journal.envelope,
        optimistic: journal.optimistic,
        dependsOn: journal.dependsOn,
        localEvents: [],
      },
      context,
    ),
    journal.envelopeCanonical,
  )
})

import 'fake-indexeddb/auto'
import test from 'node:test'
import assert from 'node:assert/strict'
import { createKernelDatabase } from '../../.tmp-kernel/src/access-kernel/database.js'
const store = await import('../../.tmp-kernel/src/access-kernel/capture-checkpoint-store.js').catch(
  () => ({}),
)
const id = '11111111-1111-4111-8111-111111111111'
const generation = '22222222-2222-4222-8222-222222222222'
const attemptId = '33333333-3333-4333-8333-333333333333'
const binding = 'a'.repeat(64),
  scopeKey = 'b'.repeat(64),
  now = 1000
const customer = { channel: 'customer', draft: { displayName: 'Synthetic', email: '', phone: '' } }
const scope = {}
async function fixture(fn) {
  const db = createKernelDatabase(`capture-${crypto.randomUUID()}`)
  try {
    await db.open()
    await db.deviceControl.put({
      key: 'device',
      generation: 1,
      tabAttemptId: null,
      activePartitionId: null,
      state: 'LOCKED',
      localSequence: 0,
      observedAt: now,
      dispatchAttemptId: null,
      dispatchScanAfter: 0,
    })
    assert.equal(
      typeof store.applyCaptureCheckpoint,
      'function',
      'shared durable checkpoint boundary exists',
    )
    const call = (command, at = now, key = scopeKey) =>
      db.transaction('rw', [db.deviceControl, db.captureCheckpoints, db.captureDraftContents], () =>
        store.applyCaptureCheckpoint(db, { checkpointId: id, scope, ...command }, binding, key, at),
      )
    assert.equal((await call({ kind: 'enroll', generation })).kind, 'ack')
    await fn(db, call)
  } finally {
    db.close()
    await db.delete()
  }
}
const cas = { generation, channel: 'customer', expectedRevision: 0 }
test('actual database persists and restores exact same-binding unsent fields', () =>
  fixture(async (db, call) => {
    assert.equal((await call({ kind: 'save', ...cas, content: customer })).kind, 'ack')
    const loaded = await call({ kind: 'load' })
    assert.deepEqual(loaded.contents.customer.draft, customer.draft)
    assert.equal(loaded.checkpoint.customer.revision, 1)
    assert.ok(Object.isFrozen(loaded.contents.customer.draft))
  }))
test('protect removes private bytes and stale clone cannot save or protect', () =>
  fixture(async (db, call) => {
    await call({ kind: 'save', ...cas, content: customer })
    assert.equal(
      (await call({ kind: 'protect', ...cas, expectedRevision: 1, attemptId })).kind,
      'ack',
    )
    assert.equal(await db.captureDraftContents.count(), 0)
    assert.equal((await call({ kind: 'save', ...cas, content: customer })).kind, 'refused')
    assert.equal(
      (await call({ kind: 'protect', ...cas, expectedRevision: 1, attemptId })).kind,
      'refused',
    )
    assert.equal((await call({ kind: 'load' })).checkpoint.customer.state, 'PROTECTED')
  }))
test('binding uniqueness prevents new checkpoint enrollment bypass', () =>
  fixture(async (db, call) => {
    assert.equal(
      (await call({ kind: 'enroll', generation, checkpointId: attemptId })).kind,
      'refused',
    )
    assert.equal(await db.captureCheckpoints.count(), 1)
  }))
test('wrong attempt cannot settle; exact trusted receipt retains fixed TTL', () =>
  fixture(async (db, call) => {
    await call({ kind: 'save', ...cas, content: customer })
    await call({ kind: 'protect', ...cas, expectedRevision: 1, attemptId })
    const receipt = {
      kind: 'settle',
      ...cas,
      expectedRevision: 2,
      attemptId,
      outcome: 'not_saved',
      content: customer,
    }
    assert.equal((await call({ ...receipt, attemptId: generation })).kind, 'refused')
    assert.equal((await call(receipt, 2000)).kind, 'ack')
    assert.equal((await call({ kind: 'load' }, 2000)).contents.customer.expiresAt, now + 86400000)
  }))
test('expiry cleanup removes PII, preserves protected denial and does not slide TTL', () =>
  fixture(async (db, call) => {
    await call({ kind: 'save', ...cas, content: customer })
    await call({ kind: 'save', ...cas, expectedRevision: 1, content: customer }, 2000)
    assert.equal((await db.captureDraftContents.get([id, 'customer'])).expiresAt, now + 86400000)
    assert.deepEqual(await store.sweepExpiredCaptureContents(db, now + 86400000), {
      kind: 'complete',
    })
    assert.equal(await db.captureDraftContents.count(), 0)
    assert.equal((await db.captureCheckpoints.get(id)).customer.state, 'EMPTY')
    await call({ kind: 'protect', ...cas, expectedRevision: 3, attemptId }, now + 86400000)
    await store.sweepExpiredCaptureContents(db, now + 2 * 86400000)
    assert.equal((await db.captureCheckpoints.get(id)).customer.state, 'PROTECTED')
  }))
test('logout closes exact generation, deletes content, retains protected marker', () =>
  fixture(async (db, call) => {
    await call({ kind: 'protect', ...cas, attemptId })
    await store.purgeCaptureContents(db, id, attemptId)
    assert.equal((await db.captureCheckpoints.get(id)).closed, false)
    await store.purgeCaptureContents(db, id, generation)
    assert.equal((await db.captureCheckpoints.get(id)).closed, true)
    assert.equal((await db.captureCheckpoints.get(id)).customer.state, 'PROTECTED')
    assert.equal((await call({ kind: 'load' })).reason, 'closed')
  }))
test('scope retirement cannot reset protection or accept old generation', () =>
  fixture(async (db, call) => {
    await call({ kind: 'protect', ...cas, attemptId })
    assert.equal((await call({ kind: 'load' }, now, 'c'.repeat(64))).kind, 'scope_changed')
    const result = await call(
      { kind: 'retireScope', generation, nextGeneration: attemptId },
      now,
      'c'.repeat(64),
    )
    assert.equal(result.kind, 'ack')
    assert.equal(result.checkpoint.customer.state, 'PROTECTED')
    assert.equal(
      (await call({ kind: 'save', ...cas, content: customer }, now, 'c'.repeat(64))).kind,
      'refused',
    )
  }))
test('clock rollback, oversize and missing checkpoints fail closed', () =>
  fixture(async (db, call) => {
    assert.equal((await call({ kind: 'load' }, now - 1)).reason, 'clock')
    assert.equal(
      (
        await call({
          kind: 'save',
          ...cas,
          content: { ...customer, draft: { ...customer.draft, displayName: 'x'.repeat(65536) } },
        })
      ).reason,
      'oversize',
    )
    await db.captureCheckpoints.delete(id)
    assert.equal((await call({ kind: 'save', ...cas, content: customer })).reason, 'missing')
  }))
test('malformed unindexed expiry is scanned and corrupt unsent is unavailable', () =>
  fixture(async (db, call) => {
    await call({ kind: 'save', ...cas, content: customer })
    await db.captureDraftContents.update([id, 'customer'], { expiresAt: undefined })
    assert.equal((await store.sweepExpiredCaptureContents(db, now)).kind, 'complete')
    assert.equal(await db.captureDraftContents.count(), 0)
    assert.equal((await db.captureCheckpoints.get(id)).customer.state, 'UNAVAILABLE')
  }))
test('missing expected UNSENT content cannot be silently recreated or dispatched', () =>
  fixture(async (db, call) => {
    await call({ kind: 'save', ...cas, content: customer })
    await db.captureDraftContents.delete([id, 'customer'])
    assert.equal(
      (await call({ kind: 'save', ...cas, expectedRevision: 1, content: customer })).reason,
      'invalid',
    )
    assert.equal(
      (await call({ kind: 'protect', ...cas, expectedRevision: 1, attemptId })).reason,
      'invalid',
    )
  }))
test('unknown command fields and malformed projections never reach durable content', () =>
  fixture(async (db, call) => {
    assert.equal(
      (await call({ kind: 'save', ...cas, content: customer, unexpected: 'private' })).reason,
      'invalid',
    )
    assert.equal(
      (
        await call({
          kind: 'save',
          ...cas,
          content: { ...customer, draft: { ...customer.draft, unexpected: 'private' } },
        })
      ).reason,
      'invalid',
    )
    assert.equal(await db.captureDraftContents.count(), 0)
  }))
test('order hidden bicycle fields and retained selection round trip unchanged', () =>
  fixture(async (db, call) => {
    const content = {
      channel: 'order',
      draft: {
        customerId: 'synthetic-customer',
        priority: 'urgent',
        reportedProblem: 'flat',
        intakeCondition: 'used',
        accessories: 'lock',
        withBicycle: false,
        brand: 'retained hidden brand',
        model: 'retained hidden model',
      },
      retainedSelection: { customerId: 'prior', priority: 'normal' },
    }
    assert.equal(
      (await call({ kind: 'save', generation, channel: 'order', expectedRevision: 0, content }))
        .kind,
      'ack',
    )
    const restored = (await call({ kind: 'load' })).contents.order
    assert.deepEqual(restored.draft, content.draft)
    assert.deepEqual(restored.retainedSelection, content.retainedSelection)
  }))
test('settlement after absolute expiry resolves without refreshing old private content', () =>
  fixture(async (db, call) => {
    await call({ kind: 'save', ...cas, content: customer })
    await call({ kind: 'protect', ...cas, expectedRevision: 1, attemptId })
    const settled = await call(
      {
        kind: 'settle',
        ...cas,
        expectedRevision: 2,
        attemptId,
        outcome: 'saved',
        content: customer,
      },
      now + 86400000,
    )
    assert.equal(settled.kind, 'ack')
    assert.equal(settled.checkpoint.customer.state, 'EMPTY')
    assert.equal(await db.captureDraftContents.count(), 0)
  }))
test('aborted transaction cannot acknowledge persisted save and keeps prior CAS', () =>
  fixture(async (db, call) => {
    db.captureDraftContents.hook('creating', () => {
      throw new Error('synthetic quota')
    })
    await assert.rejects(call({ kind: 'save', ...cas, content: customer }), /synthetic quota/)
    assert.equal((await db.captureCheckpoints.get(id)).customer.revision, 0)
    assert.equal(await db.captureDraftContents.count(), 0)
  }))
test('cleanup storage failure returns unavailable without claiming deletion', () =>
  fixture(async (db, call) => {
    await call({ kind: 'save', ...cas, content: customer })
    db.captureDraftContents.hook('deleting', () => {
      throw new Error('synthetic storage failure')
    })
    assert.equal((await store.purgeCaptureContents(db, id, generation)).kind, 'unavailable')
    assert.equal((await store.sweepExpiredCaptureContents(db, now + 86400000)).kind, 'unavailable')
    assert.equal(await db.captureDraftContents.count(), 1)
    assert.equal((await db.captureCheckpoints.get(id)).closed, false)
  }))
test('maintenance scans more than one bounded page including malformed unindexed rows', () =>
  fixture(async (db) => {
    for (let index = 0; index < 130; index++)
      await db.captureDraftContents.put({
        checkpointId: crypto.randomUUID(),
        channel: 'customer',
        draft: { displayName: 'synthetic orphan' },
        expiresAt: index % 2 ? now - 1 : undefined,
      })
    assert.equal(await db.captureDraftContents.count(), 130)
    assert.equal((await store.sweepExpiredCaptureContents(db, now)).kind, 'complete')
    assert.equal(await db.captureDraftContents.count(), 0)
  }))
test('rollback maintenance removes private values but never rearms the channel', () =>
  fixture(async (db, call) => {
    await call({ kind: 'save', ...cas, content: customer })
    assert.equal((await store.sweepExpiredCaptureContents(db, now - 1)).kind, 'complete')
    assert.equal(await db.captureDraftContents.count(), 0)
    assert.equal((await db.captureCheckpoints.get(id)).customer.state, 'UNAVAILABLE')
  }))
test('logout missing checkpoint cannot report completion leaving its matching private orphan', () =>
  fixture(async (db, call) => {
    await call({ kind: 'save', ...cas, content: customer })
    await db.captureCheckpoints.delete(id)
    const result = await store.purgeCaptureContents(db, id, generation)
    assert.equal(result.kind, 'complete')
    assert.equal(await db.captureDraftContents.count(), 0)
    assert.equal(await db.captureCheckpoints.count(), 0)
  }))
test('boxed malformed state cannot masquerade as a valid empty admission', () =>
  fixture(async (db, call) => {
    const checkpoint = await db.captureCheckpoints.get(id)
    checkpoint.customer.state = new String('EMPTY')
    await db.captureCheckpoints.put(checkpoint)
    assert.equal((await call({ kind: 'save', ...cas, content: customer })).reason, 'invalid')
    assert.equal(await db.captureDraftContents.count(), 0)
  }))

test('same-scope explicit retirement removes PII and fences old callbacks without rearming protection', () =>
  fixture(async (db, call) => {
    await call({ kind: 'save', ...cas, content: customer })
    await call({ kind: 'protect', generation, channel: 'order', expectedRevision: 0, attemptId })
    assert.equal(typeof store.retireCaptureContents, 'function')
    const result = await store.retireCaptureContents(db, id, generation, attemptId)
    assert.equal(result.kind, 'retired')
    assert.equal(result.checkpoint.generation, attemptId)
    assert.equal(result.checkpoint.scopeKey, scopeKey)
    assert.equal(result.checkpoint.closed, false)
    assert.equal(result.checkpoint.customer.state, 'EMPTY')
    assert.equal(result.checkpoint.customer.revision, 2)
    assert.equal(result.checkpoint.order.state, 'PROTECTED')
    assert.equal(result.checkpoint.order.attemptId, attemptId)
    assert.equal(result.checkpoint.order.revision, 2)
    assert.equal(result.checkpoint.customer.contentStartedAt, null)
    assert.equal(await db.captureDraftContents.count(), 0)
    assert.equal(
      (await call({ kind: 'save', ...cas, expectedRevision: 1, content: customer })).kind,
      'refused',
    )
    assert.equal(
      (
        await call({
          kind: 'settle',
          generation,
          channel: 'order',
          expectedRevision: 1,
          attemptId,
          outcome: 'saved',
          content: null,
        })
      ).kind,
      'refused',
    )
    assert.ok(Object.isFrozen(result.checkpoint))
  }))
test('deletion-only retirement refuses missing mismatched corrupt or reused generation and never reopens closed', () =>
  fixture(async (db) => {
    assert.equal(typeof store.retireCaptureContents, 'function')
    assert.equal(
      (await store.retireCaptureContents(db, id, attemptId, crypto.randomUUID())).kind,
      'unavailable',
    )
    assert.equal(
      (await store.retireCaptureContents(db, id, generation, generation)).kind,
      'unavailable',
    )
    await store.purgeCaptureContents(db, id, generation)
    await db.captureCheckpoints.update(id, { 'order.state': 'UNAVAILABLE' })
    const result = await store.retireCaptureContents(db, id, generation, attemptId)
    assert.equal(result.kind, 'retired')
    assert.equal(result.checkpoint.closed, true)
    assert.equal(result.checkpoint.order.state, 'UNAVAILABLE')
    await db.captureCheckpoints.update(id, { format: 2 })
    assert.equal(
      (await store.retireCaptureContents(db, id, attemptId, crypto.randomUUID())).kind,
      'unavailable',
    )
    await db.captureCheckpoints.delete(id)
    assert.equal(
      (await store.retireCaptureContents(db, id, attemptId, crypto.randomUUID())).kind,
      'unavailable',
    )
  }))
test('retirement transaction failure cannot acknowledge content deletion or revision changes', () =>
  fixture(async (db, call) => {
    await call({ kind: 'save', ...cas, content: customer })
    assert.equal(typeof store.retireCaptureContents, 'function')
    db.captureDraftContents.hook('deleting', () => {
      throw Error('synthetic retirement failure')
    })
    assert.equal(
      (await store.retireCaptureContents(db, id, generation, attemptId)).kind,
      'unavailable',
    )
    assert.equal(await db.captureDraftContents.count(), 1)
    assert.equal((await db.captureCheckpoints.get(id)).generation, generation)
  }))

test('fresh enrollment atomically initializes healthy writer and binds checkpoint epoch', () =>
  fixture(async (db) => {
    const control = await db.deviceControl.get('device'),
      checkpoint = await db.captureCheckpoints.get(id)
    assert.equal(control.captureWriter?.format, 1)
    assert.equal(control.captureWriter?.coveredSequence, control.localSequence)
    assert.equal(checkpoint.writerEpoch, control.captureWriter?.epoch)
    assert.match(checkpoint.writerEpoch, /^[0-9a-f-]{36}$/)
  }))
test('legacy sequence gap refuses every checkpoint operation without returning private fields', () =>
  fixture(async (db, call) => {
    await call({ kind: 'save', ...cas, content: customer })
    await db.deviceControl.update('device', { localSequence: 1 })
    for (const command of [
      { kind: 'load' },
      { kind: 'save', ...cas, expectedRevision: 1, content: customer },
      { kind: 'protect', ...cas, expectedRevision: 1, attemptId },
      { kind: 'retireScope', generation, nextGeneration: attemptId },
    ]) {
      const result = await call(
        command,
        now,
        command.kind === 'retireScope' ? 'c'.repeat(64) : scopeKey,
      )
      assert.equal(result.kind, 'refused', command.kind)
      assert.equal('contents' in result, false)
    }
    assert.equal((await db.captureCheckpoints.get(id)).generation, generation)
  }))
test('healthy new writer epoch cannot revive prior checkpoint and deletion retirement preserves old epoch', () =>
  fixture(async (db, call) => {
    await call({ kind: 'save', ...cas, content: customer })
    const old = (await db.captureCheckpoints.get(id)).writerEpoch
    await db.deviceControl.update('device', {
      localSequence: 2,
      captureWriter: { format: 1, epoch: attemptId, coveredSequence: 2 },
    })
    assert.equal((await call({ kind: 'load' })).kind, 'refused')
    const retired = await store.retireCaptureContents(db, id, generation, attemptId)
    assert.equal(retired.kind, 'retired')
    assert.equal(retired.checkpoint.writerEpoch, old)
    assert.equal((await call({ kind: 'load' })).kind, 'refused')
  }))
test('rejected duplicate binding enrollment cannot repair unhealthy writer; new binding blank enrollment can', () =>
  fixture(async (db, call) => {
    await db.deviceControl.update('device', { localSequence: 4 })
    const prior = await db.deviceControl.get('device')
    assert.equal(
      (await call({ kind: 'enroll', checkpointId: attemptId, generation })).kind,
      'refused',
    )
    assert.deepEqual(await db.deviceControl.get('device'), prior)
    const fresh = await db.transaction(
      'rw',
      [db.deviceControl, db.captureCheckpoints, db.captureDraftContents],
      () =>
        store.applyCaptureCheckpoint(
          db,
          { kind: 'enroll', checkpointId: attemptId, generation, scope },
          'd'.repeat(64),
          scopeKey,
          now,
        ),
    )
    assert.equal(fresh.kind, 'ack')
    assert.equal(fresh.checkpoint.customer.state, 'EMPTY')
    assert.equal((await db.deviceControl.get('device')).captureWriter.coveredSequence, 4)
    assert.notEqual(fresh.checkpoint.writerEpoch, prior.captureWriter?.epoch)
    assert.equal((await call({ kind: 'load' })).kind, 'refused')
  }))
test('missing or malformed writer and missing checkpoint epoch never restore', () =>
  fixture(async (db, call) => {
    const prior = await db.deviceControl.get('device')
    for (const captureWriter of [
      undefined,
      { format: 1, epoch: attemptId, coveredSequence: 0, extra: true },
      { format: 1, epoch: 'bad', coveredSequence: 0 },
      { format: 1, epoch: attemptId, coveredSequence: -1 },
    ]) {
      await db.deviceControl.put({ ...prior, captureWriter })
      assert.equal((await call({ kind: 'load' })).kind, 'refused')
    }
    await db.deviceControl.put(prior)
    await db.captureCheckpoints.update(id, { writerEpoch: undefined })
    assert.equal((await call({ kind: 'load' })).kind, 'refused')
  }))
test('failed enrollment transaction rolls writer initialization back with checkpoint creation', () =>
  fixture(async (db) => {
    await db.deviceControl.update('device', { localSequence: 1 })
    const prior = await db.deviceControl.get('device')
    db.captureCheckpoints.hook('creating', () => {
      throw Error('synthetic checkpoint quota')
    })
    await assert.rejects(
      db.transaction('rw', [db.deviceControl, db.captureCheckpoints, db.captureDraftContents], () =>
        store.applyCaptureCheckpoint(
          db,
          { kind: 'enroll', checkpointId: attemptId, generation, scope },
          'd'.repeat(64),
          scopeKey,
          now,
        ),
      ),
      /synthetic checkpoint quota/,
    )
    assert.deepEqual(await db.deviceControl.get('device'), prior)
  }))

test('healthy same-epoch covered append preserves recovery; gap prevents pending settlement', () =>
  fixture(async (db, call) => {
    await call({ kind: 'save', ...cas, content: customer })
    const control = await db.deviceControl.get('device')
    await db.deviceControl.put({
      ...control,
      localSequence: 1,
      captureWriter: { ...control.captureWriter, coveredSequence: 1 },
    })
    assert.equal((await call({ kind: 'load' })).kind, 'loaded')
    await call({ kind: 'protect', ...cas, expectedRevision: 1, attemptId })
    await db.deviceControl.update('device', { localSequence: 2 })
    assert.equal(
      (
        await call({
          kind: 'settle',
          ...cas,
          expectedRevision: 2,
          attemptId,
          outcome: 'saved',
          content: null,
        })
      ).kind,
      'refused',
    )
    assert.equal((await db.captureCheckpoints.get(id)).customer.state, 'PROTECTED')
  }))
test('writer helpers reject unknown fields unsafe sequences and invalid epochs', async () => {
  const { writerEpoch, newCaptureWriter } =
    await import('../../.tmp-kernel/src/access-kernel/capture-checkpoint.js')
  const control = {
    localSequence: 2,
    captureWriter: { format: 1, epoch: attemptId, coveredSequence: 2 },
  }
  assert.equal(writerEpoch(control), attemptId)
  for (const invalid of [
    { ...control, localSequence: -1 },
    { ...control, localSequence: Number.MAX_SAFE_INTEGER + 1 },
    { ...control, captureWriter: { ...control.captureWriter, coveredSequence: 1 } },
    { ...control, captureWriter: { ...control.captureWriter, unexpected: true } },
    { ...control, captureWriter: { ...control.captureWriter, format: 2 } },
    { ...control, captureWriter: { ...control.captureWriter, epoch: 'not-uuid' } },
  ])
    assert.equal(writerEpoch(invalid), null)
  assert.deepEqual(newCaptureWriter({ localSequence: 3 }, attemptId), {
    format: 1,
    epoch: attemptId,
    coveredSequence: 3,
  })
  assert.throws(() => newCaptureWriter({ localSequence: NaN }, attemptId))
  assert.throws(() => newCaptureWriter({ localSequence: 3 }, 'not-uuid'))
})

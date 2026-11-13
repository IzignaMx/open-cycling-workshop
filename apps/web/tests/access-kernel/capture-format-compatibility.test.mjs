import 'fake-indexeddb/auto'
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createHash } from 'node:crypto'
import ts from 'typescript'
import { createKernelDatabase } from '../../.tmp-kernel/src/access-kernel/database.js'
import * as current from '../../.tmp-kernel/src/access-kernel/capture-checkpoint-store.js'
const fixtureRoot = new URL('../fixtures/capture-reader-cc18a203/', import.meta.url)
const provenance = JSON.parse(readFileSync(new URL('provenance.json', fixtureRoot), 'utf8'))
const oldModules = new Map()
function oldModule(file) {
  if (oldModules.has(file)) return oldModules.get(file)
  const source = readFileSync(new URL(file, fixtureRoot), 'utf8')
  assert.equal(createHash('sha256').update(source).digest('hex'), provenance.files[file])
  const module = { exports: {} }
  new Function(
    'require',
    'module',
    'exports',
    ts.transpileModule(source, {
      compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS },
    }).outputText,
  )((name) => oldModule(name.replace('./', '').replace('.js', '.ts')), module, module.exports)
  oldModules.set(file, module.exports)
  return module.exports
}
function refusal(value) {
  return { kind: value.kind, reason: value.reason }
}
const legacy = oldModule('capture-checkpoint-store.ts')
const id = '11111111-1111-4111-8111-111111111111',
  generation = '22222222-2222-4222-8222-222222222222',
  attempt = '33333333-3333-4333-8333-333333333333'
const binding = 'a'.repeat(64),
  scopeKey = 'b'.repeat(64),
  now = 1000,
  ttl = 86400000
const projection = {
  channel: 'order',
  draft: {
    customerId: 'customer',
    priority: 'normal',
    reportedProblem: 'Synthetic original',
    intakeCondition: 'Wet',
    accessories: 'Lamp',
    withBicycle: false,
    brand: '',
    model: '',
  },
  retainedSelection: { customerId: '', priority: 'normal' },
}
async function fixture(t) {
  const db = createKernelDatabase(`compat-${crypto.randomUUID()}`)
  await db.open()
  t.after(async () => {
    db.close()
    await db.delete()
  })
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
  const call = (command, at = now, impl = current) =>
    db.transaction('rw', [db.deviceControl, db.captureCheckpoints, db.captureDraftContents], () =>
      impl.applyCaptureCheckpoint(
        db,
        { checkpointId: id, scope: {}, ...command },
        binding,
        scopeKey,
        at,
      ),
    )
  assert.equal((await call({ kind: 'enroll', generation })).kind, 'ack')
  assert.equal(
    (
      await call({
        kind: 'save',
        generation,
        channel: 'order',
        expectedRevision: 0,
        content: projection,
      })
    ).kind,
    'ack',
  )
  const row = await db.captureDraftContents.get([id, 'order'])
  return { db, call, row }
}
async function future(f) {
  const row = {
    ...f.row,
    format: 2,
    draft: { ...f.row.draft, existingBicycleId: 'opaque-future-association' },
  }
  await f.db.captureDraftContents.put(row)
  return row
}
test('historical real reader refuses then deletes extended payload: explicit unsupported rollout counterexample', async (t) => {
  const f = await fixture(t)
  await future(f)
  assert.deepEqual(await f.call({ kind: 'load' }, now, legacy), {
    kind: 'refused',
    reason: 'invalid',
  })
  assert.deepEqual(await legacy.sweepExpiredCaptureContents(f.db, now), { kind: 'complete' })
  assert.equal(await f.db.captureDraftContents.get([id, 'order']), undefined)
  assert.equal((await f.db.captureCheckpoints.get(id)).order.state, 'UNAVAILABLE')
})
test('historical v8 actual database reopens v9 under installed Dexie', async (t) => {
  const f = await fixture(t)
  const name = f.db.name
  const newer = createKernelDatabase(name)
  newer.version(9).stores({})
  await newer.open()
  assert.equal(newer.backendDB().version, 90)
  newer.close()
  await f.db.open()
  assert.equal(f.db.backendDB().version, 90)
  assert.deepEqual(
    (await f.call({ kind: 'load' }, now, legacy)).contents.order.draft,
    projection.draft,
  )
})
test('compatibility reader preserves unsupported payload bytes and original metadata without restoring', async (t) => {
  const f = await fixture(t),
    row = await future(f),
    checkpoint = await f.db.captureCheckpoints.get(id)
  assert.deepEqual(await current.sweepExpiredCaptureContents(f.db, now + 10), { kind: 'complete' })
  assert.deepEqual(await f.db.captureDraftContents.get([id, 'order']), row)
  assert.deepEqual(await f.db.captureCheckpoints.get(id), checkpoint)
  const result = await f.call({ kind: 'load' })
  assert.deepEqual(result, { kind: 'refused', reason: 'unsupported_format', checkpoint })
  assert.equal(Object.isFrozen(result.checkpoint), true)
  assert.equal(Object.hasOwn(result, 'contents'), false)
  assert.equal(Object.hasOwn(result, 'draft'), false)
})
test('unsupported row refuses overwrite and protection without changing revisions or private bytes', async (t) => {
  const f = await fixture(t),
    row = await future(f),
    checkpoint = await f.db.captureCheckpoints.get(id)
  for (const command of [
    { kind: 'save', content: projection },
    { kind: 'protect', attemptId: attempt },
  ])
    assert.deepEqual(
      refusal(await f.call({ ...command, generation, channel: 'order', expectedRevision: 1 })),
      { kind: 'refused', reason: 'unsupported_format' },
    )
  assert.deepEqual(await f.db.captureDraftContents.get([id, 'order']), row)
  assert.deepEqual(await f.db.captureCheckpoints.get(id), checkpoint)
})
test('unsupported fixed envelope expires only at original absolute deadline', async (t) => {
  const f = await fixture(t)
  await future(f)
  await current.sweepExpiredCaptureContents(f.db, now + ttl - 1)
  assert.equal(await f.db.captureDraftContents.count(), 1)
  await current.sweepExpiredCaptureContents(f.db, now + ttl)
  assert.equal(await f.db.captureDraftContents.count(), 0)
  assert.equal((await f.db.captureCheckpoints.get(id)).order.state, 'EMPTY')
})
test('authorized exact-generation logout purges unsupported bytes while stale generation cannot', async (t) => {
  const f = await fixture(t),
    row = await future(f)
  await current.purgeCaptureContents(f.db, id, attempt)
  assert.deepEqual(await f.db.captureDraftContents.get([id, 'order']), row)
  assert.deepEqual(await current.purgeCaptureContents(f.db, id, generation), { kind: 'complete' })
  assert.equal(await f.db.captureDraftContents.count(), 0)
  assert.equal((await f.db.captureCheckpoints.get(id)).closed, true)
})
test('existing valid v1 writes and old reader roundtrip remain byte-equivalent', async (t) => {
  const f = await fixture(t)
  await current.sweepExpiredCaptureContents(f.db, now + 1)
  assert.deepEqual((await f.call({ kind: 'load' }, now + 1, legacy)).contents.order, f.row)
  assert.deepEqual(await f.db.captureDraftContents.get([id, 'order']), f.row)
})
test('unknown-payload clock rollback preserves bytes and reports unresolved maintenance', async (t) => {
  const f = await fixture(t),
    row = await future(f),
    checkpoint = await f.db.captureCheckpoints.get(id)
  assert.deepEqual(await current.sweepExpiredCaptureContents(f.db, now - 1), {
    kind: 'unavailable',
  })
  assert.deepEqual(await f.db.captureDraftContents.get([id, 'order']), row)
  assert.deepEqual(await f.db.captureCheckpoints.get(id), checkpoint)
})
test('unsupported classification never accepts corrupt current payload or unknown lifecycle metadata', async (t) => {
  const { preservableUnsupportedContent, validContent } =
    await import('../../.tmp-kernel/src/access-kernel/capture-checkpoint.js')
  const f = await fixture(t),
    row = await future(f)
  assert.equal(preservableUnsupportedContent(row), true)
  assert.equal(validContent(row), false)
  for (const invalid of [
    { ...row, format: 1 },
    { ...row, format: 0 },
    { ...row, format: 2.5 },
    { ...row, format: Number.MAX_SAFE_INTEGER + 1 },
    { ...row, extra: true },
    { ...row, generation: 'wrong' },
    { ...row, channel: 'unknown' },
    { ...row, revision: -1 },
    { ...row, expiresAt: row.expiresAt + 1 },
    { ...row, firstPersistedAt: Number.MAX_SAFE_INTEGER, expiresAt: Number.MAX_SAFE_INTEGER },
    { ...row, draft: { undefinedValue: undefined } },
    { ...row, draft: { huge: 'x'.repeat(65536) } },
  ])
    assert.equal(preservableUnsupportedContent(invalid), false)
  assert.equal(
    validContent({ ...f.row, draft: { ...f.row.draft, existingBicycleId: 'not-v1' } }),
    false,
  )
})
test('cleanup abort preserves unsupported content and checkpoint atomically', async (t) => {
  const f = await fixture(t),
    row = await future(f),
    checkpoint = await f.db.captureCheckpoints.get(id)
  const refuse = () => {
    throw Error('synthetic quota/storage failure')
  }
  f.db.captureDraftContents.hook('deleting', refuse)
  assert.deepEqual(await current.purgeCaptureContents(f.db, id, generation), {
    kind: 'unavailable',
  })
  assert.deepEqual(await f.db.captureDraftContents.get([id, 'order']), row)
  assert.deepEqual(await f.db.captureCheckpoints.get(id), checkpoint)
  f.db.captureDraftContents.hook('deleting').unsubscribe(refuse)
})
test('explicit discard removes unsupported content without rearming protected sibling', async (t) => {
  const f = await fixture(t)
  await future(f)
  await f.db.captureCheckpoints.update(id, {
    'customer.state': 'PROTECTED',
    'customer.attemptId': attempt,
  })
  const result = await current.retireCaptureContents(f.db, id, generation, attempt)
  assert.equal(result.kind, 'retired')
  assert.equal(await f.db.captureDraftContents.count(), 0)
  assert.equal(result.checkpoint.customer.state, 'PROTECTED')
  assert.equal(result.checkpoint.customer.attemptId, attempt)
})
test('unsupported payload cannot be settled or reenrolled around the capture fence', async (t) => {
  const f = await fixture(t),
    row = await future(f)
  assert.deepEqual(
    refusal(
      await f.call({
        kind: 'settle',
        generation,
        channel: 'order',
        expectedRevision: 1,
        attemptId: attempt,
        outcome: 'not_saved',
        content: projection,
      }),
    ),
    { kind: 'refused', reason: 'unsupported_format' },
  )
  assert.deepEqual(await f.call({ kind: 'enroll', generation: attempt }), {
    kind: 'refused',
    reason: 'conflict',
  })
  assert.deepEqual(await f.db.captureDraftContents.get([id, 'order']), row)
})
test('customer future payload gets the same exact-byte preservation and refusal as order', async (t) => {
  const f = await fixture(t)
  const content = { channel: 'customer', draft: { displayName: 'Synthetic', email: '', phone: '' } }
  await f.call({ kind: 'save', generation, channel: 'customer', expectedRevision: 0, content })
  const row = await f.db.captureDraftContents.get([id, 'customer'])
  const unknown = {
    ...row,
    format: 3,
    draft: { displayName: 'Synthetic', futureField: { opaque: 'value' } },
  }
  await f.db.captureDraftContents.put(unknown)
  await current.sweepExpiredCaptureContents(f.db, now + 1)
  assert.deepEqual(await f.db.captureDraftContents.get([id, 'customer']), unknown)
  assert.deepEqual(refusal(await f.call({ kind: 'load' }, now + 1)), {
    kind: 'refused',
    reason: 'unsupported_format',
  })
  assert.deepEqual(
    refusal(
      await f.call(
        { kind: 'save', generation, channel: 'customer', expectedRevision: 1, content },
        now + 1,
      ),
    ),
    { kind: 'refused', reason: 'unsupported_format' },
  )
})
for (const field of ['checkpointId', 'generation', 'revision', 'firstPersistedAt', 'expiresAt'])
  test(`future envelope cannot bypass checkpoint ${field} mismatch`, async (t) => {
    const f = await fixture(t),
      row = await future(f)
    if (field === 'checkpointId') {
      await f.db.captureDraftContents.delete([id, 'order'])
      row.checkpointId = attempt
      await f.db.captureDraftContents.put(row)
    } else if (field === 'generation')
      await f.db.captureCheckpoints.update(id, { generation: attempt })
    else if (field === 'revision') await f.db.captureCheckpoints.update(id, { 'order.revision': 2 })
    else
      await f.db.captureCheckpoints.update(id, {
        ['order.' + (field === 'firstPersistedAt' ? 'contentStartedAt' : 'contentExpiresAt')]:
          row[field] + 1,
      })
    const commandId = id
    const before = await f.db.captureCheckpoints.toArray()
    const result = await f.db.transaction(
      'rw',
      [f.db.deviceControl, f.db.captureCheckpoints, f.db.captureDraftContents],
      () =>
        current.applyCaptureCheckpoint(
          f.db,
          { kind: 'load', checkpointId: commandId, scope: {} },
          binding,
          scopeKey,
          now,
        ),
    )
    assert.equal(result.kind, 'refused')
    assert.notEqual(result.reason, 'unsupported_format')
    assert.deepEqual(await f.db.captureDraftContents.get([row.checkpointId, 'order']), row)
    assert.deepEqual(await f.db.captureCheckpoints.toArray(), before)
  })
test('concurrent explicit cleanup and v1 overwrite cannot revive an unsupported draft', async (t) => {
  const f = await fixture(t)
  await future(f)
  const [purged, saved] = await Promise.all([
    current.purgeCaptureContents(f.db, id, generation),
    f.call({
      kind: 'save',
      generation,
      channel: 'order',
      expectedRevision: 1,
      content: projection,
    }),
  ])
  assert.deepEqual(purged, { kind: 'complete' })
  assert.equal(saved.kind, 'refused')
  assert.ok(['closed', 'unsupported_format'].includes(saved.reason))
  assert.equal(await f.db.captureDraftContents.count(), 0)
  assert.equal((await f.db.captureCheckpoints.get(id)).closed, true)
})

for (const purportedFence of ['locked_owner', 'rotated_writer_epoch', 'new_reader_marker'])
  test(`historical maintenance ignores ${purportedFence}: not an offline reader exclusion fence`, async (t) => {
    const f = await fixture(t)
    const row = await future(f)
    const control = await f.db.deviceControl.get('device')
    if (purportedFence === 'locked_owner')
      await f.db.deviceControl.put({
        ...control,
        state: 'LOCKED',
        generation: control.generation + 1,
        activePartitionId: null,
        tabAttemptId: null,
      })
    else if (purportedFence === 'rotated_writer_epoch')
      await f.db.deviceControl.put({
        ...control,
        captureWriter: { ...control.captureWriter, epoch: attempt },
      })
    else
      // Synthetic marker tests only this historical reader's non-participation.
      // It is not a proposed production schema, attestation or release permission.
      await f.db.deviceControl.put({ ...control, minimumCaptureReader: 'synthetic-new-reader' })
    const fenced = await f.db.deviceControl.get('device')
    assert.deepEqual(await current.sweepExpiredCaptureContents(f.db, now), { kind: 'complete' })
    assert.deepEqual(await f.db.captureDraftContents.get([id, 'order']), row)
    if (purportedFence === 'rotated_writer_epoch')
      assert.deepEqual(await f.call({ kind: 'load' }, now, legacy), {
        kind: 'refused',
        reason: 'unavailable',
      })
    // No ticket, server, network or deviceControl table is passed to this exact old sweep.
    assert.deepEqual(await legacy.sweepExpiredCaptureContents(f.db, now), { kind: 'complete' })
    assert.equal(await f.db.captureDraftContents.get([id, 'order']), undefined)
    assert.equal((await f.db.captureCheckpoints.get(id)).order.state, 'UNAVAILABLE')
    assert.deepEqual(await f.db.deviceControl.get('device'), fenced)
  })

test('compatible reader use and v9 upgrade do not prevent subsequent historical v8 maintenance', async (t) => {
  const f = await fixture(t)
  const row = await future(f)
  assert.equal((await f.call({ kind: 'load' })).reason, 'unsupported_format')
  assert.deepEqual(await current.sweepExpiredCaptureContents(f.db, now), { kind: 'complete' })
  const upgraded = createKernelDatabase(f.db.name)
  upgraded.version(9).stores({})
  await upgraded.open()
  assert.equal(upgraded.backendDB().version, 90)
  assert.deepEqual(await upgraded.captureDraftContents.get([id, 'order']), row)
  upgraded.close()
  await f.db.open()
  assert.equal(f.db.backendDB().version, 90)
  assert.deepEqual(await legacy.sweepExpiredCaptureContents(f.db, now), { kind: 'complete' })
  assert.equal(await f.db.captureDraftContents.get([id, 'order']), undefined)
})

test('two database connections allow historical maintenance after compatible preservation', async (t) => {
  const f = await fixture(t)
  const row = await future(f)
  const oldConnection = createKernelDatabase(f.db.name)
  t.after(() => oldConnection.close())
  await oldConnection.open()
  assert.deepEqual(await current.sweepExpiredCaptureContents(f.db, now), { kind: 'complete' })
  assert.deepEqual(await oldConnection.captureDraftContents.get([id, 'order']), row)
  await legacy.sweepExpiredCaptureContents(oldConnection, now)
  assert.equal(await f.db.captureDraftContents.get([id, 'order']), undefined)
})

test('same-origin exact v1 remains readable across compatible to historical reopen', async (t) => {
  const f = await fixture(t)
  const before = await f.db.captureCheckpoints.get(id)
  assert.deepEqual((await f.call({ kind: 'load' })).contents.order, f.row)
  await current.sweepExpiredCaptureContents(f.db, now)
  f.db.close()
  await f.db.open()
  await legacy.sweepExpiredCaptureContents(f.db, now)
  assert.deepEqual((await f.call({ kind: 'load' }, now, legacy)).contents.order, f.row)
  assert.deepEqual(await f.db.captureCheckpoints.get(id), before)
})

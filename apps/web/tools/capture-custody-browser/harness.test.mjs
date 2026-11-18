import 'fake-indexeddb/auto'
import test from 'node:test'
import assert from 'node:assert/strict'

// Fake-IDB harness API controls only. They do not prove native origin isolation,
// page reload, quota behavior, process durability or authenticated admission.
const previousWindow = globalThis.window
globalThis.window = {}
await import('./main.js')
const harness = window.custodyHarness
const now = Date.parse('2026-11-17T12:00:00Z')
async function fixture(t) {
  const id = crypto.randomUUID()
  const descriptor = await harness.seedSource(`ocwp-synthetic-custody-source-${id}`, now)
  const name = `ocwp-synthetic-custody-target-${id}`
  await harness.initializeTarget(name)
  t.after(async () => {
    delete window.custodyTransport
    await harness.cleanup(descriptor, name)
  })
  const snapshot = await harness.snapshot(descriptor)
  assert.equal(snapshot.kind, 'snapshot')
  return { descriptor, name, bundle: snapshot.bundle }
}
test.after(() => {
  if (previousWindow === undefined) delete globalThis.window
  else globalThis.window = previousWindow
})
test('fake-IDB harness rejects non-synthetic database names without creating them', async () => {
  for (const name of [
    'ocwp',
    'ocwp-authenticated-v1',
    'arbitrary',
    'ocwp-synthetic-custody-target-test',
  ])
    await assert.rejects(harness.seedSource(name, now), /Synthetic source/)
  await assert.rejects(harness.initializeTarget('ocwp'), /Synthetic target/)
  await assert.rejects(
    harness.read('ocwp-synthetic-custody-target-absent', 'id', {}, now),
    /Existing synthetic custody/,
  )
  assert.equal((await indexedDB.databases()).length, 0)
})
test('fake-IDB harness uses actual kernel v1 rows and refuses reseeding either side', async (t) => {
  const { descriptor, name, bundle } = await fixture(t)
  assert.equal(bundle.contents.length, 2)
  assert.deepEqual(
    bundle.contents.map((row) => row.format),
    [1, 1],
  )
  assert.equal(bundle.contents[0].draft.displayName, '  Synthetic\n\t二 ')
  await assert.rejects(harness.seedSource(descriptor.name, now), /Never reseed/)
  await assert.rejects(harness.initializeTarget(name), /Never reseed/)
  assert.deepEqual(await harness.targetStores(name), ['custody'])
  const source = JSON.parse(await harness.sourceBytes(descriptor))
  for (const table of ['operationJournal', 'operationDelivery', 'operationEvents'])
    assert.deepEqual(source[table], [])
})
test('fake-IDB actual coordinator transport observes unchanged then edited source, never operational use', async (t) => {
  const { descriptor, name, bundle } = await fixture(t)
  const before = await harness.sourceBytes(descriptor)
  let edit = false
  window.custodyTransport = async (candidate) => {
    const result = await harness.stage(name, 'transfer', candidate, descriptor.owner, now)
    if (edit)
      assert.equal((await harness.editSource(descriptor, 'Later synthetic edit')).kind, 'ack')
    return result
  }
  assert.deepEqual(await harness.run(descriptor), {
    kind: 'custody_retained',
    observation: 'source_unchanged_at_check',
    operationalUse: 'forbidden',
  })
  assert.equal(await harness.sourceBytes(descriptor), before)
  const retained = await harness.targetBytes(name)
  edit = true
  assert.deepEqual(await harness.run(descriptor), {
    kind: 'custody_retained',
    observation: 'source_changed',
    operationalUse: 'forbidden',
  })
  assert.notEqual(await harness.sourceBytes(descriptor), before)
  assert.equal(await harness.targetBytes(name), retained)
  assert.deepEqual(await harness.read(name, 'transfer', descriptor.owner, now + 1000), {
    kind: 'custody',
    bundle,
  })
  const changed = await harness.snapshot(descriptor)
  assert.deepEqual(
    changed.bundle.contents.map((row) => [row.firstPersistedAt, row.expiresAt]),
    bundle.contents.map((row) => [row.firstPersistedAt, row.expiresAt]),
  )
})
test('fake-IDB harness preserves source and prevents owner, collision and corrupt read exposure', async (t) => {
  const { descriptor, name, bundle } = await fixture(t)
  const before = await harness.sourceBytes(descriptor)
  const wrongOwner = { ...descriptor.owner, userId: 'synthetic-other' }
  assert.deepEqual(
    await harness.snapshot({
      ...descriptor,
      ticket: { ...descriptor.ticket, tabAttemptId: 'other' },
    }),
    { kind: 'refused', reason: 'authority' },
  )
  assert.deepEqual(await harness.stage(name, 'id', bundle, wrongOwner, now), {
    kind: 'refused',
    reason: 'invalid',
  })
  assert.equal(await harness.targetBytes(name), '[]')
  assert.deepEqual(await harness.stage(name, 'id', bundle, descriptor.owner, now), {
    kind: 'staged',
  })
  const retained = await harness.targetBytes(name)
  const changed = structuredClone(bundle)
  changed.contents[0].draft.displayName = 'Changed synthetic bytes'
  assert.deepEqual(await harness.stage(name, 'id', changed, descriptor.owner, now), {
    kind: 'refused',
    reason: 'conflict',
  })
  assert.deepEqual(await harness.read(name, 'id', wrongOwner, now), {
    kind: 'refused',
    reason: 'unavailable',
  })
  assert.equal(await harness.targetBytes(name), retained)
  await harness.corrupt(name, 'id')
  const corrupted = await harness.targetBytes(name)
  assert.deepEqual(await harness.read(name, 'id', descriptor.owner, now), {
    kind: 'refused',
    reason: 'unavailable',
  })
  assert.equal(await harness.targetBytes(name), corrupted)
  assert.equal(await harness.sourceBytes(descriptor), before)
})
test('fake-IDB harness refuses nested stage and read before outer abort with zero retained rows', async (t) => {
  const { descriptor, name, bundle } = await fixture(t)
  for (const mode of ['stage', 'read']) {
    assert.deepEqual(
      await harness.outerAbort(name, `outer-${mode}`, bundle, descriptor.owner, now, mode),
      { result: { kind: 'refused', reason: 'nested_transaction' }, aborted: true, rows: 0 },
    )
    assert.equal(await harness.targetBytes(name), '[]')
  }
})

test('fresh editor requires its own verified kernel session and fences the prior ticket', async (t) => {
  const { descriptor, name, bundle } = await fixture(t)
  await import(`./main.js?editor=${crypto.randomUUID()}`)
  const editor = window.custodyHarness
  window.custodyHarness = harness
  const before = await harness.sourceBytes(descriptor)
  await assert.rejects(editor.editSource(descriptor, 'Unverified edit'), /Session fenced/)
  assert.equal(await harness.sourceBytes(descriptor), before)
  window.custodyTransport = async (candidate) => {
    const staged = await harness.stage(name, 'editor-transfer', candidate, descriptor.owner, now)
    const admitted = await editor.verifyEditor(descriptor)
    assert.notDeepEqual(admitted.ticket, descriptor.ticket)
    assert.deepEqual(admitted.scope, descriptor.scope)
    assert.equal((await editor.editSource(admitted, 'Verified editor edit')).kind, 'ack')
    const changed = await editor.snapshot(admitted)
    assert.equal(changed.kind, 'snapshot')
    assert.equal(changed.bundle.contents[0].draft.displayName, 'Verified editor edit')
    assert.deepEqual(
      changed.bundle.contents.map((r) => [r.firstPersistedAt, r.expiresAt]),
      bundle.contents.map((r) => [r.firstPersistedAt, r.expiresAt]),
    )
    await assert.rejects(harness.editSource(descriptor, 'Stale edit'), /fenced/)
    return staged
  }
  assert.deepEqual(await harness.run(descriptor), {
    kind: 'custody_retained',
    observation: 'unavailable',
    operationalUse: 'forbidden',
  })
  assert.deepEqual(await harness.snapshot(descriptor), { kind: 'refused', reason: 'authority' })
  assert.deepEqual(await harness.read(name, 'editor-transfer', descriptor.owner, now), {
    kind: 'custody',
    bundle,
  })
  // Close the extra connection before the fixture deletes its synthetic database.
  await editor.releaseSource(descriptor)
})

test('diagnostic harness uses actual module and real kernel pending/inflight/applied states', async (t) => {
  const { descriptor } = await fixture(t)
  const initial = await harness.observeWork(descriptor)
  assert.equal(initial.kind, 'observation')
  assert.equal(initial.receipt.counts.unsent, 2)
  await harness.createSyntheticPending(descriptor)
  const pending = await harness.observeWork(descriptor)
  assert.equal(pending.receipt.counts.unresolvedOperations, 1)
  assert.ok(pending.receipt.actions.includes('review_sync_at_source'))
  assert.equal(await harness.claimSyntheticPending(descriptor), 1)
  const unknown = await harness.observeWork(descriptor)
  assert.ok(unknown.receipt.actions.includes('check_unknown_outcome_at_source'))
  await harness.acknowledgeSyntheticApplied(descriptor)
  const before = await harness.sourceBytes(descriptor),
    applied = await harness.observeWork(descriptor)
  assert.equal(applied.receipt.counts.appliedHistory, 1)
  assert.equal(applied.receipt.counts.unresolvedOperations, 0)
  assert.equal(await harness.sourceBytes(descriptor), before)
  assert.deepEqual(await harness.recheckWork(descriptor, initial.observationId), {
    kind: 'changed',
    activation: 'not_assessed',
  })
  const nearExpiry = await harness.advanceSyntheticClock(
    descriptor,
    descriptor.now + 86400000 - 500,
  )
  const renewed = await harness.verifyEditor(nearExpiry)
  const anchor = await harness.observeWork(renewed)
  const later = await harness.advanceSyntheticClock(renewed, descriptor.now + 86400000 + 500)
  const beforeExpiryRead = await harness.sourceBytes(later)
  assert.equal((await harness.observeWork(later)).receipt.counts.expired, 2)
  assert.deepEqual(await harness.recheckWork(later, anchor.observationId), {
    kind: 'changed',
    activation: 'not_assessed',
  })
  assert.equal(await harness.sourceBytes(later), beforeExpiryRead)
  await assert.rejects(
    harness.acknowledgeSyntheticApplied(descriptor),
    /Synthetic dispatch required/,
  )
})

test('diagnostic handles are scoped to their database and lost on release', async (t) => {
  const a = await fixture(t),
    b = await fixture(t)
  const observed = await harness.observeWork(a.descriptor)
  assert.deepEqual(await harness.recheckWork(b.descriptor, observed.observationId), {
    kind: 'refused',
    reason: 'witness',
  })
  await assert.rejects(
    harness.advanceSyntheticClock(a.descriptor, now - 1),
    /Monotonic synthetic clock/,
  )
  await harness.releaseSource(a.descriptor)
  assert.deepEqual(await harness.recheckWork(a.descriptor, observed.observationId), {
    kind: 'refused',
    reason: 'witness',
  })
  await assert.rejects(harness.createSyntheticPending(a.descriptor), /Session fenced/)
})

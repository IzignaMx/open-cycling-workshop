import test from 'node:test'
import assert from 'node:assert/strict'
import {
  setup,
  context,
  completedBaseline,
  NOW,
  command,
} from '../../tests/access-kernel/client-fixture.mjs'
import { observeSource, recheckObservation } from './diagnostic.mjs'
async function fixture(t) {
  const { db, kernel } = await setup(t)
  const value = context()
  const ticket = await completedBaseline(db, kernel, value)
  await kernel.rememberSession(ticket, 'binding-A')
  const scope = {
    ...value.principal,
    selectedLocationId: value.selectedLocationId,
    datasetIncarnation: value.datasetIncarnation,
    authorizationEpoch: value.authorizationEpoch,
    policyRevision: value.policyRevision,
    capabilities: value.capabilities,
    sessionBindingId: 'binding-A',
  }
  const checkpointId = crypto.randomUUID(),
    generation = crypto.randomUUID()
  await kernel.checkpointCapture(ticket, { kind: 'enroll', checkpointId, generation, scope })
  await kernel.checkpointCapture(ticket, {
    kind: 'save',
    checkpointId,
    generation,
    scope,
    channel: 'customer',
    expectedRevision: 0,
    content: {
      channel: 'customer',
      draft: { displayName: ' Private\n', email: '', phone: ' 123 ' },
    },
  })
  return {
    db,
    kernel,
    options: { db, ticket, scope, checkpointId, now: NOW, isCurrent: () => true },
  }
}
async function bytes(db) {
  return JSON.stringify(await Promise.all(db.tables.map((table) => table.toArray())))
}

test('dated minimal observation preserves bytes and never authorizes migration', async (t) => {
  const { db, options } = await fixture(t)
  const before = await bytes(db)
  const result = await observeSource(options)
  assert.equal(result.kind, 'observation')
  assert.equal(result.receipt.observedAt, NOW)
  assert.deepEqual(result.receipt.actions, ['finish_capture_at_source'])
  assert.equal(result.receipt.activation, 'not_assessed')
  assert.equal(result.receipt.migration, 'forbidden')
  assert.equal(JSON.stringify(result).includes('Private'), false)
  assert.equal(JSON.stringify(result).includes('binding-A'), false)
  assert.equal(await bytes(db), before)
  assert.deepEqual(await recheckObservation(options, result.witness), {
    kind: 'unchanged_at_check',
    activation: 'not_assessed',
  })
})
test('new local work invalidates observation without exposing command payload', async (t) => {
  const { db, kernel, options } = await fixture(t)
  const observed = await observeSource(options)
  await kernel.commitLocalCommand(options.ticket, command())
  const before = await bytes(db)
  const next = await observeSource(options)
  assert.equal(next.kind, 'observation')
  assert.ok(next.receipt.actions.includes('review_sync_at_source'))
  assert.deepEqual(await recheckObservation(options, observed.witness), {
    kind: 'changed',
    activation: 'not_assessed',
  })
  assert.equal(await bytes(db), before)
})
test('revocation, stale owner and nested transaction refuse without receipts', async (t) => {
  const { db, options } = await fixture(t)
  for (const invalid of [
    { ...options, isCurrent: () => false },
    { ...options, ticket: { ...options.ticket, deviceGeneration: 999 } },
  ])
    assert.deepEqual(await observeSource(invalid), { kind: 'refused', reason: 'authority' })
  assert.deepEqual(await db.transaction('r', db.tables, () => observeSource(options)), {
    kind: 'refused',
    reason: 'nested_transaction',
  })
})

test('applied history remains retained and is not unresolved work or an instruction to purge', async (t) => {
  const { db, kernel, options } = await fixture(t)
  await kernel.commitLocalCommand(options.ticket, command())
  const batch = await kernel.listDispatchable(options.ticket, 10)
  await kernel.applyPushResult(options.ticket, batch, {
    results: [
      {
        mutation_id: 'operation-A',
        entity_id: 'customer-shared',
        status: 'applied',
        entity_version: 1,
      },
    ],
  })
  const before = await bytes(db),
    result = await observeSource(options)
  assert.equal(result.kind, 'observation')
  assert.equal(result.receipt.counts.appliedHistory, 1)
  assert.equal(result.receipt.counts.unresolvedOperations, 0)
  assert.ok(result.receipt.actions.includes('retain_applied_history'))
  assert.equal(await bytes(db), before)
})
for (const state of [
  'inflight',
  'awaiting_confirmation',
  'retryable',
  'held_authorization',
  'held_dependency',
  'held_integrity',
  'held_retry',
  'held_recovery',
  'rejected',
])
  test(`retained ${state} work suggests only existing source review`, async (t) => {
    const { db, kernel, options } = await fixture(t)
    await kernel.commitLocalCommand(options.ticket, command())
    await db.operationDelivery.update('operation-A', { state })
    const before = await bytes(db),
      r = await observeSource(options)
    assert.equal(r.kind, 'observation')
    assert.equal(r.receipt.counts.unresolvedOperations, 1)
    assert.ok(
      r.receipt.actions.includes(
        ['inflight', 'awaiting_confirmation'].includes(state)
          ? 'check_unknown_outcome_at_source'
          : 'review_sync_at_source',
      ),
    )
    assert.equal(await bytes(db), before)
  })
test('protected capture requires receipt review, never another submission', async (t) => {
  const { db, kernel, options } = await fixture(t),
    cp = await db.captureCheckpoints.get(options.checkpointId)
  assert.equal(
    (
      await kernel.checkpointCapture(options.ticket, {
        kind: 'protect',
        checkpointId: cp.checkpointId,
        generation: cp.generation,
        scope: options.scope,
        channel: 'customer',
        expectedRevision: cp.customer.revision,
        attemptId: crypto.randomUUID(),
      })
    ).kind,
    'ack',
  )
  const r = await observeSource(options)
  assert.equal(r.receipt.counts.protected, 1)
  assert.deepEqual(r.receipt.actions, ['check_capture_receipt_at_source'])
})
for (const mutation of [
  'missing_delivery',
  'foreign_delivery',
  'unknown_state',
  'orphan_event',
  'bad_applied_result',
  'foreign_scope',
  'bad_revision',
  'unsupported',
  'expired',
])
  test(`diagnoses or refuses ${mutation} without changing bytes`, async (t) => {
    const { db, kernel, options } = await fixture(t)
    await kernel.commitLocalCommand(options.ticket, command())
    if (mutation === 'missing_delivery') await db.operationDelivery.delete('operation-A')
    if (mutation === 'foreign_delivery')
      await db.operationDelivery.update('operation-A', { entityId: 'other' })
    if (mutation === 'unknown_state')
      await db.operationDelivery.update('operation-A', { state: 'future' })
    if (mutation === 'orphan_event')
      await db.operationEvents.add({ mutationId: 'orphan', kind: 'local' })
    if (mutation === 'bad_applied_result')
      await db.operationDelivery.update('operation-A', { state: 'applied', result: null })
    if (mutation === 'foreign_scope') options.scope = { ...options.scope, userId: 'other' }
    const key = [options.checkpointId, 'customer']
    if (mutation === 'bad_revision') await db.captureDraftContents.update(key, { revision: 999 })
    if (mutation === 'unsupported') await db.captureDraftContents.update(key, { format: 2 })
    if (mutation === 'expired') {
      const start = NOW - 86400000,
        cp = await db.captureCheckpoints.get(options.checkpointId)
      await db.captureDraftContents.update(key, { firstPersistedAt: start, expiresAt: NOW })
      await db.captureCheckpoints.update(cp.checkpointId, {
        customer: { ...cp.customer, contentStartedAt: start, contentExpiresAt: NOW },
      })
    }
    const before = await bytes(db),
      r = await observeSource(options)
    if (['unsupported', 'expired'].includes(mutation)) {
      assert.equal(r.kind, 'observation')
      assert.equal(r.receipt.counts[mutation], 1)
    } else assert.equal(r.kind, 'refused')
    assert.equal(await bytes(db), before)
  })
test('bounded read refuses overflow rather than reporting truncated absence', async (t) => {
  const { db, options } = await fixture(t),
    cp = await db.captureCheckpoints.get(options.checkpointId)
  for (let i = 0; i < 32; i++)
    await db.captureCheckpoints.add({
      ...cp,
      checkpointId: crypto.randomUUID(),
      bindingKey: i.toString(16).padStart(64, '0'),
    })
  assert.deepEqual(await observeSource(options), { kind: 'refused', reason: 'capacity' })
})
test('revocation during digest and recheck clock rollback cannot emit observation', async (t) => {
  const { options } = await fixture(t),
    r = await observeSource(options)
  let calls = 0
  assert.deepEqual(await observeSource({ ...options, isCurrent: () => ++calls === 1 }), {
    kind: 'refused',
    reason: 'authority',
  })
  assert.deepEqual(await recheckObservation({ ...options, now: NOW - 1 }, r.witness), {
    kind: 'refused',
    reason: 'witness',
  })
  assert.deepEqual(await recheckObservation(options, {}), { kind: 'refused', reason: 'witness' })
})

test('empty source has no actions but is never migration ready', async (t) => {
  const { db, kernel } = await setup(t),
    value = context(),
    ticket = await completedBaseline(db, kernel, value)
  await kernel.rememberSession(ticket, 'binding-A')
  const scope = {
    ...value.principal,
    selectedLocationId: value.selectedLocationId,
    datasetIncarnation: value.datasetIncarnation,
    authorizationEpoch: value.authorizationEpoch,
    policyRevision: value.policyRevision,
    capabilities: value.capabilities,
    sessionBindingId: 'binding-A',
  }
  const r = await observeSource({ db, ticket, scope, now: NOW, isCurrent: () => true })
  assert.equal(r.kind, 'observation')
  assert.deepEqual(r.receipt.actions, [])
  assert.equal(r.receipt.migration, 'forbidden')
  assert.equal(r.receipt.activation, 'not_assessed')
})
for (const field of [
  'sessionBindingId',
  'datasetIncarnation',
  'authorizationEpoch',
  'selectedLocationId',
  'capabilities',
])
  test(`different ${field} refuses the entire scoped observation`, async (t) => {
    const { options } = await fixture(t)
    const scope = { ...options.scope, [field]: field === 'capabilities' ? [] : 'other' }
    assert.deepEqual(await observeSource({ ...options, scope }), {
      kind: 'refused',
      reason: 'authority',
    })
  })
test('UNAVAILABLE capture is recovery-only and has no draft reconstruction', async (t) => {
  const { db, options } = await fixture(t),
    cp = await db.captureCheckpoints.get(options.checkpointId)
  await db.captureDraftContents.delete([cp.checkpointId, 'customer'])
  await db.captureCheckpoints.update(cp.checkpointId, {
    customer: { ...cp.customer, state: 'UNAVAILABLE' },
  })
  const r = await observeSource(options)
  assert.equal(r.kind, 'observation')
  assert.equal(r.receipt.counts.unavailable, 1)
  assert.deepEqual(r.receipt.actions, ['review_recovery_at_source'])
})
test('same-authority edit after receipt invalidates only observation, never changes source', async (t) => {
  const { db, kernel, options } = await fixture(t),
    r = await observeSource(options),
    cp = await db.captureCheckpoints.get(options.checkpointId)
  await kernel.checkpointCapture(options.ticket, {
    kind: 'save',
    checkpointId: cp.checkpointId,
    generation: cp.generation,
    scope: options.scope,
    channel: 'customer',
    expectedRevision: cp.customer.revision,
    content: { channel: 'customer', draft: { displayName: 'Later private', email: '', phone: '' } },
  })
  const before = await bytes(db)
  assert.deepEqual(await recheckObservation(options, r.witness), {
    kind: 'changed',
    activation: 'not_assessed',
  })
  assert.equal(await bytes(db), before)
  assert.equal(JSON.stringify(r).includes('Later private'), false)
})

test('expiry between observations changes diagnosis even without a storage write', async (t) => {
  const { db, options } = await fixture(t),
    cp = await db.captureCheckpoints.get(options.checkpointId)
  const expires = NOW + 500,
    start = expires - 86400000
  await db.captureDraftContents.update([cp.checkpointId, 'customer'], {
    firstPersistedAt: start,
    expiresAt: expires,
  })
  await db.captureCheckpoints.update(cp.checkpointId, {
    customer: { ...cp.customer, contentStartedAt: start, contentExpiresAt: expires },
  })
  const r = await observeSource(options),
    before = await bytes(db)
  assert.deepEqual(await recheckObservation({ ...options, now: NOW + 1000 }, r.witness), {
    kind: 'changed',
    activation: 'not_assessed',
  })
  assert.equal(await bytes(db), before)
})

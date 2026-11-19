import assert from 'node:assert/strict'
import test from 'node:test'
import {
  buildReceipt,
  phaseDuration,
} from '../../.tmp-reception-measurement/reception-measurement.js'

const uuid = (n) => `00000000-0000-7000-8000-${String(n).padStart(12, '0')}`
const metadata = {
  browserVersion: '156.0.0.0',
  appSha256: 'a'.repeat(64),
  swSha256: 'b'.repeat(64),
  datasetBefore: { customers: 1, bicycles: 0, orders: 0 },
  datasetAfter: { customers: 1, bicycles: 3, orders: 3 },
}
const make = (trial, start, multiplier = 1) => ({
  trial,
  status: 'passed',
  phases: {
    draftDurable: phaseDuration(start, start + multiplier),
    reloadRecovered: phaseDuration(start + 10, start + 10 + multiplier * 2),
    localCommit: phaseDuration(start + 20, start + 20 + multiplier * 3),
    serverConfirmed: phaseDuration(start + 20, start + 20 + multiplier * 4),
  },
  identities: {
    orderId: uuid(trial * 10 + 1),
    bicycleId: uuid(trial * 10 + 2),
    orderMutationId: uuid(trial * 10 + 3),
    bicycleMutationId: uuid(trial * 10 + 4),
  },
})

test('reports all three trips with observational min/max, no readiness inference', () => {
  const samples = [make(1, 0), make(2, 50, 2), make(3, 100)]
  const receipt = buildReceipt(samples, metadata)
  assert.equal(receipt.readiness, 'not_assessed')
  assert.equal(receipt.outcome, 'complete')
  assert.equal(receipt.benchmark, 'actual_app_synthetic_connected_loopback')
  assert.deepEqual(receipt.counts, {
    planned: 3,
    attempted: 3,
    passed: 3,
    failed: 0,
    not_attempted: 0,
  })
  assert.deepEqual(receipt.samples, samples)
  assert.deepEqual(receipt.summary, {
    draftDurable: { minMs: 1, maxMs: 2 },
    reloadRecovered: { minMs: 2, maxMs: 4 },
    localCommit: { minMs: 3, maxMs: 6 },
    serverConfirmed: { minMs: 4, maxMs: 8 },
  })
})

test('preserves failed partial phases but excludes their durations; the remaining trial is unattempted', () => {
  const passed = make(1, 0)
  const failed = {
    trial: 2,
    status: 'failed',
    reason: 'reloadRecovered',
    phases: { draftDurable: phaseDuration(50, 51.5) },
  }
  const receipt = buildReceipt([passed, failed], { ...metadata, datasetAfter: null })
  assert.deepEqual(receipt.samples, [passed, failed])
  assert.deepEqual(receipt.counts, {
    planned: 3,
    attempted: 2,
    passed: 1,
    failed: 1,
    not_attempted: 1,
  })
  assert.deepEqual(receipt.summary.draftDurable, { minMs: 1, maxMs: 1 })
  const failedOnly = buildReceipt([{ ...failed, trial: 1 }], { ...metadata, datasetAfter: null })
  assert.equal(failedOnly.summary, null)
})

test('excludes a late failed attempt even with all phases observed', () => {
  const complete = make(1, 0)
  const failed = { ...complete, status: 'failed', reason: 'verification' }
  assert.equal(buildReceipt([failed], { ...metadata, datasetAfter: null }).summary, null)
})

test('rejects invalid and fabricated duration observations', () => {
  for (const pair of [
    [1, 0],
    [-1, 0],
    [0, Infinity],
    [NaN, 2],
  ])
    assert.throws(() => phaseDuration(...pair))
  const sample = make(1, 0)
  sample.phases.localCommit.durationMs = 0.01
  assert.throws(() => buildReceipt([sample], metadata))
})

test('rejects missing, out-of-order or incoherently overlapping phases', () => {
  const missing = make(1, 0)
  delete missing.phases.reloadRecovered
  assert.throws(() => buildReceipt([missing], metadata))
  const nonShared = make(1, 0)
  nonShared.phases.serverConfirmed = phaseDuration(21, 24)
  assert.throws(() => buildReceipt([nonShared], metadata))
  const inverted = make(1, 0)
  inverted.phases.serverConfirmed = phaseDuration(20, 21)
  assert.throws(() => buildReceipt([inverted], metadata))
  const chronological = make(1, 0)
  chronological.phases.reloadRecovered = phaseDuration(0, 8)
  assert.throws(() => buildReceipt([chronological], metadata))
})

test('rejects duplicate identities, malformed IDs, and out-of-order attempts', () => {
  const first = make(1, 0)
  const second = make(2, 50)
  second.identities.bicycleMutationId = first.identities.orderMutationId
  assert.throws(() => buildReceipt([first, second], metadata))
  const badId = make(1, 0)
  badId.identities.orderId = 'unexpected'
  assert.throws(() => buildReceipt([badId], metadata))
  assert.throws(() => buildReceipt([make(2, 50)], metadata))
  assert.throws(() => buildReceipt([first, make(2, 5)], metadata))
  assert.throws(() =>
    buildReceipt(
      [1, 2, 3, 4].map((trial) => make(trial, trial * 50)),
      metadata,
    ),
  )
})

test('fails closed on unsanitized free-form fields instead of copying them into a receipt', () => {
  assert.throws(() => buildReceipt([], { ...metadata, secret: 'unapproved' }))
  assert.throws(() => buildReceipt([], { ...metadata, browserVersion: '156.0 bearer secret' }))
  assert.throws(() => buildReceipt([], { ...metadata, appSha256: 'unapproved' }))
  assert.throws(() =>
    buildReceipt(
      [{ trial: 1, phases: {}, status: 'failed', reason: 'arbitrary detail' }],
      metadata,
    ),
  )
  assert.throws(() => buildReceipt([{ ...make(1, 0), payload: 'unapproved' }], metadata))
})

test('keeps partial failed identity evidence even when a duplicate made the trial fail', () => {
  const passed = make(1, 0)
  const failed = {
    trial: 2,
    status: 'failed',
    reason: 'localCommit',
    phases: { draftDurable: phaseDuration(50, 51) },
    identities: { orderId: passed.identities.orderId },
  }
  const receipt = buildReceipt([passed, failed], { ...metadata, datasetAfter: null })
  assert.deepEqual(receipt.samples[1], failed)
  assert.equal(receipt.counts.passed, 1)
})

test('distinguishes failed and incomplete receipts and refuses missing final dataset after three passes', () => {
  assert.equal(
    buildReceipt([make(1, 0)], { ...metadata, datasetAfter: null }).outcome,
    'incomplete',
  )
  assert.equal(
    buildReceipt([{ trial: 1, status: 'failed', reason: 'verification', phases: {} }], {
      ...metadata,
      datasetAfter: null,
    }).outcome,
    'failed',
  )
  assert.throws(
    () =>
      buildReceipt([make(1, 0), make(2, 50), make(3, 100)], { ...metadata, datasetAfter: null }),
    /final reception dataset/,
  )
})

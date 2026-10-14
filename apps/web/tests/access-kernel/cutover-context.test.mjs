import 'fake-indexeddb/auto'
import test from 'node:test'
import assert from 'node:assert/strict'
import { convertServerContext } from '../../.tmp-kernel/src/access-kernel/server-context.js'
import { contextKey, validateVerifiedContext } from '../../.tmp-kernel/src/access-kernel/context.js'
import {
  validateBaselineMetadata,
  completedBaseline,
} from '../../.tmp-kernel/src/access-kernel/baseline-state.js'
import { validateBaselineResponse } from '../../.tmp-kernel/src/access-kernel/baseline-wire.js'
import { AccessKernel } from '../../.tmp-kernel/src/access-kernel/kernel.js'
import { createKernelDatabase } from '../../.tmp-kernel/src/access-kernel/database.js'
import { completedMetadata } from './baseline-fixture.mjs'

const now = Date.parse('2026-10-14T10:00:00Z')
const incarnation = '0199ba00-0000-7000-8000-000000000001'
const restored = '0199ba00-0000-7000-8000-000000000002'
const identity = {
  apiRealm: 'https://example.test/api/v1',
  organizationId: 'org',
  userId: 'A',
  selectedLocationId: 'loc',
  deviceGeneration: 1,
  tabAttemptId: 'tab',
  sessionHandle: 'session',
}
const verified = (overrides = {}) => ({
  protocol: 1,
  principal: { apiRealm: identity.apiRealm, organizationId: 'org', userId: 'A' },
  accountLocationId: 'loc',
  selectedLocationId: 'loc',
  capabilities: ['customers.read', 'sync.pull'],
  authorizationEpoch: 'a'.repeat(43),
  policyRevision: 'ocwp-access-baseline-2',
  datasetIncarnation: incarnation,
  verifiedAt: new Date(now).toISOString(),
  offlineUntil: new Date(now + 3600000).toISOString(),
  snapshotProtocol: 'baseline-v1',
  ...overrides,
})
const wire = (context = verified()) => ({
  protocol: 1,
  principal: { api_realm: null, organization_id: 'org', user_id: 'A' },
  account_location_id: 'loc',
  selected_location_id: 'loc',
  capabilities: [...context.capabilities],
  authorization_epoch: context.authorizationEpoch,
  policy_revision: context.policyRevision,
  dataset_incarnation: context.datasetIncarnation,
  verified_at: context.verifiedAt,
  offline_until: context.offlineUntil,
  snapshot_protocol: context.snapshotProtocol,
})
function proof(context = verified()) {
  const ticket = {
    deviceGeneration: 1,
    tabAttemptId: 'tab',
    partitionId: 'partition',
    principalKey: JSON.stringify([identity.apiRealm, 'org', 'A']),
    authorizationEpoch: context.authorizationEpoch,
  }
  const baseline = completedMetadata(ticket, context, 'checkpoint')
  // Explicit provenance belongs to local completion/continuation evidence; no wire fields are synthesized.
  baseline.datasetIncarnation = context.datasetIncarnation
  return {
    partitionId: 'partition',
    principalKey: ticket.principalKey,
    locationId: 'loc',
    authorizationEpoch: context.authorizationEpoch,
    policyRevision: context.policyRevision,
    status: 'active',
    baselineComplete: true,
    cursor: 'checkpoint',
    baseline,
  }
}
test('B closed context accepts genuine supported and null advertisements with explicit provenance', () => {
  for (const snapshotProtocol of [null, 'baseline-v1']) {
    const expected = verified({ snapshotProtocol })
    assert.deepEqual(convertServerContext(wire(expected), identity, now), expected)
  }
})
test('B wire rejects missing, malformed and noncanonical incarnation, old policy and unsupported protocol', () => {
  for (const dataset of [
    undefined,
    null,
    '',
    1,
    incarnation.toUpperCase(),
    'not-a-uuid',
    ` ${incarnation}`,
  ]) {
    const body = wire()
    if (dataset === undefined) delete body.dataset_incarnation
    else body.dataset_incarnation = dataset
    assert.throws(() => convertServerContext(body, identity, now))
  }
  for (const policy_revision of ['ocwp-access-baseline-1', 'future', '', null])
    assert.throws(() => convertServerContext({ ...wire(), policy_revision }, identity, now))
  for (const snapshot_protocol of [undefined, 'baseline-v2', 1, false])
    assert.throws(() => convertServerContext({ ...wire(), snapshot_protocol }, identity, now))
})
test('B persisted context rejects unknown provenance and unknown policy without coercion', () => {
  for (const datasetIncarnation of [undefined, null, '', incarnation.toUpperCase(), 'not-a-uuid'])
    assert.throws(() => validateVerifiedContext(verified({ datasetIncarnation }), now))
  for (const policyRevision of ['ocwp-access-baseline-1', 'future', null])
    assert.throws(() => validateVerifiedContext(verified({ policyRevision }), now))
})
test('B context binding separates incarnation and effective advertisement even with repeated epoch', () => {
  assert.notEqual(contextKey(verified()), contextKey(verified({ datasetIncarnation: restored })))
  assert.notEqual(contextKey(verified()), contextKey(verified({ snapshotProtocol: null })))
})
test('B nested start and activation contexts bind explicit incarnation and policy', () => {
  const context = verified(),
    partition = proof(context)
  const baselineId = partition.baseline.baselineId
  const binding = { context, identity, baselineId, checkpoint: 'checkpoint' }
  const start = {
    protocol: 1,
    baseline_id: baselineId,
    context: wire(context),
    continuation: 'first',
    expires_at: '2026-10-14T10:30:00Z',
  }
  const activation = {
    protocol: 1,
    baseline_id: baselineId,
    authorization_epoch: context.authorizationEpoch,
    checkpoint: 'checkpoint',
    context: wire(context),
  }
  for (const [kind, response] of [
    ['start', start],
    ['activation', activation],
  ]) {
    assert.deepEqual(validateBaselineResponse(kind, response, binding, now), response)
    for (const value of [restored, undefined]) {
      const invalid = structuredClone(response)
      if (value === undefined) delete invalid.context.dataset_incarnation
      else invalid.context.dataset_incarnation = value
      assert.throws(() => validateBaselineResponse(kind, invalid, binding, now))
    }
  }
})
test('B completion proof requires explicit matching incarnation and never infers historical provenance', () => {
  const context = verified(),
    partition = proof(context)
  assert.equal(completedBaseline(partition, context), true)
  for (const datasetIncarnation of [undefined, restored, incarnation.toUpperCase()]) {
    const original = structuredClone(partition)
    if (datasetIncarnation === undefined) delete original.baseline.datasetIncarnation
    else original.baseline.datasetIncarnation = datasetIncarnation
    const before = structuredClone(original)
    assert.equal(completedBaseline(original, context), false)
    assert.deepEqual(original, before)
  }
  assert.equal(completedBaseline(partition, verified({ datasetIncarnation: restored })), false)
})
test('B historical context evidence uses the same strict closed contract as live responses', () => {
  for (const mutate of [
    (v) => delete v.dataset_incarnation,
    (v) => {
      v.dataset_incarnation = restored
    },
    (v) => {
      v.policy_revision = 'ocwp-access-baseline-1'
    },
    (v) => {
      v.authorization_epoch = 'short'
    },
    (v) => {
      v.unrecognized = true
    },
    (v) => {
      v.verified_at = '2026-10-14T11:00:00+01:00'
    },
  ]) {
    const context = verified(),
      partition = proof(context)
    const response = JSON.parse(partition.baseline.startResponse)
    mutate(response.context)
    partition.baseline.startResponse = JSON.stringify(response)
    assert.throws(() => validateBaselineMetadata(partition, context))
  }
})
test('B incarnation rotation refuses completed partition reuse while preserving old evidence', async (t) => {
  const db = createKernelDatabase(`cutover-context-${crypto.randomUUID()}`)
  await db.open()
  t.after(async () => {
    db.close()
    await db.delete()
  })
  const kernel = new AccessKernel(db, { now: () => now, newId: () => crypto.randomUUID() })
  const context = verified()
  const first = await kernel.acceptVerifiedContext(await kernel.beginVerification('first'), context)
  const baseline = completedMetadata(first.ticket, context, 'checkpoint')
  baseline.datasetIncarnation = context.datasetIncarnation
  await db.cachePartitions.update(first.ticket.partitionId, {
    baseline,
    status: 'active',
    baselineComplete: true,
    cursor: 'checkpoint',
  })
  const same = await kernel.acceptVerifiedContext(await kernel.beginVerification('renew'), context)
  assert.equal(same.state, 'READY')
  assert.equal(same.ticket.partitionId, first.ticket.partitionId)
  const before = await db.accessContexts.get(first.ticket.partitionId)
  const next = await kernel.acceptVerifiedContext(
    await kernel.beginVerification('restored'),
    verified({ datasetIncarnation: restored }),
  )
  assert.equal(next.state, 'BASELINE_REQUIRED')
  assert.notEqual(next.ticket.partitionId, first.ticket.partitionId)
  assert.deepEqual(await db.accessContexts.get(first.ticket.partitionId), before)
  // Increment C rebinds only the active owner on equivalent verification; immutable
  // origin and initial start/completion evidence remain unchanged through rotation.
  assert.deepEqual((await db.cachePartitions.get(first.ticket.partitionId)).baseline, {
    ...baseline,
    owner: same.ticket,
  })
})

test('B rejects internally consistent historical completion with unknown provenance or old policy', () => {
  for (const mode of ['missing-incarnation', 'old-policy', 'malformed-epoch']) {
    const context = verified()
    if (mode === 'old-policy') context.policyRevision = 'ocwp-access-baseline-1'
    if (mode === 'malformed-epoch') context.authorizationEpoch = 'historical-short-epoch'
    const partition = proof(context)
    if (mode === 'missing-incarnation') {
      delete context.datasetIncarnation
      delete partition.baseline.datasetIncarnation
      const original = JSON.parse(partition.baseline.startResponse)
      delete original.context.dataset_incarnation
      partition.baseline.startResponse = JSON.stringify(original)
      partition.baseline.binding = contextKey(context)
    }
    assert.equal(completedBaseline(partition, context), false, mode)
  }
})

import { createServerContextAdapter } from '../../.tmp-kernel/src/access-kernel/server-context.js'
import { createBaselineTransport } from '../../.tmp-kernel/src/access-kernel/baseline-transport.js'
import { createBaselineCoordinator } from '../../.tmp-kernel/src/access-kernel/baseline-coordinator.js'

test('B supported DTO fixtures traverse real isolated adapters and persist the complete incarnation-bound proof', async (t) => {
  const db = createKernelDatabase(`cutover-adapters-${crypto.randomUUID()}`)
  await db.open()
  t.after(async () => {
    db.close()
    await db.delete()
  })
  const kernel = new AccessKernel(db, { now: () => now, newId: () => crypto.randomUUID() })
  const attempt = await kernel.beginVerification('adapter-chain')
  const captured = { ...identity, ...attempt }
  const baselineId = '0199ba00-0000-7000-8000-000000000003'
  const context = verified()
  const calls = []
  const fetch = async (url, init) => {
    const pathname = new URL(url).pathname
    const path = pathname.includes('/deltas/') ? 'delta' : pathname.split('/').at(-1)
    calls.push(path)
    assert.equal(new Headers(init.headers).get('authorization'), 'Bearer synthetic-test-token')
    const common = {
      protocol: 1,
      baseline_id: baselineId,
      authorization_epoch: context.authorizationEpoch,
    }
    const responses = {
      context: wire(context),
      start: {
        protocol: 1,
        baseline_id: baselineId,
        context: wire(context),
        continuation: 'scan-0',
        expires_at: '2026-10-14T10:30:00Z',
      },
      page: {
        ...common,
        predecessor: 'scan-0',
        continuation: 'finalize-0',
        page_id: 'scan-page',
        records: [],
        phase: 'scan_complete',
      },
      finalize: { ...common, predecessor: 'finalize-0', continuation: 'delta-0' },
      delta: {
        ...common,
        predecessor: 'delta-0',
        continuation: 'checkpoint',
        page_id: 'delta-page',
        records: [],
        phase: 'complete',
        completion: {
          baseline_id: baselineId,
          authorization_epoch: context.authorizationEpoch,
          checkpoint: 'checkpoint',
        },
      },
      'validate-activation': { ...common, checkpoint: 'checkpoint', context: wire(context) },
    }
    assert.ok(Object.hasOwn(responses, path), path)
    const response = new Response(JSON.stringify(responses[path]), {
      headers: { 'content-type': 'application/json', 'cache-control': 'no-store' },
    })
    Object.defineProperty(response, 'url', { value: url })
    return response
  }
  const adapter = createServerContextAdapter({ apiRealm: identity.apiRealm, fetch, now: () => now })
  const result = await adapter.verify({
    identity: captured,
    bearerToken: 'synthetic-test-token',
    isCurrent: () => true,
  })
  const accepted = await kernel.acceptVerifiedContext(attempt, result.context)
  assert.equal(accepted.state, 'BASELINE_REQUIRED')
  const transport = createBaselineTransport({ apiRealm: identity.apiRealm, fetch, now: () => now })
  const coordinator = createBaselineCoordinator({
    kernel,
    transport,
    now: () => now,
    random: () => 0,
    online: () => true,
  })
  const session = {
    ticket: accepted.ticket,
    context: result.context,
    identity: captured,
    bearerToken: 'synthetic-test-token',
    isCurrent: () => true,
  }
  let outcome = await coordinator.start(session)
  assert.equal(outcome.state, 'PROGRESSED')
  session.ticket = outcome.ticket
  for (let i = 0; i < 3; i++) {
    outcome = await coordinator.step(session)
    assert.equal(outcome.state, 'PROGRESSED')
  }
  outcome = await coordinator.step(session)
  assert.equal(outcome.state, 'READY')
  const partition = await db.cachePartitions.get(outcome.ticket.partitionId)
  assert.equal(partition.baseline.datasetIncarnation, incarnation)
  assert.equal(completedBaseline(partition, result.context), true)
  assert.deepEqual(calls, ['context', 'start', 'page', 'finalize', 'delta', 'validate-activation'])
  assert.equal(
    (await db.accessContexts.get(outcome.ticket.partitionId)).context.datasetIncarnation,
    incarnation,
  )
  assert.equal(await db.operationJournal.count(), 0)
})

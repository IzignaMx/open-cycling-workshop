import 'fake-indexeddb/auto'
import test from 'node:test'
import assert from 'node:assert/strict'
import { BrandingSnapshotRepository } from '../../.tmp-branding/src/branding/cache.js'
import { createKernelDatabase } from '../../.tmp-branding/src/access-kernel/database.js'
import { principalKey } from '../../.tmp-branding/src/access-kernel/context.js'
import { NOW, INCARNATION, profile, withLogo } from './fixture.mjs'
const context = (overrides = {}) => ({
  protocol: 1,
  principal: { apiRealm: 'https://example.test/api/v1', organizationId: 'org', userId: 'A' },
  selectedLocationId: 'loc',
  accountLocationId: 'loc',
  capabilities: ['branding.read'],
  authorizationEpoch: 'A'.repeat(43),
  policyRevision: 'ocwp-access-baseline-2',
  datasetIncarnation: INCARNATION,
  verifiedAt: new Date(NOW).toISOString(),
  offlineUntil: new Date(NOW + 3600000).toISOString(),
  snapshotProtocol: 'baseline-v1',
  ...overrides,
})
async function fixture(t, ctx = context()) {
  const db = createKernelDatabase('branding-cache-' + crypto.randomUUID())
  await db.open()
  t.after(async () => {
    db.close()
    await db.delete()
  })
  const ticket = {
    partitionId: 'partition',
    principalKey: principalKey(ctx.principal),
    authorizationEpoch: ctx.authorizationEpoch,
    tabAttemptId: 'tab',
    deviceGeneration: 1,
  }
  const control = {
    key: 'device',
    generation: 1,
    tabAttemptId: 'tab',
    activePartitionId: 'partition',
    state: 'READY',
    localSequence: 0,
    observedAt: NOW,
    dispatchAttemptId: null,
    dispatchScanAfter: 0,
  }
  const partition = {
    partitionId: 'partition',
    principalKey: ticket.principalKey,
    locationId: 'loc',
    authorizationEpoch: ctx.authorizationEpoch,
    policyRevision: ctx.policyRevision,
    status: 'active',
    baselineComplete: true,
    cursor: 'qualified-by-kernel',
  }
  await db.deviceControl.put(control)
  await db.accessContexts.put({ partitionId: ticket.partitionId, context: ctx })
  await db.cachePartitions.put(partition)
  return { db, ctx, ticket, control, partition, repo: new BrandingSnapshotRepository(db) }
}
test('only admitted READY stores a complete profile; OFFLINE_READY same-lease reload reads new owner', async (t) => {
  const { repo, db, ticket, ctx, control } = await fixture(t)
  assert.equal(await repo.write(ticket, ctx, withLogo(), NOW), true)
  assert.deepEqual(await repo.read(ticket, ctx, NOW), withLogo())
  const reload = { ...ticket, deviceGeneration: 2, tabAttemptId: 'reloaded' }
  await db.deviceControl.put({
    ...control,
    state: 'OFFLINE_READY',
    generation: 2,
    tabAttemptId: 'reloaded',
  })
  assert.deepEqual(await repo.read(reload, ctx, NOW), withLogo())
  assert.equal(await repo.read(ticket, ctx, NOW), null)
  assert.equal(await repo.write(reload, ctx, profile({ version: 2 }), NOW), false)
  assert.equal(await db.operationJournal.count(), 0)
})
test('held, locked, expired, clock rollback and absent literal read cannot expose snapshots', async (t) => {
  const { repo, db, ticket, ctx, control } = await fixture(t)
  await repo.write(ticket, ctx, withLogo(), NOW)
  for (const state of [
    'LOCKED',
    'VERIFYING',
    'BASELINE_REQUIRED',
    'SNAPSHOTTING',
    'CATCHING_UP',
    'HELD',
  ]) {
    await db.deviceControl.put({ ...control, state })
    assert.equal(await repo.read(ticket, ctx, NOW), null)
    assert.equal(await repo.write(ticket, ctx, profile({ version: 2 }), NOW), false)
  }
  await db.deviceControl.put(control)
  assert.equal(await repo.read(ticket, ctx, NOW + 3600000), null)
  assert.equal(await repo.read(ticket, ctx, NOW - 1), null)
  for (const capabilities of [[], ['*'], ['branding.write']]) {
    const denied = { ...ctx, capabilities }
    await db.accessContexts.put({ partitionId: ticket.partitionId, context: denied })
    assert.equal(await repo.read(ticket, denied, NOW), null)
    assert.equal(await repo.write(ticket, denied, profile(), NOW), false)
  }
})
test('repeated snapshot scope and exact stored/current context are required', async (t) => {
  const { repo, db, ticket, ctx } = await fixture(t)
  await repo.write(ticket, ctx, profile(), NOW)
  const snapshot = await db.brandingSnapshots.get(ticket.partitionId)
  for (const key of [
    'apiRealm',
    'organizationId',
    'userId',
    'locationId',
    'authorizationEpoch',
    'policyRevision',
    'datasetIncarnation',
    'principalKey',
    'verifiedAt',
    'offlineUntil',
  ]) {
    await db.brandingSnapshots.put({ ...snapshot, [key]: 'other' })
    assert.equal(await repo.read(ticket, ctx, NOW), null, key)
  }
  await db.brandingSnapshots.put(snapshot)
  for (const changed of [
    { ...ctx, principal: { ...ctx.principal, userId: 'B' } },
    { ...ctx, principal: { ...ctx.principal, organizationId: 'other' } },
    { ...ctx, selectedLocationId: 'other', accountLocationId: 'other' },
    { ...ctx, authorizationEpoch: 'B'.repeat(43) },
    { ...ctx, datasetIncarnation: '0199ba00-0000-7000-8000-000000000002' },
    { ...ctx, offlineUntil: new Date(NOW + 7200000).toISOString() },
  ])
    assert.equal(await repo.read(ticket, changed, NOW), null)
  for (const changed of [
    profile({ organization_id: 'other' }),
    profile({ location_id: 'other' }),
    profile({ dataset_incarnation: '0199ba00-0000-7000-8000-000000000002' }),
  ])
    assert.equal(await repo.write(ticket, ctx, changed, NOW), false)
})
test('atomic monotonic versions and immutable same-version content allow explicit unavailable transitions', async (t) => {
  const { repo, db, ticket, ctx } = await fixture(t)
  await Promise.all([
    repo.write(ticket, ctx, profile({ version: 7 }), NOW),
    repo.write(ticket, ctx, profile({ version: 5 }), NOW),
  ])
  assert.equal((await repo.read(ticket, ctx, NOW)).version, 7)
  assert.equal(await repo.write(ticket, ctx, profile({ version: 6 }), NOW), false)
  assert.equal(
    await repo.write(
      ticket,
      ctx,
      profile({ version: 7, display_name: 'Conflicting same version' }),
      NOW,
    ),
    false,
  )
  await repo.write(ticket, ctx, withLogo({ version: 8 }), NOW)
  const unavailable = withLogo({
    version: 8,
    logo_state: 'unavailable',
    logo_diagnostic: 'asset_unavailable',
    logo: { ...withLogo().logo, png_base64: null },
  })
  assert.equal(await repo.write(ticket, ctx, unavailable, NOW), true)
  assert.equal((await repo.read(ticket, ctx, NOW)).logo.png_base64, null)
  assert.equal(await db.brandingSnapshots.count(), 1)
})
test('takeover during asynchronous digest fences read and write without changing unrelated data', async (t) => {
  const { repo, db, ticket, ctx, control } = await fixture(t)
  await repo.write(ticket, ctx, withLogo(), NOW)
  const original = { mutationId: 'keep', unknown: ['immutable', null] }
  await db.operationJournal.add(original)
  const oldDigest = crypto.subtle.digest.bind(crypto.subtle)
  let release, started
  const gate = new Promise((resolve) => {
    release = resolve
  })
  const entered = new Promise((resolve) => {
    started = resolve
  })
  crypto.subtle.digest = async (...args) => {
    started()
    await gate
    return oldDigest(...args)
  }
  try {
    const pending = repo.read(ticket, ctx, NOW)
    await entered
    await db.deviceControl.put({ ...control, generation: 2, tabAttemptId: 'takeover' })
    release()
    assert.equal(await pending, null)
    assert.equal(await repo.write(ticket, ctx, withLogo({ version: 2 }), NOW), false)
    assert.deepEqual(await db.operationJournal.get('keep'), original)
  } finally {
    crypto.subtle.digest = oldDigest
  }
})
test('quota failure rejects atomically and never evicts journal, receipts or personal preferences', async (t) => {
  const { repo, db, ticket, ctx } = await fixture(t)
  const row = { mutationId: 'original', unknown: true }
  await db.operationJournal.add(row)
  await db.operationDelivery.add(row)
  await db.presentationPreferences.add({ key: 'personal', value: 'retained' })
  db.brandingSnapshots.hook('creating', () => {
    throw new DOMException('full', 'QuotaExceededError')
  })
  await assert.rejects(repo.write(ticket, ctx, profile(), NOW), /full/)
  assert.deepEqual(await db.operationJournal.get('original'), row)
  assert.deepEqual(await db.operationDelivery.get('original'), row)
  assert.equal((await db.presentationPreferences.get('personal')).value, 'retained')
  assert.equal(await db.brandingSnapshots.count(), 0)
})

test('renewed admission must fetch again, then atomically updates the lease without lowering the version', async (t) => {
  const { repo, db, ticket, ctx } = await fixture(t)
  await repo.write(ticket, ctx, profile({ version: 4 }), NOW)
  const renewed = {
    ...ctx,
    verifiedAt: new Date(NOW + 1000).toISOString(),
    offlineUntil: new Date(NOW + 7200000).toISOString(),
  }
  await db.accessContexts.put({ partitionId: ticket.partitionId, context: renewed })
  assert.equal(await repo.read(ticket, renewed, NOW + 1000), null)
  assert.equal(await repo.write(ticket, renewed, profile({ version: 3 }), NOW + 1000), false)
  assert.equal(await repo.write(ticket, renewed, profile({ version: 4 }), NOW + 1000), true)
  assert.equal((await repo.read(ticket, renewed, NOW + 1000)).version, 4)
})

test('lease expiration while SHA validation waits cannot expose or persist late bytes', async (t) => {
  const short = context({ offlineUntil: new Date(NOW + 1000).toISOString() })
  const { repo, db, ticket, ctx } = await fixture(t, short)
  await repo.write(ticket, ctx, withLogo(), NOW)
  const oldDigest = crypto.subtle.digest.bind(crypto.subtle)
  const oldNow = performance.now.bind(performance)
  let elapsed = 0
  performance.now = () => elapsed
  crypto.subtle.digest = async (...args) => {
    elapsed = 1001
    return oldDigest(...args)
  }
  try {
    assert.equal(await repo.read(ticket, ctx, NOW), null)
    elapsed = 0
    assert.equal(await repo.write(ticket, ctx, withLogo({ version: 2 }), NOW), false)
    assert.equal((await db.brandingSnapshots.get(ticket.partitionId)).version, 1)
  } finally {
    crypto.subtle.digest = oldDigest
    performance.now = oldNow
  }
})

test('cache corruption is a visible persistence error and does not authorize or erase data', async (t) => {
  const { repo, db, ticket, ctx } = await fixture(t)
  await repo.write(ticket, ctx, profile(), NOW)
  const snapshot = await db.brandingSnapshots.get(ticket.partitionId)
  const corrupt = { ...snapshot, organizationId: 'other' }
  await db.brandingSnapshots.put(corrupt)
  assert.equal(await repo.read(ticket, ctx, NOW), null)
  await assert.rejects(repo.write(ticket, ctx, profile({ version: 2 }), NOW), /provenance invalid/)
  assert.deepEqual(await db.brandingSnapshots.get(ticket.partitionId), corrupt)
})

test('kernel-issued remembered admission permits offline cache reload without inferring an owner', async (t) => {
  const { setup, completedBaseline } = await import('../access-kernel/client-fixture.mjs')
  const { AccessKernel } = await import('../../.tmp-kernel/src/access-kernel/kernel.js')
  const { db, kernel } = await setup(t)
  const ctx = context()
  const ticket = await completedBaseline(db, kernel, ctx)
  const repo = new BrandingSnapshotRepository(db)
  assert.equal(await repo.write(ticket, ctx, withLogo(), NOW), true)
  const admission = await kernel.rememberSession(ticket, 'session-branding-binding')
  const reloaded = new AccessKernel(db, { now: () => NOW, newId: () => crypto.randomUUID() })
  const offline = await reloaded.resumeOffline(admission, 'reloaded-tab')
  assert.deepEqual(await repo.read(offline.ticket, offline.context, NOW), withLogo())
  assert.equal(await repo.read(ticket, ctx, NOW), null)
  assert.equal(
    await repo.write(offline.ticket, offline.context, withLogo({ version: 2 }), NOW),
    false,
  )
})

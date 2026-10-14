import 'fake-indexeddb/auto'
import { completedMetadata } from './baseline-fixture.mjs'
import assert from 'node:assert/strict'
import { createKernelDatabase } from '../../.tmp-kernel/src/access-kernel/database.js'
import { AccessKernel } from '../../.tmp-kernel/src/access-kernel/kernel.js'

export const NOW = Date.parse('2026-10-14T10:00:00.000Z')
export function context(userId = 'A', overrides = {}) {
  return {
    protocol: 1,
    principal: { apiRealm: 'https://workshop.example/api/v1', organizationId: 'org', userId },
    accountLocationId: 'loc',
    selectedLocationId: 'loc',
    capabilities: ['customers.read', 'customers.write', 'sync.push'],
    authorizationEpoch: `${userId}-epoch`.padEnd(43, '_'),
    policyRevision: 'ocwp-access-baseline-2',
    datasetIncarnation: '0199ba00-0000-7000-8000-000000000001',
    verifiedAt: new Date(NOW).toISOString(),
    offlineUntil: new Date(NOW + 3_600_000).toISOString(),
    snapshotProtocol: 'baseline-v1',
    ...overrides,
  }
}
export function command(id = 'operation-A', entityId = 'customer-shared') {
  return {
    envelope: {
      mutation_id: id,
      entity_type: 'customer',
      entity_id: entityId,
      operation: 'create',
      organization_id: 'org',
      location_id: 'loc',
      base_version: null,
      occurred_at: new Date(NOW).toISOString(),
      payload: { display_name: 'Private A', unknown: { retained: true } },
    },
    optimistic: {
      customer_id: entityId,
      organization_id: 'org',
      location_id: 'loc',
      version: 1,
      display_name: 'Private A',
    },
    dependsOn: [],
    localEvents: [{ action: 'local-evidence', detail: { retained: true } }],
  }
}
export async function setup(t) {
  const db = createKernelDatabase(`kernel-test-${crypto.randomUUID()}`)
  let now = NOW
  const kernel = new AccessKernel(db, { now: () => now, newId: () => crypto.randomUUID() })
  t.after(async () => {
    db.close()
    await db.delete()
  })
  await db.open()
  return {
    db,
    kernel,
    setNow(value) {
      now = value
    },
  }
}
export async function verified(kernel, value = context()) {
  const attempt = await kernel.beginVerification(crypto.randomUUID())
  return kernel.acceptVerifiedContext(attempt, value)
}
// Synthetic supported-protocol completion proof for kernel unit tests only.
// Actual supported-server negotiation is qualified separately.
export async function completedBaseline(db, kernel, value = context()) {
  const initial = await verified(kernel, value)
  await db.cachePartitions.update(initial.ticket.partitionId, {
    baselineComplete: true,
    status: 'active',
    cursor: 'opaque-fixture-checkpoint',
    baseline: completedMetadata(initial.ticket, value, 'opaque-fixture-checkpoint'),
  })
  const accepted = await verified(kernel, value)
  assert.equal(accepted.state, 'READY')
  return accepted.ticket
}

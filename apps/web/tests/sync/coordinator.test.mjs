import test from 'node:test'
import assert from 'node:assert/strict'
import { webcrypto } from 'node:crypto'

if (!globalThis.crypto) globalThis.crypto = webcrypto

import { SyncCoordinator } from '../../.tmp-sync/src/sync/coordinator.js'

class FakeStore {
  constructor() {
    this.pending = []
    this.cursor = 0
    this.acked = []
    this.applied = []
    this.conflicts = []
  }

  async listPending() {
    return [...this.pending]
  }

  async markAcknowledged(ids) {
    this.acked.push(...ids)
    this.pending = this.pending.filter((item) => !ids.includes(item.mutation_id))
  }

  async recordConflicts(results) {
    this.conflicts.push(...results)
    const ids = results.map((item) => item.mutation_id)
    this.pending = this.pending.filter((item) => !ids.includes(item.mutation_id))
  }

  async getCursor() {
    return this.cursor
  }

  async mergeAndAdvance(items, nextCursor) {
    this.applied.push(...items)
    this.cursor = nextCursor
  }
}

class FakeTransport {
  constructor() {
    this.pushCalls = []
    this.pullCalls = []
    this.page = { items: [], next_cursor: 0, has_more: false }
  }

  async push(mutations) {
    this.pushCalls.push(mutations)
    return {
      results: mutations.map((item) => ({
        mutation_id: item.mutation_id,
        status: 'applied',
        entity_id: item.entity_id,
        entity_version: 1,
      })),
    }
  }

  async pull(cursor, locationId) {
    this.pullCalls.push({ cursor, locationId })
    return this.page
  }
}

test('offline run performs no transport I/O', async () => {
  const store = new FakeStore()
  const transport = new FakeTransport()
  const coordinator = new SyncCoordinator({ store, transport, locationId: 'loc-1' })

  const result = await coordinator.runOnce({ online: false })

  assert.equal(result.status, 'offline')
  assert.equal(transport.pushCalls.length, 0)
  assert.equal(transport.pullCalls.length, 0)
})

test('online run pushes pending mutations before pulling changes', async () => {
  const store = new FakeStore()
  const transport = new FakeTransport()
  store.pending.push({
    mutation_id: 'mutation-1',
    entity_type: 'customer',
    entity_id: 'customer-1',
    operation: 'create',
    organization_id: 'org-1',
    location_id: 'loc-1',
    base_version: null,
    occurred_at: '2026-08-07T00:00:00Z',
    payload: { display_name: 'Ana' },
  })
  transport.page = {
    items: [{ cursor: 7, entity_type: 'customer', entity_id: 'customer-2' }],
    next_cursor: 7,
    has_more: false,
  }
  const coordinator = new SyncCoordinator({ store, transport, locationId: 'loc-1' })

  const result = await coordinator.runOnce({ online: true })

  assert.equal(result.status, 'synced')
  assert.deepEqual(store.acked, ['mutation-1'])
  assert.equal(store.cursor, 7)
  assert.equal(store.applied.length, 1)
  assert.deepEqual(transport.pullCalls, [{ cursor: 0, locationId: 'loc-1' }])
})

test('failed merge does not get hidden as a successful sync', async () => {
  const store = new FakeStore()
  store.mergeAndAdvance = async () => {
    throw new Error('local merge failed')
  }
  const transport = new FakeTransport()
  transport.page = {
    items: [{ cursor: 8, entity_type: 'customer', entity_id: 'customer-2' }],
    next_cursor: 8,
    has_more: false,
  }
  const coordinator = new SyncCoordinator({ store, transport, locationId: 'loc-1' })

  await assert.rejects(() => coordinator.runOnce({ online: true }), /local merge failed/)
  assert.equal(store.cursor, 0)
})

test('uuidv7 client ids are canonical, unique, and lexically monotonic', async () => {
  const { newUuidV7 } = await import('../../.tmp-sync/src/shared/ids.js')
  const values = Array.from({ length: 25 }, () => newUuidV7())
  assert.equal(new Set(values).size, values.length)
  assert.deepEqual(values, [...values].sort())
  assert.ok(values.every((value) => value[14] === '7'))
})


test('permanent push conflicts move out of the retry queue and into conflict center', async () => {
  const store = new FakeStore()
  const transport = new FakeTransport()
  store.pending.push({
    mutation_id: 'mutation-conflict',
    entity_type: 'customer',
    entity_id: 'customer-1',
    operation: 'update',
    organization_id: 'org-1',
    location_id: 'loc-1',
    base_version: 0,
    occurred_at: '2026-08-07T00:00:00Z',
    payload: { display_name: 'Stale' },
  })
  transport.push = async (mutations) => ({
    results: mutations.map((item) => ({
      mutation_id: item.mutation_id,
      status: 'conflict',
      entity_id: item.entity_id,
      entity_version: null,
      error_code: 'sync_conflict',
      error_message: 'base version is stale',
    })),
  })
  const coordinator = new SyncCoordinator({ store, transport, locationId: 'loc-1' })

  const result = await coordinator.runOnce({ online: true })

  assert.equal(result.conflicts, 1)
  assert.equal(store.conflicts.length, 1)
  assert.equal(store.pending.length, 0)
  assert.equal(store.acked.length, 0)
})

test('sync scope keys isolate organization and location cursors', async () => {
  const { syncScopeKey, buildScopedConflict } = await import('../../.tmp-sync/src/sync/scope.js')

  assert.equal(syncScopeKey('org-1', 'loc-1'), 'org-1::loc-1')
  assert.notEqual(syncScopeKey('org-1', 'loc-1'), syncScopeKey('org-2', 'loc-1'))
  assert.notEqual(syncScopeKey('org-1', 'loc-1'), syncScopeKey('org-1', 'loc-2'))

  const conflict = buildScopedConflict(
    { organizationId: 'org-1', locationId: 'loc-1' },
    {
      mutation_id: 'mutation-1',
      status: 'conflict',
      entity_id: 'customer-1',
      entity_version: null,
      error_code: 'sync_conflict',
      error_message: 'stale version',
    },
    '2026-08-07T08:00:00.000Z',
  )
  assert.equal(conflict.organization_id, 'org-1')
  assert.equal(conflict.location_id, 'loc-1')
  assert.equal(conflict.scope_key, 'org-1::loc-1')
})

test('sync ignores acknowledgement ids that were not present in the pushed batch', async () => {
  const store = new FakeStore()
  const transport = new FakeTransport()
  store.pending.push({
    mutation_id: 'mutation-local',
    entity_type: 'customer',
    entity_id: 'customer-local',
    operation: 'create',
    organization_id: 'org-1',
    location_id: 'loc-1',
    base_version: null,
    occurred_at: '2026-08-07T00:00:00Z',
    payload: { display_name: 'Local' },
  })
  transport.push = async () => ({
    results: [
      {
        mutation_id: 'mutation-unrelated',
        status: 'applied',
        entity_id: 'customer-unrelated',
        entity_version: 1,
      },
    ],
  })
  const coordinator = new SyncCoordinator({ store, transport, locationId: 'loc-1' })

  await coordinator.runOnce({ online: true })

  assert.deepEqual(store.acked, [])
  assert.deepEqual(store.pending.map((item) => item.mutation_id), ['mutation-local'])
})

test('HTTP sync transport preserves unauthorized status so the app can require reauthentication', async () => {
  const { HttpSyncTransport, SyncTransportError } = await import('../../.tmp-sync/src/sync/http-transport.js')
  const transport = new HttpSyncTransport('', () => 'expired-token', async () => new Response(JSON.stringify({ detail: 'invalid session' }), { status: 401, headers: { 'content-type': 'application/json' } }))

  await assert.rejects(
    () => transport.pull(0, 'loc-1'),
    (error) => error instanceof SyncTransportError && error.status === 401,
  )
})

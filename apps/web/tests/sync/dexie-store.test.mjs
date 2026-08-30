import test from 'node:test'
import assert from 'node:assert/strict'

import { DexieSyncStore } from '../../.tmp-sync/src/sync/dexie-store.js'

class FakeCollection {
  constructor(values) { this.values = values }
  limit(value) { return new FakeCollection(this.values.slice(0, value)) }
  async toArray() { return [...this.values] }
}

class FakeWhere {
  constructor(values, index) { this.values = values; this.index = index }
  equals(value) { return new FakeCollection(this.values.filter((item) => item[this.index] === value)) }
}

class FakeTable {
  constructor(keyField, values = []) { this.keyField = keyField; this.values = [...values] }
  where(index) { return new FakeWhere(this.values, index) }
  async get(key) { return this.values.find((item) => item[this.keyField] === key) }
  async put(value) {
    const index = this.values.findIndex((item) => item[this.keyField] === value[this.keyField])
    if (index >= 0) this.values[index] = value
    else this.values.push(value)
    return value[this.keyField]
  }
  async bulkDelete(keys) { this.values = this.values.filter((item) => !keys.includes(item[this.keyField])) }
}

function mutation(id, organizationId, locationId) {
  return {
    mutation_id: id,
    entity_type: 'customer',
    entity_id: `customer-${id}`,
    operation: 'create',
    organization_id: organizationId,
    location_id: locationId,
    base_version: null,
    occurred_at: '2026-08-07T08:00:00Z',
    payload: { display_name: id },
    state: 'pending',
    queued_at: '2026-08-07T08:00:00Z',
  }
}

function fakeDb() {
  return {
    customers: new FakeTable('customer_id'),
    mutationQueue: new FakeTable('mutation_id', [
      mutation('m1', 'org-1', 'loc-1'),
      mutation('m2', 'org-2', 'loc-1'),
      mutation('m3', 'org-1', 'loc-2'),
    ]),
    syncState: new FakeTable('key', [
      { key: 'cursor:org-1::loc-1', scope_key: 'org-1::loc-1', organization_id: 'org-1', location_id: 'loc-1', cursor: 5, updated_at: 'x' },
      { key: 'cursor:org-2::loc-1', scope_key: 'org-2::loc-1', organization_id: 'org-2', location_id: 'loc-1', cursor: 9, updated_at: 'x' },
    ]),
    conflicts: new FakeTable('mutation_id'),
    async transaction(_mode, ...args) {
      const callback = args.at(-1)
      return callback()
    },
  }
}

test('DexieSyncStore isolates pending mutations, cursor, and conflicts by organization and location', async () => {
  const database = fakeDb()
  const store = new DexieSyncStore(database, { organizationId: 'org-1', locationId: 'loc-1' })

  const pending = await store.listPending(100)
  assert.deepEqual(pending.map((item) => item.mutation_id), ['m1'])
  assert.equal(await store.getCursor(), 5)

  await store.recordConflicts([
    {
      mutation_id: 'm1',
      status: 'conflict',
      entity_id: 'customer-m1',
      entity_version: null,
      error_code: 'sync_conflict',
      error_message: 'stale',
    },
  ])
  assert.equal(database.conflicts.values[0].scope_key, 'org-1::loc-1')
  assert.equal(database.conflicts.values[0].organization_id, 'org-1')
  assert.equal(database.conflicts.values[0].location_id, 'loc-1')
})

test('DexieSyncStore rejects a pulled customer payload from another scope before advancing cursor', async () => {
  const database = fakeDb()
  const store = new DexieSyncStore(database, { organizationId: 'org-1', locationId: 'loc-1' })

  await assert.rejects(
    () => store.mergeAndAdvance([
      {
        cursor: 6,
        entity_type: 'customer',
        entity_id: 'customer-other',
        operation: 'create',
        organization_id: 'org-2',
        location_id: 'loc-1',
        entity_version: 1,
        occurred_at: '2026-08-07T08:00:00Z',
        payload: {
          customer_id: 'customer-other', organization_id: 'org-2', location_id: 'loc-1', display_name: 'Other',
          email: null, phone: null, created_at: '2026-08-07T08:00:00Z', updated_at: '2026-08-07T08:00:00Z', version: 1,
        },
      },
    ], 6),
    /scope/i,
  )
  assert.equal(await store.getCursor(), 5)
})

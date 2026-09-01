import test from 'node:test'
import assert from 'node:assert/strict'

import { DexieSyncStore } from '../../.tmp-sync/src/sync/dexie-store.js'

class FakeTable {
  constructor(keyField) {
    this.keyField = keyField
    this.values = []
  }
  async put(value) {
    const index = this.values.findIndex((item) => item[this.keyField] === value[this.keyField])
    if (index >= 0) this.values[index] = value
    else this.values.push(value)
    return value[this.keyField]
  }
  async toArray() {
    return [...this.values]
  }
  async get(key) {
    return this.values.find((item) => item[this.keyField] === key)
  }
}

class FakeDatabase {
  constructor() {
    this.customers = new FakeTable('customer_id')
    this.bicycles = new FakeTable('bicycle_id')
    this.serviceOrders = new FakeTable('order_id')
    this.syncState = new FakeTable('key')
  }
  async transaction(_mode, ...args) {
    return args[args.length - 1]()
  }
}

const scope = { organizationId: 'org-1', locationId: 'loc-1' }

function store(database) {
  return new DexieSyncStore(database, scope)
}

test('mergeAndAdvance upserts pulled bicycles and service orders beside customers', async () => {
  const database = new FakeDatabase()
  const syncStore = store(database)

  await syncStore.mergeAndAdvance(
    [
      {
        cursor: 1,
        entity_type: 'customer',
        entity_id: 'customer-1',
        organization_id: 'org-1',
        location_id: 'loc-1',
        payload: {
          customer_id: 'customer-1',
          organization_id: 'org-1',
          location_id: 'loc-1',
          display_name: 'Ana Rivera',
          email: null,
          phone: null,
          created_at: '2026-09-01T10:00:00Z',
          updated_at: '2026-09-01T10:00:00Z',
          version: 1,
        },
      },
      {
        cursor: 2,
        entity_type: 'bicycle',
        entity_id: 'bicycle-1',
        organization_id: 'org-1',
        location_id: 'loc-1',
        payload: {
          bicycle_id: 'bicycle-1',
          customer_id: 'customer-1',
          organization_id: 'org-1',
          location_id: 'loc-1',
          brand: 'Trek Marlin',
          model: '7',
          bicycle_type: null,
          wheel_size: null,
          notes: null,
          created_at: '2026-09-01T10:00:01Z',
          updated_at: '2026-09-01T10:00:01Z',
          version: 1,
        },
      },
      {
        cursor: 3,
        entity_type: 'service_order',
        entity_id: 'order-1',
        organization_id: 'org-1',
        location_id: 'loc-1',
        payload: {
          order_id: 'order-1',
          customer_id: 'customer-1',
          bicycle_id: 'bicycle-1',
          organization_id: 'org-1',
          location_id: 'loc-1',
          state: 'AUTHORIZED',
          reported_problem: 'Cadena saltando',
          intake_condition: null,
          accessories: null,
          priority: 'normal',
          diagnosis: null,
          created_at: '2026-09-01T10:00:02Z',
          updated_at: '2026-09-01T10:00:03Z',
          version: 3,
        },
      },
      {
        cursor: 4,
        entity_type: 'unknown_entity',
        entity_id: 'x',
        organization_id: 'org-1',
        location_id: 'loc-1',
        payload: null,
      },
    ],
    4,
  )

  const bicycles = await database.bicycles.toArray()
  assert.equal(bicycles.length, 1)
  assert.equal(bicycles[0].brand, 'Trek Marlin')
  const orders = await database.serviceOrders.toArray()
  assert.equal(orders.length, 1)
  assert.equal(orders[0].state, 'AUTHORIZED')
  assert.equal(orders[0].version, 3)
  const state = await database.syncState.get('cursor:org-1::loc-1')
  assert.equal(state.cursor, 4)
})

test('mergeAndAdvance rejects a foreign-scope order payload before advancing', async () => {
  const database = new FakeDatabase()
  const syncStore = store(database)

  await assert.rejects(
    () =>
      syncStore.mergeAndAdvance(
        [
          {
            cursor: 5,
            entity_type: 'service_order',
            entity_id: 'order-x',
            organization_id: 'org-OTHER',
            location_id: 'loc-1',
            payload: {
              order_id: 'order-x',
              customer_id: 'customer-9',
              bicycle_id: null,
              organization_id: 'org-OTHER',
              location_id: 'loc-1',
              state: 'INTAKE',
              reported_problem: 'x',
              created_at: '2026-09-01T10:00:00Z',
              updated_at: '2026-09-01T10:00:00Z',
              version: 1,
            },
          },
        ],
        5,
      ),
    /scope mismatch/,
  )
  const orders = await database.serviceOrders.toArray()
  assert.equal(orders.length, 0)
})

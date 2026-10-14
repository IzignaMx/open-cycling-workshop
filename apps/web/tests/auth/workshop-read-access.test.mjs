import test from 'node:test'
import assert from 'node:assert/strict'
import {
  canReadCachedEntity,
  workshopReadAccess,
} from '../../.tmp-auth/src/auth/workshop-read-access.js'

test('cached content requires explicit read capabilities, never write alone', () => {
  for (const capabilities of [[], ['customers.write', 'bicycles.write', 'orders.write']]) {
    assert.deepEqual(workshopReadAccess(capabilities), {
      customers: false,
      bicycles: false,
      orders: false,
    })
    for (const entity of ['customer', 'bicycle', 'service_order']) {
      assert.equal(canReadCachedEntity(capabilities, entity), false)
    }
  }
})

test('each read capability exposes only its entity; administrator wildcard covers known entities', () => {
  for (const [capability, entity] of [
    ['customers.read', 'customer'],
    ['bicycles.read', 'bicycle'],
    ['orders.read', 'service_order'],
  ]) {
    for (const candidate of ['customer', 'bicycle', 'service_order']) {
      assert.equal(canReadCachedEntity([capability], candidate), candidate === entity)
      assert.equal(canReadCachedEntity(['*'], candidate), true)
    }
  }
  assert.deepEqual(workshopReadAccess(['*']), { customers: true, bicycles: true, orders: true })
})

test('unknown conflict entity types fail closed even for administrator wildcard', () => {
  for (const entity of [
    '',
    'customers',
    'service_order_event',
    'constructor',
    '__proto__',
    'future_entity',
  ]) {
    assert.equal(canReadCachedEntity(['*'], entity), false)
  }
})

test('reader-to-restricted-user display projection does not mutate stored records or queue', () => {
  const records = Object.freeze(
    ['customer', 'bicycle', 'service_order'].map((entity_type) =>
      Object.freeze({ entity_type, entity_id: entity_type }),
    ),
  )
  const queue = Object.freeze([{ mutation_id: 'pending', entity_type: 'customer' }])
  const before = JSON.stringify({ records, queue })
  assert.equal(records.filter((row) => canReadCachedEntity(['*'], row.entity_type)).length, 3)
  assert.deepEqual(
    records.filter((row) => canReadCachedEntity([], row.entity_type)),
    [],
  )
  assert.equal(JSON.stringify({ records, queue }), before)
})

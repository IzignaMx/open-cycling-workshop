import test from 'node:test'
import assert from 'node:assert/strict'

import { BicycleLocalRepository } from '../../.tmp-sync/src/features/bicycles/repository.js'
import { ServiceOrderLocalRepository } from '../../.tmp-sync/src/features/orders/repository.js'

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
  async get(key) {
    return this.values.find((item) => item[this.keyField] === key)
  }
  async toArray() {
    return [...this.values]
  }
  async where(index) {
    const values = this.values
    return {
      equals(value) {
        return {
          async toArray() {
            return values.filter((item) => item[index] === value)
          },
        }
      },
    }
  }
}

class FakeDatabase {
  constructor() {
    this.bicycles = new FakeTable('bicycle_id')
    this.serviceOrders = new FakeTable('order_id')
    this.serviceOrderEvents = new FakeTable('event_id')
    this.mutationQueue = new FakeTable('mutation_id')
    this._journal = []
  }
  async transaction(_mode, ...args) {
    const fn = args[args.length - 1]
    this._journal.push(args.slice(0, -1).map((table) => table.keyField))
    return fn()
  }
}

test('bicycle repository writes entity and queued mutation atomically', async () => {
  const database = new FakeDatabase()
  const repository = new BicycleLocalRepository(database)

  const bicycle = await repository.create({
    organizationId: 'org-1',
    locationId: 'loc-1',
    customerId: 'customer-1',
    brand: 'Trek Marlin',
  })

  const stored = await database.bicycles.get(bicycle.bicycle_id)
  assert.equal(stored.brand, 'Trek Marlin')
  const queued = await database.mutationQueue.toArray()
  assert.equal(queued.length, 1)
  assert.equal(queued[0].entity_type, 'bicycle')
  assert.deepEqual(database._journal[0], ['bicycle_id', 'mutation_id'])
})

test('order repository creates at INTAKE and transitions append event plus queue', async () => {
  const database = new FakeDatabase()
  const repository = new ServiceOrderLocalRepository(database)

  const created = await repository.create({
    organizationId: 'org-1',
    locationId: 'loc-1',
    customerId: 'customer-1',
    reportedProblem: 'Cadena saltando',
  })
  assert.equal(created.state, 'INTAKE')

  const transitioned = await repository.applyTransition(created, 'start_diagnosis', {
    actorId: 'user-1',
  })
  assert.equal(transitioned.state, 'DIAGNOSIS')
  assert.equal(transitioned.version, 2)

  const stored = await database.serviceOrders.get(created.order_id)
  assert.equal(stored.state, 'DIAGNOSIS')
  const events = await database.serviceOrderEvents.toArray()
  assert.equal(events.length, 1)
  assert.equal(events[0].action, 'start_diagnosis')
  assert.equal(events[0].order_id, created.order_id)
  const queued = await database.mutationQueue.toArray()
  assert.equal(queued.length, 2)
  assert.equal(queued[1].entity_type, 'service_order')
  assert.equal(queued[1].base_version, 1)
  assert.deepEqual(database._journal[1], ['order_id', 'event_id', 'mutation_id'])
})

test('order repository refuses illegal transitions without writing anything', async () => {
  const database = new FakeDatabase()
  const repository = new ServiceOrderLocalRepository(database)
  const created = await repository.create({
    organizationId: 'org-1',
    locationId: 'loc-1',
    customerId: 'customer-1',
    reportedProblem: 'Cadena saltando',
  })

  await assert.rejects(
    () => repository.applyTransition(created, 'mark_ready', { actorId: 'user-1' }),
    /mark_ready/,
  )
  const stored = await database.serviceOrders.get(created.order_id)
  assert.equal(stored.state, 'INTAKE')
  const events = await database.serviceOrderEvents.toArray()
  assert.equal(events.length, 0)
  const queued = await database.mutationQueue.toArray()
  assert.equal(queued.length, 1)
})

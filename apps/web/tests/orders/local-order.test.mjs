import test from 'node:test'
import assert from 'node:assert/strict'

import { buildLocalBicycleCreate } from '../../.tmp-sync/src/features/bicycles/local-bicycle.js'
import {
  buildLocalOrderCreate,
  buildLocalOrderTransition,
} from '../../.tmp-sync/src/features/orders/local-order.js'

const deps = { now: () => '2026-09-01T10:00:00.000Z', newId: () => '018f0000-test' }

test('bicycle create builder normalizes and queues a widened mutation', () => {
  const { bicycle, mutation } = buildLocalBicycleCreate(
    {
      organizationId: 'org-1',
      locationId: 'loc-1',
      customerId: 'customer-1',
      brand: '  Trek   Marlin ',
      model: ' 7 ',
    },
    deps,
  )

  assert.equal(bicycle.brand, 'Trek Marlin')
  assert.equal(bicycle.model, '7')
  assert.equal(bicycle.customer_id, 'customer-1')
  assert.equal(bicycle.version, 1)
  assert.equal(mutation.entity_type, 'bicycle')
  assert.equal(mutation.operation, 'create')
  assert.equal(mutation.payload.brand, 'Trek Marlin')
  assert.equal(mutation.payload.customer_id, 'customer-1')
})

test('bicycle create builder rejects a blank brand', () => {
  assert.throws(
    () =>
      buildLocalBicycleCreate(
        { organizationId: 'org-1', locationId: 'loc-1', customerId: 'c1', brand: '   ' },
        deps,
      ),
    /marca/i,
  )
})

test('order create builder starts at INTAKE with a service_order mutation', () => {
  const { order, mutation } = buildLocalOrderCreate(
    {
      organizationId: 'org-1',
      locationId: 'loc-1',
      customerId: 'customer-1',
      reportedProblem: '  Cadena  saltando ',
      priority: 'high',
    },
    deps,
  )

  assert.equal(order.state, 'INTAKE')
  assert.equal(order.reported_problem, 'Cadena saltando')
  assert.equal(order.version, 1)
  assert.equal(mutation.entity_type, 'service_order')
  assert.equal(mutation.base_version, null)
  assert.equal(mutation.payload.reported_problem, 'Cadena saltando')
})

test('order transition builder advances state, version and queues base_version', () => {
  const { order } = buildLocalOrderCreate(
    {
      organizationId: 'org-1',
      locationId: 'loc-1',
      customerId: 'customer-1',
      reportedProblem: 'Falla de frenos',
    },
    deps,
  )

  const result = buildLocalOrderTransition(
    order,
    'start_diagnosis',
    { ...deps, actorId: 'user-1' },
    ' revisión inicial ',
  )

  assert.equal(result.order.state, 'DIAGNOSIS')
  assert.equal(result.order.version, order.version + 1)
  assert.equal(result.mutation.entity_type, 'service_order')
  assert.equal(result.mutation.operation, 'update')
  assert.equal(result.mutation.base_version, order.version)
  assert.deepEqual(result.mutation.payload.transition, {
    action: 'start_diagnosis',
    actor_id: 'user-1',
    note: 'revisión inicial',
  })
  assert.equal(result.event.action, 'start_diagnosis')
  assert.equal(result.event.from_state, 'INTAKE')
  assert.equal(result.event.to_state, 'DIAGNOSIS')
})

test('order transition builder refuses illegal transitions', () => {
  const { order } = buildLocalOrderCreate(
    {
      organizationId: 'org-1',
      locationId: 'loc-1',
      customerId: 'customer-1',
      reportedProblem: 'Falla de frenos',
    },
    deps,
  )

  assert.throws(
    () => buildLocalOrderTransition(order, 'mark_ready', { ...deps, actorId: 'u' }),
    /mark_ready/,
  )
})

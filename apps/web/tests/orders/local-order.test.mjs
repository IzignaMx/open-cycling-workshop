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

const bicycleInput = {
  organizationId: 'org-1',
  locationId: 'loc-1',
  customerId: 'c1',
  brand: 'Synthetic',
}
const orderInput = {
  organizationId: 'org-1',
  locationId: 'loc-1',
  customerId: 'c1',
  reportedProblem: 'Synthetic problem',
}
for (const [field, value, message] of [
  ['brand', 'x'.repeat(121), 'La marca no puede superar 120 caracteres'],
  ['model', 'x'.repeat(121), 'El modelo no puede superar 120 caracteres'],
  ['bicycleType', 'x'.repeat(61), 'El tipo de bicicleta no puede superar 60 caracteres'],
  ['wheelSize', 'x'.repeat(31), 'El tamaño de rueda no puede superar 30 caracteres'],
  ['notes', 'x'.repeat(2001), 'Las notas de la bicicleta no pueden superar 2000 caracteres'],
  ['brand', '\u0085', 'La marca de la bicicleta es obligatoria'],
]) {
  test(`bicycle prepared ${field} admission rejects before IDs (${value.length})`, () => {
    let ids = 0
    assert.throws(
      () =>
        buildLocalBicycleCreate(
          { ...bicycleInput, [field]: value },
          {
            ...deps,
            newId: () => {
              ids++
              return 'id'
            },
          },
        ),
      (error) => error.message === message,
    )
    assert.equal(ids, 0)
  })
}
for (const [field, value, message] of [
  ['reportedProblem', '\u001c\u0085', 'El problema reportado es obligatorio'],
  ['priority', 'x'.repeat(31), 'La prioridad no puede superar 30 caracteres'],
  ['priority', '\u0085', 'La prioridad es obligatoria'],
]) {
  test(`order prepared ${field} admission rejects before IDs (${value.length})`, () => {
    let ids = 0
    assert.throws(
      () =>
        buildLocalOrderCreate(
          { ...orderInput, [field]: value },
          {
            ...deps,
            newId: () => {
              ids++
              return 'id'
            },
          },
        ),
      (error) => error.message === message,
    )
    assert.equal(ids, 0)
  })
}
test('bicycle admission keeps exact prepared values and codepoint boundary', () => {
  const { bicycle, mutation } = buildLocalBicycleCreate(
    {
      ...bicycleInput,
      brand: '😀'.repeat(120),
      model: ' \u0085Model\u0085 ',
      bicycleType: 't'.repeat(60),
      wheelSize: 'w'.repeat(30),
      notes: 'n'.repeat(2000),
    },
    deps,
  )
  assert.equal(bicycle.brand, '😀'.repeat(120))
  assert.equal(bicycle.model, '\u0085Model\u0085')
  assert.equal(mutation.payload.bicycle_type, 't'.repeat(60))
  assert.equal(mutation.payload.wheel_size, 'w'.repeat(30))
  assert.equal(mutation.payload.notes, 'n'.repeat(2000))
})
test('order builders retain long Text values and non-enumerated bounded priorities', () => {
  const { order } = buildLocalOrderCreate(
    {
      ...orderInput,
      reportedProblem: 'p'.repeat(4001),
      intakeCondition: 'i'.repeat(4001),
      accessories: 'a'.repeat(2001),
      priority: 'z'.repeat(30),
    },
    deps,
  )
  assert.equal(order.reported_problem, 'p'.repeat(4001))
  assert.equal(order.intake_condition, 'i'.repeat(4001))
  assert.equal(order.accessories, 'a'.repeat(2001))
  assert.equal(order.priority, 'z'.repeat(30))
  assert.equal(
    buildLocalOrderCreate({ ...orderInput, priority: ' ' }, deps).order.priority,
    'normal',
  )
  assert.equal(
    buildLocalOrderCreate({ ...orderInput, reportedProblem: 'A\u0085B' }, deps).order
      .reported_problem,
    'A\u0085B',
  )
})

import test from 'node:test'
import assert from 'node:assert/strict'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { filterOrders } from '../../.tmp-orders/src/features/orders/order-filter.js'
import { OrderList } from '../../.tmp-orders/src/features/orders/OrderList.js'

const orders = Object.freeze([
  Object.freeze({
    order_id: 'first',
    reported_problem: 'Frenos',
    state: 'WAITING_FOR_PARTS',
    priority: 'urgent',
  }),
  Object.freeze({
    order_id: 'second',
    reported_problem: 'Frenos',
    state: 'INTAKE',
    priority: 'normal',
  }),
  Object.freeze({
    order_id: 'third',
    reported_problem: 'Esperando refacciones',
    state: 'CLOSED',
    priority: 'urgent',
  }),
])
const ids = (filters) => filterOrders(orders, filters).map((row) => row.order_id)
const defaults = { query: '', state: '', priority: '' }

test('unfiltered queue preserves input order and record identities', () => {
  const result = filterOrders(orders, defaults)
  assert.deepEqual(result, orders)
  assert.equal(result[0], orders[0])
})
test('exact state does not match the same phrase in a different order problem', () => {
  assert.deepEqual(ids({ ...defaults, state: 'WAITING_FOR_PARTS' }), ['first'])
})
test('priority combines with state and existing trimmed case-insensitive search', () => {
  assert.deepEqual(ids({ query: '  FRENOS ', state: 'WAITING_FOR_PARTS', priority: 'urgent' }), [
    'first',
  ])
  assert.deepEqual(ids({ query: 'frenos', state: 'INTAKE', priority: 'urgent' }), [])
})
test('priority alone preserves original queue order', () => {
  assert.deepEqual(ids({ ...defaults, priority: 'urgent' }), ['first', 'third'])
})
for (const query of ['FIRST', 'refacciones', 'Esperando refacciones']) {
  test(`existing search remains available: ${query}`, () => {
    assert.ok(ids({ ...defaults, query }).includes('first'))
  })
}
test('empty and unmatched inputs do not fabricate orders', () => {
  assert.deepEqual(filterOrders([], defaults), [])
  assert.deepEqual(ids({ ...defaults, query: 'missing' }), [])
  assert.deepEqual(ids({ ...defaults, state: 'UNKNOWN' }), [])
})
test('actual list exposes labeled native filters and reset without changing read-only access', () => {
  const html = renderToStaticMarkup(
    createElement(OrderList, {
      orders,
      events: [],
      canTransition: false,
      canReadBicycleInfo: false,
      protection: { notice: null, states: new Map() },
      onTransition: async () => ({ status: 'unknown' }),
    }),
  )
  assert.match(html, /Estado de la orden<select/)
  assert.match(html, /Prioridad de la orden<select/)
  assert.match(html, /value="WAITING_FOR_PARTS"/)
  assert.match(html, /value="urgent"/)
  assert.match(html, /Limpiar filtros/)
  assert.match(html, /Solo lectura/)
})

import test from 'node:test'
import assert from 'node:assert/strict'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { OrderList } from '../../.tmp-orders/src/features/orders/OrderList.js'

const order = Object.freeze({
  order_id: 'order-A',
  reported_problem: 'Frenos',
  state: 'INTAKE',
  priority: 'normal',
  version: 1,
  intake_condition: 'Manubrio rayado\nRueda delantera floja',
  accessories: 'Canasto <rojo> & candado',
  customer_id: 'private-customer-id',
  bicycle_id: 'private-bicycle-id',
})
function render(overrides = {}, canTransition = false) {
  return renderToStaticMarkup(
    createElement(OrderList, {
      orders: [{ ...order, ...overrides }],
      events: [],
      canTransition,
      canReadBicycleInfo: false,
      protection: { notice: null, states: new Map() },
      onTransition: async () => {
        assert.fail('readback cannot mutate')
      },
    }),
  )
}

test('saved intake is available as a collapsed native disclosure in a read-only order', () => {
  const html = render()
  assert.match(html, /<details class="order-intake-details"><summary>Datos de recepción<\/summary>/)
  assert.match(html, /<dt>Condición al recibir<\/dt>/)
  assert.match(html, /<dd dir="auto">Manubrio rayado\nRueda delantera floja<\/dd>/)
  assert.match(html, /<dt>Accesorios<\/dt>/)
  assert.match(html, /<dd dir="auto">Canasto &lt;rojo&gt; &amp; candado<\/dd>/)
  assert.match(html, /Solo lectura/)
  assert.doesNotMatch(html, /private-customer-id|private-bicycle-id|<rojo>/)
})
for (const value of [null, undefined, '', ' \n ']) {
  test(`missing intake text is explicitly unrecorded, not asserted absent: ${JSON.stringify(value)}`, () => {
    const html = render({ intake_condition: value, accessories: value })
    assert.match(html, /<dt>Condición al recibir<\/dt><dd dir="auto">No registrada<\/dd>/)
    assert.match(html, /<dt>Accesorios<\/dt><dd dir="auto">No registrados<\/dd>/)
    assert.doesNotMatch(html, /Sin daños|Sin accesorios|undefined|null/)
  })
}
test('readback preserves nonempty recorded text exactly and does not mutate input', () => {
  const html = render(
    { intake_condition: '  إطارات\n  desgastadas  ', accessories: '🙂'.repeat(100) },
    true,
  )
  assert.ok(html.includes('  إطارات\n  desgastadas  '))
  assert.ok(html.includes('🙂'.repeat(100)))
  assert.equal(order.intake_condition, 'Manubrio rayado\nRueda delantera floja')
  assert.match(html, /Iniciar diagnóstico/)
})

test('full-width intake disclosure follows actions to preserve desktop order columns', () => {
  const html = render()
  assert.ok(html.indexOf('class="order-actions"') < html.indexOf('class="order-intake-details"'))
})

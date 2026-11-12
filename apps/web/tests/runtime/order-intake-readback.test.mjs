import test from 'node:test'
import assert from 'node:assert/strict'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { OrderList } from '../../.tmp-orders/src/features/orders/OrderList.js'
import { setup, login } from './runtime-fixture.mjs'

test('actual admitted offline intake readback survives full runtime reload without replay or network', async (t) => {
  const f = setup(t)
  await login(f.runtime)
  f.env.online = false
  await f.runtime.offline()
  for (const [problem, condition, accessories] of [
    ['Frenos delanteros', 'Manubrio rayado\nRueda floja', 'Canasto <rojo>'],
    ['Cambio trasero', null, null],
  ]) {
    await f.runtime.createOrder({
      customerId: 'historical-A',
      reportedProblem: problem,
      intakeCondition: condition,
      accessories,
      priority: 'normal',
      brand: null,
      model: null,
    })
  }
  const journal = await f.database.operationJournal.toArray()
  const records = f.runtime.getSnapshot().orders
  assert.equal(journal.length, 2)
  f.runtime.dispose()
  const second = setup(t, { name: f.name, storage: f.storage, online: false })
  await second.runtime.start()
  assert.equal(second.runtime.getSnapshot().phase, 'ready')
  assert.deepEqual(second.runtime.getSnapshot().orders, records)
  const html = renderToStaticMarkup(
    createElement(OrderList, {
      orders: second.runtime.getSnapshot().orders,
      events: [],
      canTransition: false,
      canReadBicycleInfo: false,
      protection: { notice: null, states: new Map() },
      onTransition: async () => {
        assert.fail('readback must not write')
      },
    }),
  )
  assert.ok(html.includes('Manubrio rayado\nRueda floja'))
  assert.ok(html.includes('Canasto &lt;rojo&gt;'))
  assert.match(html, /No registrada/)
  assert.match(html, /No registrados/)
  assert.equal(second.server.calls.length, 0)
  assert.deepEqual(await second.database.operationJournal.toArray(), journal)
  await second.runtime.logout()
  assert.equal(second.runtime.getSnapshot().orders.length, 0)
})

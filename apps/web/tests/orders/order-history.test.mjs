import test from 'node:test'
import assert from 'node:assert/strict'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { OrderList } from '../../.tmp-orders/src/features/orders/OrderList.js'

const order = {
  order_id: 'order',
  reported_problem: 'Frenos',
  state: 'DIAGNOSIS',
  priority: 'normal',
  version: 2,
}
const event = (overrides = {}) => ({
  event_id: 'event',
  order_id: 'order',
  organization_id: 'org',
  from_state: 'INTAKE',
  to_state: 'DIAGNOSIS',
  action: 'start_diagnosis',
  actor_id: '0199ba00-0000-7000-8000-000000000001',
  occurred_at: '2026-11-08T12:34:56.123456-06:00',
  note: null,
  recordSource: 'local',
  ...overrides,
})
const render = (events, canTransition = false) =>
  renderToStaticMarkup(
    createElement(OrderList, {
      orders: [order],
      events,
      canTransition,
      canReadBicycleInfo: false,
      protection: { notice: null, states: new Map() },
      onTransition: async () => ({ status: 'unknown' }),
    }),
  )

test('actual OrderList renders two full authors, original zoned times and record provenance in read-only history', () => {
  const html = render([
    event(),
    event({
      event_id: 'second',
      actor_id: 'mechanic-B',
      occurred_at: '2026-11-08T18:35:00Z',
      recordSource: 'server',
    }),
  ])
  assert.match(html, /Autor \(ID\):.*0199ba00-0000-7000-8000-000000000001/)
  assert.match(html, /Autor \(ID\):.*mechanic-B/)
  assert.match(
    html,
    /<time dateTime="2026-11-08T12:34:56.123456-06:00">2026-11-08T12:34:56.123456-06:00<\/time>/,
  )
  assert.match(html, /<time dateTime="2026-11-08T18:35:00Z">2026-11-08T18:35:00Z<\/time>/)
  assert.match(html, /Registro local/)
  assert.match(html, /Registro del servidor/)
  assert.match(html, /no implica aceptación del servidor/)
  assert.match(html, /Solo lectura/)
  assert.doesNotMatch(html, /Mecánico asignado|Hora del servidor|pendiente de sincronizar/)
})

for (const value of [
  undefined,
  null,
  {},
  [],
  42,
  '',
  'bad id',
  'a/b',
  'a?b',
  'a#b',
  'a\0b',
  'a'.repeat(37),
]) {
  test(`actual history safely handles malformed actor ${JSON.stringify(value)}`, () => {
    const html = render([event({ actor_id: value })])
    assert.match(html, /Autor \(ID\):.*No disponible/)
    assert.doesNotMatch(html, /\[object Object\]/)
  })
}
for (const value of [
  undefined,
  null,
  {},
  42,
  '',
  'not-a-date',
  '2026-02-30T10:00:00Z',
  '2025-02-29T10:00:00Z',
  '2026-11-08T24:00:00Z',
  '2026-11-08T12:60:00Z',
  '2026-11-08T12:00:60Z',
  '2026-11-08T12:00:00+25:00',
  '2026-11-08T12:00:00',
  '2026-11-08',
  '2026-11-08T12:00:00-00:00',
]) {
  test(`actual history does not invent a date or zone for ${JSON.stringify(value)}`, () => {
    const html = render([event({ occurred_at: value })])
    assert.match(html, /Fecha registrada:.*No disponible o sin zona horaria verificable/)
    assert.doesNotMatch(html, /<time|Invalid Date|\[object Object\]/)
  })
}
for (const value of [
  '2024-02-29T00:00:00Z',
  '2026-11-08T12:34:56+05:30',
  '2026-11-08T12:34:56.1Z',
  '2026-11-08T12:34:56.123456789+00:00',
]) {
  test(`actual history preserves recorded precision/zone ${value}`, () => {
    assert.ok(
      render([event({ occurred_at: value })]).includes(`<time dateTime="${value}">${value}</time>`),
    )
  })
}
test('actual history renders symbolic actor text inertly and filters other orders', () => {
  const html = render([
    event({ actor_id: '<b>actor' }),
    event({ event_id: 'other', order_id: 'other-order', actor_id: 'hidden-actor' }),
  ])
  assert.match(html, /&lt;b&gt;actor/)
  assert.doesNotMatch(html, /<b>|hidden-actor/)
})

test('actual history does not invent a source for malformed presentation input', () => {
  assert.match(render([event({ recordSource: undefined })]), /Origen no disponible/)
})

test('actual history isolates the full actor ID from surrounding label direction', () => {
  const actor = 'טכנאי-123'
  const html = render([event({ actor_id: actor })])
  assert.ok(html.includes(`Autor (ID): <bdi dir="auto">${actor}</bdi>`))
})

for (const actor of ['actor\u202E-123', 'ab\u0008c', 'a\u2066b', 'a\u200Bb']) {
  test(`actual history declines visually ambiguous actor controls ${JSON.stringify(actor)}`, () => {
    const html = render([event({ actor_id: actor })])
    assert.match(html, /Autor \(ID\):.*No disponible/)
    assert.ok(!html.includes(actor))
  })
}

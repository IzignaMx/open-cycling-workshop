import test from 'node:test'
import assert from 'node:assert/strict'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { OrderList } from '../../.tmp-orders/src/features/orders/OrderList.js'
const order = {
  order_id: 'one',
  state: 'IN_PROGRESS',
  reported_problem: 'Frenos',
  priority: 'normal',
  version: 1,
}
const protection = {
  states: new Map(),
  notes: new Map([['one', 'Falta cadena']]),
  noteToken: {},
  notice: null,
}
const render = (overrides = {}) =>
  renderToStaticMarkup(
    createElement(OrderList, {
      orders: [order],
      events: [],
      canTransition: true,
      canReadBicycleInfo: false,
      protection,
      onNote: () => {},
      onTransition: async () => ({ status: 'unknown' }),
      ...overrides,
    }),
  )
test('actual order offers a labeled optional bounded note and warns that unsent text is volatile', () => {
  const html = render()
  assert.match(html, /Nota para el próximo cambio \(opcional\)/)
  assert.match(html, /<textarea[^>]*maxLength="4000"[^>]*>Falta cadena<\/textarea>/)
  assert.match(html, /sin enviar.*recargar/)
  assert.match(html, /Solicitar refacciones/)
})
test('invalid note is visible with a correction and no enabled transition actions', () => {
  const html = render({
    protection: { ...protection, notes: new Map([['one', 'x'.repeat(2001)]]) },
  })
  assert.match(html, /no puede superar 2000/)
  assert.match(html, /<button[^>]*disabled=""[^>]*>Solicitar refacciones/)
})
test('pending or unknown attempt prevents note editing without hiding the captured text', () => {
  const html = render({
    protection: {
      ...protection,
      states: new Map([['one', { busy: false, feedback: { message: 'No repitas', block: true } }]]),
    },
  })
  assert.match(html, /<textarea[^>]*disabled=""[^>]*>Falta cadena<\/textarea>/)
  assert.match(html, /No repitas/)
})
test('read-only and final orders expose no note editor', () => {
  assert.doesNotMatch(render({ canTransition: false }), /<textarea/)
  assert.doesNotMatch(
    render({
      orders: [{ ...order, state: 'CLOSED' }],
      protection: { ...protection, notes: new Map() },
    }),
    /<textarea/,
  )
})
test('historical note is inert exact text rather than new acceptance or private-note claims', () => {
  const html = render({
    canTransition: false,
    events: [
      {
        event_id: 'event',
        order_id: 'one',
        action: 'request_parts',
        from_state: 'IN_PROGRESS',
        to_state: 'WAITING_FOR_PARTS',
        actor_id: 'actor',
        occurred_at: '2026-11-12T12:00:00Z',
        recordSource: 'local',
        note: '<script>nota</script>\nsegunda línea',
      },
    ],
  })
  assert.match(html, /Nota del cambio:/)
  assert.ok(html.includes('&lt;script&gt;nota&lt;/script&gt;\nsegunda línea'))
  assert.doesNotMatch(html, /<script>|Nota privada|Nota interna/)
})

test('saved final state leaves an existing unsent draft clearable rather than hiding it', () => {
  const html = render({ orders: [{ ...order, state: 'CLOSED' }] })
  assert.match(html, /Nota sin enviar \(orden final\)/)
  assert.match(html, />Falta cadena<\/textarea>/)
  assert.doesNotMatch(html, /Solicitar refacciones/)
})

test('actual beforeunload callback warns for unsent notes and stops after explicit clearing', async () => {
  const { readFileSync } = await import('node:fs')
  const ts = (await import('typescript')).default
  const source = ts.createSourceFile(
    'App.tsx',
    readFileSync(new URL('../../src/App.tsx', import.meta.url), 'utf8'),
    ts.ScriptTarget.Latest,
    true,
  )
  let callback
  function visit(node) {
    if (ts.isVariableDeclaration(node) && node.name.getText(source) === 'warnUnsavedEdit')
      callback = node.initializer
    ts.forEachChild(node, visit)
  }
  visit(source)
  assert.ok(callback)
  const compiled = ts.transpileModule(`const handler = ${callback.getText(source)}`, {
    compilerOptions: { target: ts.ScriptTarget.ES2022 },
  }).outputText
  let unsent = true,
    prevented = 0
  const handler = new Function('runtime', compiled + ';return handler;')({
    getSnapshot: () => ({ customerEdit: null }),
    hasUnsentTransitionNotes: () => unsent,
  })
  const event = {
    preventDefault() {
      prevented++
    },
    returnValue: undefined,
  }
  handler(event)
  assert.equal(prevented, 1)
  assert.equal(event.returnValue, '')
  unsent = false
  handler(event)
  assert.equal(prevented, 1)
})

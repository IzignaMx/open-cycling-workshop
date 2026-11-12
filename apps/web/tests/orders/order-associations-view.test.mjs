import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { OrderList } from '../../.tmp-orders/src/features/orders/OrderList.js'

const order = {
  order_id: 'one',
  state: 'INTAKE',
  reported_problem: 'Frenos',
  priority: 'normal',
  version: 1,
  customer_id: 'raw-customer',
  bicycle_id: 'raw-bicycle',
}
const ready = {
  orderId: 'one',
  status: 'ready',
  customer: { status: 'available', id: 'customer-ID', name: 'Cliente <script>\nعربي' },
  bicycle: { status: 'available', id: 'bicycle-ID', brand: 'Marca <img>\nBici', model: null },
}
const render = (props = {}) =>
  renderToStaticMarkup(
    createElement(OrderList, {
      orders: [order],
      events: [],
      protection: { notice: null, states: new Map() },
      canTransition: false,
      canReadCustomerInfo: true,
      canReadBicycleInfo: true,
      onAssociations: async () => {},
      onTransition: async () => assert.fail('readback cannot mutate'),
      ...props,
    }),
  )

test('readback offers a button only with a reader and at least one independent permission', () => {
  assert.match(render(), />Ver cliente y bicicleta<\/button>/)
  assert.match(render({ canReadCustomerInfo: false }), />Ver cliente y bicicleta<\/button>/)
  assert.match(render({ canReadBicycleInfo: false }), />Ver cliente y bicicleta<\/button>/)
  assert.doesNotMatch(
    render({ canReadCustomerInfo: false, canReadBicycleInfo: false, associations: ready }),
    /Ver cliente y bicicleta|customer-ID|bicycle-ID/,
  )
  assert.doesNotMatch(render({ onAssociations: undefined }), /Ver cliente y bicicleta/)
})
test('loading is announced and disables the readback button, failed remains retryable with generic feedback', () => {
  const loading = render({ associations: { orderId: 'one', status: 'loading' } })
  assert.match(loading, /<button[^>]*disabled=""[^>]*>Ver cliente y bicicleta/)
  assert.match(loading, /role="status">Cargando cliente y bicicleta locales/)
  const failed = render({
    associations: { orderId: 'one', status: 'failed', error: 'secret-stack' },
  })
  assert.match(failed, /No se pudo cargar el cliente y la bicicleta locales/)
  assert.doesNotMatch(failed, /disabled=""[^>]*>Ver cliente y bicicleta|secret-stack/)
})
test('only matching row shows the single local snapshot with inert bidi multiline text', () => {
  const html = render({ orders: [order, { ...order, order_id: 'two' }], associations: ready })
  assert.equal((html.match(/customer-ID/g) ?? []).length, 1)
  assert.match(html, /<bdi dir="auto">Cliente &lt;script&gt;\nعربي<\/bdi>/)
  assert.match(html, /<bdi dir="auto">Marca &lt;img&gt;\nBici<\/bdi>/)
  assert.match(html, /<bdi dir="auto">customer-ID<\/bdi>/)
  assert.match(html, /Modelo no registrado/)
  assert.match(html, /Instantánea local/)
  assert.match(html, /no confirma el estado actual del servidor/)
  assert.doesNotMatch(html, /<script>|<img>|raw-customer|raw-bicycle|Propietario|Teléfono|Correo/)
  assert.doesNotMatch(
    render({ associations: { ...ready, orderId: 'other' } }),
    /customer-ID|bicycle-ID/,
  )
})
test('available snapshots are masked again by each current read permission', () => {
  const customerHidden = render({ associations: ready, canReadCustomerInfo: false })
  assert.doesNotMatch(customerHidden, /customer-ID|Cliente &lt;script/)
  assert.match(customerHidden, /Cliente: acceso restringido/)
  assert.match(customerHidden, /bicycle-ID/)
  const bicycleHidden = render({ associations: ready, canReadBicycleInfo: false })
  assert.doesNotMatch(bicycleHidden, /bicycle-ID|Marca &lt;img/)
  assert.match(bicycleHidden, /Bicicleta: acceso restringido/)
  assert.match(bicycleHidden, /customer-ID/)
})
test('unavailable, restricted, and no bicycle states have distinct truthful labels', () => {
  assert.match(
    render({
      associations: {
        ...ready,
        customer: { status: 'unavailable' },
        bicycle: { status: 'unavailable' },
      },
    }),
    /Cliente no disponible localmente.*Bicicleta no disponible localmente/,
  )
  assert.match(
    render({
      associations: {
        ...ready,
        customer: { status: 'restricted' },
        bicycle: { status: 'restricted' },
      },
    }),
    /Cliente: acceso restringido.*Bicicleta: acceso restringido/,
  )
  assert.match(
    render({ associations: { ...ready, bicycle: { status: 'none' } } }),
    /Sin bicicleta asociada en esta instantánea local/,
  )
})
test('association region follows actions, spans all columns, and preserves existing controls', () => {
  const html = render({
    associations: ready,
    canTransition: true,
    onNote: () => {},
    onTimeline: async () => {},
  })
  assert.ok(html.indexOf('class="order-actions"') < html.indexOf('class="order-associations"'))
  assert.ok(
    html.indexOf('class="order-associations"') < html.indexOf('class="order-transition-note"'),
  )
  assert.match(html, /Iniciar diagnóstico/)
  assert.match(html, /Nota para el próximo cambio/)
  assert.match(html, /Datos de recepción/)
  assert.match(html, /Ver historial/)
  const css = readFileSync(new URL('../../src/styles.css', import.meta.url), 'utf8')
  assert.match(css, /\.order-associations\s*\{[^}]*grid-column:\s*1\s*\/\s*-1/)
  assert.match(
    css,
    /\.order-associations dd\s*\{[^}]*white-space:\s*pre-wrap;[^}]*overflow-wrap:\s*anywhere/,
  )
})

test('actual read button delegates the current order and absorbs arbitrary rejection without mutation', async () => {
  const ts = (await import('typescript')).default
  const source = ts.createSourceFile(
    'OrderList.tsx',
    readFileSync(new URL('../../src/features/orders/OrderList.tsx', import.meta.url), 'utf8'),
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TSX,
  )
  let callback
  function visit(node) {
    if (
      ts.isJsxElement(node) &&
      node.openingElement.tagName.getText(source) === 'button' &&
      node.children.some(
        (child) => ts.isJsxText(child) && child.text.trim() === 'Ver cliente y bicicleta',
      )
    ) {
      callback = node.openingElement.attributes.properties.find(
        (attribute) => attribute.name?.getText(source) === 'onClick',
      )?.initializer.expression
    }
    ts.forEachChild(node, visit)
  }
  visit(source)
  assert.ok(callback)
  const compiled = ts.transpileModule(`const handler = ${callback.getText(source)}`, {
    compilerOptions: { target: ts.ScriptTarget.ES2022 },
  }).outputText
  const calls = []
  const handler = new Function('order', 'onAssociations', compiled + ';return handler;')(
    order,
    async (id) => {
      calls.push(id)
      throw new Error('private rejection')
    },
  )
  handler()
  await new Promise((resolve) => setImmediate(resolve))
  assert.deepEqual(calls, ['one'])
})

test('one pending read disables other rows until the shared snapshot completes', () => {
  const html = render({
    orders: [order, { ...order, order_id: 'two' }],
    associations: { orderId: 'one', status: 'loading' },
  })
  assert.equal((html.match(/disabled=""[^>]*>Ver cliente y bicicleta/g) ?? []).length, 2)
  assert.equal((html.match(/Cargando cliente y bicicleta locales/g) ?? []).length, 1)
})

test('each read trigger controls a unique panel and only selected snapshot is expanded', () => {
  const html = render({
    orders: [order, { ...order, order_id: 'two' }],
    associations: ready,
    onCloseAssociations: () => {},
  })
  const buttons = [
    ...html.matchAll(
      /<button[^>]*aria-expanded="(true|false)"[^>]*aria-controls="([^"]+)"[^>]*>Ver cliente y bicicleta/g,
    ),
  ]
  assert.equal(buttons.length, 2)
  assert.deepEqual(
    buttons.map((match) => match[1]),
    ['true', 'false'],
  )
  assert.notEqual(buttons[0][2], buttons[1][2])
  for (const button of buttons) assert.ok(html.includes(`id="${button[2]}"`))
})
for (const status of ['loading', 'failed', 'ready']) {
  test(`snapshot can be closed while ${status}, including during a pending read`, () => {
    const html = render({
      associations: status === 'ready' ? ready : { orderId: 'one', status },
      onCloseAssociations: () => {},
    })
    assert.match(html, />Cerrar datos de cliente y bicicleta<\/button>/)
    assert.doesNotMatch(html, /<button[^>]*disabled[^>]*>Cerrar datos de cliente y bicicleta/)
    assert.match(html, /aria-expanded="true"/)
    const closed = render({ associations: null, onCloseAssociations: () => {} })
    assert.match(closed, /aria-expanded="false"/)
    assert.doesNotMatch(closed, /Cerrar datos|customer-ID|Cargando cliente|No se pudo cargar/)
  })
}
test('actual close handler delegates the selected order ID', async () => {
  const ts = (await import('typescript')).default
  const source = ts.createSourceFile(
    'OrderList.tsx',
    readFileSync(new URL('../../src/features/orders/OrderList.tsx', import.meta.url), 'utf8'),
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TSX,
  )
  let callback
  function visit(node) {
    if (
      ts.isJsxElement(node) &&
      node.openingElement.tagName.getText(source) === 'button' &&
      node.children.some(
        (child) =>
          ts.isJsxText(child) && child.text.trim() === 'Cerrar datos de cliente y bicicleta',
      )
    )
      callback = node.openingElement.attributes.properties.find(
        (attribute) => attribute.name?.getText(source) === 'onClick',
      )?.initializer.expression
    ts.forEachChild(node, visit)
  }
  visit(source)
  assert.ok(callback)
  const compiled = ts.transpileModule(`const handler = ${callback.getText(source)}`, {
    compilerOptions: { target: ts.ScriptTarget.ES2022 },
  }).outputText
  const calls = []
  const returnAssociationFocus = { current: false }
  new Function(
    'order',
    'onCloseAssociations',
    'returnAssociationFocus',
    compiled + ';return handler;',
  )(order, (id) => calls.push(id), returnAssociationFocus)()
  assert.equal(
    returnAssociationFocus.current,
    true,
    'only actual explicit close requests focus return',
  )
  assert.deepEqual(calls, ['one'])
})

test('explicit-close focus effect waits for enabled trigger and never steals focus on unrelated resets', async () => {
  const ts = (await import('typescript')).default
  const source = ts.createSourceFile(
    'OrderList.tsx',
    readFileSync(new URL('../../src/features/orders/OrderList.tsx', import.meta.url), 'utf8'),
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TSX,
  )
  let effect
  function visit(node) {
    if (ts.isCallExpression(node) && node.expression.getText(source) === 'useLayoutEffect')
      effect = node.arguments[0]
    ts.forEachChild(node, visit)
  }
  visit(source)
  assert.ok(effect, 'explicit-close focus restoration needs a post-render effect')
  const compiled = ts.transpileModule(`const effect = ${effect.getText(source)}`, {
    compilerOptions: { target: ts.ScriptTarget.ES2022 },
  }).outputText
  let focused = 0
  const trigger = {
    disabled: false,
    focus() {
      focused++
    },
  }
  const associationTrigger = { current: trigger }
  const returnAssociationFocus = { current: false }
  const run = (associations, canReadCustomerInfo = true, canReadBicycleInfo = true) =>
    new Function(
      'associations',
      'canReadCustomerInfo',
      'canReadBicycleInfo',
      'associationTrigger',
      'returnAssociationFocus',
      compiled + ';effect();',
    )(
      associations,
      canReadCustomerInfo,
      canReadBicycleInfo,
      associationTrigger,
      returnAssociationFocus,
    )
  run(null)
  assert.equal(focused, 0, 'ordinary refresh/reset must not focus')
  returnAssociationFocus.current = true
  run(null)
  assert.equal(focused, 1, 'explicit close focuses after rendering an enabled trigger')
  assert.equal(returnAssociationFocus.current, false)
  run(null)
  assert.equal(focused, 1, 'focus request is consumed once')
  returnAssociationFocus.current = true
  run(null, false, false)
  assert.equal(focused, 1, 'permission loss must not focus')
  returnAssociationFocus.current = true
  run({ ...ready, orderId: 'two' })
  assert.equal(focused, 1, 'new order snapshot must not focus')
  assert.equal(returnAssociationFocus.current, false)
  returnAssociationFocus.current = true
  trigger.disabled = true
  run(null)
  assert.equal(focused, 1, 'disabled trigger must not focus')
  returnAssociationFocus.current = true
  associationTrigger.current = null
  run(null)
  assert.equal(focused, 1, 'unmounted trigger must not focus')
})

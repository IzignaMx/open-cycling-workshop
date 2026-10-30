import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import * as module from '../../.tmp-runtime/src/features/orders/transition-feedback.js'
const resolved = (value) => ({ kind: 'resolved', value })
const updated = () => {
  assert.equal(typeof module.orderTransitionFeedback, 'function')
  return module.orderTransitionFeedback(resolved({ status: 'committed', view: 'updated' }))
}
const uncertain = () => {
  assert.equal(typeof module.orderTransitionFeedback, 'function')
  return module.orderTransitionFeedback(resolved({ status: 'unknown' }))
}
const gate = () => {
  assert.equal(typeof module.OrderTransitionGate, 'function')
  return new module.OrderTransitionGate()
}

test('transition feedback only positive closed commit/update releases the gate', () => {
  assert.deepEqual(updated(), { message: null, block: false })
  const value = module.orderTransitionFeedback(
    resolved({ status: 'committed', view: 'unavailable' }),
  )
  assert.equal(value.block, true)
  assert.match(value.message, /guardó localmente/)
  assert.match(value.message, /No repitas/)
})

for (const value of [
  undefined,
  null,
  [],
  true,
  'private-transition-canary',
  {},
  { status: 'unknown' },
  { status: 'not_committed' },
  { status: 'committed' },
  { status: 'committed', view: 'updated', cause: 'private-transition-canary' },
  { status: 'committed', view: 'private-transition-canary' },
  {
    get status() {
      throw new Error('private-transition-canary')
    },
  },
  new Proxy(
    {},
    {
      ownKeys() {
        throw new Error('private-transition-canary')
      },
    },
  ),
])
  test(`transition feedback malformed input stays unknown ${String(value === null ? 'null' : typeof value)}`, () => {
    assert.equal(typeof module.orderTransitionFeedback, 'function')
    const result = module.orderTransitionFeedback(resolved(value))
    assert.equal(result.block, true)
    assert.match(result.message, /No se pudo confirmar/)
    assert.doesNotMatch(result.message, /private-transition-canary/)
  })

test('transition feedback never reads rejected error properties', () => {
  assert.equal(typeof module.orderTransitionFeedback, 'function')
  const result = module.orderTransitionFeedback({
    kind: 'rejected',
    error: new Proxy(
      {},
      {
        get() {
          assert.fail('error properties must not be read')
        },
      },
    ),
  })
  assert.equal(result.block, true)
  assert.match(result.message, /No se pudo confirmar/)
})

test('transition gate excludes same-tick same-order calls but permits a separate order', () => {
  const value = gate(),
    first = value.begin('a')
  assert.ok(first)
  assert.equal(value.begin('a'), null)
  assert.ok(value.begin('b'))
  assert.equal(value.get('a').busy, true)
})

test('transition gate retains unknown across card hide/show and changed action/version/callback', () => {
  const value = gate(),
    token = value.begin('a')
  assert.equal(value.finish('a', token, uncertain()), true)
  // The gate is list-owned; filtered cards/row inputs have no reset authority.
  for (let version = 1; version < 5; version++) {
    assert.equal(value.begin('a'), null)
    assert.equal(value.get('a').busy, false)
    assert.equal(value.get('a').feedback.block, true)
  }
  assert.ok(value.begin('b'))
})

test('transition gate preserves committed-unavailable and accepts no alien settlement', () => {
  const value = gate(),
    token = value.begin('a'),
    other = gate()
  const feedback = module.orderTransitionFeedback(
    resolved({ status: 'committed', view: 'unavailable' }),
  )
  assert.equal(other.finish('a', token, feedback), false)
  assert.equal(value.finish('b', token, feedback), false)
  assert.equal(value.finish('a', token, feedback), true)
  assert.equal(value.begin('a'), null)
  assert.equal(value.finish('a', token, updated()), false)
  assert.equal(value.begin('a'), null)
})

test('transition gate allows only a new explicit action after positive updated completion', () => {
  const value = gate(),
    token = value.begin('a')
  assert.equal(value.finish('a', token, updated()), true)
  assert.equal(value.get('a'), undefined)
  const next = value.begin('a')
  assert.ok(next)
  assert.notEqual(next, token)
  assert.equal(value.finish('a', token, uncertain()), false)
  assert.equal(value.get('a').busy, true)
})

test('transition UI owns gate above filtered rows and does not render arbitrary exceptions', async () => {
  const source = await readFile(
    new URL('../../src/features/orders/OrderList.tsx', import.meta.url),
    'utf8',
  )
  assert.match(source, /OrderTransitionGate/)
  assert.doesNotMatch(source, /error\.message/)
  assert.match(source, /useRef/)
  assert.match(source, /mounted/)
})

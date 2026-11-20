import assert from 'node:assert/strict'
import test from 'node:test'
import { bootstrap } from '../../.tmp-bootstrap/bootstrap.js'

for (const secure of [false, undefined, null, 'true', 1]) {
  test(`rejects non-true secure context ${String(secure)} before storage or runtime`, () => {
    const events = []
    bootstrap(
      {
        isSecureContext: secure,
        get sessionStorage() {
          throw new Error('must not read')
        },
      },
      () => events.push('runtime'),
      (reason) => events.push(reason),
    )
    assert.deepEqual(events, ['insecure-context'])
  })
}
test('storage getter failure blocks startup without exposing exception', () => {
  const events = []
  bootstrap(
    {
      isSecureContext: true,
      get sessionStorage() {
        events.push('storage')
        throw new Error('private detail')
      },
    },
    () => events.push('runtime'),
    (reason) => events.push(reason),
  )
  assert.deepEqual(events, ['storage', 'storage-unavailable'])
})
test('secure context passes storage unchanged without probing methods', () => {
  const events = []
  const storage = new Proxy(
    {},
    {
      get() {
        throw new Error('no probe')
      },
    },
  )
  bootstrap(
    {
      get isSecureContext() {
        events.push('secure')
        return true
      },
      get sessionStorage() {
        events.push('storage')
        return storage
      },
    },
    (value) => {
      assert.equal(value, storage)
      events.push('runtime')
    },
    () => assert.fail('blocked'),
  )
  assert.deepEqual(events, ['secure', 'storage', 'runtime'])
})
test('runtime errors are not mislabeled as storage errors or retried', () => {
  const error = new Error('runtime')
  assert.throws(
    () =>
      bootstrap(
        { isSecureContext: true, sessionStorage: {} },
        () => {
          throw error
        },
        () => assert.fail('blocked'),
      ),
    (value) => value === error,
  )
})

test('blocked startup preserves preexisting storage bytes without reading them', () => {
  const saved = '{"draft":"synthetic-unsent","revision":7}'
  const records = new Map([['existing-work', saved]])
  const storage = {
    getItem: () => assert.fail('read'),
    setItem: () => assert.fail('write'),
    clear: () => assert.fail('clear'),
    removeItem: () => assert.fail('remove'),
  }
  bootstrap(
    {
      isSecureContext: false,
      get sessionStorage() {
        assert.fail('getter')
        return storage
      },
    },
    () => assert.fail('runtime'),
    () => {},
  )
  assert.equal(records.get('existing-work'), saved)
})

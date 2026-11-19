import assert from 'node:assert/strict'
import test from 'node:test'
import { captureResponseDuring } from '../../.tmp-response-capture/response-capture.js'

function deferred() {
  let resolve, reject
  const promise = new Promise((yes, no) => {
    resolve = yes
    reject = no
  })
  return { promise, resolve, reject }
}

test('reads the body on response arrival before the later action expires it', async () => {
  const response = deferred()
  let available = false,
    read = false
  const value = await captureResponseDuring(
    response.promise,
    async () => {
      available = true
      response.resolve({
        json: async () => {
          assert.equal(available, true, 'body expired before capture')
          read = true
          return { token: 'synthetic' }
        },
      })
      await new Promise((resolve) => setImmediate(resolve))
      available = false
    },
    (matched) => matched.json(),
  )
  assert.equal(read, true)
  assert.deepEqual(value, { token: 'synthetic' })
})

test('waits for action completion even when capture already succeeded', async () => {
  const action = deferred()
  let settled = false
  const result = captureResponseDuring(
    Promise.resolve('matched'),
    () => action.promise,
    async (x) => x,
  ).then((value) => {
    settled = true
    return value
  })
  await new Promise((resolve) => setImmediate(resolve))
  assert.equal(settled, false)
  action.resolve()
  assert.equal(await result, 'matched')
})

test('rejects unavailable or invalid body rather than accepting fallback data', async () => {
  const failure = new Error('synthetic unavailable response body')
  await assert.rejects(
    captureResponseDuring(
      Promise.resolve({}),
      async () => {},
      async () => {
        throw failure
      },
    ),
    (error) => error === failure,
  )
})

test('action failure rejects and later waiter rejection remains observed', async () => {
  const response = deferred()
  const failure = new Error('synthetic action failure')
  const result = captureResponseDuring(
    response.promise,
    async () => {
      throw failure
    },
    async (x) => x,
  )
  await assert.rejects(result, (error) => error === failure)
  response.reject(new Error('synthetic page teardown'))
  await new Promise((resolve) => setImmediate(resolve))
})

test('waiter failure is not replaced with a stored token', async () => {
  const failure = new Error('synthetic waiter failure')
  await assert.rejects(
    captureResponseDuring(
      Promise.reject(failure),
      async () => {},
      async (x) => x,
    ),
    (error) => error === failure,
  )
})

test('synchronous action throw still observes the response rejection', async () => {
  const response = deferred()
  const failure = new Error('synthetic synchronous action failure')
  await assert.rejects(
    captureResponseDuring(
      response.promise,
      () => {
        throw failure
      },
      async (x) => x,
    ),
    (error) => error === failure,
  )
  response.reject(new Error('synthetic waiter teardown'))
  await new Promise((resolve) => setImmediate(resolve))
})

test('capture failure still observes a later action rejection', async () => {
  const action = deferred()
  const failure = new Error('synthetic capture failure')
  await assert.rejects(
    captureResponseDuring(
      Promise.resolve({}),
      () => action.promise,
      async () => {
        throw failure
      },
    ),
    (error) => error === failure,
  )
  action.reject(new Error('synthetic action teardown'))
  await new Promise((resolve) => setImmediate(resolve))
})

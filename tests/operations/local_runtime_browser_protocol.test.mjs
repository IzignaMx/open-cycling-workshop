import assert from 'node:assert/strict'
import { PassThrough, Readable } from 'node:stream'
import test from 'node:test'
import { PhaseInput, validateInput } from '../../scripts/ci/local_runtime_browser_smoke.mjs'

test('stdin phases are incremental and do not wait for EOF', async () => {
  const stream = new PassThrough()
  const input = new PhaseInput(stream, { timeoutMs: 500 })
  stream.write('{"password":"synthetic"}\n')
  assert.deepEqual(await input.read(), { password: 'synthetic' })
  stream.write('{"phase":"backup_verified"}\n')
  assert.deepEqual(await input.read(), { phase: 'backup_verified' })
  stream.end()
})

test('phase reader rejects oversized, invalid, truncated and stalled input without echo', async () => {
  for (const body of ['secret'.repeat(4000), 'not-json-secret\n', '{"password":"secret"}']) {
    const input = new PhaseInput(Readable.from([body]), { timeoutMs: 500 })
    await assert.rejects(input.read(), (error) => !error.message.includes('secret'))
  }
  const stream = new PassThrough()
  const input = new PhaseInput(stream, { timeoutMs: 10 })
  await assert.rejects(input.read(), /timed out/)
  stream.destroy()
})

test('fixture input is closed and only accepts its loopback origin and exact identifiers', () => {
  const id = '11111111-1111-4111-8111-111111111111'
  const valid = {
    base: 'http://127.0.0.1:58081',
    organizationId: id,
    locationId: id,
    userId: id,
    password: 'synthetic',
    datasetIncarnation: id,
    historicalCustomerId: id,
  }
  assert.deepEqual(validateInput(valid), valid)
  for (const change of [
    { base: 'https://operator.example.test' },
    { base: 'http://127.0.0.1:80/path' },
    { password: '' },
    { userId: 'unknown' },
    { token: 'secret' },
  ])
    assert.throws(() => validateInput({ ...valid, ...change }))
})

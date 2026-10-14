import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { PassThrough, Readable } from 'node:stream'
import test from 'node:test'
import { fileURLToPath } from 'node:url'
import { PhaseInput, validateInput } from '../../scripts/ci/local_runtime_browser_smoke.mjs'

const smokeUrl = new URL('../../scripts/ci/local_runtime_browser_smoke.mjs', import.meta.url)

test('offline smoke diagnostics identify each fixed bounded stage without exposing values', () => {
  const source = readFileSync(smokeUrl, 'utf8')
  const start = source.indexOf("    step = 'offline_event'")
  assert.notEqual(start, -1)
  const end = source.indexOf("    step = 'reconnect_and_convergence'", start)
  assert.notEqual(end, -1)
  const offline = source.slice(start, end)
  const expected = [
    ['offline_event', 'await context.setOffline(true)'],
    ['offline_ui_state', "await expect(page.getByLabel('Estado de sincronización'))"],
    ['offline_create', 'await create(customerName)'],
    ['offline_journal_delivery', 'const beforeReload = await snapshot(page)'],
    ['offline_reload', "await page.reload({ waitUntil: 'domcontentloaded' })"],
    ['offline_readmission', 'await ready(page)'],
    ['offline_reloaded_ui_state', "await expect(page.getByLabel('Estado de sincronización'))"],
    ['offline_reloaded_projection', 'getByText(customerName, { exact: true })'],
    ['offline_preserved_journal', 'assert.deepEqual(afterReload.journal, beforeReload.journal)'],
    ['offline_preserved_events', 'assert.deepEqual(afterReload.events, beforeReload.events)'],
    ['offline_pending_delivery', "assert.equal(afterReload.delivery[0].state, 'pending')"],
    ['offline_preserved_session', 'assert.equal((await session(page)).bindingId'],
    ['offline_backend_navigation', 'assert.equal(offlineApiFailed, true)'],
    ['offline_backend_no_spa', "assert.equal(await probe.locator('#root').count(), 0)"],
  ]
  const assignments = [...offline.matchAll(/^ {4}step = '([^']+)'$/gm)]
  assert.deepEqual(
    assignments.map((match) => match[1]),
    expected.map(([label]) => label),
  )
  for (let index = 0; index < assignments.length; index++) {
    const [label, assertion] = expected[index]
    assert.match(label, /^[a-z_]{1,64}$/)
    const next = assignments[index + 1]?.index ?? offline.length
    assert.ok(offline.slice(assignments[index].index, next).includes(assertion), label)
  }
  // Every phase assignment remains a static literal; no error or fixture data
  // may become part of the failed envelope sent to the Python supervisor.
  const allAssignments = source.split('\n').filter((line) => /^\s*(?:let )?step =/.test(line))
  assert.ok(allAssignments.every((line) => /^\s*(?:let )?step = '[a-z_]{1,64}'$/.test(line)))
  assert.ok(source.includes("JSON.stringify({ phase: 'failed', step }) + '\\n'"))
})

test('failed child envelope excludes raw invalid input and assertion diagnostics', () => {
  const secret = 'synthetic-private-fixture-must-not-be-logged'
  const result = spawnSync(process.execPath, [fileURLToPath(smokeUrl)], {
    input: JSON.stringify({ password: secret, token: secret, session: { token: secret } }) + '\n',
    encoding: 'utf8',
    timeout: 5000,
  })
  assert.equal(result.status, 1)
  assert.equal(result.stderr, '')
  assert.equal(result.stdout, '{"phase":"failed","step":"fixture_input"}\n')
  assert.equal((result.stdout + result.stderr).includes(secret), false)
})

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

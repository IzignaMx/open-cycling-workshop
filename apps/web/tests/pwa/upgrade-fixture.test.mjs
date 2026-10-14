import assert from 'node:assert/strict'
import test from 'node:test'
import { createServer, request } from 'node:http'
import { once } from 'node:events'
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import {
  fixtureAsset,
  startUpgradeFixture,
} from '../../../../scripts/e2e/upgrade_fixture_server.mjs'

test('old-client fixture serves only bounded static paths and never API navigation fallback', () => {
  assert.equal(fixtureAsset('/'), 'index.html')
  assert.equal(fixtureAsset('/workshop/active'), 'index.html')
  assert.equal(fixtureAsset('/sw.js'), 'sw.js')
  assert.equal(fixtureAsset('/assets/old.js'), 'assets/old.js')
  for (const path of [
    '/api',
    '/api/v1/customers',
    '/health/ready',
    '/../package.json',
    '/assets/%2e%2e/secret',
    '//external',
  ])
    assert.equal(fixtureAsset(path), null)
})

// Synthetic loopback servers exercise the actual proxy. They are not historical
// App/SW artifacts and never enter the pinned build's output directories.

const MUTATIONS = '/api/v1/sync/mutations'
const requestId = (n) => `req-${n.toString(16).padStart(32, '0')}`
const refusal = JSON.stringify({ error: { code: 'client_upgrade_required' } })

async function proxyFixture(t, respond) {
  const directory = mkdtempSync(join(tmpdir(), 'ocwp-synthetic-proxy-'))
  const old = join(directory, 'old'),
    fresh = join(directory, 'current')
  for (const path of [old, fresh]) {
    mkdirSync(path)
    writeFileSync(join(path, 'sw.js'), '// Synthetic test only; not an archived service worker.\n')
  }
  const upstream = createServer(respond)
  upstream.listen(0, '127.0.0.1')
  await once(upstream, 'listening')
  let server
  t.after(async () => {
    for (const current of [server, upstream]) {
      if (!current) continue
      current.closeAllConnections()
      await new Promise((resolve) => current.close(resolve))
    }
    rmSync(directory, { recursive: true, force: true })
  })
  assert.doesNotThrow(() => {
    server = startUpgradeFixture(0, {
      legacyDirectory: old,
      currentDirectory: fresh,
      apiPort: upstream.address().port,
    })
  }, 'loopback proxy accepts explicitly isolated synthetic assets and upstream')
  await once(server, 'listening')
  return `http://127.0.0.1:${server.address().port}`
}

function reply(res, id, body = refusal, status = 409, headers = {}) {
  res.writeHead(status, {
    'content-type': 'application/json',
    'content-length': Buffer.byteLength(body),
    'cache-control': 'no-store',
    'x-request-id': id,
    ...headers,
  })
  res.end(body)
}

async function evidence(base, id) {
  const response = await fetch(`${base}/__fixture/refusal/${id}`)
  return { status: response.status, value: response.ok ? await response.json() : null }
}

test('proxy observes the same real 409 while its downstream body remains unread', async (t) => {
  const body = JSON.stringify({ error: { code: 'client_upgrade_required', detail: 'omit-this' } })
  let forwarded = 0
  let incomingBody = ''
  const base = await proxyFixture(t, (req, res) => {
    forwarded += 1
    req.setEncoding('utf8')
    req.on('data', (chunk) => {
      incomingBody += chunk
    })
    req.on('end', () => reply(res, requestId(1), body))
  })
  const outgoing = request(`${base}${MUTATIONS}`, { method: 'POST' })
  const received = once(outgoing, 'response')
  outgoing.end('{"mutations":[]}')
  const [response] = await received
  // Deliberately do not consume the old client's response yet. The observer
  // must not depend on Playwright/Chromium completing that downstream body.
  assert.equal(response.statusCode, 409)
  assert.equal(response.headers['x-request-id'], requestId(1))
  assert.equal(response.headers['cache-control'], 'no-store')
  assert.deepEqual(await evidence(base, response.headers['x-request-id']), {
    status: 200,
    value: {
      requestId: requestId(1),
      method: 'POST',
      path: MUTATIONS,
      status: 409,
      code: 'client_upgrade_required',
    },
  })
  const chunks = []
  for await (const chunk of response) chunks.push(chunk)
  assert.equal(Buffer.concat(chunks).toString(), body)
  assert.equal(incomingBody, '{"mutations":[]}')
  assert.equal(forwarded, 1, 'evidence lookup never repeats the mutation')
})

for (const scenario of [
  { name: 'other method', method: 'GET' },
  { name: 'other route', path: '/api/v1/customers' },
  { name: 'query-suffixed route', path: `${MUTATIONS}?unrelated=1` },
  { name: 'other status', status: 200 },
  { name: 'unknown refusal code', body: '{"error":{"code":"secret-not-allowed"}}' },
  { name: 'missing error code', body: '{}' },
  { name: 'malformed JSON', body: '{' },
  { name: 'non-JSON media type', headers: { 'content-type': 'text/plain' } },
  { name: 'encoded body', headers: { 'content-encoding': 'unknown' } },
  { name: 'invalid request ID', id: 'not-a-server-request-id' },
  {
    name: 'oversized body',
    body: JSON.stringify({ error: { code: 'client_upgrade_required' }, extra: 'x'.repeat(4096) }),
  },
]) {
  test(`refusal evidence fails closed for ${scenario.name}`, async (t) => {
    const id = scenario.id ?? requestId(2)
    const base = await proxyFixture(t, (_req, res) => {
      reply(res, id, scenario.body ?? refusal, scenario.status ?? 409, scenario.headers)
    })
    const result = await fetch(`${base}${scenario.path ?? MUTATIONS}`, {
      method: scenario.method ?? 'POST',
    })
    // Unknown content encoding is deliberately invalid observation metadata.
    // Node's fetch does not decode this unknown encoding, so the original bytes
    // must still pass through unchanged.
    assert.equal(await result.text(), scenario.body ?? refusal)
    assert.deepEqual(await evidence(base, id), { status: 404, value: null })
  })
}

test('absent and duplicate request IDs cannot borrow a valid refusal', async (t) => {
  let count = 0
  const base = await proxyFixture(t, (_req, res) => {
    count += 1
    reply(res, requestId(3))
  })
  await (await fetch(`${base}${MUTATIONS}`, { method: 'POST' })).text()
  assert.equal((await evidence(base, requestId(3))).status, 200)
  assert.deepEqual(await evidence(base, requestId(4)), { status: 404, value: null })
  await (await fetch(`${base}${MUTATIONS}`, { method: 'POST' })).text()
  assert.deepEqual(await evidence(base, requestId(3)), { status: 404, value: null })
  assert.equal(count, 2)
})

test('observation waits for complete upstream bytes and preserves chunked forwarding', async (t) => {
  let finish
  const released = new Promise((resolve) => {
    finish = resolve
  })
  const base = await proxyFixture(t, async (_req, res) => {
    res.writeHead(409, {
      'content-type': 'application/json',
      'content-length': Buffer.byteLength(refusal),
      'x-request-id': requestId(5),
      'cache-control': 'no-store',
    })
    res.write(refusal.slice(0, 10))
    await released
    res.end(refusal.slice(10))
  })
  const response = await fetch(`${base}${MUTATIONS}`, { method: 'POST' })
  assert.deepEqual(await evidence(base, requestId(5)), { status: 404, value: null })
  finish()
  assert.equal(await response.text(), refusal)
  assert.equal((await evidence(base, requestId(5))).status, 200)
})

test('observation fails closed when its 32-request capacity is exceeded', async (t) => {
  let count = 0
  const base = await proxyFixture(t, (_req, res) => {
    reply(res, requestId(++count))
  })
  for (let n = 1; n <= 32; n += 1) {
    assert.equal(await (await fetch(`${base}${MUTATIONS}`, { method: 'POST' })).text(), refusal)
  }
  assert.equal((await evidence(base, requestId(1))).status, 200)
  assert.equal((await evidence(base, requestId(32))).status, 200)
  await (await fetch(`${base}${MUTATIONS}`, { method: 'POST' })).text()
  for (const id of [1, 32, 33])
    assert.deepEqual(await evidence(base, requestId(id)), { status: 404, value: null })
})

test('an incomplete upstream response never becomes refusal evidence', async (t) => {
  let interrupt
  const interrupted = new Promise((resolve) => {
    interrupt = resolve
  })
  let closed
  const upstreamClosed = new Promise((resolve) => {
    closed = resolve
  })
  const base = await proxyFixture(t, async (_req, res) => {
    res.writeHead(409, {
      'content-type': 'application/json',
      'content-length': Buffer.byteLength(refusal) + 1,
      'x-request-id': requestId(6),
    })
    res.write(refusal)
    await interrupted
    res.once('close', closed)
    res.destroy()
  })
  const response = await fetch(`${base}${MUTATIONS}`, { method: 'POST' })
  assert.deepEqual(await evidence(base, requestId(6)), { status: 404, value: null })
  interrupt()
  await upstreamClosed
  assert.deepEqual(await evidence(base, requestId(6)), { status: 404, value: null })
  await response.body.cancel()
})

test('a duplicate in-flight request ID stays invalid when the first response later completes', async (t) => {
  let finish
  const released = new Promise((resolve) => {
    finish = resolve
  })
  let count = 0
  const base = await proxyFixture(t, async (_req, res) => {
    if (++count > 1) {
      reply(res, requestId(7))
      return
    }
    res.writeHead(409, {
      'content-type': 'application/json',
      'content-length': Buffer.byteLength(refusal),
      'x-request-id': requestId(7),
    })
    res.write(refusal.slice(0, 10))
    await released
    res.end(refusal.slice(10))
  })
  const first = await fetch(`${base}${MUTATIONS}`, { method: 'POST' })
  await (await fetch(`${base}${MUTATIONS}`, { method: 'POST' })).text()
  assert.deepEqual(await evidence(base, requestId(7)), { status: 404, value: null })
  finish()
  assert.equal(await first.text(), refusal)
  assert.deepEqual(await evidence(base, requestId(7)), { status: 404, value: null })
})

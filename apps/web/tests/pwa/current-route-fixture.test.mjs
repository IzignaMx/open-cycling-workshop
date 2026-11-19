import assert from 'node:assert/strict'
import test from 'node:test'
import { createServer } from 'node:http'
import { once } from 'node:events'
import { mkdtempSync, writeFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { startCurrentRouteFixture } from '../../../../scripts/e2e/current_route_fixture_server.mjs'

test('dedicated current fixture keeps exact App/SW while closing only its own API route', async (t) => {
  const dist = mkdtempSync(join(tmpdir(), 'ocwp-current-route-'))
  writeFileSync(join(dist, 'sw.js'), '// current synthetic SW')
  writeFileSync(join(dist, 'index.html'), '<html>current synthetic App</html>')
  let forwarded = 0
  const upstream = createServer((_req, res) => {
    forwarded += 1
    res.end('server available')
  })
  upstream.listen(0, '127.0.0.1')
  await once(upstream, 'listening')
  const a = startCurrentRouteFixture(0, { directory: dist, apiPort: upstream.address().port })
  const b = startCurrentRouteFixture(0, { directory: dist, apiPort: upstream.address().port })
  await Promise.all([once(a, 'listening'), once(b, 'listening')])
  t.after(async () => {
    for (const server of [a, b, upstream]) {
      server.closeAllConnections()
      await new Promise((resolve) => server.close(resolve))
    }
    rmSync(dist, { recursive: true, force: true })
  })
  const url = (server) => `http://127.0.0.1:${server.address().port}`
  const A = url(a),
    B = url(b)
  assert.equal((await fetch(`${A}/__fixture/api-isolation/close`, { method: 'POST' })).status, 200)
  await assert.rejects(fetch(`${A}/api/v1/customers/fixture`), /fetch failed/)
  assert.equal(await (await fetch(`${B}/api/v1/customers/fixture`)).text(), 'server available')
  assert.equal(forwarded, 1)
  assert.deepEqual(await (await fetch(`${A}/__fixture/api-isolation`)).json(), {
    closed: true,
    active: 0,
    forwarded: 0,
    blocked: 1,
  })
  for (const asset of ['/', '/sw.js']) {
    const before = await (await fetch(`${A}${asset}`)).text()
    assert.equal(before, await (await fetch(`${B}${asset}`)).text())
    await fetch(`${A}/__fixture/current`, { method: 'POST' })
    assert.equal(
      await (await fetch(`${A}${asset}`)).text(),
      before,
      'no alternate historical distribution exists',
    )
  }
  assert.equal((await fetch(`${A}/__fixture/api-isolation/open`, { method: 'POST' })).status, 200)
  assert.equal(await (await fetch(`${A}/api/v1/customers/fixture`)).text(), 'server available')
  assert.equal(forwarded, 2)
})

test('socket-drop drains earlier forwarding and does not match API-like asset paths', async (t) => {
  const dist = mkdtempSync(join(tmpdir(), 'ocwp-current-drain-'))
  writeFileSync(join(dist, 'sw.js'), '// synthetic')
  writeFileSync(join(dist, 'index.html'), 'synthetic App')
  let finish, entered
  const started = new Promise((resolve) => {
    entered = resolve
  })
  const upstream = createServer((_req, res) => {
    finish = () => res.end('completed')
    entered()
  })
  upstream.listen(0, '127.0.0.1')
  await once(upstream, 'listening')
  const host = startCurrentRouteFixture(0, { directory: dist, apiPort: upstream.address().port })
  await once(host, 'listening')
  t.after(async () => {
    for (const server of [host, upstream]) {
      server.closeAllConnections()
      await new Promise((resolve) => server.close(resolve))
    }
    rmSync(dist, { recursive: true, force: true })
  })
  const base = `http://127.0.0.1:${host.address().port}`
  const control = (action) => fetch(`${base}/__fixture/api-isolation/${action}`, { method: 'POST' })
  const state = async () => (await fetch(`${base}/__fixture/api-isolation`)).json()
  const pending = fetch(`${base}/api/v1/control`, { method: 'POST' })
  await started
  assert.deepEqual(await (await control('close')).json(), {
    closed: true,
    forwarded: 1,
    active: 1,
    blocked: 0,
  })
  assert.equal((await control('open')).status, 409)
  for (const [path, method] of [
    ['/api', 'DELETE'],
    ['/api/v1/auth/login', 'POST'],
    ['/api/v1/sync/changes?cursor=0', 'GET'],
  ])
    await assert.rejects(fetch(`${base}${path}`, { method }), /fetch failed/)
  for (const path of ['/apiary', '/api-like', '/sw.js', '/__fixture/ready'])
    assert.equal((await fetch(`${base}${path}`)).status, 200)
  assert.deepEqual(await state(), { closed: true, forwarded: 1, active: 1, blocked: 3 })
  finish()
  assert.equal(await (await pending).text(), 'completed')
  assert.deepEqual(await state(), { closed: true, forwarded: 1, active: 0, blocked: 3 })
  assert.equal((await control('open')).status, 200)
  assert.equal((await control('open')).status, 409)
})

test('unknown closed API behavior fails before opening a host', async () => {
  const { startUpgradeFixture } = await import('../../../../scripts/e2e/upgrade_fixture_server.mjs')
  assert.throws(
    () => startUpgradeFixture(0, { closedApiBehavior: 'silently-online' }),
    /Unsupported synthetic closed API behavior/,
  )
})

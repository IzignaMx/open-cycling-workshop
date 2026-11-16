import { test } from 'node:test'
import assert from 'node:assert/strict'
import { mkdtempSync, mkdirSync, writeFileSync, rmSync, unlinkSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { createHash } from 'node:crypto'
import * as host from './capture_app_server.mjs'
const hash = (value) => createHash('sha256').update(value).digest('hex')
function fixture(t) {
  const root = mkdtempSync(join(tmpdir(), 'capture-admission-'))
  t.after(() => rmSync(root, { recursive: true, force: true }))
  const files = {
    'index.html': 'current HTML',
    'sw.js': 'current worker',
    'manifest.webmanifest': '{}',
    'assets/app.js': 'current app',
  }
  const expected = {
    source_commit: 'a'.repeat(40),
    source_tree: 'b'.repeat(40),
    lock_sha256: 'c'.repeat(64),
    database: 'ocwp-authenticated-v1',
    assets: Object.fromEntries(
      Object.entries(files).map(([p, s]) => [p, { bytes: Buffer.byteLength(s), sha256: hash(s) }]),
    ),
  }
  function write(name, evidence = expected, values = files) {
    const dir = join(root, name)
    mkdirSync(join(dir, 'dist/assets'), { recursive: true })
    writeFileSync(join(dir, 'evidence.json'), JSON.stringify(evidence))
    for (const [p, s] of Object.entries(values)) writeFileSync(join(dir, 'dist', p), s)
    return dir
  }
  return { expected, files, write, good: write('good') }
}
test('admission refuses serving before a complete snapshot is admitted', (t) => {
  const f = fixture(t),
    gate = host.createCaptureAppAdmission(f.expected)
  assert.equal(gate.respond('GET', '/').status, 503)
  gate.replace(f.good)
  assert.equal(gate.respond('GET', '/').body.toString(), f.files['index.html'])
})
for (const scenario of ['historical', 'mixed', 'corrupt', 'forged', 'missing', 'extra']) {
  test(`admission rejects ${scenario} artifacts and retains prior snapshot`, (t) => {
    const f = fixture(t),
      gate = host.createCaptureAppAdmission(f.expected)
    gate.replace(f.good)
    const evidence = structuredClone(f.expected),
      values = { ...f.files }
    if (scenario === 'historical') evidence.source_commit = 'd'.repeat(40)
    if (scenario === 'mixed' || scenario === 'corrupt')
      values[scenario === 'mixed' ? 'sw.js' : 'assets/app.js'] = 'incompatible'
    if (scenario === 'forged') {
      values['sw.js'] = 'old worker'
      evidence.assets['sw.js'] = { bytes: 10, sha256: hash('old worker') }
    }
    if (scenario === 'extra') {
      values['old.js'] = 'old'
      evidence.assets['old.js'] = { bytes: 3, sha256: hash('old') }
    }
    const bad = f.write('bad', evidence, values)
    if (scenario === 'missing') unlinkSync(join(bad, 'dist/sw.js'))
    assert.throws(() => gate.replace(bad))
    assert.equal(gate.respond('GET', '/sw.js').body.toString(), 'current worker')
    assert.equal(gate.respond('GET', '/old.js').status, 404)
  })
}
test('disk replacement after admission cannot change any served byte', (t) => {
  const f = fixture(t),
    gate = host.createCaptureAppAdmission(f.expected)
  gate.replace(f.good)
  writeFileSync(join(f.good, 'dist/sw.js'), 'replaced')
  writeFileSync(join(f.good, 'evidence.json'), '{}')
  rmSync(join(f.good, 'dist/assets'), { recursive: true })
  assert.equal(gate.respond('GET', '/sw.js').body.toString(), 'current worker')
  assert.equal(gate.respond('GET', '/assets/app.js').body.toString(), 'current app')
  assert.deepEqual(JSON.parse(gate.respond('GET', '/evidence.json').body), f.expected)
})
test('caller mutations cannot alter trusted policy or admitted responses', (t) => {
  const f = fixture(t),
    gate = host.createCaptureAppAdmission(f.expected)
  gate.replace(f.good)
  f.expected.source_commit = 'd'.repeat(40)
  f.expected.assets['sw.js'].sha256 = hash('old')
  gate.respond('GET', '/sw.js').body.fill(0)
  assert.equal(gate.respond('GET', '/sw.js').body.toString(), 'current worker')
  gate.replace(f.good)
})
test('all entry points use snapshot admission and unknown routes fail closed', (t) => {
  const f = fixture(t),
    gate = host.createCaptureAppAdmission(f.expected)
  gate.replace(f.good)
  for (const p of [
    '/',
    '/index.html',
    '/sw.js?update=1',
    '/manifest.webmanifest',
    '/assets/app.js',
  ])
    assert.equal(gate.respond('GET', p).status, 200)
  for (const p of ['/fallback', '/old.js', '/api/login', '/%2e%2e/sw.js', '//sw.js'])
    assert.equal(gate.respond('GET', p).status, 404)
  assert.equal(gate.respond('POST', '/sw.js').status, 404)
})

test('canonical candidate selfmanifest and bytes cannot rewrite frozen admission policy', (t) => {
  const f = fixture(t)
  const gate = host.createCaptureAppAdmission(f.expected)
  gate.replace(f.good)
  const forged = structuredClone(f.expected)
  forged.assets['sw.js'] = { bytes: 3, sha256: hash('old') }
  writeFileSync(join(f.good, 'dist/sw.js'), 'old')
  writeFileSync(join(f.good, 'evidence.json'), JSON.stringify(forged))
  assert.throws(() => gate.replace(f.good), /Full asset map/)
  assert.equal(gate.respond('GET', '/sw.js').body.toString(), 'current worker')
  assert.throws(() => host.startCaptureAppServer(f.good, 5181, f.expected), /Full asset map/)
})

for (const [field, value] of [
  ['source_tree', 'd'.repeat(40)],
  ['lock_sha256', 'd'.repeat(64)],
  ['database', 'ocwp'],
]) {
  test(`candidate ${field} mismatch is refused before startup and replacement`, (t) => {
    const f = fixture(t)
    const bad = f.write('wrong-pin', { ...f.expected, [field]: value })
    assert.throws(() => host.startCaptureAppServer(bad, 5181, f.expected), new RegExp(field))
    const gate = host.createCaptureAppAdmission(f.expected)
    gate.replace(f.good)
    assert.throws(() => gate.replace(bad), new RegExp(field))
    assert.equal(gate.respond('GET', '/sw.js').body.toString(), 'current worker')
  })
}

for (const name of [
  '../escape.js',
  '/absolute.js',
  'a\\escape.js',
  '%2e%2e/escape.js',
  'worker.js?replacement=1',
  'worker.js#fragment',
  'evidence.json',
]) {
  test(`policy refuses unsafe or reserved asset key ${JSON.stringify(name)}`, (t) => {
    const f = fixture(t)
    f.expected.assets[name] = { bytes: 1, sha256: hash('x') }
    assert.throws(() => host.createCaptureAppAdmission(f.expected))
  })
}

for (const metadata of [
  { bytes: -1, sha256: hash('x') },
  { bytes: 1.5, sha256: hash('x') },
  { bytes: 1, sha256: 'unverified' },
  { bytes: 1, sha256: hash('x'), trusted: true },
]) {
  test(`policy refuses malformed asset metadata ${JSON.stringify(metadata)}`, (t) => {
    const f = fixture(t)
    f.expected.assets['sw.js'] = metadata
    assert.throws(() => host.createCaptureAppAdmission(f.expected))
  })
}

test('absent or empty policy cannot admit a startup snapshot', (t) => {
  const f = fixture(t)
  for (const policy of [undefined, null, {}, { ...f.expected, assets: {} }]) {
    assert.throws(() => host.createCaptureAppAdmission(policy))
  }
  assert.throws(() => host.startCaptureAppServer(f.good, 5181, {}))
})

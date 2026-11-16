/** Disposable loopback host for actual archived App/SW bytes. No API proxy or SPA fallback. */
import { createServer } from 'node:http'
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { currentCaptureAppPin, validateCaptureAppPin } from './build_capture_app.mjs'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
export function captureAsset(raw) {
  let path
  try {
    path = decodeURIComponent(raw.split('?')[0])
  } catch {
    return null
  }
  if (
    !path.startsWith('/') ||
    path.startsWith('//') ||
    path.includes('\\') ||
    path.split('/').includes('..')
  )
    return null
  if (path === '/') return 'index.html'
  if (
    !/\.(?:html|js|css|json|webmanifest|svg|png|ico|woff2?)$/.test(path) ||
    path.startsWith('/api/')
  )
    return null
  return path.slice(1)
}
/** Exact build receipt is trusted input from the caller, never the candidate directory.
 * This test-only policy cannot retire historical caches or enforce a production floor.
 */
export function createCaptureAppAdmission(expected) {
  const policy = structuredClone(expected)
  assert.ok(policy && /^[a-f0-9]{40}$/.test(policy.source_commit))
  assert.match(policy.source_tree, /^[a-f0-9]{40}$/)
  assert.match(policy.lock_sha256, /^[a-f0-9]{64}$/)
  assert.equal(policy.database, 'ocwp-authenticated-v1')
  for (const required of ['index.html', 'sw.js', 'manifest.webmanifest'])
    assert.ok(Object.hasOwn(policy.assets, required))
  for (const [name, metadata] of Object.entries(policy.assets)) {
    assert.equal(captureAsset('/' + name), name, 'Unsafe or unsupported asset')
    assert.ok(!name.includes('?') && !name.includes('#') && name !== 'evidence.json')
    assert.ok(Number.isSafeInteger(metadata.bytes) && metadata.bytes >= 0)
    assert.match(metadata.sha256, /^[a-f0-9]{64}$/)
    assert.deepEqual(Object.keys(metadata).sort(), ['bytes', 'sha256'])
  }
  let snapshot = null
  return Object.freeze({
    replace(directory) {
      directory = directory instanceof URL ? fileURLToPath(directory) : directory
      const evidence = readFileSync(resolve(directory, 'evidence.json'))
      const actual = JSON.parse(evidence)
      for (const field of ['source_commit', 'source_tree', 'lock_sha256', 'database'])
        assert.equal(actual[field], policy[field], `Wrong ${field}`)
      assert.deepEqual(actual.assets, policy.assets, 'Full asset map must match admitted receipt')
      const next = new Map()
      for (const [name, metadata] of Object.entries(policy.assets)) {
        const bytes = readFileSync(resolve(directory, 'dist', name))
        assert.equal(bytes.byteLength, metadata.bytes, `Wrong length: ${name}`)
        assert.equal(
          createHash('sha256').update(bytes).digest('hex'),
          metadata.sha256,
          `Wrong hash: ${name}`,
        )
        next.set(name, bytes)
      }
      next.set('evidence.json', evidence)
      // No await, disk read, or candidate-dependent operation follows the atomic swap.
      snapshot = next
    },
    respond(method, raw) {
      const name = captureAsset(raw)
      const body = snapshot?.get(name)
      if (method !== 'GET' || !name || !body)
        return { status: snapshot ? 404 : 503, headers: {}, body: Buffer.alloc(0) }
      const type = name.endsWith('.html')
        ? 'text/html'
        : name.endsWith('.js')
          ? 'application/javascript'
          : name.endsWith('.css')
            ? 'text/css'
            : name.endsWith('.svg')
              ? 'image/svg+xml'
              : name.endsWith('.webmanifest') || name.endsWith('.json')
                ? 'application/json'
                : 'application/octet-stream'
      return {
        status: 200,
        headers: { 'Content-Type': type, 'Cache-Control': 'no-store' },
        body: Buffer.from(body),
      }
    },
  })
}
export function trustedCaptureAppEvidence(kind) {
  assert.ok(kind === 'old' || kind === 'current')
  const root = resolve(dirname(fileURLToPath(import.meta.url)), '../..')
  const expected =
    kind === 'current'
      ? currentCaptureAppPin(root)
      : validateCaptureAppPin(
          JSON.parse(readFileSync(resolve(root, 'fixtures/capture-app/manifest.json'), 'utf8')),
        )
  // This independent receipt is emitted by the successful archived builder, outside dist.
  // It is a trusted test-runner input, not an attestation against a hostile filesystem.
  const receipt = JSON.parse(
    readFileSync(resolve(root, `artifacts/capture-app-${kind}-admission.json`), 'utf8'),
  )
  for (const field of ['source_commit', 'source_tree', 'lock_sha256', 'database'])
    assert.equal(receipt[field], expected[field], `Wrong trusted receipt ${field}`)
  return receipt
}
export function startCaptureAppServer(directory, port, expected) {
  if (![5180, 5181].includes(port)) throw Error('Fixed disposable loopback ports required')
  // Select policy by intended origin role, not candidate directory or its claims.
  // Canonical receipts are produced by the archived build and checked against Git.
  const admission = createCaptureAppAdmission(
    expected ?? trustedCaptureAppEvidence(port === 5180 ? 'old' : 'current'),
  )
  admission.replace(directory) // Fail before constructing/listening on the server.
  const server = createServer((request, response) => {
    const result = admission.respond(request.method, request.url ?? '')
    response.writeHead(result.status, result.headers)
    response.end(result.body)
  })
  server.replaceCaptureApp = (candidate) => admission.replace(candidate)
  server.listen(port, '127.0.0.1')
  return server
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url))
  startCaptureAppServer(resolve(process.argv[2]), Number(process.argv[3]))

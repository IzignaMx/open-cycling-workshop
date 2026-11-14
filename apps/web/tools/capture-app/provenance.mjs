import { createHash } from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import assert from 'node:assert/strict'
const root = resolve(dirname(fileURLToPath(import.meta.url)), '../../../..')
export const oldCommit = 'cc18a203a8c754284fc14ef3570d94d7d98fac23'
export const hash = (bytes) => createHash('sha256').update(bytes).digest('hex')
export function validateEvidence(actual, expected, readAsset) {
  for (const field of ['source_commit', 'source_tree', 'lock_sha256', 'database'])
    assert.equal(actual[field], expected[field], `Wrong ${field}`)
  for (const path of ['index.html', 'sw.js', 'manifest.webmanifest'])
    assert.ok(Object.hasOwn(actual.assets, path), `Missing ${path}`)
  for (const [path, metadata] of Object.entries(actual.assets)) {
    assert.ok(
      path && !path.startsWith('/') && !path.includes('\\') && !path.split('/').includes('..'),
      'Unsafe asset path',
    )
    const bytes = readAsset(path)
    assert.equal(bytes.byteLength, metadata.bytes, `Wrong asset length: ${path}`)
    assert.equal(hash(bytes), metadata.sha256, `Wrong asset hash: ${path}`)
  }
  return actual
}
export function expectedEvidence(kind) {
  assert.ok(kind === 'old' || kind === 'current', 'Unknown fixture kind')
  const git = (...args) => execFileSync('git', args, { cwd: root })
  const commit = kind === 'old' ? oldCommit : git('rev-parse', 'HEAD').toString().trim()
  validateStartupBarrier(
    git('show', `${commit}:apps/web/src/runtime/controller.ts`).toString(),
    git('show', `${commit}:apps/web/src/App.tsx`).toString(),
  )
  const directory = resolve(root, 'artifacts', `capture-app-${kind}`)
  return validateEvidence(
    JSON.parse(readFileSync(resolve(directory, 'evidence.json'), 'utf8')),
    {
      source_commit: commit,
      source_tree: git('rev-parse', `${commit}^{tree}`).toString().trim(),
      lock_sha256: hash(git('show', `${commit}:pnpm-lock.yaml`)),
      database: 'ocwp-authenticated-v1',
    },
    (path) => readFileSync(resolve(directory, 'dist', path)),
  )
}

/** Source proof for an existing UI completion signal, not an injected runtime hook. */
export function validateStartupBarrier(controller, app) {
  const start = controller.slice(controller.indexOf('async start(): Promise<void>'))
  const body = start.slice(0, start.indexOf('const saved = this.sessionStore.getSnapshot()'))
  assert.match(controller, /legacyPresent:\s*false/)
  const cleanup = body.indexOf('await this.#captureRecovery.cleanup()')
  const inspect = body.indexOf('void inspectLegacyWork(this.options.factory ?? indexedDB)')
  const publish = body.indexOf('this.publish({ legacyPresent: present })')
  assert.ok(
    cleanup >= 0 && inspect > cleanup && publish > inspect,
    'Startup notice must follow awaited cleanup',
  )
  assert.match(body.slice(inspect, publish), /\.then\(\(present\) =>/)
  assert.match(
    app,
    /const legacy = state\.legacyPresent \? \([\s\S]*?role="status"[\s\S]*?Hay datos de una versión anterior/,
  )
  assert.match(app, /data-runtime-state=\{state\.phase\.toUpperCase\(\)\}[\s\S]*?\{legacy\}/)
}

import test from 'node:test'
import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { oldCommit, hash, validateEvidence, validateStartupBarrier } from './provenance.mjs'
const bytes = new TextEncoder().encode('synthetic')
const expected = {
  source_commit: 'a'.repeat(40),
  source_tree: 'b'.repeat(40),
  lock_sha256: 'c'.repeat(64),
  database: 'ocwp-authenticated-v1',
}
const fixture = () => ({
  ...expected,
  assets: Object.fromEntries(
    ['index.html', 'sw.js', 'manifest.webmanifest'].map((path) => [
      path,
      { bytes: bytes.length, sha256: hash(bytes) },
    ]),
  ),
})
test('accepts independently pinned source and exact local asset bytes', () =>
  assert.equal(validateEvidence(fixture(), expected, () => bytes).database, expected.database))
for (const field of Object.keys(expected))
  test(`rejects wrong ${field}`, () =>
    assert.throws(() =>
      validateEvidence({ ...fixture(), [field]: 'wrong' }, expected, () => bytes),
    ))
test('rejects self-consistent served manifest with changed local bytes', () =>
  assert.throws(() =>
    validateEvidence(fixture(), expected, () => new TextEncoder().encode('tampered!')),
  ))
test('rejects missing SW asset', () => {
  const actual = fixture()
  delete actual.assets['sw.js']
  assert.throws(() => validateEvidence(actual, expected, () => bytes))
})
test('rejects path traversal', () => {
  const actual = fixture()
  actual.assets['../secret'] = actual.assets['sw.js']
  assert.throws(() => validateEvidence(actual, expected, () => bytes))
})

const root = fileURLToPath(new URL('../../../../', import.meta.url))
for (const commit of [oldCommit, 'HEAD']) {
  const source = (path) =>
    execFileSync('git', ['show', `${commit}:${path}`], { cwd: root, encoding: 'utf8' })
  const controller = source('apps/web/src/runtime/controller.ts')
  const app = source('apps/web/src/App.tsx')
  test(`startup completion notice follows awaited cleanup in ${commit}`, () =>
    validateStartupBarrier(controller, app))
  test(`rejects notice without awaited cleanup in ${commit}`, () =>
    assert.throws(() =>
      validateStartupBarrier(
        controller.replace(
          'await this.#captureRecovery.cleanup()',
          'void this.#captureRecovery.cleanup()',
        ),
        app,
      ),
    ))
}
test('native case installs inert sentinel and waits for completion before seed and after reload', () => {
  const spec = readFileSync(
    new URL('../../tests/access-kernel/capture-app-native.spec.ts', import.meta.url),
    'utf8',
  )
  const install = spec.indexOf('await installStartupBarrier(page, origin)')
  const navigate = spec.indexOf("await page.goto(origin, { waitUntil: 'networkidle' })", install)
  const barrier = spec.indexOf('await expect(legacyNotice(page)).toBeVisible()', navigate)
  const seed = spec.indexOf('const seeded = fixture(', barrier)
  assert.ok(install >= 0 && navigate > install && barrier > navigate && seed > barrier)
  const reload = spec.indexOf('await page.reload(')
  assert.ok(spec.indexOf('await expect(legacyNotice(page)).toBeVisible()', reload) > reload)
})

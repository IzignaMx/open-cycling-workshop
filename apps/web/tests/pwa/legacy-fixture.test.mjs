import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { createHash } from 'node:crypto'
import { resolve } from 'node:path'
import {
  validateLegacyPin,
  manifestForAssets,
} from '../../../../scripts/e2e/build_legacy_client.mjs'

const root = resolve(import.meta.dirname, '../../../..')
test('old App fixture is pinned to exact pre-cutover source and lock', () => {
  const pin = JSON.parse(readFileSync(resolve(root, 'fixtures/legacy-client/manifest.json')))
  assert.equal(pin.source_commit, '714342c60f4163c7b4c1ebec8433995dccbeea01')
  assert.equal(validateLegacyPin(pin).source_commit, pin.source_commit)
  assert.throws(() => validateLegacyPin({ ...pin, source_commit: 'main' }))
  assert.throws(() => validateLegacyPin({ ...pin, source_tree: 'unknown' }))
  assert.throws(() => validateLegacyPin({ ...pin, database: 'ocwp-authenticated-v1' }))
})
test('fixture evidence hashes actual old service worker and every built asset', () => {
  const manifest = manifestForAssets(
    new Map([
      ['index.html', Buffer.from('old-app')],
      ['sw.js', Buffer.from('old-worker')],
      ['assets/old.js', Buffer.from('old-source')],
      ['manifest.webmanifest', Buffer.from('{}')],
    ]),
  )
  assert.equal(manifest['sw.js'].sha256, createHash('sha256').update('old-worker').digest('hex'))
  assert.equal(manifest['assets/old.js'].bytes, 10)
  assert.throws(() => manifestForAssets(new Map([['index.html', Buffer.from('only-html')]])))
  assert.throws(() => manifestForAssets(new Map([['../sw.js', Buffer.from('bad')]])))
})

test('reused dependency lock matches exactly except the explicitly excluded test-only package', async () => {
  const { validateInstalledLock, legacyBuildEnvironment } =
    await import('../../../../scripts/e2e/build_legacy_client.mjs')
  const pinned = readFileSync(resolve(root, 'pnpm-lock.yaml'), 'utf8')
  assert.equal(validateInstalledLock(pinned, pinned).mode, 'identical-lock')
  const testOnlyRemoved = pinned
    .replace('      fake-indexeddb:\n        specifier: 6.2.5\n        version: 6.2.5\n', '')
    .replace(
      / {2}fake-indexeddb@6\.2\.5:\n {4}resolution: \{integrity: [^\n]+\}\n {4}engines: \{node: '>=18'\}\n\n/,
      '',
    )
    .replace('  fake-indexeddb@6.2.5: {}\n\n', '')
  assert.equal(
    validateInstalledLock(pinned, testOnlyRemoved).mode,
    'identical-build-lock-test-only-omission',
  )
  assert.throws(() =>
    validateInstalledLock(pinned, testOnlyRemoved.replaceAll('vite@8.1.5', 'vite@8.1.4')),
  )
  assert.throws(() => validateInstalledLock(pinned, `${pinned}\nunknown: true\n`))
  assert.equal(
    legacyBuildEnvironment({ NODE_ENV: 'development' }, 'v24.19.0').NODE_ENV,
    'production',
  )
  assert.throws(() => legacyBuildEnvironment({}, 'v20.19.0'))
})

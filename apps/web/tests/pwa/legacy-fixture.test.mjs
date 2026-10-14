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

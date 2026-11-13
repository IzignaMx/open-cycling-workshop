import test from 'node:test'
import assert from 'node:assert/strict'
import { mkdtemp, cp, readFile, writeFile, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { pathToFileURL } from 'node:url'
import { join } from 'node:path'
import { verifyHistoricalSources } from './prepare.mjs'
const original = new URL('../../tests/fixtures/capture-reader-cc18a203/', import.meta.url)
for (const mutation of ['none', 'source', 'declared_hash', 'commit', 'dexie', 'missing'])
  test(`historical harness input verification: ${mutation}`, async (t) => {
    const path = await mkdtemp(join(tmpdir(), 'capture-pin-'))
    t.after(() => rm(path, { recursive: true, force: true }))
    await cp(original, path, { recursive: true })
    const root = pathToFileURL(path + '/')
    const manifest = new URL('provenance.json', root)
    const p = JSON.parse(await readFile(manifest, 'utf8'))
    if (mutation === 'source')
      await writeFile(new URL('capture-checkpoint-store.ts', root), 'changed')
    if (mutation === 'declared_hash') p.files['capture-checkpoint.ts'] = '0'.repeat(64)
    if (mutation === 'commit') p.commit = '0'.repeat(40)
    if (mutation === 'dexie') p.dexie = 'unknown'
    if (mutation === 'missing') await rm(new URL('capture-checkpoint.ts', root))
    await writeFile(manifest, JSON.stringify(p))
    if (mutation === 'none')
      assert.equal((await verifyHistoricalSources(root)).provenance.commit, p.commit)
    else await assert.rejects(() => verifyHistoricalSources(root))
  })

test('page provenance assertion uses the same verified historical pin', async () => {
  const source = await readFile(
    new URL('../../tests/access-kernel/capture-native.spec.ts', import.meta.url),
    'utf8',
  )
  assert.match(source, /captureBoundaryHarness\.provenance\.commit\)\)\.toBe\(\s*pin\s*,?\s*\)/)
})

for (const mutation of [
  'none',
  'pin',
  'head',
  'source',
  'empty_assets',
  'bad_asset_hash',
  'extra_field',
])
  test(`artifact provenance bound to checkout: ${mutation}`, async () => {
    const { expectedProvenance, verifyArtifactProvenance } = await import('./prepare.mjs')
    const expected = await expectedProvenance()
    const actual = { ...structuredClone(expected), assets: { 'index-example.js': 'a'.repeat(64) } }
    if (mutation === 'pin') actual.historical.commit = '0'.repeat(40)
    if (mutation === 'head') actual.currentHead = '0'.repeat(40)
    if (mutation === 'source') actual.source['tools/capture-browser/main.ts'] = '0'.repeat(64)
    if (mutation === 'empty_assets') actual.assets = {}
    if (mutation === 'bad_asset_hash') actual.assets['index-example.js'] = 'invalid'
    if (mutation === 'extra_field') actual.extra = true
    if (mutation === 'none') assert.doesNotThrow(() => verifyArtifactProvenance(actual, expected))
    else assert.throws(() => verifyArtifactProvenance(actual, expected))
  })

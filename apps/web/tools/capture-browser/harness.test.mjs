import 'fake-indexeddb/auto'
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import ts from 'typescript'
import { createKernelDatabase } from '../../.tmp-kernel/src/access-kernel/database.js'
import * as current from '../../.tmp-kernel/src/access-kernel/capture-checkpoint-store.js'
import * as historical from './.tmp-legacy/capture-checkpoint-store.js'
const source = readFileSync(new URL('./main.ts', import.meta.url), 'utf8')
function harness() {
  const window = {}
  const output = ts.transpileModule(source, {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS },
  }).outputText
  const require = (path) => {
    if (path.endsWith('/database.js')) return { createKernelDatabase }
    if (path === './.tmp-legacy/capture-checkpoint-store.js') return historical
    if (path.endsWith('/capture-checkpoint-store.js')) return current
    if (path.endsWith('/provenance.json'))
      return JSON.parse(
        readFileSync(new URL('./.tmp-legacy/provenance.json', import.meta.url), 'utf8'),
      )
    throw Error('Unexpected harness import ' + path)
  }
  new Function('require', 'exports', 'window', output)(require, {}, window)
  return window.captureBoundaryHarness
}
test('harness refuses production names and refuses reseeding existing synthetic data', async () => {
  const h = harness()
  await assert.rejects(() => h.seed('ocwp-authenticated-v1', 'bad'), /Synthetic/)
  const name = 'capture-native-' + crypto.randomUUID()
  const before = await h.seed(name, 'control')
  await assert.rejects(() => h.seed(name, 'overwrite'), /Never overwrite/)
  assert.deepEqual(await h.snapshot(name), before)
})
test('actual harness creates valid unexpired matching future envelope and exact v1 control', async () => {
  const h = harness(),
    name = 'capture-native-' + crypto.randomUUID()
  const before = await h.seed(name, 'test')
  const future = before.contents.find((x) => x.channel === 'order'),
    checkpoint = before.checkpoints[0]
  assert.equal(future.format, 2)
  assert.equal(future.generation, checkpoint.generation)
  assert.equal(future.revision, checkpoint.order.revision)
  assert.equal(future.firstPersistedAt, 1000)
  assert.equal(future.expiresAt, 86401000)
  assert.equal(checkpoint.order.contentExpiresAt, future.expiresAt)
  assert.deepEqual(await h.sweep(name, 'current'), { kind: 'complete' })
  assert.equal((await h.load(name, 'current')).reason, 'unsupported_format')
  assert.deepEqual(await h.snapshot(name), before)
  await h.sweep(name, 'historical')
  assert.deepEqual(
    (await h.snapshot(name)).contents,
    before.contents.filter((x) => x.channel === 'customer'),
  )
  assert.equal((await h.load(name, 'historical')).contents.customer.draft.displayName, 'test')
})

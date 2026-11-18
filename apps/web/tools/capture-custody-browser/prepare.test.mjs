import test from 'node:test'
import assert from 'node:assert/strict'
import { verifyArtifactProvenance } from './prepare.mjs'
const expected = () => ({
  currentHead: 'a'.repeat(40),
  currentTree: 'a'.repeat(40),
  source: {
    'source.mjs': 'b'.repeat(64),
    'tools/source-transition/diagnostic.mjs': 'e'.repeat(64),
  },
  lockSha256: 'c'.repeat(64),
  scope: 'Synthetic custody and source diagnostic modules; not App/SW or authenticated handover',
  assets: {
    'index.html': { bytes: 12, sha256: 'd'.repeat(64) },
    'assets/main.js': { bytes: 23, sha256: 'e'.repeat(64) },
  },
})
test('accepts exact source-bound built artifact', () =>
  assert.doesNotThrow(() => verifyArtifactProvenance(expected(), expected())))
for (const [label, mutate] of [
  ['head', (x) => (x.currentHead = 'f'.repeat(40))],
  ['tree', (x) => (x.currentTree = 'f'.repeat(40))],
  ['source', (x) => (x.source['source.mjs'] = 'f'.repeat(64))],
  [
    'diagnostic source',
    (x) => (x.source['tools/source-transition/diagnostic.mjs'] = 'f'.repeat(64)),
  ],
  ['missing diagnostic source', (x) => delete x.source['tools/source-transition/diagnostic.mjs']],
  ['lock', (x) => (x.lockSha256 = 'f'.repeat(64))],
  ['asset hash', (x) => (x.assets['index.html'].sha256 = 'f'.repeat(64))],
  ['asset size', (x) => x.assets['index.html'].bytes++],
  ['missing asset', (x) => delete x.assets['assets/main.js']],
  ['extra asset', (x) => (x.assets['assets/extra.js'] = { bytes: 1, sha256: 'f'.repeat(64) })],
  ['scope', (x) => (x.scope = 'Production')],
  ['unknown field', (x) => (x.success = true)],
])
  test('rejects mismatched ' + label, () => {
    const x = expected()
    mutate(x)
    assert.throws(() => verifyArtifactProvenance(x, expected()))
  })
for (const path of [
  '../escape',
  '/index.html',
  'assets/../escape',
  'assets/.',
  'assets/..',
  'assets/x?query',
  'assets/x\\escape',
])
  test('rejects unsafe manifest path ' + path + ' even if both inputs agree', () => {
    const x = expected()
    x.assets[path] = { bytes: 1, sha256: 'f'.repeat(64) }
    assert.throws(() => verifyArtifactProvenance(x, x))
  })
test('rejects self-consistent malformed metadata', () => {
  for (const mutate of [
    (x) => (x.assets['index.html'].bytes = -1),
    (x) => (x.source = {}),
    (x) => (x.currentHead = 'wrong'),
    (x) => (x.assets['index.html'].sha256 = 'not-hash'),
  ]) {
    const x = expected()
    mutate(x)
    assert.throws(() => verifyArtifactProvenance(x, x))
  }
})

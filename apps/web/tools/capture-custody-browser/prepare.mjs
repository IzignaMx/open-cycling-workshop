import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { readFile, readdir, writeFile } from 'node:fs/promises'
import { spawnSync } from 'node:child_process'
import { fileURLToPath, pathToFileURL } from 'node:url'
const web = new URL('../../', import.meta.url)
const output = new URL('.tmp-capture-custody/', web)
const sha = (bytes) => createHash('sha256').update(bytes).digest('hex')
const scope =
  'Synthetic custody and source diagnostic modules; not App/SW or authenticated handover'
const digest = (v) => typeof v === 'string' && /^[a-f0-9]{64}$/.test(v)
const safe = (path) => path === 'index.html' || /^assets\/[a-zA-Z0-9][a-zA-Z0-9_.-]*$/.test(path)
async function paths(dir, prefix = '') {
  const result = []
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    if (entry.name.startsWith('.')) continue
    const path = prefix + entry.name
    if (entry.isDirectory())
      result.push(...(await paths(new URL(entry.name + '/', dir), path + '/')))
    else if (entry.isFile()) result.push(path)
    else throw Error('Unexpected nonregular fixture file')
  }
  return result.sort()
}
async function sourceProvenance() {
  const files = [
    'package.json',
    'playwright.capture-custody.config.ts',
    'tsconfig.capture-custody.json',
    'tsconfig.kernel-test.json',
    'tests/access-kernel/baseline-fixture.mjs',
    'tests/access-kernel/capture-custody-native.spec.ts',
  ]
  for (const dir of [
    'src/',
    'tools/capture-handover/',
    'tools/source-transition/',
    'tools/capture-custody-browser/',
  ])
    for (const path of await paths(new URL(dir, web))) files.push(dir + path)
  const source = {}
  for (const path of files.sort()) source[path] = sha(await readFile(new URL(path, web)))
  const git = spawnSync('git', ['rev-parse', 'HEAD', 'HEAD^{tree}'], {
    cwd: fileURLToPath(web),
    encoding: 'utf8',
  })
  assert.equal(git.status, 0)
  return {
    currentHead: git.stdout.trim().split('\n')[0],
    currentTree: git.stdout.trim().split('\n')[1],
    source,
    lockSha256: sha(await readFile(new URL('../../pnpm-lock.yaml', web))),
    scope,
  }
}
async function assets() {
  const result = {}
  for (const path of await paths(output)) {
    if (path === 'provenance.json') continue
    assert.ok(safe(path), 'Unexpected built asset path: ' + path)
    const bytes = await readFile(new URL(path, output))
    result[path] = { bytes: bytes.length, sha256: sha(bytes) }
  }
  assert.ok(result['index.html'])
  return result
}
export async function expectedProvenance() {
  return { ...(await sourceProvenance()), assets: await assets() }
}
export function verifyArtifactProvenance(actual, expected) {
  for (const value of [actual, expected]) {
    assert.ok(value && typeof value === 'object' && !Array.isArray(value))
    assert.deepEqual(Object.keys(value).sort(), [
      'assets',
      'currentHead',
      'currentTree',
      'lockSha256',
      'scope',
      'source',
    ])
    assert.match(value.currentHead, /^[a-f0-9]{40}$/)
    assert.match(value.currentTree, /^[a-f0-9]{40}$/)
    assert.ok(digest(value.lockSha256))
    assert.equal(value.scope, scope)
    assert.ok(value.source && Object.keys(value.source).length > 0)
    for (const hash of Object.values(value.source)) assert.ok(digest(hash))
    assert.ok(value.assets?.['index.html'])
    for (const [path, asset] of Object.entries(value.assets)) {
      assert.ok(safe(path))
      assert.deepEqual(Object.keys(asset).sort(), ['bytes', 'sha256'])
      assert.ok(Number.isSafeInteger(asset.bytes) && asset.bytes >= 0)
      assert.ok(digest(asset.sha256))
    }
  }
  assert.deepEqual(actual, expected)
}
export async function build() {
  const before = await sourceProvenance()
  for (const args of [
    ['node_modules/typescript/bin/tsc', '-p', 'tsconfig.kernel-test.json', '--pretty', 'false'],
    [
      'node_modules/vite/bin/vite.js',
      'build',
      '--config',
      'tools/capture-custody-browser/vite.config.ts',
    ],
  ]) {
    const r = spawnSync(process.execPath, args, { cwd: fileURLToPath(web), stdio: 'inherit' })
    assert.equal(r.status, 0, 'Custody build failed')
  }
  assert.deepEqual(await sourceProvenance(), before, 'Source changed during build')
  const evidence = { ...before, assets: await assets() }
  verifyArtifactProvenance(evidence, evidence)
  await writeFile(new URL('provenance.json', output), JSON.stringify(evidence, null, 2) + '\n')
  return evidence
}
if (process.argv[1] && pathToFileURL(process.argv[1]).href === import.meta.url) {
  assert.deepEqual(process.argv.slice(2), ['--build'])
  const evidence = await build()
  console.log(
    JSON.stringify({ currentHead: evidence.currentHead, assets: Object.keys(evidence.assets) }),
  )
}

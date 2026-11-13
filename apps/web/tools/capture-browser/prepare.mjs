import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { readFile, mkdir, writeFile, readdir } from 'node:fs/promises'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { spawnSync } from 'node:child_process'
import ts from 'typescript'

const web = new URL('../../', import.meta.url)
export const pin = 'cc18a203a8c754284fc14ef3570d94d7d98fac23'
const expected = {
  'capture-checkpoint-store.ts': '301fe2b313e1f8fdc059fd8b885c187afa3c654221b08d1322c37cdabad12a75',
  'capture-checkpoint.ts': '07ea37dfc0dbb72572d2d002d7890cf4040de321da7031b34ed1988fba9b2003',
}
const sha = (bytes) => createHash('sha256').update(bytes).digest('hex')
export async function verifyHistoricalSources(root) {
  const provenance = JSON.parse(await readFile(new URL('provenance.json', root), 'utf8'))
  assert.equal(provenance.commit, pin)
  assert.equal(provenance.dexie, '4.4.4')
  assert.deepEqual(provenance.files, expected)
  const sources = {}
  for (const [file, hash] of Object.entries(expected)) {
    sources[file] = await readFile(new URL(file, root), 'utf8')
    assert.equal(sha(sources[file]), hash, `Historical source mismatch: ${file}`)
  }
  return { provenance, sources }
}
export async function prepare() {
  const { provenance, sources } = await verifyHistoricalSources(
    new URL('tests/fixtures/capture-reader-cc18a203/', web),
  )
  const dexie = JSON.parse(await readFile(new URL('node_modules/dexie/package.json', web), 'utf8'))
  assert.equal(dexie.version, provenance.dexie)
  const target = new URL('.tmp-legacy/', import.meta.url)
  await mkdir(target, { recursive: true })
  for (const [file, source] of Object.entries(sources))
    await writeFile(
      new URL(file.replace('.ts', '.js'), target),
      ts.transpileModule(source, {
        compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext },
      }).outputText,
    )
  await writeFile(
    new URL('capture-checkpoint-store.d.ts', target),
    `export { applyCaptureCheckpoint, sweepExpiredCaptureContents } from '../../../src/access-kernel/capture-checkpoint-store.js'\n`,
  )
  await writeFile(new URL('provenance.json', target), JSON.stringify(provenance))
  return provenance
}
export async function expectedProvenance() {
  const source = {}
  for (const file of [
    'tools/capture-browser/main.ts',
    'tools/capture-browser/prepare.mjs',
    'tools/capture-browser/vite.config.ts',
    'tests/access-kernel/capture-native.spec.ts',
    'playwright.capture.config.ts',
    'src/access-kernel/database.ts',
    'src/access-kernel/capture-checkpoint-store.ts',
    'src/access-kernel/capture-checkpoint.ts',
  ])
    source[file] = sha(await readFile(new URL(file, web)))
  const git = spawnSync('git', ['rev-parse', 'HEAD'], { cwd: fileURLToPath(web), encoding: 'utf8' })
  assert.equal(git.status, 0)
  return {
    historical: (
      await verifyHistoricalSources(new URL('tests/fixtures/capture-reader-cc18a203/', web))
    ).provenance,
    currentHead: git.stdout.trim(),
    source,
    scope: 'Pinned reducer with current database class; not historical App/SW',
  }
}
export function verifyArtifactProvenance(actual, expected) {
  assert.ok(actual && typeof actual === 'object' && !Array.isArray(actual))
  assert.deepEqual(Object.keys(actual).sort(), [
    'assets',
    'currentHead',
    'historical',
    'scope',
    'source',
  ])
  for (const key of ['historical', 'currentHead', 'source', 'scope'])
    assert.deepEqual(actual[key], expected[key], `Provenance mismatch: ${key}`)
  assert.ok(actual.assets && typeof actual.assets === 'object' && !Array.isArray(actual.assets))
  assert.ok(Object.keys(actual.assets).length > 0)
  for (const [file, hash] of Object.entries(actual.assets)) {
    assert.match(file, /^[a-zA-Z0-9_.-]+\.js$/)
    assert.match(hash, /^[0-9a-f]{64}$/)
  }
}
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  await prepare()
  if (process.argv.includes('--build')) {
    const run = spawnSync(
      process.execPath,
      [
        'node_modules/vite/bin/vite.js',
        'build',
        '--config',
        'tools/capture-browser/vite.config.ts',
      ],
      { cwd: fileURLToPath(web), stdio: 'inherit' },
    )
    if (run.status !== 0) process.exit(run.status ?? 1)
    const output = new URL('.tmp-capture-browser/', web)
    const assets = {}
    for (const file of await readdir(new URL('assets/', output)))
      assets[file] = sha(await readFile(new URL('assets/' + file, output)))
    await writeFile(
      new URL('provenance.json', output),
      JSON.stringify(
        {
          ...(await expectedProvenance()),
          assets,
        },
        null,
        2,
      ),
    )
  }
}

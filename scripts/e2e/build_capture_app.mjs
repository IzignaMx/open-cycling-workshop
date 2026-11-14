/** Archived actual App/SW test artifacts only; never activation or deployment. */
import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { buildArchivedClient, manifestForAssets } from './build_legacy_client.mjs'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '../..')
const expected = Object.freeze({
  format: 1,
  source_commit: 'cc18a203a8c754284fc14ef3570d94d7d98fac23',
  source_tree: '0116b82f10277f1a78057140cc1f7885f5a35ecf',
  lock_sha256: '64ef16938e332905e9b876048b40f7fabf9bed88df288492449feff3c6ce9c51',
  database: 'ocwp-authenticated-v1',
})
export function validateCaptureAppPin(value) {
  if (
    !value ||
    Object.keys(value).length !== Object.keys(expected).length ||
    Object.entries(expected).some(([key, entry]) => value[key] !== entry)
  )
    throw new Error('Invalid exact capture App fixture pin')
  return Object.freeze({ ...value })
}
export function validateCaptureAppAssets(assets, expectedManifest) {
  const actual = manifestForAssets(assets)
  if (
    !expectedManifest ||
    Object.keys(actual).length !== Object.keys(expectedManifest).length ||
    Object.entries(actual).some(
      ([name, entry]) =>
        expectedManifest[name]?.bytes !== entry.bytes ||
        expectedManifest[name]?.sha256 !== entry.sha256 ||
        Object.keys(expectedManifest[name]).length !== 2,
    )
  )
    throw new Error('Capture App asset provenance mismatch')
  return actual
}
export function buildCaptureApp(output = join(root, 'artifacts/capture-app-old')) {
  const pin = validateCaptureAppPin(
    JSON.parse(readFileSync(join(root, 'fixtures/capture-app/manifest.json'), 'utf8')),
  )
  return buildArchivedClient(pin, output)
}
/** Current control also uses committed archive bytes, never dirty working sources. */
export function buildCurrentCaptureApp(output = join(root, 'artifacts/capture-app-current')) {
  const git = (...args) => execFileSync('git', args, { cwd: root, encoding: 'utf8' }).trim()
  const source_commit = git('rev-parse', 'HEAD')
  const source_tree = git('rev-parse', `${source_commit}^{tree}`)
  return buildArchivedClient({ ...expected, source_commit, source_tree }, output)
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const build = process.argv.includes('--current') ? buildCurrentCaptureApp : buildCaptureApp
  const outputArg = process.argv.slice(2).find((arg) => !arg.startsWith('--'))
  const output = resolve(
    outputArg ??
      join(
        root,
        process.argv.includes('--current')
          ? 'artifacts/capture-app-current'
          : 'artifacts/capture-app-old',
      ),
  )
  const evidence = build(output)
  if (process.argv.includes('--verify-reproducible')) {
    const repeated = build(`${output}-repeated`)
    if (JSON.stringify(evidence.assets) !== JSON.stringify(repeated.assets))
      throw new Error('Capture App/SW build is not reproducible')
  }
  process.stdout.write(
    `Archived capture App/SW built: ${evidence.source_commit}, ${Object.keys(evidence.assets).length} hashed assets\n`,
  )
}

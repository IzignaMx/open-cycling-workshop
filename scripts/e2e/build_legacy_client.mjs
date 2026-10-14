/** Reproduce the unmodified pre-cutover App/SW from its exact Git source and lock. */
import { createHash } from 'node:crypto'
import { execFileSync } from 'node:child_process'
import {
  existsSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  readdirSync,
  realpathSync,
  rmSync,
  statSync,
  symlinkSync,
  writeFileSync,
  cpSync,
} from 'node:fs'
import { dirname, join, relative, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '../..')
const hash = (bytes) => createHash('sha256').update(bytes).digest('hex')
export function validateLegacyPin(value) {
  if (
    !value ||
    value.format !== 1 ||
    !/^[0-9a-f]{40}$/.test(value.source_commit) ||
    !/^[0-9a-f]{40}$/.test(value.source_tree) ||
    !/^[0-9a-f]{64}$/.test(value.lock_sha256) ||
    value.database !== 'ocwp' ||
    value.write_protocol !== 0 ||
    value.source_commit !== '714342c60f4163c7b4c1ebec8433995dccbeea01'
  )
    throw new Error('Invalid exact legacy fixture pin')
  return Object.freeze({ ...value })
}
export function manifestForAssets(assets) {
  if (!assets.has('index.html') || !assets.has('sw.js') || !assets.has('manifest.webmanifest'))
    throw new Error('Complete old App, manifest and generated SW required')
  return Object.fromEntries(
    [...assets]
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([name, bytes]) => {
        if (!name || name.startsWith('/') || name.split('/').includes('..'))
          throw new Error('Unsafe fixture asset path')
        return [name, { bytes: bytes.byteLength, sha256: hash(bytes) }]
      }),
  )
}
/** The sole permitted installation omission is the test-only IndexedDB emulator.
 * No production/build package, importer, resolution or integrity may differ.
 */
export function validateInstalledLock(pinned, installed) {
  const withoutTestEmulator = (value) =>
    value
      .replace('      fake-indexeddb:\n        specifier: 6.2.5\n        version: 6.2.5\n', '')
      .replace(
        / {2}fake-indexeddb@6\.2\.5:\n {4}resolution: \{integrity: [^\n]+\}\n {4}engines: \{node: '>=18'\}\n\n/,
        '',
      )
      .replace('  fake-indexeddb@6.2.5: {}\n\n', '')
  const exact = installed === pinned
  if (!exact && withoutTestEmulator(pinned) !== installed)
    throw new Error('Installed dependency lock does not match pinned build dependencies')
  return {
    mode: exact ? 'identical-lock' : 'identical-build-lock-test-only-omission',
    installed_lock_sha256: hash(installed),
    excluded_test_dependencies: exact ? [] : ['fake-indexeddb@6.2.5'],
  }
}
export function legacyBuildEnvironment(environment, nodeVersion = process.version) {
  const match = /^v(\d+)\.(\d+)\.(\d+)$/.exec(nodeVersion)
  if (
    !match ||
    Number(match[1]) < 22 ||
    Number(match[1]) >= 25 ||
    (Number(match[1]) === 22 && Number(match[2]) < 16)
  )
    throw new Error('Legacy builder requires the archived supported Node range >=22.16 <25')
  return { ...environment, NODE_ENV: 'production', VITE_API_BASE_URL: '' }
}
function files(directory, base = directory) {
  return new Map(
    readdirSync(directory).flatMap((name) => {
      const path = join(directory, name)
      return statSync(path).isDirectory()
        ? [...files(path, base)]
        : [[relative(base, path).replaceAll('\\', '/'), readFileSync(path)]]
    }),
  )
}
function externalDependencies(source, target, workspace) {
  mkdirSync(target, { recursive: true })
  for (const entry of readdirSync(source)) {
    if (entry === '@ocwp') {
      mkdirSync(join(target, entry), { recursive: true })
      for (const name of readdirSync(join(source, entry)))
        symlinkSync(
          join(workspace, 'packages', name === 'api-client' ? 'api-client' : name),
          join(target, entry, name),
          'junction',
        )
    } else {
      symlinkSync(realpathSync(join(source, entry)), join(target, entry), 'junction')
    }
  }
}
export function buildLegacyClient(output = join(root, 'artifacts/legacy-client')) {
  const pin = validateLegacyPin(
    JSON.parse(readFileSync(join(root, 'fixtures/legacy-client/manifest.json'), 'utf8')),
  )
  const git = (...args) =>
    execFileSync('git', args, {
      cwd: root,
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'pipe'],
    }).trim()
  if (git('rev-parse', `${pin.source_commit}^{tree}`) !== pin.source_tree)
    throw new Error('Pinned legacy source tree mismatch')
  if (hash(readFileSync(join(root, 'pnpm-lock.yaml'))) !== pin.lock_sha256)
    throw new Error('Build legacy fixture with the exact pinned frozen dependency lock')
  const dependencyEvidence = validateInstalledLock(
    readFileSync(join(root, 'pnpm-lock.yaml'), 'utf8'),
    readFileSync(join(root, 'node_modules/.pnpm/lock.yaml'), 'utf8'),
  )
  const temporary = mkdtempSync(join(root, '.tmp-legacy-source-'))
  try {
    const archive = join(temporary, 'source.zip'),
      source = join(temporary, 'source')
    execFileSync('git', ['archive', '--format=zip', `--output=${archive}`, pin.source_commit], {
      cwd: root,
    })
    execFileSync(process.env.PYTHON ?? 'python', [
      '-c',
      'import sys,zipfile; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])',
      archive,
      source,
    ])
    if (hash(readFileSync(join(source, 'pnpm-lock.yaml'))) !== pin.lock_sha256)
      throw new Error('Archived legacy lock mismatch')
    // Only external registry dependencies are reused. Every workspace package
    // resolves to this archived source, never the current production source.
    for (const path of [
      'node_modules',
      'apps/web/node_modules',
      'packages/api-client/node_modules',
      'packages/ui/node_modules',
      'packages/branding/node_modules',
    ]) {
      if (existsSync(join(root, path)))
        externalDependencies(join(root, path), join(source, path), source)
    }
    const trackedBefore = git('ls-tree', '-r', pin.source_commit)
    const verifySource = () => {
      for (const row of trackedBefore.split('\n')) {
        const [metadata, name] = row.split('\t')
        const [, kind, expected] = metadata.split(' ')
        if (kind !== 'blob') continue
        const bytes = readFileSync(join(source, name))
        const actual = createHash('sha1')
          .update(`blob ${bytes.length}\0`)
          .update(bytes)
          .digest('hex')
        if (actual !== expected) throw new Error('Archived legacy source changed during build')
      }
    }
    verifySource()
    const env = {
      ...legacyBuildEnvironment(process.env),
      SOURCE_DATE_EPOCH: git('show', '-s', '--format=%ct', pin.source_commit),
    }
    const web = join(source, 'apps/web')
    const expectedTools = JSON.parse(
      readFileSync(join(web, 'package.json'), 'utf8'),
    ).devDependencies
    const toolVersions = Object.fromEntries(
      [
        ['typescript', join(source, 'node_modules/typescript/package.json')],
        ['vite', join(web, 'node_modules/vite/package.json')],
        ['vite-plugin-pwa', join(web, 'node_modules/vite-plugin-pwa/package.json')],
      ].map(([name, path]) => {
        const version = JSON.parse(readFileSync(path, 'utf8')).version
        if (version !== expectedTools[name])
          throw new Error(`Installed ${name} does not match pinned tool version`)
        return [name, version]
      }),
    )
    execFileSync(process.execPath, [join(source, 'node_modules/typescript/bin/tsc'), '-b'], {
      cwd: web,
      env,
      stdio: 'inherit',
    })
    execFileSync(process.execPath, [join(web, 'node_modules/vite/bin/vite.js'), 'build'], {
      cwd: web,
      env,
      stdio: 'inherit',
    })
    verifySource()
    const manifest = manifestForAssets(files(join(web, 'dist')))
    mkdirSync(output, { recursive: true })
    rmSync(join(output, 'dist'), { recursive: true, force: true })
    cpSync(join(web, 'dist'), join(output, 'dist'), { recursive: true, errorOnExist: false })
    const evidence = {
      ...pin,
      node: process.version,
      preferred_node: readFileSync(join(source, '.nvmrc'), 'utf8').trim(),
      dependency_source: 'validated-existing-installation',
      dependencies: dependencyEvidence,
      tools: toolVersions,
      source_date_epoch: env.SOURCE_DATE_EPOCH,
      build: ['tsc -b', 'vite build'],
      build_environment: { VITE_API_BASE_URL: '', NODE_ENV: 'production' },
      assets: manifest,
      tracked_source_listing_sha256: hash(trackedBefore),
    }
    writeFileSync(join(output, 'evidence.json'), `${JSON.stringify(evidence, null, 2)}\n`)
    return evidence
  } finally {
    rmSync(temporary, { recursive: true, force: true })
  }
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const output = resolve(process.argv[2] ?? join(root, 'artifacts/legacy-client'))
  const result = buildLegacyClient(output)
  if (process.argv.includes('--verify-reproducible')) {
    const second = buildLegacyClient(`${output}-repeated`)
    if (JSON.stringify(result.assets) !== JSON.stringify(second.assets))
      throw new Error('Old build/SW is not reproducible')
  }
  process.stdout.write(
    `Pinned legacy App/SW built: ${result.source_commit}, ${Object.keys(result.assets).length} hashed assets\n`,
  )
}

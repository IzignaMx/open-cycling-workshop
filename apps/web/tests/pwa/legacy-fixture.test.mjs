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

test('isolated archive installation is frozen, exact and rejects source or lock mutation', async () => {
  const { mkdtempSync, mkdirSync, writeFileSync, rmSync } = await import('node:fs')
  const { tmpdir } = await import('node:os')
  const { prepareArchivedDependencies } =
    await import('../../../../scripts/e2e/build_legacy_client.mjs')
  const temporary = mkdtempSync(resolve(tmpdir(), 'archive-dependencies-'))
  const source = resolve(temporary, 'source')
  const current = resolve(temporary, 'current')
  const pinned = 'lockfileVersion: 9.0\n'
  try {
    mkdirSync(source)
    mkdirSync(current)
    writeFileSync(resolve(current, 'pnpm-lock.yaml'), 'different current lock\n')
    const tracked = {
      'pnpm-lock.yaml': pinned,
      'package.json': '{"packageManager":"pnpm@11.17.0"}',
      'source.ts': 'original',
    }
    const listing = Object.entries(tracked)
      .map(
        ([name, bytes]) =>
          `100644 blob ${createHash('sha1')
            .update(`blob ${Buffer.byteLength(bytes)}\0${bytes}`)
            .digest('hex')}\t${name}`,
      )
      .join('\n')
    const reset = () => {
      for (const [name, bytes] of Object.entries(tracked))
        writeFileSync(resolve(source, name), bytes)
    }
    reset()
    const calls = []
    const run = (command, args, options) => {
      calls.push({ command, args, options })
      if (args[0] === '--version') return '11.17.0\n'
      mkdirSync(resolve(source, 'node_modules/.pnpm'), { recursive: true })
      writeFileSync(resolve(source, 'node_modules/.pnpm/lock.yaml'), pinned)
    }
    const evidence = prepareArchivedDependencies(source, current, listing, run)
    assert.equal(evidence.dependency_source, 'isolated-frozen-archive-installation')
    assert.equal(evidence.dependencies.mode, 'identical-lock')
    assert.deepEqual(calls[1].args, ['install', '--frozen-lockfile', '--prod=false'])
    assert.equal(calls[1].options.cwd, source)
    assert.throws(
      () =>
        prepareArchivedDependencies(source, current, listing, (command, args, options) => {
          const result = run(command, args, options)
          if (args[0] === 'install') writeFileSync(resolve(source, 'source.ts'), 'mutated')
          return result
        }),
      /source changed/,
    )
    reset()
    assert.throws(
      () =>
        prepareArchivedDependencies(source, current, listing, (command, args, options) => {
          const result = run(command, args, options)
          if (args[0] === 'install')
            writeFileSync(resolve(source, 'node_modules/.pnpm/lock.yaml'), `${pinned}drift: true\n`)
          return result
        }),
      /exact archived lock/,
    )
    assert.throws(
      () => prepareArchivedDependencies(source, current, listing, () => '99.0.0'),
      /package manager/,
    )
    reset()
    writeFileSync(resolve(current, 'pnpm-lock.yaml'), pinned)
    mkdirSync(resolve(current, 'node_modules/.pnpm'), { recursive: true })
    writeFileSync(resolve(current, 'node_modules/.pnpm/lock.yaml'), 'mismatched installation')
    assert.throws(
      () =>
        prepareArchivedDependencies(source, current, listing, () =>
          assert.fail('must not install'),
        ),
      /does not match pinned/,
    )
    // A fresh archive with identical locks retains the existing reuse path.
    rmSync(resolve(source, 'node_modules'), { recursive: true, force: true })
    writeFileSync(resolve(current, 'node_modules/.pnpm/lock.yaml'), pinned)
    const reused = prepareArchivedDependencies(source, current, listing, () =>
      assert.fail('must not install'),
    )
    assert.equal(reused.dependency_source, 'validated-existing-installation')
    assert.equal(reused.dependencies.mode, 'identical-lock')
    assert.equal(readFileSync(resolve(source, 'node_modules/.pnpm/lock.yaml'), 'utf8'), pinned)
  } finally {
    rmSync(temporary, { recursive: true, force: true })
  }
})

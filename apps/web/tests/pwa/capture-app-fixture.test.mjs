import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import test from 'node:test'
import {
  validateCaptureAppPin,
  validateCaptureAppAssets,
} from '../../../../scripts/e2e/build_capture_app.mjs'
import { manifestForAssets } from '../../../../scripts/e2e/build_legacy_client.mjs'

const root = resolve(import.meta.dirname, '../../../..')
const pin = JSON.parse(readFileSync(resolve(root, 'fixtures/capture-app/manifest.json')))
test('capture App pin rejects other valid commit, tree, lock and storage identities', () => {
  assert.ok(Object.isFrozen(validateCaptureAppPin(pin)))
  for (const [key, value] of Object.entries({
    source_commit: 'a'.repeat(40),
    source_tree: 'b'.repeat(40),
    lock_sha256: 'c'.repeat(64),
    database: 'ocwp',
    format: 2,
    write_protocol: 1,
  }))
    assert.throws(() => validateCaptureAppPin({ ...pin, [key]: value }))
  assert.throws(() => validateCaptureAppPin({ ...pin, unexpected: true }))
})
test('capture App evidence rejects missing, changed and extra assets', () => {
  const assets = new Map([
    ['index.html', Buffer.from('app')],
    ['sw.js', Buffer.from('worker')],
    ['manifest.webmanifest', Buffer.from('{}')],
  ])
  const manifest = manifestForAssets(assets)
  assert.deepEqual(validateCaptureAppAssets(assets, manifest), manifest)
  for (const changed of [
    new Map([...assets].filter(([name]) => name !== 'sw.js')),
    new Map([...assets, ['sw.js', Buffer.from('changed')]]),
    new Map([...assets, ['extra.js', Buffer.from('extra')]]),
  ])
    assert.throws(() => validateCaptureAppAssets(changed, manifest))
  assert.throws(() =>
    validateCaptureAppAssets(assets, {
      ...manifest,
      'sw.js': { bytes: 6, sha256: 'a'.repeat(64) },
    }),
  )
})

test('capture archived build rejects dependency drift and ambient build overrides', async () => {
  const { validateInstalledLock, legacyBuildEnvironment } =
    await import('../../../../scripts/e2e/build_legacy_client.mjs')
  const lock = readFileSync(resolve(root, 'pnpm-lock.yaml'), 'utf8')
  assert.equal(validateInstalledLock(lock, lock).mode, 'identical-lock')
  assert.throws(() => validateInstalledLock(lock, lock.replace('vite@8.1.5', 'vite@8.1.4')))
  assert.throws(() => validateInstalledLock(lock, `${lock}\nchanged: true\n`))
  const env = legacyBuildEnvironment(
    {
      PATH: '/tools',
      VITE_API_BASE_URL: 'https://wrong.invalid',
      VITE_OTHER: 'bad',
      NODE_OPTIONS: '--require=bad',
      NODE_ENV: 'development',
    },
    'v24.19.0',
  )
  assert.deepEqual(env, { PATH: '/tools', VITE_API_BASE_URL: '', NODE_ENV: 'production' })
  assert.throws(() => legacyBuildEnvironment({}, 'v20.19.0'))
})

test('archive identity independently verifies actual Git commit/tree and current frozen lock', async () => {
  const { execFileSync } = await import('node:child_process')
  const { validateArchivedInputs } = await import('../../../../scripts/e2e/build_legacy_client.mjs')
  const git = (...args) => execFileSync('git', args, { cwd: root, encoding: 'utf8' }).trim()
  const lock = readFileSync(resolve(root, 'pnpm-lock.yaml'))
  const actual = {
    source_commit: git('rev-parse', `${pin.source_commit}^{commit}`),
    source_tree: git('rev-parse', `${pin.source_commit}^{tree}`),
    lock,
  }
  validateArchivedInputs(pin, actual)
  assert.throws(() =>
    validateArchivedInputs(pin, { ...actual, source_commit: git('rev-parse', 'HEAD') }),
  )
  assert.throws(() =>
    validateArchivedInputs(pin, { ...actual, source_tree: git('rev-parse', 'HEAD^{tree}') }),
  )
  assert.throws(() =>
    validateArchivedInputs(pin, {
      ...actual,
      lock: Buffer.concat([lock, Buffer.from('\nchanged: true\n')]),
    }),
  )
  const current = {
    ...pin,
    source_commit: git('rev-parse', 'HEAD'),
    source_tree: git('rev-parse', 'HEAD^{tree}'),
  }
  validateArchivedInputs(current, { ...current, lock })
  assert.throws(() => validateArchivedInputs(current, { ...actual, lock }))
})

test('archived tracked source verification rejects build-time source modification', async () => {
  const { mkdtempSync, writeFileSync, rmSync } = await import('node:fs')
  const { tmpdir } = await import('node:os')
  const { createHash } = await import('node:crypto')
  const { verifyArchivedSources } = await import('../../../../scripts/e2e/build_legacy_client.mjs')
  const temporary = mkdtempSync(resolve(tmpdir(), 'capture-source-control-'))
  try {
    const bytes = Buffer.from('unchanged source')
    const blob = createHash('sha1').update(`blob ${bytes.length}\0`).update(bytes).digest('hex')
    const listing = `100644 blob ${blob}\tApp.tsx`
    writeFileSync(resolve(temporary, 'App.tsx'), bytes)
    verifyArchivedSources(temporary, listing)
    writeFileSync(resolve(temporary, 'App.tsx'), 'changed source')
    assert.throws(() => verifyArchivedSources(temporary, listing))
  } finally {
    rmSync(temporary, { recursive: true, force: true })
  }
})

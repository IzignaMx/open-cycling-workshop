import assert from 'node:assert/strict'
import { readdir, readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import test from 'node:test'

const web = new URL('../../', import.meta.url)
async function files(directory) {
  const entries = await readdir(directory, { withFileTypes: true })
  return (
    await Promise.all(
      entries.map((entry) => {
        const path = new URL(entry.name + (entry.isDirectory() ? '/' : ''), directory)
        return entry.isDirectory() ? files(path) : [path]
      }),
    )
  ).flat()
}
const markers =
  /kernel-browser|openBaselineQualification|isolated-baseline-test-|Synthetic qualified fixture only|Qualification requires actual null advertisement/

test('production source has no harness admission import or helper', async () => {
  for (const path of await files(new URL('src/', web))) {
    if (!/\.(?:ts|tsx|js)$/.test(path.pathname)) continue
    assert.doesNotMatch(await readFile(path, 'utf8'), markers, fileURLToPath(path))
  }
})

test('actual production JavaScript build excludes qualification admission and fixture credentials', async () => {
  // Intentionally require an actual production build; a missing dist is not a pass.
  const assets = (await files(new URL('dist/', web))).filter((path) =>
    path.pathname.endsWith('.js'),
  )
  assert.ok(assets.length > 0, 'Build production PWA before checking isolation')
  for (const path of assets) {
    const source = await readFile(path, 'utf8')
    assert.doesNotMatch(source, markers, fileURLToPath(path))
    assert.ok(!source.includes('ocwp-e2e-password'), 'Test credentials leaked into production')
  }
})

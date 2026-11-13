import { test, expect, type Page, type BrowserContext } from '@playwright/test'
import {
  pin,
  expectedProvenance,
  verifyArtifactProvenance,
} from '../../tools/capture-browser/prepare.mjs'
import type {} from '../../tools/capture-browser/main.js'
const A = 'http://127.0.0.1:5176',
  B = 'http://127.0.0.1:5177'
async function pageAt(context: BrowserContext, origin: string) {
  const page = await context.newPage()
  await page.goto(origin, { waitUntil: 'networkidle' })
  await page.waitForFunction(() => !!window.captureBoundaryHarness)
  expect(await page.evaluate(() => location.origin)).toBe(origin)
  expect(await page.evaluate(() => window.captureBoundaryHarness.provenance.commit)).toBe(pin)
  return page
}
async function offline(context: BrowserContext, page: Page) {
  await context.setOffline(true)
  expect(await page.evaluate(() => navigator.onLine)).toBe(false)
  expect(
    await page.evaluate(async () => {
      try {
        await fetch('/offline-probe', { cache: 'no-store' })
        return false
      } catch {
        return true
      }
    }),
  ).toBe(true)
}
const snapshot = (page: Page, name: string) =>
  page.evaluate((n) => window.captureBoundaryHarness.snapshot(n), name)
test.beforeEach(async ({ browser, request }, info) => {
  const expected = await expectedProvenance()
  for (const origin of [A, B]) {
    const response = await request.get(origin + '/provenance.json')
    expect(response.ok()).toBe(true)
    const provenance = await response.json()
    verifyArtifactProvenance(provenance, expected)
    for (const [file, expectedHash] of Object.entries(provenance.assets)) {
      const asset = await request.get(origin + '/assets/' + file)
      expect(asset.ok()).toBe(true)
      const bytes = Uint8Array.from(await asset.body())
      const digest = await crypto.subtle.digest('SHA-256', bytes.buffer)
      const hash = Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, '0')).join(
        '',
      )
      expect(hash).toBe(expectedHash)
    }
    await info.attach('artifact-provenance-' + new URL(origin).port, {
      body: JSON.stringify(provenance),
      contentType: 'application/json',
    })
  }
  await info.attach('browser-version', { body: browser.version(), contentType: 'text/plain' })
})
test('loaded historical reducer offline deletes same-origin future row but preserves exact v1', async ({
  context,
}, info) => {
  const modern = await pageAt(context, A),
    old = await pageAt(context, A),
    name = 'capture-native-shared'
  const before = await modern.evaluate((n) => window.captureBoundaryHarness.seed(n, 'shared'), name)
  expect(await snapshot(old, name)).toEqual(before)
  expect(
    await modern.evaluate((n) => window.captureBoundaryHarness.sweep(n, 'current'), name),
  ).toEqual({ kind: 'complete' })
  expect(
    await modern.evaluate((n) => window.captureBoundaryHarness.load(n, 'current'), name),
  ).toMatchObject({ kind: 'refused', reason: 'unsupported_format' })
  expect(await snapshot(modern, name)).toEqual(before)
  const failures: string[] = []
  old.on('requestfailed', (r) => failures.push(r.url()))
  await offline(context, old)
  expect(
    await old.evaluate((n) => window.captureBoundaryHarness.sweep(n, 'historical'), name),
  ).toEqual({ kind: 'complete' })
  const after = await snapshot(modern, name)
  expect(after.contents).toEqual(before.contents.filter((r) => r.channel === 'customer'))
  expect(after.checkpoints[0]?.order.state).toBe('UNAVAILABLE')
  expect(
    await old.evaluate((n) => window.captureBoundaryHarness.load(n, 'historical'), name),
  ).toMatchObject({
    kind: 'loaded',
    contents: { customer: before.contents.find((r) => r.channel === 'customer') },
  })
  await expect.poll(() => failures.some((url) => url.endsWith('/offline-probe'))).toBe(true)
  await info.attach('native-snapshots', {
    body: JSON.stringify({ before, after, failures }),
    contentType: 'application/json',
  })
})
test('native v8 connection closes on v9 upgrade and reopens before historical deletion', async ({
  context,
}, info) => {
  const page = await pageAt(context, A),
    name = 'capture-native-upgrade'
  const before = await page.evaluate((n) => window.captureBoundaryHarness.seed(n, 'upgrade'), name)
  const version = await page.evaluate((n) => window.captureBoundaryHarness.upgrade(n), name)
  expect(version).toEqual({ changed: true, version: 90, reopenedVersion: 90 })
  expect(await snapshot(page, name)).toEqual(before)
  await offline(context, page)
  await page.evaluate((n) => window.captureBoundaryHarness.sweep(n, 'historical'), name)
  const after = await snapshot(page, name)
  expect(after.contents).toEqual(before.contents.filter((r) => r.channel === 'customer'))
  await info.attach('native-snapshots', {
    body: JSON.stringify({ before, after, version }),
    contentType: 'application/json',
  })
})
test('different local origins isolate identical database names in one browser context', async ({
  context,
}, info) => {
  const a = await pageAt(context, A),
    b = await pageAt(context, B),
    sameA = await pageAt(context, A),
    name = 'capture-native-origin'
  expect(a.context()).toBe(b.context())
  expect(new URL(a.url()).origin).not.toBe(new URL(b.url()).origin)
  const beforeA = await a.evaluate((n) => window.captureBoundaryHarness.seed(n, 'origin-A'), name)
  const beforeB = await b.evaluate((n) => window.captureBoundaryHarness.seed(n, 'origin-B'), name)
  expect(await snapshot(sameA, name)).toEqual(beforeA)
  expect(JSON.stringify(await snapshot(a, name))).not.toContain('origin-B')
  expect(JSON.stringify(await snapshot(b, name))).not.toContain('origin-A')
  await offline(context, a)
  await a.evaluate((n) => window.captureBoundaryHarness.sweep(n, 'historical'), name)
  const afterA = await snapshot(sameA, name),
    afterB = await snapshot(b, name)
  expect(afterA.contents).toEqual(beforeA.contents.filter((r) => r.channel === 'customer'))
  expect(afterB).toEqual(beforeB)
  expect(
    await b.evaluate((n) => window.captureBoundaryHarness.load(n, 'current'), name),
  ).toMatchObject({ kind: 'refused', reason: 'unsupported_format' })
  await info.attach('native-snapshots', {
    body: JSON.stringify({ origins: [A, B], name, beforeA, beforeB, afterA, afterB }),
    contentType: 'application/json',
  })
})

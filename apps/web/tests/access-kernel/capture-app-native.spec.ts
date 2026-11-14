import { test, expect, type Page, type APIRequestContext, type TestInfo } from '@playwright/test'
import { captureFixture, witnessId } from '../../tools/capture-app/fixture.mjs'
import { expectedEvidence, hash } from '../../tools/capture-app/provenance.mjs'
import {
  validCheckpoint,
  validContent,
  preservableUnsupportedContent,
  CAPTURE_TTL_MS,
} from '../../src/access-kernel/capture-checkpoint.js'
import { canonicalJson, operationIntact } from '../../src/access-kernel/operations.js'
import type { OwnedOperation } from '../../src/access-kernel/types.js'

// Node-only validators never enter the application page. No harness, reducer call,
// runtime hook, session, API proxy or production data is used by these cases.
const database = 'ocwp-authenticated-v1'
type Snapshot = {
  contents: Record<string, unknown>[]
  checkpoints: Record<string, unknown>[]
  journal: OwnedOperation[]
}

async function verify(
  origin: string,
  kind: 'old' | 'current',
  request: APIRequestContext,
  info: TestInfo,
) {
  const expected = expectedEvidence(kind)
  const response = await request.get(`${origin}/evidence.json`)
  expect(response.ok()).toBe(true)
  expect(await response.json()).toEqual(expected)
  for (const required of ['index.html', 'sw.js', 'manifest.webmanifest'])
    expect(Object.hasOwn(expected.assets, required)).toBe(true)
  for (const [path, metadata] of Object.entries(expected.assets)) {
    expect(path.startsWith('/') || path.split('/').includes('..')).toBe(false)
    const served = await request.get(`${origin}/${path}`)
    expect(served.ok()).toBe(true)
    const body = await served.body()
    expect(body.byteLength).toBe(metadata.bytes)
    expect(hash(body)).toBe(metadata.sha256)
  }
  await info.attach(`${kind}-verified-App-SW-assets`, {
    body: JSON.stringify(expected),
    contentType: 'application/json',
  })
  return expected
}

function fixture(now: number) {
  const seeded = captureFixture(now, CAPTURE_TTL_MS, canonicalJson)
  expect(validCheckpoint(seeded.checkpoint)).toBe(true)
  expect(validContent(seeded.customer)).toBe(true)
  expect(validContent(seeded.witness)).toBe(true)
  expect(validContent(seeded.future)).toBe(false)
  expect(preservableUnsupportedContent(seeded.future)).toBe(true)
  expect(operationIntact(seeded.journal)).toBe(true)
  return seeded
}

async function snapshot(page: Page): Promise<Snapshot> {
  return page.evaluate(async (name) => {
    const db = await new Promise<IDBDatabase>((resolve, reject) => {
      const request = indexedDB.open(name)
      request.onupgradeneeded = () => {
        request.transaction?.abort()
        reject(Error('App must create database first'))
      }
      request.onsuccess = () => resolve(request.result)
      request.onerror = () => reject(request.error)
    })
    try {
      const tx = db.transaction(
        ['captureDraftContents', 'captureCheckpoints', 'operationJournal'],
        'readonly',
      )
      const all = (store: string) =>
        new Promise<unknown[]>((resolve, reject) => {
          const req = tx.objectStore(store).getAll()
          req.onsuccess = () => resolve(req.result)
          req.onerror = () => reject(req.error)
        })
      const [contents, checkpoints, journal] = await Promise.all([
        all('captureDraftContents'),
        all('captureCheckpoints'),
        all('operationJournal'),
      ])
      return { contents, checkpoints, journal } as Snapshot
    } finally {
      db.close()
    }
  }, database)
}

const legacyNotice = (page: Page) =>
  page.getByRole('status').filter({ hasText: 'Hay datos de una versión anterior' })

async function installStartupBarrier(page: Page, origin: string) {
  // Start on an inert same-origin JSON document, before any App or SW runs.
  // This disposable legacy DB is only a count sentinel for the existing notice.
  const response = await page.goto(`${origin}/manifest.webmanifest`)
  expect(response?.ok()).toBe(true)
  expect(await page.evaluate(() => navigator.serviceWorker.controller)).toBeNull()
  expect(await page.evaluate(() => document.scripts.length)).toBe(0)
  expect(await page.evaluate(() => indexedDB.databases())).toEqual([])
  await page.evaluate(async () => {
    const db = await new Promise<IDBDatabase>((resolve, reject) => {
      const req = indexedDB.open('ocwp', 1)
      req.onupgradeneeded = () => req.result.createObjectStore('customers', { keyPath: 'id' })
      req.onsuccess = () => resolve(req.result)
      req.onerror = () => reject(req.error)
    })
    try {
      const tx = db.transaction('customers', 'readwrite')
      const done = new Promise<void>((resolve, reject) => {
        tx.oncomplete = () => resolve()
        tx.onerror = () => reject(tx.error)
        tx.onabort = () => reject(tx.error)
      })
      tx.objectStore('customers').add({ id: 'synthetic-startup-count-only' })
      await done
    } finally {
      db.close()
    }
  })
}

for (const [kind, port] of [
  ['old', 5180],
  ['current', 5181],
] as const) {
  test(`actual ${kind} App/SW offline page reload ${kind === 'old' ? 'deletes' : 'preserves'} future bytes`, async ({
    browser,
    request,
  }, info) => {
    const origin = `http://127.0.0.1:${port}`
    const evidence = await verify(origin, kind, request, info)
    const context = await browser.newContext({ serviceWorkers: 'allow' })
    const failures: { url: string; error: string | null }[] = []
    const page = await context.newPage()
    page.on('requestfailed', (r) =>
      failures.push({ url: r.url(), error: r.failure()?.errorText ?? null }),
    )
    try {
      await installStartupBarrier(page, origin)
      await page.goto(origin, { waitUntil: 'networkidle' })
      // start() awaits cleanup before inspecting legacy work and publishing this notice.
      await expect(legacyNotice(page)).toBeVisible()
      await expect(page.locator('[data-runtime-state="LOCKED"]')).toBeVisible()
      await page.waitForFunction(
        async (name) => (await indexedDB.databases()).some((db) => db.name === name),
        database,
      )
      await page.evaluate(async () => {
        await navigator.serviceWorker.ready
      })
      await page.waitForFunction(() => navigator.serviceWorker.controller?.state === 'activated')
      const controller = await page.evaluate(() => navigator.serviceWorker.controller?.scriptURL)
      expect(controller).toBe(`${origin}/sw.js`)
      expect(await snapshot(page)).toEqual({ contents: [], checkpoints: [], journal: [] })
      const seeded = fixture(Date.now() - 1000)
      await page.evaluate(
        async ({ name, seeded }) => {
          const db = await new Promise<IDBDatabase>((resolve, reject) => {
            const req = indexedDB.open(name)
            req.onupgradeneeded = () => {
              req.transaction?.abort()
              reject(Error('Missing App database'))
            }
            req.onsuccess = () => resolve(req.result)
            req.onerror = () => reject(req.error)
          })
          try {
            const tx = db.transaction(
              ['captureDraftContents', 'captureCheckpoints', 'operationJournal'],
              'readwrite',
            )
            const done = new Promise<void>((resolve, reject) => {
              tx.oncomplete = () => resolve()
              tx.onerror = () => reject(tx.error)
              tx.onabort = () => reject(tx.error)
            })
            tx.objectStore('captureCheckpoints').add(seeded.checkpoint)
            for (const row of [seeded.customer, seeded.future, seeded.witness])
              tx.objectStore('captureDraftContents').add(row)
            tx.objectStore('operationJournal').add(seeded.journal)
            await done
          } finally {
            db.close()
          }
        },
        { name: database, seeded },
      )
      const before = await snapshot(page)
      expect(before.contents).toEqual([seeded.customer, seeded.future, seeded.witness])
      expect(before.checkpoints).toEqual([seeded.checkpoint])
      expect(before.journal).toEqual([seeded.journal])
      await info.attach('before-native-IDB', {
        body: JSON.stringify(before),
        contentType: 'application/json',
      })
      await context.setOffline(true)
      expect(await page.evaluate(() => navigator.onLine)).toBe(false)
      const probe = `/uncached-capture-probe-${Date.now()}`
      expect(
        await page.evaluate(async (path) => {
          try {
            await fetch(path, { cache: 'no-store' })
            return false
          } catch {
            return true
          }
        }, probe),
      ).toBe(true)
      await expect.poll(() => failures.some((failure) => failure.url === origin + probe)).toBe(true)
      const response = await page.reload({ waitUntil: 'networkidle' })
      await expect(legacyNotice(page)).toBeVisible()
      expect(response?.fromServiceWorker()).toBe(true)
      expect(response?.ok()).toBe(true)
      expect(hash(await response!.body())).toBe(evidence.assets['index.html']!.sha256)
      await expect(page.locator('[data-runtime-state="LOCKED"]')).toBeVisible()
      await expect
        .poll(async () => (await snapshot(page)).contents.some((r) => r.checkpointId === witnessId))
        .toBe(false)
      const after = await snapshot(page)
      expect(after.journal).toEqual(before.journal)
      expect(JSON.stringify(after.journal)).toBe(JSON.stringify(before.journal))
      expect(after.contents.find((r) => r.channel === 'customer')).toEqual(seeded.customer)
      if (kind === 'old') {
        expect(after.contents).toEqual([seeded.customer])
        expect(after.checkpoints[0]).toMatchObject({
          ...seeded.checkpoint,
          observedAt: expect.any(Number),
          order: {
            revision: 2,
            state: 'UNAVAILABLE',
            attemptId: null,
            contentStartedAt: null,
            contentExpiresAt: null,
          },
        })
      } else {
        expect(after.contents).toEqual([seeded.customer, seeded.future])
        expect(JSON.stringify(after.contents[1])).toBe(JSON.stringify(seeded.future))
        expect(after.checkpoints).toEqual(before.checkpoints)
      }
      await info.attach('after-native-IDB-and-offline-evidence', {
        body: JSON.stringify({
          after,
          failures,
          browser: browser.version(),
          controller,
          navigationFromServiceWorker: response?.fromServiceWorker(),
          navigationSha256: hash(await response!.body()),
          lifecycle: 'page reload in same disposable browser context; not browser/process restart',
          scope:
            'independent artifact controls; not same-origin old/new handover or G1–G6 qualification',
        }),
        contentType: 'application/json',
      })
    } finally {
      await info.attach('browser-and-network-failures', {
        body: JSON.stringify({ browser: browser.version(), failures }),
        contentType: 'application/json',
      })
      await context.close()
    }
  })
}

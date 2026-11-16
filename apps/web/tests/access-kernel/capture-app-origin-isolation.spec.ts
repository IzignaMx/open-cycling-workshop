import {
  startCaptureAppServer,
  type CaptureAppServer,
} from '../../../../scripts/e2e/capture_app_server.mjs'
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

// Same browser context, distinct actual origins and identical database/key names.
// No reducer invocation, production hook, session or real data. Page reload only.
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

function fixture(now: number, label: string) {
  const seeded = captureFixture(now, CAPTURE_TTL_MS, canonicalJson)
  if (seeded.customer.channel !== 'customer') throw Error('Expected customer control')
  seeded.customer.draft.displayName = label
  seeded.future.draft = { opaqueFuture: label, nested: ['preserve', 2] }
  seeded.journal.envelope.payload.display_name = label
  seeded.journal.optimistic.display_name = label
  seeded.journal.envelopeCanonical = canonicalJson(seeded.journal.envelope)
  seeded.checkpoint.bindingKey = (label === 'origin-A' ? 'a' : 'c').repeat(64)
  seeded.checkpoint.scopeKey = (label === 'origin-A' ? 'b' : 'd').repeat(64)
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

async function seed(page: Page, seeded: ReturnType<typeof fixture>) {
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
  return before
}

async function openApp(page: Page, origin: string) {
  await installStartupBarrier(page, origin)
  await page.goto(origin, { waitUntil: 'networkidle' })
  await expect(legacyNotice(page)).toBeVisible()
  await expect(page.locator('[data-runtime-state="LOCKED"]')).toBeVisible()
  await page.evaluate(async () => {
    await navigator.serviceWorker.ready
  })
  await page.waitForFunction(() => navigator.serviceWorker.controller?.state === 'activated')
  expect(await page.evaluate(() => navigator.serviceWorker.controller?.scriptURL)).toBe(
    `${origin}/sw.js`,
  )
  expect(await snapshot(page)).toEqual({ contents: [], checkpoints: [], journal: [] })
}

async function offlineProbe(page: Page, failures: { url: string; error: string | null }[]) {
  expect(await page.evaluate(() => navigator.onLine)).toBe(false)
  const probe = `${new URL(page.url()).origin}/uncached-isolation-probe-${Date.now()}`
  expect(
    await page.evaluate(async (url) => {
      try {
        await fetch(url, { cache: 'no-store' })
        return false
      } catch {
        return true
      }
    }, probe),
  ).toBe(true)
  await expect.poll(() => failures.some((failure) => failure.url === probe)).toBe(true)
}

async function reloadFromSW(page: Page, expectedIndexHash: string) {
  const response = await page.reload({ waitUntil: 'networkidle' })
  expect(response?.ok()).toBe(true)
  expect(response?.fromServiceWorker()).toBe(true)
  const navigationSha256 = hash(await response!.body())
  expect(navigationSha256).toBe(expectedIndexHash)
  await expect(legacyNotice(page)).toBeVisible()
  await expect(page.locator('[data-runtime-state="LOCKED"]')).toBeVisible()
  expect(await page.evaluate(() => navigator.onLine)).toBe(false)
  return {
    url: response!.url(),
    fromServiceWorker: response!.fromServiceWorker(),
    navigationSha256,
    controller: await page.evaluate(() => navigator.serviceWorker.controller?.scriptURL),
  }
}

test('actual old A maintenance cannot alter current B in one offline browser context', async ({
  browser,
  request,
}, info) => {
  const A = 'http://127.0.0.1:5180',
    B = 'http://127.0.0.1:5181'
  const context = await browser.newContext({ serviceWorkers: 'allow' })
  const failures: { url: string; error: string | null }[] = []
  const a = await context.newPage(),
    b = await context.newPage()
  for (const page of [a, b])
    page.on('requestfailed', (r) =>
      failures.push({ url: r.url(), error: r.failure()?.errorText ?? null }),
    )
  const servers: CaptureAppServer[] = []
  const directory = (kind: 'old' | 'current') =>
    new URL(`../../../../artifacts/capture-app-${kind}/`, import.meta.url)
  const ownHost = async (kind: 'old' | 'current', port: number) => {
    // Default admission is independently pinned to the intended port's build receipt.
    const server = startCaptureAppServer(directory(kind), port)
    servers.push(server)
    if (!server.listening)
      await new Promise<void>((resolve, reject) => {
        server.once('listening', resolve)
        server.once('error', reject)
      })
    return server
  }
  try {
    await ownHost('old', 5180)
    const hostB = await ownHost('current', 5181)
    const evidenceA = await verify(A, 'old', request, info)
    const evidenceB = await verify(B, 'current', request, info)
    expect(a.context()).toBe(b.context())
    await openApp(a, A)
    await openApp(b, B)
    expect(new URL(a.url()).origin).not.toBe(new URL(b.url()).origin)
    const now = Date.now() - 1000
    const dataA = fixture(now, 'origin-A'),
      dataB = fixture(now - 3000, 'origin-B')
    const beforeA = await seed(a, dataA),
      beforeB = await seed(b, dataB)
    expect(JSON.stringify(beforeA)).not.toContain('origin-B')
    expect(JSON.stringify(beforeB)).not.toContain('origin-A')
    expect(dataA.checkpoint.checkpointId).toBe(dataB.checkpoint.checkpointId)
    expect(dataA.future.expiresAt).not.toBe(dataB.future.expiresAt)
    await info.attach('same-context-before-IDB', {
      body: JSON.stringify({ beforeA, beforeB }),
      contentType: 'application/json',
    })
    // Real listening B host rejects the historical candidate before its snapshot swap.
    // This is a test-host admission check, not a deployed production rollback floor.
    expect(() => hostB.replaceCaptureApp(directory('old'))).toThrow(/Wrong source_commit/)
    const afterRollbackEvidence = await verify(B, 'current', request, info)
    expect(afterRollbackEvidence).toEqual(evidenceB)
    const rollbackRoot = await request.get(`${B}/`)
    expect(rollbackRoot.ok()).toBe(true)
    expect(hash(await rollbackRoot.body())).toBe(evidenceB.assets['index.html']!.sha256)
    const bAfterRejectedRollback = await snapshot(b)
    expect(JSON.stringify(bAfterRejectedRollback)).toBe(JSON.stringify(beforeB))
    await info.attach('live-B-test-host-rejected-historical-rollback', {
      body: JSON.stringify({
        rejected: evidenceA.source_commit,
        retained: evidenceB.source_commit,
        assets: evidenceB.assets,
        bAfterRejectedRollback,
        scope:
          'Only this immutable test-host admission; no production floor or old-cache exclusion',
      }),
      contentType: 'application/json',
    })
    await context.setOffline(true)
    await offlineProbe(a, failures)
    await offlineProbe(b, failures)
    const navigationA = await reloadFromSW(a, evidenceA.assets['index.html']!.sha256)
    expect(navigationA.controller).toBe(`${A}/sw.js`)
    await expect
      .poll(async () => (await snapshot(a)).contents.some((r) => r.checkpointId === witnessId))
      .toBe(false)
    const afterA = await snapshot(a)
    expect(afterA.contents).toEqual([dataA.customer])
    expect(afterA.journal).toEqual(beforeA.journal)
    expect(afterA.checkpoints[0]).toMatchObject({
      ...dataA.checkpoint,
      observedAt: expect.any(Number),
      order: {
        revision: 2,
        state: 'UNAVAILABLE',
        attemptId: null,
        contentStartedAt: null,
        contentExpiresAt: null,
      },
    })
    const bAfterOldMaintenance = await snapshot(b)
    expect(bAfterOldMaintenance).toEqual(beforeB)
    expect(JSON.stringify(bAfterOldMaintenance)).toBe(JSON.stringify(beforeB))
    // The expired B witness still exists: A did not perform maintenance in B.
    expect(bAfterOldMaintenance.contents.some((r) => r.checkpointId === witnessId)).toBe(true)
    await info.attach('after-A-maintenance-B-unchanged', {
      body: JSON.stringify({ afterA, bAfterOldMaintenance, navigationA }),
      contentType: 'application/json',
    })
    const navigationB = await reloadFromSW(b, evidenceB.assets['index.html']!.sha256)
    expect(navigationB.controller).toBe(`${B}/sw.js`)
    await expect
      .poll(async () => (await snapshot(b)).contents.some((r) => r.checkpointId === witnessId))
      .toBe(false)
    await offlineProbe(b, failures)
    const afterB = await snapshot(b)
    const expectedB = { ...beforeB, contents: [dataB.customer, dataB.future] }
    expect(afterB).toEqual(expectedB)
    expect(JSON.stringify(afterB)).toBe(JSON.stringify(expectedB))
    expect(afterB.contents[1]?.expiresAt).toBe(dataB.future.expiresAt)
    expect(await snapshot(a)).toEqual(afterA)
    await info.attach('after-B-reload-native-evidence', {
      body: JSON.stringify({
        afterB,
        navigationB,
        failures,
        browser: browser.version(),
        scope:
          'Same context, two actual origins, isolated test-host snapshots. Not same-origin historical-reader exclusion, production rollback floor, migration/handover, process restart or G3.',
      }),
      contentType: 'application/json',
    })
  } finally {
    try {
      await info.attach('browser-and-network-failures', {
        body: JSON.stringify({ browser: browser.version(), failures }),
        contentType: 'application/json',
      })
    } finally {
      try {
        await context.close()
      } finally {
        await Promise.all(
          servers
            .filter((server) => server.listening)
            .map(
              (server) =>
                new Promise<void>((resolve, reject) =>
                  server.close((error) => (error ? reject(error) : resolve())),
                ),
            ),
        )
      }
    }
  }
})

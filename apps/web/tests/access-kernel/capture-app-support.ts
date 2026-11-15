import { expect, type Page, type APIRequestContext, type TestInfo } from '@playwright/test'
import { captureFixture } from '../../tools/capture-app/fixture.mjs'
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

export { database, verify, fixture, snapshot, legacyNotice, installStartupBarrier }

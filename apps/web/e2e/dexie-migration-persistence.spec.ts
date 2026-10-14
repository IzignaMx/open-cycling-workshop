import { expect, test, type Page } from '@playwright/test'
import {
  createCustomer,
  kernelSnapshot,
  LOCATION_ID,
  login,
  ORGANIZATION_ID,
  sessionToken,
  waitForApplied,
  waitForConfirmed,
  waitForReady,
} from './helpers/authenticated-workshop.js'

/** Raw logical-v1 fixture, not evidence for the separately tested installed old PWA/SW. */
async function seedVersionOneDatabase(page: Page) {
  return page.evaluate(
    async ({ organizationId, locationId }) => {
      const open = indexedDB.open('ocwp', 10)
      open.onupgradeneeded = () => {
        const schema = {
          customers: 'customer_id,organization_id,location_id,display_name,updated_at',
          mutationQueue: 'mutation_id,state,organization_id,location_id,entity_type,queued_at',
          syncState: 'key',
          conflicts: 'mutation_id,entity_type,entity_id,recorded_at',
        }
        for (const [name, definition] of Object.entries(schema)) {
          const [keyPath, ...indexes] = definition.split(',')
          const store = open.result.createObjectStore(name, { keyPath })
          for (const index of indexes) store.createIndex(index, index)
        }
      }
      const db = await new Promise<IDBDatabase>((resolve, reject) => {
        open.onsuccess = () => resolve(open.result)
        open.onerror = () => reject(open.error)
      })
      try {
        const id = crypto.randomUUID(),
          mutationId = crypto.randomUUID()
        const tx = db.transaction(
          ['customers', 'mutationQueue', 'syncState', 'conflicts'],
          'readwrite',
        )
        tx.objectStore('customers').put({
          customer_id: id,
          display_name: 'Cliente legado privado sin autor',
          organization_id: organizationId,
          location_id: locationId,
          version: 1,
          custom_unknown: { archived: false, opaque: ['keep', 17, null] },
        })
        tx.objectStore('mutationQueue').put({
          mutation_id: mutationId,
          entity_type: 'customer',
          entity_id: id,
          operation: 'create',
          organization_id: organizationId,
          location_id: locationId,
          base_version: null,
          occurred_at: '2026-10-13T10:00:00Z',
          payload: {
            display_name: 'Cliente legado privado sin autor',
            extension: { preserve: true },
          },
          state: 'pending',
          queued_at: '2026-10-13T10:00:00Z',
          actor_id: 'unverified-historical-actor',
          unknown_delivery: { maybe_applied: true, receipt: ['untrusted'] },
        })
        tx.objectStore('syncState').put({
          key: 'cursor:legacy',
          cursor: 927,
          unknown_checkpoint: 'never-adopt',
        })
        tx.objectStore('conflicts').put({
          mutation_id: mutationId,
          entity_type: 'customer',
          entity_id: id,
          recorded_at: '2026-10-13T11:00:00Z',
          reason: 'Conflicto legado privado',
          unknown_history: [{ action: 'preserve' }],
        })
        await new Promise<void>((resolve, reject) => {
          tx.oncomplete = () => resolve()
          tx.onabort = () => reject(tx.error)
          tx.onerror = () => reject(tx.error)
        })
        return { id, mutationId }
      } finally {
        db.close()
      }
    },
    { organizationId: ORGANIZATION_ID, locationId: LOCATION_ID },
  )
}

async function rawEvidence(page: Page) {
  return page.evaluate(async () => {
    const open = indexedDB.open('ocwp')
    open.onupgradeneeded = () => open.transaction!.abort()
    const db = await new Promise<IDBDatabase>((resolve, reject) => {
      open.onsuccess = () => resolve(open.result)
      open.onerror = () => reject(open.error)
    })
    try {
      const names = Array.from(db.objectStoreNames)
      const tx = db.transaction(names, 'readonly')
      const stores = await Promise.all(
        names.map((name) => {
          const store = tx.objectStore(name)
          return new Promise((resolve, reject) => {
            const all = store.getAll()
            all.onsuccess = () =>
              resolve({
                name,
                keyPath: store.keyPath,
                indexes: Array.from(store.indexNames).map((key) => {
                  const index = store.index(key)
                  return {
                    name: key,
                    keyPath: index.keyPath,
                    unique: index.unique,
                    multiEntry: index.multiEntry,
                  }
                }),
                rows: all.result,
              })
            all.onerror = () => reject(all.error)
          })
        }),
      )
      return { version: db.version, stores }
    } finally {
      db.close()
    }
  })
}

test('raw v1 legacy evidence and late old-tab additions remain exact, unknown and never replayed', async ({
  page,
  request,
}) => {
  await page.goto('/')
  const original = await seedVersionOneDatabase(page)
  const before = await rawEvidence(page)
  expect(before.version).toBe(10)
  const sentIds: string[] = []
  page.on('request', (request) => {
    if (new URL(request.url()).pathname === '/api/v1/sync/mutations')
      sentIds.push(
        ...(request.postDataJSON() as { mutations: Array<{ mutation_id: string }> }).mutations.map(
          (item) => item.mutation_id,
        ),
      )
  })
  // Supersedes the unsafe expectation that a new login claims/replays old v1 work.
  // Known-author unchanged-ID replay across reload is covered in sync-chaos.
  await login(page)
  await expect(page.getByText(/Hay datos de una versión anterior/)).toBeVisible()
  await expect(page.locator('body')).not.toContainText('Cliente legado privado sin autor')
  await expect(page.locator('body')).not.toContainText('Conflicto legado privado')
  expect(await rawEvidence(page)).toEqual(before)
  expect((await kernelSnapshot(page)).journal).toHaveLength(0)
  expect((await kernelSnapshot(page)).records.some((item) => item.entityId === original.id)).toBe(
    false,
  )

  // A second raw connection represents a late legacy writer. It intentionally
  // does not impersonate the exact historical bundle tested by legacy-cutover.
  const oldTab = await page.context().newPage()
  await oldTab.goto('/manifest.webmanifest')
  const late = await oldTab.evaluate(async () => {
    const open = indexedDB.open('ocwp')
    const db = await new Promise<IDBDatabase>((resolve, reject) => {
      open.onsuccess = () => resolve(open.result)
      open.onerror = () => reject(open.error)
    })
    try {
      const tx = db.transaction('mutationQueue', 'readwrite')
      const mutationId = crypto.randomUUID()
      tx.objectStore('mutationQueue').put({
        mutation_id: mutationId,
        entity_id: crypto.randomUUID(),
        state: 'pending',
        unknown_late_work: { exact: ['late', 23], author: null },
        payload: { display_name: 'Trabajo privado tardío' },
      })
      await new Promise<void>((resolve, reject) => {
        tx.oncomplete = () => resolve()
        tx.onabort = () => reject(tx.error)
      })
      return mutationId
    } finally {
      db.close()
    }
  })
  const afterLate = await rawEvidence(oldTab)
  expect(afterLate).not.toEqual(before)
  expect(afterLate.version).toBe(10)
  await oldTab.close()
  await page.reload({ waitUntil: 'domcontentloaded' })
  await waitForReady(page)
  await expect(page.getByText(/Hay datos de una versión anterior/)).toBeVisible()
  await expect(page.locator('body')).not.toContainText('Trabajo privado tardío')
  expect(await rawEvidence(page)).toEqual(afterLate)
  const fresh = await createCustomer(page, `Cliente actual ${crypto.randomUUID()}`)
  await waitForApplied(page, fresh.mutationId)
  await waitForConfirmed(page, fresh)
  expect(sentIds).toContain(fresh.mutationId)
  expect(sentIds).not.toContain(original.mutationId)
  expect(sentIds).not.toContain(late)
  const missing = await request.get(`/api/v1/customers/${original.id}`, {
    headers: { Authorization: `Bearer ${await sessionToken(page)}` },
  })
  expect(missing.status()).toBe(404)
  expect(await rawEvidence(page)).toEqual(afterLate)
  expect((await kernelSnapshot(page)).journal).toEqual([fresh])
  await page.getByRole('button', { name: 'Cerrar esta sesión', exact: true }).click()
  await login(page, 'e2e-other')
  await expect(page.locator('body')).not.toContainText('Cliente legado privado sin autor')
  expect((await kernelSnapshot(page)).journal).toHaveLength(0)
  expect(await rawEvidence(page)).toEqual(afterLate)
})

test('fresh authenticated login leaves an absent legacy database absent', async ({ page }) => {
  await page.goto('/')
  expect(
    await page.evaluate(async () => (await indexedDB.databases()).some((db) => db.name === 'ocwp')),
  ).toBe(false)
  await login(page)
  expect(
    await page.evaluate(async () => (await indexedDB.databases()).some((db) => db.name === 'ocwp')),
  ).toBe(false)
  await expect(page.getByText(/Hay datos de una versión anterior/)).toHaveCount(0)
})

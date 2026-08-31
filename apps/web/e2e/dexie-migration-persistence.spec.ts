import { expect, test, type Page } from '@playwright/test'

const ORGANIZATION_ID = '00000000-0000-7000-8000-000000000001'
const LOCATION_ID = '00000000-0000-7000-8000-000000000002'
const USERNAME = 'e2e-admin'
const PASSWORD = 'ocwp-e2e-password'
const MIGRATED_CUSTOMER_NAME = 'Cliente Migrado v1'

/**
 * Create the application database by hand in the exact layout Dexie schema
 * version 1 used (before version 2 added the scope indexes), seeded with a
 * pending mutation. The app must upgrade the store in place and still push
 * the preserved queue entry — offline history may never be lost to a schema
 * migration.
 */
async function seedVersionOneDatabase(page: Page): Promise<void> {
  await page.evaluate(
    async ({ organizationId, locationId, displayName }) => {
      const request = indexedDB.open('ocwp', 1)
      const database = await new Promise<IDBDatabase>((resolve, reject) => {
        request.onupgradeneeded = () => {
          const db = request.result
          const customers = db.createObjectStore('customers', { keyPath: 'customer_id' })
          customers.createIndex('organization_id', 'organization_id')
          customers.createIndex('location_id', 'location_id')
          customers.createIndex('display_name', 'display_name')
          customers.createIndex('updated_at', 'updated_at')
          const mutationQueue = db.createObjectStore('mutationQueue', { keyPath: 'mutation_id' })
          mutationQueue.createIndex('state', 'state')
          mutationQueue.createIndex('organization_id', 'organization_id')
          mutationQueue.createIndex('location_id', 'location_id')
          mutationQueue.createIndex('entity_type', 'entity_type')
          mutationQueue.createIndex('queued_at', 'queued_at')
          db.createObjectStore('syncState', { keyPath: 'key' })
          const conflicts = db.createObjectStore('conflicts', { keyPath: 'mutation_id' })
          conflicts.createIndex('entity_type', 'entity_type')
          conflicts.createIndex('entity_id', 'entity_id')
          conflicts.createIndex('recorded_at', 'recorded_at')
        }
        request.onsuccess = () => resolve(request.result)
        request.onerror = () => reject(request.error)
      })
      try {
        const transaction = database.transaction('mutationQueue', 'readwrite')
        const store = transaction.objectStore('mutationQueue')
        const record = {
          mutation_id: crypto.randomUUID(),
          entity_type: 'customer',
          entity_id: crypto.randomUUID(),
          operation: 'create',
          organization_id: organizationId,
          location_id: locationId,
          base_version: null,
          occurred_at: new Date().toISOString(),
          payload: { display_name: displayName },
          state: 'pending',
          queued_at: new Date().toISOString(),
        }
        await new Promise<void>((resolve, reject) => {
          const put = store.put(record)
          put.onsuccess = () => resolve()
          put.onerror = () => reject(put.error)
        })
      } finally {
        database.close()
      }
    },
    {
      organizationId: ORGANIZATION_ID,
      locationId: LOCATION_ID,
      displayName: MIGRATED_CUSTOMER_NAME,
    },
  )
}

test('dexie schema upgrade preserves queued mutations and syncs them', async ({ page }) => {
  // Load the shell first, seed a version-1 database before logging in (the
  // app only opens IndexedDB once a session exists), then let Dexie upgrade
  // the store when the session starts syncing.
  await page.goto('/')
  await seedVersionOneDatabase(page)

  await page.getByLabel('Organización').fill(ORGANIZATION_ID)
  await page.getByLabel('Usuario').fill(USERNAME)
  await page.getByLabel('Contraseña').fill(PASSWORD)
  await page.getByRole('button', { name: 'Iniciar sesión' }).click()
  await expect(page.getByText('Sesión:')).toBeVisible()

  // The preserved pre-upgrade mutation is applied and the queue drains.
  await expect(page.getByLabel('Estado de sincronización')).toContainText('Sincronizado', {
    timeout: 20_000,
  })

  const migrated = await page.evaluate(
    async ({ displayName }) => {
      const request = indexedDB.open('ocwp')
      const database = await new Promise<IDBDatabase>((resolve, reject) => {
        request.onsuccess = () => resolve(request.result)
        request.onerror = () => reject(request.error)
      })
      try {
        const queue = database.transaction('mutationQueue', 'readonly').objectStore('mutationQueue')
        const pending = await new Promise<number>((resolve, reject) => {
          const count = queue.count()
          count.onsuccess = () => resolve(count.result)
          count.onerror = () => reject(count.error)
        })
        const customers = database.transaction('customers', 'readonly').objectStore('customers')
        const rows = await new Promise<{ display_name: string }[]>((resolve, reject) => {
          const all = customers.getAll()
          all.onsuccess = () => resolve(all.result)
          all.onerror = () => reject(all.error)
        })
        return { pending, found: rows.some((row) => row.display_name === displayName) }
      } finally {
        database.close()
      }
    },
    { displayName: MIGRATED_CUSTOMER_NAME },
  )

  expect(migrated.pending).toBe(0)
  expect(migrated.found).toBe(true)
})

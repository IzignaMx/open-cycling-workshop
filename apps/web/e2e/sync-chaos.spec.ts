import { expect, test, type Page } from '@playwright/test'

const ORGANIZATION_ID = '00000000-0000-7000-8000-000000000001'
const LOCATION_ID = '00000000-0000-7000-8000-000000000002'
const USERNAME = 'e2e-admin'
const PASSWORD = 'ocwp-e2e-password'

interface ChangeFeedItem {
  entity_id: string
  operation?: string
}

interface LocalCustomerRow {
  customer_id: string
  display_name: string
}

async function readCustomers(page: Page): Promise<LocalCustomerRow[]> {
  return page.evaluate(async () => {
    const request = indexedDB.open('ocwp')
    const database = await new Promise<IDBDatabase>((resolve, reject) => {
      request.onsuccess = () => resolve(request.result)
      request.onerror = () => reject(request.error)
    })
    try {
      const transaction = database.transaction('customers', 'readonly')
      const store = transaction.objectStore('customers')
      return await new Promise<LocalCustomerRow[]>((resolve, reject) => {
        const all = store.getAll()
        all.onsuccess = () => resolve(all.result as LocalCustomerRow[])
        all.onerror = () => reject(all.error)
      })
    } finally {
      database.close()
    }
  })
}

async function login(page: Page) {
  await page.goto('/')
  await page.getByLabel('Organización').fill(ORGANIZATION_ID)
  await page.getByLabel('Usuario').fill(USERNAME)
  await page.getByLabel('Contraseña').fill(PASSWORD)
  await page.getByRole('button', { name: 'Iniciar sesión' }).click()
  await expect(page.getByText('Sesión:')).toBeVisible()
  await expect(page.getByText('Admin E2E')).toBeVisible()
}

async function sessionToken(page: Page): Promise<string> {
  return page.evaluate(
    () =>
      (JSON.parse(window.sessionStorage.getItem('ocwp.session.v2') ?? '{}').token ?? '') as string,
  )
}

async function pendingMutationCount(page: Page): Promise<number> {
  return page.evaluate(async () => {
    const request = indexedDB.open('ocwp')
    const database = await new Promise<IDBDatabase>((resolve, reject) => {
      request.onsuccess = () => resolve(request.result)
      request.onerror = () => reject(request.error)
    })
    try {
      const transaction = database.transaction('mutationQueue', 'readonly')
      const store = transaction.objectStore('mutationQueue')
      return await new Promise<number>((resolve, reject) => {
        const count = store.count()
        count.onsuccess = () => resolve(count.result)
        count.onerror = () => reject(count.error)
      })
    } finally {
      database.close()
    }
  })
}

test('duplicate mutation delivery applies exactly once and still drains the queue', async ({
  page,
  request,
}) => {
  await login(page)
  await expect(page.getByLabel('Estado de sincronización')).toContainText('Sincronizado', {
    timeout: 15_000,
  })
  const token = await sessionToken(page)

  // Intercept the app's push. On the first delivery we replay the exact
  // mutation out-of-band twice (duplicate delivery at the server boundary)
  // and then reset the connection so the browser never sees a response: it
  // must retry the same mutation id, and idempotency must keep the applied
  // effect singular.
  let interceptedDeliveries = 0
  let outOfBandDeliveries = 0
  await page.route('**/api/v1/sync/mutations', async (route) => {
    interceptedDeliveries += 1
    if (interceptedDeliveries === 1) {
      const headers = { ...route.request().headers() }
      const body = route.request().postData() ?? ''
      for (let i = 0; i < 2; i += 1) {
        const replay = await request.post('/api/v1/sync/mutations', { headers, data: body })
        expect(replay.ok()).toBeTruthy()
        outOfBandDeliveries += 1
      }
      await route.abort('connectionreset')
      return
    }
    await route.continue()
  })

  await page.getByLabel('Nombre').fill('Cliente Caos Duplicado')
  await page.getByLabel('Correo').fill('dup-chaos@example.test')
  await page.getByRole('button', { name: 'Guardar cliente' }).click()
  await expect(page.getByText('Cliente guardado localmente')).toBeVisible()

  // The aborted response reads as offline to the app; the bounded retry
  // re-sends the same mutation id and the receipt deduplicates it.
  await expect(page.getByLabel('Estado de sincronización')).toContainText('Sincronizado', {
    timeout: 20_000,
  })
  await expect.poll(() => pendingMutationCount(page)).toBe(0)
  await page.unrouteAll()

  // Exactly-once for THIS mutation: the change feed holds a single create
  // entry for the chaos customer (the feed legitimately contains multiple
  // entries for entities that other tests updated), and the server-side
  // customer never advanced past version 1.
  const customers = await readCustomers(page)
  const chaosCustomer = customers.find((row) => row.display_name === 'Cliente Caos Duplicado')
  expect(chaosCustomer).toBeDefined()
  const entityId = chaosCustomer!.customer_id

  const feed = await request.get(`/api/v1/sync/changes?cursor=0&location_id=${LOCATION_ID}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  const body = (await feed.json()) as { items: ChangeFeedItem[] }
  const entries = body.items.filter((item) => item.entity_id === entityId)
  expect(entries).toHaveLength(1)
  expect(entries[0].operation).toBe('create')

  const serverCustomer = await request.get(`/api/v1/customers/${entityId}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  const serverBody = (await serverCustomer.json()) as { version: number }
  expect(serverBody.version).toBe(1)

  expect(outOfBandDeliveries).toBe(2)
  expect(interceptedDeliveries).toBeGreaterThanOrEqual(2)
})

test('temporary server failure retries with backoff and converges', async ({ page }) => {
  await login(page)
  await expect(page.getByLabel('Estado de sincronización')).toContainText('Sincronizado', {
    timeout: 15_000,
  })

  // Fail the first two pushes with 503; the app must classify the failure as
  // transient (error state), re-attempt under the bounded backoff policy and
  // converge without losing the local change.
  let failures = 0
  await page.route('**/api/v1/sync/mutations', async (route) => {
    if (failures < 2) {
      failures += 1
      await route.fulfill({ status: 503, contentType: 'application/json', body: '{}' })
      return
    }
    await route.continue()
  })

  await page.getByLabel('Nombre').fill('Cliente Caos 503')
  await page.getByLabel('Correo').fill('five-oh-three@example.test')
  await page.getByRole('button', { name: 'Guardar cliente' }).click()
  await expect(page.getByText('Cliente guardado localmente')).toBeVisible()

  await expect(page.getByLabel('Estado de sincronización')).toContainText('Sincronizado', {
    timeout: 30_000,
  })
  await expect.poll(() => pendingMutationCount(page)).toBe(0)
  await page.unrouteAll()
})

/** Queue mutations exactly like the repository layer does while offline. */
async function queueCreateMutation(page: Page, displayName: string): Promise<void> {
  await page.evaluate(
    async ({ displayName, organizationId, locationId }) => {
      const request = indexedDB.open('ocwp')
      const database = await new Promise<IDBDatabase>((resolve, reject) => {
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
    { displayName, organizationId: ORGANIZATION_ID, locationId: LOCATION_ID },
  )
}

/** Queue a stale update against a customer the server has since moved on. */
async function queueStaleUpdateMutation(
  page: Page,
  entityId: string,
  displayName: string,
): Promise<void> {
  await page.evaluate(
    async ({ entityId, displayName, organizationId, locationId }) => {
      const request = indexedDB.open('ocwp')
      const database = await new Promise<IDBDatabase>((resolve, reject) => {
        request.onsuccess = () => resolve(request.result)
        request.onerror = () => reject(request.error)
      })
      try {
        const transaction = database.transaction('mutationQueue', 'readwrite')
        const store = transaction.objectStore('mutationQueue')
        const record = {
          mutation_id: crypto.randomUUID(),
          entity_type: 'customer',
          entity_id: entityId,
          operation: 'update',
          organization_id: organizationId,
          location_id: locationId,
          base_version: 1,
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
    { entityId, displayName, organizationId: ORGANIZATION_ID, locationId: LOCATION_ID },
  )
}

async function readCustomerIdByDisplayName(
  page: Page,
  displayName: string,
): Promise<string | null> {
  return page.evaluate(
    async ({ displayName }) => {
      const request = indexedDB.open('ocwp')
      const database = await new Promise<IDBDatabase>((resolve, reject) => {
        request.onsuccess = () => resolve(request.result)
        request.onerror = () => reject(request.error)
      })
      try {
        const transaction = database.transaction('customers', 'readonly')
        const store = transaction.objectStore('customers')
        const rows = await new Promise<{ customer_id: string; display_name: string }[]>(
          (resolve, reject) => {
            const all = store.getAll()
            all.onsuccess = () => resolve(all.result)
            all.onerror = () => reject(all.error)
          },
        )
        return rows.find((row) => row.display_name === displayName)?.customer_id ?? null
      } finally {
        database.close()
      }
    },
    { displayName },
  )
}

test('large reconnect batch keeps every valid operation when one mutation conflicts', async ({
  page,
  request,
}) => {
  await login(page)
  await expect(page.getByLabel('Estado de sincronización')).toContainText('Sincronizado', {
    timeout: 15_000,
  })
  const token = await sessionToken(page)

  // Base customer the offline device will edit against a stale version.
  await page.getByLabel('Nombre').fill('Cliente Lote Base')
  await page.getByLabel('Correo').fill('batch-base@example.test')
  await page.getByRole('button', { name: 'Guardar cliente' }).click()
  await expect(page.getByLabel('Estado de sincronización')).toContainText('Sincronizado', {
    timeout: 15_000,
  })
  const baseCustomerId = await readCustomerIdByDisplayName(page, 'Cliente Lote Base')
  expect(baseCustomerId).toBeTruthy()

  // Offline: the server moves the base customer forward while the device
  // queues a batch of three mutations, the middle one built on a stale
  // base_version.
  await page.context().setOffline(true)
  await expect(page.getByLabel('Estado de sincronización')).toContainText('Sin conexión')

  await request.post('/api/v1/sync/mutations', {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      mutations: [
        {
          mutation_id: crypto.randomUUID(),
          entity_type: 'customer',
          entity_id: baseCustomerId,
          operation: 'update',
          organization_id: ORGANIZATION_ID,
          location_id: LOCATION_ID,
          base_version: 1,
          occurred_at: new Date().toISOString(),
          payload: { display_name: 'Cliente Lote Base Remoto' },
        },
      ],
    },
  })

  await queueCreateMutation(page, 'Cliente Lote Valido A')
  await queueStaleUpdateMutation(page, baseCustomerId!, 'Cliente Lote Edicion Obsoleta')
  await queueCreateMutation(page, 'Cliente Lote Valido B')
  await expect.poll(() => pendingMutationCount(page)).toBe(3)

  // Reconnect: exactly one conflict must surface and both independent valid
  // creates must survive it in the same batch.
  await page.context().setOffline(false)
  await page.getByRole('button', { name: 'Sincronizar ahora' }).click()

  await expect(page.getByLabel('Estado de sincronización')).toContainText('Requiere atención', {
    timeout: 20_000,
  })
  await expect.poll(() => pendingMutationCount(page)).toBe(0)

  const center = page.locator('section[aria-labelledby="conflict-center-title"]')
  await expect(center.getByText('Cliente con conflicto')).toBeVisible()
  await expect(center.getByText(/base version/, { exact: false })).toBeVisible()

  const feed = await request.get(`/api/v1/sync/changes?cursor=0&location_id=${LOCATION_ID}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  const body = (await feed.json()) as { items: { payload?: { display_name?: string } }[] }
  const names = body.items.map((item) => item.payload?.display_name ?? '')
  expect(names).toContain('Cliente Lote Valido A')
  expect(names).toContain('Cliente Lote Valido B')
  expect(names).not.toContain('Cliente Lote Edicion Obsoleta')
})

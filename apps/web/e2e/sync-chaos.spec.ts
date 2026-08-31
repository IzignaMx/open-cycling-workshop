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

import { expect, test, type Page } from '@playwright/test'

const ORGANIZATION_ID = '00000000-0000-7000-8000-000000000001'
const LOCATION_ID = '00000000-0000-7000-8000-000000000002'
const USERNAME = 'e2e-admin'
const PASSWORD = 'ocwp-e2e-password'
const CUSTOMER_NAME = 'Cliente Conflicto E2E'
const REMOTE_EDIT_NAME = 'Cliente Editado Remoto'

interface LocalCustomerRow {
  customer_id: string
  display_name: string
  version: number
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
      const result = await new Promise<LocalCustomerRow[]>((resolve, reject) => {
        const all = store.getAll()
        all.onsuccess = () => resolve(all.result as LocalCustomerRow[])
        all.onerror = () => reject(all.error)
      })
      return result
    } finally {
      database.close()
    }
  })
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

async function queuedMutationIds(page: Page): Promise<string[]> {
  return page.evaluate(async () => {
    const request = indexedDB.open('ocwp')
    const database = await new Promise<IDBDatabase>((resolve, reject) => {
      request.onsuccess = () => resolve(request.result)
      request.onerror = () => reject(request.error)
    })
    try {
      const transaction = database.transaction('mutationQueue', 'readonly')
      const store = transaction.objectStore('mutationQueue')
      return await new Promise<string[]>((resolve, reject) => {
        const all = store.getAllKeys()
        all.onsuccess = () => resolve(all.result as string[])
        all.onerror = () => reject(all.error)
      })
    } finally {
      database.close()
    }
  })
}

/** Queue a mutation directly in IndexedDB, exactly like the repository layer
 * does for local edits (customers arrive here through CustomerLocalRepository). */
async function queueUpdateMutation(
  page: Page,
  customer: { customer_id: string },
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
    {
      entityId: customer.customer_id,
      displayName,
      organizationId: ORGANIZATION_ID,
      locationId: LOCATION_ID,
    },
  )
}

async function sessionToken(page: Page): Promise<string> {
  return page.evaluate(
    () =>
      (JSON.parse(window.sessionStorage.getItem('ocwp.session.v2') ?? '{}').token ?? '') as string,
  )
}

test('stale local edit conflicts visibly, persists in Conflict Center and converges', async ({
  page,
  request,
}) => {
  await login(page)

  // 1. Create the customer online; wait until the create is applied.
  await page.getByLabel('Nombre').fill(CUSTOMER_NAME)
  await page.getByLabel('Correo').fill('conflict@example.test')
  await page.getByRole('button', { name: 'Guardar cliente' }).click()
  await expect(page.getByText('Cliente guardado localmente')).toBeVisible()
  await expect(page.getByLabel('Estado de sincronización')).toContainText('Sincronizado', {
    timeout: 15_000,
  })
  await expect.poll(() => pendingMutationCount(page)).toBe(0)

  const customers = await readCustomers(page)
  const customer = customers.find((row) => row.display_name === CUSTOMER_NAME)
  expect(customer).toBeDefined()
  expect(customer?.version).toBe(1)
  const entityId = customer!.customer_id

  // 2. Device goes offline; meanwhile a second device legitimately updates the
  //    same customer on the server (Playwright's request context is not
  //    affected by the browser's offline emulation).
  await page.context().setOffline(true)
  await expect(page.getByLabel('Estado de sincronización')).toContainText('Sin conexión')

  const token = await sessionToken(page)
  const remoteUpdate = await request.post('/api/v1/sync/mutations', {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      mutations: [
        {
          mutation_id: crypto.randomUUID(),
          entity_type: 'customer',
          entity_id: entityId,
          operation: 'update',
          organization_id: ORGANIZATION_ID,
          location_id: LOCATION_ID,
          base_version: 1,
          occurred_at: new Date().toISOString(),
          payload: { display_name: REMOTE_EDIT_NAME },
        },
      ],
    },
  })
  expect(remoteUpdate.ok()).toBeTruthy()
  const remoteBody = (await remoteUpdate.json()) as { results: { status: string }[] }
  expect(remoteBody.results[0].status).toBe('applied')

  // 3. The offline device still knows version 1 and queues a stale edit.
  await queueUpdateMutation(page, { customer_id: entityId }, 'Edicion Local Obsoleta')
  await expect.poll(() => pendingMutationCount(page)).toBe(1)
  const queuedIds = await queuedMutationIds(page)

  // 4. Reconnect and sync: the stale mutation must surface as a conflict.
  await page.context().setOffline(false)
  await page.getByRole('button', { name: 'Sincronizar ahora' }).click()

  await expect(page.getByLabel('Estado de sincronización')).toContainText('Requiere atención', {
    timeout: 15_000,
  })

  // 5. The Conflict Center shows the incident with actionable information.
  const center = page.locator('section[aria-labelledby="conflict-center-title"]')
  await expect(center).toBeVisible()
  await expect(center.getByText('Cliente con conflicto')).toBeVisible()
  await expect(center.getByText(entityId)).toBeVisible()
  await expect(center.getByText('Requiere atención')).toBeVisible()
  await expect(center.getByText(/base version/, { exact: false })).toBeVisible()

  // 6. The conflicted mutation left the retry queue (it lives in the center now).
  await expect.poll(() => pendingMutationCount(page)).toBe(0)
  const drainedIds = await queuedMutationIds(page)
  expect(drainedIds).not.toContain(queuedIds[0])

  // 7. The device converged to the winning remote edit.
  await expect
    .poll(
      async () =>
        (await readCustomers(page)).find((row) => row.customer_id === entityId)?.display_name,
    )
    .toBe(REMOTE_EDIT_NAME)

  // 8. Conflicts persist by scope: after a reload the incident is still there.
  await page.reload({ waitUntil: 'domcontentloaded' })
  await expect(page.getByText('Sesión:')).toBeVisible()
  await expect(center.getByText('Cliente con conflicto')).toBeVisible({ timeout: 15_000 })
  await expect(center.getByText(entityId)).toBeVisible()
})

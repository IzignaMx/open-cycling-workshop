import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Page } from '@playwright/test'

const ORGANIZATION_ID = '00000000-0000-7000-8000-000000000001'
const USERNAME = 'e2e-admin'
const PASSWORD = 'ocwp-e2e-password'
const CUSTOMER_NAME = 'Cliente Offline E2E'

async function login(page: Page) {
  await page.goto('/')
  await page.getByLabel('Organización').fill(ORGANIZATION_ID)
  await page.getByLabel('Usuario').fill(USERNAME)
  await page.getByLabel('Contraseña').fill(PASSWORD)
  await page.getByRole('button', { name: 'Iniciar sesión' }).click()
  await expect(page.getByText('Sesión:')).toBeVisible()
  await expect(page.getByText('Admin E2E')).toBeVisible()
}

async function readIndexedDbCustomerNames(page: Page): Promise<string[]> {
  return page.evaluate(async () => {
    const request = indexedDB.open('ocwp')
    const database = await new Promise<IDBDatabase>((resolve, reject) => {
      request.onsuccess = () => resolve(request.result)
      request.onerror = () => reject(request.error)
    })
    try {
      const transaction = database.transaction('customers', 'readonly')
      const store = transaction.objectStore('customers')
      const result = await new Promise<Array<{ display_name: string }>>((resolve, reject) => {
        const all = store.getAll()
        all.onsuccess = () => resolve(all.result)
        all.onerror = () => reject(all.error)
      })
      return result.map((row) => row.display_name)
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

test('customer persists offline, syncs after reconnect, and converges in a second browser context', async ({
  browser,
}) => {
  const first = await browser.newContext()
  const firstPage = await first.newPage()
  await login(firstPage)

  const accessibility = await new AxeBuilder({ page: firstPage }).analyze()
  expect(
    accessibility.violations.filter((violation) =>
      ['critical', 'serious'].includes(violation.impact ?? ''),
    ),
  ).toEqual([])

  await expect
    .poll(() =>
      firstPage.evaluate(async () => Boolean((await navigator.serviceWorker.ready).active)),
    )
    .toBe(true)

  await first.setOffline(true)
  await expect(firstPage.getByLabel('Estado de sincronización')).toContainText('Sin conexión')
  await firstPage.getByLabel('Nombre').fill(CUSTOMER_NAME)
  await firstPage.getByLabel('Correo').fill('offline@example.test')
  await firstPage.getByRole('button', { name: 'Guardar cliente' }).click()
  await expect(firstPage.getByText('Cliente guardado localmente')).toBeVisible()
  await expect.poll(() => readIndexedDbCustomerNames(firstPage)).toContain(CUSTOMER_NAME)
  await expect.poll(() => pendingMutationCount(firstPage)).toBe(1)

  await firstPage.reload({ waitUntil: 'domcontentloaded' })
  await expect(
    firstPage.getByText('Operación de taller que no se detiene cuando falla Internet.'),
  ).toBeVisible()
  await expect(firstPage.getByLabel('Estado de sincronización')).toContainText('Sin conexión')
  await expect.poll(() => readIndexedDbCustomerNames(firstPage)).toContain(CUSTOMER_NAME)
  await expect.poll(() => pendingMutationCount(firstPage)).toBe(1)

  await first.setOffline(false)
  await expect(firstPage.getByLabel('Estado de sincronización')).toContainText('Sincronizado')
  await expect.poll(() => pendingMutationCount(firstPage)).toBe(0)

  const second = await browser.newContext()
  const secondPage = await second.newPage()
  await login(secondPage)
  await secondPage.getByRole('button', { name: 'Sincronizar ahora' }).click()
  await expect(secondPage.getByLabel('Estado de sincronización')).toContainText('Sincronizado')
  await expect.poll(() => readIndexedDbCustomerNames(secondPage)).toContain(CUSTOMER_NAME)

  await second.close()
  await first.close()
})

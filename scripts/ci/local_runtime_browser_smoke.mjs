// Hosted-only production-PWA journey through the real Caddy edge. Secrets arrive
// over stdin, never command arguments, reports, screenshots or browser traces.
import assert from 'node:assert/strict'
import { createRequire } from 'node:module'

const require = createRequire(new URL('../../apps/web/package.json', import.meta.url))
const { chromium, expect } = require('@playwright/test')
const chunks = []
for await (const chunk of process.stdin) chunks.push(chunk)
const input = JSON.parse(Buffer.concat(chunks).toString('utf8'))
const browser = await chromium.launch()

async function login(page) {
  await page.goto(input.base)
  assert.equal(await page.evaluate(() => window.isSecureContext), true)
  await page.getByLabel('Organización').fill(input.organizationId)
  await page.getByLabel('Usuario', { exact: true }).fill('admin')
  await page.getByLabel('Contraseña').fill(input.password)
  await page.getByRole('button', { name: 'Iniciar sesión' }).click()
  await expect(page.getByText('Sesión:')).toBeVisible()
  await page.evaluate(() => navigator.serviceWorker.ready)
  await expect
    .poll(() => page.evaluate(() => Boolean(navigator.serviceWorker.controller)))
    .toBe(true)
}

async function stored(page, store) {
  return page.evaluate(async (name) => {
    const request = indexedDB.open('ocwp')
    const db = await new Promise((resolve, reject) => {
      request.onsuccess = () => resolve(request.result)
      request.onerror = () => reject(new Error('Could not open local data'))
    })
    try {
      const transaction = db.transaction(name, 'readonly')
      const request = transaction.objectStore(name).getAll()
      return await new Promise((resolve, reject) => {
        request.onsuccess = () => resolve(request.result)
        request.onerror = () => reject(new Error('Could not read local data'))
      })
    } finally {
      db.close()
    }
  }, store)
}

try {
  const context = await browser.newContext()
  const page = await context.newPage()
  await login(page)
  // A controlled browser navigation must preserve the backend JSON 404 as well.
  const probe = await context.newPage()
  const notFound = await probe.goto(`${input.base}/api/does-not-exist`)
  assert.equal(notFound.status(), 404)
  assert.match(notFound.headers()['content-type'], /application\/json/)
  assert.equal(await probe.locator('#root').count(), 0)

  const customerName = 'Customer created offline through Caddy'
  await context.setOffline(true)
  await expect(page.getByLabel('Estado de sincronización')).toContainText('Sin conexión')
  await page.getByLabel('Nombre', { exact: true }).fill(customerName)
  await page.getByLabel('Correo', { exact: true }).fill('caddy-smoke@example.test')
  await page.getByRole('button', { name: 'Guardar cliente' }).click()
  await expect.poll(async () => (await stored(page, 'mutationQueue')).length).toBe(1)
  await page.reload({ waitUntil: 'domcontentloaded' })
  await expect(page.getByLabel('Estado de sincronización')).toContainText('Sin conexión')
  await expect
    .poll(async () => (await stored(page, 'customers')).map((row) => row.display_name))
    .toContain(customerName)
  await expect.poll(async () => (await stored(page, 'mutationQueue')).length).toBe(1)
  // An offline API navigation fails; the service worker cannot pretend success
  // by returning the cached index.html. No TLS/security bypass is configured.
  let offlineApiFailed = false
  try {
    await probe.goto(`${input.base}/api/offline-probe`, { waitUntil: 'domcontentloaded' })
  } catch {
    offlineApiFailed = true
  }
  assert.equal(offlineApiFailed, true)
  assert.equal(await probe.locator('#root').count(), 0)
  await context.setOffline(false)
  await expect(page.getByLabel('Estado de sincronización')).toContainText('Sincronizado', {
    timeout: 45_000,
  })
  await expect.poll(async () => (await stored(page, 'mutationQueue')).length).toBe(0)

  const secondContext = await browser.newContext()
  const secondPage = await secondContext.newPage()
  await login(secondPage)
  await secondPage.getByRole('button', { name: 'Sincronizar ahora' }).click()
  await expect
    .poll(async () => (await stored(secondPage, 'customers')).map((row) => row.display_name))
    .toContain(customerName)
  await secondContext.close()
  await context.close()
  console.log(
    JSON.stringify({ pwaOfflineReload: true, apiNotSpa: true, twoClientConvergence: true }),
  )
} finally {
  await browser.close()
}

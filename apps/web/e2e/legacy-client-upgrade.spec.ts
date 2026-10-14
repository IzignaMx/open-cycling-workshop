import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { expect, test, type Page } from '@playwright/test'

const ROOT = resolve(import.meta.dirname, '../../..')
const BASE = 'http://127.0.0.1:5174'
const ORGANIZATION = '00000000-0000-7000-8000-000000000101'
const PASSWORD = 'ocwp-e2e-password'
function fixture(action: 'legacy-session' | 'activate') {
  return JSON.parse(
    execFileSync('uv', ['run', 'python', 'scripts/e2e/legacy_upgrade_fixture.py', action], {
      cwd: ROOT,
      encoding: 'utf8',
      env: { ...process.env, PYTHONPATH: `${ROOT}:${ROOT}/services/platform/src` },
      stdio: ['ignore', 'pipe', 'pipe'],
    }),
  ) as { token?: string; changed?: boolean }
}
async function login(page: Page) {
  await page.getByLabel('Organización').fill(ORGANIZATION)
  await page.getByLabel('Usuario', { exact: true }).fill('e2e-legacy')
  await page.getByLabel('Contraseña').fill(PASSWORD)
  await page.getByRole('button', { name: 'Iniciar sesión' }).click()
  await expect(page.getByText('Sesión:')).toBeVisible()
}
async function rawDatabase(page: Page, name = 'ocwp') {
  return page.evaluate(async (name) => {
    const opened = indexedDB.open(name)
    const db = await new Promise<IDBDatabase>((resolve, reject) => {
      opened.onupgradeneeded = () => {
        opened.transaction?.abort()
        reject(new Error('Expected existing DB'))
      }
      opened.onsuccess = () => resolve(opened.result)
      opened.onerror = () => reject(opened.error)
    })
    try {
      const names = [...db.objectStoreNames],
        tx = db.transaction(names, 'readonly')
      const rows = await Promise.all(
        names.map(
          (name) =>
            new Promise<[string, unknown[]]>((resolve, reject) => {
              const all = tx.objectStore(name).getAll()
              all.onsuccess = () => resolve([name, all.result])
              all.onerror = () => reject(all.error)
            }),
        ),
      )
      return { version: db.version, stores: Object.fromEntries(rows) }
    } finally {
      db.close()
    }
  }, name)
}
async function queueCustomer(page: Page, name: string) {
  await page.getByLabel('Nombre', { exact: true }).fill(name)
  await page.getByRole('button', { name: 'Guardar cliente' }).click()
  await expect(page.getByText('Cliente guardado localmente')).toBeVisible()
}

// This fixture tenant advances forward exactly once. Retries cannot manufacture
// a pre-cutover session or undo the server's compatibility floor.
test.describe.configure({ retries: 0 })
test('exact old App and SW preserve offline work across floor1 upgrade and late old-tab edits', async ({
  browser,
}) => {
  const evidence = JSON.parse(
    readFileSync(resolve(ROOT, 'artifacts/legacy-client/evidence.json'), 'utf8'),
  )
  expect(evidence.source_commit).toBe('714342c60f4163c7b4c1ebec8433995dccbeea01')
  expect(evidence.assets['sw.js'].sha256).toMatch(/^[0-9a-f]{64}$/)
  const context = await browser.newContext()
  const old = await context.newPage()
  await old.goto(BASE)
  await login(old)
  await expect(old.locator('[data-runtime-state]')).toHaveCount(0)
  await old.evaluate(() => navigator.serviceWorker.ready)
  await expect
    .poll(() => old.evaluate(() => Boolean(navigator.serviceWorker.controller)))
    .toBe(true)
  await expect(old.getByLabel('Estado de sincronización')).toContainText('Sincronizado')

  // The exact archived pre-B issuer creates a real signed legacy session. B's
  // current floor0 login already includes di and is deliberately not mislabeled.
  const legacy = fixture('legacy-session')
  expect(typeof legacy.token).toBe('string')
  await context.setOffline(true)
  await old.evaluate((token) => {
    const session = JSON.parse(sessionStorage.getItem('ocwp.session.v2')!)
    sessionStorage.setItem('ocwp.session.v2', JSON.stringify({ ...session, token }))
  }, legacy.token!)
  await old.reload({ waitUntil: 'domcontentloaded' })
  await expect(old.getByText('Sesión:')).toBeVisible()
  await queueCustomer(old, 'Pending from genuine old App')
  await expect.poll(async () => (await rawDatabase(old)).stores.mutationQueue.length).toBe(1)
  const first = await rawDatabase(old)
  await old.reload({ waitUntil: 'domcontentloaded' })
  expect((await rawDatabase(old)).stores.customers).toEqual(first.stores.customers)
  expect(fixture('activate').changed).toBe(true)
  const refusedLegacy = old.waitForResponse(
    (r) => r.url().includes('/api/v1/') && r.status() === 401,
  )
  await context.setOffline(false)
  await refusedLegacy
  await expect(old.getByRole('button', { name: 'Iniciar sesión' })).toBeVisible()
  const refusedProtocol = old.waitForResponse(
    (r) => r.url().endsWith('/api/v1/sync/mutations') && r.status() === 409,
  )
  await login(old)
  expect((await (await refusedProtocol).json()).error.code).toBe('client_upgrade_required')
  await old.route('**/api/**', (route) => route.abort())
  const preserved = await rawDatabase(old)
  expect(preserved.version).toBe(40)
  expect(preserved.stores.mutationQueue).toHaveLength(1)

  await context.request.post(`${BASE}/__fixture/current`)
  await old.evaluate(async () => {
    const registration = await navigator.serviceWorker.ready
    await new Promise<void>((resolve, reject) => {
      navigator.serviceWorker.addEventListener('controllerchange', () => resolve(), { once: true })
      registration.update().catch(reject)
    })
  })
  const current = await context.newPage()
  await current.goto(BASE)
  await login(current)
  await expect(current.locator('[data-runtime-state="READY"]')).toBeVisible()
  await expect(current.getByText(/Hay datos de una versión anterior/)).toBeVisible()
  expect(await rawDatabase(current)).toEqual(preserved)
  expect((await rawDatabase(current, 'ocwp-authenticated-v1')).stores.operationJournal).toEqual([])
  await expect(current.getByText('Pending from genuine old App', { exact: true })).toHaveCount(0)

  // The existing old tab still executes its actual old bundle after new-SW
  // activation. Its late local write must not be copied, attributed or replayed.
  await queueCustomer(old, 'Late old-tab evidence')
  await expect.poll(async () => (await rawDatabase(old)).stores.mutationQueue.length).toBe(2)
  const late = await rawDatabase(old)
  await current.reload()
  await expect(current.locator('[data-runtime-state="READY"]')).toBeVisible()
  expect(await rawDatabase(current)).toEqual(late)
  expect((await rawDatabase(current, 'ocwp-authenticated-v1')).stores.operationJournal).toEqual([])
  await expect(current.getByText('Late old-tab evidence', { exact: true })).toHaveCount(0)
  await queueCustomer(current, 'New authored customer after safe upgrade')
  await expect(current.getByLabel('Estado de sincronización')).toContainText('Sincronizado')
  const journal = (await rawDatabase(current, 'ocwp-authenticated-v1')).stores.operationJournal
  expect(journal).toHaveLength(1)
  expect(journal[0]).toHaveProperty('authoredDatasetIncarnation')
  await expect
    .poll(
      async () => (await rawDatabase(current, 'ocwp-authenticated-v1')).stores.operationDelivery,
    )
    .toEqual([expect.objectContaining({ state: 'applied' })])
  expect(await rawDatabase(current)).toEqual(late)
  await context.close()
})

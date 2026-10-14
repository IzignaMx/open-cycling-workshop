import AxeBuilder from '@axe-core/playwright'
import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { expect, test, type Page } from '@playwright/test'

const ROOT = resolve(import.meta.dirname, '../../..')
const BASE = 'http://127.0.0.1:5174'
const ORGANIZATION = '00000000-0000-7000-8000-000000000101'
const PASSWORD = 'ocwp-e2e-password'
function fixture(action: 'legacy-session' | 'activate' | 'recover', expectedIncarnation?: string) {
  return JSON.parse(
    execFileSync(
      'uv',
      [
        'run',
        'python',
        'scripts/e2e/legacy_upgrade_fixture.py',
        action,
        ...(expectedIncarnation ? ['--expected-incarnation', expectedIncarnation] : []),
      ],
      {
        cwd: ROOT,
        encoding: 'utf8',
        env: { ...process.env, PYTHONPATH: `${ROOT}:${ROOT}/services/platform/src` },
        stdio: ['ignore', 'pipe', 'pipe'],
      },
    ),
  ) as { token?: string; changed?: boolean; dataset_incarnation?: string }
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
}, info) => {
  test.setTimeout(120_000)
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
  expect(await rawDatabase(old)).toEqual(first)
  expect(fixture('activate').changed).toBe(true)
  const refusedLegacy = old.waitForResponse(
    (r) => r.url().includes('/api/v1/') && r.status() === 401,
  )
  await context.setOffline(false)
  await refusedLegacy
  await expect(old.getByRole('button', { name: 'Iniciar sesión' })).toBeVisible()
  expect(await rawDatabase(old)).toEqual(first)
  const refusedProtocol = old.waitForResponse(
    (r) =>
      r.url() === `${BASE}/api/v1/sync/mutations` &&
      r.request().method() === 'POST' &&
      r.status() === 409,
  )
  await login(old)
  const protocolRefusal = await refusedProtocol
  const requestId = protocolRefusal.headers()['x-request-id']
  expect(requestId).toMatch(/^req-[0-9a-f]{32}$/)
  // The exact old transport never consumes error bodies. Read only the proxy's
  // passive observation of this same response; do not replay the mutation or
  // alter the historical App/SW to make a browser body observer complete.
  await expect
    .poll(async () => {
      const observed = await context.request.get(`${BASE}/__fixture/refusal/${requestId}`)
      if (observed.status() === 404) return null
      expect(observed.status()).toBe(200)
      return observed.json()
    })
    .toEqual({
      requestId,
      method: protocolRefusal.request().method(),
      path: new URL(protocolRefusal.url()).pathname,
      status: protocolRefusal.status(),
      code: 'client_upgrade_required',
    })
  await old.route('**/api/**', (route) => route.abort())
  const preserved = await rawDatabase(old)
  expect(preserved).toEqual(first)
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
  const authored = journal[0] as { entityId: string }
  await expect
    .poll(async () => (await rawDatabase(current, 'ocwp-authenticated-v1')).stores.cacheRecords)
    .toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          entityId: authored.entityId,
          entityType: 'customer',
          version: 1,
          payload: expect.objectContaining({
            display_name: 'New authored customer after safe upgrade',
            version: 1,
          }),
        }),
      ]),
    )
  expect((await rawDatabase(current, 'ocwp-authenticated-v1')).stores.operationJournal).toEqual(
    journal,
  )
  expect(await rawDatabase(current)).toEqual(late)
  // Reuse this isolated tenant for genuine incarnation recovery visibility.
  // Docker acceptance separately proves actual database restore ordering.
  await context.setOffline(true)
  await expect(current.getByLabel('Estado de sincronización')).toContainText('Sin conexión')
  await queueCustomer(current, 'Preserved pending recovery customer')
  const beforeRecovery = await rawDatabase(current, 'ocwp-authenticated-v1')
  const recoveryJournal = beforeRecovery.stores.operationJournal
  expect(recoveryJournal).toHaveLength(2)
  if (!recoveryJournal) throw new Error('Recovery fixture must retain its operation journal')
  const pending = recoveryJournal.find(
    (row) =>
      (row as { optimistic: { display_name: string } }).optimistic.display_name ===
      'Preserved pending recovery customer',
  ) as { mutationId: string; entityId: string; authoredDatasetIncarnation: string }
  expect(fixture('recover', pending.authoredDatasetIncarnation).changed).toBe(true)
  await current.getByRole('button', { name: 'Cerrar esta sesión', exact: true }).click()
  await context.setOffline(false)
  await login(current)
  await expect(current.locator('[data-runtime-state="READY"]')).toBeVisible()
  const recoveryItem = current
    .getByRole('list', { name: 'Trabajo conservado' })
    .getByRole('listitem')
    .filter({ hasText: pending.mutationId })
  await expect(recoveryItem).toContainText('Recuperación pendiente')
  await expect(
    current.getByText('Preserved pending recovery customer', { exact: true }),
  ).toHaveCount(0)
  expect((await rawDatabase(current, 'ocwp-authenticated-v1')).stores.operationJournal).toEqual(
    beforeRecovery.stores.operationJournal,
  )
  for (const [theme, label] of [
    ['banco', 'Banco de trabajo'],
    ['plano', 'Plano técnico'],
    ['ritmo', 'Ritmo modular'],
    ['noche', 'Turno nocturno'],
  ]) {
    await current.getByRole('button', { name: 'Personalización', exact: true }).click()
    const choice = current.getByRole('radio', { name: new RegExp(label!) })
    await choice.focus()
    await choice.press('Space')
    await expect(current.locator('.workshop-shell')).toHaveAttribute('data-theme', theme!)
    await choice.press('Escape')
    for (const width of [1440, 320]) {
      await current.setViewportSize({ width, height: 1000 })
      await expect(recoveryItem).toBeVisible()
      await expect(recoveryItem).not.toContainText('held_recovery')
      await expect(recoveryItem).toContainText(
        `Operación ${pending.mutationId} · Recuperación pendiente`,
      )
      expect(
        await current.evaluate(
          () => document.documentElement.scrollWidth <= document.documentElement.clientWidth,
        ),
      ).toBe(true)
      const accessibility = await new AxeBuilder({ page: current }).analyze()
      expect(
        accessibility.violations.filter((item) =>
          ['critical', 'serious'].includes(item.impact ?? ''),
        ),
      ).toEqual([])
      const name = `authenticated-recovery-${theme}-${width}`
      const path = info.outputPath(`${name}.png`)
      await current.screenshot({ path, fullPage: true })
      await info.attach(name, { path, contentType: 'image/png' })
    }
  }
  expect((await rawDatabase(current, 'ocwp-authenticated-v1')).stores.operationJournal).toEqual(
    beforeRecovery.stores.operationJournal,
  )
  expect(await rawDatabase(current)).toEqual(late)
  await context.close()
})

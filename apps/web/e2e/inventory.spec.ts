import { fixtureHttp, fixtureJson } from './helpers/inventory-http.mjs'
import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Locator, type Page, type TestInfo } from '@playwright/test'
import {
  createCustomer,
  kernelSnapshot,
  PASSWORD,
  waitForReady,
} from './helpers/authenticated-workshop.js'

// Only assertion-backed credential-empty screenshots are retained. Authentication
// tokens and even synthetic password bodies must not enter automatic traces.
test.use({ trace: 'off', video: 'off', screenshot: 'off' })

// Exact parity with scripts/e2e/inventory_fixtures.py, including independent retries.
const CASES = [
  'floor-zero',
  'floor-one',
  'directory',
  'denied',
  'preservation',
  'expiry-idle',
  'expiry-background',
  'scope-race',
  'product-race',
  'logout-race',
  'errors',
  'revocation',
  'empty',
  'visual-banco',
  'visual-plano',
  'visual-ritmo',
  'visual-noche',
] as const
const PRODUCT = 'P000 Cadena sintética'
const PRIVATE_CANARY = 'PRIVATE_INVENTORY_NOTE_CANARY_NOT_FOR_READ_UI'
const THEMES = [
  { id: 'banco', label: 'Banco de trabajo' },
  { id: 'plano', label: 'Plano técnico' },
  { id: 'ritmo', label: 'Ritmo modular' },
  { id: 'noche', label: 'Turno nocturno' },
] as const
function fixture(name: (typeof CASES)[number], info: TestInfo) {
  expect(info.retry).toBeLessThan(2)
  const base = 1_000_000 + info.retry * 100_000 + CASES.indexOf(name) * 1000
  const id = (entity: number) =>
    `00000000-0000-7000-8000-${String(base + entity).padStart(12, '0')}`
  return { id, organizationId: id(0), locationA: id(1), locationB: id(2), productId: id(100) }
}
type Fixture = ReturnType<typeof fixture>
function panel(page: Page) {
  return page.getByRole('region', { name: 'Inventario conectado', exact: true })
}
async function login(page: Page, f: Fixture, role = 'reader') {
  await page.goto('/')
  await page.getByLabel('Organización', { exact: true }).fill(f.organizationId)
  await page.getByLabel('Usuario', { exact: true }).fill(`e2e-inventory-${role}`)
  await page.getByLabel('Contraseña', { exact: true }).fill(PASSWORD)
  await page.getByRole('button', { name: 'Iniciar sesión', exact: true }).click()
  await expect(
    page.locator('[data-runtime-state="SELECTOR"], [data-runtime-state="READY"]'),
  ).toBeVisible({ timeout: 20_000 })
  if (role === 'workshop') await waitForReady(page)
  await expect(panel(page)).toBeVisible()
}
async function openInventory(page: Page, location?: string) {
  const region = panel(page)
  if (location) {
    await region.getByRole('button', { name: 'Consultar talleres', exact: true }).click()
    await expect(
      region.getByRole('combobox', { name: 'Taller para inventario', exact: true }),
    ).toContainText('Taller inventario A')
    await region
      .getByRole('combobox', { name: 'Taller para inventario', exact: true })
      .selectOption(location)
  }
  await region
    .getByRole('button', { name: 'Verificar y consultar inventario', exact: true })
    .click()
  await expect(
    region.getByRole('button', { name: `Consultar ${PRODUCT}`, exact: true }),
  ).toBeVisible()
}
async function selectMain(page: Page) {
  await panel(page)
    .getByRole('button', { name: `Consultar ${PRODUCT}`, exact: true })
    .click()
  await expect(panel(page).getByLabel('Cantidad disponible', { exact: true })).toContainText('148')
  await expect(
    panel(page)
      .getByRole('list', { name: 'Movimientos de inventario', exact: true })
      .getByRole('listitem'),
  ).toHaveCount(50)
  await expect(panel(page).getByRole('heading', { name: PRODUCT, exact: true })).toBeFocused()
}
function trackReads(page: Page) {
  const inventory: string[] = [],
    baseline: string[] = []
  page.on('request', (request) => {
    const path = new URL(request.url()).pathname
    if (path.startsWith('/api/v1/inventory/')) inventory.push(request.method())
    if (path.includes('/sync/baselines')) baseline.push(request.method())
  })
  return { inventory, baseline }
}
async function capture(page: Page, info: TestInfo, name: string, region: Locator = panel(page)) {
  await expect(region).toBeVisible()
  expect(
    await page
      .locator('input[type="password"]')
      .evaluateAll((inputs) => inputs.every((input) => !(input as HTMLInputElement).value)),
  ).toBe(true)
  await page.evaluate(() => {
    for (const node of document.querySelectorAll<HTMLElement>('[style], section, article')) {
      if (getComputedStyle(node).contentVisibility === 'auto')
        node.style.contentVisibility = 'visible'
    }
    window.scrollTo(0, 0)
  })
  const path = info.outputPath(`${name}.png`)
  await page.screenshot({ path, fullPage: true, animations: 'disabled' })
  await info.attach(name, { path, contentType: 'image/png' })
}

for (const floor of ['floor-zero', 'floor-one'] as const) {
  test(`inventory-only ${floor} account reads catalog, independently derived stock and bounded private history`, async ({
    page,
  }, info) => {
    const f = fixture(floor, info),
      requests = trackReads(page)
    await login(page, f)
    const contextResponse = page.waitForResponse(
      (response) => new URL(response.url()).pathname === '/api/v1/auth/context',
    )
    await openInventory(page)
    expect((await (await contextResponse).json()).snapshot_protocol).toBe(
      floor === 'floor-zero' ? null : 'baseline-v1',
    )
    await selectMain(page)
    const region = panel(page),
      ledger = region.getByRole('list', { name: 'Movimientos de inventario', exact: true })
    await expect(ledger).toContainText(f.id(350))
    await expect(ledger).toContainText('CONSUME')
    await expect(ledger).not.toContainText(f.id(349))
    await region.getByRole('button', { name: 'Movimientos anteriores', exact: true }).focus()
    await page.keyboard.press('Enter')
    await expect(ledger.getByRole('listitem')).toHaveCount(4)
    await expect(ledger).toContainText(f.id(349))
    await expect(ledger).toContainText('-4')
    await expect(ledger).toContainText(f.id(348))
    await expect(region.getByLabel('Cantidad disponible', { exact: true })).toContainText('148')
    await expect(region.getByRole('heading', { name: 'Movimientos', exact: true })).toBeFocused()
    await region.getByRole('button', { name: 'Movimientos más recientes', exact: true }).focus()
    await page.keyboard.press('Space')
    await expect(ledger.getByRole('listitem')).toHaveCount(50)
    await expect(region.getByRole('heading', { name: 'Movimientos', exact: true })).toBeFocused()
    await region.getByRole('button', { name: 'Actualizar cantidad', exact: true }).click()
    await expect(region.getByLabel('Cantidad disponible', { exact: true })).toContainText('148')
    await expect(region).not.toContainText(PRIVATE_CANARY)
    await expect(region).not.toContainText('private-order-canary')
    await region.getByRole('button', { name: 'Más productos', exact: true }).click()
    await expect(region.getByRole('button', { name: /^Consultar P/ })).toHaveCount(2)
    await expect(region.getByRole('heading', { name: 'Productos', exact: true })).toBeFocused()
    await expect(region).not.toContainText(PRODUCT)
    await region.getByRole('button', { name: 'Productos anteriores', exact: true }).click()
    await expect(region.getByRole('button', { name: /^Consultar P/ })).toHaveCount(50)
    await expect(region.getByRole('heading', { name: 'Productos', exact: true })).toBeFocused()
    await region.getByRole('button', { name: 'Consultar P001 Saldo negativo', exact: true }).click()
    await expect(region.getByLabel('Cantidad disponible', { exact: true })).toContainText('-7')
    await region
      .getByRole('button', { name: 'Consultar P002 Sin movimientos', exact: true })
      .click()
    await expect(region.getByLabel('Cantidad disponible', { exact: true })).toContainText('0')
    await expect(region).toContainText(/sin movimientos|no hay movimientos/i)
    expect(requests.inventory.length).toBeGreaterThan(5)
    expect(requests.inventory.every((method) => method === 'GET')).toBe(true)
    expect(requests.baseline).toEqual([])
    await capture(page, info, `inventory-${floor}-empty-history`)
  })
}

test('organization-wide inventory directory selection needs no operational baseline and never invents a workshop', async ({
  page,
}, info) => {
  const f = fixture('directory', info),
    requests = trackReads(page)
  await login(page, f, 'directory')
  await openInventory(page, f.locationA)
  await selectMain(page)
  const region = panel(page)
  await region
    .getByRole('combobox', { name: 'Taller para inventario', exact: true })
    .selectOption(f.locationB)
  await expect(region.getByLabel('Cantidad disponible', { exact: true })).toHaveCount(0)
  await region
    .getByRole('button', { name: 'Verificar y consultar inventario', exact: true })
    .click()
  await expect(
    region.getByRole('button', { name: 'Consultar B000 Producto de otro taller', exact: true }),
  ).toBeVisible()
  await expect(region).not.toContainText(PRODUCT)
  expect(requests.baseline).toEqual([])
  expect(requests.inventory.every((method) => method === 'GET')).toBe(true)
})

test('inventory.write alone and organization-wide account without a directory cannot issue inventory reads', async ({
  page,
}, info) => {
  const f = fixture('denied', info),
    requests = trackReads(page)
  await login(page, f, 'writer')
  await panel(page)
    .getByRole('button', { name: 'Verificar y consultar inventario', exact: true })
    .click()
  await expect(panel(page)).toContainText(/sin permiso|no tiene.*permiso|no tienes.*permiso/i)
  expect(requests.inventory).toEqual([])
  await page.getByRole('button', { name: 'Cerrar esta sesión', exact: true }).click()
  await login(page, f, 'no-directory')
  await panel(page)
    .getByRole('button', { name: 'Verificar y consultar inventario', exact: true })
    .click()
  await expect(panel(page)).toContainText('Tu cuenta no tiene acceso al directorio de talleres.')
  await expect(
    panel(page).getByRole('combobox', { name: 'Taller para inventario', exact: true }),
  ).toHaveCount(0)
  expect(requests.inventory).toEqual([])
  expect(requests.baseline).toEqual([])
})

test('inventory navigation retains unsent forms and pre-existing local-only pending work through disconnect/reload', async ({
  page,
  context,
}, info) => {
  const f = fixture('preservation', info)
  await login(page, f, 'workshop')
  const outboundWrites: { method: string; path: string }[] = []
  context.on('request', (request) => {
    const path = new URL(request.url()).pathname
    if (path.startsWith('/api/v1/') && !['GET', 'HEAD', 'OPTIONS'].includes(request.method()))
      outboundWrites.push({ method: request.method(), path })
  })
  // This synthetic identity has real operational grants except sync.push.
  // Pending work therefore cannot race delivery while connected GETs run.
  const operation = await createCustomer(page, 'Inventario conserva el trabajo pendiente')
  const before = await kernelSnapshot(page)
  expect(before.context.capabilities).not.toContain('sync.push')
  expect(before.journal).toEqual([operation])
  expect(before.delivery).toHaveLength(1)
  expect(before.delivery[0]).toMatchObject({
    mutationId: operation.mutationId,
    state: 'pending',
    unresolved: 1,
    attempts: 0,
    attemptId: null,
    result: null,
  })
  // Customer creation has no domain event; without sync.push there must also
  // be no dispatch/result event. Preserve this exact history rather than inventing one.
  expect(before.events).toEqual([])
  expect(outboundWrites).toEqual([])
  await expect(page.getByLabel('Estado de sincronización')).toContainText('Guardado localmente')
  const expectPreserved = async () => {
    const snapshot = await kernelSnapshot(page)
    expect(snapshot.journal).toEqual(before.journal)
    expect(snapshot.delivery).toEqual(before.delivery)
    expect(snapshot.events).toEqual(before.events)
    expect(outboundWrites).toEqual([])
  }
  await page.getByLabel('Nombre', { exact: true }).fill('Borrador local sin enviar')
  await page.getByRole('link', { name: 'Inventario', exact: true }).click()
  await openInventory(page)
  await selectMain(page)
  await expect(page.getByLabel('Nombre', { exact: true })).toHaveValue('Borrador local sin enviar')
  await expectPreserved()
  await context.setOffline(true)
  await page.evaluate(() => window.dispatchEvent(new Event('offline')))
  await expect(panel(page)).toContainText('Inventario no disponible sin conexión')
  await expect(panel(page).getByLabel('Cantidad disponible', { exact: true })).toHaveCount(0)
  await expect(page.getByLabel('Nombre', { exact: true })).toHaveValue('Borrador local sin enviar')
  await expectPreserved()
  await page.reload()
  await waitForReady(page)
  await expect(panel(page)).not.toContainText(PRODUCT)
  const after = await kernelSnapshot(page)
  expect(after.journal).toEqual(before.journal)
  expect(after.delivery).toEqual(before.delivery)
  expect(after.events).toEqual(before.events)
  expect(outboundWrites).toEqual([])
  await expect(page.getByLabel('Estado de sincronización')).toContainText('Sin conexión')
  await capture(page, info, 'inventory-disconnected-journal-preserved')
})

for (const mode of ['idle', 'background'] as const) {
  test(`inventory-only display clears on ${mode} expiry with no further inventory read`, async ({
    page,
  }, info) => {
    const f = fixture(`expiry-${mode}`, info),
      requests = trackReads(page)
    await page.clock.install()
    await login(page, f)
    const contextResponse = page.waitForResponse(
      (response) => new URL(response.url()).pathname === '/api/v1/auth/context',
    )
    await openInventory(page)
    const expiresAt = Date.parse((await (await contextResponse).json()).offline_until)
    await selectMain(page)
    const count = requests.inventory.length
    if (mode === 'idle') {
      const now = await page.evaluate(() => Date.now())
      await page.clock.fastForward(expiresAt - now + 1)
    } else {
      await page.clock.setFixedTime(new Date(expiresAt + 1))
      await page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')))
    }
    await expect(panel(page).getByLabel('Cantidad disponible', { exact: true })).toHaveCount(0)
    await expect(panel(page)).not.toContainText(PRODUCT)
    expect(requests.inventory.length).toBe(count)
    expect(requests.baseline).toEqual([])
  })
}

for (const transition of ['scope', 'product', 'logout'] as const) {
  test(`late inventory stock response after ${transition} cannot overwrite the new selection`, async ({
    page,
  }, info) => {
    const f = fixture(`${transition}-race`, info)
    await login(page, f, transition === 'scope' ? 'directory' : 'reader')
    await openInventory(page, transition === 'scope' ? f.locationA : undefined)
    await selectMain(page)
    let release = () => {},
      held = false,
      once = true
    const gate = new Promise<void>((resolve) => {
      release = resolve
    })
    await page.route(`**/inventory/products/${f.productId}/stock`, async (route) => {
      if (!once) {
        await route.continue()
        return
      }
      once = false
      const response = await fixtureHttp(new URL(page.url()).origin, route.request().url(), {
        headers: route.request().headers(),
      })
      expect(response.status).toBe(200)
      held = true
      await gate
      await route.fulfill(response).catch(() => undefined)
    })
    try {
      await panel(page).getByRole('button', { name: 'Actualizar cantidad', exact: true }).click()
      await expect.poll(() => held).toBe(true)
      if (transition === 'scope') {
        await panel(page)
          .getByRole('combobox', { name: 'Taller para inventario', exact: true })
          .selectOption(f.locationB)
        await panel(page)
          .getByRole('button', { name: 'Verificar y consultar inventario', exact: true })
          .click()
        await expect(
          panel(page).getByRole('button', {
            name: 'Consultar B000 Producto de otro taller',
            exact: true,
          }),
        ).toBeVisible()
      } else if (transition === 'product') {
        await panel(page)
          .getByRole('button', { name: 'Consultar P001 Saldo negativo', exact: true })
          .click()
        await expect(panel(page).getByLabel('Cantidad disponible', { exact: true })).toContainText(
          '-7',
        )
      } else {
        await page.getByRole('button', { name: 'Cerrar esta sesión', exact: true }).click()
        await expect(
          page.getByRole('button', { name: 'Iniciar sesión', exact: true }),
        ).toBeVisible()
        await login(page, f, 'reader-b')
        await panel(page)
          .getByRole('button', { name: 'Verificar y consultar inventario', exact: true })
          .click()
        await expect(
          panel(page).getByRole('button', {
            name: 'Consultar B000 Producto de otro taller',
            exact: true,
          }),
        ).toBeVisible()
      }
      release()
      await page.unrouteAll({ behavior: 'wait' })
      if (transition === 'product')
        await expect(panel(page).getByLabel('Cantidad disponible', { exact: true })).toContainText(
          '-7',
        )
      else
        await expect(panel(page).getByLabel('Cantidad disponible', { exact: true })).toHaveCount(0)
      await expect(panel(page)).not.toContainText('Cantidad recibida: 148')
    } finally {
      release()
      await page.unrouteAll({ behavior: 'wait' })
    }
  })
}

test('committed session revocation clears inventory on the next current read', async ({
  page,
}, info) => {
  const f = fixture('revocation', info)
  await login(page, f)
  await openInventory(page)
  await selectMain(page)
  const origin = new URL(page.url()).origin
  const loginResponse = await fixtureHttp(origin, '/api/v1/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      organization_id: f.organizationId,
      username: 'e2e-inventory-owner',
      password: PASSWORD,
    }),
  })
  expect(loginResponse.status).toBe(200)
  const accessToken = fixtureJson(loginResponse).access_token
  if (typeof accessToken !== 'string' || !accessToken) throw new Error('Fixture session missing')
  const revoked = await fixtureHttp(origin, `/api/v1/admin/users/${f.id(3)}/revoke-sessions`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${accessToken}`,
      'X-OCWP-Write-Protocol': '1',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ expected_version: 1 }),
  })
  expect(revoked.status).toBe(200)
  const denied = page.waitForResponse(
    (response) =>
      new URL(response.url()).pathname === `/api/v1/inventory/products/${f.productId}/stock` &&
      response.status() === 401,
  )
  await panel(page).getByRole('button', { name: 'Actualizar cantidad', exact: true }).click()
  await denied
  await expect(panel(page).getByLabel('Cantidad disponible', { exact: true })).toHaveCount(0)
  await expect(panel(page)).not.toContainText(PRODUCT)
  await expect(page.getByRole('button', { name: 'Iniciar sesión', exact: true })).toBeVisible()
  await capture(page, info, 'inventory-invalid-session')
})

test('unsafe numeric wire values and a failed quantity refresh never show a rounded or stale balance', async ({
  page,
}, info) => {
  const f = fixture('errors', info)
  await login(page, f)
  await openInventory(page)
  await selectMain(page)
  const endpoint = `**/inventory/products/${f.productId}/stock`
  // Clearly labelled malformed-response injection, not authoritative server data.
  await page.route(endpoint, async (route) => {
    const response = await fixtureHttp(new URL(page.url()).origin, route.request().url(), {
      headers: route.request().headers(),
    })
    expect(response.status).toBe(200)
    const body = response.body.replace(
      '"available_quantity":148',
      '"available_quantity":9007199254740991.1',
    )
    expect(body).toContain('9007199254740991.1')
    await route.fulfill({ ...response, body })
  })
  await panel(page).getByRole('button', { name: 'Actualizar cantidad', exact: true }).click()
  await expect(panel(page).getByLabel('Cantidad disponible', { exact: true })).toHaveCount(0)
  await expect(panel(page)).toContainText(
    /cantidad.*(compatible|admitid|represent)|valor.*(compatible|admitid|represent)|respuesta.*válid/i,
  )
  await expect(panel(page)).not.toContainText('9,007,199,254,740,991')
  await page.unrouteAll({ behavior: 'wait' })
  await page.route(endpoint, (route) =>
    route.fulfill({
      status: 503,
      contentType: 'application/json',
      headers: { 'Cache-Control': 'no-store' },
      body: '{"detail":"synthetic temporary unavailable"}',
    }),
  )
  await panel(page).getByRole('button', { name: 'Actualizar cantidad', exact: true }).click()
  await expect(panel(page).getByLabel('Cantidad disponible', { exact: true })).toHaveCount(0)
  await expect(panel(page).getByRole('alert')).toHaveText(
    'El inventario no está disponible en el servidor. Vuelve a consultar más tarde.',
  )
  await expect(
    panel(page).getByRole('button', { name: 'Actualizar cantidad', exact: true }),
  ).toBeEnabled()
  await expect(
    panel(page)
      .getByRole('list', { name: 'Movimientos de inventario', exact: true })
      .getByRole('listitem'),
  ).toHaveCount(50)
  await capture(page, info, 'inventory-quantity-unavailable')
})

test('empty catalog is explicit and inventory JSON is absent from production service-worker cache', async ({
  page,
}, info) => {
  const f = fixture('empty', info)
  await login(page, f)
  await panel(page)
    .getByRole('button', { name: 'Verificar y consultar inventario', exact: true })
    .click()
  await expect(panel(page)).toContainText(/no hay productos|sin productos/i)
  await page.evaluate(async () => navigator.serviceWorker.ready)
  expect(
    await page.evaluate(async () => {
      const requests = (
        await Promise.all((await caches.keys()).map(async (key) => (await caches.open(key)).keys()))
      ).flat()
      return requests.filter((request) =>
        new URL(request.url).pathname.startsWith('/api/v1/inventory'),
      ).length
    }),
  ).toBe(0)
  const api = await fixtureHttp(new URL(page.url()).origin, '/api/v1/inventory/missing')
  expect(api.status).toBe(404)
  expect(api.headers['content-type']).toContain('application/json')
  await capture(page, info, 'inventory-empty-catalog')
  const navigation = await page.context().newPage()
  await navigation.goto('/')
  await navigation.evaluate(async () => navigator.serviceWorker.ready)
  await page.context().setOffline(true)
  let failed = false
  try {
    const response = await navigation.goto('/api/v1/inventory/missing')
    expect(response?.status()).not.toBe(200)
    expect(response?.headers()['content-type'] ?? '').not.toContain('text/html')
  } catch (error) {
    expect(String(error)).toMatch(/net::ERR|NS_ERROR|NetworkError/)
    failed = true
  }
  expect(failed).toBe(true)
  await navigation.close()
})

for (const theme of THEMES) {
  test(`inventory ${theme.id} retains four-theme keyboard, target sizes and reflow states`, async ({
    page,
  }, info) => {
    const f = fixture(`visual-${theme.id}`, info)
    test.setTimeout(120_000)
    await login(page, f, 'workshop')
    const settings = page.getByRole('button', { name: 'Personalización', exact: true })
    await settings.click()
    await expect(settings).toHaveAttribute('aria-expanded', 'true')
    const choice = page.getByRole('radio', { name: new RegExp(theme.label) })
    // check() is a no-op for the initially selected Banco radio. Exercise the
    // actual in-panel keyboard contract for every theme, including that default.
    await choice.focus()
    await choice.press('Space')
    await expect(choice).toBeChecked()
    await expect(choice).toBeFocused()
    await choice.press('Escape')
    await expect(page.locator('#personalization-panel')).toBeHidden()
    await expect(settings).toHaveAttribute('aria-expanded', 'false')
    await expect(settings).toBeFocused()
    await openInventory(page)
    await selectMain(page)
    for (const scene of [
      { name: 'desktop', width: 1440, height: 1000, scale: 1, scheme: 'light', workshop: false },
      { name: 'tablet', width: 820, height: 1180, scale: 1, scheme: 'dark', workshop: true },
      { name: 'narrow', width: 320, height: 900, scale: 1, scheme: 'light', workshop: true },
      { name: 'css200', width: 640, height: 1200, scale: 2, scheme: 'dark', workshop: false },
    ]) {
      await page.getByRole('button', { name: 'Personalización', exact: true }).click()
      await page
        .getByRole('combobox', { name: 'Esquema de superficies', exact: true })
        .selectOption(scene.scheme)
      await page.getByLabel('Modo taller', { exact: false }).setChecked(scene.workshop)
      await page.getByRole('button', { name: 'Cerrar personalización', exact: true }).click()
      await expect(page.locator('.workshop-shell')).toHaveAttribute('data-theme', theme.id)
      await expect(page.locator('.workshop-shell')).toHaveAttribute('data-scheme', scene.scheme)
      await expect(page.locator('.workshop-shell')).toHaveAttribute(
        'data-density',
        scene.workshop ? 'workshop' : 'comfortable',
      )
      await page.setViewportSize({ width: scene.width, height: scene.height })
      await page.evaluate((zoom) => {
        document.documentElement.style.zoom = String(zoom)
      }, scene.scale)
      await expect(panel(page).getByLabel('Cantidad disponible', { exact: true })).toContainText(
        '148',
      )
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1,
        ),
      ).toBe(true)
      const small = await panel(page)
        .getByRole('button')
        .evaluateAll((buttons) =>
          buttons
            .filter((button) => {
              const rect = button.getBoundingClientRect()
              return rect.width > 0 && rect.height > 0 && (rect.width < 44 || rect.height < 44)
            })
            .map((button) => button.textContent),
        )
      expect(small).toEqual([])
      if (scene.workshop) {
        const primary = panel(page).getByRole('button', {
          name: 'Actualizar cantidad',
          exact: true,
        })
        expect((await primary.boundingBox())!.height).toBeGreaterThanOrEqual(56)
      }
      const geometry = await panel(page)
        .getByRole('button')
        .evaluateAll((buttons) => {
          const zoom = Number(getComputedStyle(document.documentElement).zoom)
          return buttons.map((button) => {
            const rect = button.getBoundingClientRect(),
              style = getComputedStyle(button)
            const words = []
            const walker = document.createTreeWalker(button, NodeFilter.SHOW_TEXT)
            for (let node = walker.nextNode(); node; node = walker.nextNode()) {
              for (const word of (node.textContent ?? '').matchAll(/\S+/g)) {
                const range = document.createRange()
                range.setStart(node, word.index)
                range.setEnd(node, word.index + word[0].length)
                words.push({
                  text: word[0],
                  rects: Array.from(range.getClientRects(), (r) => ({
                    left: r.left,
                    right: r.right,
                  })),
                })
              }
            }
            return {
              text: button.textContent,
              width: rect.width / zoom,
              height: rect.height / zoom,
              left:
                rect.left +
                zoom * (parseFloat(style.paddingLeft) + parseFloat(style.borderLeftWidth)),
              right:
                rect.right -
                zoom * (parseFloat(style.paddingRight) + parseFloat(style.borderRightWidth)),
              words,
            }
          })
        })
      await info.attach(`inventory-${theme.id}-${scene.name}-control-geometry`, {
        body: JSON.stringify(geometry),
        contentType: 'application/json',
      })
      for (const control of geometry) {
        expect(control.width).toBeGreaterThanOrEqual(44)
        expect(control.height).toBeGreaterThanOrEqual(scene.workshop ? 56 : 44)
        for (const word of control.words) {
          expect(word.rects, `intact control word: ${word.text}`).toHaveLength(1)
          expect(word.rects[0]!.left).toBeGreaterThanOrEqual(control.left - 0.5)
          expect(word.rects[0]!.right).toBeLessThanOrEqual(control.right + 0.5)
        }
      }
      const refresh = panel(page).getByRole('button', { name: 'Actualizar cantidad', exact: true })
      await refresh.focus()
      await page.keyboard.press('Tab')
      await expect(
        panel(page).getByRole('button', { name: 'Movimientos más recientes', exact: true }),
      ).toBeFocused()
      await page.keyboard.press('Shift+Tab')
      await expect(refresh).toBeFocused()
      await capture(page, info, `inventory-${theme.id}-${scene.name}`)
    }
    await page.evaluate(() => {
      document.documentElement.style.zoom = '1'
    })
    await page.setViewportSize({ width: 820, height: 1180 })
    await page.emulateMedia({ forcedColors: 'active' })
    await capture(page, info, `inventory-${theme.id}-forced-colors`)
    await page.emulateMedia({ forcedColors: 'none' })
    const results = await new AxeBuilder({ page }).include('#workshop-inventory').analyze()
    expect(
      results.violations.filter((violation) =>
        ['critical', 'serious'].includes(violation.impact ?? ''),
      ),
    ).toEqual([])
  })
}

import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Locator, type Page, type TestInfo } from '@playwright/test'
import {
  createCaseIdentity,
  WORKSHOP_CAPABILITIES,
  DATABASE,
  kernelSnapshot,
  login,
  ORGANIZATION_ID,
  waitForReady,
} from './helpers/authenticated-workshop.js'
import { seedWorkshop, READ_CAPABILITIES, addScopedVisualUser } from './helpers/visual-fixture.js'

const THEMES = [
  { id: 'banco', label: 'Banco de trabajo', palette: 'bosque' },
  { id: 'plano', label: 'Plano técnico', palette: 'cobalto' },
  { id: 'ritmo', label: 'Ritmo modular', palette: 'malva' },
  { id: 'noche', label: 'Turno nocturno', palette: 'lima' },
] as const
const VALID_LOGO =
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNQCbD7DwADAAGyeEyo+gAAAABJRU5ErkJggg=='

async function operationalSnapshot(page: Page) {
  const snapshot = await kernelSnapshot(page)
  return {
    version: snapshot.version,
    journal: snapshot.journal,
    delivery: snapshot.delivery,
    events: snapshot.events,
    records: snapshot.records,
  }
}

async function openSettings(page: Page) {
  await page.getByRole('button', { name: 'Personalización', exact: true }).click()
  await expect(page.getByRole('radio', { name: /Banco de trabajo/ })).toBeEnabled()
}

async function attachScreenshot(page: Page, info: TestInfo, name: string, fullPage = false) {
  await page.evaluate(() => window.scrollTo(0, 0))
  const path = info.outputPath(`${name}.png`)
  await page.screenshot({ path, fullPage })
  await info.attach(name, { path, contentType: 'image/png' })
}

async function assertSharedButtonPresentation(button: Locator, minimum = 44) {
  const appearance = await button.evaluate((element) => {
    const actual = getComputedStyle(element)
    const probe = document.createElement('span')
    probe.style.cssText = 'background: var(--ocwp-color-accent); color: var(--ocwp-color-on-accent)'
    element.append(probe)
    const expected = getComputedStyle(probe)
    const result = {
      background: actual.backgroundColor,
      foreground: actual.color,
      expectedBackground: expected.backgroundColor,
      expectedForeground: expected.color,
      paddingX: parseFloat(actual.paddingLeft),
      paddingY: parseFloat(actual.paddingTop),
      radius: parseFloat(actual.borderTopLeftRadius),
      weight: Number(actual.fontWeight),
    }
    probe.remove()
    return result
  })
  // Theme changes legitimately animate Button colors. Wait for exact resolved
  // tokens with normal web-first assertions, rather than sample interpolation.
  await expect(button).toHaveCSS('background-color', appearance.expectedBackground)
  await expect(button).toHaveCSS('color', appearance.expectedForeground)
  expect(appearance.expectedBackground).not.toBe(appearance.expectedForeground)
  expect(appearance.paddingX).toBeGreaterThanOrEqual(16)
  expect(appearance.paddingY).toBeGreaterThanOrEqual(8)
  expect(appearance.radius).toBeGreaterThanOrEqual(4)
  expect(appearance.weight).toBeGreaterThanOrEqual(600)
  const box = await button.boundingBox()
  expect(box!.height).toBeGreaterThanOrEqual(minimum)
  expect(box!.width).toBeGreaterThanOrEqual(minimum)
}

async function assertSingleLine(control: Locator) {
  expect(
    await control.evaluate((element) => {
      const range = document.createRange()
      range.selectNodeContents(element)
      return range.getClientRects().length
    }),
  ).toBe(1)
}

for (const theme of THEMES) {
  test(`${theme.id}: keyboard preserves drafts, history, focus and authenticated pending journal offline`, async ({
    page,
    request,
  }, info) => {
    await page.setViewportSize({ width: 1440, height: 1000 })
    await seedWorkshop(page, request)
    if (theme.id === 'banco') await attachScreenshot(page, info, 'banco-default-desktop')
    const before = await operationalSnapshot(page)
    expect(before.version).toBe(60)
    expect(before.journal).toHaveLength(1)
    expect(before.records.filter((row) => row.entityType === 'bicycle')).toHaveLength(1)
    await page.locator('.workshop-identity').focus()
    await page.keyboard.press('Tab')
    await expect(page.getByRole('button', { name: 'Personalización', exact: true })).toBeFocused()
    for (const name of ['Resumen', 'Órdenes', 'Recepción', 'Incidencias']) {
      await page.keyboard.press('Tab')
      await expect(page.getByRole('link', { name, exact: true })).toBeFocused()
    }
    await page.getByLabel('Nombre', { exact: true }).fill('Borrador de cliente')
    await page.getByLabel('Problema reportado').fill('Borrador sin guardar')
    await page.getByLabel('Agregar bicicleta').check()
    await page.getByLabel('Marca', { exact: true }).fill('Bicicleta en borrador')
    await page.getByLabel('Buscar órdenes').fill('Caso')
    await page.getByText('Historial (3)', { exact: true }).click()
    const draft = await page.getByLabel('Problema reportado').elementHandle()
    await draft!.evaluate((element) => (element as HTMLTextAreaElement).setSelectionRange(3, 8))
    await openSettings(page)
    await page.getByLabel('Paleta personal').selectOption('cobalto')
    const choice = page.getByRole('radio', { name: new RegExp(theme.label) })
    await choice.focus()
    await choice.press('Space')
    await expect(choice).toBeChecked()
    await expect(choice).toBeFocused()
    await expect(page.locator('.workshop-shell')).toHaveAttribute('data-theme', theme.id)
    await expect(page.getByLabel('Paleta personal')).toHaveValue('cobalto')
    await expect(page.locator('.preference-status')).toContainText('guardada en este dispositivo')
    expect(await draft!.evaluate((element) => element.isConnected)).toBe(true)
    expect(
      await draft!.evaluate((element) => (element as HTMLTextAreaElement).selectionStart),
    ).toBe(3)
    await expect(page.getByLabel('Problema reportado')).toHaveValue('Borrador sin guardar')
    await expect(page.getByLabel('Nombre', { exact: true })).toHaveValue('Borrador de cliente')
    await expect(page.getByLabel('Marca', { exact: true })).toHaveValue('Bicicleta en borrador')
    await expect(page.getByLabel('Buscar órdenes')).toHaveValue('Caso')
    await expect(page.locator('.order-history')).toHaveAttribute('open', '')
    expect(await operationalSnapshot(page)).toEqual(before)
    await choice.press('Escape')
    await expect(page.getByRole('button', { name: 'Personalización', exact: true })).toBeFocused()
    await expect(page.locator('#personalization-panel')).toBeHidden()
    for (const name of ['Guardar cliente', 'Guardar orden']) {
      await assertSharedButtonPresentation(page.getByRole('button', { name, exact: true }))
    }
    await assertSingleLine(page.getByRole('button', { name: 'Actualizar', exact: true }))
    const navigation = await page.locator('.workshop-navigation').boundingBox()
    const main = await page.locator('#workshop-content').boundingBox()
    expect(navigation).not.toBeNull()
    expect(main).not.toBeNull()
    if (theme.id === 'plano') expect(main!.y).toBeGreaterThan(navigation!.y + navigation!.height)
    else expect(main!.x).toBeGreaterThan(navigation!.x + navigation!.width)
    const cards = page.locator('.order-card')
    const first = await cards.nth(0).boundingBox(),
      second = await cards.nth(1).boundingBox()
    if (theme.id === 'ritmo' || theme.id === 'noche') expect(second!.x).toBeGreaterThan(first!.x)
    else expect(second!.y).toBeGreaterThan(first!.y)
    const accessibility = await new AxeBuilder({ page }).analyze()
    expect(
      accessibility.violations.filter((item) =>
        ['critical', 'serious'].includes(item.impact ?? ''),
      ),
    ).toEqual([])
    await attachScreenshot(page, info, `${theme.id}-desktop`)
    await page.reload()
    await expect(page.locator('.workshop-shell')).toHaveAttribute('data-theme', theme.id)
    await expect(page.locator('.order-card')).toHaveCount(4)
    expect(await operationalSnapshot(page)).toEqual(before)
    // Retain same-palette structural evidence above, then separately capture
    // the catalog's canonical palette and truthful personal/local settings.
    await openSettings(page)
    await page.getByLabel('Paleta personal').selectOption(theme.palette)
    await expect(page.locator('.preference-status')).toContainText('guardada en este dispositivo')
    const settingsPath = info.outputPath(`${theme.id}-personal-local-settings.png`)
    await page.locator('#personalization-panel').screenshot({ path: settingsPath })
    await info.attach(`${theme.id}-personal-local-settings`, {
      path: settingsPath,
      contentType: 'image/png',
    })
    await page.getByRole('button', { name: 'Cerrar personalización' }).click()
    await attachScreenshot(page, info, `${theme.id}-canonical-desktop-full`, true)
  })
}

test.describe('touch and narrow reflow', () => {
  test.use({ hasTouch: true, viewport: { width: 834, height: 1100 } })
  for (const theme of THEMES) {
    test(`${theme.id}: touch targets, protected states, tablet and 320px reflow`, async ({
      page,
      request,
    }, info) => {
      await seedWorkshop(page, request)
      await openSettings(page)
      await page.getByText(theme.label, { exact: true }).tap()
      await page.getByLabel('Paleta personal').selectOption(theme.palette)
      await expect(page.locator('.workshop-shell')).toHaveAttribute('data-theme', theme.id)
      await page.getByLabel('Modo taller').check()
      await page.getByRole('button', { name: 'Cerrar personalización' }).tap()
      for (const control of [
        page.getByRole('link', { name: '+ Nueva orden' }),
        page.getByRole('button', { name: 'Guardar cliente' }),
        page.getByRole('button', { name: 'Marcar lista' }),
      ]) {
        const box = await control.boundingBox()
        expect(box!.height).toBeGreaterThanOrEqual(56)
        expect(box!.width).toBeGreaterThanOrEqual(56)
      }
      await expect(page.getByText('En trabajo', { exact: true })).toBeVisible()
      const semantic = await page
        .locator('.state-badge[data-tone="success"]')
        .first()
        .evaluate((element) => ({
          foreground: getComputedStyle(element).color,
          background: getComputedStyle(element).backgroundColor,
        }))
      expect(semantic).toEqual({ foreground: 'rgb(34, 89, 59)', background: 'rgb(227, 243, 232)' })
      await attachScreenshot(page, info, `${theme.id}-tablet-touch`)
      await attachScreenshot(page, info, `${theme.id}-tablet-touch-full`, true)
      for (const width of [390, 320]) {
        await page.setViewportSize({ width, height: 900 })
        expect(
          await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
        ).toBe(true)
        await expect(page.getByRole('button', { name: 'Guardar cliente' })).toBeVisible()
        for (const link of await page
          .getByRole('navigation', { name: 'Navegación del taller' })
          .getByRole('link')
          .all()) {
          await assertSingleLine(link)
        }
        await assertSingleLine(page.getByRole('button', { name: 'Actualizar', exact: true }))
        for (const name of ['Guardar cliente', 'Guardar orden']) {
          await assertSharedButtonPresentation(page.getByRole('button', { name, exact: true }), 56)
        }
        const monogram = await page.locator('.workshop-monogram').boundingBox()
        expect(monogram!.width).toBeGreaterThanOrEqual(36)
        expect(monogram!.width).toBeCloseTo(monogram!.height, 1)
      }
      await attachScreenshot(page, info, `${theme.id}-mobile-320`)
      await attachScreenshot(page, info, `${theme.id}-mobile-320-full`, true)
      await page.emulateMedia({ forcedColors: 'active', reducedMotion: 'reduce' })
      // Switch from touch to actual keyboard modality; imperative focus alone
      // intentionally does not require :focus-visible after a pointer interaction.
      await page.locator('.workshop-identity').focus()
      await page.keyboard.press('Tab')
      const settings = page.getByRole('button', { name: 'Personalización', exact: true })
      await expect(settings).toBeFocused()
      expect(await settings.evaluate((element) => element.matches(':focus-visible'))).toBe(true)
      await expect(settings).toHaveCSS('outline-style', 'solid')
      await expect(settings).toHaveCSS('outline-width', '3px')
      const activeLink = page.getByRole('link', { name: 'Resumen', exact: true })
      const activeColors = await activeLink.evaluate((element) => ({
        text: getComputedStyle(element).color,
        background: getComputedStyle(element).backgroundColor,
      }))
      expect(activeColors.text).not.toBe(activeColors.background)
      await expect(activeLink).toHaveCSS('border-top-width', '2px')
      await expect(activeLink).toHaveCSS('text-decoration-line', 'underline')
      await attachScreenshot(page, info, `${theme.id}-mobile-forced-colors-keyboard`)
    })
  }
})

test('personal logo survives offline, follows its workshop, and never another user', async ({
  page,
  request,
}) => {
  const identity = await createCaseIdentity(request, {
    locationId: null,
    capabilities: [...WORKSHOP_CAPABILITIES, 'locations.read'],
  })
  await login(page, identity, 'Taller E2E')
  await openSettings(page)
  await page.getByLabel('Archivo de logo local').setInputFiles({
    name: 'unsafe.svg',
    mimeType: 'image/svg+xml',
    buffer: Buffer.from('<svg onload="alert(1)"/>'),
  })
  await expect(page.getByText(/Elige un archivo PNG o JPEG/)).toBeVisible()
  await page.getByLabel('Archivo de logo local').setInputFiles({
    name: 'local.png',
    mimeType: 'image/png',
    buffer: Buffer.from(VALID_LOGO, 'base64'),
  })
  await expect(page.getByAltText('Vista previa del logo local')).toBeVisible()
  await page.getByRole('button', { name: 'Usar logo en mi vista' }).click()
  await expect(page.locator('.preference-status')).toContainText('guardada en este dispositivo')
  await page.getByRole('button', { name: 'Restablecer mi apariencia' }).click()
  await expect(page.locator('.preference-status')).toContainText('guardada en este dispositivo')
  await page.getByRole('radio', { name: /Ritmo modular/ }).check()
  await expect(page.locator('.preference-status')).toContainText('guardada en este dispositivo')
  await page.context().setOffline(true)
  await page.reload()
  await waitForReady(page)
  await expect(page.locator('.workshop-logo')).toBeVisible()
  expect(
    await page
      .locator('.workshop-logo')
      .evaluate((element) => (element as HTMLImageElement).naturalWidth),
  ).toBeGreaterThan(0)
  await expect(page.locator('.workshop-shell')).toHaveAttribute('data-theme', 'ritmo')
  await page.context().setOffline(false)
  await waitForReady(page)
  await page.getByRole('button', { name: 'Cambiar taller', exact: true }).click()
  await page.getByRole('button', { name: 'Segundo taller E2E', exact: true }).click()
  await waitForReady(page)
  await expect(page.locator('.workshop-monogram')).toBeVisible()
  await expect(page.locator('.workshop-logo')).toHaveCount(0)
  await expect(page.locator('.workshop-shell')).toHaveAttribute('data-theme', 'ritmo')
  await page.getByRole('button', { name: 'Cambiar taller', exact: true }).click()
  await page.getByRole('button', { name: 'Taller E2E', exact: true }).click()
  await waitForReady(page)
  await expect(page.locator('.workshop-logo')).toBeVisible()
  await page.getByRole('button', { name: 'Cerrar esta sesión', exact: true }).click()
  const otherIdentity = await createCaseIdentity(request)
  await login(page, otherIdentity)
  await expect(page.locator('.workshop-logo')).toHaveCount(0)
  await expect(page.locator('.workshop-shell')).toHaveAttribute('data-theme', 'banco')
})

test('read-only permissions, corrupt configuration and failed saves keep the workshop usable', async ({
  page,
  request,
}) => {
  const fixture = await seedWorkshop(page, request, READ_CAPABILITIES)
  await openSettings(page)
  for (const theme of THEMES) {
    await page.getByRole('radio', { name: new RegExp(theme.label) }).check()
    await expect(page.getByRole('button', { name: 'Guardar orden', exact: true })).toHaveCount(0)
    await expect(page.locator('.order-actions button')).toHaveCount(0)
  }
  await expect(page.locator('.preference-status')).toContainText('guardada en este dispositivo')
  const before = await operationalSnapshot(page)
  await page.evaluate(
    async ({ name, organizationId, userId }) => {
      const request = indexedDB.open(name)
      const db = await new Promise<IDBDatabase>((resolve) => {
        request.onsuccess = () => resolve(request.result)
      })
      const tx = db.transaction('presentationPreferences', 'readwrite')
      tx.objectStore('presentationPreferences').put({
        key: JSON.stringify(['appearance', organizationId, userId]),
        organizationId,
        userId,
        locationId: null,
        kind: 'appearance',
        value: { schemaVersion: 1, themeId: 'hostile-theme' },
      })
      await new Promise<void>((resolve, reject) => {
        tx.oncomplete = () => resolve()
        tx.onabort = () => reject(tx.error)
      })
      db.close()
    },
    { name: DATABASE, organizationId: ORGANIZATION_ID, userId: fixture.userId },
  )
  await page.reload()
  await waitForReady(page)
  await openSettings(page)
  await expect(page.locator('.workshop-shell')).toHaveAttribute('data-theme', 'banco')
  await expect(page.locator('.preference-status')).toContainText('no es válida')
  await page.evaluate(() => {
    const original = IDBObjectStore.prototype.put
    IDBObjectStore.prototype.put = function (...args: Parameters<IDBObjectStore['put']>) {
      if (this.name === 'presentationPreferences')
        throw new DOMException('Synthetic quota failure', 'QuotaExceededError')
      return original.apply(this, args)
    }
  })
  await page.getByRole('radio', { name: /Ritmo modular/ }).check()
  await expect(page.locator('.preference-status')).toContainText('no pudo guardarse')
  await expect(page.locator('.workshop-shell')).toHaveAttribute('data-theme', 'ritmo')
  await expect(page.locator('.order-card')).toHaveCount(4)
  expect(await operationalSnapshot(page)).toEqual(before)
})

test("same-workshop restricted user cannot render another reader's cached data or drafts in any theme", async ({
  page,
  request,
}) => {
  const fixture = await seedWorkshop(page, request)
  await expect(page.getByRole('combobox', { name: 'Cliente', exact: true })).toContainText(
    'Cliente de prueba visual',
  )
  await expect(page.locator('.order-summary').first()).toContainText('con bicicleta')
  await page.getByLabel('Nombre', { exact: true }).fill('Borrador privado de cliente')
  await page.getByLabel('Problema reportado').fill('Borrador privado de orden')
  const original = await kernelSnapshot(page)
  const restricted = await addScopedVisualUser(request, fixture.locationId, [
    'customers.write',
    'orders.write',
  ])
  await page.getByRole('button', { name: 'Cerrar esta sesión', exact: true }).click()
  await page.context().setOffline(false)
  await login(page, restricted)
  await openSettings(page)
  for (const theme of THEMES) {
    await page.getByRole('radio', { name: new RegExp(theme.label) }).check()
    await expect(page.locator('.order-card')).toHaveCount(0)
    await expect(page.getByLabel('Buscar órdenes')).toHaveCount(0)
    await expect(page.getByRole('combobox', { name: 'Cliente', exact: true })).toHaveCount(0)
    await expect(page.locator('.order-history')).toHaveCount(0)
    await expect(page.locator('.workshop-metrics dd')).toHaveText([
      'Sin acceso',
      'Sin acceso',
      'Sin acceso',
      'Sin acceso',
    ])
    await expect(page.locator('main')).not.toContainText('Cliente de prueba visual')
    await expect(page.locator('main')).not.toContainText('Cliente pendiente de prueba visual')
    await expect(page.locator('main')).not.toContainText('Caso visual')
    await expect(page.getByLabel('Nombre', { exact: true })).toHaveValue('')
  }
  expect((await kernelSnapshot(page)).journal).toHaveLength(0)
  await page.getByRole('button', { name: 'Cerrar esta sesión', exact: true }).click()
  await login(page, fixture)
  expect((await kernelSnapshot(page)).journal).toEqual(original.journal)
  await expect(page.getByLabel('Nombre', { exact: true })).toHaveValue('')
  await expect(page.getByLabel('Problema reportado')).toHaveValue('')
})

test('partial reads hide bicycle association without changing retained order payloads', async ({
  page,
  request,
}) => {
  const fixture = await seedWorkshop(page, request, [
    'orders.read',
    'orders.write',
    'sync.pull',
    'sync.push',
  ])
  const before = await operationalSnapshot(page)
  await expect(page.locator('.order-card')).toHaveCount(4)
  for (const summary of await page.locator('.order-summary').all())
    await expect(summary).not.toContainText('con bicicleta')
  await expect(page.getByRole('combobox', { name: 'Cliente', exact: true })).toHaveCount(0)
  await expect(page.locator('.workshop-metrics dd').last()).toHaveText('Sin acceso')
  expect(before.records.filter((item) => item.entityType !== 'service_order')).toHaveLength(0)
  await page.getByRole('button', { name: 'Marcar lista', exact: true }).click()
  await expect(page.locator('.order-card').first().locator('.state-badge')).toHaveText('Lista')
  const after = await operationalSnapshot(page)
  expect(after.records).toEqual(before.records)
  expect(after.journal).toHaveLength(1)
  expect(after.journal[0]?.optimistic.bicycle_id).toBe(fixture.bicycleId)
  expect(after.journal[0]?.envelope.payload).toEqual({
    transition: { action: 'mark_ready', actor_id: fixture.userId, note: null },
  })
})

test('shared login button keeps its production styling, keyboard focus and disabled busy state', async ({
  page,
}, info) => {
  let release!: () => void
  const gate = new Promise<void>((resolve) => {
    release = resolve
  })
  await page.route('**/api/v1/auth/login', async (route) => {
    await gate
    await route.fulfill({ status: 401, json: { detail: 'Synthetic login rejection' } })
  })
  try {
    await page.goto('/')
    const login = page.getByRole('button', { name: 'Iniciar sesión', exact: true })
    await assertSharedButtonPresentation(login)
    await page.getByLabel('Organización', { exact: true }).fill('synthetic-org')
    await page.getByLabel('Usuario', { exact: true }).fill('synthetic-user')
    await page.getByLabel('Contraseña', { exact: true }).fill('synthetic-test-only')
    await page.keyboard.press('Tab')
    await expect(login).toBeFocused()
    expect(await login.evaluate((element) => element.matches(':focus-visible'))).toBe(true)
    await expect(login).toHaveCSS('outline-style', 'solid')
    await expect(login).toHaveCSS('outline-width', '2px')
    const focusColor = await login.evaluate((element) => {
      const probe = document.createElement('span')
      probe.style.color = 'var(--ocwp-color-focus)'
      element.append(probe)
      const color = getComputedStyle(probe).color
      probe.remove()
      return color
    })
    await expect(login).toHaveCSS('outline-color', focusColor)
    await attachScreenshot(page, info, 'login-shared-button-keyboard')
    await page.keyboard.press('Enter')
    const busy = page.getByRole('button', { name: 'Ingresando…', exact: true })
    await expect(busy).toBeDisabled()
    await expect(busy).toHaveCSS('opacity', '0.5')
    await assertSharedButtonPresentation(busy)
    await attachScreenshot(page, info, 'login-shared-button-disabled')
    release()
    await expect(login).toBeEnabled()
  } finally {
    release()
  }
})

test('real selector, baseline progress and server upgrade hold remain keyboard accessible', async ({
  page,
  request,
}, info) => {
  const identity = await createCaseIdentity(request, {
    locationId: null,
    capabilities: [...WORKSHOP_CAPABILITIES, 'locations.read'],
  })
  await page.goto('/')
  await page.getByLabel('Organización', { exact: true }).fill(ORGANIZATION_ID)
  await page.getByLabel('Usuario', { exact: true }).fill(identity.username)
  await page.getByLabel('Contraseña', { exact: true }).fill('ocwp-e2e-password')
  await page.getByRole('button', { name: 'Iniciar sesión', exact: true }).click()
  await expect(page.locator('[data-runtime-state="SELECTOR"]')).toBeVisible()
  const assertAccessible = async () => {
    const result = await new AxeBuilder({ page }).analyze()
    expect(
      result.violations.filter((item) => ['critical', 'serious'].includes(item.impact ?? '')),
    ).toEqual([])
  }
  await assertAccessible()
  await attachScreenshot(page, info, 'authenticated-workshop-selector')
  await page.setViewportSize({ width: 320, height: 900 })
  await assertAccessible()
  await attachScreenshot(page, info, 'authenticated-workshop-selector-320', true)
  await page.setViewportSize({ width: 1440, height: 1000 })
  const workshop = page.getByRole('button', { name: 'Taller E2E', exact: true })
  await workshop.focus()
  await expect(workshop).toBeFocused()
  let releaseBaseline = () => {},
    releaseRefusal = () => {}
  const baselineGate = new Promise<void>((resolve) => {
    releaseBaseline = resolve
  })
  const refusalGate = new Promise<void>((resolve) => {
    releaseRefusal = resolve
  })
  await page.route('**/api/v1/sync/baselines/start', async (route) => {
    const response = await route.fetch()
    expect(response.status()).toBe(200)
    await baselineGate
    await route.fulfill({ response })
  })
  try {
    await workshop.press('Enter')
    await expect(page.locator('[data-runtime-state="BASELINE"]')).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Preparando el taller' })).toBeVisible()
    await expect(page.locator('.order-card')).toHaveCount(0)
    await assertAccessible()
    await attachScreenshot(page, info, 'authenticated-baseline-progress')
    releaseBaseline()
    await waitForReady(page)
    await expect(page.getByLabel('Estado de sincronización')).toContainText('Sincronizado')
    expect((await kernelSnapshot(page)).context.principal.userId).toBe(identity.userId)
    const originalPartition = (await kernelSnapshot(page)).partition.partitionId
    let refusalHeld = false
    await page.route('**/api/v1/sync/mutations', async (route) => {
      const headers = { ...route.request().headers() }
      delete headers['x-ocwp-write-protocol']
      // Exercise the actual floor-1 server refusal, not a manufactured error object.
      const response = await route.fetch({ headers })
      expect(response.status()).toBe(409)
      expect(await response.text()).toContain('client_upgrade_required')
      refusalHeld = true
      await refusalGate
      await route.fulfill({ response })
    })
    await page.getByLabel('Nombre', { exact: true }).fill(`Cliente retenido ${crypto.randomUUID()}`)
    await page.getByRole('button', { name: 'Guardar cliente', exact: true }).click()
    await expect.poll(() => refusalHeld).toBe(true)
    const authored = (await kernelSnapshot(page)).journal
    expect(authored).toHaveLength(1)
    releaseRefusal()
    await expect(page.locator('[data-runtime-state="HELD"]')).toBeVisible()
    await expect(page.locator('.order-card')).toHaveCount(0)
    await expect(
      page.getByRole('button', { name: 'Verificar sesión y reintentar', exact: true }),
    ).toBeEnabled()
    expect((await kernelSnapshot(page, originalPartition)).journal).toEqual(authored)
    await assertAccessible()
    await attachScreenshot(page, info, 'authenticated-upgrade-held')
    await page.setViewportSize({ width: 320, height: 900 })
    await assertAccessible()
    await attachScreenshot(page, info, 'authenticated-upgrade-held-320', true)
  } finally {
    releaseBaseline()
    releaseRefusal()
    await page.unrouteAll({ behavior: 'wait' })
  }
})

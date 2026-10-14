import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Locator, type Page, type TestInfo } from '@playwright/test'

const THEMES = [
  { id: 'banco', label: 'Banco de trabajo', palette: 'bosque' },
  { id: 'plano', label: 'Plano técnico', palette: 'cobalto' },
  { id: 'ritmo', label: 'Ritmo modular', palette: 'malva' },
  { id: 'noche', label: 'Turno nocturno', palette: 'lima' },
] as const
const READ_CAPABILITIES = ['customers.read', 'bicycles.read', 'orders.read']
const SCOPE = { organizationId: 'visual-org', userId: 'visual-user', locationId: 'visual-workshop' }
const VALID_LOGO =
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNQCbD7DwADAAGyeEyo+gAAAABJRU5ErkJggg=='

/** Exact Dexie v3 stores at physical IDB version 30, before presentation v4. All data is synthetic. */
async function seedWorkshop(
  page: Page,
  capabilities = [...READ_CAPABILITIES, 'customers.write', 'orders.write'],
) {
  await page.route('**/api/**', (route) => route.abort('internetdisconnected'))
  await page.goto('/')
  await page.evaluate(async () => {
    await navigator.serviceWorker.ready
  })
  await page.evaluate(
    async ({ scope, capabilities }) => {
      const request = indexedDB.open('ocwp', 30)
      request.onupgradeneeded = () => {
        const schema = {
          customers: 'customer_id,organization_id,location_id,display_name,updated_at',
          mutationQueue: 'mutation_id,state,organization_id,location_id,entity_type,queued_at',
          syncState: 'key,scope_key,organization_id,location_id',
          conflicts:
            'mutation_id,scope_key,organization_id,location_id,entity_type,entity_id,recorded_at',
          bicycles: 'bicycle_id,organization_id,location_id,customer_id,updated_at',
          serviceOrders: 'order_id,organization_id,location_id,customer_id,state,updated_at',
          serviceOrderEvents: 'event_id,order_id,organization_id,occurred_at',
        }
        for (const [name, definition] of Object.entries(schema)) {
          const [keyPath, ...indexes] = definition.split(',')
          const store = request.result.createObjectStore(name, { keyPath: keyPath! })
          for (const index of indexes) store.createIndex(index, index)
        }
      }
      const database = await new Promise<IDBDatabase>((resolve, reject) => {
        request.onsuccess = () => resolve(request.result)
        request.onerror = () => reject(request.error)
      })
      const now = '2026-10-14T09:00:00Z'
      const common = {
        organization_id: scope.organizationId,
        location_id: scope.locationId,
        created_at: now,
        updated_at: now,
        version: 1,
      }
      const transaction = database.transaction(
        [
          'customers',
          'bicycles',
          'serviceOrders',
          'serviceOrderEvents',
          'mutationQueue',
          'syncState',
          'conflicts',
        ],
        'readwrite',
      )
      transaction.objectStore('customers').put({
        ...common,
        customer_id: 'visual-customer',
        display_name: 'Cliente de prueba visual',
        email: null,
        phone: null,
      })
      transaction.objectStore('bicycles').put({
        ...common,
        bicycle_id: 'visual-bike',
        customer_id: 'visual-customer',
        brand: 'Prueba',
        model: 'Visual',
      })
      for (const [index, state] of [
        'IN_PROGRESS',
        'WAITING_FOR_PARTS',
        'READY',
        'INTAKE',
      ].entries()) {
        transaction.objectStore('serviceOrders').put({
          ...common,
          order_id: `visual-order-${index}`,
          customer_id: 'visual-customer',
          bicycle_id: 'visual-bike',
          state,
          reported_problem: `Caso visual ${index + 1}: revisión de frenos y transmisión`,
          intake_condition: null,
          accessories: null,
          diagnosis: null,
          priority: 'normal',
          created_at: `2026-10-14T09:00:0${index}Z`,
        })
      }
      transaction.objectStore('serviceOrderEvents').put({
        event_id: 'visual-event',
        order_id: 'visual-order-0',
        organization_id: scope.organizationId,
        from_state: 'AUTHORIZED',
        to_state: 'IN_PROGRESS',
        action: 'start_work',
        actor_id: scope.userId,
        note: null,
        occurred_at: now,
      })
      transaction.objectStore('syncState').put({
        key: `cursor:${scope.organizationId}::${scope.locationId}`,
        scope_key: `${scope.organizationId}::${scope.locationId}`,
        organization_id: scope.organizationId,
        location_id: scope.locationId,
        cursor: 7,
        updated_at: now,
      })
      transaction.objectStore('conflicts').put({
        mutation_id: 'visual-conflict',
        entity_type: 'customer',
        entity_id: 'visual-customer',
        organization_id: scope.organizationId,
        location_id: scope.locationId,
        scope_key: `${scope.organizationId}::${scope.locationId}`,
        reason: 'Conflicto sintético preservado',
        recorded_at: now,
      })
      transaction.objectStore('mutationQueue').put({
        mutation_id: 'visual-pending',
        entity_type: 'customer',
        entity_id: 'visual-customer',
        operation: 'create',
        organization_id: scope.organizationId,
        location_id: scope.locationId,
        base_version: null,
        occurred_at: now,
        queued_at: now,
        state: 'pending',
        payload: { display_name: 'Cliente de prueba visual' },
      })
      await new Promise<void>((resolve, reject) => {
        transaction.oncomplete = () => resolve()
        transaction.onerror = () => reject(transaction.error)
      })
      database.close()
      sessionStorage.setItem(
        'ocwp.session.v2',
        JSON.stringify({
          token: 'synthetic-visual-test',
          user: {
            user_id: scope.userId,
            organization_id: scope.organizationId,
            location_id: scope.locationId,
            display_name: 'Usuario de prueba',
            capabilities,
          },
        }),
      )
    },
    { scope: SCOPE, capabilities },
  )
  const beforeUpgrade = await operationalSnapshot(page)
  expect(beforeUpgrade.version).toBe(30)
  await page.reload()
  await expect(page.getByText('Sesión:')).toBeVisible()
  await expect(page.locator('.order-card')).toHaveCount(4)
  await expect(page.getByLabel('Estado de sincronización')).toContainText('Sin conexión')
  await page.context().setOffline(true)
  const afterUpgrade = await operationalSnapshot(page)
  expect(afterUpgrade.version).toBe(40)
  expect({ ...afterUpgrade, version: 30 }).toEqual(beforeUpgrade)
}

async function operationalSnapshot(page: Page) {
  return page.evaluate(async () => {
    const request = indexedDB.open('ocwp')
    const database = await new Promise<IDBDatabase>((resolve, reject) => {
      request.onsuccess = () => resolve(request.result)
      request.onerror = () => reject(request.error)
    })
    const data: Record<string, unknown> = { version: database.version }
    for (const name of [
      'customers',
      'bicycles',
      'serviceOrders',
      'serviceOrderEvents',
      'mutationQueue',
      'syncState',
      'conflicts',
    ]) {
      data[name] = await new Promise((resolve, reject) => {
        const read = database.transaction(name).objectStore(name).getAll()
        read.onsuccess = () => resolve(read.result)
        read.onerror = () => reject(read.error)
      })
    }
    database.close()
    return data
  })
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
  expect(appearance.background).toBe(appearance.expectedBackground)
  expect(appearance.foreground).toBe(appearance.expectedForeground)
  expect(appearance.background).not.toBe(appearance.foreground)
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
  test(`${theme.id}: keyboard preserves drafts, history, focus and v3 pending queue offline`, async ({
    page,
  }, info) => {
    await page.setViewportSize({ width: 1440, height: 1000 })
    await seedWorkshop(page)
    if (theme.id === 'banco') await attachScreenshot(page, info, 'banco-default-desktop')
    const before = await operationalSnapshot(page)
    expect(before.version).toBe(40)
    expect((before.mutationQueue as unknown[]).length).toBe(1)
    expect((before.bicycles as unknown[]).length).toBe(1)
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
    await page.getByText('Historial (1)', { exact: true }).click()
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
    }, info) => {
      await seedWorkshop(page)
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

test('personal logo remains available offline, is location scoped, and restore does not remove it', async ({
  page,
}) => {
  await seedWorkshop(page)
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
  await expect(page.locator('.workshop-logo')).toBeVisible()
  await page.getByRole('button', { name: 'Restablecer mi apariencia' }).click()
  await expect(page.locator('.preference-status')).toContainText('guardada en este dispositivo')
  await page.reload()
  await expect(page.locator('.workshop-logo')).toBeVisible()
  expect(
    await page
      .locator('.workshop-logo')
      .evaluate((element) => (element as HTMLImageElement).naturalWidth),
  ).toBeGreaterThan(0)
  await page.evaluate(() => {
    const session = JSON.parse(sessionStorage.getItem('ocwp.session.v2')!)
    session.user.location_id = 'other-workshop'
    sessionStorage.setItem('ocwp.session.v2', JSON.stringify(session))
  })
  await page.reload()
  await expect(page.locator('.workshop-monogram')).toBeVisible()
  await expect(page.locator('.order-card')).toHaveCount(0)
})

test('read-only permissions, corrupt configuration and failed saves keep the workshop usable', async ({
  page,
}) => {
  await seedWorkshop(page, READ_CAPABILITIES)
  await openSettings(page)
  for (const theme of THEMES) {
    await page.getByRole('radio', { name: new RegExp(theme.label) }).check()
    await expect(page.getByRole('button', { name: 'Guardar orden', exact: true })).toHaveCount(0)
    await expect(page.locator('.order-actions button')).toHaveCount(0)
  }
  await expect(page.locator('.preference-status')).toContainText('guardada en este dispositivo')
  await page.evaluate(async (scope) => {
    const request = indexedDB.open('ocwp')
    const db = await new Promise<IDBDatabase>((resolve) => {
      request.onsuccess = () => resolve(request.result)
    })
    const tx = db.transaction('presentationPreferences', 'readwrite')
    tx.objectStore('presentationPreferences').put({
      key: JSON.stringify(['appearance', scope.organizationId, scope.userId]),
      organizationId: scope.organizationId,
      userId: scope.userId,
      locationId: null,
      kind: 'appearance',
      value: { schemaVersion: 1, themeId: 'hostile-theme' },
    })
    await new Promise<void>((resolve) => {
      tx.oncomplete = () => resolve()
    })
    db.close()
  }, SCOPE)
  await page.reload()
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
})

test("same-workshop restricted user cannot render another reader's cached data in any theme", async ({
  page,
}) => {
  await seedWorkshop(page)
  await expect(page.getByRole('combobox', { name: 'Cliente', exact: true })).toContainText(
    'Cliente de prueba visual',
  )
  // v3 hardcoded every conflict as customer; retain the row but hide its ambiguous details.
  await expect(page.getByText('Conflicto sintético preservado', { exact: true })).toHaveCount(0)
  await page.evaluate(async (scope) => {
    const request = indexedDB.open('ocwp')
    const database = await new Promise<IDBDatabase>((resolve) => {
      request.onsuccess = () => resolve(request.result)
    })
    const tx = database.transaction('conflicts', 'readwrite')
    tx.objectStore('conflicts').put({
      mutation_id: 'verified-customer-conflict',
      organization_id: scope.organizationId,
      location_id: scope.locationId,
      scope_key: `${scope.organizationId}::${scope.locationId}`,
      entity_type: 'customer',
      entity_type_source: 'queued_mutation',
      entity_id: 'visual-customer',
      reason: 'Conflicto verificado de cliente',
      recorded_at: '2026-10-14T10:00:00Z',
    })
    await new Promise<void>((resolve) => {
      tx.oncomplete = () => resolve()
    })
    database.close()
  }, SCOPE)
  await page.getByRole('button', { name: 'Actualizar', exact: true }).click()
  await expect(page.getByText('Conflicto verificado de cliente', { exact: true })).toBeVisible()
  await expect(page.locator('.order-summary').first()).toContainText('con bicicleta')
  await page.getByLabel('Nombre', { exact: true }).fill('Cliente creado antes del cambio')
  await page.getByRole('button', { name: 'Guardar cliente' }).click()
  await expect(page.getByText('Último cliente local:')).toContainText(
    'Cliente creado antes del cambio',
  )
  const before = await operationalSnapshot(page)
  expect((before.mutationQueue as unknown[]).length).toBe(2)
  await page.evaluate(() => {
    const session = JSON.parse(sessionStorage.getItem('ocwp.session.v2')!)
    session.user.user_id = 'restricted-user-same-workshop'
    session.user.display_name = 'Usuario sin lectura'
    // A write capability must never imply permission to read the retained cache.
    session.user.capabilities = ['customers.write', 'orders.write']
    sessionStorage.setItem('ocwp.session.v2', JSON.stringify(session))
  })
  await page.reload()
  await expect(page.getByText('Usuario sin lectura', { exact: true })).toBeVisible()
  await openSettings(page)
  for (const theme of THEMES) {
    await page.getByRole('radio', { name: new RegExp(theme.label) }).check()
    await expect(page.locator('.order-card')).toHaveCount(0)
    await expect(page.getByLabel('Buscar órdenes')).toHaveCount(0)
    await expect(page.getByRole('combobox', { name: 'Cliente', exact: true })).toHaveCount(0)
    await expect(page.getByText('Historial (1)', { exact: true })).toHaveCount(0)
    await expect(page.getByText('Conflicto sintético preservado', { exact: true })).toHaveCount(0)
    await expect(page.getByText('Conflicto verificado de cliente', { exact: true })).toHaveCount(0)
    await expect(page.getByText('Último cliente local:')).toHaveCount(0)
    await expect(page.locator('.workshop-metrics dd')).toHaveText([
      'Sin acceso',
      'Sin acceso',
      'Sin acceso',
      'Sin acceso',
    ])
    await expect(page.locator('main')).not.toContainText('Cliente de prueba visual')
    await expect(page.locator('main')).not.toContainText('Cliente creado antes del cambio')
    await expect(page.locator('main')).not.toContainText('Caso visual')
  }
  expect(await operationalSnapshot(page)).toEqual(before)
})

test('partial reads hide bicycle association and customer conflicts without changing order payloads', async ({
  page,
}) => {
  await seedWorkshop(page, ['orders.read', 'orders.write'])
  const before = await operationalSnapshot(page)
  await expect(page.locator('.order-card')).toHaveCount(4)
  for (const summary of await page.locator('.order-summary').all()) {
    await expect(summary).not.toContainText('con bicicleta')
  }
  await expect(page.getByText('Conflicto sintético preservado', { exact: true })).toHaveCount(0)
  await expect(page.getByRole('combobox', { name: 'Cliente', exact: true })).toHaveCount(0)
  await expect(page.getByText('Para seleccionar un cliente necesitas el permiso')).toBeVisible()
  await expect(page.locator('.workshop-metrics dd').last()).toHaveText('Sin acceso')
  await page.getByRole('button', { name: 'Marcar lista', exact: true }).click()
  await expect(page.locator('.order-card').first().locator('.state-badge')).toHaveText('Lista')
  const after = await operationalSnapshot(page)
  const changedOrder = (after.serviceOrders as { order_id: string; bicycle_id: string }[]).find(
    (row) => row.order_id === 'visual-order-0',
  )
  expect(changedOrder?.bicycle_id).toBe('visual-bike')
  expect(after.bicycles).toEqual(before.bicycles)
  expect(after.customers).toEqual(before.customers)
  expect(after.conflicts).toEqual(before.conflicts)
  expect((after.mutationQueue as unknown[]).length).toBe(2)
  const transition = (after.mutationQueue as { entity_type: string; payload: unknown }[]).find(
    (row) => row.entity_type === 'service_order',
  )
  expect(transition?.payload).toEqual({
    transition: { action: 'mark_ready', actor_id: SCOPE.userId, note: null },
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

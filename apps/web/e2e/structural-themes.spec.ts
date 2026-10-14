import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Page, type TestInfo } from '@playwright/test'

const THEMES = [
  { id: 'banco', label: 'Banco de trabajo' },
  { id: 'plano', label: 'Plano técnico' },
  { id: 'ritmo', label: 'Ritmo modular' },
  { id: 'noche', label: 'Turno nocturno' },
] as const
const SCOPE = { organizationId: 'visual-org', userId: 'visual-user', locationId: 'visual-workshop' }
const VALID_LOGO =
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNQCbD7DwADAAGyeEyo+gAAAABJRU5ErkJggg=='

/** Exact Dexie v3 stores at physical IDB version 30, before presentation v4. All data is synthetic. */
async function seedWorkshop(page: Page, capabilities = ['customers.write', 'orders.write']) {
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

async function attachScreenshot(page: Page, info: TestInfo, name: string) {
  await page.evaluate(() => window.scrollTo(0, 0))
  const path = info.outputPath(`${name}.png`)
  await page.screenshot({ path })
  await info.attach(name, { path, contentType: 'image/png' })
}

for (const theme of THEMES) {
  test(`${theme.id}: keyboard preserves drafts, history, focus and v3 pending queue offline`, async ({
    page,
  }, info) => {
    await page.setViewportSize({ width: 1440, height: 1000 })
    await seedWorkshop(page)
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
      for (const width of [390, 320]) {
        await page.setViewportSize({ width, height: 900 })
        expect(
          await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
        ).toBe(true)
        await expect(page.getByRole('button', { name: 'Guardar cliente' })).toBeVisible()
      }
      await attachScreenshot(page, info, `${theme.id}-mobile-320`)
      await page.emulateMedia({ forcedColors: 'active', reducedMotion: 'reduce' })
      await page.getByRole('button', { name: 'Personalización', exact: true }).focus()
      expect(
        await page
          .getByRole('button', { name: 'Personalización', exact: true })
          .evaluate((element) => getComputedStyle(element).outlineStyle),
      ).not.toBe('none')
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
  await seedWorkshop(page, [])
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

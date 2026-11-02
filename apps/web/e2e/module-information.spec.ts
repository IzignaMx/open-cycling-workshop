import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Locator, type Page, type Request, type Route } from '@playwright/test'
import {
  DATABASE,
  holdJournalCompletion,
  kernelSnapshot,
  releaseJournalCompletion,
  waitForJournalBarrier,
  waitForReady,
} from './helpers/authenticated-workshop.js'
import { seedWorkshop } from './helpers/visual-fixture.js'
import { moduleInformationBundle } from './helpers/module-information-bundle.mjs'

const SUMMARY = 'Información del módulo integrado'
const UNKNOWN =
  'No se pudo confirmar si el cambio se guardó. No lo envíes otra vez; verifica el estado del taller antes de continuar.'
const STORED = 'Borrador guardado para recuperar al recargar esta sesión.'
const FALLBACK = 'No se pudo mostrar la información del módulo. La recepción sigue disponible.'
const OMITTED = 'Esta compilación no incluye la referencia de información del módulo.'
const CUSTOMER = {
  Nombre: 'Cliente privado mientras inspecciono',
  Correo: 'module@example.invalid',
  Teléfono: '5550177',
}
const ORDER = {
  'Problema reportado': 'Orden privada mientras inspecciono',
  'Condición al recibir': 'Condición privada',
  Accesorios: 'Luz privada',
  Marca: 'Marca privada',
  Modelo: 'Modelo privado',
}
const customerForm = (page: Page) =>
  page.locator('form[aria-describedby~="customer-create-status"]')
const orderForm = (page: Page) => page.locator('form[aria-describedby~="order-intake-status"]')
const inspector = (page: Page) => page.locator('#workshop-module-information')
const summary = (page: Page) => inspector(page).locator('summary')
async function fill(target: Locator, values: Record<string, string>) {
  for (const [name, value] of Object.entries(values))
    await target.getByRole('textbox', { name, exact: true }).fill(value)
}
async function fields(target: Locator, values: Record<string, string>) {
  for (const [name, value] of Object.entries(values))
    await expect(target.getByRole('textbox', { name, exact: true })).toHaveValue(value)
}
async function captureState(page: Page) {
  const kernel = await kernelSnapshot(page)
  const content = await page.evaluate(async (database) => {
    const open = indexedDB.open(database)
    open.onupgradeneeded = () => open.transaction!.abort()
    const db = await new Promise<IDBDatabase>((resolve, reject) => {
      open.onsuccess = () => resolve(open.result)
      open.onerror = () => reject(open.error)
    })
    try {
      const tx = db.transaction(['captureCheckpoints', 'captureDraftContents'], 'readonly')
      return await Promise.all(
        ['captureCheckpoints', 'captureDraftContents'].map(
          (name) =>
            new Promise<unknown[]>((resolve, reject) => {
              const request = tx.objectStore(name).getAll()
              request.onsuccess = () => resolve(request.result)
              request.onerror = () => reject(request.error)
            }),
        ),
      )
    } finally {
      db.close()
    }
  }, DATABASE)
  return { journal: kernel.journal, localSequence: kernel.control.localSequence, content }
}
async function disclosure(page: Page) {
  const control = summary(page)
  await expect(control).toHaveText(SUMMARY)
  await control.focus()
  await control.press('Enter')
  await expect(inspector(page).locator('details')).toHaveAttribute('open', '')
  await expect(control).toBeFocused()
  await expect(control).toHaveCSS('outline-style', 'solid')
  await expect(inspector(page)).toContainText('AGPL-3.0-only')
  await expect(
    inspector(page)
      .locator('dd')
      .filter({ hasText: /^Ninguno$/ }),
  ).toHaveCount(4)
  await expect(inspector(page)).toContainText(
    'La información puede consultarse sin conexión. No habilita operaciones sin conexión.',
  )
  await expect(inspector(page)).toContainText('no instala módulos ni concede permisos')
  await control.press('Space')
  await expect(inspector(page).locator('details')).not.toHaveAttribute('open', '')
  await expect(control).toBeFocused()
}
/** Real unchanged successful context response; no authority or saved result is fabricated. */
async function reverify(page: Page) {
  let release!: () => void
  const waiting = new Promise<void>((resolve) => {
    release = resolve
  })
  let observed = false
  const handler = async (route: Route) => {
    const response = await route.fetch()
    expect(response.status()).toBe(200)
    observed = true
    await waiting
    await route.fulfill({ response })
  }
  await page.route('**/api/v1/auth/context?*', handler)
  try {
    await page.context().setOffline(false)
    await expect.poll(() => observed).toBe(true)
    await expect(customerForm(page)).toHaveCount(0)
    await expect(orderForm(page)).toHaveCount(0)
    release()
    await waitForReady(page)
  } finally {
    release()
    await page.unroute('**/api/v1/auth/context?*', handler)
  }
}

const themes = [
  { id: 'banco', label: 'Banco de trabajo', channel: 'customer' },
  { id: 'plano', label: 'Plano técnico', channel: 'order' },
  { id: 'ritmo', label: 'Ritmo modular', channel: 'customer' },
  { id: 'noche', label: 'Turno nocturno', channel: 'order' },
] as const
for (const theme of themes)
  test(`${theme.id}: module disclosure preserves drafts, pending and UNKNOWN capture guards`, async ({
    page,
    request,
  }, info) => {
    await page.setViewportSize({ width: 1440, height: 1000 })
    const seeded = await seedWorkshop(page, request)
    await page.getByRole('button', { name: 'Personalización', exact: true }).click()
    const choice = page.getByRole('radio', { name: new RegExp(theme.label) })
    await choice.focus()
    await choice.press('Space')
    await expect(choice).toBeChecked()
    await choice.press('Escape')
    await expect(page.locator('.workshop-shell')).toHaveAttribute('data-theme', theme.id)
    await expect(page.locator('.workshop-shell')).toHaveAttribute('data-density', 'comfortable')
    expect((await summary(page).boundingBox())!.height).toBeGreaterThanOrEqual(44)
    if (theme.id === 'noche') {
      await page.getByRole('button', { name: 'Personalización', exact: true }).click()
      await page.getByRole('checkbox', { name: /Modo taller/ }).check()
      await expect(page.locator('.workshop-shell')).toHaveAttribute('data-density', 'workshop')
      await page.getByRole('button', { name: 'Cerrar personalización', exact: true }).click()
      expect((await summary(page).boundingBox())!.height).toBeGreaterThanOrEqual(56)
    }
    await fill(customerForm(page), CUSTOMER)
    await orderForm(page)
      .getByRole('combobox', { name: 'Cliente', exact: true })
      .selectOption(seeded.customerId)
    await orderForm(page)
      .getByRole('combobox', { name: 'Prioridad', exact: true })
      .selectOption('high')
    await orderForm(page).getByLabel('Agregar bicicleta').check()
    await fill(orderForm(page), ORDER)
    await expect(customerForm(page).getByText(STORED, { exact: true })).toBeVisible()
    await expect(orderForm(page).getByText(STORED, { exact: true })).toBeVisible()
    const name = customerForm(page).getByRole('textbox', { name: 'Nombre', exact: true })
    const problem = orderForm(page).getByRole('textbox', {
      name: 'Problema reportado',
      exact: true,
    })
    const nameNode = await name.elementHandle(),
      problemNode = await problem.elementHandle()
    const untouched = await captureState(page)
    await disclosure(page)
    await fields(customerForm(page), CUSTOMER)
    await fields(orderForm(page), ORDER)
    expect(await name.evaluate((node, original) => node === original, nameNode)).toBe(true)
    expect(await problem.evaluate((node, original) => node === original, problemNode)).toBe(true)
    expect(await captureState(page)).toEqual(untouched)
    await expect(customerForm(page)).toHaveAttribute('data-dirty', 'true')
    await expect(orderForm(page)).toHaveAttribute('data-dirty', 'true')

    const customer = theme.channel === 'customer'
    const target = customer ? customerForm(page) : orderForm(page)
    const commandStatus = target.locator(
      customer ? '#customer-create-status' : '#order-intake-status',
    )
    await holdJournalCompletion(
      page,
      customer
        ? { entityType: 'customer', payloadKey: 'display_name', value: CUSTOMER.Nombre }
        : {
            entityType: 'service_order',
            payloadKey: 'reported_problem',
            value: ORDER['Problema reportado'],
          },
    )
    try {
      await target
        .getByRole('button', { name: customer ? 'Guardar cliente' : 'Guardar orden', exact: true })
        .click()
      await waitForJournalBarrier(page)
      const pending = await captureState(page)
      expect(pending.journal).toHaveLength(untouched.journal.length + (customer ? 1 : 2))
      await expect(target.getByRole('button', { name: 'Guardando…', exact: true })).toBeDisabled()
      await disclosure(page)
      await fields(customerForm(page), CUSTOMER)
      await fields(orderForm(page), ORDER)
      expect(await captureState(page)).toEqual(pending)
      await target.evaluate((element) => (element as HTMLFormElement).requestSubmit())
      expect((await kernelSnapshot(page)).journal).toEqual(pending.journal)

      await reverify(page)
      await releaseJournalCompletion(page)
      await expect(commandStatus).toHaveText(UNKNOWN)
      const unknown = await captureState(page)
      await disclosure(page)
      await expect(commandStatus).toHaveText(UNKNOWN)
      await expect(
        target.getByRole('button', {
          name: customer ? 'Guardar cliente' : 'Guardar orden',
          exact: true,
        }),
      ).toBeDisabled()
      await fields(customerForm(page), CUSTOMER)
      await fields(orderForm(page), ORDER)
      expect(await captureState(page)).toEqual(unknown)
      await target.evaluate((element) => (element as HTMLFormElement).requestSubmit())
      expect((await kernelSnapshot(page)).journal).toEqual(pending.journal)
      await summary(page).press('Enter')
      await expect(inspector(page).locator('details')).toHaveAttribute('open', '')
      expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([])
      await info.attach(`module-information-${theme.id}`, {
        body: await page.screenshot({ fullPage: true }),
        contentType: 'image/png',
      })
    } finally {
      await releaseJournalCompletion(page)
    }
  })

test('isolated real module component omits honestly and contains a synchronous detail render failure', async ({
  page,
}, info) => {
  const bundle = await moduleInformationBundle()
  // Only the blank test document is routed. It grants no application authority;
  // actual compiled React components render below, not hand-authored fake forms.
  const fixtureURL = 'https://module-information.invalid/'
  await page.route(fixtureURL, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'text/html',
      body: '<!doctype html><html lang="es"><head><title>Referencia aislada</title></head><body></body></html>',
    }),
  )
  for (const mode of ['omit', 'throw'] as const) {
    await page.goto(fixtureURL)
    await page.setContent(
      `<!doctype html><html lang="es"><head><title>Referencia aislada</title></head><body data-fixture-mode="${mode}"><div id="fixture-root"></div></body></html>`,
    )
    await page.evaluate(() => localStorage.setItem('fixture-sentinel', 'unchanged'))
    const databases = await page.evaluate(() => indexedDB.databases())
    const outbound: string[] = []
    const observe = (request: Request) => outbound.push(request.url())
    page.on('request', observe)
    try {
      await page.addStyleTag({ content: bundle.style })
      await page.addScriptTag({ content: bundle.script })
      await expect(summary(page)).toHaveText(SUMMARY)
      const name = customerForm(page).getByRole('textbox', { name: 'Nombre', exact: true })
      const problem = orderForm(page).getByRole('textbox', {
        name: 'Problema reportado',
        exact: true,
      })
      const originalName = await name.elementHandle(),
        originalProblem = await problem.elementHandle()
      await summary(page).focus()
      await summary(page).press('Enter')
      await expect(summary(page)).toBeFocused()
      await expect(
        inspector(page).getByText(mode === 'omit' ? OMITTED : FALLBACK, { exact: true }),
      ).toBeVisible()
      await expect(inspector(page).locator('dl')).toHaveCount(0)
      await expect(page.locator('body')).not.toContainText('module-render-private-error-canary')
      const attempts = await page.evaluate(
        () =>
          (window as unknown as { moduleInformationFixtureProbe: { renderAttempts: number } })
            .moduleInformationFixtureProbe.renderAttempts,
      )
      if (mode === 'omit') expect(attempts).toBe(0)
      else expect(attempts).toBeGreaterThan(0)
      await name.fill('Cliente editado tras el fallo local')
      await problem.fill('Orden editada tras el fallo local')
      await expect(name).toHaveValue('Cliente editado tras el fallo local')
      await expect(problem).toHaveValue('Orden editada tras el fallo local')
      expect(await name.evaluate((node, original) => node === original, originalName)).toBe(true)
      expect(await problem.evaluate((node, original) => node === original, originalProblem)).toBe(
        true,
      )
      await expect(
        customerForm(page).getByRole('button', { name: 'Guardar cliente' }),
      ).toBeEnabled()
      await expect(orderForm(page).getByRole('button', { name: 'Guardar orden' })).toBeEnabled()
      await summary(page).focus()
      await summary(page).press('Space')
      await expect(inspector(page).locator('details')).not.toHaveAttribute('open', '')
      await summary(page).press('Enter')
      await expect(
        inspector(page).getByText(mode === 'omit' ? OMITTED : FALLBACK, { exact: true }),
      ).toBeVisible()
      expect(
        await page.evaluate(
          () =>
            (window as unknown as { moduleInformationFixtureProbe: { renderAttempts: number } })
              .moduleInformationFixtureProbe.renderAttempts,
        ),
      ).toBe(attempts)
      expect(await page.evaluate(() => ({ ...localStorage }))).toEqual({
        'fixture-sentinel': 'unchanged',
      })
      expect(await page.evaluate(() => indexedDB.databases())).toEqual(databases)
      expect(outbound).toEqual([])
      expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([])
      await info.attach(`module-isolated-${mode}`, {
        body: await page.screenshot({ fullPage: true }),
        contentType: 'image/png',
      })
      // This proves real React boundary/editability isolation, not an authenticated
      // capture commit, full PWA failure journey or universal module sandbox.
    } finally {
      page.off('request', observe)
    }
  }
})

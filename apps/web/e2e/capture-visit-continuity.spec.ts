import AxeBuilder from '@axe-core/playwright'
import {
  expect,
  test,
  type Dialog,
  type Request,
  type Locator,
  type Page,
  type Route,
  type TestInfo,
} from '@playwright/test'
import {
  apiLogin,
  DATABASE,
  holdJournalCompletion,
  kernelSnapshot,
  ORGANIZATION_ID,
  PASSWORD,
  releaseJournalCompletion,
  sessionToken,
  waitForJournalBarrier,
  waitForReady,
  writeHeaders,
} from './helpers/authenticated-workshop.js'
import { addScopedVisualUser, FULL_CAPABILITIES, seedWorkshop } from './helpers/visual-fixture.js'

const UNKNOWN =
  'No se pudo confirmar si el cambio se guardó. No lo envíes otra vez; verifica el estado del taller antes de continuar.'
const customerForm = (page: Page) =>
  page.locator('form[aria-describedby~="customer-create-status"]')
const orderForm = (page: Page) => page.locator('form[aria-describedby~="order-intake-status"]')
const CUSTOMER = {
  Nombre: 'Privado continuidad cliente',
  Correo: 'visit@example.invalid',
  Teléfono: '5550199',
}
const ORDER = {
  'Problema reportado': 'Privado continuidad transmisión',
  'Condición al recibir': 'Privado condición',
  Accesorios: 'Privado candado',
  Marca: 'Privado marca',
  Modelo: 'Privado modelo',
}
async function fill(form: Locator, values: Record<string, string>) {
  for (const [name, value] of Object.entries(values))
    await form.getByRole('textbox', { name, exact: true }).fill(value)
}
async function fields(form: Locator, values: Record<string, string>) {
  for (const [name, value] of Object.entries(values))
    await expect(form.getByRole('textbox', { name, exact: true })).toHaveValue(value)
}
async function evidence(page: Page, info: TestInfo, name: string) {
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([])
  await info.attach(name, {
    body: await page.screenshot({ fullPage: true }),
    contentType: 'image/png',
  })
}
async function masked(page: Page, secrets: string[]) {
  await expect(page.locator('.workshop-shell')).toHaveCount(0)
  await expect(customerForm(page)).toHaveCount(0)
  await expect(orderForm(page)).toHaveCount(0)
  // DOM privacy only; detached/frozen runtime snapshots are controller-test evidence.
  const dom = await page.evaluate(
    () =>
      document.body.outerHTML +
      Array.from(
        document.querySelectorAll('input,textarea,select'),
        (element) => (element as HTMLInputElement).value,
      ).join('\n'),
  )
  for (const secret of secrets) expect(dom).not.toContain(secret)
}
/** Hold an unchanged genuine context response, never manufacture authority. */
async function pauseContext(page: Page) {
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
  return {
    observed: () => observed,
    release,
    async dispose() {
      release()
      await page.unroute('**/api/v1/auth/context?*', handler)
    },
  }
}
async function reverify(page: Page, secrets: string[], info: TestInfo, name: string) {
  await page.context().setOffline(true)
  const barrier = await pauseContext(page)
  try {
    await page.context().setOffline(false)
    await expect.poll(barrier.observed).toBe(true)
    await masked(page, secrets)
    await evidence(page, info, `${name}-masked`)
    barrier.release()
    await waitForReady(page)
  } finally {
    await barrier.dispose()
  }
}
async function dismissDeparture(page: Page, action: () => Promise<unknown>) {
  const dialog = page.waitForEvent('dialog').then(async (confirmation) => {
    const message = confirmation.message()
    await confirmation.dismiss()
    return message
  })
  await action()
  const message = await dialog
  expect(message).toContain('formularios')
  // Fixed copy must not suggest logout confirms or rolls back uncertain work.
  expect(message).toMatch(/no confirma|ni confirma/)
}
async function loginFields(page: Page, username: string) {
  await page.getByLabel('Organización', { exact: true }).fill(ORGANIZATION_ID)
  await page.getByLabel('Usuario', { exact: true }).fill(username)
  await page.getByLabel('Contraseña', { exact: true }).fill(PASSWORD)
}
async function theme(page: Page, label: string) {
  await page.getByRole('button', { name: 'Personalización', exact: true }).click()
  const radio = page.getByRole('radio', { name: new RegExp(label) })
  await radio.focus()
  await radio.press('Space')
  await expect(radio).toBeChecked()
  await radio.press('Escape')
}

type Probe = { terminal: { type: string; trusted: boolean }[]; writes: number; restore(): void }
type ProbeWindow = Window & { captureVisitProbe?: Probe }
async function observeWrites(page: Page) {
  await page.evaluate((database) => {
    const original = IDBObjectStore.prototype.add
    const seen = new WeakSet<IDBTransaction>()
    const probe: Probe = {
      terminal: [],
      writes: 0,
      restore: () => {
        IDBObjectStore.prototype.add = original
      },
    }
    ;(window as ProbeWindow).captureVisitProbe = probe
    IDBObjectStore.prototype.add = function (...args: Parameters<IDBObjectStore['add']>) {
      const result = original.apply(this, args)
      if (this.name === 'operationJournal' && this.transaction.db.name === database) {
        probe.writes++
        if (!seen.has(this.transaction)) {
          seen.add(this.transaction)
          for (const type of ['complete', 'abort'])
            this.transaction.addEventListener(
              type,
              (event) => probe.terminal.push({ type: event.type, trusted: event.isTrusted }),
              { once: true },
            )
        }
      }
      return result
    }
  }, DATABASE)
}
async function probe(page: Page) {
  return page.evaluate(() => {
    const value = (window as ProbeWindow).captureVisitProbe!
    return { terminal: value.terminal, writes: value.writes }
  })
}
async function restoreProbe(page: Page) {
  await page.evaluate(() => (window as ProbeWindow).captureVisitProbe?.restore())
}

test('capture visit restores drafts, hidden bicycle fields and clean retained defaults through real verification', async ({
  page,
  request,
}, info) => {
  const seeded = await seedWorkshop(page, request)
  await theme(page, 'Banco de trabajo')
  const order = orderForm(page)
  await order
    .getByRole('combobox', { name: 'Cliente', exact: true })
    .selectOption(seeded.customerId)
  await order.getByRole('combobox', { name: 'Prioridad', exact: true }).selectOption('high')
  await order
    .getByRole('textbox', { name: 'Problema reportado', exact: true })
    .fill('Orden para defaults limpios')
  await order.getByRole('button', { name: 'Guardar orden' }).click()
  await expect(order.locator('#order-intake-status[role="status"]')).toHaveText(
    'Orden guardada localmente',
  )
  await expect(order).toHaveAttribute('data-dirty', 'false')
  const saved = await kernelSnapshot(page)
  await reverify(page, ['Orden para defaults limpios', seeded.customerId], info, 'defaults')
  await expect(order.getByRole('combobox', { name: 'Cliente', exact: true })).toHaveValue(
    seeded.customerId,
  )
  await expect(order.getByRole('combobox', { name: 'Prioridad', exact: true })).toHaveValue('high')
  await expect(order).toHaveAttribute('data-dirty', 'false')
  await fill(customerForm(page), CUSTOMER)
  await order.getByLabel('Agregar bicicleta').check()
  await fill(order, ORDER)
  await order.getByLabel('Agregar bicicleta').uncheck()
  await reverify(
    page,
    [...Object.values(CUSTOMER), ...Object.values(ORDER), seeded.customerId],
    info,
    'drafts',
  )
  await fields(customerForm(page), CUSTOMER)
  await expect(customerForm(page)).toHaveAttribute('data-dirty', 'true')
  await expect(order.getByLabel('Agregar bicicleta')).not.toBeChecked()
  await order.getByLabel('Agregar bicicleta').check()
  await fields(order, ORDER)
  await expect(order).toHaveAttribute('data-dirty', 'true')
  expect((await kernelSnapshot(page)).journal).toEqual(saved.journal)
  await evidence(page, info, 'drafts-restored')
})

for (const kind of ['customer', 'order'] as const)
  test(`capture visit ${kind} pending and genuine UNKNOWN survive remount without another journal admission`, async ({
    page,
    request,
  }, info) => {
    const seeded = await seedWorkshop(page, request)
    await theme(page, kind === 'customer' ? 'Plano técnico' : 'Ritmo modular')
    const customer = kind === 'customer'
    const form = customer ? customerForm(page) : orderForm(page)
    const values = customer ? CUSTOMER : ORDER
    if (!customer) {
      await form
        .getByRole('combobox', { name: 'Cliente', exact: true })
        .selectOption(seeded.customerId)
      await form.getByLabel('Agregar bicicleta').check()
    }
    await fill(form, values)
    const before = await kernelSnapshot(page)
    await observeWrites(page)
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
      await form
        .getByRole('button', { name: customer ? 'Guardar cliente' : 'Guardar orden' })
        .click()
      await waitForJournalBarrier(page)
      expect(await probe(page)).toEqual({
        writes: customer ? 1 : 2,
        terminal: [{ type: 'complete', trusted: true }],
      })
      const committed = await kernelSnapshot(page)
      expect(committed.journal).toHaveLength(before.journal.length + (customer ? 1 : 2))
      expect(committed.journal.slice(0, before.journal.length)).toEqual(before.journal)
      await reverify(page, Object.values(values), info, `${kind}-pending`)
      await fields(form, values)
      await expect(form.getByRole('button', { name: 'Guardando…', exact: true })).toBeDisabled()
      await form.evaluate((element) => (element as HTMLFormElement).requestSubmit())
      // The native callback gate precedes the kernel postwrite fence. Reverification
      // invalidates its source: real committed bytes are NOT authority to say saved.
      await releaseJournalCompletion(page)
      await expect(
        form.locator(
          customer
            ? '#customer-create-status[role="status"]'
            : '#order-intake-status[role="status"]',
        ),
      ).toHaveText(UNKNOWN)
      await reverify(page, Object.values(values), info, `${kind}-unknown`)
      await fields(form, values)
      await expect(
        form.locator(
          customer
            ? '#customer-create-status[role="status"]'
            : '#order-intake-status[role="status"]',
        ),
      ).toHaveText(UNKNOWN)
      await fill(form, Object.fromEntries(Object.keys(values).map((name) => [name, ''])))
      if (!customer) {
        await form.getByLabel('Agregar bicicleta').uncheck()
        await form.getByRole('combobox', { name: 'Cliente', exact: true }).selectOption('')
      }
      await expect(form).toHaveAttribute('data-dirty', 'true')
      await expect(form.getByRole('button')).toBeDisabled()
      // Restore required validity to make requestSubmit exercise the guard, not
      // merely native required-field validation. UNKNOWN must survive both edits.
      if (!customer)
        await form
          .getByRole('combobox', { name: 'Cliente', exact: true })
          .selectOption(seeded.customerId)
      const input = form.getByRole('textbox', {
        name: customer ? 'Nombre' : 'Problema reportado',
        exact: true,
      })
      await input.fill('Otro intento explícito prohibido')
      await input.press('Enter')
      await form.evaluate((element) => (element as HTMLFormElement).requestSubmit())
      await expect(
        form.locator(
          customer
            ? '#customer-create-status[role="status"]'
            : '#order-intake-status[role="status"]',
        ),
      ).toHaveText(UNKNOWN)
      expect((await kernelSnapshot(page)).journal).toEqual(committed.journal)
      expect((await probe(page)).writes).toBe(customer ? 1 : 2)
      await evidence(page, info, `${kind}-unknown-restored`)
    } finally {
      await releaseJournalCompletion(page)
      await restoreProbe(page)
    }
  })

test('capture visit canceled logout and explicit login while nonready preserve the original draft', async ({
  page,
  request,
}, info) => {
  const seeded = await seedWorkshop(page, request)
  await theme(page, 'Turno nocturno')
  await fill(customerForm(page), CUSTOMER)
  const before = await kernelSnapshot(page)
  const token = await sessionToken(page)
  const barrier = await pauseContext(page)
  try {
    await page.context().setOffline(false)
    await expect.poll(barrier.observed).toBe(true)
    await masked(page, Object.values(CUSTOMER))
    await dismissDeparture(page, () =>
      page.getByRole('button', { name: 'Cancelar', exact: true }).click(),
    )
    expect(await sessionToken(page)).toBe(token)
    barrier.release()
    await waitForReady(page)
  } finally {
    await barrier.dispose()
  }
  await fields(customerForm(page), CUSTOMER)
  // A bounded genuine transport failure reaches HELD, where login is enabled.
  // No forged context/response or disabled-button bypass is used.
  await page.context().setOffline(true)
  const failContext = (route: Route) => route.abort('failed')
  await page.route('**/api/v1/auth/context?*', failContext)
  try {
    await page.context().setOffline(false)
    await expect(page.locator('[data-runtime-state="HELD"]')).toBeVisible()
    await masked(page, Object.values(CUSTOMER))
    let loginPosts = 0
    const countLogin = (request: Request) => {
      if (request.url().endsWith('/api/v1/auth/login') && request.method() === 'POST') loginPosts++
    }
    page.on('request', countLogin)
    try {
      await loginFields(page, seeded.username)
      await dismissDeparture(page, () =>
        page.getByRole('button', { name: 'Iniciar sesión', exact: true }).click(),
      )
      expect(loginPosts).toBe(0)
      expect(await sessionToken(page)).toBe(token)
    } finally {
      page.off('request', countLogin)
    }
    // Administration's session controls require connected account authority;
    // absent/nonready administration guard coverage stays in controller/UI tests.
    await evidence(page, info, 'canceled-login-held')
  } finally {
    await page.unroute('**/api/v1/auth/context?*', failContext)
  }
  await page.getByRole('button', { name: 'Verificar sesión y reintentar', exact: true }).click()
  await waitForReady(page)
  await fields(customerForm(page), CUSTOMER)
  expect((await kernelSnapshot(page)).journal).toEqual(before.journal)
  await evidence(page, info, 'canceled-departure-restored')
})

test('capture visit accepted new principal never displays old private draft or late feedback', async ({
  page,
  request,
}, info) => {
  const seeded = await seedWorkshop(page, request)
  const other = await addScopedVisualUser(
    request,
    seeded.locationId,
    FULL_CAPABILITIES.filter((capability) => capability !== 'sync.pull'),
  )
  await fill(customerForm(page), CUSTOMER)
  await observeWrites(page)
  await holdJournalCompletion(page, {
    entityType: 'customer',
    payloadKey: 'display_name',
    value: CUSTOMER.Nombre,
  })
  try {
    await customerForm(page).getByRole('button', { name: 'Guardar cliente' }).click()
    await waitForJournalBarrier(page)
    const committed = await kernelSnapshot(page)
    await customerForm(page)
      .getByRole('textbox', { name: 'Nombre', exact: true })
      .fill('Privado borrador de visita cerrada')
    page.once('dialog', (dialog) => void dialog.accept())
    await page.getByRole('button', { name: 'Cerrar esta sesión', exact: true }).click()
    await masked(page, ['Privado borrador de visita cerrada', ...Object.values(CUSTOMER)])
    await page.context().setOffline(false)
    await loginFields(page, other.username)
    await page.getByRole('button', { name: 'Iniciar sesión', exact: true }).click()
    await waitForReady(page)
    expect((await kernelSnapshot(page)).context.principal.userId).toBe(other.userId)
    await fields(customerForm(page), { Nombre: '', Correo: '', Teléfono: '' })
    await expect(
      orderForm(page).getByRole('combobox', { name: 'Cliente', exact: true }),
    ).toHaveValue('')
    await customerForm(page)
      .getByRole('textbox', { name: 'Nombre', exact: true })
      .fill('Borrador de nueva visita')
    await releaseJournalCompletion(page)
    // Callback delivery plus rendered-frame observation is bounded browser evidence,
    // not full settlement proof; controller tests await the stale promise itself.
    await page.evaluate(
      () => new Promise<void>((resolve) => requestAnimationFrame(() => resolve())),
    )
    await fields(customerForm(page), {
      Nombre: 'Borrador de nueva visita',
      Correo: '',
      Teléfono: '',
    })
    await expect(customerForm(page).locator('#customer-create-status[role="status"]')).toBeEmpty()
    await expect(page.locator('body')).not.toContainText('Privado borrador de visita cerrada')
    expect((await kernelSnapshot(page, committed.partition.partitionId)).journal).toEqual(
      committed.journal,
    )
    expect((await probe(page)).writes).toBe(1)
    await evidence(page, info, 'new-principal-private-capture')
  } finally {
    await releaseJournalCompletion(page)
    await restoreProbe(page)
  }
})

test('capture visit genuine capability invalidation masks private drafts without a voluntary veto', async ({
  page,
  request,
}, info) => {
  const seeded = await seedWorkshop(page, request)
  await fill(customerForm(page), CUSTOMER)
  const before = await kernelSnapshot(page)
  const owner = await apiLogin(request, 'e2e-owner')
  const response = await request.patch(`/api/v1/admin/users/${seeded.userId}`, {
    headers: await writeHeaders(request, owner, seeded.locationId),
    data: {
      expected_version: 1,
      capabilities: FULL_CAPABILITIES.filter((capability) => capability !== 'bicycles.write'),
    },
  })
  expect(response.status(), await response.text()).toBe(200)
  let confirmations = 0
  const dismiss = async (dialog: Dialog) => {
    confirmations++
    await dialog.dismiss()
  }
  page.on('dialog', dismiss)
  try {
    await page.context().setOffline(false)
    await expect(
      page.locator('[data-runtime-state="HELD"], [data-runtime-state="LOCKED"]'),
    ).toBeVisible()
    await masked(page, Object.values(CUSTOMER))
    expect(confirmations).toBe(0)
    expect((await kernelSnapshot(page, before.partition.partitionId)).journal).toEqual(
      before.journal,
    )
    await evidence(page, info, 'revoked-capture-masked')
  } finally {
    page.off('dialog', dismiss)
  }
  // Real capability updates invalidate the bearer, not a fabricated same-session
  // scope switch. An explicit new login may ask to discard the old volatile draft.
  page.on('dialog', (dialog) => void dialog.accept())
  await loginFields(page, seeded.username)
  await page.getByRole('button', { name: 'Iniciar sesión', exact: true }).click()
  await waitForReady(page)
  await fields(customerForm(page), { Nombre: '', Correo: '', Teléfono: '' })
  await expect(customerForm(page)).toHaveAttribute('data-dirty', 'false')
  await evidence(page, info, 'revoked-new-visit-empty')
})

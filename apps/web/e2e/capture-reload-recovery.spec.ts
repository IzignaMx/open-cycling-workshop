import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Locator, type Page, type Route, type TestInfo } from '@playwright/test'
import {
  DATABASE,
  kernelSnapshot,
  ORGANIZATION_ID,
  PASSWORD,
  waitForReady,
} from './helpers/authenticated-workshop.js'
import { addScopedVisualUser, FULL_CAPABILITIES, seedWorkshop } from './helpers/visual-fixture.js'

const STORED = 'Borrador guardado para recuperar al recargar esta sesión.'
const PROTECTED =
  'Hay una captura anterior pendiente de confirmar. No la repitas; verifica el estado del taller antes de continuar.'
const FAILURE =
  'No se envió la captura. No se pudo asegurar su recuperación local; conserva este formulario.'
const UNKNOWN =
  'No se pudo confirmar si el cambio se guardó. No lo envíes otra vez; verifica el estado del taller antes de continuar.'
const UNAVAILABLE =
  'La recuperación de capturas no está disponible en esta sesión. Cierra sesión e inicia una nueva para continuar; esto no confirma los envíos anteriores.'
const HINT = 'ocwp.capture-checkpoint.v1'
const TTL = 86_400_000
const CUSTOMER = {
  Nombre: 'Borrador privado recuperable',
  Correo: 'reload@example.invalid',
  Teléfono: '5550188',
}
const ORDER = {
  'Problema reportado': 'Borrador privado de transmisión',
  'Condición al recibir': 'Condición privada',
  Accesorios: 'Candado privado',
  Marca: 'Marca privada',
  Modelo: 'Modelo privado',
}
type Channel = 'customer' | 'order'
type ChannelRow = {
  state: 'EMPTY' | 'UNSENT' | 'PROTECTED' | 'UNAVAILABLE'
  revision: number
  attemptId: string | null
  contentStartedAt: number | null
  contentExpiresAt: number | null
}
type Checkpoint = {
  checkpointId: string
  generation: string
  bindingKey: string
  writerEpoch: string
  closed: boolean
  customer: ChannelRow
  order: ChannelRow
}
type Content = {
  checkpointId: string
  generation: string
  channel: Channel
  revision: number
  firstPersistedAt: number
  expiresAt: number
  draft: Record<string, unknown>
  retainedSelection?: { customerId: string; priority: string }
}
const form = (page: Page, channel: Channel) =>
  page.locator(
    `form[aria-describedby~="${channel === 'customer' ? 'customer-create' : 'order-intake'}-status"]`,
  )
const commandStatus = (page: Page, channel: Channel) =>
  page.locator(`#${channel === 'customer' ? 'customer-create' : 'order-intake'}-status`)
const submit = (page: Page, channel: Channel) =>
  form(page, channel).getByRole('button', {
    name: channel === 'customer' ? 'Guardar cliente' : 'Guardar orden',
    exact: true,
  })
async function fillFields(target: Locator, values: Record<string, string>) {
  for (const [name, value] of Object.entries(values))
    await target.getByRole('textbox', { name, exact: true }).fill(value)
}
async function expectFields(target: Locator, values: Record<string, string>) {
  for (const [name, value] of Object.entries(values))
    await expect(target.getByRole('textbox', { name, exact: true })).toHaveValue(value)
}
async function evidence(page: Page, info: TestInfo, name: string) {
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([])
  await info.attach(name, {
    body: await page.screenshot({ fullPage: true }),
    contentType: 'image/png',
  })
}
async function recovery(page: Page, checkpointId?: string) {
  return page.evaluate(
    async ({ name, hintKey, checkpointId }) => {
      const id =
        checkpointId ??
        (JSON.parse(sessionStorage.getItem(hintKey) ?? 'null') as { checkpointId: string } | null)
          ?.checkpointId
      if (!id) throw new Error('No expected capture checkpoint')
      const open = indexedDB.open(name)
      open.onupgradeneeded = () => open.transaction!.abort()
      const db = await new Promise<IDBDatabase>((resolve, reject) => {
        open.onsuccess = () => resolve(open.result)
        open.onerror = () => reject(open.error)
      })
      const read = <T>(request: IDBRequest<T>) =>
        new Promise<T>((resolve, reject) => {
          request.onsuccess = () => resolve(request.result)
          request.onerror = () => reject(request.error)
        })
      try {
        const tx = db.transaction(['captureCheckpoints', 'captureDraftContents'], 'readonly')
        const checkpoint = (await read(tx.objectStore('captureCheckpoints').get(id))) as
          Checkpoint | undefined
        const contents = (await read(tx.objectStore('captureDraftContents').getAll())) as Content[]
        return { checkpoint, contents: contents.filter((row) => row.checkpointId === id) }
      } finally {
        db.close()
      }
    },
    { name: DATABASE, hintKey: HINT, checkpointId },
  )
}
async function acknowledged(page: Page, channel: Channel) {
  await expect(form(page, channel).getByText(STORED, { exact: true })).toBeVisible()
  await expect.poll(async () => (await recovery(page)).checkpoint?.[channel].state).toBe('UNSENT')
  const state = await recovery(page)
  const content = state.contents.find((row) => row.channel === channel)!
  expect(content).toBeDefined()
  expect(content.revision).toBe(state.checkpoint![channel].revision)
  expect(content.expiresAt - content.firstPersistedAt).toBe(TTL)
  const control = (await kernelSnapshot(page)).control
  expect(control.captureWriter?.coveredSequence).toBe(control.localSequence)
  expect(state.checkpoint!.writerEpoch).toBe(control.captureWriter?.epoch)
  return content
}
async function prepare(page: Page, channel: Channel, customerId: string) {
  if (channel === 'order') {
    await form(page, channel)
      .getByRole('combobox', { name: 'Cliente', exact: true })
      .selectOption(customerId)
    await form(page, channel)
      .getByRole('combobox', { name: 'Prioridad', exact: true })
      .selectOption('high')
    await form(page, channel).getByLabel('Agregar bicicleta').check()
  }
  await fillFields(form(page, channel), channel === 'customer' ? CUSTOMER : ORDER)
  const content = await acknowledged(page, channel)
  expect(content.draft).toEqual(
    channel === 'customer'
      ? { displayName: CUSTOMER.Nombre, email: CUSTOMER.Correo, phone: CUSTOMER.Teléfono }
      : {
          customerId,
          priority: 'high',
          withBicycle: true,
          reportedProblem: ORDER['Problema reportado'],
          intakeCondition: ORDER['Condición al recibir'],
          accessories: ORDER.Accesorios,
          brand: ORDER.Marca,
          model: ORDER.Modelo,
        },
  )
  const checkpoint = (await recovery(page)).checkpoint!
  for (const privateValue of [...Object.values(CUSTOMER), ...Object.values(ORDER), customerId])
    expect(JSON.stringify(checkpoint)).not.toContain(privateValue)
  return content
}
async function restoredProtection(page: Page, channel: Channel) {
  await expect(form(page, channel).getByText(PROTECTED, { exact: true })).toBeVisible()
  await expect(submit(page, channel)).toBeDisabled()
  // Reload restores a content-free recovery guard, not a volatile dirty draft.
  await expect(form(page, channel)).toHaveAttribute('data-dirty', 'false')
  await expect
    .poll(async () => (await recovery(page)).checkpoint?.[channel].state)
    .toBe('PROTECTED')
  expect((await recovery(page)).contents.some((row) => row.channel === channel)).toBe(false)
  if (channel === 'customer')
    await expectFields(form(page, channel), { Nombre: '', Correo: '', Teléfono: '' })
  else
    await expectFields(form(page, channel), {
      'Problema reportado': '',
      'Condición al recibir': '',
      Accesorios: '',
    })
  const protectedBefore = await recovery(page)
  const journalBefore = (await kernelSnapshot(page)).journal
  // Empty fields must not bypass voluntary-leave protection: the durable owner,
  // independently of DOM dirty state, still requires an informed confirmation.
  const confirmation = page.waitForEvent('dialog').then(async (dialog) => {
    const observed = { type: dialog.type(), message: dialog.message() }
    await dialog.dismiss()
    return observed
  })
  await page.getByRole('button', { name: 'Cerrar esta sesión', exact: true }).click()
  expect(await confirmation).toEqual({
    type: 'confirm',
    message:
      '¿Continuar y descartar los formularios sin enviar o sin confirmar? El trabajo local ya guardado se conserva. Esta acción no confirma ni revierte los envíos pendientes; no los repitas.',
  })
  await expect(page.locator('.workshop-shell')).toBeVisible()
  await expect(form(page, channel).getByText(PROTECTED, { exact: true })).toBeVisible()
  await expect(submit(page, channel)).toBeDisabled()
  expect(await recovery(page)).toEqual(protectedBefore)
  expect((await kernelSnapshot(page)).journal).toEqual(journalBefore)
}
async function attemptAgain(page: Page, channel: Channel, customerId: string) {
  const target = form(page, channel)
  if (channel === 'order')
    await target.getByRole('combobox', { name: 'Cliente', exact: true }).selectOption(customerId)
  const input = target.getByRole('textbox', {
    name: channel === 'customer' ? 'Nombre' : 'Problema reportado',
    exact: true,
  })
  await input.fill('Intento explícito bloqueado')
  await expect(input).toHaveValue('Intento explícito bloqueado')
  await input.press('Enter')
  // Required fields are valid: this exercises the application guard, not just
  // native form validation or the disabled submit button.
  await target.evaluate((element) => (element as HTMLFormElement).requestSubmit())
  await expect(submit(page, channel)).toBeDisabled()
}

type GateTarget =
  | { kind: 'protect'; checkpointId: string; channel: Channel }
  | { kind: 'journal'; channel: Channel; value: string }
type Probe = {
  held: boolean
  terminal: { type: string; trusted: boolean }[]
  journalWrites: number
  release(): void
  restore(): void
}
type ProbeWindow = Window & { captureReloadProbe?: Probe }
// Delay only the registered JS notification AFTER a genuine native complete.
// No native event is synthesized/reordered and no transaction is kept alive.
async function holdCompletion(page: Page, target: GateTarget) {
  await page.evaluate(
    ({ database, target }) => {
      const descriptor = Object.getOwnPropertyDescriptor(IDBTransaction.prototype, 'oncomplete')!
      const add = IDBObjectStore.prototype.add,
        put = IDBObjectStore.prototype.put
      const marked = new WeakSet<IDBTransaction>()
      const restore = () => {
        Object.defineProperty(IDBTransaction.prototype, 'oncomplete', descriptor)
        IDBObjectStore.prototype.add = add
        IDBObjectStore.prototype.put = put
      }
      const probe: Probe = {
        held: false,
        terminal: [],
        journalWrites: 0,
        release: restore,
        restore,
      }
      ;(window as ProbeWindow).captureReloadProbe = probe
      const observe = (store: IDBObjectStore, value: unknown) => {
        if (store.transaction.db.name !== database) return
        if (store.name === 'operationJournal') probe.journalWrites++
        const row = value as {
          checkpointId?: string
          customer?: ChannelRow
          order?: ChannelRow
          entityType?: string
          envelope?: { payload?: Record<string, unknown> }
        }
        const matches =
          target.kind === 'protect'
            ? store.name === 'captureCheckpoints' &&
              row.checkpointId === target.checkpointId &&
              row[target.channel]?.state === 'PROTECTED'
            : store.name === 'operationJournal' &&
              row.entityType === (target.channel === 'customer' ? 'customer' : 'service_order') &&
              row.envelope?.payload?.[
                target.channel === 'customer' ? 'display_name' : 'reported_problem'
              ] === target.value
        if (matches && !marked.has(store.transaction)) {
          marked.add(store.transaction)
          for (const type of ['complete', 'abort'])
            store.transaction.addEventListener(
              type,
              (event) => probe.terminal.push({ type: event.type, trusted: event.isTrusted }),
              { once: true },
            )
        }
      }
      IDBObjectStore.prototype.add = function (...args: Parameters<IDBObjectStore['add']>) {
        const request = add.apply(this, args)
        observe(this, args[0])
        return request
      }
      IDBObjectStore.prototype.put = function (...args: Parameters<IDBObjectStore['put']>) {
        const request = put.apply(this, args)
        observe(this, args[0])
        return request
      }
      Object.defineProperty(IDBTransaction.prototype, 'oncomplete', {
        configurable: true,
        get: descriptor.get!,
        set(callback: (this: IDBTransaction, event: Event) => void) {
          descriptor.set!.call(this, function (this: IDBTransaction, event: Event) {
            if (marked.has(this)) {
              restore()
              probe.held = true
              probe.release = () => {
                probe.release = () => {}
                callback.call(this, event)
              }
            } else callback.call(this, event)
          })
        },
      })
    },
    { database: DATABASE, target },
  )
}
async function held(page: Page) {
  await page.waitForFunction(() => (window as ProbeWindow).captureReloadProbe?.held)
  const result = await page.evaluate(() => {
    const probe = (window as ProbeWindow).captureReloadProbe!
    return { terminal: probe.terminal, journalWrites: probe.journalWrites }
  })
  expect(result.terminal).toEqual([{ type: 'complete', trusted: true }])
  return result
}
async function release(page: Page) {
  await page.evaluate(() => {
    const probe = (window as ProbeWindow).captureReloadProbe
    probe?.release()
    probe?.restore()
  })
}
async function genuineReverify(page: Page) {
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
    await expect(page.locator('.workshop-shell')).toHaveCount(0)
    release()
    await waitForReady(page)
  } finally {
    release()
    await page.unroute('**/api/v1/auth/context?*', handler)
  }
}
async function beginProtected(page: Page, channel: Channel) {
  await holdCompletion(page, {
    kind: 'journal',
    channel,
    value: channel === 'customer' ? CUSTOMER.Nombre : ORDER['Problema reportado'],
  })
  await submit(page, channel).click()
  await held(page)
  expect((await recovery(page)).checkpoint![channel].state).toBe('PROTECTED')
  expect((await recovery(page)).contents.some((row) => row.channel === channel)).toBe(false)
}

for (const mode of ['online', 'offline'] as const)
  test(`acknowledged unsent capture drafts restore on ${mode} reload without command replay`, async ({
    page,
    request,
  }, info) => {
    const seeded = await seedWorkshop(page, request)
    if (mode === 'online') {
      await page.context().setOffline(false)
      await waitForReady(page)
    }
    // Clean retained selections are part of the checkpoint projection even
    // though they are not an unsent business draft.
    await form(page, 'order')
      .getByRole('combobox', { name: 'Cliente', exact: true })
      .selectOption(seeded.customerId)
    await form(page, 'order')
      .getByRole('combobox', { name: 'Prioridad', exact: true })
      .selectOption('high')
    await form(page, 'order')
      .getByRole('textbox', { name: 'Problema reportado', exact: true })
      .fill('Orden para defaults recuperables')
    await submit(page, 'order').click()
    await expect(commandStatus(page, 'order')).toHaveText('Orden guardada localmente')
    await expect(form(page, 'order')).toHaveAttribute('data-dirty', 'false')
    const cleanOrder = await acknowledged(page, 'order')
    expect(cleanOrder.retainedSelection).toEqual({
      customerId: seeded.customerId,
      priority: 'high',
    })
    const before = await kernelSnapshot(page)
    await page.reload()
    await waitForReady(page)
    await expect(
      form(page, 'order').getByRole('combobox', { name: 'Cliente', exact: true }),
    ).toHaveValue(seeded.customerId)
    await expect(
      form(page, 'order').getByRole('combobox', { name: 'Prioridad', exact: true }),
    ).toHaveValue('high')
    await expect(form(page, 'order')).toHaveAttribute('data-dirty', 'false')
    expect((await kernelSnapshot(page)).journal).toEqual(before.journal)
    await prepare(page, 'customer', seeded.customerId)
    await prepare(page, 'order', seeded.customerId)
    await form(page, 'order').getByLabel('Agregar bicicleta').uncheck()
    const originalOrder = await acknowledged(page, 'order')
    expect(originalOrder.draft.withBicycle).toBe(false)
    const original = await recovery(page)
    await page.reload()
    await waitForReady(page)
    await expectFields(form(page, 'customer'), CUSTOMER)
    await expect(form(page, 'order').getByLabel('Agregar bicicleta')).not.toBeChecked()
    await expect(
      form(page, 'order').getByRole('combobox', { name: 'Cliente', exact: true }),
    ).toHaveValue(seeded.customerId)
    await expect(
      form(page, 'order').getByRole('combobox', { name: 'Prioridad', exact: true }),
    ).toHaveValue('high')
    const restored = await recovery(page)
    expect(restored.checkpoint!.checkpointId).toBe(original.checkpoint!.checkpointId)
    expect(restored.contents.find((row) => row.channel === 'order')).toEqual(originalOrder)
    await form(page, 'order').getByLabel('Agregar bicicleta').check()
    await expectFields(form(page, 'order'), ORDER)
    await acknowledged(page, 'order')
    expect((await recovery(page)).contents.find((row) => row.channel === 'order')!.expiresAt).toBe(
      originalOrder.expiresAt,
    )
    expect((await kernelSnapshot(page)).journal).toEqual(before.journal)
    await expect(form(page, 'customer')).toHaveAttribute('data-dirty', 'true')
    await evidence(page, info, `reload-${mode}-restored`)
  })

test('pre-submit native opener clone observes shared protection after current admission', async ({
  page,
  request,
}, info) => {
  const seeded = await seedWorkshop(page, request)
  await prepare(page, 'customer', seeded.customerId)
  const popupEvent = page.waitForEvent('popup')
  await page.evaluate(() => {
    window.open('about:blank', '_blank')
  })
  const clone = await popupEvent
  const originalHint = await page.evaluate((key) => sessionStorage.getItem(key), HINT)
  expect(await clone.evaluate((key) => sessionStorage.getItem(key), HINT)).toBe(originalHint)
  // Native opener copying is not forged authority. The second startup must obtain
  // its own kernel admission; takeover checks remain enabled throughout.
  try {
    await beginProtected(page, 'customer')
    const committed = await kernelSnapshot(page)
    await clone.goto('/')
    await waitForReady(clone)
    await restoredProtection(clone, 'customer')
    await attemptAgain(clone, 'customer', seeded.customerId)
    expect((await kernelSnapshot(clone)).journal).toEqual(committed.journal)
    await release(page)
    await clone.reload()
    await waitForReady(clone)
    await restoredProtection(clone, 'customer')
    expect((await kernelSnapshot(clone)).journal).toEqual(committed.journal)
    await evidence(clone, info, 'native-clone-protected')
  } finally {
    await release(page)
    await clone.close()
  }
})

test('reload after native protection commit before command dispatch never replays the capture', async ({
  page,
  request,
}, info) => {
  const seeded = await seedWorkshop(page, request)
  await prepare(page, 'order', seeded.customerId)
  const before = await kernelSnapshot(page)
  const original = await recovery(page)
  await holdCompletion(page, {
    kind: 'protect',
    checkpointId: original.checkpoint!.checkpointId,
    channel: 'order',
  })
  try {
    await submit(page, 'order').click()
    expect((await held(page)).journalWrites).toBe(0)
    expect((await recovery(page)).checkpoint!.order.state).toBe('PROTECTED')
    expect((await kernelSnapshot(page)).journal).toEqual(before.journal)
    // Reload destroys the old JS continuation; it is not a power-loss test.
    await page.reload()
    await waitForReady(page)
    await restoredProtection(page, 'order')
    await attemptAgain(page, 'order', seeded.customerId)
    expect((await kernelSnapshot(page)).journal).toEqual(before.journal)
    await evidence(page, info, 'predispatch-reload-protected')
  } finally {
    await release(page)
  }
})

test('reload after genuine business commit preserves protection, not newer protected-interval input', async ({
  page,
  request,
}, info) => {
  const seeded = await seedWorkshop(page, request)
  await prepare(page, 'customer', seeded.customerId)
  const before = await kernelSnapshot(page)
  try {
    await beginProtected(page, 'customer')
    const committed = await kernelSnapshot(page)
    expect(committed.journal).toHaveLength(before.journal.length + 1)
    expect(committed.journal.at(-1)!.envelope.payload).toEqual({
      display_name: CUSTOMER.Nombre,
      email: CUSTOMER.Correo,
      phone: CUSTOMER.Teléfono,
    })
    await form(page, 'customer')
      .getByRole('textbox', { name: 'Nombre', exact: true })
      .fill('Edición privada durante protección')
    expect((await recovery(page)).contents.some((row) => row.channel === 'customer')).toBe(false)
    await page.reload()
    await waitForReady(page)
    await restoredProtection(page, 'customer')
    // Protected-interval edits are volatile by policy, never silently checkpointed
    // as sendable input. The original committed journal remains immutable.
    await attemptAgain(page, 'customer', seeded.customerId)
    expect((await kernelSnapshot(page)).journal).toEqual(committed.journal)
    await evidence(page, info, 'postcommit-reload-protected')
  } finally {
    await release(page)
  }
})

test('genuine UNKNOWN survives reload with no second journal admission', async ({
  page,
  request,
}, info) => {
  const seeded = await seedWorkshop(page, request)
  await prepare(page, 'customer', seeded.customerId)
  try {
    await beginProtected(page, 'customer')
    const committed = await kernelSnapshot(page)
    // Actual re-verification invalidates the held command's source before its
    // postwrite fence. Observed native commit does not reinterpret UNKNOWN.
    await genuineReverify(page)
    await release(page)
    await expect(commandStatus(page, 'customer')).toHaveText(UNKNOWN)
    await page.reload()
    await waitForReady(page)
    await restoredProtection(page, 'customer')
    await attemptAgain(page, 'customer', seeded.customerId)
    expect((await kernelSnapshot(page)).journal).toEqual(committed.journal)
    await evidence(page, info, 'unknown-reload-protected')
  } finally {
    await release(page)
  }
})

test('24-hour app-open cleanup deletes expired private fields without clearing protection', async ({
  page,
  request,
}, info) => {
  await page.clock.install()
  const seeded = await seedWorkshop(page, request)
  await prepare(page, 'customer', seeded.customerId)
  const order = await prepare(page, 'order', seeded.customerId)
  try {
    await beginProtected(page, 'customer')
    const original = await recovery(page)
    const committed = await kernelSnapshot(page)
    const id = original.checkpoint!.checkpointId
    await page.clock.setFixedTime(new Date(order.expiresAt + 1))
    await page.reload()
    // Real lease/token lifetime is 8h. Do NOT fake READY authority at +24h.
    await expect(page.locator('.workshop-shell')).toHaveCount(0)
    await expect.poll(async () => (await recovery(page, id)).contents.length).toBe(0)
    const cleaned = await recovery(page, id)
    expect(cleaned.checkpoint!.customer.state).toBe('PROTECTED')
    expect(cleaned.checkpoint!.order.state).toBe('EMPTY')
    expect(cleaned.checkpoint!.customer.attemptId).toBe(original.checkpoint!.customer.attemptId)
    expect((await kernelSnapshot(page, committed.partition.partitionId)).journal).toEqual(
      committed.journal,
    )
    for (const value of [...Object.values(CUSTOMER), ...Object.values(ORDER)])
      await expect(page.locator('body')).not.toContainText(value)
    await evidence(page, info, 'expired-content-masked-protection-retained')
  } finally {
    await release(page)
  }
})

test('logout purges private content while closed protection and saved journal survive a new principal', async ({
  page,
  request,
}, info) => {
  const seeded = await seedWorkshop(page, request)
  const other = await addScopedVisualUser(
    request,
    seeded.locationId,
    FULL_CAPABILITIES.filter((capability) => capability !== 'sync.pull'),
  )
  await prepare(page, 'customer', seeded.customerId)
  await prepare(page, 'order', seeded.customerId)
  try {
    await beginProtected(page, 'customer')
    const original = await recovery(page)
    const committed = await kernelSnapshot(page)
    const id = original.checkpoint!.checkpointId
    page.once('dialog', (dialog) => void dialog.accept())
    await page.getByRole('button', { name: 'Cerrar esta sesión', exact: true }).click()
    await expect(page.locator('.workshop-shell')).toHaveCount(0)
    await expect
      .poll(async () => {
        const state = await recovery(page, id)
        return state.checkpoint?.closed && state.contents.length === 0
      })
      .toBe(true)
    expect((await recovery(page, id)).checkpoint!.customer.state).toBe('PROTECTED')
    await release(page)
    expect((await recovery(page, id)).contents).toEqual([])
    await page.context().setOffline(false)
    await page.getByLabel('Organización', { exact: true }).fill(ORGANIZATION_ID)
    await page.getByLabel('Usuario', { exact: true }).fill(other.username)
    await page.getByLabel('Contraseña', { exact: true }).fill(PASSWORD)
    await page.getByRole('button', { name: 'Iniciar sesión', exact: true }).click()
    await waitForReady(page)
    await expectFields(form(page, 'customer'), { Nombre: '', Correo: '', Teléfono: '' })
    await expectFields(form(page, 'order'), {
      'Problema reportado': '',
      'Condición al recibir': '',
      Accesorios: '',
    })
    const next = await recovery(page)
    expect(next.checkpoint!.checkpointId).not.toBe(id)
    expect(next.checkpoint!.bindingKey).not.toBe(original.checkpoint!.bindingKey)
    expect((await recovery(page, id)).contents).toEqual([])
    expect((await recovery(page, id)).checkpoint!.customer.state).toBe('PROTECTED')
    expect((await kernelSnapshot(page, committed.partition.partitionId)).journal).toEqual(
      committed.journal,
    )
    await evidence(page, info, 'logout-new-principal-no-old-draft')
  } finally {
    await release(page)
  }
})

test('native capture-content quota failure cannot advertise persistence or admit a business create', async ({
  page,
  request,
}, info) => {
  const seeded = await seedWorkshop(page, request)
  await prepare(page, 'customer', seeded.customerId)
  const original = await recovery(page)
  const before = await kernelSnapshot(page)
  await page.evaluate(
    ({ database, checkpointId }) => {
      const original = IDBObjectStore.prototype.put
      Object.assign(window, {
        captureQuota: {
          calls: 0,
          restore: () => {
            IDBObjectStore.prototype.put = original
          },
        },
      })
      IDBObjectStore.prototype.put = function (...args: Parameters<IDBObjectStore['put']>) {
        const row = args[0] as { checkpointId?: string; channel?: string }
        if (
          this.transaction.db.name === database &&
          this.name === 'captureDraftContents' &&
          row?.checkpointId === checkpointId &&
          row.channel === 'customer'
        ) {
          ;(window as unknown as { captureQuota: { calls: number } }).captureQuota.calls++
          // Bounded native API failure only: no synthetic abort/complete event and
          // no manufactured not_saved result or promise-settlement ordering.
          throw new DOMException('synthetic-capture-storage-canary', 'QuotaExceededError')
        }
        return original.apply(this, args)
      }
    },
    { database: DATABASE, checkpointId: original.checkpoint!.checkpointId },
  )
  try {
    await form(page, 'customer')
      .getByRole('textbox', { name: 'Nombre', exact: true })
      .fill('Borrador posterior no persistido')
    await expect(form(page, 'customer').getByText(FAILURE, { exact: true })).toBeVisible()
    await expect(form(page, 'customer').getByText(STORED, { exact: true })).toHaveCount(0)
    await form(page, 'customer').evaluate((element) => (element as HTMLFormElement).requestSubmit())
    await expectFields(form(page, 'customer'), {
      ...CUSTOMER,
      Nombre: 'Borrador posterior no persistido',
    })
    expect(
      await page.evaluate(
        () => (window as unknown as { captureQuota: { calls: number } }).captureQuota.calls,
      ),
    ).toBeGreaterThan(0)
    expect((await kernelSnapshot(page)).journal).toEqual(before.journal)
    expect((await recovery(page)).contents).toEqual(original.contents)
    await expect(page.locator('body')).not.toContainText('synthetic-capture-storage-canary')
    await evidence(page, info, 'quota-draft-not-advertised-saved')
  } finally {
    await page.evaluate(() =>
      (window as unknown as { captureQuota: { restore(): void } }).captureQuota.restore(),
    )
  }
})

test('native old-writer-compatible commit invalidates recovery even after a healthy new command', async ({
  page,
  request,
}, info) => {
  const seeded = await seedWorkshop(page, request)
  const customer = await prepare(page, 'customer', seeded.customerId)
  const original = await recovery(page)
  const before = await kernelSnapshot(page)
  const writer = before.control.captureWriter!
  expect(writer.coveredSequence).toBe(before.control.localSequence)
  expect(original.checkpoint!.writerEpoch).toBe(writer.epoch)
  const problem = 'Orden real con omisión de cobertura del escritor antiguo'
  await form(page, 'order')
    .getByRole('combobox', { name: 'Cliente', exact: true })
    .selectOption(seeded.customerId)
  await form(page, 'order')
    .getByRole('textbox', { name: 'Problema reportado', exact: true })
    .fill(problem)
  await acknowledged(page, 'order')
  await page.evaluate(
    ({ database, problem, writer, sequence }) => {
      const add = IDBObjectStore.prototype.add
      const put = IDBObjectStore.prototype.put
      const target = new WeakSet<IDBTransaction>()
      const probe = {
        omissions: 0,
        terminal: [] as { type: string; trusted: boolean }[],
        restore: () => {
          IDBObjectStore.prototype.add = add
          IDBObjectStore.prototype.put = put
        },
      }
      Object.assign(window, { legacyCaptureWriterProbe: probe })
      IDBObjectStore.prototype.add = function (...args: Parameters<IDBObjectStore['add']>) {
        const request = add.apply(this, args)
        const operation = args[0] as {
          entityType?: string
          envelope?: { payload?: { reported_problem?: string } }
        }
        if (
          this.transaction.db.name === database &&
          this.name === 'operationJournal' &&
          operation?.entityType === 'service_order' &&
          operation.envelope?.payload?.reported_problem === problem
        ) {
          target.add(this.transaction)
          for (const type of ['complete', 'abort'])
            this.transaction.addEventListener(
              type,
              (event) => probe.terminal.push({ type: event.type, trusted: event.isTrusted }),
              { once: true },
            )
        }
        return request
      }
      IDBObjectStore.prototype.put = function (...args: Parameters<IDBObjectStore['put']>) {
        const control = args[0] as { localSequence?: number; captureWriter?: unknown }
        if (
          this.transaction.db.name === database &&
          this.name === 'deviceControl' &&
          target.has(this.transaction) &&
          control.localSequence === sequence + 1
        ) {
          probe.omissions++
          // Model only the old writer's omission in a genuine admitted business
          // transaction. All authority/control fields, journal/delivery bytes and
          // native terminal ordering are untouched; no result is manufactured.
          return put.call(this, { ...control, captureWriter: writer }, args[1])
        }
        return put.apply(this, args)
      }
    },
    { database: DATABASE, problem, writer, sequence: before.control.localSequence },
  )
  const restore = () =>
    page.evaluate(() =>
      (
        window as unknown as { legacyCaptureWriterProbe?: { restore(): void } }
      ).legacyCaptureWriterProbe?.restore(),
    )
  try {
    await submit(page, 'order').click()
    await expect
      .poll(() =>
        page.evaluate(() => {
          const probe = (
            window as unknown as {
              legacyCaptureWriterProbe: {
                omissions: number
                terminal: { type: string; trusted: boolean }[]
              }
            }
          ).legacyCaptureWriterProbe
          return { omissions: probe.omissions, terminal: probe.terminal }
        }),
      )
      .toEqual({ omissions: 1, terminal: [{ type: 'complete', trusted: true }] })
    const legacy = await kernelSnapshot(page)
    expect(legacy.journal).toHaveLength(before.journal.length + 1)
    expect(legacy.journal.slice(0, before.journal.length)).toEqual(before.journal)
    expect(legacy.journal.at(-1)!.envelope.payload).toMatchObject({
      customer_id: seeded.customerId,
      reported_problem: problem,
    })
    expect(legacy.control.captureWriter).toEqual(writer)
    expect(legacy.control.localSequence).toBe(before.control.localSequence + 1)
    expect((await recovery(page)).contents.find((row) => row.channel === 'customer')).toEqual(
      customer,
    )
    await restore()

    // A real independent transition is allowed by the existing authority path.
    // Its healthy writer rotation must not make the old checkpoint sendable.
    const card = page.getByRole('listitem', {
      name: 'Orden Caso visual 4: revisión de frenos y transmisión',
      exact: true,
    })
    await card.getByRole('button', { name: 'Iniciar diagnóstico', exact: true }).click()
    await expect
      .poll(async () => (await kernelSnapshot(page)).journal.length)
      .toBe(legacy.journal.length + 1)
    const rotated = await kernelSnapshot(page)
    expect(rotated.journal.slice(0, legacy.journal.length)).toEqual(legacy.journal)
    expect(rotated.journal.at(-1)!.envelope.payload).toMatchObject({
      transition: { action: 'start_diagnosis' },
    })
    expect(rotated.control.captureWriter!.coveredSequence).toBe(rotated.control.localSequence)
    expect(rotated.control.captureWriter!.epoch).not.toBe(writer.epoch)
    expect((await recovery(page)).checkpoint!.writerEpoch).toBe(writer.epoch)
    await page.reload()
    await waitForReady(page)
    await expectFields(form(page, 'customer'), { Nombre: '', Correo: '', Teléfono: '' })
    await expect(form(page, 'customer').getByText(UNAVAILABLE, { exact: true })).toBeVisible()
    await expect(submit(page, 'customer')).toBeDisabled()
    await attemptAgain(page, 'customer', seeded.customerId)
    expect((await kernelSnapshot(page)).journal).toEqual(rotated.journal)
    expect((await recovery(page)).checkpoint!.writerEpoch).toBe(writer.epoch)
    // This is native old-writer-compatible fault coverage, not execution of a v7
    // bundle. The independently maintained actual-v7 probe proves that boundary.
    await evidence(page, info, 'legacy-writer-gap-not-laundered')
  } finally {
    await restore()
  }
})

for (const invalid of [
  { field: 'Nombre', value: 'a'.repeat(201), message: 'El nombre no puede superar 200 caracteres' },
  {
    field: 'Correo',
    value: 'a'.repeat(309) + '@example.com',
    message: 'El correo no puede superar 320 caracteres',
  },
  {
    field: 'Teléfono',
    value: '1'.repeat(65),
    message: 'El teléfono no puede superar 64 caracteres',
  },
]) {
  test(`customer ${invalid.field} overflow retains recoverable draft without journal admission`, async ({
    page,
    request,
  }, info) => {
    await seedWorkshop(page, request)
    const fields = { ...CUSTOMER, [invalid.field]: invalid.value }
    await fillFields(form(page, 'customer'), fields)
    await acknowledged(page, 'customer')
    const before = await kernelSnapshot(page)
    await submit(page, 'customer').click()
    await expect(commandStatus(page, 'customer')).toHaveText(invalid.message)
    await expectFields(form(page, 'customer'), fields)
    await expect(form(page, 'customer')).toHaveAttribute('data-dirty', 'true')
    await expect(submit(page, 'customer')).toBeEnabled()
    // Actual native protection must settle back to recoverable UNSENT, never
    // remain PROTECTED or manufacture a command receipt for rejected input.
    await acknowledged(page, 'customer')
    expect((await kernelSnapshot(page)).journal).toEqual(before.journal)
    await page.reload()
    await waitForReady(page)
    await expectFields(form(page, 'customer'), fields)
    await expect(submit(page, 'customer')).toBeEnabled()
    expect((await kernelSnapshot(page)).journal).toEqual(before.journal)
    await fillFields(form(page, 'customer'), CUSTOMER)
    await submit(page, 'customer').click()
    await expect(commandStatus(page, 'customer')).toHaveText('Cliente guardado localmente')
    await expect(form(page, 'customer')).toHaveAttribute('data-dirty', 'false')
    await expectFields(form(page, 'customer'), { Nombre: '', Correo: '', Teléfono: '' })
    const after = await kernelSnapshot(page)
    expect(after.journal).toHaveLength(before.journal.length + 1)
    expect(after.journal.slice(0, before.journal.length)).toEqual(before.journal)
    expect(after.journal.at(-1)!.envelope.payload).toEqual({
      display_name: CUSTOMER.Nombre,
      email: CUSTOMER.Correo,
      phone: CUSTOMER.Teléfono,
    })
    if (invalid.field === 'Nombre') await evidence(page, info, 'customer-length-corrected')
  })
}

test('single-label customer email passes native validity but is rejected without losing recoverable input', async ({
  page,
  request,
}) => {
  await seedWorkshop(page, request)
  const fields = { ...CUSTOMER, Correo: 'person@localhost' }
  await fillFields(form(page, 'customer'), fields)
  const email = form(page, 'customer').getByRole('textbox', { name: 'Correo', exact: true })
  // Prove the real application handler, not a browser email-validation block,
  // is responsible for refusing this server-inadmissible address.
  expect(await email.evaluate((element) => (element as HTMLInputElement).checkValidity())).toBe(
    true,
  )
  expect(
    await form(page, 'customer').evaluate((element) =>
      (element as HTMLFormElement).checkValidity(),
    ),
  ).toBe(true)
  await acknowledged(page, 'customer')
  const before = await kernelSnapshot(page)
  await submit(page, 'customer').click()
  await expect(commandStatus(page, 'customer')).toHaveText('El correo no es válido')
  await expectFields(form(page, 'customer'), fields)
  await expect(form(page, 'customer')).toHaveAttribute('data-dirty', 'true')
  await expect(submit(page, 'customer')).toBeEnabled()
  await acknowledged(page, 'customer')
  expect((await kernelSnapshot(page)).journal).toEqual(before.journal)
  await page.reload()
  await waitForReady(page)
  await expectFields(form(page, 'customer'), fields)
  await expect(submit(page, 'customer')).toBeEnabled()
  expect((await kernelSnapshot(page)).journal).toEqual(before.journal)
  await email.fill(CUSTOMER.Correo)
  await submit(page, 'customer').click()
  await expect(commandStatus(page, 'customer')).toHaveText('Cliente guardado localmente')
  await expectFields(form(page, 'customer'), { Nombre: '', Correo: '', Teléfono: '' })
  const after = await kernelSnapshot(page)
  expect(after.journal).toHaveLength(before.journal.length + 1)
  expect(after.journal.slice(0, before.journal.length)).toEqual(before.journal)
  expect(after.journal.at(-1)!.envelope.payload).toEqual({
    display_name: CUSTOMER.Nombre,
    email: CUSTOMER.Correo,
    phone: CUSTOMER.Teléfono,
  })
})

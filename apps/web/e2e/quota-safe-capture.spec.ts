import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Page } from '@playwright/test'
import { DATABASE, kernelSnapshot } from './helpers/authenticated-workshop.js'
import { seedWorkshop } from './helpers/visual-fixture.js'

const UNKNOWN =
  'No se pudo confirmar si el cambio se guardó. No lo envíes otra vez; verifica el estado del taller antes de continuar.'
const CANARY = 'quota-capture-private-error-canary'

type FaultProbe = {
  calls: number
  injected: number
  terminalEvents: { type: string; trusted: boolean }[]
  restore: () => void
}
type ProbeWindow = Window & { quotaCaptureProbe?: FaultProbe }

async function snapshot(page: Page) {
  const value = await kernelSnapshot(page)
  // The fixture has one disposable browser database. Read whole durable stores
  // as well, so an orphan delivery/event cannot hide behind journal filtering.
  const durable = await page.evaluate(async (name) => {
    const open = indexedDB.open(name)
    const db = await new Promise<IDBDatabase>((resolve, reject) => {
      open.onsuccess = () => resolve(open.result)
      open.onerror = () => reject(open.error)
    })
    try {
      const stores = ['operationJournal', 'operationDelivery', 'operationEvents']
      const tx = db.transaction(stores, 'readonly')
      return await Promise.all(
        stores.map(
          (store) =>
            new Promise<unknown[]>((resolve, reject) => {
              const read = tx.objectStore(store).getAll()
              read.onsuccess = () => resolve(read.result)
              read.onerror = () => reject(read.error)
            }),
        ),
      )
    } finally {
      db.close()
    }
  }, DATABASE)
  return {
    records: value.records,
    journal: value.journal,
    durable,
    localSequence: value.control.localSequence,
  }
}

// Inject only a bounded API failure. In particular, never call abort(), synthesize
// terminal events, delay Dexie's rejection, or reorder native event handlers.
// Locked Dexie can reject before native abort: that is UNKNOWN, not retry proof.
async function installFault(page: Page, kind: 'quota' | 'preparation', journalOrdinal: number) {
  await page.evaluate(
    ({ kind, journalOrdinal, canary }) => {
      const probe: FaultProbe = { calls: 0, injected: 0, terminalEvents: [], restore: () => {} }
      ;(window as ProbeWindow).quotaCaptureProbe = probe
      if (kind === 'preparation') {
        const original = crypto.getRandomValues
        crypto.getRandomValues = function <T extends ArrayBufferView | null>(array: T): T {
          probe.calls += 1
          if (probe.injected === 0) {
            probe.injected += 1
            throw new Error(canary)
          }
          return original.call(crypto, array) as T
        }
        probe.restore = () => {
          crypto.getRandomValues = original
        }
        return
      }
      const original = IDBObjectStore.prototype.add
      IDBObjectStore.prototype.add = function (value: unknown, key?: IDBValidKey) {
        if (this.name === 'operationJournal') {
          probe.calls += 1
          if (probe.calls === journalOrdinal) {
            probe.injected += 1
            for (const type of ['abort', 'complete']) {
              this.transaction.addEventListener(
                type,
                (event) =>
                  probe.terminalEvents.push({ type: event.type, trusted: event.isTrusted }),
                { once: true },
              )
            }
            // The real locked Dexie wraps this native DOMException itself.
            throw new DOMException(canary, 'QuotaExceededError')
          }
        }
        return original.call(this, value, key)
      }
      probe.restore = () => {
        IDBObjectStore.prototype.add = original
      }
    },
    { kind, journalOrdinal, canary: CANARY },
  )
}

const cases = [
  { theme: 'banco', label: 'Banco de trabajo', form: 'customer', fault: 'quota' },
  { theme: 'plano', label: 'Plano técnico', form: 'order', fault: 'quota' },
  { theme: 'ritmo', label: 'Ritmo modular', form: 'customer', fault: 'preparation' },
  { theme: 'noche', label: 'Turno nocturno', form: 'order', fault: 'preparation' },
] as const

for (const scenario of cases) {
  test(`${scenario.theme}: ${scenario.form} ${scenario.fault} unknown preserves draft and blocks resubmission`, async ({
    page,
    request,
  }, info) => {
    await page.setViewportSize({ width: 1440, height: 1000 })
    const seeded = await seedWorkshop(page, request)
    await page.getByRole('button', { name: 'Personalización', exact: true }).click()
    const theme = page.getByRole('radio', { name: new RegExp(scenario.label) })
    await theme.focus()
    await theme.press('Space')
    await expect(theme).toBeChecked()
    await expect(page.locator('.workshop-shell')).toHaveAttribute('data-theme', scenario.theme)
    await expect(page.locator('.preference-status')).toContainText('guardada en este dispositivo')
    await theme.press('Escape')
    await expect(page.getByRole('button', { name: 'Personalización', exact: true })).toBeFocused()

    const customer = scenario.form === 'customer'
    const form = page.locator(
      customer
        ? 'form[aria-describedby="customer-create-status"]'
        : 'form[aria-describedby="order-intake-status"]',
    )
    const values = customer
      ? {
          Nombre: 'Cliente borrador cuota',
          Correo: 'synthetic@example.invalid',
          Teléfono: '5550100',
        }
      : {
          'Problema reportado': 'Freno pendiente de revisión',
          'Condición al recibir': 'Sin daños',
          Accesorios: 'Luz sintética',
          Marca: 'Bicicleta sintética',
          Modelo: 'Modelo de prueba',
        }
    if (!customer) {
      await form.getByLabel('Cliente', { exact: true }).selectOption(seeded.customerId)
      await form.getByLabel('Prioridad', { exact: true }).selectOption('high')
      await form.getByLabel('Agregar bicicleta').check()
    }
    for (const [label, value] of Object.entries(values)) {
      await form.getByLabel(label, { exact: true }).fill(value)
    }
    const before = await snapshot(page)
    expect(before.journal).toHaveLength(1) // unrelated pending work must survive
    await installFault(page, scenario.fault, customer ? 1 : 2)
    const submit = form.getByRole('button', {
      name: customer ? 'Guardar cliente' : 'Guardar orden',
    })
    await submit.focus()
    await submit.press('Enter')
    const status = form.getByRole('status')
    await expect(status).toHaveText(UNKNOWN)
    await expect(status).toHaveAttribute('aria-live', 'polite')
    await expect(submit).toBeDisabled()
    await expect(form).toHaveAttribute('data-dirty', 'true')
    await expect(page.locator('body')).not.toContainText(CANARY)
    for (const [label, value] of Object.entries(values)) {
      await expect(form.getByLabel(label, { exact: true })).toHaveValue(value)
    }
    if (!customer) {
      await expect(form.getByLabel('Cliente', { exact: true })).toHaveValue(seeded.customerId)
      await expect(form.getByLabel('Prioridad', { exact: true })).toHaveValue('high')
      await expect(form.getByLabel('Agregar bicicleta')).toBeChecked()
    }
    if (scenario.fault === 'quota') {
      // Observe the real eventual abort, without changing its ordering relative
      // to the already-delivered UNKNOWN result. This is rollback evidence only.
      await expect
        .poll(() => page.evaluate(() => (window as ProbeWindow).quotaCaptureProbe!.terminalEvents))
        .toEqual([{ type: 'abort', trusted: true }])
    }
    expect(await snapshot(page)).toEqual(before)
    const observations = await page.evaluate(() => {
      const probe = (window as ProbeWindow).quotaCaptureProbe!
      return { calls: probe.calls, injected: probe.injected, terminalEvents: probe.terminalEvents }
    })
    expect(observations.injected).toBe(1)
    expect(observations.calls).toBe(scenario.fault === 'quota' && !customer ? 2 : 1)

    // The one-shot injection is now exhausted; a second admission would succeed
    // or change the counters. Editing, Enter and direct native form submission
    // must all preserve the UNKNOWN latch rather than retry implicitly.
    const editable = form.getByLabel(customer ? 'Nombre' : 'Condición al recibir', { exact: true })
    await editable.fill('Borrador editado después del fallo')
    await editable.press('Enter')
    await form.evaluate((element) => (element as HTMLFormElement).requestSubmit())
    await expect(status).toHaveText(UNKNOWN)
    expect(await snapshot(page)).toEqual(before)
    expect(await page.evaluate(() => (window as ProbeWindow).quotaCaptureProbe!.calls)).toBe(
      observations.calls,
    )

    for (const label of Object.keys(values)) await form.getByLabel(label, { exact: true }).fill('')
    if (!customer) {
      await form.getByLabel('Agregar bicicleta').uncheck()
      await form.getByLabel('Cliente', { exact: true }).selectOption('')
      await form.getByLabel('Prioridad', { exact: true }).selectOption('normal')
    }
    await expect(form).toHaveAttribute('data-dirty', 'true')
    await expect(submit).toBeDisabled()
    const dialog = page.waitForEvent('dialog').then(async (confirmation) => {
      const message = confirmation.message()
      await confirmation.dismiss()
      return message
    })
    await page.getByRole('button', { name: 'Cerrar esta sesión', exact: true }).click()
    expect(await dialog).toContain('formularios sin enviar')
    await expect(page.locator('.workshop-shell')).toBeVisible()
    await expect(status).toHaveText(UNKNOWN)
    expect(await snapshot(page)).toEqual(before)
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([])
    await info.attach('bounded-fault-observations', {
      body: JSON.stringify({ scenario, ...observations, provenRetrySafe: false }),
      contentType: 'application/json',
    })
    await info.attach(`quota-feedback-${scenario.theme}`, {
      body: await page.screenshot({ fullPage: true }),
      contentType: 'image/png',
    })
    await page.evaluate(() => (window as ProbeWindow).quotaCaptureProbe!.restore())
  })
}

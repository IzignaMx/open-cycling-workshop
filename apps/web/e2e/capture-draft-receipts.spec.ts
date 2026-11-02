import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Locator, type Page } from '@playwright/test'
import {
  DATABASE,
  holdJournalCompletion,
  kernelSnapshot,
  releaseJournalCompletion,
  waitForJournalBarrier,
  type JournalOperation,
} from './helpers/authenticated-workshop.js'
import { seedWorkshop } from './helpers/visual-fixture.js'

const PREVIOUS_SAVED =
  'El envío anterior se guardó localmente. El formulario actual sigue sin guardar.'

type CompletionProbe = {
  events: { type: string; trusted: boolean }[]
  restore(): void
}
type ProbeWindow = Window & { captureCompletionProbe?: CompletionProbe }

// Observe only. The existing gate delays delivery of Dexie's registered callback
// AFTER genuine native completion; neither adapter manufactures a saved result,
// aborts a transaction, nor changes the order of native terminal events. Keep the
// admitted offline visit stable: the gate is before the kernel's postwrite fence.
async function observeCompletion(page: Page, entityType: string, key: string, value: string) {
  await page.evaluate(
    ({ database, entityType, key, value }) => {
      const original = IDBObjectStore.prototype.add
      const probe: CompletionProbe = {
        events: [],
        restore: () => {
          IDBObjectStore.prototype.add = original
        },
      }
      ;(window as ProbeWindow).captureCompletionProbe = probe
      IDBObjectStore.prototype.add = function (...args: Parameters<IDBObjectStore['add']>) {
        const request = original.apply(this, args)
        const row = args[0] as {
          entityType?: string
          envelope?: { payload?: Record<string, unknown> }
        }
        if (
          this.transaction.db.name === database &&
          this.name === 'operationJournal' &&
          row?.entityType === entityType &&
          row.envelope?.payload?.[key] === value
        ) {
          for (const type of ['complete', 'abort'])
            this.transaction.addEventListener(
              type,
              (event) => probe.events.push({ type: event.type, trusted: event.isTrusted }),
              { once: true },
            )
        }
        return request
      }
    },
    { database: DATABASE, entityType, key, value },
  )
}

async function fillFields(form: Locator, values: Record<string, string>) {
  for (const [label, value] of Object.entries(values))
    await form.getByRole('textbox', { name: label, exact: true }).fill(value)
}
async function expectFields(form: Locator, values: Record<string, string>) {
  for (const [label, value] of Object.entries(values))
    await expect(form.getByRole('textbox', { name: label, exact: true })).toHaveValue(value)
}
function expectPayloads(
  operations: JournalOperation[],
  customer: boolean,
  values: Record<string, string>,
  customerId: string,
  priority: string,
) {
  expect(operations).toHaveLength(customer ? 1 : 2)
  expect(operations.every((operation) => operation.envelope.operation === 'create')).toBe(true)
  if (customer) {
    expect(operations[0]!.entityType).toBe('customer')
    expect(operations[0]!.envelope.payload).toEqual({
      display_name: values.Nombre,
      email: values.Correo,
      phone: values.Teléfono,
    })
  } else {
    const bicycle = operations.find((operation) => operation.entityType === 'bicycle')!
    const order = operations.find((operation) => operation.entityType === 'service_order')!
    expect(bicycle).toBeDefined()
    expect(order).toBeDefined()
    expect(bicycle.envelope.payload).toEqual({
      customer_id: customerId,
      brand: values.Marca,
      model: values.Modelo,
      bicycle_type: null,
      wheel_size: null,
      notes: null,
    })
    expect(order.envelope.payload).toEqual({
      customer_id: customerId,
      bicycle_id: bicycle.entityId,
      reported_problem: values['Problema reportado'],
      intake_condition: values['Condición al recibir'],
      accessories: values.Accesorios,
      priority,
    })
  }
}

const cases = [
  { theme: 'banco', label: 'Banco de trabajo', form: 'customer' },
  { theme: 'plano', label: 'Plano técnico', form: 'order' },
  { theme: 'ritmo', label: 'Ritmo modular', form: 'customer' },
  { theme: 'noche', label: 'Turno nocturno', form: 'order' },
] as const

for (const scenario of cases)
  test(`${scenario.theme}: ${scenario.form} late saved receipt preserves newer draft until explicit save`, async ({
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
    await theme.press('Escape')
    await expect(page.getByRole('button', { name: 'Personalización', exact: true })).toBeFocused()

    const customer = scenario.form === 'customer'
    const form = page.locator(
      customer
        ? 'form[aria-describedby~="customer-create-status"]'
        : 'form[aria-describedby~="order-intake-status"]',
    )
    const oldValues: Record<string, string> = customer
      ? { Nombre: 'Cliente envío anterior', Correo: 'old@example.invalid', Teléfono: '5550101' }
      : {
          'Problema reportado': 'Freno del envío anterior',
          'Condición al recibir': 'Condición anterior',
          Accesorios: 'Luz anterior',
          Marca: 'Marca anterior',
          Modelo: 'Modelo anterior',
        }
    const newValues: Record<string, string> = customer
      ? { Nombre: 'Cliente borrador nuevo', Correo: 'new@example.invalid', Teléfono: '5550102' }
      : {
          'Problema reportado': 'Transmisión del borrador nuevo',
          'Condición al recibir': 'Condición nueva',
          Accesorios: 'Candado nuevo',
          Marca: 'Marca nueva',
          Modelo: 'Modelo nuevo',
        }
    const before = await kernelSnapshot(page)
    expect(before.journal).toHaveLength(1) // unrelated pending fixture capture
    const nextCustomerId = before.journal[0]!.entityId
    if (!customer) {
      await form
        .getByRole('combobox', { name: 'Cliente', exact: true })
        .selectOption(seeded.customerId)
      await form.getByRole('combobox', { name: 'Prioridad', exact: true }).selectOption('high')
      await form.getByLabel('Agregar bicicleta').check()
    }
    await fillFields(form, oldValues)
    const entityType = customer ? 'customer' : 'service_order'
    const key = customer ? 'display_name' : 'reported_problem'
    const oldValue = oldValues[customer ? 'Nombre' : 'Problema reportado']!
    await observeCompletion(page, entityType, key, oldValue)
    await holdJournalCompletion(page, { entityType, payloadKey: key, value: oldValue })
    try {
      await form
        .getByRole('button', { name: customer ? 'Guardar cliente' : 'Guardar orden' })
        .click()
      await waitForJournalBarrier(page)
      await expect(form.getByRole('button', { name: 'Guardando…', exact: true })).toBeDisabled()
      const committed = await kernelSnapshot(page)
      expect(committed.journal.slice(0, before.journal.length)).toEqual(before.journal)
      expectPayloads(
        committed.journal.slice(before.journal.length),
        customer,
        oldValues,
        seeded.customerId,
        'high',
      )
      expect(
        await page.evaluate(() => (window as ProbeWindow).captureCompletionProbe!.events),
      ).toEqual([{ type: 'complete', trusted: true }])

      await fillFields(form, newValues)
      if (!customer) {
        await form
          .getByRole('combobox', { name: 'Cliente', exact: true })
          .selectOption(nextCustomerId)
        await form.getByRole('combobox', { name: 'Prioridad', exact: true }).selectOption('urgent')
        await form.getByLabel('Agregar bicicleta').uncheck()
      }
      await expect(form).toHaveAttribute('data-dirty', 'true')
      await releaseJournalCompletion(page)
      const status = form.locator(
        customer ? '#customer-create-status[role="status"]' : '#order-intake-status[role="status"]',
      )
      await expect(status).toHaveText(PREVIOUS_SAVED)
      await expect(status).toHaveAttribute('aria-live', 'polite')
      await expect(form).toHaveAttribute('data-dirty', 'true')
      const submit = form.getByRole('button', {
        name: customer ? 'Guardar cliente' : 'Guardar orden',
      })
      await expect(submit).toBeEnabled()
      if (!customer) {
        await expect(form.getByLabel('Agregar bicicleta')).not.toBeChecked()
        await expect(form.getByRole('textbox', { name: 'Marca', exact: true })).toHaveCount(0)
        await expect(form.getByRole('combobox', { name: 'Cliente', exact: true })).toHaveValue(
          nextCustomerId,
        )
        await expect(form.getByRole('combobox', { name: 'Prioridad', exact: true })).toHaveValue(
          'urgent',
        )
        // Reveal the preserved hidden draft; this is another explicit user edit,
        // not an automatic retry or a claim of create-operation deduplication.
        await form.getByLabel('Agregar bicicleta').check()
      }
      await expectFields(form, newValues)
      expect((await kernelSnapshot(page)).journal).toEqual(committed.journal)
      const dialog = page.waitForEvent('dialog').then(async (confirmation) => {
        const message = confirmation.message()
        await confirmation.dismiss()
        return message
      })
      await page.getByRole('button', { name: 'Cerrar esta sesión', exact: true }).click()
      expect(await dialog).toContain('formularios sin enviar')
      await expect(status).toHaveText(PREVIOUS_SAVED)
      await expectFields(form, newValues)
      expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([])
      await info.attach(`newer-draft-${scenario.theme}`, {
        body: await page.screenshot({ fullPage: true }),
        contentType: 'image/png',
      })

      await submit.focus()
      await submit.press('Enter')
      await expect(status).toHaveText(
        customer ? 'Cliente guardado localmente' : 'Orden guardada localmente',
      )
      await expect(form).toHaveAttribute('data-dirty', 'false')
      const after = await kernelSnapshot(page)
      expect(after.journal.slice(0, committed.journal.length)).toEqual(committed.journal)
      expectPayloads(
        after.journal.slice(committed.journal.length),
        customer,
        newValues,
        nextCustomerId,
        'urgent',
      )
      for (const label of Object.keys(newValues).filter(
        (label) => !['Marca', 'Modelo'].includes(label),
      ))
        await expect(form.getByRole('textbox', { name: label, exact: true })).toHaveValue('')
      if (!customer) {
        await expect(form.getByRole('combobox', { name: 'Cliente', exact: true })).toHaveValue(
          nextCustomerId,
        )
        await expect(form.getByRole('combobox', { name: 'Prioridad', exact: true })).toHaveValue(
          'urgent',
        )
        await expect(form.getByLabel('Agregar bicicleta')).not.toBeChecked()
        await form.getByLabel('Agregar bicicleta').check()
        await expectFields(form, { Marca: '', Modelo: '' })
        await form.getByLabel('Agregar bicicleta').uncheck()
        await expect(form).toHaveAttribute('data-dirty', 'false')
      }
      expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([])
      await info.attach(`explicit-save-${scenario.theme}`, {
        body: await page.screenshot({ fullPage: true }),
        contentType: 'image/png',
      })
    } finally {
      await releaseJournalCompletion(page)
      await page.evaluate(() => (window as ProbeWindow).captureCompletionProbe?.restore())
    }
  })

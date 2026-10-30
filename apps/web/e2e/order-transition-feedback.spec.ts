import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Page } from '@playwright/test'
import {
  DATABASE,
  kernelSnapshot,
  holdJournalCompletion,
  waitForJournalBarrier,
  releaseJournalCompletion,
} from './helpers/authenticated-workshop.js'
import { seedWorkshop } from './helpers/visual-fixture.js'

const CANARY = 'private-transition-browser-canary'
const UNKNOWN =
  'No se pudo confirmar si el cambio se guardó. No repitas la acción; verifica el estado del taller antes de continuar.'
const COMMITTED =
  'El cambio se guardó localmente, pero no se pudo actualizar la vista. No repitas la acción; verifica el estado y el historial antes de continuar.'
type Fault = 'preparation' | 'quota' | 'history' | 'none'
type Probe = {
  calls: number
  writes: number
  injected: number
  mutationId: string | null
  terminal: { type: string; trusted: boolean }[]
  restore(): void
}
type ProbeWindow = Window & { orderTransitionProbe?: Probe }

async function installFault(page: Page, orderId: string, fault: Fault) {
  await page.evaluate(
    ({ orderId, fault, database, canary }) => {
      const probe: Probe = {
        calls: 0,
        writes: 0,
        injected: 0,
        mutationId: null,
        terminal: [],
        restore() {},
      }
      ;(window as ProbeWindow).orderTransitionProbe = probe
      const random = crypto.getRandomValues
      const add = IDBObjectStore.prototype.add
      const getAll = IDBIndex.prototype.getAll
      let committed = false
      let writeTransaction: IDBTransaction | null = null
      if (fault === 'preparation')
        crypto.getRandomValues = function <T extends ArrayBufferView | null>(array: T): T {
          probe.calls++
          if (!probe.injected) {
            probe.injected++
            throw new Error(canary)
          }
          return random.call(crypto, array) as T
        }
      IDBObjectStore.prototype.add = function (value: unknown, key?: IDBValidKey) {
        const row = value as {
          entityType?: string
          entityId?: string
          mutationId?: string
          envelope?: { operation?: string; payload?: { transition?: { action?: string } } }
        }
        if (
          this.transaction.db.name === database &&
          this.name === 'operationJournal' &&
          row.entityType === 'service_order' &&
          row.entityId === orderId &&
          row.envelope?.operation === 'update' &&
          row.envelope.payload?.transition?.action === 'start_diagnosis'
        ) {
          probe.writes++
          probe.mutationId = row.mutationId ?? null
          writeTransaction = this.transaction
          for (const type of ['complete', 'abort'])
            this.transaction.addEventListener(
              type,
              (event) => {
                probe.terminal.push({ type: event.type, trusted: event.isTrusted })
                if (type === 'complete' && event.isTrusted) committed = true
              },
              { once: true },
            )
          if (fault === 'quota' && !probe.injected) {
            probe.injected++
            throw new DOMException(canary, 'QuotaExceededError')
          }
        }
        return add.call(this, value, key)
      }
      IDBIndex.prototype.getAll = function (...args: Parameters<IDBIndex['getAll']>) {
        const argument: unknown = args[0]
        const options =
          argument !== null && typeof argument === 'object' && 'query' in argument
            ? (argument as { query: unknown; count?: number })
            : null
        const range = options ? options.query : argument
        const count = options ? options.count : args[1]
        if (
          fault === 'history' &&
          committed &&
          !probe.injected &&
          this.objectStore.transaction.db.name === database &&
          this.objectStore.name === 'operationEvents' &&
          this.name === '[mutationId+sequence]' &&
          this.objectStore.transaction !== writeTransaction &&
          range instanceof IDBKeyRange &&
          Array.isArray(range.lower) &&
          Array.isArray(range.upper) &&
          range.lower[0] === probe.mutationId &&
          range.upper[0] === probe.mutationId &&
          range.lower[1] === 0 &&
          range.upper[1] === Number.MAX_SAFE_INTEGER &&
          count === 51
        ) {
          probe.injected++
          throw new Error(canary)
        }
        return Reflect.apply(getAll, this, args)
      }
      probe.restore = () => {
        crypto.getRandomValues = random
        IDBObjectStore.prototype.add = add
        IDBIndex.prototype.getAll = getAll
      }
    },
    { orderId, fault, database: DATABASE, canary: CANARY },
  )
}

const scenarios = [
  { theme: 'banco', label: 'Banco de trabajo', fault: 'preparation' },
  { theme: 'plano', label: 'Plano técnico', fault: 'quota' },
  { theme: 'ritmo', label: 'Ritmo modular', fault: 'history' },
  { theme: 'noche', label: 'Turno nocturno', fault: 'none' },
] as const

for (const scenario of scenarios)
  test(`${scenario.theme}: order transition ${scenario.fault} preserves outcome and excludes repeated action`, async ({
    page,
    request,
  }, info) => {
    await page.setViewportSize({ width: 1440, height: 1000 })
    const seeded = await seedWorkshop(page, request)
    if (scenario.theme !== 'banco') {
      await page.getByRole('button', { name: 'Personalización', exact: true }).click()
      const theme = page.getByRole('radio', { name: new RegExp(scenario.label) })
      await theme.focus()
      await theme.press('Space')
      await expect(theme).toBeChecked()
      await expect(page.locator('.workshop-shell')).toHaveAttribute('data-theme', scenario.theme)
      await expect(page.locator('.preference-status')).toContainText('guardada en este dispositivo')
      await theme.press('Escape')
    }
    const problem = 'Caso visual 4: revisión de frenos y transmisión'
    const card = page.getByRole('listitem', { name: `Orden ${problem}`, exact: true })
    const orderId = seeded.orders[3]!
    const before = await kernelSnapshot(page)
    await installFault(page, orderId, scenario.fault)
    try {
      const action = card.getByRole('button', { name: 'Iniciar diagnóstico', exact: true })
      await action.focus()
      // End-to-end same-task duplicate activation; pure gate tests separately
      // prove synchronous exclusion. No transaction or promise ordering is altered.
      await action.evaluate((button) => {
        ;(button as HTMLButtonElement).click()
        ;(button as HTMLButtonElement).click()
      })
      const saved = scenario.fault === 'history' || scenario.fault === 'none'
      if (scenario.fault === 'none') {
        await expect(card.getByRole('button', { name: 'Autorizar', exact: true })).toBeEnabled()
      } else {
        await expect(card.getByRole('alert')).toHaveText(saved ? COMMITTED : UNKNOWN)
        for (const button of await card.locator('.order-actions button').all())
          await expect(button).toBeDisabled()
      }
      await expect(
        card.getByText(saved ? 'En diagnóstico' : 'Recibida', { exact: true }),
      ).toBeVisible()
      await expect(page.locator('body')).not.toContainText(CANARY)
      if (scenario.fault !== 'preparation')
        await expect
          .poll(() => page.evaluate(() => (window as ProbeWindow).orderTransitionProbe!.terminal))
          .toEqual([{ type: saved ? 'complete' : 'abort', trusted: true }])
      const after = await kernelSnapshot(page)
      expect(after.records).toEqual(before.records)
      expect(after.journal).toHaveLength(before.journal.length + Number(saved))
      expect(after.events).toHaveLength(before.events.length + Number(saved))
      if (saved) {
        const mutation = after.journal.find(
          (row) => row.entityId === orderId && row.envelope.operation === 'update',
        )!
        expect(mutation.optimistic.state).toBe('DIAGNOSIS')
        expect(
          after.events.filter(
            (event) => event.mutationId === mutation.mutationId && event.kind === 'local',
          ),
        ).toHaveLength(1)
      } else {
        expect(after.journal).toEqual(before.journal)
        expect(after.events).toEqual(before.events)
        expect(after.delivery).toEqual(before.delivery)
      }
      const observation = await page.evaluate(() => {
        const p = (window as ProbeWindow).orderTransitionProbe!
        return { calls: p.calls, writes: p.writes, injected: p.injected, terminal: p.terminal }
      })
      expect(observation.writes).toBe(scenario.fault === 'preparation' ? 0 : 1)
      expect(observation.calls).toBe(scenario.fault === 'preparation' ? 1 : 0)
      expect(observation.injected).toBe(scenario.fault === 'none' ? 0 : 1)

      // The same list remains mounted through filtering and a page refresh.
      const search = page.getByRole('searchbox', { name: 'Buscar órdenes', exact: true })
      await search.fill('not-present-synthetic-order')
      await expect(card).toHaveCount(0)
      await search.fill('')
      await page.getByRole('button', { name: 'Primeras órdenes', exact: true }).click()
      await expect(card).toBeVisible()
      if (scenario.fault !== 'none') {
        await expect(card.getByRole('alert')).toHaveText(saved ? COMMITTED : UNKNOWN)
        for (const button of await card.locator('.order-actions button').all()) {
          await expect(button).toBeDisabled()
          await button.evaluate((element) => (element as HTMLButtonElement).click())
        }
        await card.getByRole('button', { name: 'Ver historial', exact: true }).click()
        await expect(card.getByRole('alert')).toHaveText(saved ? COMMITTED : UNKNOWN)
        const retained = await kernelSnapshot(page)
        expect(retained.journal).toEqual(after.journal)
        expect(retained.events).toEqual(after.events)
        expect(retained.records).toEqual(after.records)
      } else {
        const next = card.getByRole('button', { name: 'Autorizar', exact: true })
        await next.focus()
        await next.press('Enter')
        await expect(card.getByText('Autorizada', { exact: true })).toBeVisible()
        await expect(
          card.getByRole('button', { name: 'Iniciar trabajo', exact: true }),
        ).toBeEnabled()
        expect((await kernelSnapshot(page)).journal).toHaveLength(before.journal.length + 2)
      }
      const other = page.getByRole('listitem', {
        name: 'Orden Caso visual 1: revisión de frenos y transmisión',
        exact: true,
      })
      await expect(
        other.getByRole('button', { name: 'Solicitar refacciones', exact: true }),
      ).toBeEnabled()
      expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([])
      await info.attach('order-transition-observation', {
        body: JSON.stringify({ scenario, ...observation, guardLifetime: 'mounted-list-only' }),
        contentType: 'application/json',
      })
      await info.attach(`order-transition-${scenario.theme}`, {
        body: await page.screenshot({ fullPage: true }),
        contentType: 'image/png',
      })
    } finally {
      await page.evaluate(() => (window as ProbeWindow).orderTransitionProbe?.restore())
    }
  })

for (const boundary of ['filtered-cards', 'workspace-unmount'] as const) {
  test(`pending order transition survives ${boundary} without false settlement`, async ({
    page,
    request,
  }, info) => {
    const seeded = await seedWorkshop(page, request)
    const problem = 'Caso visual 4: revisión de frenos y transmisión'
    const card = page.getByRole('listitem', { name: `Orden ${problem}`, exact: true })
    const before = await kernelSnapshot(page)
    const partition = before.partition.partitionId
    await holdJournalCompletion(page, {
      entityType: 'service_order',
      orderId: seeded.orders[3]!,
      transitionAction: 'start_diagnosis',
    })
    try {
      await card.getByRole('button', { name: 'Iniciar diagnóstico', exact: true }).click()
      await waitForJournalBarrier(page)
      // Existing barrier delays Dexie's notification AFTER genuine native commit,
      // never the commit itself. This is a composition fault, not timing evidence.
      const committed = await kernelSnapshot(page)
      expect(committed.journal).toHaveLength(before.journal.length + 1)
      expect(committed.events).toHaveLength(before.events.length + 1)
      expect(
        committed.journal.filter(
          (row) => row.entityId === seeded.orders[3] && row.optimistic.state === 'DIAGNOSIS',
        ),
      ).toHaveLength(1)
      if (boundary === 'filtered-cards') {
        const search = page.getByRole('searchbox', { name: 'Buscar órdenes', exact: true })
        await search.fill('not-present-synthetic-order')
        await expect(card).toHaveCount(0)
        await search.fill('')
        await page.getByRole('button', { name: 'Primeras órdenes', exact: true }).click()
        await expect(card.getByText('En diagnóstico', { exact: true })).toBeVisible()
        for (const button of await card.locator('.order-actions button').all()) {
          await expect(button).toBeDisabled()
          await button.evaluate((element) => (element as HTMLButtonElement).click())
        }
        expect((await kernelSnapshot(page)).journal).toEqual(committed.journal)
        await releaseJournalCompletion(page)
        await expect(card.getByRole('button', { name: 'Autorizar', exact: true })).toBeEnabled()
        expect((await kernelSnapshot(page)).journal).toEqual(committed.journal)
      } else {
        page.once('dialog', (dialog) => void dialog.accept())
        await page.getByRole('button', { name: 'Cerrar esta sesión', exact: true }).click()
        await expect(page.locator('.workshop-shell')).toHaveCount(0)
        await expect(
          page.getByRole('button', { name: 'Iniciar sesión', exact: true }),
        ).toBeVisible()
        await releaseJournalCompletion(page)
        // Logout preserves the selected partition/context. The old callback
        // cannot restore a workspace or publish into the login screen.
        const retained = await kernelSnapshot(page, partition)
        expect(retained.journal).toEqual(committed.journal)
        expect(retained.events).toEqual(committed.events)
        expect(retained.records).toEqual(committed.records)
        await expect(page.locator('.workshop-shell')).toHaveCount(0)
        await expect(
          page.getByRole('button', { name: 'Iniciar sesión', exact: true }),
        ).toBeVisible()
        await expect(page.locator('body')).not.toContainText(COMMITTED)
        await expect(page.locator('body')).not.toContainText(UNKNOWN)
      }
      expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([])
      await info.attach(`order-transition-${boundary}`, {
        body: await page.screenshot({ fullPage: true }),
        contentType: 'image/png',
      })
    } finally {
      await releaseJournalCompletion(page)
    }
  })
}

import type { Page } from '@playwright/test'
import { DATABASE } from './authenticated-workshop.js'

export const CANARY = 'private-transition-browser-canary'
export const UNKNOWN =
  'No se pudo confirmar si el cambio se guardó. No repitas la acción; verifica el estado del taller antes de continuar.'
export const COMMITTED =
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
export type ProbeWindow = Window & { orderTransitionProbe?: Probe }

export async function installFault(page: Page, orderId: string, fault: Fault) {
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

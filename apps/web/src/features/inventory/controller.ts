import type { WorkshopController } from '../../runtime/controller.js'
import type { ConnectedReadCapture, ConnectedReadSnapshot } from '../../runtime/connected-read.js'
import type { AccountAccessSnapshot } from '../../runtime/account-access.js'
import type { WorkshopLocation } from '../../runtime/transport.js'
import { createInventoryTransport, type InventoryTransport } from './transport.js'
import {
  InventoryHttpError,
  type InventoryErrorCode,
  type InventoryProduct,
  type InventoryStock,
  type InventoryMovementPage,
} from './contracts.js'

type Runtime = Pick<
  WorkshopController,
  | 'connectedReads'
  | 'getAccountSnapshot'
  | 'subscribeAccount'
  | 'verifyAccount'
  | 'getSnapshot'
  | 'subscribe'
  | 'loadLocations'
>
type ReadKind = 'catalog' | 'stock' | 'history'
export interface InventoryRead<T> {
  phase: 'idle' | 'loading' | 'ready' | 'error'
  value: T | null
  error: InventoryErrorCode | null
  receivedAt: number | null
}
export interface InventorySnapshot {
  access: ConnectedReadSnapshot
  account: AccountAccessSnapshot
  generation: number
  locations: WorkshopLocation[]
  nextLocation: string | null
  catalog: InventoryRead<InventoryProduct[]>
  offset: number
  product: InventoryProduct | null
  stock: InventoryRead<InventoryStock>
  history: InventoryRead<InventoryMovementPage>
  historyBefore: string | null
}
const emptyRead = <T>(): InventoryRead<T> => ({
  phase: 'idle',
  value: null,
  error: null,
  receivedAt: null,
})
/** One bounded page per kind. Every volatile result belongs to a current runtime capture. */
export class InventoryController {
  #snapshot: InventorySnapshot
  #listeners = new Set<() => void>()
  #unsubscribers: (() => void)[]
  #generation = 0
  #selection = 0
  #entry = 0
  #disposed = false
  #requests = { catalog: 0, stock: 0, history: 0 }
  #aborts = {
    catalog: new AbortController(),
    stock: new AbortController(),
    history: new AbortController(),
  }
  constructor(
    private readonly runtime: Runtime,
    private readonly transport?: InventoryTransport,
    private readonly now = Date.now,
  ) {
    this.#snapshot = this.empty()
    this.#unsubscribers = [
      runtime.connectedReads.subscribe(() => this.reset()),
      runtime.subscribeAccount(() => this.reset()),
      runtime.subscribe(() => {
        const state = runtime.getSnapshot()
        if (
          state.locations !== this.#snapshot.locations ||
          state.nextLocation !== this.#snapshot.nextLocation
        )
          this.publish({ locations: state.locations, nextLocation: state.nextLocation })
      }),
    ]
  }
  private empty(): InventorySnapshot {
    const state = this.runtime.getSnapshot()
    return {
      access: this.runtime.connectedReads.getSnapshot(),
      account: this.runtime.getAccountSnapshot(),
      generation: this.#generation,
      locations: state.locations,
      nextLocation: state.nextLocation,
      catalog: emptyRead(),
      offset: 0,
      product: null,
      stock: emptyRead(),
      history: emptyRead(),
      historyBefore: null,
    }
  }
  getSnapshot = () => this.#snapshot
  subscribe = (listener: () => void) => {
    this.#listeners.add(listener)
    return () => this.#listeners.delete(listener)
  }
  private publish(patch: Partial<InventorySnapshot>) {
    if (this.#disposed) return
    this.#snapshot = Object.freeze({ ...this.#snapshot, ...patch })
    for (const listener of this.#listeners) listener()
  }
  private cancel(kind: ReadKind) {
    this.#requests[kind]++
    this.#aborts[kind].abort()
    this.#aborts[kind] = new AbortController()
  }
  private reset() {
    if (this.#disposed) return
    this.#generation++
    this.#selection++
    for (const kind of ['catalog', 'stock', 'history'] as const) this.cancel(kind)
    this.#snapshot = this.empty()
    for (const listener of this.#listeners) listener()
  }
  async enter(locationId?: string) {
    if (this.#disposed) return
    const entry = ++this.#entry
    const expectedUser = this.runtime.getAccountSnapshot().user ?? this.runtime.getSnapshot().user
    try {
      // verifyAccount establishes its generation synchronously, before its first await.
      // Capture that generation after invocation so its own reset is accepted while
      // a later A→B→A/session replacement cannot continue this explicit action.
      const verification =
        this.runtime.getAccountSnapshot().phase !== 'connected'
          ? this.runtime.verifyAccount()
          : Promise.resolve()
      const accountGeneration = this.runtime.getAccountSnapshot().generation
      await verification
      const account = this.runtime.getAccountSnapshot(),
        user = account.user
      if (
        this.#disposed ||
        entry !== this.#entry ||
        accountGeneration !== account.generation ||
        !user ||
        (expectedUser &&
          (user.user_id !== expectedUser.user_id ||
            user.organization_id !== expectedUser.organization_id))
      )
        return
      const connected = this.runtime.connectedReads.verify(locationId)
      const accessGeneration = this.runtime.connectedReads.getSnapshot().generation
      await connected
      if (
        !this.#disposed &&
        entry === this.#entry &&
        accountGeneration === this.runtime.getAccountSnapshot().generation &&
        accessGeneration === this.runtime.connectedReads.getSnapshot().generation
      )
        await this.loadCatalog()
    } catch {
      // The runtime owns verification state and safe refusal messages.
    }
  }
  clearSelection() {
    this.#entry++
    this.runtime.connectedReads.clear()
  }
  loadLocations = (afterId?: string) => this.runtime.loadLocations(afterId)
  private begin(kind: ReadKind) {
    if (this.#disposed) return null
    this.cancel(kind)
    let account: ConnectedReadCapture
    try {
      account = this.runtime.connectedReads.capture()
    } catch {
      return null
    }
    if (!account.context.capabilities.includes('inventory.read')) {
      this.publish({ [kind]: { ...emptyRead(), phase: 'error', error: 'capability_denied' } })
      return null
    }
    const generation = this.#generation,
      selection = this.#selection,
      sequence = this.#requests[kind]
    const signal = AbortSignal.any([account.signal, this.#aborts[kind].signal])
    const request: ConnectedReadCapture = Object.freeze({
      ...account,
      signal,
      isCurrent: () =>
        !this.#disposed &&
        !signal.aborted &&
        generation === this.#generation &&
        selection === this.#selection &&
        sequence === this.#requests[kind] &&
        account.isCurrent(),
    })
    this.publish({ [kind]: { ...emptyRead(), phase: 'loading' } })
    return {
      account,
      request,
      http:
        this.transport ??
        createInventoryTransport({ apiRealm: account.apiRealm, fetch: globalThis.fetch }),
    }
  }
  private async current(source: NonNullable<ReturnType<InventoryController['begin']>>) {
    // Live-query notifications can lag a committed durable owner takeover.
    // Inspect the actual owner before dispatch and after every network await.
    try {
      await this.runtime.connectedReads.check()
      return source.request.isCurrent()
    } catch {
      return false
    }
  }
  private async failed(
    kind: ReadKind,
    source: NonNullable<ReturnType<InventoryController['begin']>>,
    error: unknown,
  ) {
    if (!(await this.current(source))) return
    if (error instanceof InventoryHttpError && (error.status === 401 || error.status === 403)) {
      this.runtime.connectedReads.refuse(source.account, error.status)
      return
    }
    this.publish({
      [kind]: {
        ...emptyRead(),
        phase: 'error',
        error: error instanceof InventoryHttpError ? error.code : 'network_error',
      },
    })
  }
  private received<T>(value: T): InventoryRead<T> {
    const now = this.now()
    if (!Number.isFinite(now)) throw new InventoryHttpError('stale_request')
    return { phase: 'ready', value, error: null, receivedAt: now }
  }
  async loadCatalog(offset = 0) {
    if (!Number.isSafeInteger(offset) || offset < 0 || offset > 2147483647 || this.#disposed) return
    this.#selection++
    this.cancel('stock')
    this.cancel('history')
    this.publish({
      offset,
      product: null,
      stock: emptyRead(),
      history: emptyRead(),
      historyBefore: null,
    })
    const source = this.begin('catalog')
    if (!source) return
    try {
      if (!(await this.current(source))) return
      const rows = await source.http.catalog(source.request, offset)
      if (await this.current(source)) this.publish({ catalog: this.received(rows) })
    } catch (error) {
      await this.failed('catalog', source, error)
    }
  }
  async selectProduct(productId: string) {
    if (this.#disposed) return
    const product = this.#snapshot.catalog.value?.find((row) => row.product_id === productId)
    if (!product) return
    this.#selection++
    this.cancel('stock')
    this.cancel('history')
    this.publish({ product, stock: emptyRead(), history: emptyRead(), historyBefore: null })
    await Promise.all([this.refreshStock(), this.newest()])
  }
  async refreshStock() {
    const product = this.#snapshot.product
    if (!product) return
    const source = this.begin('stock')
    if (!source) return
    try {
      if (!(await this.current(source))) return
      const value = await source.http.stock(source.request, product.product_id)
      if (await this.current(source)) this.publish({ stock: this.received(value) })
    } catch (error) {
      await this.failed('stock', source, error)
    }
  }
  private async history(before?: string) {
    const product = this.#snapshot.product
    if (!product) return
    const source = this.begin('history')
    if (!source) return
    this.publish({ historyBefore: before ?? null })
    try {
      if (!(await this.current(source))) return
      const value = await source.http.movements(source.request, product.product_id, before)
      if (await this.current(source)) this.publish({ history: this.received(value) })
    } catch (error) {
      await this.failed('history', source, error)
    }
  }
  newest = () => this.history()
  older = async () => {
    const next = this.#snapshot.history.value?.next_cursor
    if (next) await this.history(next)
  }
  dispose() {
    if (this.#disposed) return
    this.reset()
    this.#entry++
    this.#disposed = true
    for (const unsubscribe of this.#unsubscribers) unsubscribe()
    this.runtime.connectedReads.clear()
    this.#listeners.clear()
  }
}

/** Volatile read presentation only. No draft ownership, persistence or authority. */
export interface CustomerChoice {
  customer_id: string
  display_name: string
}
export interface CustomerLookupSnapshot {
  query: string
  searching: boolean
  matches: readonly CustomerChoice[]
  nextAfterId: string | null
  pages: number
  busy: boolean
  message: string | null
  selection: {
    id: string
    status: 'none' | 'pending' | 'available' | 'unavailable' | 'failed'
    customer: CustomerChoice | null
  }
}
const initial = (): Omit<CustomerLookupSnapshot, 'busy'> => ({
  query: '',
  searching: false,
  matches: [],
  nextAfterId: null,
  pages: 0,
  message: null,
  selection: { id: '', status: 'none', customer: null },
})
export class CustomerLookup {
  revision = 0
  selectionRevision = 0
  private view: object | null = null
  private state = initial()
  private flight: Promise<void> | null = null
  constructor(private readonly changed: () => void) {}
  snapshot(): CustomerLookupSnapshot {
    return Object.freeze({ ...this.state, busy: this.flight !== null })
  }
  bind(view: object) {
    if (this.view !== view) {
      this.clear()
      this.view = view
    }
  }
  clear() {
    this.revision++
    this.selectionRevision++
    this.view = null
    this.state = initial()
  }
  edit(query: string) {
    this.revision++
    this.state = {
      ...this.state,
      query,
      searching: query.length > 0,
      matches: [],
      nextAfterId: null,
      pages: 0,
      message: null,
    }
  }
  select(id: string) {
    if (this.state.selection.id === id) return
    this.revision++
    this.selectionRevision++
    this.state = {
      ...this.state,
      selection: { id, status: id ? 'pending' : 'none', customer: null },
    }
  }
  message(message: string) {
    this.state = { ...this.state, message }
  }
  selected(id: string, customer: CustomerChoice | null) {
    this.state = {
      ...this.state,
      selection: { id, status: customer ? 'available' : 'unavailable', customer },
    }
  }
  page(matches: readonly CustomerChoice[], nextAfterId: string | null, restart: boolean) {
    this.state = {
      ...this.state,
      searching: true,
      matches: Object.freeze(matches),
      nextAfterId,
      pages: restart ? 1 : this.state.pages + 1,
      message: null,
    }
  }
  retry() {
    this.revision++
    this.selectionRevision++
    this.state = {
      ...this.state,
      message: null,
      selection: {
        id: this.state.selection.id,
        status: this.state.selection.id ? 'pending' : 'none',
        customer: null,
      },
    }
  }
  async wait() {
    await this.flight
  }
  async run<T>(
    read: () => Promise<T>,
    apply: (value: T) => void,
    current: () => boolean,
    epoch: () => number = () => this.revision,
  ) {
    if (this.flight) return
    const revision = epoch()
    let done!: () => void
    this.flight = new Promise<void>((resolve) => {
      done = resolve
    })
    this.changed()
    try {
      if (revision !== epoch() || !current()) return
      const result = await read()
      if (revision === epoch() && current()) apply(result)
    } catch {
      if (revision === epoch() && current())
        this.state = {
          ...this.state,
          matches: [],
          selection: {
            id: this.state.selection.id,
            status: this.state.selection.id ? 'failed' : 'none',
            customer: null,
          },
          message: 'No se pudo consultar la lista local. Vuelve a intentarlo.',
        }
    } finally {
      this.flight = null
      done()
      this.changed()
    }
  }
}

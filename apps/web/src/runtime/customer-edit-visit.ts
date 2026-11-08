import type { CustomerDraftState } from '../features/draft-state.js'
import type { LocalCustomer } from '../local/types.js'
import type { CaptureFeedback } from '../features/capture-feedback.js'

export interface CustomerEditDraft extends CustomerDraftState {
  customerId: string
  baseVersion: number
  original: CustomerDraftState
}
export interface CustomerEditSnapshot {
  draft: Readonly<CustomerEditDraft> | null
  dirty: boolean
  busy: boolean
  blocked: boolean
  message: string | null
}
/** Memory-only edit ownership for one uninterrupted view; saved updates use the kernel journal. */
export class CustomerEditVisit {
  private scope: string | null = null
  private draft: CustomerEditDraft | null = null
  private pending: { token: object; input: CustomerEditDraft } | null = null
  private blocked = false
  private message: string | null = null
  private revision = 0
  snapshot(): CustomerEditSnapshot {
    const draft = this.draft
      ? Object.freeze({ ...this.draft, original: Object.freeze({ ...this.draft.original }) })
      : null
    return Object.freeze({
      draft,
      dirty: this.dirty(),
      busy: !!this.pending,
      blocked: this.blocked,
      message: this.message,
    })
  }
  private dirty() {
    return (
      !!this.draft &&
      (['displayName', 'email', 'phone'] as const).some(
        (key) => this.draft![key] !== this.draft!.original[key],
      )
    )
  }
  hasUnsent() {
    return this.dirty() || !!this.pending || this.blocked
  }
  observeScope(scope: string) {
    if (this.scope === scope) return
    this.reset()
    this.scope = scope
  }
  reset() {
    this.revision++
    this.draft = null
    this.pending = null
    this.blocked = false
    this.message = null
  }
  revisionToken() {
    return this.revision
  }
  open(customer: LocalCustomer) {
    if (this.hasUnsent()) return false
    const original = {
      displayName: customer.display_name,
      email: customer.email ?? '',
      phone: customer.phone ?? '',
    }
    this.draft = {
      ...original,
      original,
      customerId: customer.customer_id,
      baseVersion: customer.version,
    }
    this.message = null
    this.revision++
    return true
  }
  edit<K extends keyof CustomerDraftState>(field: K, value: CustomerDraftState[K]) {
    if (!this.draft || this.pending || this.blocked) return false
    this.draft = { ...this.draft, [field]: value }
    this.revision++
    this.message = null
    return true
  }
  cancel(discard = false) {
    if (this.pending || this.blocked || (this.dirty() && !discard)) return false
    this.reset()
    return true
  }
  begin() {
    if (!this.draft || !this.dirty() || this.pending || this.blocked) return null
    const input = structuredClone(this.draft)
    this.pending = { token: {}, input }
    this.message = null
    return this.pending
  }
  finish(token: object, feedback: CaptureFeedback) {
    if (this.pending?.token !== token) return false
    this.pending = null
    this.blocked ||= feedback.blockSubmission
    this.message = feedback.message
    if (feedback.status === 'saved') {
      this.draft = null
      this.message =
        'Cambio guardado en este dispositivo. Consulta el estado de sincronización y las incidencias.'
    }
    this.revision++
    return true
  }
  notice(message: string) {
    this.message = message
  }
}

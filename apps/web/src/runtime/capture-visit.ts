import type { CaptureFeedback } from '../features/capture-feedback.js'
import {
  hasCustomerDraft,
  hasOrderDraft,
  type CustomerDraftState,
  type OrderDraftState,
  type RetainedOrderSelection,
} from '../features/draft-state.js'
import type { TransitionProtectionScope } from './transition-protection.js'

export type CaptureVisitScope = TransitionProtectionScope
export type CaptureViewToken = object
export interface CaptureAttempt<D = CustomerDraftState | OrderDraftState> {
  readonly token: object
  readonly input: Readonly<D>
}
export interface CaptureFormSnapshot<D> {
  readonly draft: Readonly<D>
  readonly busy: boolean
  readonly blocked: boolean
  readonly message: string | null
  readonly dirty: boolean
}
export interface CaptureVisitSnapshot {
  readonly viewToken: CaptureViewToken
  readonly customer: CaptureFormSnapshot<CustomerDraftState>
  readonly order: CaptureFormSnapshot<OrderDraftState>
  readonly notice: string | null
}
interface Pending<D> extends CaptureAttempt<D> {
  revision: object
}
interface FormState<D> {
  draft: D
  revision: object
  pending: Pending<D> | null
  blocked: boolean
  message: string | null
}
const emptyCustomer = (): CustomerDraftState => ({ displayName: '', email: '', phone: '' })
const emptySelection = (): RetainedOrderSelection => ({ customerId: '', priority: 'normal' })
const emptyOrder = (): OrderDraftState => ({
  ...emptySelection(),
  reportedProblem: '',
  intakeCondition: '',
  accessories: '',
  withBicycle: false,
  brand: '',
  model: '',
})
const form = <D>(draft: D): FormState<D> => ({
  draft,
  revision: {},
  pending: null,
  blocked: false,
  message: null,
})
const deniedNotice =
  'Hay una captura pendiente de confirmar de la visita anterior. No la repitas; las nuevas capturas están bloqueadas en esta visita.'
const closedNotice =
  'Las capturas no están disponibles en esta visita. Inicia una nueva sesión para continuar.'
const discardedNotice = 'Los formularios anteriores no están disponibles en este contexto.'
const olderSaved = 'El envío anterior se guardó localmente. El formulario actual sigue sin guardar.'
function scopeKey(scope: CaptureVisitScope): string {
  return JSON.stringify([
    scope.apiRealm,
    scope.organizationId,
    scope.userId,
    scope.selectedLocationId,
    scope.datasetIncarnation,
    scope.authorizationEpoch,
    scope.policyRevision,
    [...new Set(scope.capabilities)].sort(),
    scope.sessionBindingId,
  ])
}

/** One volatile visit, never execution authority or durable recovery. */
export class CaptureVisit {
  private customer = form(emptyCustomer())
  private order = form(emptyOrder())
  private retained = emptySelection()
  private scope: string | null = null
  private view: CaptureViewToken | null = null
  private closed = false
  private denied = false
  private notice: string | null = null

  private clearValues(): void {
    this.customer = form(emptyCustomer())
    this.order = form(emptyOrder())
    this.retained = emptySelection()
  }
  startVisit(): void {
    this.clearValues()
    this.scope = null
    this.view = null
    this.closed = false
    this.denied = false
    this.notice = null
  }
  endVisit(): void {
    this.startVisit()
    this.closed = true
  }
  suspendView(): void {
    this.view = null
  }
  observeScope(scope: CaptureVisitScope): void {
    if (this.closed || this.denied) return
    const next = scopeKey(scope)
    if (this.scope !== null && this.scope !== next) {
      const protectedAttempt = !!(
        this.customer.pending ||
        this.customer.blocked ||
        this.order.pending ||
        this.order.blocked
      )
      const unsent = this.hasUnsent()
      this.suspendView()
      this.clearValues()
      if (protectedAttempt) {
        this.denied = true
        this.notice = deniedNotice
        this.scope = null
        return
      }
      if (unsent) this.notice = discardedNotice
    }
    this.scope = next
  }
  activateView(): void {
    // A view can present empty closed/denied state, but isCurrentView denies edits/commands.
    this.view = Object.freeze({})
  }
  isCurrentView(token: CaptureViewToken): boolean {
    return this.view === token && !this.closed && !this.denied && this.scope !== null
  }
  editCustomer<K extends keyof CustomerDraftState>(
    token: CaptureViewToken,
    field: K,
    value: CustomerDraftState[K],
  ): boolean {
    if (
      !this.isCurrentView(token) ||
      !Object.hasOwn(this.customer.draft, field) ||
      typeof value !== 'string'
    )
      return false
    this.customer.draft[field] = value
    this.customer.revision = {}
    return true
  }
  editOrder<K extends keyof OrderDraftState>(
    token: CaptureViewToken,
    field: K,
    value: OrderDraftState[K],
  ): boolean {
    if (
      !this.isCurrentView(token) ||
      !Object.hasOwn(this.order.draft, field) ||
      typeof value !== (field === 'withBicycle' ? 'boolean' : 'string')
    )
      return false
    this.order.draft[field] = value
    this.order.revision = {}
    return true
  }
  begin(token: CaptureViewToken, kind: 'customer'): CaptureAttempt<CustomerDraftState> | null
  begin(token: CaptureViewToken, kind: 'order'): CaptureAttempt<OrderDraftState> | null
  begin(token: CaptureViewToken, kind: 'customer' | 'order'): CaptureAttempt | null {
    if (!this.isCurrentView(token)) return null
    if (kind === 'customer') return this.beginForm(this.customer)
    if (kind === 'order') return this.beginForm(this.order)
    return null
  }
  private beginForm<D extends object>(state: FormState<D>): CaptureAttempt<D> | null {
    if (state.pending || state.blocked) return null
    const attempt = {
      token: Object.freeze({}),
      input: Object.freeze({ ...state.draft }),
      revision: state.revision,
    }
    state.pending = attempt
    state.message = null
    return Object.freeze({ token: attempt.token, input: attempt.input })
  }
  finish(token: object, feedback: CaptureFeedback): boolean {
    if (this.closed || this.denied) return false
    if (this.customer.pending?.token === token) {
      const attempt = this.customer.pending
      this.customer.pending = null
      this.customer.blocked ||= feedback.blockSubmission || feedback.status === 'unknown'
      this.customer.message = feedback.message
      if (feedback.status === 'saved') {
        if (attempt.revision !== this.customer.revision) this.customer.message = olderSaved
        else {
          this.customer.draft = emptyCustomer()
          this.customer.message = 'Cliente guardado localmente'
        }
      }
      return true
    }
    if (this.order.pending?.token === token) {
      const attempt = this.order.pending
      this.order.pending = null
      this.order.blocked ||= feedback.blockSubmission || feedback.status === 'unknown'
      this.order.message = feedback.message
      if (feedback.status === 'saved') {
        if (attempt.revision !== this.order.revision) this.order.message = olderSaved
        else {
          this.retained = {
            customerId: attempt.input.customerId,
            priority: attempt.input.priority,
          }
          this.order.draft = { ...emptyOrder(), ...this.retained }
          this.order.message = 'Orden guardada localmente'
        }
      }
      return true
    }
    return false
  }
  hasUnsent(): boolean {
    if (this.closed) return false
    return (
      this.denied ||
      !!this.customer.pending ||
      this.customer.blocked ||
      hasCustomerDraft(this.customer.draft) ||
      !!this.order.pending ||
      this.order.blocked ||
      hasOrderDraft(this.order.draft, this.retained)
    )
  }
  getSnapshot(): CaptureVisitSnapshot | null {
    if (this.view === null) return null
    const unavailable = this.closed || this.denied
    return Object.freeze({
      viewToken: this.view,
      customer: Object.freeze({
        draft: Object.freeze({ ...this.customer.draft }),
        busy: !!this.customer.pending,
        blocked: unavailable || this.customer.blocked,
        message: this.customer.message,
        dirty:
          this.denied ||
          !!this.customer.pending ||
          this.customer.blocked ||
          hasCustomerDraft(this.customer.draft),
      }),
      order: Object.freeze({
        draft: Object.freeze({ ...this.order.draft }),
        busy: !!this.order.pending,
        blocked: unavailable || this.order.blocked,
        message: this.order.message,
        dirty:
          this.denied ||
          !!this.order.pending ||
          this.order.blocked ||
          hasOrderDraft(this.order.draft, this.retained),
      }),
      notice: this.closed ? closedNotice : this.denied ? deniedNotice : this.notice,
    })
  }
}

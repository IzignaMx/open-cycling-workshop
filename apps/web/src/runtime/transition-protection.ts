import {
  OrderTransitionGate,
  type OrderTransitionFeedback,
  type OrderTransitionState,
} from '../features/orders/transition-feedback.js'

export interface TransitionProtectionScope {
  apiRealm: string
  organizationId: string
  userId: string
  selectedLocationId: string
  datasetIncarnation: string
  authorizationEpoch: string
  policyRevision: string
  capabilities: readonly string[]
  sessionBindingId: string
}
export interface TransitionProtectionSnapshot {
  readonly states: ReadonlyMap<string, OrderTransitionState>
  readonly notice: string | null
}
const capacityNotice =
  'No se pueden iniciar más acciones: hay cambios pendientes de confirmar en esta vista. No repitas las acciones anteriores.'
const scopeNotice =
  'Se conservó una protección por un cambio sin confirmar. Las acciones de órdenes están bloqueadas en esta visita; no repitas ese cambio.'

function scopeKey(scope: TransitionProtectionScope): string {
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

/** Volatile protection only. Scope comparison never grants authority or proves replay safety. */
export class TransitionProtection {
  private gate = new OrderTransitionGate()
  private scope: string | null = null
  private closed = true
  private denied = false

  startVisit(): void {
    this.gate = new OrderTransitionGate()
    this.scope = null
    this.denied = false
    this.closed = false
  }

  endVisit(): void {
    this.gate = new OrderTransitionGate()
    this.scope = null
    this.closed = true
  }

  observeScope(scope: TransitionProtectionScope): void {
    if (this.closed || this.denied) return
    const key = scopeKey(scope)
    if (this.scope !== null && this.scope !== key && this.gate.size > 0) {
      this.denied = true
      this.gate = new OrderTransitionGate()
      this.scope = null
      return
    }
    this.scope = key
  }

  begin(orderId: string): object | null {
    if (this.closed || this.denied || this.scope === null || this.gate.size >= 50) return null
    return this.gate.begin(orderId)
  }

  finish(orderId: string, token: object, feedback: OrderTransitionFeedback): boolean {
    if (this.closed || this.denied) return false
    return this.gate.finish(orderId, token, feedback)
  }

  getSnapshot(): TransitionProtectionSnapshot {
    return Object.freeze({
      states: this.gate.snapshot(),
      notice:
        this.closed || this.denied ? scopeNotice : this.gate.size >= 50 ? capacityNotice : null,
    })
  }
}

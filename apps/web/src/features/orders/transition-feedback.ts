export interface OrderTransitionFeedback {
  message: string | null
  block: boolean
}

const unknown = (): OrderTransitionFeedback => ({
  message:
    'No se pudo confirmar si el cambio se guardó. No repitas la acción; verifica el estado del taller antes de continuar.',
  block: true,
})

export function orderTransitionFeedback(
  input: { kind: 'resolved'; value: unknown } | { kind: 'rejected'; error: unknown },
): OrderTransitionFeedback {
  if (input.kind === 'rejected') return unknown()
  try {
    const value = input.value
    if (value === null || typeof value !== 'object' || Array.isArray(value)) return unknown()
    const record = value as Record<string, unknown>
    const keys = Reflect.ownKeys(record)
    if (keys.some((key) => typeof key !== 'string')) return unknown()
    if ((keys as string[]).sort().join(',') !== 'status,view') return unknown()
    if (record.status !== 'committed') return unknown()
    if (record.view === 'updated') return { message: null, block: false }
    if (record.view === 'unavailable')
      return {
        message:
          'El cambio se guardó localmente, pero no se pudo actualizar la vista. No repitas la acción; verifica el estado y el historial antes de continuar.',
        block: true,
      }
    return unknown()
  } catch {
    return unknown()
  }
}

export interface OrderTransitionState {
  readonly busy: boolean
  readonly feedback: OrderTransitionFeedback | null
}

/** Mounted-list exclusion only: no reconnect/reload or durable replay guarantee. */
export class OrderTransitionGate {
  private readonly entries = new Map<string, { token: object; state: OrderTransitionState }>()

  begin(orderId: string): object | null {
    if (this.entries.has(orderId)) return null
    const token = {}
    this.entries.set(orderId, { token, state: { busy: true, feedback: null } })
    return token
  }

  get(orderId: string): OrderTransitionState | undefined {
    return this.entries.get(orderId)?.state
  }

  finish(orderId: string, token: object, feedback: OrderTransitionFeedback): boolean {
    const entry = this.entries.get(orderId)
    if (!entry || entry.token !== token || !entry.state.busy) return false
    if (feedback.block) entry.state = { busy: false, feedback }
    else this.entries.delete(orderId)
    return true
  }
}

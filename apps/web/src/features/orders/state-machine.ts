import type { ServiceOrderState } from '../../local/service-order-types.js'

export type OrderAction =
  | 'start_diagnosis'
  | 'authorize'
  | 'reject'
  | 'start_work'
  | 'request_parts'
  | 'resume_work'
  | 'mark_ready'
  | 'close'
  | 'cancel'

/** Client mirror of the server-authoritative state machine. The server
 * remains the authority: an optimistic local transition carries the current
 * version as base_version and a stale mirror becomes a permanent conflict
 * (invalid_state_transition / base version mismatch) in the Conflict Center. */
export const ORDER_TRANSITIONS: Readonly<
  Record<OrderAction, Readonly<Partial<Record<ServiceOrderState, ServiceOrderState>>>>
> = {
  start_diagnosis: { INTAKE: 'DIAGNOSIS' },
  authorize: { DIAGNOSIS: 'AUTHORIZED' },
  reject: { DIAGNOSIS: 'REJECTED' },
  start_work: { AUTHORIZED: 'IN_PROGRESS' },
  request_parts: { IN_PROGRESS: 'WAITING_FOR_PARTS' },
  resume_work: { WAITING_FOR_PARTS: 'IN_PROGRESS' },
  mark_ready: { IN_PROGRESS: 'READY' },
  close: { READY: 'CLOSED' },
  cancel: {
    INTAKE: 'CANCELLED',
    DIAGNOSIS: 'CANCELLED',
    AUTHORIZED: 'CANCELLED',
    REJECTED: 'CANCELLED',
    IN_PROGRESS: 'CANCELLED',
    WAITING_FOR_PARTS: 'CANCELLED',
  },
}

export function legalTransition(
  state: ServiceOrderState,
  action: OrderAction,
): ServiceOrderState | null {
  return ORDER_TRANSITIONS[action]?.[state] ?? null
}

export function orderActionsFor(state: ServiceOrderState): OrderAction[] {
  return (Object.keys(ORDER_TRANSITIONS) as OrderAction[]).filter(
    (action) => ORDER_TRANSITIONS[action][state] !== undefined,
  )
}

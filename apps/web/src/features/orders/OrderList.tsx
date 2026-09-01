import type { LocalServiceOrder, LocalServiceOrderEvent } from '../../local/service-order-types.js'
import { ORDER_STATE_LABELS, TRANSITION_ACTION_LABELS } from './order-model.js'
import { orderActionsFor, type OrderAction } from './state-machine.js'

export interface OrderListProps {
  orders: readonly LocalServiceOrder[]
  events: readonly LocalServiceOrderEvent[]
  onTransition(order: LocalServiceOrder, action: OrderAction): Promise<void>
}

export function OrderList({ orders, events, onTransition }: OrderListProps) {
  if (orders.length === 0) {
    return (
      <p className="mt-4 rounded-xl border border-dashed border-[var(--ocwp-color-border)] p-4 text-sm text-[var(--ocwp-color-muted)]">
        Aún no hay órdenes de servicio registradas.
      </p>
    )
  }

  return (
    <ul className="mt-4 grid gap-3" aria-label="Órdenes de servicio">
      {orders.map((order) => {
        const actions = orderActionsFor(order.state)
        const timeline = events.filter((event) => event.order_id === order.order_id)
        return (
          <li
            key={order.order_id}
            className="rounded-xl border border-[var(--ocwp-color-border)] bg-white p-4"
            aria-label={`Orden ${order.reported_problem}`}
          >
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div className="grid gap-1">
                <strong>{order.reported_problem}</strong>
                <span className="text-sm text-[var(--ocwp-color-muted)]">
                  Prioridad {order.priority} · versión {order.version}
                  {order.bicycle_id ? ' · con bicicleta' : ''}
                </span>
              </div>
              <span className="rounded-full border border-[var(--ocwp-color-border)] px-3 py-1 text-sm font-semibold">
                {ORDER_STATE_LABELS[order.state] ?? order.state}
              </span>
            </div>
            {actions.length > 0 ? (
              <div className="mt-3 flex flex-wrap gap-2">
                {actions.map((action) => (
                  <button
                    key={action}
                    type="button"
                    onClick={() => void onTransition(order, action)}
                    className="min-h-11 rounded-[var(--ocwp-radius-sm)] border border-[var(--ocwp-color-border)] px-3 font-semibold focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--ocwp-color-accent)]"
                  >
                    {TRANSITION_ACTION_LABELS[action] ?? action}
                  </button>
                ))}
              </div>
            ) : (
              <p className="mt-3 text-sm text-[var(--ocwp-color-muted)]">
                Estado final: sin acciones disponibles.
              </p>
            )}
            {timeline.length > 0 ? (
              <details className="mt-3">
                <summary className="cursor-pointer text-sm font-medium">
                  Historial ({timeline.length})
                </summary>
                <ol className="mt-2 grid gap-1 text-sm text-[var(--ocwp-color-muted)]">
                  {timeline.map((event) => (
                    <li key={event.event_id}>
                      {TRANSITION_ACTION_LABELS[event.action] ?? event.action} ·{' '}
                      {ORDER_STATE_LABELS[event.from_state] ?? event.from_state} →{' '}
                      {ORDER_STATE_LABELS[event.to_state] ?? event.to_state}
                    </li>
                  ))}
                </ol>
              </details>
            ) : null}
          </li>
        )
      })}
    </ul>
  )
}

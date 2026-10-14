import { useState, type CSSProperties, type ChangeEvent } from 'react'
import type { LocalServiceOrder, LocalServiceOrderEvent } from '../../local/service-order-types.js'
import { ORDER_STATE_LABELS, TRANSITION_ACTION_LABELS } from './order-model.js'
import { orderActionsFor, type OrderAction } from './state-machine.js'

export interface OrderListProps {
  orders: readonly LocalServiceOrder[]
  events: readonly LocalServiceOrderEvent[]
  canTransition: boolean
  onTransition(order: LocalServiceOrder, action: OrderAction): Promise<void>
}

function OrderRecord({
  order,
  events,
  onTransition,
  canTransition,
}: {
  order: LocalServiceOrder
  events: readonly LocalServiceOrderEvent[]
  canTransition: boolean
  onTransition: OrderListProps['onTransition']
}) {
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const actions = canTransition ? orderActionsFor(order.state) : []
  const tone = ['READY', 'CLOSED'].includes(order.state)
    ? 'success'
    : order.state === 'WAITING_FOR_PARTS'
      ? 'warning'
      : ['CANCELLED', 'REJECTED'].includes(order.state)
        ? 'danger'
        : 'info'
  async function transition(action: OrderAction) {
    if (busy || !canTransition) return
    setBusy(true)
    setMessage(null)
    try {
      await onTransition(order, action)
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : 'No se pudo guardar el cambio. La orden sigue disponible.',
      )
    } finally {
      setBusy(false)
    }
  }
  return (
    <li className="order-card" aria-label={`Orden ${order.reported_problem}`}>
      <div className="order-summary">
        <small>Orden · {order.order_id.slice(-8)}</small>
        <strong>{order.reported_problem}</strong>
        <span className="muted">
          Prioridad {order.priority} · versión {order.version}
          {order.bicycle_id ? ' · con bicicleta' : ''}
        </span>
      </div>
      <div className="order-state">
        <span className="sr-only">Estado: </span>
        <span className="state-badge" data-tone={tone}>
          {ORDER_STATE_LABELS[order.state] ?? order.state}
        </span>
      </div>
      <div className="order-actions">
        {actions.length > 0 ? (
          actions.map((action) => (
            <button
              key={action}
              type="button"
              className="secondary-button"
              disabled={busy}
              onClick={() => void transition(action)}
            >
              {TRANSITION_ACTION_LABELS[action] ?? action}
            </button>
          ))
        ) : (
          <p className="muted">
            {canTransition
              ? 'Estado final: sin acciones disponibles.'
              : 'Solo lectura: tu sesión no permite cambiar órdenes.'}
          </p>
        )}
      </div>
      {events.length > 0 ? (
        <details className="order-history">
          <summary>Historial ({events.length})</summary>
          <ol>
            {events.map((event) => (
              <li key={event.event_id}>
                {TRANSITION_ACTION_LABELS[event.action] ?? event.action} ·{' '}
                {ORDER_STATE_LABELS[event.from_state] ?? event.from_state} →{' '}
                {ORDER_STATE_LABELS[event.to_state] ?? event.to_state}
              </li>
            ))}
          </ol>
        </details>
      ) : null}
      {message ? (
        <p role="alert" className="order-error">
          {message}
        </p>
      ) : null}
    </li>
  )
}

export function OrderList({ orders, events, onTransition, canTransition }: OrderListProps) {
  const [query, setQuery] = useState('')
  const filtered = orders.filter((order) =>
    `${order.reported_problem} ${order.order_id} ${ORDER_STATE_LABELS[order.state] ?? order.state}`
      .toLocaleLowerCase()
      .includes(query.trim().toLocaleLowerCase()),
  )
  return (
    <>
      <div className="order-tools">
        <label>
          Buscar órdenes
          <input
            type="search"
            value={query}
            onChange={(event: ChangeEvent<HTMLInputElement>) => setQuery(event.currentTarget.value)}
            placeholder="Problema, identificador o estado"
          />
        </label>
        <p className="muted" role="status">
          {query ? `${filtered.length} resultados locales` : 'Ordenadas por fecha de registro'}
        </p>
      </div>
      {orders.length === 0 ? (
        <p className="empty-state">Aún no hay órdenes de servicio registradas.</p>
      ) : filtered.length === 0 ? (
        <p className="empty-state">No hay órdenes que coincidan. Prueba otra búsqueda.</p>
      ) : (
        <>
          <div className="order-column-labels" aria-hidden="true">
            <span>Orden y prioridad</span>
            <span>Estado</span>
            <span>Acciones disponibles</span>
          </div>
          <ul
            className="order-list"
            aria-label="Órdenes de servicio"
            style={{ '--order-queue-rows': Math.max(1, filtered.length - 1) } as CSSProperties}
          >
            {filtered.map((order) => (
              <OrderRecord
                key={order.order_id}
                order={order}
                events={events.filter((event) => event.order_id === order.order_id)}
                onTransition={onTransition}
                canTransition={canTransition}
              />
            ))}
          </ul>
        </>
      )}
    </>
  )
}

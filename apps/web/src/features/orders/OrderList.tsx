import type { OrderAssociations } from './order-associations.js'
import { transitionNoteError } from './transition-note.js'
import { filterOrders } from './order-filter.js'
import {
  useId,
  useState,
  useRef,
  useLayoutEffect,
  type CSSProperties,
  type ChangeEvent,
} from 'react'
import type { LocalServiceOrder } from '../../local/service-order-types.js'
import { historyActorId, historyOccurrence, type OrderHistoryEvent } from './order-history.js'
import { ORDER_STATE_LABELS, TRANSITION_ACTION_LABELS } from './order-model.js'
import { orderActionsFor, type OrderAction } from './state-machine.js'
import type { OrderTransitionResult } from '../../runtime/order-transition-outcome.js'
import type { OrderTransitionState } from './transition-feedback.js'
import type { TransitionProtectionSnapshot } from '../../runtime/transition-protection.js'

export interface OrderListProps {
  orders: readonly LocalServiceOrder[]
  events: readonly OrderHistoryEvent[]
  canTransition: boolean
  protection: TransitionProtectionSnapshot
  canReadBicycleInfo: boolean
  canReadCustomerInfo?: boolean
  associations?: OrderAssociations | null
  onAssociations?(orderId: string): Promise<void>
  onCloseAssociations?(orderId: string): void
  onNote?(orderId: string, value: string): void
  onTimeline?(orderId: string): Promise<void>
  onTransition(order: LocalServiceOrder, action: OrderAction): Promise<OrderTransitionResult>
}

function OrderRecord({
  order,
  events,
  onTransition,
  canTransition,
  canReadBicycleInfo,
  canReadCustomerInfo,
  associations,
  onAssociations,
  onCloseAssociations,
  onTimeline,
  transitionState,
  transitionDisabled,
  note,
  onNote,
  noteCapacity,
}: {
  order: LocalServiceOrder
  events: readonly OrderHistoryEvent[]
  canTransition: boolean
  canReadBicycleInfo: boolean
  canReadCustomerInfo: boolean
  associations: OrderListProps['associations']
  onAssociations: OrderListProps['onAssociations']
  onCloseAssociations: OrderListProps['onCloseAssociations']
  onTransition(order: LocalServiceOrder, action: OrderAction): Promise<void>
  onTimeline: OrderListProps['onTimeline']
  transitionState: OrderTransitionState | undefined
  transitionDisabled: boolean
  note: string
  onNote: OrderListProps['onNote']
  noteCapacity: boolean
}) {
  const noteId = useId()
  const associationsId = `${noteId}-associations`
  const associationTrigger = useRef<HTMLButtonElement>(null)
  const returnAssociationFocus = useRef(false)
  useLayoutEffect(() => {
    if (!returnAssociationFocus.current) return
    returnAssociationFocus.current = false
    if (
      associations === null &&
      (canReadCustomerInfo || canReadBicycleInfo) &&
      associationTrigger.current &&
      !associationTrigger.current.disabled
    ) {
      associationTrigger.current.focus()
    }
  }, [associations, canReadCustomerInfo, canReadBicycleInfo])
  const noteError = transitionNoteError(note)
  const [historyMessage, setHistoryMessage] = useState<string | null>(null)
  const message = transitionState?.feedback?.message ?? historyMessage
  const actions = canTransition ? orderActionsFor(order.state) : []
  const tone = ['READY', 'CLOSED'].includes(order.state)
    ? 'success'
    : order.state === 'WAITING_FOR_PARTS'
      ? 'warning'
      : ['CANCELLED', 'REJECTED'].includes(order.state)
        ? 'danger'
        : 'info'
  return (
    <li className="order-card" aria-label={`Orden ${order.reported_problem}`}>
      <div className="order-summary">
        <small>Orden · {order.order_id.slice(-8)}</small>
        <strong>{order.reported_problem}</strong>
        <span className="muted">
          Prioridad {order.priority} · versión {order.version}
          {canReadBicycleInfo && order.bicycle_id ? ' · con bicicleta' : ''}
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
              disabled={transitionState !== undefined || transitionDisabled || noteError !== null}
              onClick={() => void onTransition(order, action)}
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
      {onAssociations && (canReadCustomerInfo || canReadBicycleInfo) ? (
        <div className="order-associations">
          <button
            type="button"
            className="secondary-button"
            aria-expanded={associations?.orderId === order.order_id}
            aria-controls={associationsId}
            ref={associationTrigger}
            disabled={associations?.status === 'loading'}
            onClick={() => {
              void onAssociations(order.order_id).catch(() => {
                /* The host owns the generic failure snapshot; never echo raw errors. */
              })
            }}
          >
            Ver cliente y bicicleta
          </button>
          <div id={associationsId} hidden={associations?.orderId !== order.order_id}>
            {associations?.orderId === order.order_id && onCloseAssociations ? (
              <button
                type="button"
                className="secondary-button"
                onClick={() => {
                  returnAssociationFocus.current = true
                  onCloseAssociations(order.order_id)
                }}
              >
                Cerrar datos de cliente y bicicleta
              </button>
            ) : null}
            {associations?.orderId === order.order_id ? (
              associations.status === 'loading' ? (
                <p role="status">Cargando cliente y bicicleta locales.</p>
              ) : associations.status === 'failed' ? (
                <p role="alert">
                  No se pudo cargar el cliente y la bicicleta locales. Vuelve a intentarlo.
                </p>
              ) : associations.status === 'ready' ? (
                <>
                  <p>Instantánea local: no confirma el estado actual del servidor.</p>
                  <dl>
                    <dt>Cliente de la orden</dt>
                    <dd>
                      {!canReadCustomerInfo || associations.customer.status === 'restricted' ? (
                        'Cliente: acceso restringido'
                      ) : associations.customer.status === 'available' ? (
                        <>
                          <bdi dir="auto">{associations.customer.name}</bdi>
                          <br />
                          ID: <bdi dir="auto">{associations.customer.id}</bdi>
                        </>
                      ) : (
                        'Cliente no disponible localmente'
                      )}
                    </dd>
                    <dt>Bicicleta de la orden</dt>
                    <dd>
                      {!canReadBicycleInfo || associations.bicycle.status === 'restricted' ? (
                        'Bicicleta: acceso restringido'
                      ) : associations.bicycle.status === 'available' ? (
                        <>
                          <bdi dir="auto">{associations.bicycle.brand}</bdi>
                          <br />
                          {associations.bicycle.model?.trim() ? (
                            <bdi dir="auto">{associations.bicycle.model}</bdi>
                          ) : (
                            'Modelo no registrado'
                          )}
                          <br />
                          ID: <bdi dir="auto">{associations.bicycle.id}</bdi>
                        </>
                      ) : associations.bicycle.status === 'none' ? (
                        'Sin bicicleta asociada en esta instantánea local'
                      ) : (
                        'Bicicleta no disponible localmente'
                      )}
                    </dd>
                  </dl>
                </>
              ) : null
            ) : null}
          </div>
        </div>
      ) : null}
      {canTransition && onNote && (actions.length > 0 || note !== '') ? (
        <div className="order-transition-note">
          <label htmlFor={noteId}>
            {actions.length
              ? 'Nota para el próximo cambio (opcional)'
              : 'Nota sin enviar (orden final)'}
          </label>
          <textarea
            id={noteId}
            rows={2}
            maxLength={4000}
            value={note}
            disabled={transitionState !== undefined || transitionDisabled || noteCapacity}
            aria-invalid={noteError !== null}
            aria-describedby={`${noteId}-help ${noteId}-error`}
            onChange={(event: ChangeEvent<HTMLTextAreaElement>) =>
              onNote(order.order_id, event.currentTarget.value)
            }
          />
          <p id={`${noteId}-help`}>
            La nota acompaña al próximo cambio y se muestra en su historial. Máximo 2000 caracteres.
            Las notas sin enviar se pierden al recargar. Puedes borrar el texto para descartarlo.
            {noteCapacity ? ' Ya hay 50 notas sin enviar; borra una antes de añadir otra.' : ''}
          </p>
          <p id={`${noteId}-error`} role="status">
            {noteError}
          </p>
        </div>
      ) : null}
      <details className="order-intake-details">
        <summary>Datos de recepción</summary>
        <dl>
          <dt>Condición al recibir</dt>
          <dd dir="auto">
            {order.intake_condition?.trim() ? order.intake_condition : 'No registrada'}
          </dd>
          <dt>Accesorios</dt>
          <dd dir="auto">{order.accessories?.trim() ? order.accessories : 'No registrados'}</dd>
        </dl>
      </details>
      {onTimeline ? (
        <button
          type="button"
          className="secondary-button"
          onClick={() => {
            void onTimeline(order.order_id).catch(() =>
              setHistoryMessage('No se pudo cargar el historial local.'),
            )
          }}
        >
          Ver historial
        </button>
      ) : null}
      {events.length > 0 ? (
        <details className="order-history">
          <summary>Historial ({events.length})</summary>
          <p>
            El registro local no implica aceptación del servidor; puede incluir intentos rechazados
            o en conflicto.
          </p>
          <ol>
            {events.map((event) => {
              const occurredAt = historyOccurrence(event.occurred_at)
              return (
                <li key={event.event_id}>
                  {TRANSITION_ACTION_LABELS[event.action] ?? event.action} ·{' '}
                  {ORDER_STATE_LABELS[event.from_state] ?? event.from_state} →{' '}
                  {ORDER_STATE_LABELS[event.to_state] ?? event.to_state}
                  {event.note ? (
                    <div className="order-history-note">
                      Nota del cambio: <span dir="auto">{event.note}</span>
                    </div>
                  ) : null}
                  <div className="order-history-metadata">
                    <span>
                      Autor (ID): <bdi dir="auto">{historyActorId(event.actor_id)}</bdi>
                    </span>
                    <span>
                      Fecha registrada:{' '}
                      {occurredAt ? (
                        <time dateTime={occurredAt}>{occurredAt}</time>
                      ) : (
                        'No disponible o sin zona horaria verificable'
                      )}
                    </span>
                    <span>
                      {event.recordSource === 'local'
                        ? 'Registro local'
                        : event.recordSource === 'server'
                          ? 'Registro del servidor'
                          : 'Origen no disponible'}
                    </span>
                  </div>
                </li>
              )
            })}
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

export function OrderList({
  orders,
  events,
  onTransition,
  canTransition,
  canReadBicycleInfo,
  canReadCustomerInfo,
  associations,
  onAssociations,
  onCloseAssociations,
  onTimeline,
  onNote,
  protection,
}: OrderListProps) {
  const [query, setQuery] = useState('')
  const [state, setState] = useState('')
  const [priority, setPriority] = useState('')
  const hasFilters = Boolean(query.trim() || state || priority)
  async function transition(order: LocalServiceOrder, action: OrderAction) {
    if (!canTransition || protection.notice || protection.states.has(order.order_id)) return
    // Admission and outcome ownership live in the host, not this replaceable view.
    try {
      await onTransition(order, action)
    } catch {
      /* Never echo arbitrary errors. */
    }
  }
  const filtered = filterOrders(orders, { query, state, priority })
  return (
    <>
      {protection.notice ? (
        <p role="alert" className="order-error">
          {protection.notice}
        </p>
      ) : null}
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
        <label>
          Estado de la orden
          <select
            value={state}
            onChange={(event: ChangeEvent<HTMLSelectElement>) =>
              setState(event.currentTarget.value)
            }
          >
            <option value="">Todos los estados</option>
            {Object.entries(ORDER_STATE_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Prioridad de la orden
          <select
            value={priority}
            onChange={(event: ChangeEvent<HTMLSelectElement>) =>
              setPriority(event.currentTarget.value)
            }
          >
            <option value="">Todas las prioridades</option>
            <option value="low">Baja</option>
            <option value="normal">Normal</option>
            <option value="high">Alta</option>
            <option value="urgent">Urgente</option>
          </select>
        </label>
        <button
          type="button"
          className="secondary-button"
          disabled={!hasFilters}
          onClick={() => {
            setQuery('')
            setState('')
            setPriority('')
          }}
        >
          Limpiar filtros
        </button>
        <p className="muted" role="status">
          {hasFilters ? `${filtered.length} resultados locales` : 'Ordenadas por fecha de registro'}
        </p>
      </div>
      {orders.length === 0 ? (
        <p className="empty-state">Aún no hay órdenes de servicio registradas.</p>
      ) : filtered.length === 0 ? (
        <p className="empty-state">No hay órdenes que coincidan. Cambia o limpia los filtros.</p>
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
                onTransition={transition}
                transitionState={protection.states.get(order.order_id)}
                transitionDisabled={protection.notice !== null}
                canTransition={canTransition}
                canReadBicycleInfo={canReadBicycleInfo}
                canReadCustomerInfo={canReadCustomerInfo ?? false}
                associations={associations}
                onAssociations={onAssociations}
                onCloseAssociations={onCloseAssociations}
                onTimeline={onTimeline}
                onNote={onNote}
                note={protection.notes?.get(order.order_id) ?? ''}
                noteCapacity={
                  !!protection.notes &&
                  protection.notes.size >= 50 &&
                  !protection.notes.has(order.order_id)
                }
              />
            ))}
          </ul>
        </>
      )}
    </>
  )
}

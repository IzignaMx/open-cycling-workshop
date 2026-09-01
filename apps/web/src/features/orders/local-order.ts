import type { LocalServiceOrder, LocalServiceOrderEvent } from '../../local/service-order-types.js'
import type { QueuedMutation } from '../../local/types.js'
import { legalTransition, type OrderAction } from './state-machine.js'

export interface CreateServiceOrderInput {
  organizationId: string
  locationId: string
  customerId: string
  bicycleId?: string | null
  reportedProblem: string
  intakeCondition?: string | null
  accessories?: string | null
  priority?: string
}

export interface LocalDependencies {
  now(): string
  newId(): string
}

export interface LocalOrderCreateResult {
  order: LocalServiceOrder
  mutation: QueuedMutation
}

export interface LocalOrderTransitionDependencies extends LocalDependencies {
  actorId: string
}

export interface LocalOrderTransitionResult {
  order: LocalServiceOrder
  event: LocalServiceOrderEvent
  mutation: QueuedMutation
}

function collapse(value: string): string {
  return value.trim().replace(/\s+/g, ' ')
}

export function buildLocalOrderCreate(
  input: CreateServiceOrderInput,
  dependencies: LocalDependencies,
): LocalOrderCreateResult {
  const reportedProblem = collapse(input.reportedProblem)
  if (!reportedProblem) throw new Error('El problema reportado es obligatorio')
  const now = dependencies.now()
  const orderId = dependencies.newId()
  const order: LocalServiceOrder = {
    order_id: orderId,
    customer_id: input.customerId,
    bicycle_id: input.bicycleId?.trim() || null,
    organization_id: input.organizationId,
    location_id: input.locationId,
    state: 'INTAKE',
    reported_problem: reportedProblem,
    intake_condition: input.intakeCondition?.trim() || null,
    accessories: input.accessories?.trim() || null,
    priority: input.priority?.trim() || 'normal',
    diagnosis: null,
    created_at: now,
    updated_at: now,
    version: 1,
  }
  const mutation: QueuedMutation = {
    mutation_id: dependencies.newId(),
    entity_type: 'service_order',
    entity_id: orderId,
    operation: 'create',
    organization_id: input.organizationId,
    location_id: input.locationId,
    base_version: null,
    occurred_at: now,
    payload: {
      customer_id: input.customerId,
      bicycle_id: order.bicycle_id,
      reported_problem: reportedProblem,
      intake_condition: order.intake_condition,
      accessories: order.accessories,
      priority: order.priority,
    },
    state: 'pending',
    queued_at: now,
  }
  return { order, mutation }
}

export function buildLocalOrderTransition(
  order: LocalServiceOrder,
  action: OrderAction,
  dependencies: LocalOrderTransitionDependencies,
  note?: string | null,
): LocalOrderTransitionResult {
  const target = legalTransition(order.state, action)
  if (target === null) {
    throw new Error(`Acción inválida: ${action} no es posible desde ${order.state}`)
  }
  const now = dependencies.now()
  const normalizedNote = note?.trim() || null
  const nextOrder: LocalServiceOrder = {
    ...order,
    state: target,
    updated_at: now,
    version: order.version + 1,
  }
  const event: LocalServiceOrderEvent = {
    event_id: dependencies.newId(),
    order_id: order.order_id,
    organization_id: order.organization_id,
    from_state: order.state,
    to_state: target,
    action,
    actor_id: dependencies.actorId,
    note: normalizedNote,
    occurred_at: now,
  }
  const mutation: QueuedMutation = {
    mutation_id: dependencies.newId(),
    entity_type: 'service_order',
    entity_id: order.order_id,
    operation: 'update',
    organization_id: order.organization_id,
    location_id: order.location_id,
    base_version: order.version,
    occurred_at: now,
    payload: {
      transition: {
        action,
        actor_id: dependencies.actorId,
        note: normalizedNote,
      },
    },
    state: 'pending',
    queued_at: now,
  }
  return { order: nextOrder, event, mutation }
}

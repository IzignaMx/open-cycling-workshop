import type { AccessKernel } from '../access-kernel/kernel.js'
import type { BaselineSession } from '../access-kernel/baseline-coordinator.js'
import type { LocalCommand } from '../access-kernel/types.js'
import type { EntityType, MutationEnvelope } from '../sync/types.js'
import type { LocalCustomer, QueuedMutation } from '../local/types.js'
import type { LocalServiceOrder, LocalServiceOrderEvent } from '../local/service-order-types.js'
import {
  buildLocalCustomerCreate,
  type CreateCustomerInput,
} from '../features/customers/local-customer.js'
import { buildLocalBicycleCreate } from '../features/bicycles/local-bicycle.js'
import { buildLocalOrderCreate, buildLocalOrderTransition } from '../features/orders/local-order.js'
import type { OrderAction } from '../features/orders/state-machine.js'
import { newUuidV7 } from '../shared/ids.js'

/** Strip delivery fields from the old pure builders. Wire authority comes only from the ticket. */
export function wireEnvelope(value: QueuedMutation): MutationEnvelope {
  const {
    mutation_id,
    entity_type,
    entity_id,
    operation,
    organization_id,
    location_id,
    base_version,
    occurred_at,
    payload,
  } = value
  return {
    mutation_id,
    entity_type,
    entity_id,
    operation,
    organization_id,
    location_id,
    base_version,
    occurred_at,
    payload: structuredClone(payload),
  }
}
export interface IntakeInput {
  customerId: string
  reportedProblem: string
  intakeCondition: string | null
  accessories: string | null
  priority: string
  brand: string | null
  model: string | null
}
export class WorkshopRepositories {
  constructor(
    private readonly kernel: AccessKernel,
    private readonly now: () => number = Date.now,
    private readonly newId: () => string = newUuidV7,
  ) {}
  private capture(source: BaselineSession) {
    const ticket = structuredClone(source.ticket),
      context = structuredClone(source.context),
      identity = structuredClone(source.identity),
      check = source.isCurrent
    const current = () => check(identity)
    if (!current()) throw new Error('La sesión cambió. Vuelve a abrir el taller.')
    return {
      ticket,
      context,
      current,
      scope: {
        organizationId: context.principal.organizationId,
        locationId: context.selectedLocationId,
      },
      dependencies: { now: () => new Date(this.now()).toISOString(), newId: this.newId },
    }
  }
  async createCustomer(
    source: BaselineSession,
    input: Omit<CreateCustomerInput, 'organizationId' | 'locationId'>,
  ): Promise<LocalCustomer> {
    const captured = this.capture(source),
      { customer, mutation } = buildLocalCustomerCreate(
        { ...input, ...captured.scope },
        captured.dependencies,
      )
    await this.kernel.commitLocalCommands(
      captured.ticket,
      [
        {
          envelope: wireEnvelope(mutation),
          optimistic: { ...customer },
          dependsOn: [],
          localEvents: [],
        },
      ],
      captured.current,
    )
    return customer
  }
  async createOrder(source: BaselineSession, input: IntakeInput): Promise<LocalServiceOrder> {
    const captured = this.capture(source),
      commands: LocalCommand[] = []
    let bicycleId: string | null = null
    if (input.brand) {
      const { bicycle, mutation } = buildLocalBicycleCreate(
        { ...captured.scope, customerId: input.customerId, brand: input.brand, model: input.model },
        captured.dependencies,
      )
      bicycleId = bicycle.bicycle_id
      commands.push({
        envelope: wireEnvelope(mutation),
        optimistic: { ...bicycle },
        dependsOn: [],
        localEvents: [],
      })
    }
    const { order, mutation } = buildLocalOrderCreate(
      {
        ...captured.scope,
        customerId: input.customerId,
        bicycleId,
        reportedProblem: input.reportedProblem,
        intakeCondition: input.intakeCondition,
        accessories: input.accessories,
        priority: input.priority,
      },
      captured.dependencies,
    )
    commands.push({
      envelope: wireEnvelope(mutation),
      optimistic: { ...order },
      dependsOn: commands.map((c) => c.envelope.mutation_id),
      localEvents: [],
    })
    await this.kernel.commitLocalCommands(captured.ticket, commands, captured.current)
    return order
  }
  async transition(
    source: BaselineSession,
    orderId: string,
    action: OrderAction,
  ): Promise<LocalServiceOrder> {
    const c = this.capture(source),
      projection = await this.kernel.readEntity(c.ticket, 'service_order', orderId, c.current)
    const row = projection?.optimistic ?? projection?.confirmed
    if (!row) throw new Error('La orden no está disponible en este taller.')
    const result = buildLocalOrderTransition(row as unknown as LocalServiceOrder, action, {
      ...c.dependencies,
      actorId: c.context.principal.userId,
    })
    await this.kernel.commitLocalCommands(
      c.ticket,
      [
        {
          envelope: wireEnvelope(result.mutation),
          optimistic: { ...result.order },
          dependsOn: [],
          localEvents: [{ ...result.event }],
        },
      ],
      c.current,
    )
    return result.order
  }
  async page(source: BaselineSession, type: EntityType, afterId?: string) {
    const c = this.capture(source)
    return this.kernel.listEntities(
      c.ticket,
      type,
      { limit: 50, ...(afterId ? { afterId } : {}) },
      c.current,
    )
  }
  async issues(source: BaselineSession, afterSequence?: number) {
    const c = this.capture(source)
    return this.kernel.listOperations(
      c.ticket,
      { limit: 50, ...(afterSequence === undefined ? {} : { afterSequence }) },
      c.current,
    )
  }
  async localTimeline(
    source: BaselineSession,
    orderId: string,
  ): Promise<{ events: LocalServiceOrderEvent[]; partial: boolean }> {
    const c = this.capture(source),
      history = await this.kernel.listOperationHistory(
        c.ticket,
        'service_order',
        orderId,
        { limit: 50 },
        c.current,
      )
    const events: LocalServiceOrderEvent[] = []
    let partial = history.nextAfterSequence !== null
    for (const { operation } of history.items) {
      const page = await this.kernel.listOperationEvents(
        c.ticket,
        operation.mutationId,
        { limit: 50 },
        c.current,
      )
      partial ||= page.nextAfterSequence !== null
      for (const event of page.items) {
        if (
          event.kind === 'local' &&
          event.details.order_id === orderId &&
          event.details.organization_id === c.context.principal.organizationId
        )
          events.push(event.details as unknown as LocalServiceOrderEvent)
      }
    }
    return { events, partial }
  }
}

import type { OcwpDatabase } from '../../local/db.js'
import type { LocalServiceOrder } from '../../local/service-order-types.js'
import { newUuidV7 } from '../../shared/ids.js'
import type { OrderAction } from './state-machine.js'
import {
  buildLocalOrderCreate,
  buildLocalOrderTransition,
  type CreateServiceOrderInput,
} from './local-order.js'

export type { CreateServiceOrderInput } from './local-order.js'
export type { OrderAction } from './state-machine.js'

export interface ApplyTransitionOptions {
  actorId: string
  note?: string | null
}

export class ServiceOrderLocalRepository {
  constructor(private readonly database: OcwpDatabase) {}

  async create(input: CreateServiceOrderInput): Promise<LocalServiceOrder> {
    const { order, mutation } = buildLocalOrderCreate(input, {
      now: () => new Date().toISOString(),
      newId: newUuidV7,
    })
    await this.database.transaction(
      'rw',
      this.database.serviceOrders,
      this.database.mutationQueue,
      async () => {
        await this.database.serviceOrders.put(order)
        await this.database.mutationQueue.put(mutation)
      },
    )
    return order
  }

  async applyTransition(
    order: LocalServiceOrder,
    action: OrderAction,
    options: ApplyTransitionOptions,
  ): Promise<LocalServiceOrder> {
    // Build first so an illegal transition never writes anything.
    const {
      order: nextOrder,
      event,
      mutation,
    } = buildLocalOrderTransition(
      order,
      action,
      {
        now: () => new Date().toISOString(),
        newId: newUuidV7,
        actorId: options.actorId,
      },
      options.note,
    )
    await this.database.transaction(
      'rw',
      this.database.serviceOrders,
      this.database.serviceOrderEvents,
      this.database.mutationQueue,
      async () => {
        await this.database.serviceOrders.put(nextOrder)
        await this.database.serviceOrderEvents.put(event)
        await this.database.mutationQueue.put(mutation)
      },
    )
    return nextOrder
  }
}

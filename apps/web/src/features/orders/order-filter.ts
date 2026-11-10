import type { LocalServiceOrder } from '../../local/service-order-types.js'
import { ORDER_STATE_LABELS } from './order-model.js'

export interface OrderFilters {
  query: string
  state: string
  priority: string
}

export function filterOrders(orders: readonly LocalServiceOrder[], filters: OrderFilters) {
  const query = filters.query.trim().toLocaleLowerCase()
  return orders.filter(
    (order) =>
      (!filters.state || order.state === filters.state) &&
      (!filters.priority || order.priority === filters.priority) &&
      `${order.reported_problem} ${order.order_id} ${ORDER_STATE_LABELS[order.state] ?? order.state}`
        .toLocaleLowerCase()
        .includes(query),
  )
}

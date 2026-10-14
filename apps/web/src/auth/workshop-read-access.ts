import type { ConflictRecord } from '../local/types.js'
import { hasCapability } from './capabilities.js'

/** Presentation boundary only: does not revoke cached data or revalidate offline permissions. */
export function workshopReadAccess(capabilities: readonly string[]) {
  return {
    customers: hasCapability(capabilities, 'customers.read'),
    bicycles: hasCapability(capabilities, 'bicycles.read'),
    orders: hasCapability(capabilities, 'orders.read'),
  }
}

/** Unknown entity types stay hidden until their read contract is explicitly defined. */
export function canReadCachedEntity(capabilities: readonly string[], entityType: string): boolean {
  switch (entityType) {
    case 'customer':
      return hasCapability(capabilities, 'customers.read')
    case 'bicycle':
      return hasCapability(capabilities, 'bicycles.read')
    case 'service_order':
      return hasCapability(capabilities, 'orders.read')
    default:
      return false
  }
}

/** Legacy rows were labelled customer irrespective of their source. Retain but never expose them. */
export function canReadConflict(
  capabilities: readonly string[],
  conflict: Pick<ConflictRecord, 'entity_type' | 'entity_type_source'>,
): boolean {
  return (
    conflict.entity_type_source === 'queued_mutation' &&
    canReadCachedEntity(capabilities, conflict.entity_type)
  )
}

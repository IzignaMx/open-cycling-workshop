import type { OcwpDatabase } from '../local/db.js'
import type { LocalBicycle } from '../local/bicycle-types.js'
import type { LocalServiceOrder } from '../local/service-order-types.js'
import type { LocalCustomer, SyncStateRecord } from '../local/types.js'
import { buildScopedConflict, syncScopeKey, type SyncScope } from './scope.js'
import type { ChangeItem, ConflictMutationResult, MutationEnvelope, SyncStore } from './types.js'

function customerFromChange(item: ChangeItem, scope: SyncScope): LocalCustomer | null {
  if (item.entity_type !== 'customer' || !item.payload) return null
  if (item.organization_id !== scope.organizationId || item.location_id !== scope.locationId) {
    throw new Error(`sync change scope mismatch for cursor ${item.cursor}`)
  }
  const payload = item.payload
  if (
    typeof payload.customer_id !== 'string' ||
    typeof payload.organization_id !== 'string' ||
    typeof payload.location_id !== 'string' ||
    typeof payload.display_name !== 'string' ||
    typeof payload.created_at !== 'string' ||
    typeof payload.updated_at !== 'string' ||
    typeof payload.version !== 'number'
  ) {
    throw new Error(`invalid customer change payload for cursor ${item.cursor}`)
  }
  if (
    payload.organization_id !== scope.organizationId ||
    payload.location_id !== scope.locationId
  ) {
    throw new Error(`customer payload scope mismatch for cursor ${item.cursor}`)
  }
  return {
    customer_id: payload.customer_id,
    organization_id: payload.organization_id,
    location_id: payload.location_id,
    display_name: payload.display_name,
    email: typeof payload.email === 'string' ? payload.email : null,
    phone: typeof payload.phone === 'string' ? payload.phone : null,
    created_at: payload.created_at,
    updated_at: payload.updated_at,
    version: payload.version,
  }
}

function requireScope(item: ChangeItem, scope: SyncScope, kind: string): Record<string, unknown> {
  if (item.organization_id !== scope.organizationId || item.location_id !== scope.locationId) {
    throw new Error(`sync change scope mismatch for cursor ${item.cursor}`)
  }
  if (!item.payload) {
    throw new Error(`invalid ${kind} change payload for cursor ${item.cursor}`)
  }
  return item.payload
}

function bicycleFromChange(item: ChangeItem, scope: SyncScope): LocalBicycle | null {
  if (item.entity_type !== 'bicycle') return null
  const payload = requireScope(item, scope, 'bicycle') as Record<string, unknown>
  if (
    typeof payload.bicycle_id !== 'string' ||
    typeof payload.customer_id !== 'string' ||
    typeof payload.brand !== 'string' ||
    typeof payload.created_at !== 'string' ||
    typeof payload.updated_at !== 'string' ||
    typeof payload.version !== 'number'
  ) {
    throw new Error(`invalid bicycle change payload for cursor ${item.cursor}`)
  }
  return {
    bicycle_id: payload.bicycle_id,
    customer_id: payload.customer_id,
    organization_id: scope.organizationId,
    location_id: scope.locationId,
    brand: payload.brand,
    model: (payload.model as string | null) ?? null,
    bicycle_type: (payload.bicycle_type as string | null) ?? null,
    wheel_size: (payload.wheel_size as string | null) ?? null,
    notes: (payload.notes as string | null) ?? null,
    created_at: payload.created_at,
    updated_at: payload.updated_at,
    version: payload.version,
  }
}

function serviceOrderFromChange(item: ChangeItem, scope: SyncScope): LocalServiceOrder | null {
  if (item.entity_type !== 'service_order') return null
  const payload = requireScope(item, scope, 'service order') as Record<string, unknown>
  if (
    typeof payload.order_id !== 'string' ||
    typeof payload.customer_id !== 'string' ||
    typeof payload.state !== 'string' ||
    typeof payload.reported_problem !== 'string' ||
    typeof payload.created_at !== 'string' ||
    typeof payload.updated_at !== 'string' ||
    typeof payload.version !== 'number'
  ) {
    throw new Error(`invalid service order change payload for cursor ${item.cursor}`)
  }
  return {
    order_id: payload.order_id,
    customer_id: payload.customer_id,
    bicycle_id: (payload.bicycle_id as string | null) ?? null,
    organization_id: scope.organizationId,
    location_id: scope.locationId,
    state: payload.state as LocalServiceOrder['state'],
    reported_problem: payload.reported_problem,
    intake_condition: (payload.intake_condition as string | null) ?? null,
    accessories: (payload.accessories as string | null) ?? null,
    priority: (payload.priority as string) ?? 'normal',
    diagnosis: (payload.diagnosis as string | null) ?? null,
    created_at: payload.created_at,
    updated_at: payload.updated_at,
    version: payload.version,
  }
}

export class DexieSyncStore implements SyncStore {
  readonly #scope: SyncScope
  readonly #scopeKey: string

  constructor(
    private readonly database: OcwpDatabase,
    scope: SyncScope,
  ) {
    this.#scope = scope
    this.#scopeKey = syncScopeKey(scope.organizationId, scope.locationId)
  }

  async listPending(limit: number): Promise<MutationEnvelope[]> {
    const organizationQueue = await this.database.mutationQueue
      .where('organization_id')
      .equals(this.#scope.organizationId)
      .toArray()
    return organizationQueue
      .filter((item) => item.state === 'pending' && item.location_id === this.#scope.locationId)
      .slice(0, limit)
      .map(({ state: _state, queued_at: _queuedAt, ...mutation }) => mutation)
  }

  async markAcknowledged(mutationIds: string[]): Promise<void> {
    await this.database.mutationQueue.bulkDelete(mutationIds)
  }

  async recordConflicts(results: ConflictMutationResult[]): Promise<void> {
    const recordedAt = new Date().toISOString()
    await this.database.transaction(
      'rw',
      this.database.mutationQueue,
      this.database.conflicts,
      async () => {
        for (const result of results) {
          await this.database.conflicts.put(buildScopedConflict(this.#scope, result, recordedAt))
        }
        await this.database.mutationQueue.bulkDelete(results.map((result) => result.mutation_id))
      },
    )
  }

  async getCursor(): Promise<number> {
    return (await this.database.syncState.get(`cursor:${this.#scopeKey}`))?.cursor ?? 0
  }

  async mergeAndAdvance(items: ChangeItem[], nextCursor: number): Promise<void> {
    await this.database.transaction(
      'rw',
      this.database.customers,
      this.database.bicycles,
      this.database.serviceOrders,
      this.database.syncState,
      async () => {
        for (const item of items) {
          const customer = customerFromChange(item, this.#scope)
          if (customer) {
            await this.database.customers.put(customer)
            continue
          }
          const bicycle = bicycleFromChange(item, this.#scope)
          if (bicycle) {
            await this.database.bicycles.put(bicycle)
            continue
          }
          const order = serviceOrderFromChange(item, this.#scope)
          if (order) await this.database.serviceOrders.put(order)
        }
        const state: SyncStateRecord = {
          key: `cursor:${this.#scopeKey}`,
          scope_key: this.#scopeKey,
          organization_id: this.#scope.organizationId,
          location_id: this.#scope.locationId,
          cursor: nextCursor,
          updated_at: new Date().toISOString(),
        }
        await this.database.syncState.put(state)
      },
    )
  }
}

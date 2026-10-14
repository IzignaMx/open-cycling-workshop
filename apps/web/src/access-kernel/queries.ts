import type { EntityType } from '../sync/types.js'
import type { KernelDatabase } from './database.js'
import { entityCapability, requireCapability } from './operations.js'
import { readProjection } from './projection.js'
import type { ContextTicket, VerifiedAccessContext } from './types.js'

export interface EntityPageOptions {
  limit: number
  afterId?: string
}
export interface HistoryPageOptions {
  limit: number
  afterSequence?: number
}
function limit(value: number): void {
  if (!Number.isSafeInteger(value) || value < 1 || value > 100)
    throw new Error('Invalid query page limit')
}
function after(value: number | undefined): number {
  if (value !== undefined && (!Number.isSafeInteger(value) || value < 0))
    throw new Error('Invalid history cursor')
  return value ?? 0
}
/** Enumerate bounded unique index keys, never every user's immutable journal. */
export async function entityPage(
  db: KernelDatabase,
  ticket: ContextTicket,
  context: VerifiedAccessContext,
  entityType: EntityType,
  options: EntityPageOptions,
) {
  limit(options.limit)
  requireCapability(context, entityCapability(entityType, 'read'))
  if (
    options.afterId !== undefined &&
    (typeof options.afterId !== 'string' || !options.afterId || options.afterId.length > 512)
  )
    throw new Error('Invalid entity cursor')
  const low = options.afterId ?? ''
  const [cache, owned] = await Promise.all([
    db.cacheRecords
      .where('[partitionId+entityType+entityId]')
      .between(
        [ticket.partitionId, entityType, low],
        [ticket.partitionId, entityType, []],
        false,
        false,
      )
      .limit(options.limit + 1)
      .keys(),
    db.operationJournal
      .where('[principalKey+locationId+entityType+entityId]')
      .between(
        [ticket.principalKey, context.selectedLocationId, entityType, low],
        [ticket.principalKey, context.selectedLocationId, entityType, []],
        false,
        false,
      )
      .limit(options.limit + 1)
      .uniqueKeys(),
  ])
  const id = (key: unknown) => (key as string[]).at(-1)!
  const keys = [...new Set([...cache.map(id), ...owned.map(id)])].sort()
  const selected = keys.slice(0, options.limit)
  const items = []
  for (const entityId of selected) {
    const projection = await readProjection(db, ticket, context, entityType, entityId)
    if (projection) items.push({ entityId, ...projection })
  }
  return { items, nextAfterId: keys.length > options.limit ? selected.at(-1)! : null }
}

export async function operationPage(
  db: KernelDatabase,
  ticket: ContextTicket,
  context: VerifiedAccessContext,
  options: HistoryPageOptions,
  entity?: { entityType: EntityType; entityId: string },
) {
  limit(options.limit)
  const cursor = after(options.afterSequence)
  if (entity) requireCapability(context, entityCapability(entity.entityType, 'read'))
  const prefix = entity
    ? [ticket.principalKey, context.selectedLocationId, entity.entityType, entity.entityId]
    : [ticket.principalKey, context.selectedLocationId]
  const index = entity
    ? '[principalKey+locationId+entityType+entityId+localSequence]'
    : '[principalKey+locationId+localSequence]'
  const page = await db.operationJournal
    .where(index)
    .between([...prefix, cursor], [...prefix, Number.MAX_SAFE_INTEGER], false, true)
    .limit(options.limit + 1)
    .toArray()
  const selected = page.slice(0, options.limit)
  const items = []
  for (const operation of selected) {
    if (!context.capabilities.includes(entityCapability(operation.entityType, 'read'))) continue
    items.push({ operation, delivery: await db.operationDelivery.get(operation.mutationId) })
  }
  return {
    items,
    nextAfterSequence: page.length > options.limit ? selected.at(-1)!.localSequence : null,
  }
}

export async function eventPage(
  db: KernelDatabase,
  mutationId: string,
  options: HistoryPageOptions,
) {
  limit(options.limit)
  const cursor = after(options.afterSequence)
  const page = await db.operationEvents
    .where('[mutationId+sequence]')
    .between([mutationId, cursor], [mutationId, Number.MAX_SAFE_INTEGER], false, true)
    .limit(options.limit + 1)
    .toArray()
  return {
    items: page.slice(0, options.limit),
    nextAfterSequence: page.length > options.limit ? page[options.limit - 1]!.sequence! : null,
  }
}

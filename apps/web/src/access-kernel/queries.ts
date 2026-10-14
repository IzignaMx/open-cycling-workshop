import type { EntityType } from '../sync/types.js'
import type { KernelDatabase } from './database.js'
import { entityCapability, requireCapability } from './operations.js'
import { readProjection } from './projection.js'
import type {
  ContextTicket,
  OperationDelivery,
  OperationState,
  VerifiedAccessContext,
} from './types.js'

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

/** Fixed protocol states, independent of the dispatchable/blocked optimization flags. */
export const ISSUE_STATES = [
  'awaiting_confirmation',
  'held_authorization',
  'held_dependency',
  'held_integrity',
  'held_recovery',
  'held_retry',
  'rejected',
] as const satisfies readonly OperationState[]
const ISSUE_ENTITIES: readonly EntityType[] = ['customer', 'bicycle', 'service_order']

/** At most 21 bounded metadata streams; originals are fetched only for the selected page.
 * hasIssues describes all readable issues, not merely the requested page.
 */
export async function issuePage(
  db: KernelDatabase,
  ticket: ContextTicket,
  context: VerifiedAccessContext,
  options: HistoryPageOptions,
) {
  limit(options.limit)
  const cursor = after(options.afterSequence)
  const groups = ISSUE_ENTITIES.filter((entity) =>
    context.capabilities.includes(entityCapability(entity, 'read')),
  ).flatMap((entity) => ISSUE_STATES.map((state) => ({ entity, state })))
  const pages = await Promise.all(
    groups.map(async ({ entity, state }) => {
      const prefix = [ticket.principalKey, context.selectedLocationId, entity, state]
      const from = (sequence: number) =>
        db.operationDelivery
          .where('[principalKey+locationId+entityType+state+localSequence]')
          .between([...prefix, sequence], [...prefix, Number.MAX_SAFE_INTEGER], false, true)
      const candidates = await from(cursor)
        .limit(options.limit + 1)
        .toArray()
      const first = cursor === 0 ? candidates[0] : await from(0).first()
      return { candidates, hasIssues: first !== undefined }
    }),
  )
  const candidates: OperationDelivery[] = pages
    .flatMap((page) => page.candidates)
    .sort((left, right) => left.localSequence - right.localSequence)
  const selected = candidates.slice(0, options.limit)
  const items = []
  for (const delivery of selected) {
    const operation = await db.operationJournal.get(delivery.mutationId)
    if (
      !operation ||
      operation.principalKey !== ticket.principalKey ||
      operation.locationId !== context.selectedLocationId ||
      operation.entityType !== delivery.entityType ||
      operation.entityId !== delivery.entityId ||
      operation.localSequence !== delivery.localSequence ||
      !Number.isSafeInteger(operation.localSequence) ||
      operation.localSequence <= cursor
    )
      throw new Error('Invalid issue delivery metadata')
    items.push({ operation, delivery })
  }
  const pending = await Promise.all(
    ISSUE_ENTITIES.filter((entity) =>
      context.capabilities.includes(entityCapability(entity, 'read')),
    ).flatMap((entity) =>
      (['pending', 'inflight', 'retryable', 'awaiting_confirmation'] as const).map(
        async (state) => {
          const prefix = [ticket.principalKey, context.selectedLocationId, entity, state]
          const delivery = await db.operationDelivery
            .where('[principalKey+locationId+entityType+state+localSequence]')
            .between([...prefix, 0], [...prefix, Number.MAX_SAFE_INTEGER], false, true)
            .first()
          const retry =
            state === 'retryable' && delivery
              ? await db.operationDelivery
                  .where('[principalKey+locationId+entityType+state+retryAt]')
                  .between([...prefix, 0], [...prefix, Number.MAX_SAFE_INTEGER], true, true)
                  .first()
              : undefined
          if (delivery && (!Number.isSafeInteger(delivery.retryAt) || delivery.retryAt < 0))
            throw new Error('Invalid pending delivery retry metadata')
          return { present: delivery !== undefined, retryAt: retry?.retryAt ?? null }
        },
      ),
    ),
  )
  const retries = pending.flatMap((row) => (row.retryAt === null ? [] : [row.retryAt]))
  return {
    items,
    nextAfterSequence: candidates.length > options.limit ? selected.at(-1)!.localSequence : null,
    hasIssues: pages.some((page) => page.hasIssues),
    hasPending: pending.some((row) => row.present),
    nextRetryAt: retries.length ? Math.min(...retries) : null,
  }
}

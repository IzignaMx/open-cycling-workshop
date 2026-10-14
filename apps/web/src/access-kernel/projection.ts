import type { EntityType } from '../sync/types.js'
import type { KernelDatabase } from './database.js'
import {
  entityCapability,
  operationIntact,
  operationProvenance,
  requireCapability,
  validateProjection,
} from './operations.js'
import type {
  ContextTicket,
  OperationDelivery,
  OwnedOperation,
  VerifiedAccessContext,
} from './types.js'

export const replayableStates = new Set(['pending', 'retryable', 'awaiting_confirmation'])
export const heldDependencyStates = new Set([
  'rejected',
  'held_authorization',
  'held_dependency',
  'held_integrity',
  'held_retry',
  'held_recovery',
])

/** Confirmed prerequisites come only from the admitted current partition. */
export async function hasConfirmedEntity(
  db: KernelDatabase,
  partitionId: string,
  context: VerifiedAccessContext,
  entityType: EntityType,
  entityId: string,
): Promise<boolean> {
  if (!context.capabilities.includes(entityCapability(entityType, 'read'))) return false
  const confirmed = await db.cacheRecords.get([partitionId, entityType, entityId])
  if (!confirmed) return false
  validateProjection(entityType, entityId, confirmed.payload, context)
  if (confirmed.version !== confirmed.payload.version)
    throw new Error('Confirmed projection version integrity mismatch')
  return true
}

/** Old-incarnation implicit history cannot block independently confirmed current data.
 * Explicit dependencies are still validated separately and never bypass this boundary.
 * Pages stay bounded even after many retained recovery generations.
 */
export async function aggregateBoundary(
  db: KernelDatabase,
  context: VerifiedAccessContext,
  prefix: readonly (string | number)[],
  field: 'unresolved' | 'blocked',
  confirmed: boolean,
  upper = Number.MAX_SAFE_INTEGER,
  reverse = false,
): Promise<OperationDelivery | undefined> {
  const index = `[principalKey+locationId+entityType+entityId+${field}+localSequence]`
  let lower = 0,
    before = upper
  while (true) {
    let query = db.operationDelivery
      .where(index)
      .between([...prefix, 1, lower], [...prefix, 1, before], false, !reverse)
    if (reverse) query = query.reverse()
    if (!confirmed) return query.first()
    const page = await query.limit(100).toArray()
    for (const delivery of page) {
      const operation = await db.operationJournal.get(delivery.mutationId)
      if (!operation || operationProvenance(operation, context)) return delivery
    }
    if (page.length < 100) return undefined
    if (reverse) before = page.at(-1)!.localSequence
    else lower = page.at(-1)!.localSequence
  }
}

async function dependenciesVisible(
  db: KernelDatabase,
  operation: OwnedOperation,
  context: VerifiedAccessContext,
  partitionId: string,
): Promise<boolean> {
  const pending = [operation]
  const visited = new Set<string>()
  while (pending.length) {
    const child = pending.pop()!
    if (visited.has(child.mutationId)) continue
    visited.add(child.mutationId)
    // Per-aggregate order is an implicit dependency, even if the command did
    // not explicitly list its preceding local mutation.
    const prefix = [child.principalKey, child.locationId, child.entityType, child.entityId]
    const confirmed = await hasConfirmedEntity(
      db,
      partitionId,
      context,
      child.entityType,
      child.entityId,
    )
    const predecessor = await aggregateBoundary(
      db,
      context,
      prefix,
      'unresolved',
      confirmed,
      child.localSequence,
      true,
    )
    const dependencies = new Set([
      ...child.dependsOn,
      ...(predecessor ? [predecessor.mutationId] : []),
    ])
    for (const id of dependencies) {
      const parent = await db.operationJournal.get(id)
      const delivery = await db.operationDelivery.get(id)
      if (
        !parent ||
        !delivery ||
        !operationIntact(parent) ||
        !operationProvenance(parent, context) ||
        parent.principalKey !== operation.principalKey ||
        parent.locationId !== operation.locationId ||
        parent.localSequence >= child.localSequence ||
        heldDependencyStates.has(delivery.state)
      )
        return false
      if (delivery.state !== 'applied') {
        if (!context.capabilities.includes(entityCapability(parent.entityType, 'write')))
          return false
        pending.push(parent)
      }
    }
  }
  return true
}

/** Called only inside the kernel's fenced transaction. An ACK is not server projection data. */
export async function readProjection(
  db: KernelDatabase,
  ticket: ContextTicket,
  context: VerifiedAccessContext,
  entityType: EntityType,
  entityId: string,
) {
  requireCapability(context, entityCapability(entityType, 'read'))
  const confirmed = await db.cacheRecords.get([ticket.partitionId, entityType, entityId])
  if (confirmed) {
    validateProjection(entityType, entityId, confirmed.payload, context)
    if (confirmed.version !== confirmed.payload.version)
      throw new Error('Confirmed projection version integrity mismatch')
  }
  const prefix = [ticket.principalKey, context.selectedLocationId, entityType, entityId]
  const load = async (delivery: OperationDelivery) => {
    const operation = await db.operationJournal.get(delivery.mutationId)
    if (
      !operation ||
      !operationIntact(operation) ||
      operation.principalKey !== ticket.principalKey ||
      operation.locationId !== context.selectedLocationId ||
      operation.entityType !== entityType ||
      operation.entityId !== entityId ||
      operation.localSequence !== delivery.localSequence
    )
      throw new Error('Operation projection integrity mismatch')
    validateProjection(entityType, entityId, operation.optimistic, context)
    return operation
  }
  let optimistic: Record<string, unknown> | undefined
  let optimisticStatus: 'pending' | 'applied_awaiting_projection' | undefined
  let overlaySequence = 0
  // Read at most the newest acknowledged version beyond confirmed coverage, not
  // every historical immutable envelope. It remains explicitly unconfirmed.
  const applied = await db.operationDelivery
    .where('[principalKey+locationId+entityType+entityId+resultVersion]')
    .between(
      [...prefix, confirmed?.version ?? 0],
      [...prefix, Number.MAX_SAFE_INTEGER],
      false,
      true,
    )
    .reverse()
    .first()
  if (applied) {
    if (
      applied.state !== 'applied' ||
      applied.result?.status !== 'applied' ||
      applied.resultVersion !== applied.result.entity_version
    )
      throw new Error('Invalid applied projection metadata')
    const operation = await load(applied)
    if (
      operationProvenance(operation, context) &&
      (await dependenciesVisible(db, operation, context, ticket.partitionId))
    ) {
      optimistic = operation.optimistic
      optimisticStatus = 'applied_awaiting_projection'
      overlaySequence = operation.localSequence
    }
  }
  const blocked = await aggregateBoundary(db, context, prefix, 'blocked', confirmed !== undefined)
  if (context.capabilities.includes(entityCapability(entityType, 'write'))) {
    // Bound allocation even for a long offline chain. Continue to older pages
    // when newer dependency chains are held; never silently lose an eligible overlay.
    let before = blocked?.localSequence ?? Number.MAX_SAFE_INTEGER
    let includeUpper = blocked === undefined
    while (before > overlaySequence) {
      const page = await db.operationDelivery
        .where('[principalKey+locationId+entityType+entityId+dispatchable+localSequence]')
        .between([...prefix, 1, overlaySequence], [...prefix, 1, before], false, includeUpper)
        .reverse()
        .limit(100)
        .toArray()
      let found = false
      for (const delivery of page) {
        if (!replayableStates.has(delivery.state) && delivery.state !== 'inflight') continue
        const operation = await load(delivery)
        if (
          operationProvenance(operation, context) &&
          (await dependenciesVisible(db, operation, context, ticket.partitionId))
        ) {
          optimistic = operation.optimistic
          optimisticStatus = 'pending'
          found = true
          break
        }
      }
      if (found || page.length < 100) break
      before = page[page.length - 1]!.localSequence
      includeUpper = false
    }
  }
  return confirmed || optimistic
    ? { confirmed: confirmed?.payload, optimistic, optimisticStatus }
    : undefined
}

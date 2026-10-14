import type { EntityType } from '../sync/types.js'
import type { KernelDatabase } from './database.js'
import {
  entityCapability,
  operationIntact,
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
])

async function dependenciesVisible(
  db: KernelDatabase,
  operation: OwnedOperation,
  context: VerifiedAccessContext,
): Promise<boolean> {
  const pending = [operation]
  const visited = new Set<string>()
  while (pending.length) {
    const child = pending.pop()!
    if (visited.has(child.mutationId)) continue
    visited.add(child.mutationId)
    for (const id of child.dependsOn) {
      const parent = await db.operationJournal.get(id)
      const delivery = await db.operationDelivery.get(id)
      if (
        !parent ||
        !delivery ||
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
    optimistic = operation.optimistic
    optimisticStatus = 'applied_awaiting_projection'
    overlaySequence = operation.localSequence
  }
  const blocked = await db.operationDelivery
    .where('[principalKey+locationId+entityType+entityId+blocked+localSequence]')
    .between([...prefix, 1, 0], [...prefix, 1, Number.MAX_SAFE_INTEGER], true, true)
    .first()
  if (context.capabilities.includes(entityCapability(entityType, 'write'))) {
    // Only unresolved candidate metadata is materialized; applied/rejected lifetime
    // history is excluded by the index. Fetch payloads lazily, newest first.
    const pending = await db.operationDelivery
      .where('[principalKey+locationId+entityType+entityId+dispatchable+localSequence]')
      .between(
        [...prefix, 1, overlaySequence],
        [...prefix, 1, blocked?.localSequence ?? Number.MAX_SAFE_INTEGER],
        false,
        blocked === undefined,
      )
      .reverse()
      .toArray()
    for (const delivery of pending) {
      if (!replayableStates.has(delivery.state) && delivery.state !== 'inflight') continue
      const operation = await load(delivery)
      if (await dependenciesVisible(db, operation, context)) {
        optimistic = operation.optimistic
        optimisticStatus = 'pending'
        break
      }
    }
  }
  return confirmed || optimistic
    ? { confirmed: confirmed?.payload, optimistic, optimisticStatus }
    : undefined
}

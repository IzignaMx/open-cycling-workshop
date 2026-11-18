/** Synthetic custody prototype only. Not a production authorization or handover API. */
import { KernelDatabase } from '../../.tmp-kernel/src/access-kernel/database.js'
import {
  validCheckpoint,
  validContent,
  validInteger,
  validUUID,
  writerEpoch,
  frozenCopy,
} from '../../.tmp-kernel/src/access-kernel/capture-checkpoint.js'
import { canonicalJson } from '../../.tmp-kernel/src/access-kernel/operations.js'
import {
  validateVerifiedContext,
  principalKey,
} from '../../.tmp-kernel/src/access-kernel/context.js'
import { validateAdmission } from '../../.tmp-kernel/src/access-kernel/session-admission.js'
import { completedBaseline } from '../../.tmp-kernel/src/access-kernel/baseline-state.js'

const witnesses = new WeakMap()
const channels = ['customer', 'order']
const refused = (reason) => ({ kind: 'refused', reason })
const hash = async (value) => {
  const bytes = await crypto.subtle.digest(
    'SHA-256',
    new TextEncoder().encode(canonicalJson(value)),
  )
  return [...new Uint8Array(bytes)].map((byte) => byte.toString(16).padStart(2, '0')).join('')
}
const same = (a, b) => canonicalJson(a) === canonicalJson(b)

/** The caller supplies a live synthetic authority callback; stored rows alone are not authentication.
 * Conservative bound: reject any history and more than two total draft rows. No history is exported.
 */
async function inspect(options) {
  const { db, now, isCurrent } = options
  if (
    !(db instanceof KernelDatabase) ||
    !validInteger(now) ||
    typeof isCurrent !== 'function' ||
    isCurrent() !== true
  )
    return refused('authority')
  if (db.constructor.currentTransaction) return refused('nested_transaction')
  const ticket = structuredClone(options.ticket),
    scope = structuredClone(options.scope)
  const checkpointId = options.checkpointId
  if (!validUUID(checkpointId)) return refused('invalid')
  const bindingKey = await hash([scope.apiRealm, scope.sessionBindingId]),
    scopeKey = await hash({ ...scope, capabilities: [...new Set(scope.capabilities)].sort() })
  const result = await db.transaction(
    'r',
    [
      db.deviceControl,
      db.accessContexts,
      db.cachePartitions,
      db.captureCheckpoints,
      db.captureDraftContents,
      db.operationJournal,
      db.operationDelivery,
      db.operationEvents,
    ],
    async () => {
      if (isCurrent() !== true) return refused('authority')
      const control = await db.deviceControl.get('device')
      const record = await db.accessContexts.get(ticket.partitionId)
      const partition = await db.cachePartitions.get(ticket.partitionId)
      const checkpoint = await db.captureCheckpoints.get(checkpointId)
      // Existence inspection is sufficient for the intentionally empty-history contract.
      for (const table of [db.operationJournal, db.operationDelivery, db.operationEvents]) {
        if ((await table.toCollection().limit(1).primaryKeys()).length)
          return refused('history_present')
      }
      const rows = await db.captureDraftContents.limit(3).toArray()
      if (rows.length > 2) return refused('capacity')
      if (!control || !record || !partition || !validCheckpoint(checkpoint))
        return refused('invalid')
      const context = record.context
      validateVerifiedContext(context, now)
      if (
        !validInteger(control.generation) ||
        !validInteger(control.observedAt) ||
        !validInteger(control.dispatchScanAfter) ||
        !['READY', 'OFFLINE_READY'].includes(control.state) ||
        control.generation !== ticket.deviceGeneration ||
        control.tabAttemptId !== ticket.tabAttemptId ||
        control.activePartitionId !== ticket.partitionId ||
        record.partitionId !== ticket.partitionId ||
        partition.partitionId !== ticket.partitionId ||
        principalKey(context.principal) !== ticket.principalKey ||
        partition.principalKey !== ticket.principalKey ||
        context.authorizationEpoch !== ticket.authorizationEpoch ||
        partition.authorizationEpoch !== ticket.authorizationEpoch ||
        partition.locationId !== context.selectedLocationId ||
        partition.policyRevision !== context.policyRevision ||
        !completedBaseline(partition, context) ||
        !same(partition.baseline.owner, ticket) ||
        now < control.observedAt ||
        now < checkpoint.observedAt ||
        checkpoint.closed ||
        writerEpoch(control) !== checkpoint.writerEpoch
      )
        return refused('authority')
      const admission = validateAdmission(partition.sessionAdmission, partition, context)
      const actualScope = {
        ...context.principal,
        selectedLocationId: context.selectedLocationId,
        datasetIncarnation: context.datasetIncarnation,
        authorizationEpoch: context.authorizationEpoch,
        policyRevision: context.policyRevision,
        capabilities: [...context.capabilities].sort(),
        sessionBindingId: admission.sessionBindingId,
      }
      if (
        !same(admission.owner, ticket) ||
        !same(actualScope, { ...scope, capabilities: [...scope.capabilities].sort() }) ||
        checkpoint.bindingKey !== bindingKey ||
        checkpoint.scopeKey !== scopeKey
      )
        return refused('authority')
      if (rows.some((row) => row.checkpointId !== checkpointId || !channels.includes(row.channel)))
        return refused('foreign_content')
      const contents = []
      for (const channel of channels) {
        const state = checkpoint[channel],
          row = rows.find((r) => r.channel === channel)
        if (state.state === 'EMPTY') {
          if (row) return refused('invalid')
          continue
        }
        if (state.state !== 'UNSENT') return refused('protected')
        if (
          !context.capabilities.includes(
            channel === 'customer' ? 'customers.write' : 'orders.write',
          ) ||
          (channel === 'order' && !context.capabilities.includes('customers.read'))
        )
          return refused('authority')
        if (
          !validContent(row) ||
          row.generation !== checkpoint.generation ||
          row.revision !== state.revision ||
          row.firstPersistedAt !== state.contentStartedAt ||
          row.expiresAt !== state.contentExpiresAt
        )
          return refused('invalid')
        if (now < row.firstPersistedAt || now >= row.expiresAt) return refused('expired')
        contents.push(row)
      }
      if (!contents.length) return refused('empty')
      if (isCurrent() !== true) return refused('authority')
      const owner = {
        apiRealm: context.principal.apiRealm,
        organizationId: context.principal.organizationId,
        userId: context.principal.userId,
        selectedLocationId: context.selectedLocationId,
        datasetIncarnation: context.datasetIncarnation,
      }
      const bundle = {
        format: 1,
        kind: 'inert-capture-custody',
        owner,
        capturedAt: now,
        checkpoint,
        contents,
      }
      // Only a private comparison value leaves this function, never a printable raw snapshot.
      const comparison = canonicalJson({
        control,
        record,
        partition,
        checkpoint,
        rows,
        ticket,
        scope,
        journal: [],
        delivery: [],
        events: [],
      })
      return { kind: 'inspected', bundle: frozenCopy(bundle), comparison }
    },
  )
  return isCurrent() === true ? result : refused('authority')
}

export async function snapshotSource(options) {
  try {
    const result = await inspect(options)
    if (result.kind !== 'inspected') return result
    const witness = Object.freeze({})
    witnesses.set(witness, { db: options.db, comparison: result.comparison })
    return { kind: 'snapshot', bundle: result.bundle, witness }
  } catch {
    return refused('unavailable')
  }
}

/** A positive check is an observation only: a subsequent old-client write is still possible. */
export async function revalidateSource(options, witness) {
  try {
    const prior = witnesses.get(witness)
    if (!prior || prior.db !== options.db) return refused('witness')
    const result = await inspect(options)
    if (result.kind !== 'inspected') return result
    return {
      kind: result.comparison === prior.comparison ? 'source_unchanged_at_check' : 'source_changed',
    }
  } catch {
    return refused('unavailable')
  }
}

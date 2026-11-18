/** Test-only source-work observation. Never a migration/activation or authentication API. */
import { KernelDatabase } from '../../.tmp-kernel/src/access-kernel/database.js'
import {
  canonicalJson,
  operationIntact,
  operationProvenance,
  validateResults,
} from '../../.tmp-kernel/src/access-kernel/operations.js'
import {
  validateVerifiedContext,
  principalKey,
} from '../../.tmp-kernel/src/access-kernel/context.js'
import { completedBaseline } from '../../.tmp-kernel/src/access-kernel/baseline-state.js'
import { validateAdmission } from '../../.tmp-kernel/src/access-kernel/session-admission.js'
import {
  validCheckpoint,
  validContent,
  preservableUnsupportedContent,
  validInteger,
} from '../../.tmp-kernel/src/access-kernel/capture-checkpoint.js'
const witnesses = new WeakMap()
const refused = (reason) => ({ kind: 'refused', reason })
const same = (a, b) => canonicalJson(a) === canonicalJson(b)
const digest = async (value) =>
  Array.from(
    new Uint8Array(
      await crypto.subtle.digest('SHA-256', new TextEncoder().encode(canonicalJson(value))),
    ),
    (b) => b.toString(16).padStart(2, '0'),
  ).join('')
export const LIMITS = Object.freeze({
  captureCheckpoints: 32,
  captureDraftContents: 64,
  operationJournal: 128,
  operationDelivery: 128,
  operationEvents: 512,
})
const states = new Set([
  'pending',
  'inflight',
  'retryable',
  'awaiting_confirmation',
  'held_authorization',
  'held_dependency',
  'held_integrity',
  'held_retry',
  'held_recovery',
  'rejected',
  'applied',
])
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
  const bindingKey = await digest([scope.apiRealm, scope.sessionBindingId]),
    scopeKey = await digest({ ...scope, capabilities: [...new Set(scope.capabilities)].sort() })
  const tables = ['deviceControl', 'accessContexts', 'cachePartitions', ...Object.keys(LIMITS)]
  const result = await db.transaction(
    'r',
    tables.map((n) => db[n]),
    async () => {
      if (isCurrent() !== true) return refused('authority')
      const control = await db.deviceControl.get('device'),
        record = await db.accessContexts.get(ticket.partitionId),
        partition = await db.cachePartitions.get(ticket.partitionId)
      if (!control || !record || !partition) return refused('authority')
      const context = record.context
      validateVerifiedContext(context, now)
      if (
        !['READY', 'OFFLINE_READY'].includes(control.state) ||
        control.generation !== ticket.deviceGeneration ||
        control.tabAttemptId !== ticket.tabAttemptId ||
        control.activePartitionId !== ticket.partitionId ||
        principalKey(context.principal) !== ticket.principalKey ||
        context.authorizationEpoch !== ticket.authorizationEpoch ||
        !completedBaseline(partition, context) ||
        !same(partition.baseline.owner, ticket) ||
        !validInteger(control.observedAt) ||
        !validInteger(control.localSequence) ||
        now < control.observedAt
      )
        return refused('authority')
      const admission = validateAdmission(partition.sessionAdmission, partition, context)
      const actual = {
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
        !same(actual, { ...scope, capabilities: [...scope.capabilities].sort() })
      )
        return refused('authority')
      const rows = {}
      for (const [name, limit] of Object.entries(LIMITS)) {
        rows[name] = await db[name].limit(limit + 1).toArray()
        if (rows[name].length > limit) return refused('capacity')
      }
      const actions = new Set(),
        counts = {
          unsent: 0,
          protected: 0,
          unavailable: 0,
          expired: 0,
          unsupported: 0,
          appliedHistory: 0,
          unresolvedOperations: 0,
        }
      const checkpointIds = new Set()
      for (const cp of rows.captureCheckpoints) {
        if (!validCheckpoint(cp) || cp.observedAt > now) return refused('integrity')
        if (cp.bindingKey !== bindingKey || cp.scopeKey !== scopeKey) return refused('scope')
        checkpointIds.add(cp.checkpointId)
        for (const channel of ['customer', 'order']) {
          const state = cp[channel],
            content = rows.captureDraftContents.find(
              (r) => r.checkpointId === cp.checkpointId && r.channel === channel,
            )
          if (state.state === 'EMPTY') {
            if (content) return refused('integrity')
            continue
          }
          if (
            !context.capabilities.includes(
              channel === 'customer' ? 'customers.write' : 'orders.write',
            ) ||
            (channel === 'order' && !context.capabilities.includes('customers.read'))
          )
            return refused('authority')
          if (state.state === 'PROTECTED') {
            if (content) return refused('integrity')
            counts.protected++
            actions.add('check_capture_receipt_at_source')
            continue
          }
          if (state.state === 'UNAVAILABLE') {
            if (content) return refused('integrity')
            counts.unavailable++
            actions.add('review_recovery_at_source')
            continue
          }
          if (
            !content ||
            (!validContent(content) && !preservableUnsupportedContent(content)) ||
            content.generation !== cp.generation ||
            content.revision !== state.revision ||
            content.firstPersistedAt !== state.contentStartedAt ||
            content.expiresAt !== state.contentExpiresAt ||
            now < content.firstPersistedAt
          )
            return refused('integrity')
          if (content.format > 1) {
            counts.unsupported++
            actions.add('use_compatible_recovery_at_source')
          }
          if (now >= content.expiresAt) {
            counts.expired++
            actions.add('review_expired_capture_at_source')
          }
          if (state.state === 'UNSENT') {
            counts.unsent++
            if (content.format === 1 && now < content.expiresAt && !cp.closed)
              actions.add('finish_capture_at_source')
          }
          if (cp.closed) actions.add('review_recovery_at_source')
        }
      }
      if (
        rows.captureDraftContents.some(
          (r) => !checkpointIds.has(r.checkpointId) || !['customer', 'order'].includes(r.channel),
        )
      )
        return refused('integrity')
      const journal = new Map(rows.operationJournal.map((r) => [r.mutationId, r]))
      if (rows.operationDelivery.length !== journal.size) return refused('integrity')
      const sequences = new Set()
      for (const op of journal.values()) {
        if (
          !validInteger(op.localSequence) ||
          op.localSequence < 1 ||
          op.localSequence > control.localSequence ||
          sequences.has(op.localSequence) ||
          !Array.isArray(op.dependsOn) ||
          op.dependsOn.some((id) => typeof id !== 'string' || !journal.has(id))
        )
          return refused('integrity')
        sequences.add(op.localSequence)
        if (!operationIntact(op) || !operationProvenance(op, context)) return refused('integrity')
        if (
          op.principalKey !== ticket.principalKey ||
          op.organizationId !== context.principal.organizationId ||
          op.locationId !== context.selectedLocationId
        )
          return refused('scope')
        const delivery = rows.operationDelivery.find((d) => d.mutationId === op.mutationId)
        if (
          !delivery ||
          !states.has(delivery.state) ||
          ['dispatchable', 'unresolved', 'blocked'].some((k) => ![0, 1].includes(delivery[k])) ||
          ['attempts', 'resultVersion', 'retryAt'].some((k) => !validInteger(delivery[k])) ||
          ['principalKey', 'locationId', 'entityType', 'entityId', 'localSequence'].some(
            (k) => delivery[k] !== op[k],
          )
        )
          return refused('integrity')
        if (delivery.state === 'applied') {
          const [r] = validateResults([op], { results: [delivery.result] })
          if (
            r.status !== 'applied' ||
            delivery.unresolved !== 0 ||
            delivery.dispatchable !== 0 ||
            delivery.blocked !== 0
          )
            return refused('integrity')
          counts.appliedHistory++
          actions.add('retain_applied_history')
        } else {
          counts.unresolvedOperations++
          actions.add(
            ['inflight', 'awaiting_confirmation'].includes(delivery.state)
              ? 'check_unknown_outcome_at_source'
              : 'review_sync_at_source',
          )
        }
      }
      if (
        rows.operationEvents.some(
          (e) =>
            !journal.has(e.mutationId) ||
            !validInteger(e.sequence) ||
            !['local', 'dispatch', 'result', 'held', 'retry'].includes(e.kind) ||
            !Number.isFinite(Date.parse(e.occurredAt)) ||
            Date.parse(e.occurredAt) > now ||
            !e.details ||
            typeof e.details !== 'object',
        )
      )
        return refused('integrity')
      if (isCurrent() !== true) return refused('authority')
      return {
        kind: 'inspected',
        receipt: {
          format: 1,
          observedAt: now,
          coverage: 'bounded_single_database_current_scope',
          counts,
          actions: [...actions].sort(),
          activation: 'not_assessed',
          migration: 'forbidden',
        },
        comparison: canonicalJson({
          control,
          record,
          partition,
          rows,
          ticket,
          scope,
          counts,
          actions: [...actions].sort(),
        }),
      }
    },
  )
  return isCurrent() === true ? result : refused('authority')
}
export async function observeSource(options) {
  try {
    const result = await inspect(options)
    if (result.kind !== 'inspected') return result
    const witness = Object.freeze({})
    witnesses.set(witness, {
      db: options.db,
      comparison: result.comparison,
      observedAt: options.now,
    })
    return { kind: 'observation', receipt: result.receipt, witness }
  } catch {
    return refused('unavailable')
  }
}
export async function recheckObservation(options, witness) {
  try {
    const previous = witnesses.get(witness)
    if (!previous || previous.db !== options.db || options.now < previous.observedAt)
      return refused('witness')
    const next = await inspect(options)
    if (next.kind !== 'inspected') return next
    return {
      kind: next.comparison === previous.comparison ? 'unchanged_at_check' : 'changed',
      activation: 'not_assessed',
    }
  } catch {
    return refused('unavailable')
  }
}

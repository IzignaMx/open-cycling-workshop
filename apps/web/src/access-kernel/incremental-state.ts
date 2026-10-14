import { contextKey, principalKey } from './context.js'
import { canonicalJson } from './operations.js'
import { validateBaselineRequest, BASELINE_RESPONSE_LIMIT } from './baseline-wire.js'
import {
  incrementalObject,
  incrementalToken,
  validateIncrementalResponse,
} from './incremental-wire.js'
import type { CachePartition, ContextTicket, VerifiedAccessContext } from './types.js'

export interface IncrementalRequest {
  kind: 'delta'
  body: string
}
export interface IncrementalMetadata {
  format: 1
  binding: string
  datasetIncarnation: string
  owner: ContextTicket
  initialCheckpoint: string
  sequence: number
  phase: 'complete' | 'catching_up'
  next: IncrementalRequest
  receipt: { predecessor: string; requestBody: string; response: string } | null
  retryCount: number
  hold: { reason: string; retryAt: number | null; attempts: number } | null
}
/** Additive metadata, never an IndexedDB schema or index upgrade. */
export type IncrementalPartition = CachePartition & { incremental?: IncrementalMetadata }
export const incrementalTransientReasons = [
  'network_error',
  'baseline_in_progress',
  'baseline_capacity',
  'temporary_unavailable',
] as const
export function incrementalRequiresBaseline(value: IncrementalMetadata): boolean {
  return (
    value.hold !== null &&
    [
      'checkpoint_expired',
      'baseline_expired',
      'continuation_stale',
      'dataset_changed',
      'context_changed',
      'projection_too_large',
      'cursor_invalid',
      'unsupported_protocol',
      'invalid_response',
      'invalid_request',
    ].includes(value.hold.reason)
  )
}
function reject(): never {
  throw new Error('Invalid incremental metadata')
}
function parse(body: string, limit: number): unknown {
  if (typeof body !== 'string' || new TextEncoder().encode(body).byteLength > limit) return reject()
  return JSON.parse(body) as unknown
}
export function validateIncrementalRequest(request: IncrementalRequest): string {
  incrementalObject(request, ['kind', 'body'])
  if (request.kind !== 'delta') return reject()
  const body = validateBaselineRequest('delta', request.body)
  if (!('continuation' in body) || request.body !== canonicalJson(body)) return reject()
  return body.continuation
}
/** Called only after the independent immutable initial proof has been validated.
 * Sequence and anchor witness atomic local transitions, not discarded history or
 * cryptographic authority. No separate last-complete cursor is fabricated.
 */
export function validateIncrementalMetadata(
  partition: IncrementalPartition,
  context: VerifiedAccessContext,
): IncrementalMetadata {
  const value = partition.incremental
  incrementalObject(value, [
    'format',
    'binding',
    'datasetIncarnation',
    'owner',
    'initialCheckpoint',
    'sequence',
    'phase',
    'next',
    'receipt',
    'retryCount',
    'hold',
  ])
  if (
    !value ||
    value.format !== 1 ||
    value.binding !== contextKey(context) ||
    value.datasetIncarnation !== context.datasetIncarnation ||
    context.snapshotProtocol !== 'baseline-v1' ||
    partition.status !== 'active' ||
    !partition.baselineComplete ||
    partition.principalKey !== principalKey(context.principal) ||
    partition.locationId !== context.selectedLocationId ||
    partition.authorizationEpoch !== context.authorizationEpoch ||
    partition.policyRevision !== context.policyRevision ||
    partition.baseline?.phase !== 'active' ||
    partition.baseline.hold !== null ||
    value.initialCheckpoint !== partition.baseline.checkpoint ||
    canonicalJson(value.owner) !== canonicalJson(partition.baseline.owner) ||
    !Number.isSafeInteger(value.sequence) ||
    value.sequence < 0 ||
    !['complete', 'catching_up'].includes(value.phase)
  )
    return reject()
  incrementalToken(value.initialCheckpoint)
  const successor = validateIncrementalRequest(value.next)
  if (successor !== partition.cursor) return reject()
  if (value.sequence === 0) {
    if (
      value.receipt !== null ||
      successor !== value.initialCheckpoint ||
      value.phase !== 'complete'
    )
      return reject()
  } else {
    const raw = incrementalObject(value.receipt, ['predecessor', 'requestBody', 'response'])
    if (
      typeof raw.predecessor !== 'string' ||
      typeof raw.requestBody !== 'string' ||
      typeof raw.response !== 'string'
    )
      return reject()
    const predecessor = validateIncrementalRequest({ kind: 'delta', body: raw.requestBody })
    if (
      predecessor !== raw.predecessor ||
      (value.sequence === 1 && predecessor !== value.initialCheckpoint)
    )
      return reject()
    const receipt = validateIncrementalResponse(parse(raw.response, BASELINE_RESPONSE_LIMIT), {
      context,
      predecessor,
    })
    if (
      canonicalJson(receipt) !== raw.response ||
      receipt.continuation !== successor ||
      receipt.phase !== value.phase ||
      successor === value.initialCheckpoint
    )
      return reject()
  }
  if (!Number.isSafeInteger(value.retryCount) || value.retryCount < 0 || value.retryCount > 100)
    return reject()
  if (value.hold !== null) {
    const hold = incrementalObject(value.hold, ['reason', 'retryAt', 'attempts'])
    if (
      typeof hold.reason !== 'string' ||
      !hold.reason ||
      hold.reason.length > 80 ||
      hold.attempts !== value.retryCount ||
      value.retryCount < 1 ||
      (hold.retryAt !== null &&
        (typeof hold.retryAt !== 'number' ||
          !Number.isSafeInteger(hold.retryAt) ||
          hold.retryAt < 0))
    )
      return reject()
  }
  return value
}
export function initialIncrementalMetadata(
  partition: CachePartition,
  context: VerifiedAccessContext,
): IncrementalMetadata {
  const checkpoint = incrementalToken(partition.baseline?.checkpoint)
  if (!partition.baseline) return reject()
  return {
    format: 1,
    binding: contextKey(context),
    datasetIncarnation: context.datasetIncarnation,
    owner: structuredClone(partition.baseline.owner),
    initialCheckpoint: checkpoint,
    sequence: 0,
    phase: 'complete',
    next: { kind: 'delta', body: canonicalJson({ protocol: 1, continuation: checkpoint }) },
    receipt: null,
    retryCount: 0,
    hold: null,
  }
}

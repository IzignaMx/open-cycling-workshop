import {
  BASELINE_RESPONSE_LIMIT,
  validateBaselineRecord,
  type BaselineRecord,
} from './baseline-wire.js'
import { canonicalJson } from './operations.js'
import type { VerifiedAccessContext } from './types.js'

export interface IncrementalResponse {
  protocol: 1
  baseline_id: null
  authorization_epoch: string
  predecessor: string
  continuation: string
  page_id: string
  records: BaselineRecord[]
  phase: 'catching_up' | 'complete'
  completion: { baseline_id: null; authorization_epoch: string; checkpoint: string } | null
}
export interface IncrementalBinding {
  context: VerifiedAccessContext
  predecessor: string
}
function reject(): never {
  throw new Error('Invalid incremental wire data')
}
export function incrementalObject(
  value: unknown,
  keys: readonly string[],
): Record<string, unknown> {
  if (
    !value ||
    typeof value !== 'object' ||
    Array.isArray(value) ||
    Object.keys(value).length !== keys.length ||
    keys.some((key) => !Object.hasOwn(value, key))
  )
    return reject()
  return value as Record<string, unknown>
}
export function incrementalToken(value: unknown): string {
  if (
    typeof value !== 'string' ||
    !value ||
    value.length > 512 ||
    [...value].some((character) => character.charCodeAt(0) > 127)
  )
    return reject()
  return value
}
/** Initial ingestion and ongoing deltas deliberately have distinct closed parsers. */
export function validateIncrementalResponse(
  value: unknown,
  binding: IncrementalBinding,
): IncrementalResponse {
  const raw = incrementalObject(value, [
    'protocol',
    'baseline_id',
    'authorization_epoch',
    'predecessor',
    'continuation',
    'page_id',
    'records',
    'phase',
    'completion',
  ])
  if (
    raw.protocol !== 1 ||
    raw.baseline_id !== null ||
    raw.authorization_epoch !== binding.context.authorizationEpoch ||
    typeof raw.page_id !== 'string' ||
    !raw.page_id ||
    [...raw.page_id].length > 36 ||
    !Array.isArray(raw.records) ||
    raw.records.length > 100 ||
    (raw.phase !== 'catching_up' && raw.phase !== 'complete')
  )
    return reject()
  const predecessor = incrementalToken(raw.predecessor),
    continuation = incrementalToken(raw.continuation)
  if (predecessor !== binding.predecessor || predecessor === continuation) return reject()
  let completion: IncrementalResponse['completion'] = null
  if (raw.phase === 'complete') {
    const complete = incrementalObject(raw.completion, [
      'baseline_id',
      'authorization_epoch',
      'checkpoint',
    ])
    if (
      complete.baseline_id !== null ||
      complete.authorization_epoch !== raw.authorization_epoch ||
      complete.checkpoint !== continuation
    )
      return reject()
    completion = {
      baseline_id: null,
      authorization_epoch: raw.authorization_epoch as string,
      checkpoint: continuation,
    }
  } else if (raw.completion !== null) return reject()
  if (new TextEncoder().encode(canonicalJson(raw)).byteLength > BASELINE_RESPONSE_LIMIT)
    return reject()
  const result: IncrementalResponse = {
    protocol: 1,
    baseline_id: null,
    authorization_epoch: raw.authorization_epoch as string,
    predecessor,
    continuation,
    page_id: raw.page_id,
    phase: raw.phase,
    completion,
    records: raw.records.map((record) => {
      validateBaselineRecord(record, binding.context)
      return structuredClone(record) as BaselineRecord
    }),
  }
  return freeze(result)
}
function freeze<T>(value: T): T {
  if (value !== null && typeof value === 'object') {
    for (const child of Object.values(value)) freeze(child)
    Object.freeze(value)
  }
  return value
}

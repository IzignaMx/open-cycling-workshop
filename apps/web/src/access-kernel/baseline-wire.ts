import { entityCapability } from './operations.js'
import { contextKey } from './context.js'
import { convertServerContext, type ContextRequestIdentity } from './server-context.js'
import type { VerifiedAccessContext } from './types.js'

export const BASELINE_RESPONSE_LIMIT = 1_048_576
export const BASELINE_CONTROL_LIMIT = 16_384
export type BaselineKind = 'start' | 'scan' | 'finalize' | 'delta' | 'activation'
export interface BaselineWireContext {
  protocol: 1
  principal: { api_realm: null; organization_id: string; user_id: string }
  account_location_id: string | null
  selected_location_id: string
  capabilities: string[]
  authorization_epoch: string
  policy_revision: 'ocwp-access-baseline-2'
  dataset_incarnation: string
  verified_at: string
  offline_until: string
  snapshot_protocol: null | 'baseline-v1'
}
export interface BaselineRecord {
  entity_type: 'customer' | 'bicycle' | 'service_order'
  entity_id: string
  entity_version: number
  payload: Record<string, unknown>
}
export interface BaselineStartResponse {
  protocol: 1
  baseline_id: string
  context: BaselineWireContext
  continuation: string
  expires_at: string
}
export interface BaselineFinalizeResponse {
  protocol: 1
  baseline_id: string
  authorization_epoch: string
  predecessor: string
  continuation: string
}
export interface BaselineScanResponse extends BaselineFinalizeResponse {
  page_id: string
  records: BaselineRecord[]
  phase: 'scan' | 'scan_complete'
}
export interface BaselineCompletion {
  baseline_id: string
  authorization_epoch: string
  checkpoint: string
}
export interface BaselineDeltaResponse extends BaselineFinalizeResponse {
  page_id: string
  records: BaselineRecord[]
  phase: 'catching_up' | 'complete'
  completion: BaselineCompletion | null
}
export interface BaselineActivationResponse {
  protocol: 1
  baseline_id: string
  authorization_epoch: string
  checkpoint: string
  context: BaselineWireContext
}
export interface BaselineResponseMap {
  start: BaselineStartResponse
  scan: BaselineScanResponse
  finalize: BaselineFinalizeResponse
  delta: BaselineDeltaResponse
  activation: BaselineActivationResponse
}
export interface BaselineBinding {
  context: VerifiedAccessContext
  identity: Readonly<ContextRequestIdentity>
  baselineId?: string
  predecessor?: string
  checkpoint?: string
}
export type BaselineRequest =
  | { protocol: 1; selected_location_id: string; authorization_epoch: string; request_id: string }
  | { protocol: 1; continuation: string }
  | { protocol: 1; checkpoint: string }

export { convertServerContext as convertBaselineContext }
function reject(): never {
  throw new Error('Invalid baseline wire data')
}
function object(value: unknown, keys: readonly string[]): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return reject()
  const result = value as Record<string, unknown>
  if (Object.keys(result).length !== keys.length || keys.some((key) => !Object.hasOwn(result, key)))
    return reject()
  return result
}
function string(value: unknown, max?: number): string {
  if (typeof value !== 'string' || (max !== undefined && (!value || [...value].length > max)))
    return reject()
  return value
}
function identifier(value: unknown): string {
  return string(value, 36)
}
function uuid(value: unknown): string {
  const result = string(value)
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(result))
    return reject()
  return result
}
function token(value: unknown): string {
  const result = string(value, 512)
  if ([...result].some((character) => character.charCodeAt(0) > 127)) return reject()
  return result
}
function version(value: unknown): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < 1) return reject()
  return value
}
function nullableString(value: unknown): string | null {
  return value === null ? null : string(value)
}
function freeze<T>(value: T): T {
  if (value !== null && typeof value === 'object') {
    for (const child of Object.values(value)) freeze(child)
    Object.freeze(value)
  }
  return value
}
/** Exact UTC microsecond canonicalization. Never normalize invalid calendar dates. */
export function canonicalBaselineTimestamp(value: unknown): string {
  if (typeof value !== 'string') return reject()
  const match =
    /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,6}))?(Z|[+-]\d{2}:\d{2})$/.exec(
      value,
    )
  if (!match) return reject()
  const [year, month, day, hour, minute, second] = match.slice(1, 7).map(Number)
  if (
    year === undefined ||
    month === undefined ||
    day === undefined ||
    hour === undefined ||
    minute === undefined ||
    second === undefined ||
    year < 1 ||
    month < 1 ||
    month > 12 ||
    day < 1 ||
    hour > 23 ||
    minute > 59 ||
    second > 59
  )
    return reject()
  const date = new Date(0)
  date.setUTCFullYear(year, month - 1, day)
  date.setUTCHours(hour, minute, second, 0)
  if (
    date.getUTCFullYear() !== year ||
    date.getUTCMonth() !== month - 1 ||
    date.getUTCDate() !== day
  )
    return reject()
  const zone = match[8]!
  if (zone !== 'Z') {
    const hours = Number(zone.slice(1, 3)),
      minutes = Number(zone.slice(4, 6))
    if (hours > 23 || minutes > 59) return reject()
    date.setTime(date.getTime() - (zone[0] === '+' ? 1 : -1) * (hours * 60 + minutes) * 60_000)
  }
  if (date.getUTCFullYear() < 1 || date.getUTCFullYear() > 9999) return reject()
  return `${date.toISOString().slice(0, 19)}.${(match[7] ?? '').padEnd(6, '0')}Z`
}
const common = ['organization_id', 'location_id', 'created_at', 'updated_at', 'version']
const fields = {
  customer: ['customer_id', 'display_name', 'email', 'phone'],
  bicycle: ['bicycle_id', 'customer_id', 'brand', 'model', 'bicycle_type', 'wheel_size', 'notes'],
  service_order: [
    'order_id',
    'customer_id',
    'bicycle_id',
    'state',
    'reported_problem',
    'intake_condition',
    'accessories',
    'priority',
    'diagnosis',
  ],
} as const
const states = [
  'INTAKE',
  'DIAGNOSIS',
  'AUTHORIZED',
  'REJECTED',
  'IN_PROGRESS',
  'WAITING_FOR_PARTS',
  'READY',
  'CLOSED',
  'CANCELLED',
]
export function validateBaselineRecord(
  value: unknown,
  context: VerifiedAccessContext,
): BaselineRecord {
  const envelope = object(value, ['entity_type', 'entity_id', 'entity_version', 'payload'])
  const type = envelope.entity_type
  if (type !== 'customer' && type !== 'bicycle' && type !== 'service_order') return reject()
  if (!context.capabilities.includes(entityCapability(type, 'read'))) return reject()
  const raw = object(envelope.payload, [...common, ...fields[type]])
  const payload: Record<string, unknown> = {
    organization_id: identifier(raw.organization_id),
    location_id: identifier(raw.location_id),
    created_at: canonicalBaselineTimestamp(raw.created_at),
    updated_at: canonicalBaselineTimestamp(raw.updated_at),
    version: version(raw.version),
  }
  if (
    payload.organization_id !== context.principal.organizationId ||
    payload.location_id !== context.selectedLocationId
  )
    return reject()
  for (const field of fields[type]) {
    if (field.endsWith('_id'))
      payload[field] =
        field === 'bicycle_id' && type === 'service_order' && raw[field] === null
          ? null
          : identifier(raw[field])
    else if (['display_name', 'brand', 'state', 'reported_problem', 'priority'].includes(field))
      payload[field] = string(raw[field])
    else payload[field] = nullableString(raw[field])
  }
  if (type === 'service_order' && !states.includes(payload.state as string)) return reject()
  const entityId = identifier(envelope.entity_id),
    entityVersion = version(envelope.entity_version)
  if (
    payload[type === 'service_order' ? 'order_id' : `${type}_id`] !== entityId ||
    payload.version !== entityVersion
  )
    return reject()
  return { entity_type: type, entity_id: entityId, entity_version: entityVersion, payload }
}
function context(value: unknown, binding: BaselineBinding, now: number): BaselineWireContext {
  const converted = convertServerContext(value, binding.identity, now)
  if (
    contextKey(converted) !== contextKey(binding.context) ||
    converted.snapshotProtocol !== binding.context.snapshotProtocol
  )
    return reject()
  // Copy only after closed conversion; no modification of null protocol or server evidence.
  return structuredClone(value) as BaselineWireContext
}
export function validateBaselineRequest(kind: BaselineKind, body: string): BaselineRequest {
  if (
    typeof body !== 'string' ||
    new TextEncoder().encode(body).byteLength > BASELINE_CONTROL_LIMIT
  )
    return reject()
  let raw: unknown
  try {
    raw = JSON.parse(body)
  } catch {
    return reject()
  }
  const value = object(
    raw,
    kind === 'start'
      ? ['protocol', 'selected_location_id', 'authorization_epoch', 'request_id']
      : kind === 'activation'
        ? ['protocol', 'checkpoint']
        : ['protocol', 'continuation'],
  )
  if (value.protocol !== 1) return reject()
  if (kind === 'start')
    return freeze({
      protocol: 1,
      selected_location_id: identifier(value.selected_location_id),
      authorization_epoch: string(value.authorization_epoch, 256),
      request_id: uuid(value.request_id),
    })
  if (kind === 'activation') return freeze({ protocol: 1, checkpoint: token(value.checkpoint) })
  return freeze({ protocol: 1, continuation: token(value.continuation) })
}
export function validateBaselineResponse<K extends BaselineKind>(
  kind: K,
  value: unknown,
  binding: BaselineBinding,
  now: number,
): BaselineResponseMap[K] {
  const base = ['protocol', 'baseline_id']
  const keys =
    kind === 'start'
      ? [...base, 'context', 'continuation', 'expires_at']
      : kind === 'activation'
        ? [...base, 'authorization_epoch', 'checkpoint', 'context']
        : [
            ...base,
            'authorization_epoch',
            'predecessor',
            'continuation',
            ...(kind === 'finalize' ? [] : ['page_id', 'records', 'phase']),
            ...(kind === 'delta' ? ['completion'] : []),
          ]
  const raw = object(value, keys)
  if (raw.protocol !== 1) return reject()
  const baselineId = uuid(raw.baseline_id)
  if (
    (kind !== 'start' && !binding.baselineId) ||
    (binding.baselineId !== undefined && baselineId !== binding.baselineId)
  )
    return reject()
  let result: BaselineResponseMap[BaselineKind]
  if (kind === 'start') {
    const expiresAt = canonicalBaselineTimestamp(raw.expires_at)
    if (Date.parse(expiresAt) <= now) return reject()
    result = {
      protocol: 1,
      baseline_id: baselineId,
      context: context(raw.context, binding, now),
      continuation: token(raw.continuation),
      expires_at: raw.expires_at as string,
    }
  } else {
    const epoch = string(raw.authorization_epoch, 256)
    if (epoch !== binding.context.authorizationEpoch) return reject()
    if (kind === 'activation') {
      const checkpoint = token(raw.checkpoint)
      if (checkpoint !== binding.checkpoint) return reject()
      result = {
        protocol: 1,
        baseline_id: baselineId,
        authorization_epoch: epoch,
        checkpoint,
        context: context(raw.context, binding, now),
      }
    } else {
      const predecessor = token(raw.predecessor),
        continuation = token(raw.continuation)
      if (predecessor !== binding.predecessor || predecessor === continuation) return reject()
      const response: BaselineFinalizeResponse = {
        protocol: 1,
        baseline_id: baselineId,
        authorization_epoch: epoch,
        predecessor,
        continuation,
      }
      if (kind === 'finalize') result = response
      else {
        if (!Array.isArray(raw.records) || raw.records.length > 100) return reject()
        const page = {
          ...response,
          page_id: identifier(raw.page_id),
          records: raw.records.map((record) => {
            validateBaselineRecord(record, binding.context)
            // Retain exact validated wire spelling for bounded receipt/replay.
            // The durable merge normalizes timestamps independently.
            return structuredClone(record) as BaselineRecord
          }),
        }
        if (kind === 'scan') {
          if (raw.phase !== 'scan' && raw.phase !== 'scan_complete') return reject()
          result = { ...page, phase: raw.phase }
        } else {
          if (raw.phase !== 'catching_up' && raw.phase !== 'complete') return reject()
          let completion: BaselineCompletion | null = null
          if (raw.phase === 'catching_up') {
            if (raw.completion !== null) return reject()
          } else {
            const complete = object(raw.completion, [
              'baseline_id',
              'authorization_epoch',
              'checkpoint',
            ])
            if (
              complete.baseline_id !== baselineId ||
              complete.authorization_epoch !== epoch ||
              complete.checkpoint !== continuation
            )
              return reject()
            completion = {
              baseline_id: baselineId,
              authorization_epoch: epoch,
              checkpoint: continuation,
            }
          }
          result = { ...page, phase: raw.phase, completion }
        }
      }
    }
  }
  return freeze(result) as BaselineResponseMap[K]
}

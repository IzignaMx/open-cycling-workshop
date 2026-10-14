import {
  canonicalBaselineTimestamp,
  validateBaselineRequest,
  validateBaselineResponse,
} from './baseline-wire.js'
import { contextKey, principalKey, validateVerifiedContext } from './context.js'
import { canonicalJson } from './operations.js'
import type { CachePartition, ContextTicket, VerifiedAccessContext } from './types.js'

export type BaselinePhase =
  'start_pending' | 'scan' | 'finalize_pending' | 'catching_up' | 'activation_pending' | 'active'
export type BaselineAction = 'start' | 'scan' | 'finalize' | 'delta' | 'activation'
export interface BaselineRequest {
  kind: BaselineAction
  body: string
}
export interface BaselineMetadata {
  format: 1
  binding: string
  origin: ContextTicket
  owner: ContextTicket
  requestId: string
  startBody: string
  startResponse: string | null
  baselineId: string | null
  expiresAt: string | null
  phase: BaselinePhase
  next: BaselineRequest | null
  checkpoint: string | null
  receipt: { kind: BaselineAction; predecessor: string; response: string } | null
  retryCount: number
  hold: { reason: string; retryAt: number | null; attempts: number } | null
}
const keys = [
  'format',
  'binding',
  'origin',
  'owner',
  'requestId',
  'startBody',
  'startResponse',
  'baselineId',
  'expiresAt',
  'phase',
  'next',
  'checkpoint',
  'receipt',
  'retryCount',
  'hold',
]
const phases: Record<BaselinePhase, BaselineAction | null> = {
  start_pending: 'start',
  scan: 'scan',
  finalize_pending: 'finalize',
  catching_up: 'delta',
  activation_pending: 'activation',
  active: null,
}
export function boundedJson(value: string, limit: number): unknown {
  if (typeof value !== 'string' || new TextEncoder().encode(value).length > limit)
    throw new Error('Invalid bounded baseline metadata')
  return JSON.parse(value) as unknown
}
function object(value: unknown, expected: readonly string[]): Record<string, unknown> {
  if (
    !value ||
    typeof value !== 'object' ||
    Array.isArray(value) ||
    Object.keys(value).length !== expected.length ||
    expected.some((key) => !Object.hasOwn(value, key))
  )
    throw new Error('Invalid baseline metadata shape')
  return value as Record<string, unknown>
}
function ticket(value: ContextTicket): void {
  object(value, [
    'deviceGeneration',
    'tabAttemptId',
    'principalKey',
    'partitionId',
    'authorizationEpoch',
  ])
  if (
    !Number.isSafeInteger(value.deviceGeneration) ||
    value.deviceGeneration < 0 ||
    [value.tabAttemptId, value.principalKey, value.partitionId, value.authorizationEpoch].some(
      (value) => typeof value !== 'string' || !value,
    )
  )
    throw new Error('Invalid baseline owner')
}
function token(value: unknown): value is string {
  return (
    typeof value === 'string' &&
    value.length > 0 &&
    value.length <= 512 &&
    [...value].every((character) => character.charCodeAt(0) <= 127)
  )
}
function storedContext(value: unknown, expected: VerifiedAccessContext): VerifiedAccessContext {
  const raw = object(value, [
    'protocol',
    'principal',
    'account_location_id',
    'selected_location_id',
    'capabilities',
    'authorization_epoch',
    'policy_revision',
    'verified_at',
    'offline_until',
    'snapshot_protocol',
  ])
  const principal = object(raw.principal, ['api_realm', 'organization_id', 'user_id'])
  const id = (value: unknown): string => {
    if (typeof value !== 'string' || !value || [...value].length > 36 || value.includes('\0'))
      throw new Error('Invalid stored context identity')
    return value
  }
  if (
    raw.protocol !== 1 ||
    principal.api_realm !== null ||
    !Array.isArray(raw.capabilities) ||
    raw.capabilities.some(
      (grant) =>
        typeof grant !== 'string' || !/^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$/.test(grant),
    ) ||
    typeof raw.authorization_epoch !== 'string' ||
    raw.authorization_epoch.length > 256 ||
    typeof raw.policy_revision !== 'string' ||
    (raw.snapshot_protocol !== null && raw.snapshot_protocol !== 'baseline-v1')
  )
    throw new Error('Invalid original context schema')
  const context: VerifiedAccessContext = {
    protocol: 1,
    principal: {
      apiRealm: expected.principal.apiRealm,
      organizationId: id(principal.organization_id),
      userId: id(principal.user_id),
    },
    accountLocationId: raw.account_location_id === null ? null : id(raw.account_location_id),
    selectedLocationId: id(raw.selected_location_id),
    capabilities: raw.capabilities as string[],
    authorizationEpoch: raw.authorization_epoch,
    policyRevision: raw.policy_revision,
    verifiedAt: canonicalBaselineTimestamp(raw.verified_at),
    offlineUntil: canonicalBaselineTimestamp(raw.offline_until),
    snapshotProtocol: raw.snapshot_protocol,
  }
  // Validate the original bounded lease at its own verification time. Retained
  // evidence never renews a lease, and initial completion can outlive start expiry.
  validateVerifiedContext(context, Date.parse(context.verifiedAt))
  if (
    contextKey(context) !== contextKey(expected) ||
    context.snapshotProtocol !== expected.snapshotProtocol
  )
    throw new Error('Contradictory original context')
  return context
}
export function validateBaselineMetadata(
  partition: CachePartition,
  context: VerifiedAccessContext,
): BaselineMetadata {
  const value = partition.baseline
  object(value, keys)
  if (
    !value ||
    value.format !== 1 ||
    value.binding !== contextKey(context) ||
    partition.principalKey !== principalKey(context.principal) ||
    partition.locationId !== context.selectedLocationId ||
    partition.authorizationEpoch !== context.authorizationEpoch ||
    partition.policyRevision !== context.policyRevision ||
    !Object.hasOwn(phases, value.phase)
  )
    throw new Error('Invalid baseline binding or format')
  ticket(value.origin)
  ticket(value.owner)
  for (const owner of [value.origin, value.owner]) {
    if (
      owner.partitionId !== partition.partitionId ||
      owner.principalKey !== partition.principalKey ||
      owner.authorizationEpoch !== partition.authorizationEpoch
    )
      throw new Error('Invalid baseline partition binding')
  }
  validateBaselineRequest('start', value.startBody)
  const start = object(boundedJson(value.startBody, 16384), [
    'protocol',
    'selected_location_id',
    'authorization_epoch',
    'request_id',
  ])
  if (
    start.protocol !== 1 ||
    start.selected_location_id !== context.selectedLocationId ||
    start.authorization_epoch !== context.authorizationEpoch ||
    start.request_id !== value.requestId ||
    !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(value.requestId)
  )
    throw new Error('Invalid baseline start identity')
  if (value.phase === 'start_pending') {
    if (
      value.startResponse !== null ||
      value.baselineId !== null ||
      value.expiresAt !== null ||
      value.checkpoint !== null ||
      value.receipt !== null
    )
      throw new Error('Invalid pending start')
  } else {
    if (
      typeof value.startResponse !== 'string' ||
      !value.baselineId ||
      !value.expiresAt ||
      !Number.isFinite(Date.parse(value.expiresAt))
    )
      throw new Error('Missing baseline start evidence')
    const response = object(boundedJson(value.startResponse, 16384), [
      'protocol',
      'baseline_id',
      'context',
      'continuation',
      'expires_at',
    ])
    if (
      response.protocol !== 1 ||
      response.baseline_id !== value.baselineId ||
      response.expires_at !== value.expiresAt ||
      !token(response.continuation)
    )
      throw new Error('Contradictory baseline start evidence')
    if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(value.baselineId))
      throw new Error('Invalid original baseline ID')
    const original = storedContext(response.context, context)
    const expiry = canonicalBaselineTimestamp(response.expires_at)
    if (
      Date.parse(expiry) <= Date.parse(original.verifiedAt) ||
      Date.parse(expiry) > Date.parse(original.offlineUntil)
    )
      throw new Error('Invalid original baseline deadline')
  }
  if (value.phase === 'active') {
    if (value.next !== null || !token(value.checkpoint) || partition.cursor !== value.checkpoint)
      throw new Error('Invalid baseline completion')
  } else {
    const next = object(value.next, ['kind', 'body'])
    if (next.kind !== phases[value.phase] || typeof next.body !== 'string')
      throw new Error('Invalid baseline next phase')
    validateBaselineRequest(next.kind as BaselineAction, next.body)
    const body = object(
      boundedJson(next.body, 16384),
      value.phase === 'start_pending'
        ? ['protocol', 'selected_location_id', 'authorization_epoch', 'request_id']
        : value.phase === 'activation_pending'
          ? ['protocol', 'checkpoint']
          : ['protocol', 'continuation'],
    )
    if (
      body.protocol !== 1 ||
      (value.phase === 'start_pending'
        ? next.body !== value.startBody
        : !token(body[value.phase === 'activation_pending' ? 'checkpoint' : 'continuation']))
    )
      throw new Error('Invalid baseline next request')
    if (value.phase === 'activation_pending' && body.checkpoint !== value.checkpoint)
      throw new Error('Invalid activation checkpoint')
  }
  if (!['active', 'activation_pending'].includes(value.phase) && value.checkpoint !== null)
    throw new Error('Premature baseline checkpoint')
  if (value.receipt !== null) {
    object(value.receipt, ['kind', 'predecessor', 'response'])
    if (
      !['scan', 'finalize', 'delta'].includes(value.receipt.kind) ||
      !token(value.receipt.predecessor) ||
      typeof value.receipt.response !== 'string'
    )
      throw new Error('Invalid baseline receipt')
    const receipt = boundedJson(value.receipt.response, 1048576) as Record<string, unknown>
    const validated = validateBaselineResponse(
      value.receipt.kind as 'scan' | 'finalize' | 'delta',
      receipt,
      {
        context,
        identity: {
          ...context.principal,
          selectedLocationId: context.selectedLocationId,
          deviceGeneration: value.owner.deviceGeneration,
          tabAttemptId: value.owner.tabAttemptId,
          sessionHandle: 'retained-evidence',
        },
        baselineId: value.baselineId!,
        predecessor: value.receipt.predecessor,
      },
      Date.parse(context.verifiedAt),
    )
    if (canonicalJson(validated) !== canonicalJson(receipt))
      throw new Error('Noncanonical retained receipt')
    if (
      value.next &&
      value.phase !== 'activation_pending' &&
      JSON.parse(value.next.body).continuation !== validated.continuation
    )
      throw new Error('Receipt does not support next continuation')
    if (
      (value.phase === 'scan' && (value.receipt.kind !== 'scan' || receipt.phase !== 'scan')) ||
      (value.phase === 'finalize_pending' &&
        (value.receipt.kind !== 'scan' || receipt.phase !== 'scan_complete')) ||
      (value.phase === 'catching_up' &&
        value.receipt.kind !== 'finalize' &&
        (value.receipt.kind !== 'delta' || receipt.phase !== 'catching_up'))
    )
      throw new Error('Receipt does not support current phase')
    if (
      !receipt ||
      receipt.predecessor !== value.receipt.predecessor ||
      receipt.baseline_id !== value.baselineId ||
      receipt.authorization_epoch !== context.authorizationEpoch
    )
      throw new Error('Contradictory baseline receipt')
    if (['active', 'activation_pending'].includes(value.phase)) {
      const completion = receipt.completion as Record<string, unknown> | null
      if (
        value.receipt.kind !== 'delta' ||
        receipt.phase !== 'complete' ||
        receipt.continuation !== value.checkpoint ||
        !completion ||
        completion.checkpoint !== value.checkpoint ||
        completion.baseline_id !== value.baselineId ||
        completion.authorization_epoch !== context.authorizationEpoch
      )
        throw new Error('Missing complete baseline receipt')
    }
  }
  if (
    value.receipt === null &&
    value.phase === 'scan' &&
    JSON.parse(value.next!.body).continuation !== JSON.parse(value.startResponse!).continuation
  )
    throw new Error('Start does not support first scan')
  if (
    ['finalize_pending', 'catching_up', 'active', 'activation_pending'].includes(value.phase) &&
    value.receipt === null
  )
    throw new Error('Missing baseline completion evidence')
  if (!Number.isSafeInteger(value.retryCount) || value.retryCount < 0 || value.retryCount > 100)
    throw new Error('Invalid baseline retry count')
  if (value.hold !== null) {
    object(value.hold, ['reason', 'retryAt', 'attempts'])
    if (
      typeof value.hold.reason !== 'string' ||
      !value.hold.reason ||
      value.hold.reason.length > 80 ||
      !Number.isSafeInteger(value.hold.attempts) ||
      value.hold.attempts < 1 ||
      (value.hold.retryAt !== null && !Number.isFinite(value.hold.retryAt))
    )
      throw new Error('Invalid baseline hold')
  }
  return value
}
export function completedBaseline(
  partition: CachePartition,
  context: VerifiedAccessContext,
): boolean {
  try {
    const value = validateBaselineMetadata(partition, context)
    return (
      context.snapshotProtocol === 'baseline-v1' &&
      partition.baselineComplete &&
      partition.status === 'active' &&
      value.phase === 'active' &&
      value.hold === null
    )
  } catch {
    return false
  }
}

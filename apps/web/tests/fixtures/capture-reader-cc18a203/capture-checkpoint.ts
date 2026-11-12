import type { CaptureWriter, DeviceControl } from './types.js'
import type {
  CaptureCheckpoint,
  CaptureCheckpointCommand,
  CaptureDraftContent,
  ChannelCheckpoint,
  ContentProjection,
} from './capture-checkpoint-types.js'
export const CAPTURE_TTL_MS = 86_400_000
export const MAX_CONTENT_UTF8_BYTES = 65_536
export const MAINTENANCE_PAGE_SIZE = 64
export const validInteger = (value: unknown): value is number =>
  typeof value === 'number' && Number.isSafeInteger(value) && value >= 0
export const validUUID = (value: unknown): value is string =>
  typeof value === 'string' &&
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(value)
export const validHash = (value: unknown): value is string =>
  typeof value === 'string' && /^[0-9a-f]{64}$/.test(value)
const record = (v: unknown): v is Record<string, unknown> =>
  v !== null && typeof v === 'object' && !Array.isArray(v)
const exact = (v: Record<string, unknown>, keys: string[]) =>
  Object.keys(v).length === keys.length && keys.every((k) => Object.hasOwn(v, k))
function strings(v: unknown, keys: string[]): boolean {
  return record(v) && exact(v, keys) && keys.every((k) => typeof v[k] === 'string')
}
export function validProjection(v: unknown): v is ContentProjection {
  if (!record(v) || !record(v.draft)) return false
  if (v.channel === 'customer')
    return exact(v, ['channel', 'draft']) && strings(v.draft, ['displayName', 'email', 'phone'])
  return (
    v.channel === 'order' &&
    exact(v, ['channel', 'draft', 'retainedSelection']) &&
    strings(v.retainedSelection, ['customerId', 'priority']) &&
    exact(v.draft, [
      'customerId',
      'priority',
      'reportedProblem',
      'intakeCondition',
      'accessories',
      'withBicycle',
      'brand',
      'model',
    ]) &&
    Object.entries(v.draft).every(([key, value]) =>
      key === 'withBicycle' ? typeof value === 'boolean' : typeof value === 'string',
    )
  )
}
export function projectionBytes(v: ContentProjection): number {
  return new TextEncoder().encode(JSON.stringify(v)).length
}
export function emptyChannel(revision = 0): ChannelCheckpoint {
  return {
    revision,
    state: 'EMPTY',
    attemptId: null,
    contentStartedAt: null,
    contentExpiresAt: null,
  }
}
function validChannel(v: unknown): v is ChannelCheckpoint {
  if (
    !record(v) ||
    !exact(v, ['revision', 'state', 'attemptId', 'contentStartedAt', 'contentExpiresAt']) ||
    !validInteger(v.revision) ||
    typeof v.state !== 'string' ||
    !['EMPTY', 'UNSENT', 'PROTECTED', 'UNAVAILABLE'].includes(v.state)
  )
    return false
  if (v.attemptId !== null && !validUUID(v.attemptId)) return false
  if (v.state === 'PROTECTED' ? v.attemptId === null : v.attemptId !== null) return false
  if (v.state === 'UNSENT' && v.contentStartedAt === null) return false
  if (v.state === 'EMPTY' && v.contentStartedAt !== null) return false
  return (
    (v.contentStartedAt === null && v.contentExpiresAt === null) ||
    (validInteger(v.contentStartedAt) &&
      validInteger(v.contentExpiresAt) &&
      v.contentExpiresAt === v.contentStartedAt + CAPTURE_TTL_MS)
  )
}
export function validCheckpoint(v: unknown): v is CaptureCheckpoint {
  return (
    record(v) &&
    exact(v, [
      'format',
      'writerEpoch',
      'checkpointId',
      'bindingKey',
      'scopeKey',
      'generation',
      'closed',
      'observedAt',
      'customer',
      'order',
    ]) &&
    v.format === 1 &&
    validUUID(v.checkpointId) &&
    validUUID(v.writerEpoch) &&
    validHash(v.bindingKey) &&
    validHash(v.scopeKey) &&
    validUUID(v.generation) &&
    typeof v.closed === 'boolean' &&
    validInteger(v.observedAt) &&
    validChannel(v.customer) &&
    validChannel(v.order)
  )
}
export function contentProjection(v: CaptureDraftContent): ContentProjection {
  return v.channel === 'customer'
    ? { channel: 'customer', draft: v.draft }
    : { channel: 'order', draft: v.draft, retainedSelection: v.retainedSelection }
}
export function validContent(v: unknown): v is CaptureDraftContent {
  if (
    !record(v) ||
    !exact(v, [
      'format',
      'checkpointId',
      'generation',
      'channel',
      'revision',
      'firstPersistedAt',
      'expiresAt',
      'draft',
      ...(v.channel === 'order' ? ['retainedSelection'] : []),
    ])
  )
    return false
  if (
    v.format !== 1 ||
    !validUUID(v.checkpointId) ||
    !validUUID(v.generation) ||
    !validInteger(v.revision) ||
    !validInteger(v.firstPersistedAt) ||
    !validInteger(v.expiresAt) ||
    v.expiresAt !== v.firstPersistedAt + CAPTURE_TTL_MS
  )
    return false
  const projection =
    v.channel === 'order'
      ? { channel: v.channel, draft: v.draft, retainedSelection: v.retainedSelection }
      : { channel: v.channel, draft: v.draft }
  return validProjection(projection) && projectionBytes(projection) <= MAX_CONTENT_UTF8_BYTES
}
export function frozenCopy<T>(value: T): T {
  const copy = structuredClone(value)
  const freeze = (v: unknown): void => {
    if (v && typeof v === 'object') {
      Object.values(v).forEach(freeze)
      Object.freeze(v)
    }
  }
  freeze(copy)
  return copy
}

export function validCommandShape(value: unknown): value is CaptureCheckpointCommand {
  if (!record(value)) return false
  const identity = ['kind', 'checkpointId', 'scope']
  const expected = [...identity, 'generation']
  const cas = [...expected, 'channel', 'expectedRevision']
  switch (value.kind) {
    case 'enroll':
      return exact(value, expected)
    case 'load':
      return exact(value, identity)
    case 'save':
      return exact(value, [...cas, 'content'])
    case 'protect':
      return exact(value, [...cas, 'attemptId'])
    case 'settle':
      return exact(value, [...cas, 'attemptId', 'outcome', 'content'])
    case 'retireScope':
      return exact(value, [...expected, 'nextGeneration'])
    default:
      return false
  }
}

/** Healthy only when every committed journal append is covered by this exact writer epoch. */
export function writerEpoch(
  control: Pick<DeviceControl, 'localSequence' | 'captureWriter'>,
): string | null {
  const writer: unknown = control.captureWriter
  return validInteger(control.localSequence) &&
    record(writer) &&
    exact(writer, ['format', 'epoch', 'coveredSequence']) &&
    writer.format === 1 &&
    validUUID(writer.epoch) &&
    validInteger(writer.coveredSequence) &&
    writer.coveredSequence === control.localSequence
    ? writer.epoch
    : null
}
export function newCaptureWriter(
  control: Pick<DeviceControl, 'localSequence'>,
  epoch: string,
): CaptureWriter {
  if (!validInteger(control.localSequence) || !validUUID(epoch))
    throw new Error('Invalid capture writer metadata')
  return { format: 1, epoch, coveredSequence: control.localSequence }
}

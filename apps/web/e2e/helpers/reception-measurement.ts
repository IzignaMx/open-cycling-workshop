// Test-only validation and aggregation of observed reception phases.
export const receptionPhases = [
  'draftDurable',
  'reloadRecovered',
  'localCommit',
  'serverConfirmed',
] as const

export type ReceptionPhase = (typeof receptionPhases)[number]
export type ReceptionOutcome = 'complete' | 'failed' | 'incomplete'
export type ReceptionFailure = ReceptionPhase | 'verification'
export type PhaseDuration = { startMs: number; endMs: number; durationMs: number }
export type ReceptionIdentities = {
  orderId: string
  bicycleId: string
  orderMutationId: string
  bicycleMutationId: string
}
export type ReceptionSample = {
  trial: number
  phases: Partial<Record<ReceptionPhase, PhaseDuration>>
} & (
  | { status: 'passed'; identities: ReceptionIdentities }
  | { status: 'failed'; reason: ReceptionFailure; identities?: Partial<ReceptionIdentities> }
)
type DatasetCounts = { customers: number; bicycles: number; orders: number }
export type ReceptionMetadata = {
  browserVersion: string
  appSha256: string
  swSha256: string
  datasetBefore: DatasetCounts
  datasetAfter: DatasetCounts | null
}

const planned = 3
const identityFields = ['orderId', 'bicycleId', 'orderMutationId', 'bicycleMutationId'] as const
const uuidV7 = /^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/
const hash = /^[0-9a-f]{64}$/

function closedRecord(
  value: object,
  required: readonly string[],
  optional: readonly string[] = [],
) {
  if (
    !value ||
    Object.getPrototypeOf(value) !== Object.prototype ||
    !required.every((key) => Object.hasOwn(value, key)) ||
    !Reflect.ownKeys(value).every(
      (key) => typeof key === 'string' && (required.includes(key) || optional.includes(key)),
    )
  )
    throw new Error('Unexpected reception receipt fields')
}

export function phaseDuration(startMs: number, endMs: number): PhaseDuration {
  if (!Number.isFinite(startMs) || startMs < 0 || !Number.isFinite(endMs) || endMs < startMs)
    throw new Error('Invalid monotonic reception observation')
  return { startMs, endMs, durationMs: endMs - startMs }
}

function validateDataset(dataset: DatasetCounts) {
  closedRecord(dataset, ['customers', 'bicycles', 'orders'])
  if (!Object.values(dataset).every((value) => Number.isSafeInteger(value) && value >= 0))
    throw new Error('Invalid reception dataset counts')
}

export function buildReceipt(samples: readonly ReceptionSample[], metadata: ReceptionMetadata) {
  closedRecord(metadata, [
    'browserVersion',
    'appSha256',
    'swSha256',
    'datasetBefore',
    'datasetAfter',
  ])
  if (
    typeof metadata.browserVersion !== 'string' ||
    !/^\d{1,5}(?:\.\d{1,5}){1,3}$/.test(metadata.browserVersion) ||
    typeof metadata.appSha256 !== 'string' ||
    !hash.test(metadata.appSha256) ||
    typeof metadata.swSha256 !== 'string' ||
    !hash.test(metadata.swSha256)
  )
    throw new Error('Invalid reception build/browser identity')
  validateDataset(metadata.datasetBefore)
  if (metadata.datasetAfter !== null) validateDataset(metadata.datasetAfter)
  if (samples.length > planned) throw new Error('Too many reception attempts')

  const usedIds = new Set<string>()
  const successful: Extract<ReceptionSample, { status: 'passed' }>[] = []
  let previousEnd = 0
  for (const [index, sample] of samples.entries()) {
    if (!sample || sample.trial !== index + 1 || !['passed', 'failed'].includes(sample.status))
      throw new Error('Invalid reception trial sequence')
    if (sample.status === 'passed') {
      closedRecord(sample, ['trial', 'phases', 'status', 'identities'])
    } else {
      closedRecord(sample, ['trial', 'phases', 'status', 'reason'], ['identities'])
      if (sample.reason !== 'verification' && !receptionPhases.includes(sample.reason))
        throw new Error('Unknown reception failure stage')
    }
    closedRecord(sample.phases, sample.status === 'passed' ? receptionPhases : [], receptionPhases)
    let missing = false
    for (const phase of receptionPhases) {
      const observed = sample.phases[phase]
      if (!Object.hasOwn(sample.phases, phase)) {
        missing = true
        continue
      }
      if (!observed || missing) throw new Error('Missing reception phase before observed phase')
      closedRecord(observed, ['startMs', 'endMs', 'durationMs'])
      const { startMs, endMs } = observed
      const expected = phaseDuration(startMs, endMs)
      if (expected.durationMs !== observed.durationMs)
        throw new Error('Inconsistent reception duration')
      if (phase === 'serverConfirmed') {
        // Confirmation is cumulative from the same submit action, not additive.
        if (startMs !== sample.phases.localCommit?.startMs || endMs < previousEnd)
          throw new Error('Inconsistent overlapping submit observations')
      } else if (startMs < previousEnd) throw new Error('Overlapping sequential reception phases')
      previousEnd = endMs
    }
    if (sample.status === 'passed' || Object.hasOwn(sample, 'identities')) {
      const identities = sample.identities!
      closedRecord(identities, sample.status === 'passed' ? identityFields : [], identityFields)
      for (const id of Object.values(identities)) {
        if (typeof id !== 'string' || !uuidV7.test(id))
          throw new Error('Invalid reception identity')
        // Preserve the evidence if a duplicate caused a failed attempt. A
        // later passed attempt cannot borrow any already observed identity.
        if (sample.status === 'passed' && usedIds.has(id))
          throw new Error('Duplicate identity in a passed reception attempt')
        usedIds.add(id)
      }
    }
    if (sample.status === 'passed') successful.push(sample)
  }

  if (successful.length === planned && metadata.datasetAfter === null)
    throw new Error('Missing final reception dataset after all planned trials passed')
  const failed = samples.length - successful.length
  const outcome: ReceptionOutcome = failed
    ? 'failed'
    : successful.length === planned
      ? 'complete'
      : 'incomplete'
  const summary = successful.length
    ? (Object.fromEntries(
        receptionPhases.map((phase) => {
          const durations = successful.map((sample) => sample.phases[phase]!.durationMs)
          return [phase, { minMs: Math.min(...durations), maxMs: Math.max(...durations) }]
        }),
      ) as Record<ReceptionPhase, { minMs: number; maxMs: number }>)
    : null

  return {
    schema: 1,
    benchmark: 'actual_app_synthetic_connected_loopback',
    readiness: 'not_assessed',
    outcome,
    condition: 'connected_loopback_sequential',
    sampleRegime: 'first_then_repeated_same_session_no_warmup_discard',
    clock: 'node_performance_now_observational_ms',
    metadata: structuredClone(metadata),
    counts: {
      planned,
      attempted: samples.length,
      passed: successful.length,
      failed,
      not_attempted: planned - samples.length,
    },
    samples: structuredClone(samples),
    summary,
  } as const
}

import { contextKey } from './context.js'
import { canonicalJson } from './operations.js'
import type { CachePartition, ContextTicket, VerifiedAccessContext } from './types.js'

/** This noncredential continuity marker is usable only with the exact durable owner. */
export interface RememberedAdmission {
  format: 1
  sessionBindingId: string
  owner: ContextTicket
  binding: string
  datasetIncarnation: string
}
export function createAdmission(
  owner: ContextTicket,
  context: VerifiedAccessContext,
  sessionBindingId: string,
): RememberedAdmission {
  if (
    typeof sessionBindingId !== 'string' ||
    !sessionBindingId.trim() ||
    sessionBindingId.length > 128
  )
    throw new Error('Invalid session admission binding')
  return {
    format: 1,
    sessionBindingId,
    owner: structuredClone(owner),
    binding: contextKey(context),
    datasetIncarnation: context.datasetIncarnation,
  }
}
export function validateAdmission(
  value: unknown,
  partition: CachePartition,
  context: VerifiedAccessContext,
): RememberedAdmission {
  if (!value || typeof value !== 'object' || Array.isArray(value))
    throw new Error('Missing session admission')
  const admission = value as RememberedAdmission
  const expected = ['format', 'sessionBindingId', 'owner', 'binding', 'datasetIncarnation']
  if (
    Object.keys(admission).length !== expected.length ||
    expected.some((key) => !Object.hasOwn(admission, key)) ||
    admission.format !== 1
  )
    throw new Error('Unknown session admission format')
  const owner = admission.owner
  if (
    !owner ||
    Object.keys(owner).length !== 5 ||
    !Number.isSafeInteger(owner.deviceGeneration) ||
    owner.deviceGeneration < 0 ||
    typeof owner.tabAttemptId !== 'string' ||
    !owner.tabAttemptId.trim() ||
    owner.partitionId !== partition.partitionId ||
    owner.principalKey !== partition.principalKey ||
    owner.authorizationEpoch !== partition.authorizationEpoch
  )
    throw new Error('Session admission owner mismatch')
  if (
    canonicalJson(createAdmission(owner, context, admission.sessionBindingId)) !==
    canonicalJson(admission)
  )
    throw new Error('Session admission provenance mismatch')
  return structuredClone(admission)
}

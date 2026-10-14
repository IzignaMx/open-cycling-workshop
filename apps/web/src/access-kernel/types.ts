import type { BaselineMetadata } from './baseline-state.js'
import type { EntityType, MutationEnvelope, MutationResult } from '../sync/types.js'

export interface PrincipalKey {
  apiRealm: string
  organizationId: string
  userId: string
}

/** Input from a future authenticated server-context adapter, NOT browser session metadata.
 * This type/its validation are routing checks, never authentication or cryptographic proof.
 */
export interface VerifiedAccessContext {
  protocol: 1
  principal: PrincipalKey
  accountLocationId: string | null
  selectedLocationId: string
  capabilities: readonly string[]
  authorizationEpoch: string
  policyRevision: string
  verifiedAt: string
  offlineUntil: string
  snapshotProtocol: 'baseline-v1' | null
}

export type ContextState =
  | 'LOCKED'
  | 'VERIFYING'
  | 'BASELINE_REQUIRED'
  | 'SNAPSHOTTING'
  | 'CATCHING_UP'
  | 'READY'
  | 'OFFLINE_READY'
  | 'HELD'

export interface VerificationAttempt {
  deviceGeneration: number
  tabAttemptId: string
}
export interface ContextTicket extends VerificationAttempt {
  principalKey: string
  partitionId: string
  authorizationEpoch: string
}
export interface DeviceControl {
  key: 'device'
  generation: number
  tabAttemptId: string | null
  activePartitionId: string | null
  state: ContextState
  localSequence: number
  observedAt: number
  dispatchAttemptId: string | null
  dispatchScanAfter: number
}
export interface AccessContextRecord {
  partitionId: string
  context: VerifiedAccessContext
}
export interface CachePartition {
  /** Additive non-indexed record format; v1–v5 schema history is unchanged. */
  baseline?: BaselineMetadata
  partitionId: string
  principalKey: string
  locationId: string
  authorizationEpoch: string
  policyRevision: string
  status: 'staging' | 'active' | 'superseded'
  baselineComplete: boolean
  cursor: string | null
}
export interface CacheRecord {
  partitionId: string
  entityType: EntityType
  entityId: string
  version: number
  payload: Record<string, unknown>
}
export interface LocalCommand {
  envelope: MutationEnvelope
  optimistic: Record<string, unknown>
  dependsOn: readonly string[]
  localEvents: readonly Record<string, unknown>[]
}
export interface OwnedOperation {
  mutationId: string
  principalKey: string
  organizationId: string
  locationId: string
  entityType: EntityType
  entityId: string
  authoredUnderEpoch: string
  localSequence: number
  dependsOn: readonly string[]
  envelope: MutationEnvelope
  /** Exact canonical JSON, a collision-free accidental-mutation check, NOT authentication. */
  envelopeCanonical: string
  optimistic: Record<string, unknown>
  createdAt: string
}
export type OperationState =
  | 'pending'
  | 'inflight'
  | 'retryable'
  | 'awaiting_confirmation'
  | 'held_authorization'
  | 'held_dependency'
  | 'held_integrity'
  | 'held_retry'
  | 'rejected'
  | 'applied'
export interface OperationDelivery {
  principalKey: string
  locationId: string
  entityType: EntityType
  entityId: string
  localSequence: number
  dispatchable: 0 | 1
  unresolved: 0 | 1
  blocked: 0 | 1
  resultVersion: number
  mutationId: string
  state: OperationState
  attemptId: string | null
  deviceGeneration: number | null
  attempts: number
  retryAt: number
  result: MutationResult | null
}
export interface OperationEvent {
  sequence?: number
  mutationId: string
  kind: 'local' | 'dispatch' | 'result' | 'held' | 'retry'
  occurredAt: string
  attemptId: string | null
  details: Record<string, unknown>
}
export interface LocalMigrationState {
  key: 'identity-kernel-v5'
  protocol: 1
  legacyPresent: boolean
  legacyAttribution: 'unknown'
}
export interface DispatchBatch {
  ticket: ContextTicket
  attemptId: string
  operations: readonly OwnedOperation[]
}

import type { ConflictRecord } from '../local/types.js'
import type { ConflictMutationResult, MutationEnvelope } from './types.js'

export interface SyncScope {
  organizationId: string
  locationId: string
}

export function syncScopeKey(organizationId: string, locationId: string): string {
  if (!organizationId || !locationId)
    throw new Error('sync scope requires organization and location')
  return `${organizationId}::${locationId}`
}

export function buildScopedConflict(
  scope: SyncScope,
  result: ConflictMutationResult,
  recordedAt: string,
  mutation: MutationEnvelope,
): ConflictRecord {
  if (!['customer', 'bicycle', 'service_order'].includes(mutation.entity_type))
    throw new Error('unknown queued conflict entity type')
  if (
    mutation.mutation_id !== result.mutation_id ||
    mutation.entity_id !== result.entity_id ||
    mutation.organization_id !== scope.organizationId ||
    mutation.location_id !== scope.locationId
  )
    throw new Error('conflict result does not match the queued mutation scope and identity')
  return {
    mutation_id: result.mutation_id,
    organization_id: scope.organizationId,
    location_id: scope.locationId,
    scope_key: syncScopeKey(scope.organizationId, scope.locationId),
    entity_type: mutation.entity_type,
    entity_type_source: 'queued_mutation',
    entity_id: result.entity_id,
    reason: result.error_message,
    recorded_at: recordedAt,
  }
}

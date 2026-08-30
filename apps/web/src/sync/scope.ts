import type { ConflictRecord } from '../local/types.js'
import type { ConflictMutationResult } from './types.js'

export interface SyncScope {
  organizationId: string
  locationId: string
}

export function syncScopeKey(organizationId: string, locationId: string): string {
  if (!organizationId || !locationId) throw new Error('sync scope requires organization and location')
  return `${organizationId}::${locationId}`
}

export function buildScopedConflict(
  scope: SyncScope,
  result: ConflictMutationResult,
  recordedAt: string,
): ConflictRecord {
  return {
    mutation_id: result.mutation_id,
    organization_id: scope.organizationId,
    location_id: scope.locationId,
    scope_key: syncScopeKey(scope.organizationId, scope.locationId),
    entity_type: 'customer',
    entity_id: result.entity_id,
    reason: result.error_message,
    recorded_at: recordedAt,
  }
}

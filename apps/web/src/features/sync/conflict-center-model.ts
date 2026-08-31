import type { ConflictRecord } from '../../local/types.js'

export interface ConflictCenterItem {
  mutationId: string
  entityId: string
  title: string
  description: string
  recordedAt: string
  statusLabel: 'Requiere atención'
}

const ENTITY_TITLES: Record<string, string> = {
  customer: 'Cliente con conflicto',
}

export function buildConflictCenterItems(
  conflicts: readonly ConflictRecord[],
): ConflictCenterItem[] {
  return [...conflicts]
    .map((conflict) => ({
      mutationId: conflict.mutation_id,
      entityId: conflict.entity_id,
      title: ENTITY_TITLES[conflict.entity_type] ?? 'Cambio con conflicto',
      description: conflict.reason,
      recordedAt: conflict.recorded_at,
      statusLabel: 'Requiere atención' as const,
    }))
    .sort((left, right) => right.recordedAt.localeCompare(left.recordedAt))
}

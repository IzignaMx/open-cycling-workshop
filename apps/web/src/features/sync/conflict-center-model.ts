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

const OPERATION_STATE_LABELS: Readonly<Record<string, string>> = {
  awaiting_confirmation: 'Confirmación pendiente',
  held_authorization: 'Autorización pendiente',
  held_dependency: 'Dependencia pendiente',
  held_integrity: 'Integridad pendiente',
  held_retry: 'Reintento pendiente',
  held_recovery: 'Recuperación pendiente',
  rejected: 'Cambio rechazado',
}

/** Presentation only: unknown protocol values never become user-facing labels. */
export function operationStateLabel(state: string): string {
  return Object.hasOwn(OPERATION_STATE_LABELS, state)
    ? OPERATION_STATE_LABELS[state]!
    : 'Requiere atención'
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

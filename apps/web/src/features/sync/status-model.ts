export type SyncVisualState = 'local' | 'offline' | 'syncing' | 'synced' | 'conflict' | 'error'

export interface SyncStatusPresentation {
  label: string
  detail: string
}

const PRESENTATIONS: Record<SyncVisualState, SyncStatusPresentation> = {
  local: {
    label: 'Guardado localmente',
    detail: 'Los cambios están seguros en este dispositivo y pendientes de sincronización.',
  },
  offline: {
    label: 'Sin conexión',
    detail: 'El trabajo sigue guardándose en este dispositivo.',
  },
  syncing: {
    label: 'Sincronizando',
    detail: 'Enviando y recibiendo cambios pendientes.',
  },
  synced: {
    label: 'Sincronizado',
    detail: 'Los cambios locales y del servidor están al día.',
  },
  conflict: {
    label: 'Requiere atención',
    detail: 'Hay cambios que necesitan resolución manual.',
  },
  error: {
    label: 'Sincronización interrumpida',
    detail: 'Los cambios locales se conservan. Se reintentará cuando sea posible.',
  },
}

export function syncStatusPresentation(state: SyncVisualState): SyncStatusPresentation {
  return PRESENTATIONS[state]
}

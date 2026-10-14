import { syncStatusPresentation, type SyncVisualState } from './status-model.js'

export interface SyncStatusProps {
  state: SyncVisualState
}

export function SyncStatus({ state }: SyncStatusProps) {
  const presentation = syncStatusPresentation(state)
  return (
    <section
      data-tone={
        state === 'synced'
          ? 'success'
          : state === 'error'
            ? 'danger'
            : state === 'offline' || state === 'conflict'
              ? 'warning'
              : 'info'
      }
      aria-live="polite"
      aria-label="Estado de sincronización"
      className="sync-banner"
    >
      <strong className="block">{presentation.label}</strong>
      <span className="sync-detail">{presentation.detail}</span>
    </section>
  )
}

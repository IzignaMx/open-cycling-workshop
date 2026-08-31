import { syncStatusPresentation, type SyncVisualState } from './status-model.js'

export interface SyncStatusProps {
  state: SyncVisualState
}

export function SyncStatus({ state }: SyncStatusProps) {
  const presentation = syncStatusPresentation(state)
  return (
    <section
      aria-live="polite"
      aria-label="Estado de sincronización"
      className="rounded-xl border border-[var(--ocwp-color-border)] bg-[var(--ocwp-color-surface)] p-4"
    >
      <strong className="block">{presentation.label}</strong>
      <span className="mt-1 block text-sm leading-6 text-[var(--ocwp-color-muted)]">
        {presentation.detail}
      </span>
    </section>
  )
}

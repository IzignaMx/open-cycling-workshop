import type { ConflictRecord } from '../../local/types.js'
import { buildConflictCenterItems } from './conflict-center-model.js'

export interface ConflictCenterProps {
  conflicts: readonly ConflictRecord[]
  onRefresh(): void | Promise<void>
}

export function ConflictCenter({ conflicts, onRefresh }: ConflictCenterProps) {
  const items = buildConflictCenterItems(conflicts)

  return (
    <section
      aria-labelledby="conflict-center-title"
      className="rounded-2xl border border-[var(--ocwp-color-border)] bg-[var(--ocwp-color-surface)] p-5"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="grid gap-1">
          <h2 id="conflict-center-title" className="text-xl font-semibold">
            Centro de incidencias
          </h2>
          <p className="text-sm leading-6 text-[var(--ocwp-color-muted)]">
            Los conflictos se conservan localmente para que puedan resolverse sin perder cambios.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void onRefresh()}
          className="min-h-11 rounded-[var(--ocwp-radius-sm)] border border-[var(--ocwp-color-border)] px-3 font-semibold focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--ocwp-color-accent)]"
        >
          Actualizar
        </button>
      </div>

      {items.length === 0 ? (
        <p className="mt-4 rounded-xl border border-dashed border-[var(--ocwp-color-border)] p-4 text-sm text-[var(--ocwp-color-muted)]">
          No hay conflictos pendientes.
        </p>
      ) : (
        <ul className="mt-4 grid gap-3" aria-live="polite">
          {items.map((item) => (
            <li
              key={item.mutationId}
              className="rounded-xl border border-[var(--ocwp-color-border)] bg-white p-4"
            >
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="grid gap-1">
                  <strong>{item.title}</strong>
                  <span className="text-sm text-[var(--ocwp-color-muted)]">{item.description}</span>
                </div>
                <span className="text-sm font-semibold text-[var(--ocwp-color-danger)]">
                  {item.statusLabel}
                </span>
              </div>
              <p className="mt-3 text-xs text-[var(--ocwp-color-muted)]">
                ID: <code>{item.entityId}</code>
              </p>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

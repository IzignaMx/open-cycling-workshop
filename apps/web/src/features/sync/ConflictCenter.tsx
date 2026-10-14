import type { ConflictRecord } from '../../local/types.js'
import { buildConflictCenterItems } from './conflict-center-model.js'

export interface ConflictCenterProps {
  conflicts?: readonly ConflictRecord[]
  hasIssues?: boolean
  issues?: readonly {
    mutationId: string
    entityId: string
    entityType: string
    errorMessage: string | null
    state: string
    errorCode: string | null
  }[]
  onRefresh(): void | Promise<void>
}

export function ConflictCenter({
  conflicts = [],
  issues = [],
  hasIssues = false,
  onRefresh,
}: ConflictCenterProps) {
  const items = buildConflictCenterItems(conflicts)

  return (
    <section
      aria-labelledby="conflict-center-title"
      className="rounded-2xl border border-[var(--ocwp-color-border)] bg-[var(--ocwp-color-surface)] p-5"
    >
      <div className="conflict-header">
        <div className="conflict-heading grid gap-1">
          <h2 id="conflict-center-title" className="text-xl font-semibold">
            Centro de incidencias
          </h2>
          <p className="text-sm leading-6 text-[var(--ocwp-color-muted)]">
            Los conflictos se conservan localmente para que puedan resolverse sin perder cambios.
            Sólo se muestran incidencias con tipo verificado y permiso de lectura.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void onRefresh()}
          className="secondary-button conflict-refresh"
        >
          Actualizar
        </button>
      </div>

      {issues.length > 0 ? (
        <ul aria-label="Trabajo conservado">
          {issues.map((issue) => (
            <li key={issue.mutationId}>
              <strong>
                {issue.state === 'held_recovery'
                  ? 'Recuperación pendiente'
                  : issue.state === 'held_integrity'
                    ? 'Integridad pendiente'
                    : issue.entityType === 'customer'
                      ? 'Cliente con conflicto'
                      : issue.entityType === 'bicycle'
                        ? 'Bicicleta con conflicto'
                        : 'Orden de servicio con conflicto'}
              </strong>
              <p>ID: {issue.entityId}</p>
              {issue.errorMessage ? <p>{issue.errorMessage}</p> : null}
              <p>
                Operación {issue.mutationId} · {issue.state}
                {issue.errorCode ? ` · ${issue.errorCode}` : ''}. El original se conserva.
              </p>
            </li>
          ))}
        </ul>
      ) : null}
      {items.length === 0 && issues.length === 0 ? (
        <p className="mt-4 rounded-xl border border-dashed border-[var(--ocwp-color-border)] p-4 text-sm text-[var(--ocwp-color-muted)]">
          {hasIssues
            ? 'No hay incidencias en esta página. Usa Actualizar para volver al inicio.'
            : 'No hay incidencias visibles para tus permisos actuales.'}
        </p>
      ) : (
        <ul className="mt-4 grid gap-3" aria-live="polite">
          {items.map((item) => (
            <li
              key={item.mutationId}
              className="rounded-xl border border-[var(--ocwp-color-border)] bg-[var(--ocwp-color-surface)] p-4"
            >
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="grid gap-1">
                  <strong>{item.title}</strong>
                  <span className="text-sm text-[var(--ocwp-color-muted)]">{item.description}</span>
                </div>
                <span data-tone="danger" className="state-badge">
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

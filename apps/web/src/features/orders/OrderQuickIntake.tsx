import type { CustomerLookupSnapshot } from '../../runtime/customer-lookup.js'
import { type ChangeEvent, type FormEvent, type KeyboardEvent } from 'react'
import { Button } from '@ocwp/ui'
import type { OrderDraftState } from '../draft-state.js'
import type { CaptureFormSnapshot } from '../../runtime/capture-visit.js'

export interface OrderQuickIntakeProps {
  capture: CaptureFormSnapshot<OrderDraftState>
  onEdit<K extends keyof OrderDraftState>(field: K, value: OrderDraftState[K]): void
  onSubmit(): Promise<void>
  lookup?: CustomerLookupSnapshot | null
  onRetrySelected?(): Promise<void>
  onQuery?(value: string): void
  onSearch?(action: 'restart' | 'continue'): Promise<void>
  customers: readonly { customer_id: string; display_name: string }[]
}

export function OrderQuickIntake({
  capture,
  onEdit,
  onSubmit,
  customers,
  lookup,
  onQuery,
  onSearch,
  onRetrySelected,
}: OrderQuickIntakeProps) {
  const { busy, blocked, message } = capture
  const {
    customerId,
    reportedProblem,
    intakeCondition,
    accessories,
    priority,
    withBicycle,
    brand,
    model,
  } = capture.draft
  const page = lookup?.searching ? lookup.matches : customers
  const selected = lookup?.selection.id === customerId ? lookup.selection : null
  const options = [...page]
  if (
    selected?.status === 'available' &&
    selected.customer &&
    !options.some((row) => row.customer_id === customerId)
  )
    options.push(selected.customer)
  const lookupBlocked =
    !!lookup && (!!lookup.busy || !customerId || selected?.status !== 'available')
  const duplicateNames = new Set(
    options
      .filter((row, index) =>
        options.some((other, at) => at !== index && other.display_name === row.display_name),
      )
      .map((row) => row.display_name),
  )
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (lookupBlocked) return
    await onSubmit()
  }

  const inputClass =
    'min-h-11 rounded-lg border border-[var(--ocwp-color-control-border)] bg-[var(--ocwp-color-surface)] px-3'

  return (
    <form
      onSubmit={submit}
      className="grid gap-4"
      aria-describedby="order-intake-status order-recovery-status"
      data-dirty={capture.dirty}
    >
      {lookup ? (
        <div className="grid gap-2">
          <label className="grid gap-1">
            <span className="font-medium">Buscar cliente por nombre</span>
            <input
              type="search"
              value={lookup.query}
              className={inputClass}
              aria-describedby="customer-lookup-status"
              onChange={(event: ChangeEvent<HTMLInputElement>) =>
                onQuery?.(event.currentTarget.value)
              }
              onKeyDown={(event: KeyboardEvent<HTMLInputElement>) => {
                if (event.key === 'Enter') {
                  event.preventDefault()
                  if (!lookup.busy) void onSearch?.('restart')
                }
              }}
            />
          </label>
          <div className="flex flex-wrap gap-2">
            <Button type="button" disabled={lookup.busy} onClick={() => void onSearch?.('restart')}>
              Buscar clientes locales
            </Button>
            <Button
              type="button"
              disabled={lookup.busy || !lookup.pages || lookup.nextAfterId === null}
              onClick={() => void onSearch?.('continue')}
            >
              Continuar búsqueda local
            </Button>
            <Button
              type="button"
              disabled={lookup.busy || !lookup.pages}
              onClick={() => void onSearch?.('restart')}
            >
              Reiniciar búsqueda local
            </Button>
            <Button type="button" onClick={() => onQuery?.('')}>
              Usar lista actual
            </Button>
            {customerId ? (
              <Button type="button" disabled={lookup.busy} onClick={() => void onRetrySelected?.()}>
                Verificar cliente seleccionado
              </Button>
            ) : null}
          </div>
        </div>
      ) : null}
      <label className="grid gap-1">
        <span className="font-medium">Cliente</span>
        <select
          required
          value={customerId}
          onChange={(event: ChangeEvent<HTMLSelectElement>) => {
            onEdit('customerId', event.currentTarget.value)
          }}
          className={inputClass}
        >
          <option value="">Selecciona un cliente…</option>
          {customerId && !options.some((row) => row.customer_id === customerId) ? (
            <option value={customerId}>Cliente seleccionado no disponible</option>
          ) : null}
          {options.map((customer) => (
            <option key={customer.customer_id} value={customer.customer_id}>
              {customer.display_name}
              {lookup?.searching || duplicateNames.has(customer.display_name)
                ? ` · ${customer.customer_id}`
                : ''}
            </option>
          ))}
        </select>
      </label>
      {options.length === 0 && !customerId ? (
        <p className="text-sm text-[var(--ocwp-color-muted)]">
          {lookup?.searching
            ? 'No hay coincidencias en esta página local.'
            : 'Primero registra un cliente con el alta rápida de clientes.'}
        </p>
      ) : null}
      <label className="grid gap-1">
        <span className="font-medium">Problema reportado</span>
        <textarea
          required
          rows={2}
          value={reportedProblem}
          onChange={(event: ChangeEvent<HTMLTextAreaElement>) => {
            onEdit('reportedProblem', event.currentTarget.value)
          }}
          className="min-h-11 rounded-lg border border-[var(--ocwp-color-control-border)] bg-[var(--ocwp-color-surface)] px-3 py-2"
        />
      </label>
      <label className="grid gap-1">
        <span className="font-medium">Condición al recibir</span>
        <input
          value={intakeCondition}
          onChange={(event: ChangeEvent<HTMLInputElement>) => {
            onEdit('intakeCondition', event.currentTarget.value)
          }}
          className={inputClass}
        />
      </label>
      <label className="grid gap-1">
        <span className="font-medium">Accesorios</span>
        <input
          value={accessories}
          onChange={(event: ChangeEvent<HTMLInputElement>) => {
            onEdit('accessories', event.currentTarget.value)
          }}
          className={inputClass}
        />
      </label>
      <label className="grid gap-1">
        <span className="font-medium">Prioridad</span>
        <select
          value={priority}
          onChange={(event: ChangeEvent<HTMLSelectElement>) => {
            onEdit('priority', event.currentTarget.value)
          }}
          className={inputClass}
        >
          <option value="low">Baja</option>
          <option value="normal">Normal</option>
          <option value="high">Alta</option>
          <option value="urgent">Urgente</option>
        </select>
      </label>
      <label className="flex min-h-11 items-center gap-2">
        <input
          type="checkbox"
          checked={withBicycle}
          onChange={(event: ChangeEvent<HTMLInputElement>) => {
            onEdit('withBicycle', event.currentTarget.checked)
          }}
          className="size-5"
        />
        <span className="font-medium">Agregar bicicleta</span>
      </label>
      {withBicycle ? (
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="grid gap-1">
            <span className="font-medium">Marca</span>
            <input
              required
              value={brand}
              onChange={(event: ChangeEvent<HTMLInputElement>) => {
                onEdit('brand', event.currentTarget.value)
              }}
              className={inputClass}
            />
          </label>
          <label className="grid gap-1">
            <span className="font-medium">Modelo</span>
            <input
              value={model}
              onChange={(event: ChangeEvent<HTMLInputElement>) => {
                onEdit('model', event.currentTarget.value)
              }}
              className={inputClass}
            />
          </label>
        </div>
      ) : null}
      <Button type="submit" disabled={blocked || busy || lookupBlocked || options.length === 0}>
        {busy ? 'Guardando…' : 'Guardar orden'}
      </Button>
      <p id="order-intake-status" role="status" aria-live="polite" className="min-h-6 text-sm">
        {message}
      </p>
      {lookup ? (
        <p id="customer-lookup-status" role="status" aria-live="polite">
          {lookup.busy
            ? 'Consultando clientes locales…'
            : (lookup.message ??
              (lookup.pages
                ? `${lookup.matches.length} coincidencias en esta página. ${lookup.pages} páginas revisadas. ${lookup.nextAfterId !== null ? 'Quedan páginas locales por revisar.' : 'Fin de los registros disponibles localmente; puede haber clientes no descargados.'} Si los datos cambiaron, reinicia la búsqueda.`
                : 'Busca por nombre entre los registros disponibles localmente; no es una búsqueda completa del servidor.'))}
          {selected?.status === 'pending'
            ? ' Verificando cliente seleccionado…'
            : selected?.status === 'unavailable' || selected?.status === 'failed'
              ? ' El cliente seleccionado no está disponible; conserva el formulario y elige un cliente disponible.'
              : ''}
        </p>
      ) : null}
      <p id="order-recovery-status" role="status">
        {capture.recoveryMessage}
      </p>
    </form>
  )
}

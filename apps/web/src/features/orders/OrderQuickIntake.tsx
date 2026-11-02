import { type ChangeEvent, type FormEvent } from 'react'
import { Button } from '@ocwp/ui'
import type { OrderDraftState } from '../draft-state.js'
import type { CaptureFormSnapshot } from '../../runtime/capture-visit.js'

export interface OrderQuickIntakeProps {
  capture: CaptureFormSnapshot<OrderDraftState>
  onEdit<K extends keyof OrderDraftState>(field: K, value: OrderDraftState[K]): void
  onSubmit(): Promise<void>
  customers: readonly { customer_id: string; display_name: string }[]
}

export function OrderQuickIntake({ capture, onEdit, onSubmit, customers }: OrderQuickIntakeProps) {
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
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    await onSubmit()
  }

  const inputClass =
    'min-h-11 rounded-lg border border-[var(--ocwp-color-control-border)] bg-[var(--ocwp-color-surface)] px-3'

  return (
    <form
      onSubmit={submit}
      className="grid gap-4"
      aria-describedby="order-intake-status"
      data-dirty={capture.dirty}
    >
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
          {customers.map((customer) => (
            <option key={customer.customer_id} value={customer.customer_id}>
              {customer.display_name}
            </option>
          ))}
        </select>
      </label>
      {customers.length === 0 ? (
        <p className="text-sm text-[var(--ocwp-color-muted)]">
          Primero registra un cliente con el alta rápida de clientes.
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
      <Button type="submit" disabled={blocked || busy || customers.length === 0}>
        {busy ? 'Guardando…' : 'Guardar orden'}
      </Button>
      <p id="order-intake-status" role="status" aria-live="polite" className="min-h-6 text-sm">
        {message}
      </p>
    </form>
  )
}

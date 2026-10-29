import {
  captureFeedback,
  CaptureSubmissionGate,
  type CaptureFeedback,
} from '../capture-feedback.js'
import { captureValidation, type CaptureSubmissionResult } from '../../runtime/capture-outcome.js'
import { useRef, useState, type ChangeEvent, type FormEvent } from 'react'

import { hasOrderDraft } from '../draft-state.js'
import { Button } from '@ocwp/ui'
import { normalizeOrderIntake } from './order-model.js'

export interface OrderQuickIntakeProps {
  customers: readonly { customer_id: string; display_name: string }[]
  onCreateOrder(input: {
    customerId: string
    reportedProblem: string
    intakeCondition: string | null
    accessories: string | null
    priority: string
    brand: string | null
    model: string | null
  }): Promise<CaptureSubmissionResult>
}

export function OrderQuickIntake({ customers, onCreateOrder }: OrderQuickIntakeProps) {
  const [customerId, setCustomerId] = useState('')
  const [retainedSelection, setRetainedSelection] = useState({ customerId: '', priority: 'normal' })
  const [reportedProblem, setReportedProblem] = useState('')
  const [intakeCondition, setIntakeCondition] = useState('')
  const [accessories, setAccessories] = useState('')
  const [priority, setPriority] = useState('normal')
  const [withBicycle, setWithBicycle] = useState(false)
  const [brand, setBrand] = useState('')
  const [model, setModel] = useState('')
  const gate = useRef(new CaptureSubmissionGate())
  const [blocked, setBlocked] = useState(false)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<string | null>(null)

  function finish(feedback: CaptureFeedback) {
    gate.current.finish(feedback)
    setBlocked(gate.current.blocked)
    setMessage(feedback.message)
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!gate.current.begin()) return
    setBusy(true)
    setMessage(null)
    try {
      let normalized
      try {
        normalized = normalizeOrderIntake({
          customerId,
          reportedProblem,
          intakeCondition,
          accessories,
          priority,
          brand: withBicycle ? brand : null,
          model: withBicycle ? model : null,
        })
      } catch (error) {
        const validation = captureValidation(error)
        if (!validation) throw error
        finish(captureFeedback({ kind: 'resolved', value: validation }))
        return
      }
      const result = await onCreateOrder(normalized)
      const feedback = captureFeedback({ kind: 'resolved', value: result })
      finish(feedback)
      if (feedback.status !== 'saved') return
      // Customer and priority intentionally remain selected after a successful local save.
      // They become clean defaults only here; a refused/failed save keeps the draft dirty.
      setRetainedSelection({ customerId, priority })
      setReportedProblem('')
      setIntakeCondition('')
      setAccessories('')
      setWithBicycle(false)
      setBrand('')
      setModel('')
      setMessage('Orden guardada localmente')
    } catch (error) {
      finish(captureFeedback({ kind: 'rejected', error }))
    } finally {
      setBusy(false)
    }
  }

  const inputClass =
    'min-h-11 rounded-lg border border-[var(--ocwp-color-control-border)] bg-[var(--ocwp-color-surface)] px-3'

  return (
    <form
      onSubmit={submit}
      className="grid gap-4"
      aria-describedby="order-intake-status"
      data-dirty={
        blocked ||
        busy ||
        hasOrderDraft(
          {
            customerId,
            priority,
            reportedProblem,
            intakeCondition,
            accessories,
            withBicycle,
            brand,
            model,
          },
          retainedSelection,
        )
      }
    >
      <label className="grid gap-1">
        <span className="font-medium">Cliente</span>
        <select
          required
          value={customerId}
          onChange={(event: ChangeEvent<HTMLSelectElement>) =>
            setCustomerId(event.currentTarget.value)
          }
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
          onChange={(event: ChangeEvent<HTMLTextAreaElement>) =>
            setReportedProblem(event.currentTarget.value)
          }
          className="min-h-11 rounded-lg border border-[var(--ocwp-color-control-border)] bg-[var(--ocwp-color-surface)] px-3 py-2"
        />
      </label>
      <label className="grid gap-1">
        <span className="font-medium">Condición al recibir</span>
        <input
          value={intakeCondition}
          onChange={(event: ChangeEvent<HTMLInputElement>) =>
            setIntakeCondition(event.currentTarget.value)
          }
          className={inputClass}
        />
      </label>
      <label className="grid gap-1">
        <span className="font-medium">Accesorios</span>
        <input
          value={accessories}
          onChange={(event: ChangeEvent<HTMLInputElement>) =>
            setAccessories(event.currentTarget.value)
          }
          className={inputClass}
        />
      </label>
      <label className="grid gap-1">
        <span className="font-medium">Prioridad</span>
        <select
          value={priority}
          onChange={(event: ChangeEvent<HTMLSelectElement>) =>
            setPriority(event.currentTarget.value)
          }
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
          onChange={(event: ChangeEvent<HTMLInputElement>) =>
            setWithBicycle(event.currentTarget.checked)
          }
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
              onChange={(event: ChangeEvent<HTMLInputElement>) =>
                setBrand(event.currentTarget.value)
              }
              className={inputClass}
            />
          </label>
          <label className="grid gap-1">
            <span className="font-medium">Modelo</span>
            <input
              value={model}
              onChange={(event: ChangeEvent<HTMLInputElement>) =>
                setModel(event.currentTarget.value)
              }
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

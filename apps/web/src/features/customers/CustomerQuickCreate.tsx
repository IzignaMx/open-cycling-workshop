import {
  captureFeedback,
  CaptureSubmissionGate,
  type CaptureFeedback,
} from '../capture-feedback.js'
import type { CaptureSubmissionResult } from '../../runtime/capture-outcome.js'
import { useRef, useState, type ChangeEvent, type FormEvent } from 'react'

import { hasCustomerDraft } from '../draft-state.js'
import { Button } from '@ocwp/ui'

export interface CustomerQuickCreateProps {
  onCreate(input: {
    displayName: string
    email: string | null
    phone: string | null
  }): Promise<CaptureSubmissionResult>
}

export function CustomerQuickCreate({ onCreate }: CustomerQuickCreateProps) {
  const [displayName, setDisplayName] = useState('')
  const [email, setEmail] = useState('')
  const [phone, setPhone] = useState('')
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
      const result = await onCreate({
        displayName,
        email: email || null,
        phone: phone || null,
      })
      const feedback = captureFeedback({ kind: 'resolved', value: result })
      finish(feedback)
      if (feedback.status !== 'saved') return
      setDisplayName('')
      setEmail('')
      setPhone('')
      setMessage('Cliente guardado localmente')
    } catch (error) {
      finish(captureFeedback({ kind: 'rejected', error }))
    } finally {
      setBusy(false)
    }
  }

  return (
    <form
      onSubmit={submit}
      className="grid gap-4"
      aria-describedby="customer-create-status"
      data-dirty={blocked || busy || hasCustomerDraft({ displayName, email, phone })}
    >
      <label className="grid gap-1">
        <span className="font-medium">Nombre</span>
        <input
          required
          value={displayName}
          onChange={(event: ChangeEvent<HTMLInputElement>) =>
            setDisplayName(event.currentTarget.value)
          }
          className="min-h-11 rounded-lg border border-[var(--ocwp-color-control-border)] bg-[var(--ocwp-color-surface)] px-3"
          autoComplete="name"
        />
      </label>
      <label className="grid gap-1">
        <span className="font-medium">Correo</span>
        <input
          type="email"
          value={email}
          onChange={(event: ChangeEvent<HTMLInputElement>) => setEmail(event.currentTarget.value)}
          className="min-h-11 rounded-lg border border-[var(--ocwp-color-control-border)] bg-[var(--ocwp-color-surface)] px-3"
          autoComplete="email"
        />
      </label>
      <label className="grid gap-1">
        <span className="font-medium">Teléfono</span>
        <input
          inputMode="tel"
          value={phone}
          onChange={(event: ChangeEvent<HTMLInputElement>) => setPhone(event.currentTarget.value)}
          className="min-h-11 rounded-lg border border-[var(--ocwp-color-control-border)] bg-[var(--ocwp-color-surface)] px-3"
          autoComplete="tel"
        />
      </label>
      <Button type="submit" disabled={busy || blocked}>
        {busy ? 'Guardando…' : 'Guardar cliente'}
      </Button>
      <p id="customer-create-status" role="status" aria-live="polite" className="min-h-6 text-sm">
        {message}
      </p>
    </form>
  )
}

import { type ChangeEvent, type FormEvent } from 'react'
import { Button } from '@ocwp/ui'
import type { CustomerDraftState } from '../draft-state.js'
import type { CaptureFormSnapshot } from '../../runtime/capture-visit.js'

export interface CustomerQuickCreateProps {
  capture: CaptureFormSnapshot<CustomerDraftState>
  onEdit<K extends keyof CustomerDraftState>(field: K, value: CustomerDraftState[K]): void
  onSubmit(): Promise<void>
}

export function CustomerQuickCreate({ capture, onEdit, onSubmit }: CustomerQuickCreateProps) {
  const { busy, blocked, message } = capture
  const { displayName, email, phone } = capture.draft
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    await onSubmit()
  }

  return (
    <form
      onSubmit={submit}
      className="grid gap-4"
      aria-describedby="customer-create-status customer-recovery-status"
      data-dirty={capture.dirty}
    >
      <label className="grid gap-1">
        <span className="font-medium">Nombre</span>
        <input
          required
          value={displayName}
          onChange={(event: ChangeEvent<HTMLInputElement>) => {
            onEdit('displayName', event.currentTarget.value)
          }}
          className="min-h-11 rounded-lg border border-[var(--ocwp-color-control-border)] bg-[var(--ocwp-color-surface)] px-3"
          autoComplete="name"
        />
      </label>
      <label className="grid gap-1">
        <span className="font-medium">Correo</span>
        <input
          type="email"
          value={email}
          onChange={(event: ChangeEvent<HTMLInputElement>) => {
            onEdit('email', event.currentTarget.value)
          }}
          className="min-h-11 rounded-lg border border-[var(--ocwp-color-control-border)] bg-[var(--ocwp-color-surface)] px-3"
          autoComplete="email"
        />
      </label>
      <label className="grid gap-1">
        <span className="font-medium">Teléfono</span>
        <input
          inputMode="tel"
          value={phone}
          onChange={(event: ChangeEvent<HTMLInputElement>) => {
            onEdit('phone', event.currentTarget.value)
          }}
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
      <p id="customer-recovery-status" role="status">
        {capture.recoveryMessage}
      </p>
    </form>
  )
}

import { useState, type ChangeEvent, type FormEvent } from 'react'

import { Button } from '@ocwp/ui'

export interface CustomerQuickCreateProps {
  onCreate(input: { displayName: string; email: string | null; phone: string | null }): Promise<void>
}

export function CustomerQuickCreate({ onCreate }: CustomerQuickCreateProps) {
  const [displayName, setDisplayName] = useState('')
  const [email, setEmail] = useState('')
  const [phone, setPhone] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<string | null>(null)

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setBusy(true)
    setMessage(null)
    try {
      await onCreate({
        displayName,
        email: email || null,
        phone: phone || null,
      })
      setDisplayName('')
      setEmail('')
      setPhone('')
      setMessage('Cliente guardado localmente')
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No se pudo guardar el cliente')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} className="grid gap-4" aria-describedby="customer-create-status">
      <label className="grid gap-1">
        <span className="font-medium">Nombre</span>
        <input
          required
          value={displayName}
          onChange={(event: ChangeEvent<HTMLInputElement>) => setDisplayName(event.currentTarget.value)}
          className="min-h-11 rounded-lg border border-[var(--ocwp-color-border)] bg-white px-3"
          autoComplete="name"
        />
      </label>
      <label className="grid gap-1">
        <span className="font-medium">Correo</span>
        <input
          type="email"
          value={email}
          onChange={(event: ChangeEvent<HTMLInputElement>) => setEmail(event.currentTarget.value)}
          className="min-h-11 rounded-lg border border-[var(--ocwp-color-border)] bg-white px-3"
          autoComplete="email"
        />
      </label>
      <label className="grid gap-1">
        <span className="font-medium">Teléfono</span>
        <input
          inputMode="tel"
          value={phone}
          onChange={(event: ChangeEvent<HTMLInputElement>) => setPhone(event.currentTarget.value)}
          className="min-h-11 rounded-lg border border-[var(--ocwp-color-border)] bg-white px-3"
          autoComplete="tel"
        />
      </label>
      <Button type="submit" disabled={busy}>
        {busy ? 'Guardando…' : 'Guardar cliente'}
      </Button>
      <p id="customer-create-status" role="status" aria-live="polite" className="min-h-6 text-sm">
        {message}
      </p>
    </form>
  )
}

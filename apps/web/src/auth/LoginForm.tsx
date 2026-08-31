import { useState, type ChangeEvent, type FormEvent } from 'react'

import { Button } from '@ocwp/ui'

import { buildLoginRequest, type LoginFormInput, type LoginRequestPayload } from './login-model.js'

export interface LoginFormProps {
  busy: boolean
  message: string | null
  onLogin(input: LoginRequestPayload): Promise<void>
}

export function LoginForm({ busy, message, onLogin }: LoginFormProps) {
  const [organizationId, setOrganizationId] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [localMessage, setLocalMessage] = useState<string | null>(null)

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setLocalMessage(null)
    try {
      const input: LoginFormInput = { organizationId, username, password }
      await onLogin(buildLoginRequest(input))
      setPassword('')
    } catch (error) {
      setLocalMessage(error instanceof Error ? error.message : 'No se pudo iniciar sesión')
    }
  }

  return (
    <form onSubmit={submit} className="grid gap-4" aria-describedby="login-status">
      <label className="grid gap-1">
        <span className="font-medium">Organización</span>
        <input
          required
          value={organizationId}
          onChange={(event: ChangeEvent<HTMLInputElement>) =>
            setOrganizationId(event.currentTarget.value)
          }
          className="min-h-11 rounded-lg border border-[var(--ocwp-color-border)] bg-white px-3"
          autoComplete="organization"
        />
      </label>
      <label className="grid gap-1">
        <span className="font-medium">Usuario</span>
        <input
          required
          value={username}
          onChange={(event: ChangeEvent<HTMLInputElement>) =>
            setUsername(event.currentTarget.value)
          }
          className="min-h-11 rounded-lg border border-[var(--ocwp-color-border)] bg-white px-3"
          autoComplete="username"
        />
      </label>
      <label className="grid gap-1">
        <span className="font-medium">Contraseña</span>
        <input
          required
          type="password"
          value={password}
          onChange={(event: ChangeEvent<HTMLInputElement>) =>
            setPassword(event.currentTarget.value)
          }
          className="min-h-11 rounded-lg border border-[var(--ocwp-color-border)] bg-white px-3"
          autoComplete="current-password"
        />
      </label>
      <Button type="submit" disabled={busy}>
        {busy ? 'Ingresando…' : 'Iniciar sesión'}
      </Button>
      <p id="login-status" role="status" aria-live="polite" className="min-h-6 text-sm">
        {localMessage ?? message}
      </p>
    </form>
  )
}

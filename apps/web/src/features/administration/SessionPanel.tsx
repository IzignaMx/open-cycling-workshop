import { useState, type FormEvent, type ChangeEvent } from 'react'
import { SecurityNotice, takeSecret, useSecret, type ConnectedProps } from './controls.js'
import { validatePassword } from './model.js'

export function SessionPanel({ controller, snapshot }: ConnectedProps) {
  const current = useSecret(controller)
  const next = useSecret(controller)
  const [reviewed, setReviewed] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [dirty, setDirty] = useState(false)
  return (
    <section aria-labelledby="administration-session">
      <h2 id="administration-session">Mi sesión</h2>
      <p>{snapshot.account.user?.display_name}</p>
      <SecurityNotice self />
      <form
        aria-label="Cambiar contraseña"
        data-dirty={dirty}
        onSubmit={(event: FormEvent<HTMLFormElement>) => {
          event.preventDefault()
          if (!reviewed || snapshot.busy) return
          const oldValue = takeSecret(current),
            newValue = takeSecret(next)
          setDirty(false)
          setReviewed(false)
          if (!validatePassword(oldValue, true) || !validatePassword(newValue)) {
            setError('Introduce la contraseña actual y una nueva de 12 a 1024 caracteres.')
            return
          }
          setError(null)
          void controller.changePassword(oldValue, newValue)
        }}
      >
        {error && (
          <p id="administration-session-error" role="alert">
            {error}
          </p>
        )}
        <label>
          Contraseña actual
          <input
            ref={current}
            aria-describedby={error ? 'administration-session-error' : undefined}
            type="password"
            autoComplete="current-password"
            required
            maxLength={2048}
            onInput={() => setDirty(true)}
          />
        </label>
        <label>
          Nueva contraseña
          <input
            ref={next}
            aria-describedby={error ? 'administration-session-error' : undefined}
            type="password"
            autoComplete="new-password"
            required
            maxLength={2048}
            onInput={() => setDirty(true)}
          />
        </label>
        <p>
          La nueva contraseña debe tener entre 12 y 1024 caracteres. Se pedirá de nuevo después de
          cualquier fallo.
        </p>
        <label className="administration-check">
          <input
            type="checkbox"
            checked={reviewed}
            onChange={(event: ChangeEvent<HTMLInputElement>) =>
              setReviewed(event.currentTarget.checked)
            }
          />
          Confirmo el cambio de seguridad
        </label>
        <button type="submit" disabled={!reviewed || snapshot.busy}>
          Cambiar contraseña
        </button>
        <button
          type="button"
          onClick={() => {
            takeSecret(current)
            takeSecret(next)
            setDirty(false)
            setReviewed(false)
            setError(null)
          }}
        >
          Cancelar cambio de contraseña
        </button>
      </form>
      <button
        type="button"
        disabled={snapshot.busy || !reviewed}
        onClick={() => {
          takeSecret(current)
          takeSecret(next)
          setReviewed(false)
          void controller.logoutAll()
        }}
      >
        Cerrar todas mis sesiones
      </button>
      <button
        type="button"
        disabled={snapshot.busy}
        onClick={() => {
          takeSecret(current)
          takeSecret(next)
          controller.logout()
        }}
      >
        Cerrar sesión en este dispositivo
      </button>
    </section>
  )
}

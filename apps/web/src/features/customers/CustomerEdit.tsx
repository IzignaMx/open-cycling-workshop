import { useEffect, useRef, type ChangeEvent, type FormEvent } from 'react'
import { Button } from '@ocwp/ui'
import type { CustomerDraftState } from '../draft-state.js'
import type { CustomerEditSnapshot } from '../../runtime/customer-edit-visit.js'

export function CustomerEdit({
  edit,
  onEdit,
  onSubmit,
  onCancel,
}: {
  edit: CustomerEditSnapshot
  onEdit<K extends keyof CustomerDraftState>(field: K, value: CustomerDraftState[K]): void
  onSubmit(): Promise<void>
  onCancel(discard: boolean): void
}) {
  const heading = useRef<HTMLHeadingElement>(null)
  const id = edit.draft?.customerId
  useEffect(() => {
    if (id) heading.current?.focus()
  }, [id])
  if (!edit.draft) return <p role="status">{edit.message}</p>
  const { draft, busy, blocked } = edit
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    await onSubmit()
  }
  return (
    <section aria-labelledby="customer-edit-title">
      <h3 id="customer-edit-title" tabIndex={-1} ref={heading}>
        Editar cliente
      </h3>
      <form
        onSubmit={submit}
        data-dirty={edit.dirty || busy || blocked}
        aria-describedby="customer-edit-status customer-edit-lifetime"
      >
        <fieldset disabled={busy || blocked} className="grid gap-4">
          <legend className="sr-only">Datos del cliente existente</legend>
          {(['displayName', 'email', 'phone'] as const).map((field) => (
            <label key={field} className="grid gap-1">
              <span>
                {field === 'displayName' ? 'Nombre' : field === 'email' ? 'Correo' : 'Teléfono'}
              </span>
              <input
                required={field === 'displayName'}
                type={field === 'email' ? 'email' : field === 'phone' ? 'tel' : 'text'}
                autoComplete={
                  field === 'displayName' ? 'name' : field === 'email' ? 'email' : 'tel'
                }
                value={draft[field]}
                onChange={(event: ChangeEvent<HTMLInputElement>) =>
                  onEdit(field, event.currentTarget.value)
                }
                className="min-h-11 rounded-lg border border-[var(--ocwp-color-control-border)] bg-[var(--ocwp-color-surface)] px-3"
              />
            </label>
          ))}
          <Button type="submit" disabled={!edit.dirty}>
            {busy ? 'Guardando cambios…' : 'Guardar cambios'}
          </Button>
          <Button
            type="button"
            onClick={() => {
              if (
                !edit.dirty ||
                window.confirm('¿Descartar los cambios de este cliente sin guardar?')
              )
                onCancel(edit.dirty)
            }}
          >
            Cancelar edición
          </Button>
        </fieldset>
        <p id="customer-edit-status" role="status" aria-live="polite">
          {edit.message}
        </p>
        <p id="customer-edit-lifetime" role="status">
          Esta edición sin guardar solo permanece en esta pantalla. Se pierde al recargar, cerrar
          sesión o interrumpirse la sesión; no se recupera después.
        </p>
        <p>
          Los cambios guardados quedan pendientes de sincronización. Revisa las incidencias antes de
          repetirlos.
        </p>
      </form>
    </section>
  )
}

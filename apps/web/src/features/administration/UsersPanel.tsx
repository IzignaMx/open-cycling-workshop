import { useLayoutEffect, useRef, useState, type FormEvent, type ChangeEvent } from 'react'
import type { UserResponse } from './contracts.js'
import { canAdminister, hasCapability, validatePassword } from './model.js'
import {
  discardDraft,
  SecurityNotice,
  takeSecret,
  useSecret,
  type ConnectedProps,
} from './controls.js'
import { UserForm } from './UserForm.js'

function UserSecurity({
  controller,
  snapshot,
  row,
  action,
  onClose,
}: ConnectedProps & { row: UserResponse; action: 'reset' | 'revoke'; onClose(): void }) {
  const secret = useSecret(controller)
  const form = useRef<HTMLFormElement>(null)
  useLayoutEffect(() => {
    form.current?.querySelector<HTMLInputElement>('input')?.focus()
  }, [])
  const [reviewed, setReviewed] = useState(false)
  const [error, setError] = useState<string | null>(null)
  return (
    <form
      ref={form}
      aria-label={
        action === 'reset'
          ? `Restablecer contraseña de ${row.username}`
          : `Revocar sesiones de ${row.username}`
      }
      data-dirty="true"
      onSubmit={(event: FormEvent<HTMLFormElement>) => {
        event.preventDefault()
        if (!reviewed || snapshot.busy) return
        setReviewed(false)
        if (action === 'reset') {
          const password = takeSecret(secret)
          if (!validatePassword(password)) {
            setError('Escribe una contraseña de 12 a 1024 caracteres.')
            return
          }
          setError(null)
          void controller.resetPassword(row, password)
        } else {
          takeSecret(secret)
          void controller.revokeSessions(row)
        }
      }}
    >
      <h3>
        {action === 'reset' ? 'Restablecer contraseña' : 'Revocar sesiones'}: {row.username}
      </h3>
      <p>Versión revisada: {row.version}</p>
      <SecurityNotice self={row.user_id === snapshot.account.user?.user_id} />
      {error && (
        <p id="administration-reset-error" role="alert">
          {error}
        </p>
      )}
      {action === 'reset' && (
        <label>
          Nueva contraseña del usuario
          <input
            ref={secret}
            aria-describedby={error ? 'administration-reset-error' : undefined}
            type="password"
            autoComplete="new-password"
            required
            maxLength={2048}
          />
        </label>
      )}
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
      <button type="submit" disabled={snapshot.busy || !reviewed}>
        Confirmar acción
      </button>
      <button
        type="button"
        onClick={() => {
          takeSecret(secret)
          onClose()
        }}
      >
        Cancelar acción
      </button>
    </form>
  )
}
const MAX_DIRECTORY_PAGES = 64

export function UsersPanel({ controller, snapshot }: ConnectedProps) {
  const [active, setActive] = useState('all')
  const [editorInstance, setEditorInstance] = useState(0)
  const [cursors, setCursors] = useState<string[]>([])
  const returnFocus = useRef<HTMLElement | null>(null)
  const [editor, setEditor] = useState<{
    row?: UserResponse
    action: 'edit' | 'reset' | 'revoke'
  } | null>(null)
  const actor = snapshot.account.user!
  const catalog = snapshot.catalog
  const has = (capability: string) => hasCapability(actor, capability, catalog ?? undefined)
  function open(next: typeof editor) {
    if (!editor || discardDraft()) {
      returnFocus.current =
        document.activeElement instanceof HTMLElement ? document.activeElement : null
      setEditorInstance((previous) => previous + 1)
      setEditor(next ? { ...next, ...(next.row ? { row: structuredClone(next.row) } : {}) } : null)
    }
  }
  function closeEditor() {
    setEditor(null)
    returnFocus.current?.focus()
  }
  function refresh(filter = active, afterId?: string) {
    void controller.loadUsers({
      ...(filter === 'all' ? {} : { active: filter === 'true' }),
      ...(afterId ? { afterId } : {}),
    })
  }
  return (
    <section aria-labelledby="administration-users">
      <h2 id="administration-users">Usuarios y permisos</h2>
      {!has('users.read') ? (
        <p>No tienes permiso para consultar usuarios.</p>
      ) : (
        <>
          <label>
            Estado de usuarios
            <select
              value={active}
              onChange={(event: ChangeEvent<HTMLSelectElement>) => {
                setActive(event.currentTarget.value)
                setCursors([])
                refresh(event.currentTarget.value)
              }}
            >
              <option value="all">Todos</option>
              <option value="true">Activos</option>
              <option value="false">Inactivos</option>
            </select>
          </label>
          <button
            type="button"
            disabled={snapshot.busy}
            onClick={() => {
              setCursors([])
              refresh()
            }}
          >
            Cargar usuarios
          </button>
          <button
            type="button"
            disabled={snapshot.busy}
            onClick={() => void controller.loadCatalog()}
          >
            Cargar catálogo de permisos
          </button>
          <p>
            Condición de propietario de tu cuenta:{' '}
            {snapshot.ownerHint === 'owner'
              ? 'Propietario verificado'
              : snapshot.ownerHint === 'non-owner'
                ? 'No propietario'
                : 'Sin verificar'}
            .
          </p>
          {snapshot.ownerHint === 'unknown' && (
            <button
              type="button"
              disabled={snapshot.busy}
              onClick={() => void controller.continueOwnerLookup()}
            >
              Continuar verificación de propietario
            </button>
          )}
          {has('users.write') && has('users.grants.write') && (
            <button
              type="button"
              disabled={snapshot.busy || !catalog}
              onClick={() => open({ action: 'edit' })}
            >
              Crear usuario
            </button>
          )}
          <div className="administration-user-list">
            {snapshot.users.map((row) => {
              const allowed =
                !!catalog &&
                canAdminister(
                  actor,
                  row,
                  {
                    display_name: row.display_name,
                    capabilities: row.capabilities,
                    location_id: row.location_id,
                    is_active: row.is_active,
                    is_owner: row.is_owner,
                  },
                  snapshot.ownerHint,
                  catalog,
                )
              return (
                <article key={row.user_id} aria-label={`Usuario ${row.username}`}>
                  <h3>{row.display_name}</h3>
                  <p>
                    {row.username} · {row.is_active ? 'Activo' : 'Inactivo'} ·{' '}
                    {row.is_owner ? 'Propietario' : 'No propietario'}
                  </p>
                  <p>
                    Ámbito: {row.location_id ?? 'Toda la organización'} · Versión: {row.version}
                  </p>
                  <p>Permisos: {row.capabilities.join(', ') || 'Sin permisos'}</p>
                  <div className="administration-actions">
                    {has('users.write') && (
                      <button
                        type="button"
                        disabled={snapshot.busy || !allowed}
                        onClick={() => open({ row, action: 'edit' })}
                      >
                        Editar usuario
                      </button>
                    )}
                    {has('users.credentials.reset') && (
                      <button
                        type="button"
                        disabled={snapshot.busy || !allowed}
                        onClick={() => open({ row, action: 'reset' })}
                      >
                        Restablecer contraseña
                      </button>
                    )}
                    {has('users.sessions.revoke') && (
                      <button
                        type="button"
                        disabled={snapshot.busy || !allowed}
                        onClick={() => open({ row, action: 'revoke' })}
                      >
                        Revocar sesiones
                      </button>
                    )}
                  </div>
                </article>
              )
            })}
          </div>
          {cursors.length > 0 && (
            <button
              type="button"
              disabled={snapshot.busy}
              onClick={() => {
                const previous = cursors.slice(0, -1)
                setCursors(previous)
                refresh(active, previous.at(-1))
              }}
            >
              Página anterior de usuarios
            </button>
          )}
          {cursors.length >= MAX_DIRECTORY_PAGES - 1 && (
            <p role="status">
              Límite de 64 páginas alcanzado. Usa Cargar usuarios para volver a la primera página o
              Página anterior para retroceder.
            </p>
          )}
          {snapshot.usersNext && (
            <button
              type="button"
              disabled={snapshot.busy || cursors.length >= MAX_DIRECTORY_PAGES - 1}
              onClick={() => {
                if (cursors.length >= MAX_DIRECTORY_PAGES - 1) return
                const next = snapshot.usersNext!
                setCursors((previous) =>
                  previous.length < MAX_DIRECTORY_PAGES - 1 ? [...previous, next] : previous,
                )
                refresh(active, next)
              }}
            >
              Siguiente página de usuarios
            </button>
          )}
          {editor &&
            catalog &&
            (editor.action === 'edit' ? (
              <UserForm
                key={`edit-${editorInstance}`}
                controller={controller}
                snapshot={snapshot}
                row={editor.row}
                onClose={closeEditor}
              />
            ) : (
              editor.row && (
                <UserSecurity
                  key={`${editor.action}-${editorInstance}`}
                  controller={controller}
                  snapshot={snapshot}
                  row={editor.row}
                  action={editor.action}
                  onClose={closeEditor}
                />
              )
            ))}
        </>
      )}
    </section>
  )
}

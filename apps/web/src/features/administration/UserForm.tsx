import { useLayoutEffect, useRef, useState, type FormEvent, type ChangeEvent } from 'react'
import { isConfirmedDraftRevision } from './draft-revision.js'
import type { UserDraft, UserResponse } from './contracts.js'
import {
  canAdminister,
  hasCapability,
  isSelfSecurityChange,
  matchingRole,
  minimalUserPatch,
  normalizeUsername,
  validatePassword,
  validateUserDraft,
} from './model.js'
import {
  discardDraft,
  SecurityNotice,
  takeSecret,
  useSecret,
  type ConnectedProps,
} from './controls.js'

export function UserForm({
  controller,
  snapshot,
  row,
  onClose,
}: ConnectedProps & { row?: UserResponse | undefined; onClose(): void }) {
  const form = useRef<HTMLFormElement>(null)
  useLayoutEffect(() => {
    form.current?.querySelector<HTMLInputElement>('input')?.focus()
  }, [])
  const actor = snapshot.account.user!
  const catalog = snapshot.catalog!
  const [draft, setDraft] = useState<UserDraft>(() =>
    row
      ? {
          display_name: row.display_name,
          location_id: row.location_id,
          capabilities: [...row.capabilities],
          is_active: row.is_active,
          is_owner: row.is_owner,
        }
      : {
          display_name: '',
          location_id: actor.location_id,
          capabilities: [],
          is_active: true,
          is_owner: false,
        },
  )
  const [username, setUsername] = useState('')
  const [dirty, setDirty] = useState(false)
  const revision = useRef(0)
  function markEdited() {
    revision.current++
    setDirty(true)
  }
  const [reviewed, setReviewed] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const initialSecret = useSecret(controller)
  const grantsWrite = hasCapability(actor, 'users.grants.write', catalog)
  const patch = (() => {
    try {
      return row ? minimalUserPatch(row, draft, catalog) : null
    } catch {
      return null
    }
  })()
  const target = row ?? {
    ...draft,
    user_id: '',
    username,
    organization_id: actor.organization_id,
    version: 1,
  }
  const subordinate = canAdminister(actor, target, draft, snapshot.ownerHint, catalog, !row)
  const valid = validateUserDraft(draft, catalog, row ?? undefined).length === 0
  const security =
    !!row &&
    !!patch &&
    Object.keys(patch).some((key) => key !== 'expected_version' && key !== 'display_name')
  const self = !!row && !!patch && isSelfSecurityChange(actor, row, patch)
  const unknown = draft.capabilities.filter(
    (grant) => grant !== '*' && !catalog.capabilities.includes(grant),
  )
  function change(values: Partial<UserDraft>) {
    setDraft((previous) => ({ ...previous, ...values }))
    markEdited()
    setReviewed(false)
  }
  function cancel() {
    if (!dirty || discardDraft()) {
      takeSecret(initialSecret)
      onClose()
    }
  }
  return (
    <form
      ref={form}
      aria-label={row ? `Editar usuario ${row.username}` : 'Crear usuario'}
      data-dirty={dirty}
      onSubmit={(event: FormEvent<HTMLFormElement>) => {
        event.preventDefault()
        if (snapshot.busy || !valid || !subordinate || (security && !reviewed)) return
        const submittedRevision = revision.current
        const submittedGeneration = snapshot.generation
        setDirty(true)
        const settle = (receipt: unknown) => {
          if (
            form.current &&
            controller.getSnapshot().generation === submittedGeneration &&
            isConfirmedDraftRevision(receipt, submittedRevision, revision.current)
          )
            setDirty(false)
        }
        if (row) {
          if (patch) {
            takeSecret(initialSecret)
            void controller.updateUser(row, patch).then(settle)
          }
        } else {
          const password = takeSecret(initialSecret)
          const normalized = normalizeUsername(username)
          if (!validatePassword(password) || !normalized || Array.from(normalized).length > 160) {
            setError(
              'Revisa el nombre de usuario y escribe una contraseña inicial de 12 a 1024 caracteres.',
            )
            return
          }
          setError(null)
          void controller
            .createUser({
              username: normalized,
              display_name: draft.display_name.trim(),
              location_id: draft.location_id,
              capabilities: [...draft.capabilities],
              is_owner: draft.is_owner,
              password,
            })
            .then(settle)
        }
      }}
    >
      <h3>{row ? `Editar ${row.username}` : 'Crear usuario'}</h3>
      {error && (
        <p id="administration-user-error" role="alert">
          {error}
        </p>
      )}
      {row && (
        <p>
          Versión revisada: {row.version}. Si cambia en el servidor, cancela y vuelve a abrir el
          usuario; no se reintentará automáticamente.
        </p>
      )}
      {!row && (
        <label>
          Nombre de usuario
          <input
            required
            value={username}
            onChange={(event: ChangeEvent<HTMLInputElement>) => {
              setUsername(event.currentTarget.value)
              markEdited()
            }}
            autoComplete="off"
            aria-describedby={error ? 'administration-user-error' : undefined}
            maxLength={320}
          />
        </label>
      )}
      <label>
        Nombre visible
        <input
          required
          value={draft.display_name}
          onChange={(event: ChangeEvent<HTMLInputElement>) =>
            change({ display_name: event.currentTarget.value })
          }
          maxLength={400}
        />
      </label>
      {!row && (
        <>
          <label>
            Contraseña inicial
            <input
              ref={initialSecret}
              aria-describedby={`administration-initial-secret-help${error ? ' administration-user-error' : ''}`}
              required
              type="password"
              autoComplete="new-password"
              maxLength={2048}
              onInput={markEdited}
            />
          </label>
          <p id="administration-initial-secret-help">
            Entre 12 y 1024 caracteres. No se conserva después de enviar.
          </p>
        </>
      )}
      <fieldset disabled={snapshot.busy || !grantsWrite || unknown.length > 0}>
        <legend>Permisos y ámbito</legend>
        <label>
          Rol
          <select
            value={matchingRole(draft.capabilities, catalog) ?? ''}
            onChange={(event: ChangeEvent<HTMLSelectElement>) => {
              const role = catalog.roles.find((item) => item.name === event.currentTarget.value)
              if (role) change({ capabilities: [...role.capabilities] })
            }}
          >
            <option value="">Permisos personalizados</option>
            {catalog.roles.map((role) => (
              <option
                key={role.name}
                value={role.name}
                disabled={role.capabilities.some(
                  (capability) => !hasCapability(actor, capability, catalog),
                )}
              >
                {role.name}
              </option>
            ))}
          </select>
        </label>
        <p>
          Elegir un rol reemplaza los permisos. El rol Owner no designa por sí solo a un
          propietario.
        </p>
        <label>
          Ámbito del usuario
          <select
            value={draft.location_id ?? ''}
            disabled={actor.location_id !== null}
            onChange={(event: ChangeEvent<HTMLSelectElement>) =>
              change({ location_id: event.currentTarget.value || null })
            }
          >
            <option value="">Toda la organización</option>
            {draft.location_id &&
              !snapshot.locations.some((item) => item.location_id === draft.location_id) && (
                <option value={draft.location_id}>{draft.location_id}</option>
              )}
            {snapshot.locations.map((location) => (
              <option value={location.location_id} key={location.location_id}>
                {location.name}
              </option>
            ))}
          </select>
        </label>
        <fieldset>
          <legend>Capacidades del catálogo vigente</legend>
          {catalog.capabilities.map((capability) => (
            <label className="administration-check" key={capability}>
              <input
                type="checkbox"
                checked={draft.capabilities.includes(capability)}
                disabled={!hasCapability(actor, capability, catalog)}
                onChange={(event: ChangeEvent<HTMLInputElement>) =>
                  change({
                    capabilities: event.currentTarget.checked
                      ? [...draft.capabilities, capability]
                      : draft.capabilities.filter((item) => item !== capability),
                  })
                }
              />
              {capability}
            </label>
          ))}
        </fieldset>
        <label className="administration-check">
          <input
            type="checkbox"
            checked={draft.is_owner}
            disabled={snapshot.ownerHint !== 'owner'}
            onChange={(event: ChangeEvent<HTMLInputElement>) =>
              change({ is_owner: event.currentTarget.checked })
            }
          />
          Es propietario
        </label>
      </fieldset>
      {unknown.length > 0 && (
        <p role="alert">
          Permisos no editables o desconocidos: {unknown.join(', ')}. Requieren revisión; no se
          eliminarán silenciosamente.
        </p>
      )}
      {row && (
        <label className="administration-check">
          <input
            type="checkbox"
            checked={draft.is_active}
            onChange={(event: ChangeEvent<HTMLInputElement>) =>
              change({ is_active: event.currentTarget.checked })
            }
          />
          Usuario activo
        </label>
      )}
      {!subordinate && (
        <p>No puedes administrar este ámbito, propietario o conjunto de permisos.</p>
      )}
      {security && (
        <>
          <SecurityNotice self={self} />
          <label className="administration-check">
            <input
              type="checkbox"
              checked={reviewed}
              onChange={(event: ChangeEvent<HTMLInputElement>) => {
                markEdited()
                setReviewed(event.currentTarget.checked)
              }}
            />
            Confirmo el cambio de seguridad
          </label>
        </>
      )}
      <button
        type="submit"
        disabled={
          snapshot.busy ||
          !valid ||
          !subordinate ||
          (row ? !patch : !username.trim()) ||
          (security && !reviewed)
        }
      >
        {row ? 'Guardar cambios' : 'Guardar usuario'}
      </button>
      <button type="button" onClick={cancel}>
        Descartar cambios de usuario
      </button>
    </form>
  )
}

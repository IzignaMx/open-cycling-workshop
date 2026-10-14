import { useState, type FormEvent, type ChangeEvent } from 'react'
import { hasCapability } from './model.js'
import { discardDraft, type ConnectedProps } from './controls.js'

const MAX_DIRECTORY_PAGES = 64

export function LocationsPanel({ controller, snapshot }: ConnectedProps) {
  const [name, setName] = useState('')
  const [cursors, setCursors] = useState<string[]>([])
  const actor = snapshot.account.user!
  const canRead = hasCapability(actor, 'locations.read', snapshot.catalog ?? undefined)
  const canCreate =
    actor.location_id === null &&
    hasCapability(actor, 'locations.create', snapshot.catalog ?? undefined)
  return (
    <section aria-labelledby="administration-locations">
      <h2 id="administration-locations">Ubicaciones</h2>
      <p>Crear una ubicación no cambia el taller seleccionado ni el ámbito de tu cuenta.</p>
      {canRead ? (
        <>
          <button
            type="button"
            disabled={snapshot.busy}
            onClick={() => {
              setCursors([])
              void controller.loadLocations()
            }}
          >
            Cargar ubicaciones
          </button>
          <ul>
            {snapshot.locations.map((location) => (
              <li key={location.location_id}>
                {location.name} <small>{location.location_id}</small>
              </li>
            ))}
          </ul>
          {cursors.length > 0 && (
            <button
              type="button"
              disabled={snapshot.busy}
              onClick={() => {
                const previous = cursors.slice(0, -1)
                setCursors(previous)
                void controller.loadLocations(previous.at(-1))
              }}
            >
              Página anterior de ubicaciones
            </button>
          )}
          {cursors.length >= MAX_DIRECTORY_PAGES - 1 && (
            <p role="status">
              Límite de 64 páginas alcanzado. Usa Cargar ubicaciones para volver a la primera página
              o Página anterior para retroceder.
            </p>
          )}
          {snapshot.locationsNext && (
            <button
              type="button"
              disabled={snapshot.busy || cursors.length >= MAX_DIRECTORY_PAGES - 1}
              onClick={() => {
                if (cursors.length >= MAX_DIRECTORY_PAGES - 1) return
                const next = snapshot.locationsNext!
                setCursors((previous) =>
                  previous.length < MAX_DIRECTORY_PAGES - 1 ? [...previous, next] : previous,
                )
                void controller.loadLocations(next)
              }}
            >
              Siguiente página de ubicaciones
            </button>
          )}
        </>
      ) : (
        <p>No tienes permiso para consultar ubicaciones.</p>
      )}
      {canCreate && (
        <form
          aria-label="Crear ubicación"
          data-dirty={name !== ''}
          onSubmit={(event: FormEvent<HTMLFormElement>) => {
            event.preventDefault()
            if (!name.trim() || snapshot.busy) return
            void controller.createLocation(name.trim())
          }}
        >
          <label>
            Nombre de ubicación
            <input
              required
              value={name}
              onChange={(event: ChangeEvent<HTMLInputElement>) =>
                setName(event.currentTarget.value)
              }
              maxLength={320}
            />
          </label>
          <button
            type="submit"
            disabled={snapshot.busy || !name.trim() || Array.from(name.trim()).length > 160}
          >
            Crear ubicación
          </button>
          <button
            type="button"
            disabled={!name}
            onClick={() => {
              if (discardDraft()) setName('')
            }}
          >
            Descartar ubicación
          </button>
        </form>
      )}
    </section>
  )
}

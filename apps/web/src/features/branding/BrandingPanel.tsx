import { useRef, useState, useSyncExternalStore, type ChangeEvent, type FormEvent } from 'react'
import { PALETTES } from '../../personalization/catalog.js'
import { prepareLocalLogo } from '../../personalization/logo.js'
import { LogoImage } from '../../personalization/LogoImage.js'
import { isNormalizedBrandingName, type BrandingProfile } from './contracts.js'
import type { BrandingEditorController, BrandingEditorSnapshot } from './controller.js'
import './branding.css'

function discard(): boolean {
  return window.confirm('¿Descartar el borrador de marca compartida? El taller guardado no cambia.')
}
export function BrandingPanel({
  controller,
  selectedLocationId,
}: {
  controller: BrandingEditorController
  selectedLocationId: string | null
}) {
  const snapshot = useSyncExternalStore(controller.subscribe, controller.getSnapshot)
  return (
    <section
      id="workshop-shared-branding"
      className="branding-panel"
      aria-label="Marca compartida del taller"
    >
      <h2>Marca compartida del taller</h2>
      <p>
        Nombre, colores y logo para las personas de este taller. Requiere conexión para guardar; la
        estructura y los ajustes de tu vista siguen siendo personales.
      </p>
      {snapshot.account.phase !== 'connected' ? (
        <>
          <p>Verifica la cuenta con conexión para consultar o cambiar la marca compartida.</p>
          <button
            type="button"
            disabled={
              snapshot.account.phase === 'verifying' || snapshot.account.phase === 'suspended'
            }
            onClick={() => void controller.verify()}
          >
            Verificar acceso a marca compartida
          </button>
        </>
      ) : (
        <ConnectedBranding
          key={snapshot.generation}
          controller={controller}
          snapshot={snapshot}
          selectedLocationId={selectedLocationId}
        />
      )}
      {snapshot.message && (
        <p
          role={snapshot.result === 'error' || snapshot.result === 'uncertain' ? 'alert' : 'status'}
        >
          {snapshot.message}
        </p>
      )}
    </section>
  )
}
function ConnectedBranding({
  controller,
  snapshot,
  selectedLocationId,
}: {
  controller: BrandingEditorController
  snapshot: BrandingEditorSnapshot
  selectedLocationId: string | null
}) {
  const user = snapshot.account.user!
  const canRead = user.capabilities.includes('branding.read'),
    canWrite = user.capabilities.includes('branding.write')
  const [target, setTarget] = useState(user.location_id ?? selectedLocationId ?? '')
  const [writeOnly, setWriteOnly] = useState(false)
  const root = useRef<HTMLDivElement>(null)
  const mayLeave = () => !root.current?.querySelector('[data-dirty="true"]') || discard()
  if (!canRead && !canWrite)
    return (
      <p>
        Tu cuenta no tiene permisos explícitos de marca compartida. Un propietario autorizado debe
        asignarlos y debes volver a iniciar sesión.
      </p>
    )
  return (
    <div ref={root}>
      <p>
        Taller operativo: {selectedLocationId ?? 'Ninguno'}. Editar otro taller aquí no cambia tu
        selección operativa.
      </p>
      <div className="branding-target">
        {user.location_id === null ? (
          <>
            <label>
              Taller objetivo
              <input
                value={target}
                maxLength={36}
                onChange={(event: ChangeEvent<HTMLInputElement>) => {
                  if (mayLeave()) {
                    setTarget(event.currentTarget.value)
                    setWriteOnly(false)
                  }
                }}
              />
            </label>
            <button type="button" onClick={() => void controller.loadLocations()}>
              Consultar talleres permitidos
            </button>
            {snapshot.locations.length > 0 && (
              <label>
                Elegir del directorio
                <select
                  value=""
                  onChange={(event: ChangeEvent<HTMLSelectElement>) => {
                    if (event.currentTarget.value && mayLeave()) {
                      setTarget(event.currentTarget.value)
                      setWriteOnly(false)
                    }
                  }}
                >
                  <option value="">Selecciona un taller</option>
                  {snapshot.locations.map((location) => (
                    <option key={location.location_id} value={location.location_id}>
                      {location.name} · {location.location_id}
                    </option>
                  ))}
                </select>
              </label>
            )}
            {snapshot.nextLocation && (
              <button
                type="button"
                onClick={() => void controller.loadLocations(snapshot.nextLocation!)}
              >
                Más talleres permitidos
              </button>
            )}
          </>
        ) : (
          <p>Taller asignado: {target}</p>
        )}
        {canRead ? (
          <button
            type="button"
            disabled={!target || snapshot.busy}
            onClick={() => {
              if (mayLeave()) void controller.load(target)
            }}
          >
            Cargar marca y revisar versión
          </button>
        ) : (
          <button
            type="button"
            disabled={!target || snapshot.busy}
            onClick={() => {
              if (mayLeave()) setWriteOnly(true)
            }}
          >
            Preparar reemplazo sin lectura
          </button>
        )}
      </div>
      {canRead && snapshot.profile && snapshot.targetId === target && (
        <BrandingForm
          key={`${snapshot.reviewId}:${target}`}
          controller={controller}
          snapshot={snapshot}
          target={target}
          original={snapshot.profile}
          canWrite={canWrite}
        />
      )}
      {!canRead && canWrite && writeOnly && (
        <BrandingForm
          key={`write:${target}`}
          controller={controller}
          snapshot={snapshot}
          target={target}
          original={null}
          canWrite
        />
      )}
    </div>
  )
}
function BrandingForm({
  controller,
  snapshot,
  target,
  original: initial,
  canWrite,
}: {
  controller: BrandingEditorController
  snapshot: BrandingEditorSnapshot
  target: string
  original: BrandingProfile | null
  canWrite: boolean
}) {
  const [original, setOriginal] = useState(initial)
  const [name, setName] = useState(initial?.display_name ?? '')
  const [palette, setPalette] = useState(initial?.palette_id ?? 'bosque')
  const [logo, setLogo] = useState(
    initial?.logo_state === 'available' ? (initial.logo?.png_base64 ?? null) : null,
  )
  const [logoResolved, setLogoResolved] = useState(initial?.logo_state !== 'unavailable')
  const [expectedVersion, setExpectedVersion] = useState(initial?.version ?? 0)
  const [dirty, setDirty] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [preparing, setPreparing] = useState(false)
  const [brokenPreview, setBrokenPreview] = useState<string | null>(null)
  const revision = useRef(0),
    upload = useRef(0),
    form = useRef<HTMLFormElement>(null)
  const changed = () => {
    revision.current++
    setDirty(true)
  }
  const normalized = name.normalize('NFC').trim()
  return (
    <form
      ref={form}
      className="branding-form"
      aria-label="Editar marca compartida"
      data-dirty={dirty}
      onSubmit={(event: FormEvent<HTMLFormElement>) => {
        event.preventDefault()
        if (
          !canWrite ||
          snapshot.busy ||
          preparing ||
          !logoResolved ||
          !isNormalizedBrandingName(normalized) ||
          !Number.isSafeInteger(expectedVersion) ||
          expectedVersion < 0
        )
          return
        const sentRevision = revision.current,
          generation = snapshot.generation
        void controller
          .save(target, {
            expected_version: expectedVersion,
            display_name: normalized,
            palette_id: palette,
            logo_png_base64: logo,
          })
          .then((profile) => {
            if (
              !profile ||
              !form.current ||
              revision.current !== sentRevision ||
              controller.getSnapshot().generation !== generation
            )
              return
            setOriginal(profile)
            setExpectedVersion(profile.version)
            setName(profile.display_name)
            setPalette(profile.palette_id)
            setLogo(profile.logo?.png_base64 ?? null)
            setLogoResolved(true)
            setDirty(false)
          })
      }}
    >
      <h3>
        {original?.version
          ? 'Marca guardada del taller'
          : original
            ? 'Sin marca compartida guardada'
            : 'Reemplazo completo sin permiso de lectura'}
      </h3>
      <p>
        Taller objetivo: <strong>{target}</strong>. Versión revisada: {expectedVersion}.
      </p>
      {!initial && (
        <p>
          No se han consultado datos existentes. Necesitas la versión exacta comunicada por un
          administrador; 0 solo crea una marca ausente.
        </p>
      )}
      <fieldset disabled={!canWrite}>
        <legend>Perfil compartido</legend>
        {!initial && (
          <label>
            Versión esperada
            <input
              type="number"
              min="0"
              step="1"
              value={expectedVersion}
              onChange={(event: ChangeEvent<HTMLInputElement>) => {
                setExpectedVersion(Number(event.currentTarget.value))
                changed()
              }}
            />
          </label>
        )}
        <label>
          Nombre visible del taller
          <input
            value={name}
            onChange={(event: ChangeEvent<HTMLInputElement>) => {
              setName(event.currentTarget.value)
              changed()
            }}
            aria-describedby="branding-name-help"
          />
        </label>
        <small id="branding-name-help">
          De 1 a 160 caracteres. No cambia el nombre legal ni documentos anteriores.
        </small>
        <label>
          Paleta compartida
          <select
            value={palette}
            onChange={(event: ChangeEvent<HTMLSelectElement>) => {
              const chosen = PALETTES.find((item) => item.id === event.currentTarget.value)
              if (chosen) {
                setPalette(chosen.id)
                changed()
              }
            }}
          >
            {PALETTES.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </label>
        <p>
          Vista previa del acento:{' '}
          <span
            className="branding-swatch"
            style={{ backgroundColor: PALETTES.find((item) => item.id === palette)?.light.primary }}
            aria-hidden="true"
          />
          {PALETTES.find((item) => item.id === palette)?.name}
        </p>
        {!logoResolved && (
          <p role="alert">
            El archivo guardado no está disponible. Debes elegir explícitamente un reemplazo o
            quitar el logo antes de guardar.
          </p>
        )}
        <label>
          Archivo para logo compartido
          <input
            type="file"
            accept="image/png,image/jpeg"
            onChange={(event: ChangeEvent<HTMLInputElement>) => {
              const file = event.currentTarget.files?.[0]
              event.currentTarget.value = ''
              if (!file) return
              const version = ++upload.current
              setPreparing(true)
              setMessage('Preparando vista previa; todavía no se ha enviado.')
              void prepareLocalLogo(file)
                .then((dataUrl) => {
                  if (version === upload.current && form.current) {
                    setLogo(dataUrl.slice('data:image/png;base64,'.length))
                    setLogoResolved(true)
                    changed()
                    setMessage('Vista previa lista. El logo solo se comparte al guardar.')
                  }
                })
                .catch(() => {
                  if (version === upload.current && form.current)
                    setMessage(
                      'No se pudo preparar esa imagen. Usa PNG o JPEG estático de hasta 2 MB.',
                    )
                })
                .finally(() => {
                  if (version === upload.current && form.current) setPreparing(false)
                })
            }}
          />
        </label>
        <small>
          PNG o JPEG estático, máximo 2 MB. Se reduce a PNG de 512 px. No se suben tus logos
          personales automáticamente.
        </small>
        {logo && brokenPreview !== logo && (
          <LogoImage
            className="branding-preview"
            src={`data:image/png;base64,${logo}`}
            alt="Vista previa del logo compartido"
            onError={() => setBrokenPreview(logo)}
            width="160"
            height="64"
          />
        )}
        <button
          type="button"
          onClick={() => {
            upload.current++
            setLogo(null)
            setLogoResolved(true)
            setPreparing(false)
            changed()
          }}
        >
          Quitar logo compartido
        </button>
        <button
          type="button"
          onClick={() => {
            if (!dirty || discard()) {
              upload.current++
              setName(original?.display_name ?? '')
              setPalette(original?.palette_id ?? 'bosque')
              setLogo(
                original?.logo_state === 'available' ? (original.logo?.png_base64 ?? null) : null,
              )
              setLogoResolved(original?.logo_state !== 'unavailable')
              setExpectedVersion(original?.version ?? 0)
              setDirty(false)
              setMessage(null)
              setPreparing(false)
              revision.current++
            }
          }}
        >
          Descartar cambios de marca
        </button>
        <button
          className="primary-button"
          type="submit"
          disabled={
            snapshot.busy ||
            preparing ||
            (logo !== null && brokenPreview === logo) ||
            !logoResolved ||
            !isNormalizedBrandingName(normalized)
          }
        >
          {snapshot.busy ? 'Guardando…' : 'Guardar marca compartida'}
        </button>
      </fieldset>
      {message && <p role="status">{message}</p>}
      {logo && brokenPreview === logo && (
        <p role="status">No se pudo mostrar la vista previa. Elige otra imagen antes de guardar.</p>
      )}
      {!canWrite && <p>Consulta de solo lectura. Cambiar la marca requiere branding.write.</p>}
    </form>
  )
}

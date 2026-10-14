import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
  type ChangeEvent,
  type KeyboardEvent,
} from 'react'

import { db } from '../local/db.js'
import { PALETTES, THEMES, presentationTokens } from './catalog.js'
import { prepareLocalLogo } from './logo.js'
import {
  DEFAULT_PREFERENCES,
  type PreferenceScope,
  type PresentationPreferences,
} from './preferences.js'
import { PreferenceRepository } from './repository.js'

interface WorkshopShellProps {
  scope: PreferenceScope
  userName: string
  canCreateOrders: boolean
  children: ReactNode
}

export function WorkshopShell({ scope, userName, canCreateOrders, children }: WorkshopShellProps) {
  const repository = useMemo(() => new PreferenceRepository(db.presentationPreferences), [])
  const [preferences, setPreferences] = useState<PresentationPreferences>({
    ...DEFAULT_PREFERENCES,
  })
  const latest = useRef(preferences)
  const saveVersion = useRef(0)
  const unsavedKinds = useRef(new Set<'appearance' | 'logo'>())
  const uploadVersion = useRef(0)
  const [loaded, setLoaded] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [message, setMessage] = useState('Cargando preferencias locales…')
  const [logoPreview, setLogoPreview] = useState<string | null>(null)
  const [logoMessage, setLogoMessage] = useState<string | null>(null)
  const [logoBroken, setLogoBroken] = useState(false)
  const trigger = useRef<HTMLButtonElement>(null)
  const { organizationId, userId, locationId } = scope

  useEffect(() => {
    let cancelled = false
    void repository
      .load({ organizationId, userId, locationId })
      .then((result) => {
        if (cancelled) return
        latest.current = result.preferences
        setPreferences(result.preferences)
        setMessage(
          result.valid
            ? 'Preferencias locales listas.'
            : 'La configuración guardada no es válida. Se aplicó Banco de trabajo; tus datos del taller no cambiaron.',
        )
        setLoaded(true)
      })
      .catch(() => {
        if (cancelled) return
        setMessage(
          'No se pudieron leer las preferencias. Puedes personalizar esta sesión sin afectar el trabajo local.',
        )
        setLoaded(true)
      })
    return () => {
      cancelled = true
    }
  }, [repository, organizationId, userId, locationId])

  function update(patch: Partial<PresentationPreferences>) {
    const next = { ...latest.current, ...patch }
    latest.current = next
    setPreferences(next)
    setLogoBroken(false)
    const version = ++saveVersion.current
    const kind = 'logoDataUrl' in patch ? 'logo' : 'appearance'
    setMessage('Aplicado en tu vista. Guardando en este dispositivo…')
    // Enqueue immediately at the shared repository boundary, including across remounts.
    const saved =
      kind === 'logo'
        ? repository.saveLogo(scope, next.logoDataUrl)
        : repository.saveAppearance(scope, next)
    void saved
      .then(() => {
        unsavedKinds.current.delete(kind)
        if (version === saveVersion.current)
          setMessage(
            unsavedKinds.current.size > 0
              ? 'Hay cambios de apariencia o logo que no pudieron guardarse. Se mantienen en esta sesión; vuelve a aplicarlos para reintentar.'
              : `${THEMES.find((theme) => theme.id === next.themeId)?.label ?? 'Tema'} aplicado. Preferencia guardada en este dispositivo.`,
          )
      })
      .catch(() => {
        unsavedKinds.current.add(kind)
        if (version === saveVersion.current)
          setMessage(
            'Se aplicó en esta sesión, pero no pudo guardarse. Revisa el almacenamiento del navegador; tus órdenes y cambios pendientes no se modificaron.',
          )
      })
  }

  const tokens = presentationTokens(preferences)
  const style: CSSProperties = {
    '--ocwp-color-canvas': tokens.canvas,
    '--ocwp-color-surface': tokens.surface,
    '--ocwp-color-ink': tokens.ink,
    '--ocwp-color-text': tokens.ink,
    '--ocwp-color-muted': tokens.muted,
    '--ocwp-color-border': tokens.border,
    '--ocwp-color-control-border': tokens.controlBorder,
    '--ocwp-color-accent': tokens.accent,
    '--ocwp-color-accent-strong': tokens.accentHover,
    '--ocwp-color-on-accent': tokens.accentInk,
    '--ocwp-color-accent-soft': tokens.accentSoft,
    '--ocwp-color-nav': tokens.nav,
    '--ocwp-color-nav-ink': tokens.navInk,
    '--ocwp-radius-md': `${tokens.radius}px`,
    '--ocwp-radius-sm': `${tokens.controlRadius}px`,
  } as CSSProperties

  function closeSettings() {
    setSettingsOpen(false)
    trigger.current?.focus()
  }

  return (
    <div
      className="workshop-shell"
      data-theme={preferences.themeId}
      data-scheme={tokens.appearance}
      data-density={preferences.density}
      style={style}
    >
      <a className="skip-link" href="#workshop-content">
        Saltar al contenido
      </a>
      <header className="workshop-navigation">
        <a href="#workshop-content" className="workshop-identity" aria-label="OCWP, taller activo">
          {preferences.logoDataUrl && !logoBroken ? (
            <img
              className="workshop-logo"
              src={preferences.logoDataUrl}
              alt=""
              width="160"
              height="48"
              onError={() => setLogoBroken(true)}
            />
          ) : (
            <span className="workshop-monogram" aria-hidden="true">
              OC
            </span>
          )}
          <span>
            <strong>OCWP</strong>
            <small>
              {locationId ? `Ubicación · ${locationId.slice(-8)}` : 'Sin ubicación activa'}
            </small>
          </span>
        </a>
        <button
          ref={trigger}
          type="button"
          className="settings-trigger"
          aria-expanded={settingsOpen}
          aria-controls="personalization-panel"
          onClick={() => setSettingsOpen((open) => !open)}
        >
          Personalización
        </button>
        <nav aria-label="Navegación del taller" className="workshop-links">
          <a href="#workshop-content">Resumen</a>
          <a href="#workshop-orders">Órdenes</a>
          <a href="#workshop-reception">Recepción</a>
          <a href="#workshop-issues">Incidencias</a>
        </nav>
        <div className="workshop-user">
          <span>
            Sesión: <strong>{userName}</strong>
          </span>
          <small>Vista personal · este dispositivo</small>
        </div>
      </header>
      <div className="workshop-body">
        <section
          id="personalization-panel"
          className="personalization-panel workshop-panel"
          hidden={!settingsOpen}
          aria-labelledby="personalization-title"
          onKeyDown={(event: KeyboardEvent<HTMLElement>) => {
            if (event.key === 'Escape') {
              event.stopPropagation()
              closeSettings()
            }
          }}
        >
          <div className="section-heading">
            <div>
              <p className="eyebrow">Tu espacio de trabajo</p>
              <h2 id="personalization-title">Personalización</h2>
            </div>
            <button type="button" className="secondary-button" onClick={closeSettings}>
              Cerrar personalización
            </button>
          </div>
          <p id="personalization-scope">
            La apariencia se guarda solo para tu usuario y organización en este dispositivo. El logo
            local también pertenece al taller activo. No se comparten con otras personas ni
            dispositivos.
          </p>
          <fieldset disabled={!loaded} aria-describedby="personalization-scope">
            <legend>Estructura del espacio</legend>
            <div className="theme-options">
              {THEMES.map((theme) => (
                <label
                  className="theme-option"
                  key={theme.id}
                  data-selected={preferences.themeId === theme.id}
                >
                  <input
                    type="radio"
                    name="workshop-theme"
                    value={theme.id}
                    checked={preferences.themeId === theme.id}
                    onChange={() => update({ themeId: theme.id })}
                  />
                  <span className="theme-miniature" data-preview={theme.id} aria-hidden="true">
                    <i />
                    <span>
                      <b />
                      <b />
                      <b />
                      <b />
                    </span>
                  </span>
                  <strong>{theme.label}</strong>
                  <small>
                    {theme.id === 'banco'
                      ? 'Predeterminado · lista y navegación lateral'
                      : theme.id === 'plano'
                        ? 'Navegación superior y filas alineadas'
                        : theme.id === 'ritmo'
                          ? 'Tarjetas y módulos amplios'
                          : 'Orden protagonista y cola de trabajo'}
                  </small>
                </label>
              ))}
            </div>
            <div className="preference-fields">
              <label>
                Paleta personal
                <select
                  value={preferences.paletteId}
                  onChange={(event: ChangeEvent<HTMLSelectElement>) =>
                    update({ paletteId: event.currentTarget.value })
                  }
                >
                  {PALETTES.map((palette) => (
                    <option key={palette.id} value={palette.id}>
                      {palette.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Esquema de superficies
                <select
                  value={preferences.scheme}
                  onChange={(event: ChangeEvent<HTMLSelectElement>) =>
                    update({
                      scheme: event.currentTarget.value as PresentationPreferences['scheme'],
                    })
                  }
                >
                  <option value="theme">Predeterminado del tema</option>
                  <option value="light">Claro</option>
                  <option value="dark">Oscuro</option>
                </select>
              </label>
              <label className="workshop-mode">
                <input
                  type="checkbox"
                  checked={preferences.density === 'workshop'}
                  onChange={(event: ChangeEvent<HTMLInputElement>) =>
                    update({ density: event.currentTarget.checked ? 'workshop' : 'comfortable' })
                  }
                />
                <span>
                  Modo taller<small>Controles de 56 px y texto más amplio</small>
                </span>
              </label>
            </div>
            <button
              type="button"
              className="secondary-button"
              onClick={() =>
                update({
                  themeId: 'banco',
                  paletteId: 'bosque',
                  scheme: 'theme',
                  density: 'comfortable',
                })
              }
            >
              Restablecer mi apariencia
            </button>
          </fieldset>
          <fieldset disabled={!loaded || !locationId} className="logo-settings">
            <legend>Logo local para mi vista</legend>
            <p>
              Solo cambia tu vista de este taller en este dispositivo. La identidad compartida del
              taller todavía no se edita aquí.
            </p>
            <label>
              Archivo de logo local
              <input
                type="file"
                accept="image/png,image/jpeg"
                aria-describedby="logo-help"
                onChange={(event: ChangeEvent<HTMLInputElement>) => {
                  const file = event.currentTarget.files?.[0]
                  event.currentTarget.value = ''
                  if (!file) return
                  const version = ++uploadVersion.current
                  setLogoPreview(null)
                  setLogoMessage('Preparando imagen local…')
                  void prepareLocalLogo(file)
                    .then((image) => {
                      if (version === uploadVersion.current) {
                        setLogoPreview(image)
                        setLogoMessage('Vista previa lista. Guarda el logo para aplicarlo.')
                      }
                    })
                    .catch((error: unknown) => {
                      if (version === uploadVersion.current)
                        setLogoMessage(
                          error instanceof Error ? error.message : 'No se pudo preparar la imagen.',
                        )
                    })
                }}
              />
            </label>
            <small id="logo-help">
              PNG o JPEG, máximo 2 MB y 4096 px por lado. Se reduce a 512 px; no se envía a un
              servidor.
            </small>
            {logoPreview ? (
              <div className="logo-preview">
                <img src={logoPreview} width="160" height="64" alt="Vista previa del logo local" />
                <button
                  type="button"
                  className="primary-button"
                  onClick={() => {
                    update({ logoDataUrl: logoPreview })
                    setLogoPreview(null)
                    setLogoMessage(null)
                  }}
                >
                  Usar logo en mi vista
                </button>
                <button
                  type="button"
                  className="secondary-button"
                  onClick={() => {
                    uploadVersion.current++
                    setLogoPreview(null)
                    setLogoMessage(null)
                  }}
                >
                  Descartar vista previa
                </button>
              </div>
            ) : null}
            <button
              type="button"
              className="secondary-button"
              onClick={() => {
                uploadVersion.current++
                setLogoPreview(null)
                setLogoMessage(null)
                update({ logoDataUrl: null })
              }}
            >
              Quitar mi logo local
            </button>
            {logoMessage ? <p role="status">{logoMessage}</p> : null}
          </fieldset>
          <p className="preference-status" role="status" aria-live="polite">
            {message}
          </p>
        </section>
        <main id="workshop-content" tabIndex={-1}>
          <div className="workshop-heading">
            <div>
              <p className="eyebrow">Open Cycling Workshop</p>
              <h1>
                {preferences.themeId === 'plano'
                  ? 'Resumen de operaciones'
                  : preferences.themeId === 'ritmo'
                    ? 'Cada orden, su siguiente paso'
                    : preferences.themeId === 'noche'
                      ? 'Tu turno, en foco'
                      : 'El taller, hoy'}
              </h1>
              <p>Clientes y órdenes guardados primero en este dispositivo.</p>
            </div>
            {canCreateOrders ? (
              <a className="primary-button" href="#order-intake-title">
                + Nueva orden
              </a>
            ) : null}
          </div>
          {children}
        </main>
      </div>
    </div>
  )
}

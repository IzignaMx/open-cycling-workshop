import { useCallback, useEffect, useMemo, useState } from 'react'

import { ApiClient, ApiError, type CurrentUserResponse, type LoginRequest } from '@ocwp/api-client'
import { defaultBrand } from '@ocwp/branding'
import { Button } from '@ocwp/ui'

import { hasCapability } from './auth/capabilities.js'
import { LoginForm } from './auth/LoginForm.js'
import { shouldClearSessionAfterAuthError } from './auth/session-policy.js'
import { SessionStore } from './auth/session.js'
import { CustomerQuickCreate } from './features/customers/CustomerQuickCreate.js'
import { CustomerLocalRepository } from './features/customers/repository.js'
import { ConflictCenter } from './features/sync/ConflictCenter.js'
import { SyncStatus } from './features/sync/SyncStatus.js'
import type { SyncVisualState } from './features/sync/status-model.js'
import { db } from './local/db.js'
import type { ConflictRecord } from './local/types.js'
import { SyncCoordinator } from './sync/coordinator.js'
import { DexieSyncStore } from './sync/dexie-store.js'
import {
  HttpSyncTransport,
  SyncTransportError,
  SyncTransportOfflineError,
} from './sync/http-transport.js'
import { syncScopeKey } from './sync/scope.js'

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? ''

export function App() {
  const repository = useMemo(() => new CustomerLocalRepository(db), [])
  const sessionStore = useMemo(() => new SessionStore(window.sessionStorage), [])
  const api = useMemo(
    () =>
      new ApiClient({
        baseUrl: apiBaseUrl,
        tokenProvider: () => sessionStore.getToken(),
      }),
    [sessionStore],
  )

  const initialSnapshot = useMemo(() => sessionStore.getSnapshot(), [sessionStore])
  const [currentUser, setCurrentUser] = useState<CurrentUserResponse | null>(
    initialSnapshot?.user ?? null,
  )
  const [authBusy, setAuthBusy] = useState(false)
  // Derived once at mount: a persisted session that starts offline informs the
  // user immediately without a synchronous setState inside an effect.
  const [authMessage, setAuthMessage] = useState<string | null>(() => {
    const snapshot = initialSnapshot
    if (snapshot?.token && snapshot.user && !navigator.onLine) {
      return 'Sesión local activa. Se revalidará cuando vuelva la conexión.'
    }
    return null
  })
  const [lastCustomer, setLastCustomer] = useState<string | null>(null)
  const [conflicts, setConflicts] = useState<ConflictRecord[]>([])
  const [syncState, setSyncState] = useState<SyncVisualState>(() =>
    navigator.onLine ? 'local' : 'offline',
  )

  const syncScope = useMemo(() => {
    if (!currentUser?.location_id) return null
    return {
      organizationId: currentUser.organization_id,
      locationId: currentUser.location_id,
    }
  }, [currentUser])

  const coordinator = useMemo(() => {
    if (!syncScope) return null
    return new SyncCoordinator({
      store: new DexieSyncStore(db, syncScope),
      transport: new HttpSyncTransport(apiBaseUrl, () => sessionStore.getToken()),
      locationId: syncScope.locationId,
    })
  }, [sessionStore, syncScope])

  const refreshConflicts = useCallback(async (): Promise<ConflictRecord[]> => {
    // Every path awaits before setState so effects can invoke this without a
    // synchronous state update cascading inside the effect body.
    const pending = syncScope
      ? db.conflicts
          .where('scope_key')
          .equals(syncScopeKey(syncScope.organizationId, syncScope.locationId))
          .toArray()
      : Promise.resolve<ConflictRecord[]>([])
    const items = await pending
    setConflicts(items)
    return items
  }, [syncScope])

  const runSync = useCallback(async () => {
    if (!coordinator) return

    // Attempt the real transport even when navigator.onLine claims offline:
    // the browser signal is unreliable and the transport classifies network
    // failures as offline by itself, so an optimistic attempt is the only way
    // to discover that connectivity has returned.
    setSyncState('syncing')
    try {
      const result = await coordinator.runOnce({ online: true })
      const storedConflicts = await refreshConflicts()
      setSyncState(result.conflicts > 0 || storedConflicts.length > 0 ? 'conflict' : 'synced')
    } catch (error) {
      if (error instanceof SyncTransportOfflineError) {
        setSyncState('offline')
        return
      }
      if (error instanceof SyncTransportError && error.status === 401) {
        sessionStore.clear()
        setCurrentUser(null)
        setAuthMessage(
          'La sesión expiró. Tus cambios locales siguen guardados. Inicia sesión para sincronizarlos.',
        )
      }
      // A failure while the device is offline is the offline state, not an
      // error: local changes are safe and the queue retries on reconnect.
      setSyncState(navigator.onLine ? 'error' : 'offline')
    }
  }, [coordinator, refreshConflicts, sessionStore])

  useEffect(() => {
    const snapshot = sessionStore.getSnapshot()
    if (!snapshot?.token) return
    if (!navigator.onLine) return

    let cancelled = false
    void api
      .me()
      .then((user) => {
        if (cancelled) return
        sessionStore.setUser(user)
        setCurrentUser(user)
        setAuthMessage(null)
      })
      .catch((error: unknown) => {
        if (cancelled) return
        const status = error instanceof ApiError ? error.status : null
        if (shouldClearSessionAfterAuthError(status)) {
          sessionStore.clear()
          setCurrentUser(null)
          setAuthMessage('La sesión expiró. Inicia sesión nuevamente.')
        } else if (snapshot.user) {
          setAuthMessage('No se pudo revalidar la sesión. El trabajo local continúa disponible.')
        }
      })

    return () => {
      cancelled = true
    }
  }, [api, sessionStore])

  useEffect(() => {
    const online = () => void runSync()
    const offline = () => setSyncState('offline')
    window.addEventListener('online', online)
    window.addEventListener('offline', offline)
    return () => {
      window.removeEventListener('online', online)
      window.removeEventListener('offline', offline)
    }
  }, [runSync])

  useEffect(() => {
    // Bounded periodic retry while offline: navigator.onLine and the window
    // 'online' event are not reliable in every browser state, so the only
    // trustworthy reconnect signal is a real transport attempt.
    if (syncState !== 'offline') return
    const timer = window.setTimeout(() => void runSync(), 2000)
    return () => window.clearTimeout(timer)
  }, [syncState, runSync])

  useEffect(() => {
    if (!currentUser) return
    let cancelled = false
    // Both functions setState; running them inside an async continuation keeps
    // the effect body free of synchronous state updates.
    void (async () => {
      await refreshConflicts()
      if (!cancelled) await runSync()
    })()
    return () => {
      cancelled = true
    }
  }, [currentUser, refreshConflicts, runSync])

  async function login(input: LoginRequest) {
    setAuthBusy(true)
    setAuthMessage(null)
    try {
      const loginResponse = await api.login(input)
      sessionStore.setToken(loginResponse.access_token)
      const user = await api.me()
      sessionStore.setUser(user)
      setCurrentUser(user)
    } catch (error) {
      sessionStore.clear()
      setCurrentUser(null)
      if (error instanceof ApiError && error.status === 401)
        throw new Error('Credenciales inválidas')
      throw error
    } finally {
      setAuthBusy(false)
    }
  }

  function logoutLocal() {
    sessionStore.clear()
    setCurrentUser(null)
    setConflicts([])
    setLastCustomer(null)
    setSyncState(navigator.onLine ? 'local' : 'offline')
    setAuthMessage(null)
  }

  async function revokeSessions() {
    setAuthBusy(true)
    try {
      await api.logoutAll()
      logoutLocal()
    } catch {
      setAuthMessage('No se pudieron revocar las sesiones remotas. Puedes cerrar sólo esta sesión.')
    } finally {
      setAuthBusy(false)
    }
  }

  if (!currentUser) {
    return (
      <main className="mx-auto grid min-h-screen max-w-lg content-center gap-8 px-5 py-10">
        <header className="grid gap-3">
          <p className="text-sm font-semibold uppercase tracking-[0.16em] text-[var(--ocwp-color-accent-strong)]">
            {defaultBrand.shortName}
          </p>
          <h1 className="text-4xl font-semibold tracking-tight">Acceso al taller</h1>
          <p className="leading-7 text-[var(--ocwp-color-muted)]">
            Inicia sesión una vez para trabajar con el scope de tu organización y ubicación, incluso
            durante interrupciones temporales de red.
          </p>
        </header>
        <section className="rounded-2xl border border-[var(--ocwp-color-border)] bg-[var(--ocwp-color-surface)] p-5 shadow-sm">
          <LoginForm busy={authBusy} message={authMessage} onLogin={login} />
        </section>
      </main>
    )
  }

  const canCreateCustomers =
    Boolean(currentUser.location_id) && hasCapability(currentUser.capabilities, 'customers.write')

  return (
    <main className="mx-auto grid min-h-screen max-w-5xl gap-8 px-5 py-8 md:grid-cols-[1fr_22rem]">
      <section className="grid content-start gap-5">
        <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-[var(--ocwp-color-muted)]">
          <span>V0.1 · local-first bootstrap</span>
          <span>
            Sesión:{' '}
            <strong className="text-[var(--ocwp-color-text)]">{currentUser.display_name}</strong>
          </span>
        </div>
        <div className="grid gap-3">
          <p className="text-sm font-semibold uppercase tracking-[0.16em] text-[var(--ocwp-color-accent-strong)]">
            {defaultBrand.shortName}
          </p>
          <h1 className="max-w-3xl text-4xl font-semibold tracking-tight md:text-6xl">
            Operación de taller que no se detiene cuando falla Internet.
          </h1>
          <p className="max-w-2xl text-lg leading-8 text-[var(--ocwp-color-muted)]">
            Los clientes se guardan primero en este dispositivo. La sincronización ocurre después y
            nunca convierte una operación local válida en un error por una caída de red.
          </p>
        </div>
        <SyncStatus state={syncState} />
        {authMessage ? (
          <p
            role="status"
            className="rounded-xl border border-[var(--ocwp-color-border)] p-4 text-sm"
          >
            {authMessage}
          </p>
        ) : null}
        {lastCustomer ? (
          <div
            className="rounded-xl border border-[var(--ocwp-color-border)] bg-white p-4"
            role="status"
          >
            Último cliente local: <strong>{lastCustomer}</strong>
          </div>
        ) : null}
        <div className="flex flex-wrap gap-3">
          <Button type="button" onClick={() => void runSync()}>
            Sincronizar ahora
          </Button>
          <Button type="button" onClick={logoutLocal}>
            Cerrar esta sesión
          </Button>
          <Button
            type="button"
            disabled={authBusy || !navigator.onLine}
            onClick={() => void revokeSessions()}
          >
            Revocar todas las sesiones
          </Button>
        </div>
      </section>

      <aside className="grid content-start gap-5">
        <section className="rounded-2xl border border-[var(--ocwp-color-border)] bg-[var(--ocwp-color-surface)] p-5 shadow-sm">
          <h2 className="mb-4 text-xl font-semibold">Alta rápida</h2>
          {!currentUser.location_id ? (
            <p className="text-sm leading-6 text-[var(--ocwp-color-muted)]">
              Este usuario no tiene una ubicación activa. Selecciona o asigna una ubicación antes de
              registrar clientes.
            </p>
          ) : !canCreateCustomers ? (
            <p className="text-sm leading-6 text-[var(--ocwp-color-muted)]">
              Tu sesión actual no tiene la capability <code>customers.write</code>.
            </p>
          ) : (
            <CustomerQuickCreate
              onCreate={async (input) => {
                const locationId = currentUser.location_id
                if (!locationId) throw new Error('Se requiere una ubicación activa')
                const customer = await repository.create({
                  organizationId: currentUser.organization_id,
                  locationId,
                  ...input,
                })
                setLastCustomer(customer.display_name)
                setSyncState(navigator.onLine ? 'local' : 'offline')
                void runSync()
              }}
            />
          )}
        </section>
        <ConflictCenter
          conflicts={conflicts}
          onRefresh={async () => {
            await refreshConflicts()
          }}
        />
      </aside>
    </main>
  )
}

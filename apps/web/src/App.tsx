import { useCallback, useEffect, useMemo, useState } from 'react'

import { ApiClient, ApiError, type CurrentUserResponse, type LoginRequest } from '@ocwp/api-client'
import { defaultBrand } from '@ocwp/branding'
import { Button } from '@ocwp/ui'

import { hasCapability } from './auth/capabilities.js'
import { LoginForm } from './auth/LoginForm.js'
import { shouldClearSessionAfterAuthError } from './auth/session-policy.js'
import { SessionStore } from './auth/session.js'
import { SessionViewGeneration } from './auth/view-generation.js'
import { BicycleLocalRepository } from './features/bicycles/repository.js'
import { CustomerQuickCreate } from './features/customers/CustomerQuickCreate.js'
import { CustomerLocalRepository } from './features/customers/repository.js'
import { OrderList } from './features/orders/OrderList.js'
import { OrderQuickIntake } from './features/orders/OrderQuickIntake.js'
import { ServiceOrderLocalRepository } from './features/orders/repository.js'
import type { OrderAction } from './features/orders/state-machine.js'
import { ConflictCenter } from './features/sync/ConflictCenter.js'
import { SyncStatus } from './features/sync/SyncStatus.js'
import type { SyncVisualState } from './features/sync/status-model.js'
import { db } from './local/db.js'
import { WorkshopShell } from './personalization/WorkshopShell.js'
import { preferenceScopeKey } from './personalization/preferences.js'
import type { LocalServiceOrder, LocalServiceOrderEvent } from './local/service-order-types.js'
import type { ConflictRecord } from './local/types.js'
import { SyncCoordinator } from './sync/coordinator.js'
import { DexieSyncStore } from './sync/dexie-store.js'
import {
  HttpSyncTransport,
  SyncTransportError,
  SyncTransportOfflineError,
} from './sync/http-transport.js'
import { retryPlan } from './sync/retry-policy.js'
import { syncScopeKey } from './sync/scope.js'

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? ''

interface CustomerRow {
  organization_id: string
  location_id: string
  customer_id: string
  display_name: string
}

export function App() {
  const repository = useMemo(() => new CustomerLocalRepository(db), [])
  const bicycleRepository = useMemo(() => new BicycleLocalRepository(db), [])
  const orderRepository = useMemo(() => new ServiceOrderLocalRepository(db), [])
  const sessionStore = useMemo(() => new SessionStore(window.sessionStorage), [])
  const viewGeneration = useMemo(() => new SessionViewGeneration(), [])
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
  const [lastCustomer, setLastCustomer] = useState<{
    displayName: string
    userId: string
    organizationId: string
    locationId: string
  } | null>(null)
  const [localCustomers, setLocalCustomers] = useState<CustomerRow[]>([])
  const [orders, setOrders] = useState<LocalServiceOrder[]>([])
  const [orderEvents, setOrderEvents] = useState<LocalServiceOrderEvent[]>([])
  const [conflicts, setConflicts] = useState<ConflictRecord[]>([])
  const [syncState, setSyncState] = useState<SyncVisualState>(() =>
    navigator.onLine ? 'local' : 'offline',
  )
  const [retryAttempt, setRetryAttempt] = useState(0)

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
    const ticket = viewGeneration.capture(currentUser)
    // Every path awaits before setState so effects can invoke this without a
    // synchronous state update cascading inside the effect body.
    const pending = syncScope
      ? db.conflicts
          .where('scope_key')
          .equals(syncScopeKey(syncScope.organizationId, syncScope.locationId))
          .toArray()
      : Promise.resolve<ConflictRecord[]>([])
    const items = await pending
    if (!viewGeneration.isCurrent(ticket, sessionStore.getSnapshot()?.user ?? null)) return []
    setConflicts(items)
    return items
  }, [syncScope, currentUser, sessionStore, viewGeneration])

  const refreshWorkshopData = useCallback(async (): Promise<void> => {
    const ticket = viewGeneration.capture(currentUser)
    // Await-first so effects can call this without synchronous setState.
    if (!syncScope) {
      if (!viewGeneration.isCurrent(ticket, sessionStore.getSnapshot()?.user ?? null)) return
      setLocalCustomers([])
      setOrders([])
      setOrderEvents([])
      return
    }
    const [customers, orderRows, eventRows] = await Promise.all([
      db.customers
        .where('organization_id')
        .equals(syncScope.organizationId)
        .toArray()
        .then((rows) =>
          rows
            .filter((row) => row.location_id === syncScope.locationId)
            .map((row) => ({
              customer_id: row.customer_id,
              display_name: row.display_name,
              organization_id: row.organization_id,
              location_id: row.location_id,
            })),
        ),
      db.serviceOrders
        .where('organization_id')
        .equals(syncScope.organizationId)
        .toArray()
        .then((rows) =>
          rows
            .filter((row) => row.location_id === syncScope.locationId)
            .sort((a, b) => a.created_at.localeCompare(b.created_at)),
        ),
      db.serviceOrderEvents.toArray(),
    ])
    if (!viewGeneration.isCurrent(ticket, sessionStore.getSnapshot()?.user ?? null)) return
    setLocalCustomers(customers)
    setOrders(orderRows)
    setOrderEvents(eventRows)
  }, [syncScope, currentUser, sessionStore, viewGeneration])

  const runSync = useCallback(async () => {
    if (!coordinator) return
    const ticket = viewGeneration.capture(currentUser)
    if (!viewGeneration.isCurrent(ticket, sessionStore.getSnapshot()?.user ?? null)) return

    // Attempt the real transport even when navigator.onLine claims offline:
    // the browser signal is unreliable and the transport classifies network
    // failures as offline by itself, so an optimistic attempt is the only way
    // to discover that connectivity has returned.
    setSyncState('syncing')
    try {
      const result = await coordinator.runOnce({ online: true })
      if (!viewGeneration.isCurrent(ticket, sessionStore.getSnapshot()?.user ?? null)) return
      const storedConflicts = await refreshConflicts()
      if (!viewGeneration.isCurrent(ticket, sessionStore.getSnapshot()?.user ?? null)) return
      setSyncState(result.conflicts > 0 || storedConflicts.length > 0 ? 'conflict' : 'synced')
      setRetryAttempt(0)
    } catch (error) {
      if (!viewGeneration.isCurrent(ticket, sessionStore.getSnapshot()?.user ?? null)) return
      if (error instanceof SyncTransportOfflineError) {
        setSyncState('offline')
        return
      }
      if (error instanceof SyncTransportError && error.status === 401) {
        viewGeneration.advance()
        sessionStore.clear()
        setAuthBusy(false)
        setCurrentUser(null)
        setAuthMessage(
          'La sesión expiró. Tus cambios locales siguen guardados. Inicia sesión para sincronizarlos.',
        )
      }
      // A failure while the device is offline is the offline state, not an
      // error: local changes are safe and the queue retries on reconnect.
      setSyncState(navigator.onLine ? 'error' : 'offline')
    }
  }, [coordinator, refreshConflicts, sessionStore, currentUser, viewGeneration])

  useEffect(() => {
    const snapshot = sessionStore.getSnapshot()
    if (!snapshot?.token) return
    if (!navigator.onLine) return

    let cancelled = false
    const ticket = viewGeneration.capture(snapshot.user)
    void api
      .me()
      .then((user) => {
        if (
          cancelled ||
          !viewGeneration.isCurrent(ticket, sessionStore.getSnapshot()?.user ?? null)
        )
          return
        sessionStore.setUser(user)
        setCurrentUser(user)
        setAuthMessage(null)
      })
      .catch((error: unknown) => {
        if (
          cancelled ||
          !viewGeneration.isCurrent(ticket, sessionStore.getSnapshot()?.user ?? null)
        )
          return
        const status = error instanceof ApiError ? error.status : null
        if (shouldClearSessionAfterAuthError(status)) {
          viewGeneration.advance()
          sessionStore.clear()
          setAuthBusy(false)
          setCurrentUser(null)
          setAuthMessage('La sesión expiró. Inicia sesión nuevamente.')
        } else if (snapshot.user) {
          setAuthMessage('No se pudo revalidar la sesión. El trabajo local continúa disponible.')
        }
      })

    return () => {
      cancelled = true
    }
  }, [api, sessionStore, viewGeneration])

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
    // Bounded exponential backoff for transient outcomes (offline and
    // temporary server failures). navigator.onLine and the window 'online'
    // event are not reliable in every browser state, and 5xx responses must
    // also re-attempt, so the trustworthy signal is a real transport attempt
    // under a bounded budget. Permanent failures never schedule retries: they
    // surface in the Conflict Center.
    if (syncState !== 'offline' && syncState !== 'error') return
    if (!coordinator) return
    const plan = retryPlan(retryAttempt)
    if (plan.exhausted) return
    const timer = window.setTimeout(() => {
      setRetryAttempt((attempt) => attempt + 1)
      void runSync()
    }, plan.delayMs)
    return () => window.clearTimeout(timer)
  }, [syncState, retryAttempt, coordinator, runSync])

  useEffect(() => {
    if (!currentUser) return
    let cancelled = false
    // Both functions setState; running them inside an async continuation keeps
    // the effect body free of synchronous state updates.
    void (async () => {
      await refreshWorkshopData()
      await refreshConflicts()
      if (!cancelled) await runSync()
    })()
    return () => {
      cancelled = true
    }
  }, [currentUser, refreshConflicts, refreshWorkshopData, runSync])

  async function login(input: LoginRequest) {
    const generation = viewGeneration.advance()
    setAuthBusy(true)
    setAuthMessage(null)
    try {
      const loginResponse = await api.login(input)
      if (!viewGeneration.isGenerationCurrent(generation)) return
      sessionStore.setToken(loginResponse.access_token)
      const user = await api.me()
      if (!viewGeneration.isGenerationCurrent(generation)) return
      sessionStore.setUser(user)
      setCurrentUser(user)
    } catch (error) {
      if (!viewGeneration.isGenerationCurrent(generation)) return
      sessionStore.clear()
      setCurrentUser(null)
      if (error instanceof ApiError && error.status === 401)
        throw new Error('Credenciales inválidas')
      throw error
    } finally {
      if (viewGeneration.isGenerationCurrent(generation)) setAuthBusy(false)
    }
  }

  function logoutLocal() {
    viewGeneration.advance()
    sessionStore.clear()
    setCurrentUser(null)
    setConflicts([])
    setAuthBusy(false)
    setLastCustomer(null)
    setSyncState(navigator.onLine ? 'local' : 'offline')
    setAuthMessage(null)
  }

  async function revokeSessions() {
    const ticket = viewGeneration.capture(currentUser)
    setAuthBusy(true)
    try {
      await api.logoutAll()
      if (viewGeneration.isCurrent(ticket, sessionStore.getSnapshot()?.user ?? null)) logoutLocal()
    } catch {
      if (!viewGeneration.isCurrent(ticket, sessionStore.getSnapshot()?.user ?? null)) return
      setAuthMessage('No se pudieron revocar las sesiones remotas. Puedes cerrar sólo esta sesión.')
    } finally {
      if (viewGeneration.isCurrent(ticket, sessionStore.getSnapshot()?.user ?? null))
        setAuthBusy(false)
    }
  }

  async function createOrder(input: {
    customerId: string
    reportedProblem: string
    intakeCondition: string | null
    accessories: string | null
    priority: string
    brand: string | null
    model: string | null
  }): Promise<void> {
    const ticket = viewGeneration.capture(currentUser)
    const scope = syncScope
    if (!scope) throw new Error('Se requiere una ubicación activa')
    let bicycleId: string | null = null
    if (input.brand) {
      const bicycle = await bicycleRepository.create({
        organizationId: scope.organizationId,
        locationId: scope.locationId,
        customerId: input.customerId,
        brand: input.brand,
        model: input.model,
      })
      bicycleId = bicycle.bicycle_id
    }
    await orderRepository.create({
      organizationId: scope.organizationId,
      locationId: scope.locationId,
      customerId: input.customerId,
      bicycleId,
      reportedProblem: input.reportedProblem,
      intakeCondition: input.intakeCondition,
      accessories: input.accessories,
      priority: input.priority,
    })
    if (!viewGeneration.isCurrent(ticket, sessionStore.getSnapshot()?.user ?? null)) return
    setSyncState(navigator.onLine ? 'local' : 'offline')
    await refreshWorkshopData()
    void runSync()
  }

  async function transitionOrder(order: LocalServiceOrder, action: OrderAction): Promise<void> {
    if (!currentUser || !hasCapability(currentUser.capabilities, 'orders.write')) return
    const ticket = viewGeneration.capture(currentUser)
    await orderRepository.applyTransition(order, action, { actorId: currentUser.user_id })
    if (!viewGeneration.isCurrent(ticket, sessionStore.getSnapshot()?.user ?? null)) return
    setSyncState(navigator.onLine ? 'local' : 'offline')
    await refreshWorkshopData()
    void runSync()
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
  const canCreateOrders =
    Boolean(currentUser.location_id) && hasCapability(currentUser.capabilities, 'orders.write')

  const preferenceScope = {
    organizationId: currentUser.organization_id,
    userId: currentUser.user_id,
    locationId: currentUser.location_id,
  }
  // Also scope the render during identity changes, before the asynchronous refresh completes.
  const visibleCustomers = localCustomers.filter(
    (row) =>
      row.organization_id === currentUser.organization_id &&
      row.location_id === currentUser.location_id,
  )
  const visibleOrders = orders.filter(
    (row) =>
      row.organization_id === currentUser.organization_id &&
      row.location_id === currentUser.location_id,
  )
  const visibleLastCustomer =
    lastCustomer?.userId === currentUser.user_id &&
    lastCustomer.organizationId === currentUser.organization_id &&
    lastCustomer.locationId === currentUser.location_id
      ? lastCustomer.displayName
      : null
  const activeOrders = visibleOrders.filter(
    (order) => !['CLOSED', 'CANCELLED', 'REJECTED'].includes(order.state),
  )

  return (
    <WorkshopShell
      key={preferenceScopeKey(preferenceScope, 'logo')}
      scope={preferenceScope}
      userName={currentUser.display_name}
      canCreateOrders={canCreateOrders}
    >
      <SyncStatus state={syncState} />
      {authMessage ? (
        <p role="status" className="workshop-notice">
          {authMessage}
        </p>
      ) : null}
      {visibleLastCustomer ? (
        <p role="status" className="workshop-notice">
          Último cliente local: <strong>{visibleLastCustomer}</strong>
        </p>
      ) : null}
      <dl className="workshop-metrics" aria-label="Resumen local del taller">
        <div>
          <dt>Órdenes activas</dt>
          <dd>{activeOrders.length}</dd>
        </div>
        <div>
          <dt>Listas para entrega</dt>
          <dd>{visibleOrders.filter((order) => order.state === 'READY').length}</dd>
        </div>
        <div>
          <dt>Esperan refacción</dt>
          <dd>{visibleOrders.filter((order) => order.state === 'WAITING_FOR_PARTS').length}</dd>
        </div>
        <div>
          <dt>Clientes locales</dt>
          <dd>{visibleCustomers.length}</dd>
        </div>
      </dl>
      <section id="workshop-orders" className="orders-workspace" aria-labelledby="orders-title">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Cola local</p>
            <h2 id="orders-title">Órdenes de servicio</h2>
          </div>
          <span className="muted">{visibleOrders.length} registradas</span>
        </div>
        <OrderList
          orders={visibleOrders}
          events={orderEvents}
          onTransition={transitionOrder}
          canTransition={canCreateOrders}
        />
      </section>
      <section
        id="workshop-reception"
        className="reception-workspace"
        aria-label="Recepción del taller"
      >
        <section className="workshop-panel" aria-labelledby="customer-create-title">
          <h2 id="customer-create-title">Alta rápida</h2>
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
                const ticket = viewGeneration.capture(currentUser)
                const locationId = currentUser.location_id
                if (!locationId) throw new Error('Se requiere una ubicación activa')
                const customer = await repository.create({
                  organizationId: currentUser.organization_id,
                  locationId,
                  ...input,
                })
                if (!viewGeneration.isCurrent(ticket, sessionStore.getSnapshot()?.user ?? null))
                  return
                setLastCustomer({
                  displayName: customer.display_name,
                  userId: currentUser.user_id,
                  organizationId: currentUser.organization_id,
                  locationId,
                })
                setSyncState(navigator.onLine ? 'local' : 'offline')
                await refreshWorkshopData()
                void runSync()
              }}
            />
          )}
        </section>
        <section aria-labelledby="order-intake-title" className="workshop-panel">
          <h2 id="order-intake-title" tabIndex={-1}>
            Nueva orden de servicio
          </h2>
          {!canCreateOrders ? (
            <p className="text-sm leading-6 text-[var(--ocwp-color-muted)]">
              Tu sesión actual no tiene la capability <code>orders.write</code>.
            </p>
          ) : (
            <OrderQuickIntake customers={visibleCustomers} onCreateOrder={createOrder} />
          )}
        </section>
      </section>
      <section id="workshop-issues" aria-label="Incidencias de sincronización">
        <ConflictCenter
          conflicts={conflicts.filter(
            (row) =>
              row.organization_id === currentUser.organization_id &&
              row.location_id === currentUser.location_id,
          )}
          onRefresh={async () => {
            await refreshConflicts()
          }}
        />
      </section>
      <section className="workshop-panel session-actions" aria-label="Sesión y sincronización">
        <div>
          <h2>Sesión y sincronización</h2>
          <p className="muted">
            Tus datos operativos y sus permisos son los mismos en los cuatro temas.
          </p>
        </div>
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
      </section>
      <footer className="workshop-footer">
        OCWP · Local first · Los cambios pendientes se conservan en este dispositivo.
      </footer>
    </WorkshopShell>
  )
}

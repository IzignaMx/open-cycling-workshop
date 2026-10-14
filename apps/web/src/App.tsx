import {
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useSyncExternalStore,
  type FormEvent,
} from 'react'
import { AdministrationPanel } from './features/administration/AdministrationPanel.js'
import { AdministrationController } from './features/administration/controller.js'
import './features/administration/administration.css'
import { Button } from '@ocwp/ui'
import { LoginForm } from './auth/LoginForm.js'
import { CustomerQuickCreate } from './features/customers/CustomerQuickCreate.js'
import { OrderList } from './features/orders/OrderList.js'
import { OrderQuickIntake } from './features/orders/OrderQuickIntake.js'
import { ConflictCenter } from './features/sync/ConflictCenter.js'
import { SyncStatus } from './features/sync/SyncStatus.js'
import { WorkshopShell } from './personalization/WorkshopShell.js'
import type { WorkshopController } from './runtime/controller.js'

export function App({ runtime }: { runtime: WorkshopController }) {
  const state = useSyncExternalStore(runtime.subscribe, runtime.getSnapshot)
  const operationalDirty = useRef(false)
  const leaveWorkshop = (action: () => Promise<void>) => {
    if (
      (operationalDirty.current ||
        document.querySelector('#workshop-administration [data-dirty="true"]')) &&
      !window.confirm(
        '¿Continuar y descartar los formularios sin enviar? El trabajo local ya guardado se conserva.',
      )
    )
      return
    operationalDirty.current = false
    void action()
  }
  const administration = useMemo(() => new AdministrationController(runtime), [runtime])
  useLayoutEffect(() => {
    administration.setLogoutGuard(
      () =>
        !(
          operationalDirty.current ||
          document.querySelector('#workshop-administration [data-dirty="true"]')
        ) ||
        window.confirm(
          '¿Continuar y descartar los formularios sin enviar? El trabajo local ya guardado se conserva.',
        ),
    )
  }, [administration])
  useEffect(() => () => administration.dispose(), [administration])
  useEffect(() => {
    void runtime.start()
    const online = () => void runtime.reconnect(),
      offline = () => void runtime.offline(),
      check = () => void runtime.checkLease()
    window.addEventListener('online', online)
    window.addEventListener('offline', offline)
    window.addEventListener('focus', check)
    window.addEventListener('pageshow', check)
    document.addEventListener('visibilitychange', check)
    return () => {
      window.removeEventListener('online', online)
      window.removeEventListener('offline', offline)
      window.removeEventListener('focus', check)
      window.removeEventListener('pageshow', check)
      document.removeEventListener('visibilitychange', check)
    }
  }, [runtime])
  const legacy = state.legacyPresent ? (
    <p role="status" className="workshop-notice">
      Hay datos de una versión anterior en este dispositivo. Se conservan por separado; no se han
      atribuido ni reenviado con esta sesión.
    </p>
  ) : null
  if (state.phase === 'selector')
    return (
      <main className="login-shell" data-runtime-state="SELECTOR">
        <section className="workshop-panel">
          <h1>Selecciona un taller</h1>
          <p>Cuenta: {state.user?.display_name}. La selección limita los datos de esta vista.</p>
          <p role="status">{state.message}</p>
          <ul className="workshop-selector-options">
            {state.locations.map((location) => (
              <li key={location.location_id}>
                <Button
                  type="button"
                  onClick={() => void runtime.selectWorkshop(location.location_id)}
                >
                  {location.name}
                </Button>
              </li>
            ))}
          </ul>
          <div className="session-actions">
            <Button type="button" onClick={() => void runtime.loadLocations()}>
              Primera página
            </Button>
            {state.nextLocation ? (
              <Button type="button" onClick={() => void runtime.loadLocations(state.nextLocation!)}>
                Más talleres
              </Button>
            ) : null}
            <Button type="button" onClick={() => leaveWorkshop(() => runtime.logout())}>
              Cerrar esta sesión
            </Button>
          </div>
          {legacy}
          <AdministrationPanel controller={administration} selectedLocationId={null} />
        </section>
      </main>
    )
  if (state.phase !== 'ready' || !state.user || !state.context || !runtime.preferences)
    return (
      <main className="login-shell" data-runtime-state={state.phase.toUpperCase()}>
        <section className="workshop-panel">
          <h1>Open Cycling Workshop</h1>
          <p>Acceso verificado al taller · primero en este dispositivo</p>
          {state.phase === 'baseline' ? (
            <>
              <h2>Preparando el taller</h2>
              <p role="status">{state.message}</p>
              <Button type="button" onClick={() => leaveWorkshop(() => runtime.logout())}>
                Cancelar y cerrar sesión
              </Button>
            </>
          ) : (
            <>
              <LoginForm
                key={state.identityKey}
                busy={state.phase === 'verifying'}
                message={state.message}
                onLogin={(input) => runtime.login(input)}
              />
              {state.phase === 'held' && runtime.sessionStore.getToken() ? (
                <Button type="button" onClick={() => void runtime.retryVerification()}>
                  Verificar sesión y reintentar
                </Button>
              ) : null}
              {state.phase === 'verifying' ? (
                <Button type="button" onClick={() => leaveWorkshop(() => runtime.logout())}>
                  Cancelar
                </Button>
              ) : null}
            </>
          )}
          {legacy}
          <AdministrationPanel controller={administration} selectedLocationId={null} />
        </section>
      </main>
    )
  const context = state.context,
    readCustomers = context.capabilities.includes('customers.read'),
    readOrders = context.capabilities.includes('orders.read'),
    writeCustomers = context.capabilities.includes('customers.write'),
    writeOrders = context.capabilities.includes('orders.write'),
    readBicycles = context.capabilities.includes('bicycles.read')
  const scope = {
    organizationId: context.principal.organizationId,
    userId: context.principal.userId,
    locationId: context.selectedLocationId,
  }
  return (
    <WorkshopShell
      key={state.identityKey}
      scope={scope}
      repository={runtime.preferences}
      userName={state.user.display_name}
      canCreateOrders={writeOrders}
    >
      <div
        data-runtime-state="READY"
        data-selected-workshop={context.selectedLocationId}
        onInputCapture={(event: FormEvent<HTMLDivElement>) => {
          if (
            !(event.currentTarget.ownerDocument.activeElement as HTMLElement).closest(
              '.administration-panel',
            )
          )
            operationalDirty.current = true
        }}
      >
        <SyncStatus state={state.sync} />
        {state.message ? (
          <p role="status" className="workshop-notice">
            {state.message}
          </p>
        ) : null}
        {legacy}
        <dl className="workshop-metrics" aria-label="Resumen local del taller">
          <div>
            <dt>Órdenes activas en esta página</dt>
            <dd>
              {readOrders
                ? state.orders.filter((o) => !['CLOSED', 'CANCELLED', 'REJECTED'].includes(o.state))
                    .length
                : 'Sin acceso'}
            </dd>
          </div>
          <div>
            <dt>Listas para entrega</dt>
            <dd>
              {readOrders ? state.orders.filter((o) => o.state === 'READY').length : 'Sin acceso'}
            </dd>
          </div>
          <div>
            <dt>Esperan refacción</dt>
            <dd>
              {readOrders
                ? state.orders.filter((o) => o.state === 'WAITING_FOR_PARTS').length
                : 'Sin acceso'}
            </dd>
          </div>
          <div>
            <dt>Clientes locales en esta página</dt>
            <dd>{readCustomers ? state.customers.length : 'Sin acceso'}</dd>
          </div>
        </dl>
        <section id="workshop-orders" className="orders-workspace" aria-labelledby="orders-title">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Cola local</p>
              <h2 id="orders-title">Órdenes de servicio</h2>
            </div>
            <span className="muted">
              {readOrders ? `${state.orders.length} en esta página` : 'Lectura restringida'}
            </span>
          </div>
          {readOrders ? (
            <>
              <OrderList
                orders={state.orders}
                events={state.events}
                canTransition={writeOrders}
                canReadBicycleInfo={readBicycles}
                onTransition={(order, action) => runtime.transition(order.order_id, action)}
                onTimeline={(orderId) => runtime.timeline(orderId)}
              />
              <div className="session-actions">
                <Button type="button" onClick={() => void runtime.refresh('service_order')}>
                  Primeras órdenes
                </Button>
                {state.orderAfter ? (
                  <Button
                    type="button"
                    onClick={() => void runtime.refresh('service_order', state.orderAfter!)}
                  >
                    Más órdenes
                  </Button>
                ) : null}
              </div>
              {state.timelineMessage ? <p role="status">{state.timelineMessage}</p> : null}
            </>
          ) : (
            <p className="empty-state">
              Tu sesión no tiene permiso para consultar órdenes (orders.read).
            </p>
          )}
        </section>
        <section
          id="workshop-reception"
          className="reception-workspace"
          aria-label="Recepción del taller"
        >
          <section className="workshop-panel" aria-labelledby="customer-create-title">
            <h2 id="customer-create-title">Alta rápida</h2>
            {writeCustomers ? (
              <CustomerQuickCreate onCreate={(input) => runtime.createCustomer(input)} />
            ) : (
              <p>Tu sesión no tiene el permiso customers.write.</p>
            )}
            {readCustomers ? (
              <>
                <h3>Clientes locales</h3>
                <ul aria-label="Clientes locales">
                  {state.customers.map((customer) => (
                    <li key={customer.customer_id}>{customer.display_name}</li>
                  ))}
                </ul>
                <div className="session-actions">
                  <Button type="button" onClick={() => void runtime.refresh('customer')}>
                    Primeros clientes
                  </Button>
                  {state.customerAfter ? (
                    <Button
                      type="button"
                      onClick={() => void runtime.refresh('customer', state.customerAfter!)}
                    >
                      Más clientes
                    </Button>
                  ) : null}
                </div>
              </>
            ) : null}
          </section>
          <section className="workshop-panel" aria-labelledby="order-intake-title">
            <h2 id="order-intake-title" tabIndex={-1}>
              Nueva orden de servicio
            </h2>
            {writeOrders && readCustomers ? (
              <OrderQuickIntake
                customers={state.customers}
                onCreateOrder={(input) => runtime.createOrder(input)}
              />
            ) : (
              <p>Para registrar una orden necesitas orders.write y customers.read.</p>
            )}
          </section>
        </section>
        <section id="workshop-issues" aria-label="Incidencias de sincronización">
          <ConflictCenter
            issues={state.issues}
            hasIssues={state.hasIssues}
            onRefresh={() => runtime.loadIssues()}
          />
          {state.issueAfter !== null ? (
            <Button type="button" onClick={() => void runtime.loadIssues(state.issueAfter!)}>
              Más incidencias
            </Button>
          ) : null}
        </section>
        <section className="workshop-panel session-actions" aria-label="Sesión y sincronización">
          <div>
            <h2>Sesión y sincronización</h2>
            <p className="muted">
              Tus datos operativos y sus permisos son los mismos en los cuatro temas.
            </p>
          </div>
          <Button type="button" onClick={() => void runtime.sync()}>
            Sincronizar ahora
          </Button>
          {state.user.location_id === null ? (
            <Button type="button" onClick={() => leaveWorkshop(() => runtime.changeWorkshop())}>
              Cambiar taller
            </Button>
          ) : null}
          <Button type="button" onClick={() => leaveWorkshop(() => runtime.logout())}>
            Cerrar esta sesión
          </Button>
        </section>
        <AdministrationPanel
          controller={administration}
          selectedLocationId={context.selectedLocationId}
        />
        <footer className="workshop-footer">
          OCWP · Local first · Los cambios pendientes se conservan en este dispositivo.
        </footer>
      </div>
    </WorkshopShell>
  )
}

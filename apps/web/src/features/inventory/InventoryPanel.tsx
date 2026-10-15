import {
  useEffect,
  useRef,
  useState,
  useSyncExternalStore,
  type ChangeEvent,
  type RefObject,
} from 'react'
import { hasCapability } from '../../auth/capabilities.js'
import type { InventoryController, InventoryRead } from './controller.js'
import type { InventoryErrorCode } from './contracts.js'
import './inventory.css'
const errors: Record<InventoryErrorCode, string> = {
  stale_request: 'La lectura dejó de estar vigente. Verifica el acceso y vuelve a consultar.',
  invalid_session: 'La sesión ya no es válida. Inicia sesión de nuevo.',
  capability_denied: 'Tu sesión no tiene permiso para consultar inventario (inventory.read).',
  network_error:
    'No se pudo conectar con el inventario. Comprueba la conexión y vuelve a consultar.',
  invalid_response: 'La respuesta del inventario no es válida. No se muestran datos sin verificar.',
  unsupported_quantity:
    'La cantidad excede el rango numérico compatible. No se muestra un valor aproximado.',
  unavailable: 'El inventario no está disponible en el servidor. Vuelve a consultar más tarde.',
}
const localTime = (value: number | string) => new Date(value).toLocaleString()
const signed = (value: number) => (value > 0 ? `+${value}` : String(value))
function ReadStatus({ value, loading }: { value: InventoryRead<unknown>; loading: string }) {
  return (
    <div aria-live="polite" aria-atomic="true">
      {value.phase === 'loading' && <p role="status">{loading}</p>}
      {value.error && <p role="alert">{errors[value.error]}</p>}
    </div>
  )
}
export function InventoryPanel({ controller }: { controller: InventoryController }) {
  const state = useSyncExternalStore(
    controller.subscribe,
    controller.getSnapshot,
    controller.getSnapshot,
  )
  const [location, setLocation] = useState({ generation: -1, id: '' })
  const [online, setOnline] = useState(() => navigator.onLine)
  const catalogHeading = useRef<HTMLHeadingElement>(null),
    productHeading = useRef<HTMLHeadingElement>(null),
    historyHeading = useRef<HTMLHeadingElement>(null)
  const focusVersion = useRef({ sequence: 0 })
  useEffect(() => {
    const ownership = focusVersion.current
    const update = () => setOnline(navigator.onLine)
    window.addEventListener('online', update)
    window.addEventListener('offline', update)
    return () => {
      ownership.sequence++
      window.removeEventListener('online', update)
      window.removeEventListener('offline', update)
    }
  }, [])
  async function focusAfter(action: Promise<void>, target: RefObject<HTMLHeadingElement | null>) {
    const version = ++focusVersion.current.sequence
    await action
    if (version === focusVersion.current.sequence) target.current?.focus()
  }
  const ready = online && state.access.phase === 'ready'
  const allowed = ready && !!state.access.context?.capabilities.includes('inventory.read')
  const selected =
    location.generation === state.account.generation &&
    state.locations.some((row) => row.location_id === location.id)
      ? location.id
      : ''
  const canChoose =
    state.account.phase === 'connected' &&
    state.account.user?.location_id === null &&
    hasCapability(state.account.user.capabilities, 'locations.read')
  const verifying = state.access.phase === 'verifying' || state.account.phase === 'verifying'
  return (
    <section id="workshop-inventory" className="inventory-panel" aria-label="Inventario conectado">
      <header>
        <div>
          <p className="eyebrow">Consulta de piezas</p>
          <h2>Inventario conectado</h2>
        </div>
        <span className="inventory-connection">
          {!online
            ? 'Sin conexión'
            : ready
              ? 'Acceso conectado verificado'
              : 'Acceso pendiente de verificación'}
        </span>
      </header>
      <p>
        Consulta disponible solo con conexión. No se guarda inventario para uso sin conexión. El
        catálogo y los movimientos se consultan por páginas en vivo; pueden cambiar entre lecturas.
      </p>
      {!online ? (
        <p role="status">
          Inventario no disponible sin conexión. El trabajo local del taller se conserva.
        </p>
      ) : (
        <>
          {state.access.message && <p role="status">{state.access.message}</p>}
          {canChoose && (
            <div className="inventory-scope">
              <label>
                Taller para inventario
                <select
                  value={selected}
                  onChange={(event: ChangeEvent<HTMLSelectElement>) => {
                    controller.clearSelection()
                    setLocation({
                      generation: state.account.generation,
                      id: event.currentTarget.value,
                    })
                  }}
                >
                  <option value="">Usar el taller operativo seleccionado</option>
                  {state.locations.map((row) => (
                    <option key={row.location_id} value={row.location_id}>
                      {row.name}
                    </option>
                  ))}
                </select>
              </label>
              <button type="button" onClick={() => void controller.loadLocations()}>
                Consultar talleres
              </button>
              {state.nextLocation && (
                <button
                  type="button"
                  onClick={() => void controller.loadLocations(state.nextLocation!)}
                >
                  Más talleres para inventario
                </button>
              )}
            </div>
          )}
          {!ready && (
            <p>
              Se necesita una sesión verificada y un taller autorizado. Las cuentas asignadas a un
              taller pueden consultarlo directamente; las cuentas de toda la organización pueden
              elegirlo en su directorio autorizado.
            </p>
          )}
          <button
            type="button"
            className="inventory-primary"
            disabled={verifying || state.account.phase === 'suspended'}
            onClick={() => void focusAfter(controller.enter(selected || undefined), catalogHeading)}
          >
            {verifying
              ? 'Verificando inventario…'
              : ready
                ? 'Actualizar catálogo'
                : 'Verificar y consultar inventario'}
          </button>
          {ready && !allowed && <p role="alert">{errors.capability_denied}</p>}
        </>
      )}
      {allowed && (
        <>
          <section aria-labelledby="inventory-catalog-title">
            <h3 id="inventory-catalog-title" ref={catalogHeading} tabIndex={-1}>
              Productos
            </h3>
            <ReadStatus value={state.catalog} loading="Consultando productos…" />
            {state.catalog.phase === 'ready' && (
              <>
                <p role="status">
                  {state.catalog.value?.length ?? 0} productos en esta página. Página{' '}
                  {Math.floor(state.offset / 50) + 1}.
                </p>
                {state.catalog.value?.length === 0 ? (
                  <p>No hay productos en esta página.</p>
                ) : (
                  <ul className="inventory-products" aria-label="Productos de inventario">
                    {state.catalog.value?.map((product) => (
                      <li key={product.product_id}>
                        <div>
                          <strong>{product.name}</strong>
                          <span>SKU: {product.sku}</span>
                          <span>Unidad: {product.unit}</span>
                        </div>
                        <button
                          type="button"
                          aria-label={`Consultar ${product.name}`}
                          aria-pressed={state.product?.product_id === product.product_id}
                          onClick={() =>
                            void focusAfter(
                              controller.selectProduct(product.product_id),
                              productHeading,
                            )
                          }
                        >
                          Consultar producto
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </>
            )}
            <div className="inventory-actions">
              <button
                type="button"
                disabled={state.catalog.phase === 'loading' || state.offset === 0}
                onClick={() =>
                  void focusAfter(
                    controller.loadCatalog(Math.max(0, state.offset - 50)),
                    catalogHeading,
                  )
                }
              >
                Productos anteriores
              </button>
              <button
                type="button"
                disabled={
                  state.catalog.phase !== 'ready' ||
                  state.catalog.value?.length !== 50 ||
                  state.offset > 2147483597
                }
                onClick={() =>
                  void focusAfter(controller.loadCatalog(state.offset + 50), catalogHeading)
                }
              >
                Más productos
              </button>
            </div>
          </section>
          {state.product && (
            <section className="inventory-detail" aria-labelledby="inventory-product-title">
              <h3 id="inventory-product-title" ref={productHeading} tabIndex={-1}>
                {state.product.name}
              </h3>
              <p>
                SKU: {state.product.sku} · Unidad: {state.product.unit}
              </p>
              <h4>Cantidad disponible</h4>
              <ReadStatus value={state.stock} loading="Consultando cantidad disponible…" />
              {state.stock.value && (
                <>
                  <output aria-label="Cantidad disponible" className="inventory-quantity">
                    {signed(state.stock.value.available_quantity)} {state.product.unit}
                  </output>
                  <p>
                    Cantidad recibida:{' '}
                    <time dateTime={new Date(state.stock.receivedAt!).toISOString()}>
                      {localTime(state.stock.receivedAt!)}
                    </time>
                    .
                  </p>
                </>
              )}
              <button
                type="button"
                disabled={state.stock.phase === 'loading'}
                onClick={() => void controller.refreshStock()}
              >
                Actualizar cantidad
              </button>
              <p>
                La cantidad disponible proviene del registro completo del servidor. Puede ser
                negativa. Cantidad y movimientos son lecturas independientes; sus horas indican
                cuándo se recibió cada respuesta y no una instantánea conjunta.
              </p>
              <h4 id="inventory-history-title" ref={historyHeading} tabIndex={-1}>
                Movimientos
              </h4>
              <p>
                ADJUST: corrección con signo. RESERVE: cantidad negativa que retiene disponibilidad.
                RELEASE y CONSUME: cantidades positivas que finalizan una retención. CONSUME puede
                tener un ADJUST negativo por la salida física en otra página. Hay movimientos
                históricos sin vínculo; esta vista no reconstruye ni agrupa reservas.
              </p>
              <p>
                “Movimientos anteriores” reemplaza esta página. “Movimientos más recientes” vuelve
                al inicio e incluye cambios nuevos. Los cambios más antiguos pueden aparecer al
                seguir avanzando.
              </p>
              <ReadStatus value={state.history} loading="Consultando movimientos…" />
              {state.history.phase === 'ready' && (
                <>
                  <p role="status">
                    {state.history.value?.items.length ?? 0} movimientos en esta página.
                  </p>
                  <p>
                    Movimientos recibidos:{' '}
                    <time dateTime={new Date(state.history.receivedAt!).toISOString()}>
                      {localTime(state.history.receivedAt!)}
                    </time>
                    .
                  </p>
                  {state.history.value?.items.length === 0 ? (
                    <p>No hay movimientos en esta página.</p>
                  ) : (
                    <ol className="inventory-movements" aria-label="Movimientos de inventario">
                      {state.history.value?.items.map((row) => (
                        <li key={row.movement_id}>
                          <strong>
                            {row.kind} · {signed(row.quantity)} {state.product!.unit}
                          </strong>
                          <span>Movimiento: {row.movement_id}</span>
                          <time dateTime={row.occurred_at}>{localTime(row.occurred_at)}</time>
                        </li>
                      ))}
                    </ol>
                  )}
                </>
              )}
              <div className="inventory-actions">
                <button
                  type="button"
                  disabled={state.history.phase === 'loading'}
                  onClick={() => void focusAfter(controller.newest(), historyHeading)}
                >
                  Movimientos más recientes
                </button>
                <button
                  type="button"
                  disabled={state.history.phase !== 'ready' || !state.history.value?.next_cursor}
                  onClick={() => void focusAfter(controller.older(), historyHeading)}
                >
                  Movimientos anteriores
                </button>
              </div>
            </section>
          )}
        </>
      )}
    </section>
  )
}

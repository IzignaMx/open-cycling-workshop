import { useRef, useSyncExternalStore } from 'react'
import type { AdministrationController } from './controller.js'
import { UsersPanel } from './UsersPanel.js'
import { LocationsPanel } from './LocationsPanel.js'
import { SessionPanel } from './SessionPanel.js'
import { discardDraft } from './controls.js'
import './administration.css'

export interface AdministrationPanelProps {
  controller: AdministrationController
  selectedLocationId: string | null
  onClose?(): void
}
export function AdministrationPanel({
  controller,
  selectedLocationId,
  onClose,
}: AdministrationPanelProps) {
  const snapshot = useSyncExternalStore(
    controller.subscribe,
    controller.getSnapshot,
    controller.getSnapshot,
  )
  const root = useRef<HTMLElement>(null)
  const connected = snapshot.account.phase === 'connected'
  function close() {
    if (root.current?.querySelector('[data-dirty="true"]') && !discardDraft()) return
    controller.close()
    onClose?.()
  }
  return (
    <section
      id="workshop-administration"
      ref={root}
      className="administration-panel"
      aria-label="Administración"
    >
      <header>
        <h1>Administración</h1>
        <button type="button" onClick={close}>
          Cerrar administración
        </button>
      </header>
      <p>
        Administración conectada. Los cambios se envían directamente al servidor y no se guardan en
        una cola sin conexión.
      </p>
      <dl className="administration-context">
        <div>
          <dt>Ámbito asignado a la cuenta</dt>
          <dd>
            {connected
              ? (snapshot.account.user?.location_id ?? 'Toda la organización')
              : 'Pendiente de verificación'}
          </dd>
        </div>
        <div>
          <dt>Taller operativo seleccionado</dt>
          <dd>{selectedLocationId ?? 'Ningún taller abierto'}</dd>
        </div>
        <div>
          <dt>Directorio administrativo</dt>
          <dd>Limitado por el servidor al ámbito y los permisos de la cuenta.</dd>
        </div>
      </dl>
      {(snapshot.message || snapshot.account.message) && (
        <p
          role={snapshot.result === 'error' || snapshot.result === 'uncertain' ? 'alert' : 'status'}
        >
          {snapshot.message ?? snapshot.account.message}
        </p>
      )}
      {!connected ? (
        <div>
          <p>
            Verifica tu cuenta para consultar o cambiar la administración. Los borradores anteriores
            se descartan al perder el acceso verificado.
          </p>
          <button
            type="button"
            disabled={
              snapshot.busy ||
              snapshot.account.phase === 'verifying' ||
              snapshot.account.phase === 'suspended'
            }
            onClick={() => void controller.enter()}
          >
            Verificar acceso a administración
          </button>
        </div>
      ) : (
        <div key={snapshot.generation} className="administration-sections">
          <UsersPanel controller={controller} snapshot={snapshot} />
          <LocationsPanel controller={controller} snapshot={snapshot} />
          <SessionPanel controller={controller} snapshot={snapshot} />
        </div>
      )}
    </section>
  )
}

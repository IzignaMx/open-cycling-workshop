import { Component, type ReactNode } from 'react'
import type { OfficialModuleReference } from './reference.js'

class DetailBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false }
  static getDerivedStateFromError() {
    return { failed: true }
  }
  render() {
    return this.state.failed ? (
      <p role="status">
        No se pudo mostrar la información del módulo. La recepción sigue disponible.
      </p>
    ) : (
      this.props.children
    )
  }
}

function ReferenceDetails({ reference }: { reference: OfficialModuleReference | null }) {
  if (!reference) return <p>Esta compilación no incluye la referencia de información del módulo.</p>
  return (
    <>
      <p>{reference.name}</p>
      <dl>
        <div>
          <dt>Identificador de la referencia</dt>
          <dd>{reference.id}</dd>
        </div>
        <div>
          <dt>Licencia</dt>
          <dd>{reference.license}</dd>
        </div>
        <div>
          <dt>Composición</dt>
          <dd>Importación explícita al compilar ({reference.composition})</dd>
        </div>
        <div>
          <dt>Modo operativo declarado</dt>
          <dd>
            Solo en línea; esta referencia no ejecuta operaciones ({reference.operationalMode})
          </dd>
        </div>
        <div>
          <dt>Permisos solicitados</dt>
          <dd>{reference.permissions.join(', ') || 'Ninguno'}</dd>
        </div>
        <div>
          <dt>Datos operativos</dt>
          <dd>{reference.data.join(', ') || 'Ninguno'}</dd>
        </div>
        <div>
          <dt>Secretos</dt>
          <dd>{reference.secrets.join(', ') || 'Ninguno'}</dd>
        </div>
        <div>
          <dt>Destinos de red</dt>
          <dd>{reference.network.join(', ') || 'Ninguno'}</dd>
        </div>
      </dl>
      <p>Estas declaraciones describen solo esta referencia, no toda la aplicación.</p>
      <p>
        Consultar esta información estática no instala módulos ni concede permisos; no certifica
        compatibilidad ni proporciona aislamiento.
      </p>
      <p>La información puede consultarse sin conexión. No habilita operaciones sin conexión.</p>
    </>
  )
}

/** Explicit host composition only; no authority or operational callbacks cross this boundary. */
export function ModuleInformation({ reference }: { reference: OfficialModuleReference | null }) {
  return (
    <section
      id="workshop-module-information"
      className="workshop-panel module-information"
      aria-labelledby="module-information-title"
    >
      <h2 id="module-information-title">Módulo integrado</h2>
      <details>
        <summary>Información del módulo integrado</summary>
        <DetailBoundary>
          <ReferenceDetails reference={reference} />
        </DetailBoundary>
      </details>
    </section>
  )
}

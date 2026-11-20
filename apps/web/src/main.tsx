import { createRoot } from 'react-dom/client'
import { App } from './App.js'
import { WorkshopController } from './runtime/controller.js'
import { bootstrap } from './bootstrap.js'
import './styles.css'

const root = document.getElementById('root')
if (!root) throw new Error('missing #root application mount point')
bootstrap(
  window,
  (storage) => {
    const origin = import.meta.env.VITE_API_BASE_URL ?? window.location.origin
    const apiRealm = new URL('/api/v1', origin || window.location.origin).href
    const runtime = new WorkshopController({
      apiRealm,
      storage,
      fetch: window.fetch.bind(window),
      online: () => navigator.onLine,
    })
    createRoot(root).render(<App runtime={runtime} />)
  },
  (reason) => {
    createRoot(root).render(
      <main className="login-shell" aria-labelledby="bootstrap-heading">
        <section className="workshop-panel">
          <h1 id="bootstrap-heading">No se puede iniciar el taller aquí</h1>
          <div role="alert">
            <p>
              {reason === 'insecure-context'
                ? 'Esta dirección no ofrece un contexto seguro. Usa la dirección HTTPS confiable preparada y autorizada para este equipo. No ignores advertencias de certificados.'
                : 'El navegador no permite acceder al almacenamiento de sesión. No se inició el taller. Pide ayuda para revisar el acceso en este navegador.'}
            </p>
            <p>
              No borres los datos del navegador. Cambiar de dirección no transfiere borradores: el
              trabajo anterior puede seguir únicamente en la dirección original.
            </p>
          </div>
        </section>
      </main>,
    )
  },
)

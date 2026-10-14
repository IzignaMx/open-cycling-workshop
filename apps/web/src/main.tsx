import { createRoot } from 'react-dom/client'
import { App } from './App.js'
import { WorkshopController } from './runtime/controller.js'
import './styles.css'

const root = document.getElementById('root')
if (!root) throw new Error('missing #root application mount point')
const origin = import.meta.env.VITE_API_BASE_URL ?? window.location.origin
const apiRealm = new URL('/api/v1', origin || window.location.origin).href
const runtime = new WorkshopController({
  apiRealm,
  storage: window.sessionStorage,
  fetch: window.fetch.bind(window),
  online: () => navigator.onLine,
})
createRoot(root).render(<App runtime={runtime} />)

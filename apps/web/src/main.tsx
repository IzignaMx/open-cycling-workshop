import { createRoot } from 'react-dom/client'

import { App } from './App.js'
import './styles.css'

const root = document.getElementById('root')
if (!root) throw new Error('missing #root application mount point')
createRoot(root).render(<App />)

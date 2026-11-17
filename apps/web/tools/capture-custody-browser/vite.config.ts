import { defineConfig } from 'vite'
export default defineConfig({
  root: 'tools/capture-custody-browser',
  build: { outDir: '../../.tmp-capture-custody', emptyOutDir: true },
})

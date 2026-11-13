import { defineConfig } from 'vite'
export default defineConfig({
  root: 'tools/capture-browser',
  build: { outDir: '../../.tmp-capture-browser', emptyOutDir: true },
})

import { defineConfig } from 'vite'
export default defineConfig({
  root: 'tools/kernel-browser',
  build: { outDir: '../../.tmp-kernel-browser', emptyOutDir: true },
})

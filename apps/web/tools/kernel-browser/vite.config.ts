import { defineConfig } from 'vite'
export default defineConfig({
  root: 'tools/kernel-browser',
  preview: { proxy: { '/api': 'http://127.0.0.1:8007' } },
  build: { outDir: '../../.tmp-kernel-browser', emptyOutDir: true },
})

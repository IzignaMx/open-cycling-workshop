import { fileURLToPath } from 'node:url'
import { build } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

/** Bundle actual components only in memory; no PWA route, debug hook or output mutation. */
export async function moduleInformationBundle() {
  const result = await build({
    root: fileURLToPath(new URL('../..', import.meta.url)),
    configFile: false,
    // Library mode preserves this Node expression unless explicitly replaced.
    // Match the production PWA React build without installing a browser global shim.
    define: { 'process.env.NODE_ENV': JSON.stringify('production') },
    plugins: [react(), tailwindcss()],
    logLevel: 'error',
    build: {
      write: false,
      emptyOutDir: false,
      minify: false,
      sourcemap: false,
      lib: {
        entry: fileURLToPath(new URL('./module-information-harness.tsx', import.meta.url)),
        name: 'ModuleInformationFixture',
        formats: ['iife'],
      },
    },
  })
  const outputs = Array.isArray(result) ? result : [result]
  let script = '',
    style = ''
  for (const output of outputs) {
    if (!('output' in output))
      throw new Error('Expected an in-memory fixture bundle, not a watcher')
    for (const file of output.output) {
      if (file.type === 'chunk') script += file.code
      else if (file.fileName.endsWith('.css'))
        style +=
          typeof file.source === 'string' ? file.source : new TextDecoder().decode(file.source)
    }
  }
  if (!script || !style) throw new Error('Fixture must include actual React and host styles')
  if (script.includes('process.env.NODE_ENV'))
    throw new Error('Browser fixture must not require Node process.env.NODE_ENV')
  return { script, style }
}

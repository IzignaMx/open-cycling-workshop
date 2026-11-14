/** Disposable loopback host for actual archived App/SW bytes. No API proxy or SPA fallback. */
import { createServer } from 'node:http'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
export function captureAsset(raw) {
  let path
  try {
    path = decodeURIComponent(raw.split('?')[0])
  } catch {
    return null
  }
  if (
    !path.startsWith('/') ||
    path.startsWith('//') ||
    path.includes('\\') ||
    path.split('/').includes('..')
  )
    return null
  if (path === '/') return 'index.html'
  if (
    !/\.(?:html|js|css|json|webmanifest|svg|png|ico|woff2?)$/.test(path) ||
    path.startsWith('/api/')
  )
    return null
  return path.slice(1)
}
export function startCaptureAppServer(directory, port) {
  if (![5180, 5181].includes(port)) throw Error('Fixed disposable loopback ports required')
  const evidence = readFileSync(resolve(directory, 'evidence.json'))
  const assets = JSON.parse(evidence).assets
  const server = createServer((request, response) => {
    const name = captureAsset(request.url ?? '')
    if (
      request.method !== 'GET' ||
      !name ||
      (name !== 'evidence.json' && !Object.hasOwn(assets, name))
    ) {
      response.writeHead(404)
      response.end()
      return
    }
    const type = name.endsWith('.html')
      ? 'text/html'
      : name.endsWith('.js')
        ? 'application/javascript'
        : name.endsWith('.css')
          ? 'text/css'
          : name.endsWith('.svg')
            ? 'image/svg+xml'
            : name.endsWith('.webmanifest') || name.endsWith('.json')
              ? 'application/json'
              : 'application/octet-stream'
    response.writeHead(200, { 'Content-Type': type, 'Cache-Control': 'no-store' })
    response.end(
      name === 'evidence.json' ? evidence : readFileSync(resolve(directory, 'dist', name)),
    )
  })
  server.listen(port, '127.0.0.1')
  return server
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url))
  startCaptureAppServer(resolve(process.argv[2]), Number(process.argv[3]))

/** Loopback-only acceptance host: actual pinned old distribution then current build.
 * It is never imported by or bundled into the production app.
 */
import { createServer, request as proxyRequest } from 'node:http'
import { readFileSync, existsSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
const root = resolve(dirname(fileURLToPath(import.meta.url)), '../..')
export function fixtureAsset(raw) {
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
  if (/^\/(?:api|health|__fixture)(?:\/|$)/.test(path)) return null
  if (path === '/' || !path.split('/').at(-1).includes('.')) return 'index.html'
  return path.slice(1)
}
export function startUpgradeFixture(port = 5174) {
  let current = false
  const old = resolve(root, 'artifacts/legacy-client/dist')
  const fresh = resolve(root, 'apps/web/dist')
  for (const directory of [old, fresh]) {
    if (!existsSync(resolve(directory, 'sw.js')))
      throw new Error('Build both actual App/SW distributions before upgrade acceptance')
  }
  const server = createServer((req, res) => {
    const path = req.url ?? '/'
    if (path === '/__fixture/ready') {
      res.end('ready')
      return
    }
    if (path === '/__fixture/current' && req.method === 'POST') {
      current = true
      res.end('current')
      return
    }
    if (/^\/api(?:\/|$)/.test(path)) {
      const proxy = proxyRequest(
        { hostname: '127.0.0.1', port: 8000, path, method: req.method, headers: req.headers },
        (upstream) => {
          res.writeHead(upstream.statusCode ?? 502, upstream.headers)
          upstream.pipe(res)
        },
      )
      proxy.on('error', () => {
        res.writeHead(502, { 'content-type': 'application/json' })
        res.end('{"error":"fixture_api_unavailable"}')
      })
      req.pipe(proxy)
      return
    }
    const asset = fixtureAsset(path)
    const file = asset && resolve(current ? fresh : old, asset)
    if (!file || !existsSync(file)) {
      res.writeHead(404)
      res.end()
      return
    }
    const type = file.endsWith('.js')
      ? 'text/javascript'
      : file.endsWith('.css')
        ? 'text/css'
        : file.endsWith('.html')
          ? 'text/html'
          : 'application/json'
    res.writeHead(200, {
      'content-type': type,
      'cache-control': 'no-store',
      'service-worker-allowed': '/',
    })
    res.end(readFileSync(file))
  })
  return server.listen(port, '127.0.0.1')
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url))
  startUpgradeFixture()

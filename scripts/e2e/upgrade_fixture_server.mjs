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
// The pinned old transport leaves error bodies unread. A browser
// response-body observer can therefore wait forever for completion. Observe the
// same upstream response passively instead; never replay or rewrite its request.
function refusalObservations() {
  const records = new Map()
  let exhausted = false
  return {
    observe(method, path, upstream) {
      if (method !== 'POST' || path !== '/api/v1/sync/mutations' || upstream.statusCode !== 409)
        return
      const requestId = upstream.headers['x-request-id']
      if (typeof requestId !== 'string' || !/^req-[0-9a-f]{32}$/.test(requestId) || exhausted)
        return
      // Retain invalid/pending IDs too: a duplicate must never borrow a prior
      // valid observation. Capacity overflow invalidates the whole bounded set.
      if (records.has(requestId)) {
        records.set(requestId, null)
        return
      }
      if (records.size >= 32) {
        exhausted = true
        records.clear()
        return
      }
      const entry = { value: null }
      records.set(requestId, entry)
      const length = upstream.headers['content-length']
      if (
        typeof length !== 'string' ||
        !/^[1-9][0-9]{0,3}$/.test(length) ||
        Number(length) > 4096 ||
        !/^application\/json(?:;\s*charset=utf-8)?$/i.test(
          upstream.headers['content-type'] ?? '',
        ) ||
        (upstream.headers['content-encoding'] &&
          upstream.headers['content-encoding'] !== 'identity')
      )
        return
      let bytes = 0
      let chunks = []
      let invalid = false
      const discard = () => {
        invalid = true
        chunks = []
      }
      upstream.on('data', (chunk) => {
        bytes += chunk.length
        if (bytes > Number(length)) discard()
        if (!invalid) chunks.push(chunk)
      })
      upstream.once('aborted', discard)
      upstream.once('error', discard)
      upstream.once('end', () => {
        if (
          !invalid &&
          upstream.complete &&
          bytes === Number(length) &&
          records.get(requestId) === entry
        ) {
          try {
            const code = JSON.parse(Buffer.concat(chunks).toString('utf8'))?.error?.code
            // A closed allowlist prevents arbitrary response text, tokens,
            // details, or payloads from entering the retained evidence.
            if (code === 'client_upgrade_required')
              entry.value = { requestId, method, path, status: upstream.statusCode, code }
          } catch {
            /* Invalid bodies remain unavailable evidence. */
          }
        }
        chunks = []
      })
    },
    read(requestId) {
      return records.get(requestId)?.value ?? null
    },
  }
}
export function startUpgradeFixture(port = 5174, options = {}) {
  let current = false
  const refusals = refusalObservations()
  const old = options.legacyDirectory ?? resolve(root, 'artifacts/legacy-client/dist')
  const fresh = options.currentDirectory ?? resolve(root, 'apps/web/dist')
  for (const directory of [old, fresh]) {
    if (!existsSync(resolve(directory, 'sw.js')))
      throw new Error('Build both actual App/SW distributions before upgrade acceptance')
  }
  const server = createServer((req, res) => {
    const path = req.url ?? '/'
    const observation = /^\/__fixture\/refusal\/(req-[0-9a-f]{32})$/.exec(path)
    if (observation && req.method === 'GET') {
      const value = refusals.read(observation[1])
      res.writeHead(value ? 200 : 404, {
        'content-type': 'application/json',
        'cache-control': 'no-store',
      })
      res.end(JSON.stringify(value ?? { error: 'fixture_refusal_unavailable' }))
      return
    }
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
        {
          hostname: '127.0.0.1',
          port: options.apiPort ?? 8000,
          path,
          method: req.method,
          headers: req.headers,
        },
        (upstream) => {
          refusals.observe(req.method, path, upstream)
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

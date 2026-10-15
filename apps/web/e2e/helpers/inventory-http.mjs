/** Test-only native HTTP boundary: Playwright API errors retain Authorization in
 * nested HTML steps even if caught. Never pass credentialed requests to those
 * instrumented APIs, and never propagate native errors, bodies or private headers.
 */
export async function fixtureHttp(origin, target, options = {}, fetcher = fetch) {
  try {
    const base = new URL(origin)
    const url = new URL(target, base)
    const method = options.method ?? 'GET'
    const read = /^\/api\/v1\/inventory\/(?:products\/[0-9a-f-]{36}\/stock|missing)$/.test(
      url.pathname,
    )
    const write = /^\/api\/v1\/(?:auth\/login|admin\/users\/[0-9a-f-]{36}\/revoke-sessions)$/.test(
      url.pathname,
    )
    if (
      base.protocol !== 'http:' ||
      !['127.0.0.1', 'localhost'].includes(base.hostname) ||
      base.username ||
      base.password ||
      base.search ||
      base.hash ||
      base.pathname !== '/' ||
      url.origin !== base.origin ||
      url.username ||
      url.password ||
      url.search ||
      url.hash ||
      !((method === 'GET' && read) || (method === 'POST' && write))
    )
      throw new Error()
    const headers = new Headers()
    const incoming = new Headers(options.headers)
    for (const name of ['authorization', 'content-type', 'x-ocwp-write-protocol']) {
      const value = incoming.get(name)
      if (value) headers.set(name, value)
    }
    const response = await fetcher(url.href, {
      method,
      headers,
      body: options.body,
      redirect: 'error',
      signal: AbortSignal.timeout(10_000),
    })
    const reader = response.body?.getReader()
    const chunks = []
    let size = 0
    if (reader) {
      try {
        for (;;) {
          const { done, value } = await reader.read()
          if (done) break
          size += value.byteLength
          if (size > 1_048_576) throw new Error()
          chunks.push(value)
        }
      } finally {
        await reader.cancel().catch(() => undefined)
        reader.releaseLock()
      }
    }
    const body = Buffer.concat(chunks).toString('utf8')
    const safeHeaders = {}
    for (const name of ['content-type', 'cache-control']) {
      const value = response.headers.get(name)
      if (value) safeHeaders[name] = value
    }
    return { status: response.status, headers: safeHeaders, body }
  } catch {
    throw new Error('Inventory fixture HTTP failed')
  }
}

export function fixtureJson(response) {
  try {
    const body = JSON.parse(response.body)
    if (!body || typeof body !== 'object' || Array.isArray(body)) throw new Error()
    return body
  } catch {
    throw new Error('Inventory fixture JSON failed')
  }
}

import type { ConnectedReadCapture } from '../../runtime/connected-read.js'
import {
  decodeCursor,
  failInventory,
  InventoryHttpError,
  INVENTORY_PAGE_SIZE,
  MAX_INVENTORY_BODY_BYTES,
  parseCatalog,
  parseMovementPage,
  parseStock,
  validInventoryId,
} from './contracts.js'
export { InventoryHttpError } from './contracts.js'
export function createInventoryTransport(options: { apiRealm: string; fetch: typeof fetch }) {
  const realm = new URL(options.apiRealm)
  if (
    realm.href !== options.apiRealm ||
    realm.username ||
    realm.password ||
    realm.search ||
    realm.hash ||
    options.apiRealm.endsWith('/') ||
    !['https:', 'http:'].includes(realm.protocol)
  )
    failInventory()
  async function request<T>(
    source: ConnectedReadCapture,
    path: string,
    parse: (raw: string) => T,
  ): Promise<T> {
    const token = source.token,
      signal = source.signal,
      check = source.isCurrent
    let finished = false
    const now = Date.now(),
      monotonicStart = performance.now(),
      expiry = Date.parse(source.context.offlineUntil)
    if (!Number.isFinite(now) || !Number.isFinite(expiry) || expiry <= now)
      failInventory('stale_request')
    const deadline = Math.min(10000, expiry - now),
      until = now + deadline
    let observedAt = now
    const current = () => {
      const at = Date.now(),
        elapsed = performance.now() - monotonicStart
      if (
        !Number.isFinite(at) ||
        !Number.isFinite(elapsed) ||
        at < observedAt ||
        at >= until ||
        elapsed < 0 ||
        elapsed >= deadline
      )
        return false
      observedAt = at
      return !finished && !signal.aborted && check()
    }
    if (!current()) failInventory('stale_request')
    if (
      !token ||
      token.length > 16384 ||
      /\s/.test(token) ||
      !validInventoryId(source.context.principal.organizationId) ||
      !validInventoryId(source.context.selectedLocationId)
    )
      failInventory()
    const url = `${options.apiRealm}/inventory/${path}`
    if (new URL(url).href !== url) failInventory()
    const abort = new AbortController()
    let timer: ReturnType<typeof setTimeout> | undefined, response: Response | undefined
    let reader: ReadableStreamDefaultReader<Uint8Array> | undefined
    let rejectAbort: (error: InventoryHttpError) => void = () => {}
    const aborted = new Promise<never>((_, reject) => {
      rejectAbort = reject
    })
    const forward = () => {
      abort.abort()
      rejectAbort(new InventoryHttpError('stale_request'))
    }
    signal.addEventListener('abort', forward, { once: true })
    const work = async (): Promise<T> => {
      try {
        response = await options.fetch.call(globalThis, url, {
          method: 'GET',
          headers: { Accept: 'application/json', Authorization: `Bearer ${token}` },
          cache: 'no-store',
          credentials: 'omit',
          redirect: 'error',
          referrerPolicy: 'no-referrer',
          signal: abort.signal,
        })
      } catch {
        return failInventory(current() ? 'network_error' : 'stale_request')
      }
      if (!current()) {
        if (response.body && !response.body.locked)
          void response.body.cancel().catch(() => undefined)
        failInventory('stale_request')
      }
      // A current refusal takes precedence over every untrusted response field/body.
      if (response.status === 401 || response.status === 403)
        failInventory(
          response.status === 401 ? 'invalid_session' : 'capability_denied',
          response.status,
        )
      if (
        response.url !== url ||
        response.redirected ||
        !response.headers
          .get('cache-control')
          ?.split(',')
          .some((v) => v.trim().toLowerCase() === 'no-store') ||
        !/^application\/json(?:\s*;|\s*$)/i.test(response.headers.get('content-type') ?? '')
      )
        failInventory()
      if (response.status !== 200)
        failInventory(response.status >= 500 ? 'unavailable' : 'invalid_response', response.status)
      const length = response.headers.get('content-length')
      if (length !== null && (!/^\d+$/.test(length) || Number(length) > MAX_INVENTORY_BODY_BYTES))
        failInventory()
      reader = response.body?.getReader()
      if (!reader) failInventory()
      const chunks: Uint8Array[] = []
      let size = 0
      try {
        while (true) {
          const chunk = await reader.read()
          if (!current()) failInventory('stale_request')
          if (chunk.done) break
          size += chunk.value.byteLength
          if (size > MAX_INVENTORY_BODY_BYTES) failInventory()
          chunks.push(chunk.value)
        }
      } catch (error) {
        if (error instanceof InventoryHttpError) throw error
        return failInventory(current() ? 'network_error' : 'stale_request')
      }
      const bytes = new Uint8Array(size)
      let offset = 0
      for (const chunk of chunks) {
        bytes.set(chunk, offset)
        offset += chunk.byteLength
      }
      let raw: string
      try {
        raw = new TextDecoder('utf-8', { fatal: true }).decode(bytes)
      } catch {
        return failInventory()
      }
      const result = parse(raw)
      if (!current()) failInventory('stale_request')
      return result
    }
    try {
      return await Promise.race([
        work(),
        aborted,
        new Promise<never>((_, reject) => {
          timer = setTimeout(() => {
            const code = deadline < 10000 || !current() ? 'stale_request' : 'network_error'
            finished = true
            abort.abort()
            reject(new InventoryHttpError(code))
          }, deadline)
        }),
      ])
    } finally {
      finished = true
      if (timer !== undefined) clearTimeout(timer)
      signal.removeEventListener('abort', forward)
      abort.abort()
      if (reader) {
        const capturedReader = reader
        void capturedReader
          .cancel()
          .catch(() => undefined)
          .finally(() => capturedReader.releaseLock())
      } else if (response?.body && !response.body.locked)
        void response.body.cancel().catch(() => undefined)
    }
  }
  const scope = (source: ConnectedReadCapture) => ({
    organizationId: source.context.principal.organizationId,
    locationId: source.context.selectedLocationId,
  })
  return Object.freeze({
    catalog: (source: ConnectedReadCapture, offset = 0) => {
      if (!Number.isSafeInteger(offset) || offset < 0 || offset > 2147483647) failInventory()
      const selected = scope(source)
      return request(
        source,
        `products?${new URLSearchParams({ location_id: selected.locationId, limit: String(INVENTORY_PAGE_SIZE), offset: String(offset) })}`,
        (raw) => parseCatalog(raw, selected),
      )
    },
    stock: (source: ConnectedReadCapture, productId: string) => {
      if (!validInventoryId(productId)) failInventory()
      const selected = scope(source)
      return request(source, `products/${encodeURIComponent(productId)}/stock`, (raw) =>
        parseStock(raw, selected, productId),
      )
    },
    movements: (source: ConnectedReadCapture, productId: string, before?: string) => {
      if (!validInventoryId(productId)) failInventory()
      const selected = scope(source),
        query = new URLSearchParams({ limit: String(INVENTORY_PAGE_SIZE) })
      if (before !== undefined) {
        decodeCursor(before, selected, productId)
        query.set('before', before)
      }
      return request(
        source,
        `products/${encodeURIComponent(productId)}/movements?${query}`,
        (raw) => parseMovementPage(raw, selected, productId, before),
      )
    },
  })
}
export type InventoryTransport = ReturnType<typeof createInventoryTransport>

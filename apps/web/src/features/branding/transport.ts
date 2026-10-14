import {
  MAX_BRANDING_BODY_BYTES,
  parseBrandingProfileJson,
  isNormalizedBrandingName,
  type BrandingProfile,
  type BrandingPutRequest,
} from './contracts.js'
import { PALETTES } from '../../personalization/catalog.js'

export interface BrandingCapture {
  readonly token: string
  readonly organizationId: string
  readonly locationId: string
  readonly datasetIncarnation: string | null
  readonly signal?: AbortSignal
  isCurrent(): boolean
}
export class BrandingHttpError extends Error {
  constructor(
    readonly code: string,
    readonly status: number | null = null,
  ) {
    super('No se pudo confirmar la configuración del taller.')
    this.name = 'BrandingHttpError'
  }
}
const fail = (code = 'invalid_response', status: number | null = null): never => {
  throw new BrandingHttpError(code, status)
}
const validId = (value: string) => !!value && value.length <= 36 && !value.includes('\0')
const safeCodes = new Set([
  'stale_branding_version',
  'branding_conflict',
  'branding_denied',
  'validation_error',
  'branding_busy',
  'branding_storage_unavailable',
  'client_upgrade_required',
])
export function createBrandingTransport(options: { apiRealm: string; fetch: typeof fetch }) {
  const realm = new URL(options.apiRealm)
  if (
    realm.href !== options.apiRealm ||
    realm.username ||
    realm.password ||
    realm.search ||
    realm.hash ||
    options.apiRealm.endsWith('/') ||
    !['http:', 'https:'].includes(realm.protocol)
  )
    fail('invalid_request')
  async function request(
    source: BrandingCapture,
    method: 'GET' | 'PUT',
    payload?: BrandingPutRequest,
  ): Promise<BrandingProfile> {
    const captured = {
      token: source.token,
      organizationId: source.organizationId,
      locationId: source.locationId,
      datasetIncarnation: source.datasetIncarnation,
      check: source.isCurrent,
      signal: source.signal,
    }
    let expired = false
    const current = () => !expired && !captured.signal?.aborted && captured.check()
    if (!current()) fail('stale_request')
    if (
      !validId(captured.organizationId) ||
      !validId(captured.locationId) ||
      !captured.token ||
      captured.token.length > 16384 ||
      /\s/.test(captured.token)
    )
      fail('invalid_request')
    if (
      payload &&
      (Object.keys(payload).sort().join(',') !==
        'display_name,expected_version,logo_png_base64,palette_id' ||
        !Number.isSafeInteger(payload.expected_version) ||
        payload.expected_version < 0 ||
        payload.expected_version >= Number.MAX_SAFE_INTEGER ||
        typeof payload.display_name !== 'string' ||
        !isNormalizedBrandingName(payload.display_name.normalize('NFC').trim()) ||
        !PALETTES.some((p) => p.id === payload.palette_id) ||
        (payload.logo_png_base64 !== null && typeof payload.logo_png_base64 !== 'string'))
    )
      fail('invalid_request')
    const serialized = payload === undefined ? undefined : JSON.stringify(payload)
    if (serialized && new TextEncoder().encode(serialized).length > MAX_BRANDING_BODY_BYTES)
      fail('invalid_request')
    const url = `${options.apiRealm}/locations/${encodeURIComponent(captured.locationId)}/branding`
    if (new URL(url).href !== url) fail('invalid_request')
    const abort = new AbortController()
    const forward = () => abort.abort()
    captured.signal?.addEventListener('abort', forward, { once: true })
    let timer: ReturnType<typeof setTimeout> | undefined
    let response: Response | undefined
    const work = async (): Promise<BrandingProfile> => {
      try {
        response = await options.fetch.call(globalThis, url, {
          method,
          headers: {
            Accept: 'application/json',
            Authorization: `Bearer ${captured.token}`,
            'X-OCWP-Write-Protocol': '1',
            ...(serialized === undefined ? {} : { 'Content-Type': 'application/json' }),
          },
          cache: 'no-store',
          credentials: 'omit',
          redirect: 'error',
          referrerPolicy: 'no-referrer',
          signal: abort.signal,
          ...(serialized === undefined ? {} : { body: serialized }),
        })
      } catch {
        return fail(current() ? 'network_error' : 'stale_request')
      }
      if (!current()) return fail('stale_request')
      if (response.url !== url || response.redirected) return fail()
      // Refusals revoke only this exact current admission without waiting on untrusted bodies.
      if (response.status === 401 || response.status === 403)
        return fail(
          response.status === 401 ? 'invalid_session' : 'branding_denied',
          response.status,
        )
      if (
        !response.headers
          .get('cache-control')
          ?.split(',')
          .some((v) => v.trim().toLowerCase() === 'no-store') ||
        !response.headers.get('content-type')?.toLowerCase().startsWith('application/json')
      )
        return fail()
      const length = response.headers.get('content-length')
      if (length !== null && (!/^\d+$/.test(length) || Number(length) > MAX_BRANDING_BODY_BYTES))
        return fail()
      const reader = response.body?.getReader()
      if (!reader) return fail()
      const chunks: Uint8Array[] = []
      let size = 0
      try {
        while (true) {
          const chunk = await reader.read()
          if (!current()) return fail('stale_request')
          if (chunk.done) break
          size += chunk.value.byteLength
          if (size > MAX_BRANDING_BODY_BYTES) return fail()
          chunks.push(chunk.value)
        }
      } finally {
        void reader.cancel().catch(() => undefined)
        reader.releaseLock()
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
        return fail()
      }
      if (response.status !== 200) {
        let code = 'request_refused'
        try {
          const value: unknown = JSON.parse(raw)
          if (
            value &&
            typeof value === 'object' &&
            'error' in value &&
            value.error &&
            typeof value.error === 'object' &&
            'code' in value.error &&
            typeof value.error.code === 'string' &&
            safeCodes.has(value.error.code)
          )
            code = value.error.code
        } catch {
          /* Never echo response content. */
        }
        return fail(code, response.status)
      }
      let profile: BrandingProfile
      try {
        profile = await parseBrandingProfileJson(raw)
      } catch {
        return fail()
      }
      if (!current()) return fail('stale_request')
      if (
        profile.organization_id !== captured.organizationId ||
        profile.location_id !== captured.locationId ||
        (captured.datasetIncarnation !== null &&
          profile.dataset_incarnation !== captured.datasetIncarnation)
      )
        return fail()
      if (
        payload &&
        (profile.version !== payload.expected_version + 1 ||
          profile.display_name !== payload.display_name.normalize('NFC').trim() ||
          profile.palette_id !== payload.palette_id ||
          profile.logo_state !== (payload.logo_png_base64 === null ? 'none' : 'available'))
      )
        return fail()
      return profile
    }
    try {
      return await Promise.race([
        work(),
        new Promise<never>((_, reject) => {
          timer = setTimeout(() => {
            const code = current() ? 'network_error' : 'stale_request'
            expired = true
            abort.abort()
            reject(new BrandingHttpError(code))
          }, 10000)
        }),
      ])
    } finally {
      if (timer !== undefined) clearTimeout(timer)
      captured.signal?.removeEventListener('abort', forward)
      abort.abort()
      if (response?.body && !response.body.locked)
        void response.body.cancel().catch(() => undefined)
    }
  }
  return Object.freeze({
    read: (source: BrandingCapture) => request(source, 'GET'),
    save: (source: BrandingCapture, payload: BrandingPutRequest) =>
      request(source, 'PUT', structuredClone(payload)),
  })
}
export type BrandingTransport = ReturnType<typeof createBrandingTransport>

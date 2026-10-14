import { BoundedHttpError, cancelResponse, readBoundedJson } from '../access-kernel/bounded-http.js'
import { isUserSnapshot, type SessionUserSnapshot } from '../auth/session.js'
import type { LoginRequestPayload } from '../auth/login-model.js'
import type { LocalServiceOrderEvent } from '../local/service-order-types.js'

export type RuntimeHttpCode =
  'network_error' | 'invalid_response' | 'invalid_session' | 'capability_denied' | 'stale_request'
export class RuntimeHttpError extends Error {
  constructor(readonly code: RuntimeHttpCode) {
    super(
      code === 'invalid_session'
        ? 'La sesión no es válida. Inicia sesión nuevamente.'
        : code === 'network_error'
          ? 'No hay conexión con el servidor.'
          : 'No se pudo verificar la respuesta del servidor.',
    )
    this.name = 'RuntimeHttpError'
  }
}
function fail(code: RuntimeHttpCode = 'invalid_response'): never {
  throw new RuntimeHttpError(code)
}
function record(value: unknown, keys: readonly string[]): value is Record<string, unknown> {
  return (
    !!value &&
    typeof value === 'object' &&
    !Array.isArray(value) &&
    Object.keys(value).length === keys.length &&
    keys.every((k) => Object.hasOwn(value, k))
  )
}
function id(value: unknown): value is string {
  return (
    typeof value === 'string' && value.length > 0 && value.length <= 36 && !/[\s\0/?#]/.test(value)
  )
}
export interface CapturedRead {
  token: string
  isCurrent(): boolean
}
export interface WorkshopLocation {
  location_id: string
  organization_id: string
  name: string
}
export function createRuntimeTransport(options: { apiRealm: string; fetch: typeof fetch }) {
  const realm = new URL(options.apiRealm)
  if (
    realm.href !== options.apiRealm ||
    options.apiRealm.endsWith('/') ||
    realm.username ||
    realm.password ||
    realm.search ||
    realm.hash ||
    !['http:', 'https:'].includes(realm.protocol)
  )
    fail()
  async function request(
    path: string,
    source: CapturedRead | null,
    body: unknown,
    limit: number,
    check: () => boolean,
  ): Promise<unknown> {
    const token = source?.token,
      current = source?.isCurrent ?? check,
      url = `${options.apiRealm}${path}`
    if (!current()) fail('stale_request')
    const headers: Record<string, string> = { Accept: 'application/json' }
    if (token) headers.Authorization = `Bearer ${token}`
    if (path === '/auth/logout-all') headers['X-OCWP-Write-Protocol'] = '1'
    const serialized = body === undefined ? undefined : JSON.stringify(body)
    if (serialized !== undefined) {
      if (new TextEncoder().encode(serialized).byteLength > 16384) fail()
      headers['Content-Type'] = 'application/json'
    }
    let response: Response
    try {
      response = await options.fetch(url, {
        method: serialized === undefined ? 'GET' : 'POST',
        headers,
        ...(serialized === undefined ? {} : { body: serialized }),
        credentials: 'omit',
        redirect: 'error',
        cache: 'no-store',
        referrerPolicy: 'no-referrer',
      })
    } catch {
      fail(current() ? 'network_error' : 'stale_request')
    }
    if (!current()) {
      await cancelResponse(response)
      fail('stale_request')
    }
    if (
      response.status === 204 &&
      path === '/auth/logout-all' &&
      response.url === url &&
      !response.redirected
    )
      return null
    if (
      response.redirected ||
      response.url !== url ||
      response.headers.get('content-type')?.split(';')[0]?.trim().toLowerCase() !==
        'application/json' ||
      !response.headers
        .get('cache-control')
        ?.split(',')
        .some((v) => v.trim().toLowerCase() === 'no-store')
    ) {
      await cancelResponse(response)
      fail()
    }
    let value: unknown
    try {
      value = await readBoundedJson(response, limit)
    } catch (error) {
      fail(
        error instanceof BoundedHttpError && error.code === 'network_error'
          ? 'network_error'
          : 'invalid_response',
      )
    }
    if (!current()) fail('stale_request')
    if (!response.ok) {
      if (response.status === 401) fail('invalid_session')
      if (response.status === 403) fail('capability_denied')
      fail()
    }
    return value
  }
  return Object.freeze({
    async login(input: LoginRequestPayload, current: () => boolean): Promise<string> {
      const value = await request('/auth/login', null, input, 32768, current)
      if (
        !record(value, ['access_token', 'token_type']) ||
        value.token_type !== 'bearer' ||
        typeof value.access_token !== 'string' ||
        value.access_token.length < 1 ||
        value.access_token.length > 16384 ||
        /\s/.test(value.access_token)
      )
        fail()
      return value.access_token
    },
    async me(source: CapturedRead): Promise<SessionUserSnapshot> {
      const value = await request('/auth/me', source, undefined, 16384, source.isCurrent)
      if (
        !record(value, [
          'user_id',
          'organization_id',
          'location_id',
          'display_name',
          'capabilities',
        ]) ||
        !isUserSnapshot(value) ||
        new Set(value.capabilities).size !== value.capabilities.length
      )
        fail()
      return value
    },
    async locations(
      source: CapturedRead,
      organizationId: string,
      afterId?: string,
    ): Promise<{ items: WorkshopLocation[]; nextCursor: string | null }> {
      if (afterId !== undefined && !id(afterId)) fail()
      const query = new URLSearchParams({ limit: '50' })
      if (afterId) query.set('after_id', afterId)
      const value = await request(`/locations?${query}`, source, undefined, 32768, source.isCurrent)
      if (
        !record(value, ['items', 'next_cursor']) ||
        !Array.isArray(value.items) ||
        value.items.length > 50 ||
        (value.next_cursor !== null && !id(value.next_cursor))
      )
        fail()
      const seen = new Set<string>()
      for (const row of value.items) {
        if (
          !record(row, ['location_id', 'organization_id', 'name']) ||
          !id(row.location_id) ||
          row.organization_id !== organizationId ||
          typeof row.name !== 'string' ||
          !row.name ||
          row.name.length > 256 ||
          seen.has(row.location_id)
        )
          fail()
        seen.add(row.location_id)
      }
      if (
        value.next_cursor !== null &&
        (value.items.length === 0 ||
          value.next_cursor !== value.items.at(-1).location_id ||
          value.next_cursor === afterId)
      )
        fail()
      return {
        items: value.items as WorkshopLocation[],
        nextCursor: value.next_cursor as string | null,
      }
    },
    async timeline(
      source: CapturedRead,
      organizationId: string,
      orderId: string,
    ): Promise<LocalServiceOrderEvent[]> {
      if (!id(orderId)) fail()
      const value = await request(
        `/service-orders/${encodeURIComponent(orderId)}/events`,
        source,
        undefined,
        262144,
        source.isCurrent,
      )
      if (!Array.isArray(value) || value.length > 200) fail()
      const seen = new Set<string>()
      for (const row of value) {
        if (
          !record(row, [
            'event_id',
            'order_id',
            'from_state',
            'to_state',
            'action',
            'actor_id',
            'note',
            'occurred_at',
          ]) ||
          !id(row.event_id) ||
          row.order_id !== orderId ||
          !id(row.actor_id) ||
          !['from_state', 'to_state', 'action'].every(
            (k) => typeof row[k] === 'string' && (row[k] as string).length <= 64,
          ) ||
          (row.note !== null && (typeof row.note !== 'string' || row.note.length > 8192)) ||
          typeof row.occurred_at !== 'string' ||
          !Number.isFinite(Date.parse(row.occurred_at)) ||
          seen.has(row.event_id)
        )
          fail()
        seen.add(row.event_id)
      }
      return value.map((row) => ({
        ...row,
        organization_id: organizationId,
      })) as LocalServiceOrderEvent[]
    },
    async revoke(source: CapturedRead): Promise<void> {
      await request('/auth/logout-all', source, {}, 16384, source.isCurrent)
    },
  })
}

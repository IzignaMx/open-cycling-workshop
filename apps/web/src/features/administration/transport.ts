import { cancelResponse, readBoundedJson } from '../../access-kernel/bounded-http.js'
import { validText, validatePassword, normalizeUsername } from './model.js'
import type {
  AdministrationCapture,
  ChangePasswordRequest,
  CreateLocationRequest,
  CreateUserRequest,
  LocationPage,
  LocationResponse,
  PageOptions,
  PatchUserRequest,
  ResetPasswordRequest,
  RoleCatalogResponse,
  UserPage,
  UserPageOptions,
  UserResponse,
  VersionRequest,
} from './contracts.js'
export type AdministrationHttpCode =
  | 'network_error'
  | 'invalid_response'
  | 'invalid_request'
  | 'stale_request'
  | 'invalid_session'
  | 'invalid_credentials'
  | 'administration_denied'
  | 'capability_denied'
  | 'stale_user_version'
  | 'last_owner'
  | 'username_conflict'
  | 'account_conflict'
  | 'user_not_found'
  | 'invalid_owner'
  | 'validation_error'
  | 'client_upgrade_required'
  | 'database_command_failed'
export class AdministrationHttpError extends Error {
  constructor(
    readonly code: AdministrationHttpCode,
    readonly status: number | null = null,
    readonly fields: readonly string[] = [],
  ) {
    super(
      code === 'client_upgrade_required'
        ? 'Actualiza la aplicación antes de continuar.'
        : code === 'stale_user_version'
          ? 'La cuenta cambió. Actualiza y revisa los cambios.'
          : 'No se pudo confirmar la operación.',
    )
    this.name = 'AdministrationHttpError'
  }
}
function fail(
  code: AdministrationHttpCode = 'invalid_response',
  status: number | null = null,
): never {
  throw new AdministrationHttpError(code, status)
}
function object(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}
function shape(value: unknown, keys: readonly string[]): value is Record<string, unknown> {
  return (
    object(value) &&
    Object.keys(value).length === keys.length &&
    keys.every((k) => Object.hasOwn(value, k))
  )
}
const id = (value: unknown): value is string => validText(value, 36)
const version = (value: unknown): value is number =>
  typeof value === 'number' && Number.isSafeInteger(value) && value > 0
function grants(value: unknown): value is string[] {
  return (
    Array.isArray(value) &&
    value.length <= 100 &&
    value.every((g) => validText(g, 128)) &&
    new Set(value).size === value.length
  )
}
function user(value: unknown, source: AdministrationCapture): UserResponse {
  if (
    !shape(value, [
      'user_id',
      'organization_id',
      'location_id',
      'username',
      'display_name',
      'capabilities',
      'is_active',
      'is_owner',
      'version',
    ]) ||
    !id(value.user_id) ||
    value.organization_id !== source.user.organization_id ||
    (value.location_id !== null && !id(value.location_id)) ||
    (source.user.location_id !== null && value.location_id !== source.user.location_id) ||
    !validText(value.username, 160) ||
    !validText(value.display_name, 200) ||
    !grants(value.capabilities) ||
    typeof value.is_active !== 'boolean' ||
    typeof value.is_owner !== 'boolean' ||
    !version(value.version)
  )
    fail()
  return value as unknown as UserResponse
}
function location(value: unknown, source: AdministrationCapture): LocationResponse {
  if (
    !shape(value, ['location_id', 'organization_id', 'name']) ||
    !id(value.location_id) ||
    value.organization_id !== source.user.organization_id ||
    (source.user.location_id !== null && value.location_id !== source.user.location_id) ||
    !validText(value.name, 160)
  )
    fail()
  return value as unknown as LocationResponse
}
const knownErrors: Record<number, readonly string[]> = {
  401: ['invalid_session', 'invalid_credentials'],
  403: ['administration_denied', 'capability_denied'],
  404: ['user_not_found'],
  409: [
    'stale_user_version',
    'last_owner',
    'username_conflict',
    'account_conflict',
    'client_upgrade_required',
  ],
  422: ['invalid_owner', 'validation_error'],
  503: ['database_command_failed'],
}
const fieldNames = new Set([
  'username',
  'display_name',
  'location_id',
  'capabilities',
  'role',
  'is_owner',
  'is_active',
  'expected_version',
  'password',
  'current_password',
  'new_password',
  'name',
  'active',
  'after_id',
  'limit',
])
function errorFrom(value: unknown, status: number): AdministrationHttpError {
  let code: unknown
  if (object(value)) {
    if (object(value.error)) code = value.error.code
    else if (typeof value.detail === 'string') code = value.detail
    if (status === 422 && Array.isArray(value.detail)) {
      const fields = new Set<string>()
      for (const item of value.detail.slice(0, 100))
        if (object(item) && Array.isArray(item.loc))
          for (const part of item.loc)
            if (typeof part === 'string' && fieldNames.has(part)) fields.add(part)
      return new AdministrationHttpError('validation_error', status, [...fields])
    }
  }
  if (typeof code === 'string' && knownErrors[status]?.includes(code))
    return new AdministrationHttpError(code as AdministrationHttpCode, status)
  if (status === 401) return new AdministrationHttpError('invalid_session', status)
  if (status === 403) return new AdministrationHttpError('capability_denied', status)
  return new AdministrationHttpError('invalid_response', status)
}
function allowedInput(
  value: unknown,
  allowed: readonly string[],
  required: readonly string[],
): asserts value is Record<string, unknown> {
  if (
    !object(value) ||
    Object.keys(value).some((k) => !allowed.includes(k)) ||
    required.some((k) => !Object.hasOwn(value, k))
  )
    fail('invalid_request')
}
function selection(value: { role?: string | null; capabilities?: string[] | null }): boolean {
  return (
    (value.role != null) !== (value.capabilities != null) &&
    (value.role == null || validText(value.role, 128)) &&
    (value.capabilities == null ||
      (grants(value.capabilities) && !value.capabilities.includes('*')))
  )
}
export function createAdministrationTransport(options: { apiRealm: string; fetch: typeof fetch }) {
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
    fail('invalid_request')
  async function request(
    source: AdministrationCapture,
    path: string,
    method: 'GET' | 'POST' | 'PATCH',
    expected: number,
    body?: unknown,
  ): Promise<unknown> {
    const token = source.token,
      check = source.isCurrent,
      signal = source.signal
    const current = () => !signal?.aborted && check()
    if (!current()) fail('stale_request')
    if (!token || token.length > 16384 || /\s/.test(token)) fail('invalid_request')
    const serialized = body === undefined ? undefined : JSON.stringify(body)
    if (serialized !== undefined && new TextEncoder().encode(serialized).length > 32768)
      fail('invalid_request')
    const url = `${options.apiRealm}${path}`
    if (new URL(url).href !== url) fail('invalid_request')
    const headers: Record<string, string> = {
      Accept: 'application/json',
      Authorization: `Bearer ${token}`,
    }
    if (method !== 'GET') headers['X-OCWP-Write-Protocol'] = '1'
    if (serialized !== undefined) headers['Content-Type'] = 'application/json'
    const abort = new AbortController()
    const forward = () => abort.abort()
    signal?.addEventListener('abort', forward, { once: true })
    let timer: ReturnType<typeof setTimeout> | undefined
    const deadline = new Promise<never>((_, reject) => {
      timer = setTimeout(() => {
        abort.abort()
        reject(new AdministrationHttpError(current() ? 'network_error' : 'stale_request'))
      }, 10000)
    })
    let response: Response | undefined
    let expired = false
    try {
      const work = (async () => {
        let r: Response
        try {
          // Native browser fetch requires the global receiver, not this options object.
          r = await options.fetch.call(globalThis, url, {
            method,
            headers,
            ...(serialized === undefined ? {} : { body: serialized }),
            signal: abort.signal,
            cache: 'no-store',
            credentials: 'omit',
            redirect: 'error',
            referrerPolicy: 'no-referrer',
          })
        } catch {
          fail(current() ? 'network_error' : 'stale_request')
        }
        response = r
        if (expired || !current()) {
          void cancelResponse(r)
          fail('stale_request')
        }
        if (r.url !== url || r.redirected) {
          void cancelResponse(r)
          fail()
        }
        // A received current refusal is authoritative even if its body or
        // ancillary headers are malformed. Never turn it into connectivity.
        if (r.status === 401 || r.status === 403) {
          void cancelResponse(r)
          fail(r.status === 401 ? 'invalid_session' : 'capability_denied', r.status)
        }
        if (
          !r.headers
            .get('cache-control')
            ?.split(',')
            .some((v) => v.trim().toLowerCase() === 'no-store')
        ) {
          void cancelResponse(r)
          fail()
        }
        if (r.status === 204 && expected === 204) return undefined
        if (
          r.headers.get('content-type')?.split(';')[0]?.trim().toLowerCase() !== 'application/json'
        ) {
          void cancelResponse(r)
          fail()
        }
        let value: unknown
        try {
          value = await readBoundedJson(r, 1048576, abort.signal)
        } catch {
          if (!current()) fail('stale_request')
          fail('invalid_response')
        }
        if (expired || !current()) fail('stale_request')
        if (r.status !== expected) {
          if (!r.ok) throw errorFrom(value, r.status)
          fail()
        }
        return value
      })()
      return await Promise.race([work, deadline])
    } finally {
      expired = true
      if (timer !== undefined) clearTimeout(timer)
      signal?.removeEventListener('abort', forward)
      if (response && abort.signal.aborted) void cancelResponse(response)
    }
  }
  function capture(source: AdministrationCapture): AdministrationCapture {
    // Copy authority metadata before the first await; the runtime owns its exact-current predicate.
    return {
      token: source.token,
      user: { ...source.user, capabilities: [...source.user.capabilities] },
      isCurrent: source.isCurrent,
      ...(source.signal ? { signal: source.signal } : {}),
    }
  }
  function query(options: PageOptions): { query: URLSearchParams; limit: number } {
    const limit = options.limit ?? 50
    if (
      !Number.isSafeInteger(limit) ||
      limit < 1 ||
      limit > 200 ||
      (options.afterId !== undefined && !id(options.afterId))
    )
      fail('invalid_request')
    const query = new URLSearchParams({ limit: String(limit) })
    if (options.afterId !== undefined) query.set('after_id', options.afterId)
    return { query, limit }
  }
  function page<T>(
    value: unknown,
    limit: number,
    afterId: string | undefined,
    parse: (row: unknown) => T,
    key: (row: T) => string,
  ): { items: T[]; next_cursor: string | null } {
    if (
      !shape(value, ['items', 'next_cursor']) ||
      !Array.isArray(value.items) ||
      value.items.length > limit ||
      (value.next_cursor !== null && !id(value.next_cursor))
    )
      fail()
    const items = value.items.map(parse),
      ids = items.map(key)
    if (
      new Set(ids).size !== ids.length ||
      ids.some((v, i) => (i > 0 && v <= ids[i - 1]!) || (afterId !== undefined && v <= afterId))
    )
      fail()
    if (value.next_cursor !== null && (items.length !== limit || value.next_cursor !== ids.at(-1)))
      fail()
    return { items, next_cursor: value.next_cursor as string | null }
  }
  function targetPath(targetId: string): string {
    if (!id(targetId)) fail('invalid_request')
    return `/admin/users/${encodeURIComponent(targetId)}`
  }
  async function targetCommand(
    source: AdministrationCapture,
    targetId: string,
    body: PatchUserRequest | VersionRequest | ResetPasswordRequest,
    suffix = '',
    method: 'POST' | 'PATCH' = 'POST',
  ): Promise<UserResponse> {
    if (!version(body.expected_version)) fail('invalid_request')
    const s = capture(source),
      path = targetPath(targetId)
    const result = user(await request(s, `${path}${suffix}`, method, 200, body), s)
    if (result.user_id !== targetId || result.version <= body.expected_version) fail()
    return result
  }
  return Object.freeze({
    async roles(source: AdministrationCapture): Promise<RoleCatalogResponse> {
      const s = capture(source),
        value = await request(s, '/admin/roles', 'GET', 200)
      if (
        !shape(value, ['roles', 'capabilities']) ||
        !grants(value.capabilities) ||
        value.capabilities.includes('*') ||
        !Array.isArray(value.roles) ||
        value.roles.length > 100
      )
        fail()
      const names = new Set<string>()
      for (const role of value.roles) {
        if (
          !shape(role, ['name', 'capabilities']) ||
          !validText(role.name, 128) ||
          names.has(role.name) ||
          !grants(role.capabilities) ||
          role.capabilities.some((g) => !(value.capabilities as string[]).includes(g))
        )
          fail()
        names.add(role.name)
      }
      return value as unknown as RoleCatalogResponse
    },
    async users(source: AdministrationCapture, options: UserPageOptions = {}): Promise<UserPage> {
      const s = capture(source),
        { query: q, limit } = query(options),
        active = options.active,
        afterId = options.afterId
      if (active !== undefined) {
        if (typeof active !== 'boolean') fail('invalid_request')
        q.set('active', String(active))
      }
      const result = page(
        await request(s, `/admin/users?${q}`, 'GET', 200),
        limit,
        afterId,
        (row) => user(row, s),
        (row) => row.user_id,
      )
      if (active !== undefined && result.items.some((row) => row.is_active !== active)) fail()
      return result
    },
    async locations(
      source: AdministrationCapture,
      options: PageOptions = {},
    ): Promise<LocationPage> {
      const s = capture(source),
        { query: q, limit } = query(options),
        afterId = options.afterId
      return page(
        await request(s, `/locations?${q}`, 'GET', 200),
        limit,
        afterId,
        (row) => location(row, s),
        (row) => row.location_id,
      )
    },
    async createUser(
      source: AdministrationCapture,
      input: CreateUserRequest,
    ): Promise<UserResponse> {
      allowedInput(
        input,
        ['username', 'display_name', 'password', 'location_id', 'role', 'capabilities', 'is_owner'],
        ['username', 'display_name', 'password', 'location_id'],
      )
      if (
        typeof input.username !== 'string' ||
        typeof input.display_name !== 'string' ||
        typeof input.password !== 'string'
      )
        fail('invalid_request')
      const body = {
        ...input,
        username: normalizeUsername(input.username),
        display_name: input.display_name.trim(),
        ...(input.capabilities ? { capabilities: [...input.capabilities] } : {}),
      }
      if (
        !validText(body.username, 160) ||
        !validText(body.display_name, 200) ||
        !validatePassword(body.password) ||
        !selection(body) ||
        (body.location_id !== null && !id(body.location_id)) ||
        (body.is_owner !== undefined && typeof body.is_owner !== 'boolean')
      )
        fail('invalid_request')
      const s = capture(source)
      return user(await request(s, '/admin/users', 'POST', 201, body), s)
    },
    async updateUser(
      source: AdministrationCapture,
      targetId: string,
      input: PatchUserRequest,
    ): Promise<UserResponse> {
      allowedInput(
        input,
        [
          'expected_version',
          'display_name',
          'location_id',
          'role',
          'capabilities',
          'is_active',
          'is_owner',
        ],
        ['expected_version'],
      )
      if (
        Object.keys(input).length < 2 ||
        (Object.hasOwn(input, 'display_name') &&
          (!validText(input.display_name, 200) || !input.display_name.trim())) ||
        (Object.hasOwn(input, 'location_id') &&
          input.location_id !== null &&
          !id(input.location_id)) ||
        (['is_active', 'is_owner'] as const).some(
          (k) => Object.hasOwn(input, k) && typeof input[k] !== 'boolean',
        ) ||
        ((Object.hasOwn(input, 'role') || Object.hasOwn(input, 'capabilities')) &&
          !selection(input))
      )
        fail('invalid_request')
      const body = {
        ...input,
        ...(input.display_name !== undefined ? { display_name: input.display_name.trim() } : {}),
        ...(input.capabilities ? { capabilities: [...input.capabilities] } : {}),
      }
      return targetCommand(source, targetId, body, '', 'PATCH')
    },
    async resetPassword(
      source: AdministrationCapture,
      targetId: string,
      input: ResetPasswordRequest,
    ): Promise<UserResponse> {
      allowedInput(
        input,
        ['expected_version', 'new_password'],
        ['expected_version', 'new_password'],
      )
      if (typeof input.new_password !== 'string' || !validatePassword(input.new_password))
        fail('invalid_request')
      return targetCommand(source, targetId, { ...input }, '/reset-password')
    },
    async revokeSessions(
      source: AdministrationCapture,
      targetId: string,
      input: VersionRequest,
    ): Promise<UserResponse> {
      allowedInput(input, ['expected_version'], ['expected_version'])
      return targetCommand(source, targetId, { ...input }, '/revoke-sessions')
    },
    async createLocation(
      source: AdministrationCapture,
      input: CreateLocationRequest,
    ): Promise<LocationResponse> {
      allowedInput(input, ['name'], ['name'])
      if (typeof input.name !== 'string' || !validText(input.name.trim(), 160))
        fail('invalid_request')
      const s = capture(source)
      return location(await request(s, '/locations', 'POST', 201, { name: input.name.trim() }), s)
    },
    async changePassword(
      source: AdministrationCapture,
      input: ChangePasswordRequest,
    ): Promise<void> {
      allowedInput(
        input,
        ['current_password', 'new_password'],
        ['current_password', 'new_password'],
      )
      if (
        typeof input.current_password !== 'string' ||
        typeof input.new_password !== 'string' ||
        !validatePassword(input.current_password, true) ||
        !validatePassword(input.new_password)
      )
        fail('invalid_request')
      await request(capture(source), '/auth/change-password', 'POST', 204, { ...input })
    },
    async logoutAll(source: AdministrationCapture): Promise<void> {
      await request(capture(source), '/auth/logout-all', 'POST', 204, {})
    },
  })
}
export type AdministrationTransport = ReturnType<typeof createAdministrationTransport>

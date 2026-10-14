import { validateVerifiedContext } from './context.js'
import type { ContextRequestIdentity } from './server-context.js'
import {
  BASELINE_CONTROL_LIMIT,
  BASELINE_RESPONSE_LIMIT,
  validateBaselineRequest,
  validateBaselineResponse,
  type BaselineBinding,
  type BaselineKind,
  type BaselineResponseMap,
} from './baseline-wire.js'

export type BaselineErrorCode =
  | 'invalid_response'
  | 'invalid_request'
  | 'network_error'
  | 'stale_request'
  | 'invalid_session'
  | 'capability_denied'
  | 'scope_denied'
  | 'unsupported_protocol'
  | 'context_changed'
  | 'continuation_stale'
  | 'dataset_changed'
  | 'baseline_expired'
  | 'checkpoint_expired'
  | 'baseline_in_progress'
  | 'baseline_capacity'
  | 'temporary_unavailable'
  | 'projection_too_large'
  | 'cursor_invalid'
/** Only fixed safe codes and bounded numeric retry metadata cross the error boundary. */
export class BaselineTransportError extends Error {
  constructor(
    readonly code: BaselineErrorCode,
    readonly status: number | null = null,
    readonly retryAfterMs: number | null = null,
  ) {
    super(`Baseline request failed: ${code}`)
    this.name = 'BaselineTransportError'
  }
}
function reject(code: BaselineErrorCode = 'invalid_response'): never {
  throw new BaselineTransportError(code)
}
/** Count streamed bytes before decoding/parsing, irrespective of Content-Length. */
export async function readBoundedBaselineJson(
  response: Response,
  limit = BASELINE_RESPONSE_LIMIT,
): Promise<unknown> {
  if (!Number.isSafeInteger(limit) || limit < 1 || limit > BASELINE_RESPONSE_LIMIT) return reject()
  const stream = response.body
  if (!stream) return reject()
  const reader = stream.getReader()
  let completed = false
  try {
    const length = response.headers.get('content-length')
    if (
      length !== null &&
      (!/^\d+$/.test(length) || !Number.isSafeInteger(Number(length)) || Number(length) > limit)
    )
      return reject()
    const decoder = new TextDecoder('utf-8', { fatal: true })
    let bytes = 0,
      text = ''
    for (;;) {
      const next = await reader.read().catch(() => reject('network_error'))
      if (next.done) {
        completed = true
        break
      }
      bytes += next.value.byteLength
      if (bytes > limit) return reject()
      text += decoder.decode(next.value, { stream: true })
    }
    text += decoder.decode()
    return JSON.parse(text) as unknown
  } catch (error) {
    if (error instanceof BaselineTransportError) throw error
    return reject()
  } finally {
    if (!completed) {
      try {
        await reader.cancel()
      } catch {
        /* no raw stream errors escape */
      }
    }
    reader.releaseLock()
  }
}
async function cancelResponse(response: Response): Promise<void> {
  try {
    await response.body?.cancel()
  } catch {
    /* Do not expose stream exceptions. */
  }
}
const paths: Record<BaselineKind, string> = {
  start: '/sync/baselines/start',
  scan: '/sync/baselines/page',
  finalize: '/sync/baselines/finalize',
  delta: '/sync/deltas/page',
  activation: '/sync/baselines/validate-activation',
}
const knownErrors: Partial<Record<BaselineErrorCode, number>> = {
  invalid_session: 401,
  capability_denied: 403,
  scope_denied: 403,
  unsupported_protocol: 422,
  context_changed: 409,
  continuation_stale: 409,
  dataset_changed: 409,
  baseline_expired: 410,
  checkpoint_expired: 410,
  baseline_in_progress: 409,
  baseline_capacity: 429,
  temporary_unavailable: 503,
  projection_too_large: 413,
  cursor_invalid: 422,
}
function errorResponse(response: Response, value: unknown, now: number): BaselineTransportError {
  let code: BaselineErrorCode = 'invalid_response'
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    const body = value as Record<string, unknown>
    if (body.error && typeof body.error === 'object' && !Array.isArray(body.error)) {
      const candidate = (body.error as Record<string, unknown>).code
      if (
        typeof candidate === 'string' &&
        Object.hasOwn(knownErrors, candidate) &&
        knownErrors[candidate as BaselineErrorCode] === response.status
      )
        code = candidate as BaselineErrorCode
    } else if (Object.keys(body).length === 1 && Object.hasOwn(body, 'detail')) {
      if (response.status === 401 && typeof body.detail === 'string') code = 'invalid_session'
      if (response.status === 403 && typeof body.detail === 'string') code = 'capability_denied'
      if (response.status === 422 && Array.isArray(body.detail)) code = 'invalid_request'
    }
  }
  const retry = response.headers.get('retry-after')
  let retryAfterMs: number | null = null
  if (retry !== null) {
    const delay = /^\d+$/.test(retry)
      ? Number(retry) * 1000
      : /^[A-Za-z]{3}, \d{2} [A-Za-z]{3} \d{4} \d{2}:\d{2}:\d{2} GMT$/.test(retry)
        ? Date.parse(retry) - now
        : NaN
    if (Number.isSafeInteger(delay) && delay >= 0 && Number.isSafeInteger(now + delay))
      retryAfterMs = delay
  }
  return new BaselineTransportError(code, response.status, retryAfterMs)
}
export interface BaselineTransportOptions {
  apiRealm: string
  fetch: typeof globalThis.fetch
  now: () => number
}
export interface BaselineTransportRequest<K extends BaselineKind> {
  kind: K
  /** Persisted exact body; validation never reserializes it for dispatch. */
  body: string
  identity: ContextRequestIdentity
  bearerToken: string
  isCurrent: (identity: Readonly<ContextRequestIdentity>) => boolean
  binding: BaselineBinding
}
function canonicalRealm(value: string): string {
  try {
    const url = new URL(value)
    if (
      !['http:', 'https:'].includes(url.protocol) ||
      url.username ||
      url.password ||
      url.search ||
      url.hash ||
      value.endsWith('/') ||
      url.href !== value
    )
      return reject('invalid_request')
    return value
  } catch {
    return reject('invalid_request')
  }
}
/** Lower-level protocol transport. Actual null advertisement is retained; admission is coordinator-owned. */
export function createBaselineTransport(options: BaselineTransportOptions) {
  const realm = canonicalRealm(options.apiRealm),
    fetchRequest = options.fetch,
    clock = options.now
  let sequence = 0
  return Object.freeze({
    invalidate() {
      sequence += 1
    },
    async request<K extends BaselineKind>(
      request: BaselineTransportRequest<K>,
    ): Promise<BaselineResponseMap[K]> {
      const operation = ++sequence
      let networkStarted = false
      let current: (() => boolean) | undefined
      try {
        // No await precedes this complete credential, request, authority and routing capture.
        const source = request.identity
        const identity: Readonly<ContextRequestIdentity> = Object.freeze({
          apiRealm: source.apiRealm,
          organizationId: source.organizationId,
          userId: source.userId,
          selectedLocationId: source.selectedLocationId,
          deviceGeneration: source.deviceGeneration,
          tabAttemptId: source.tabAttemptId,
          sessionHandle: source.sessionHandle,
          ...(source.expectedAuthorizationEpoch === undefined
            ? {}
            : { expectedAuthorizationEpoch: source.expectedAuthorizationEpoch }),
        })
        const bearer = request.bearerToken,
          body = request.body,
          kind = request.kind,
          isCurrent = request.isCurrent
        const binding: BaselineBinding = structuredClone(request.binding)
        binding.identity = identity
        Object.freeze(binding.context.principal)
        Object.freeze(binding.context.capabilities)
        Object.freeze(binding.context)
        Object.freeze(binding)
        current = () => {
          try {
            return operation === sequence && isCurrent(identity) === true
          } catch {
            return false
          }
        }
        const started = clock()
        if (!current()) return reject('stale_request')
        if (
          identity.apiRealm !== realm ||
          typeof bearer !== 'string' ||
          !bearer ||
          /\s/.test(bearer) ||
          !Number.isSafeInteger(identity.deviceGeneration) ||
          identity.deviceGeneration < 0 ||
          typeof identity.tabAttemptId !== 'string' ||
          !identity.tabAttemptId ||
          typeof identity.sessionHandle !== 'string' ||
          !identity.sessionHandle ||
          !Number.isFinite(started) ||
          !Object.hasOwn(paths, kind)
        )
          return reject('invalid_request')
        validateVerifiedContext(binding.context, started)
        if (
          binding.context.principal.apiRealm !== realm ||
          binding.context.principal.organizationId !== identity.organizationId ||
          binding.context.principal.userId !== identity.userId ||
          binding.context.selectedLocationId !== identity.selectedLocationId ||
          (identity.expectedAuthorizationEpoch !== undefined &&
            identity.expectedAuthorizationEpoch !== binding.context.authorizationEpoch)
        )
          return reject('invalid_request')
        const parsed = validateBaselineRequest(kind, body)
        if (
          'selected_location_id' in parsed &&
          (parsed.selected_location_id !== identity.selectedLocationId ||
            parsed.authorization_epoch !== binding.context.authorizationEpoch)
        )
          return reject('invalid_request')
        if ('continuation' in parsed && parsed.continuation !== binding.predecessor)
          return reject('invalid_request')
        if ('checkpoint' in parsed && parsed.checkpoint !== binding.checkpoint)
          return reject('invalid_request')
        const url = `${realm}${paths[kind]}`
        networkStarted = true
        const response = await fetchRequest(url, {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${bearer}`,
            Accept: 'application/json',
            'Content-Type': 'application/json',
          },
          body,
          cache: 'no-store',
          redirect: 'error',
          credentials: 'omit',
          referrerPolicy: 'no-referrer',
        })
        if (!current()) {
          await cancelResponse(response)
          return reject('stale_request')
        }
        if (
          response.redirected ||
          response.url !== url ||
          response.headers.get('content-type')?.split(';')[0]?.trim().toLowerCase() !==
            'application/json' ||
          !response.headers
            .get('cache-control')
            ?.split(',')
            .some((part) => part.trim().toLowerCase() === 'no-store')
        ) {
          await cancelResponse(response)
          return reject()
        }
        const value = await readBoundedBaselineJson(
          response,
          response.ok && kind === 'start' ? BASELINE_CONTROL_LIMIT : BASELINE_RESPONSE_LIMIT,
        )
        if (!current()) return reject('stale_request')
        const finished = clock()
        if (!Number.isFinite(finished) || finished < started) return reject()
        if (!response.ok) throw errorResponse(response, value, finished)
        try {
          return validateBaselineResponse(kind, value, binding, finished)
        } catch {
          return reject()
        }
      } catch (error) {
        if (error instanceof BaselineTransportError) throw error
        if (current && !current()) return reject('stale_request')
        return reject(networkStarted ? 'network_error' : 'invalid_request')
      }
    },
  })
}

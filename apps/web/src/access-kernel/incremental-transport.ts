import { BoundedHttpError, readBoundedJson, cancelResponse } from './bounded-http.js'
import { validateVerifiedContext } from './context.js'
import type { ContextRequestIdentity } from './server-context.js'
import { BASELINE_CONTROL_LIMIT, BASELINE_RESPONSE_LIMIT } from './baseline-wire.js'
import { validateIncrementalRequest } from './incremental-state.js'
import {
  validateIncrementalResponse,
  type IncrementalBinding,
  type IncrementalResponse,
} from './incremental-wire.js'

export type IncrementalErrorCode =
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
export class IncrementalTransportError extends Error {
  constructor(
    readonly code: IncrementalErrorCode,
    readonly status: number | null = null,
    readonly retryAfterMs: number | null = null,
  ) {
    super(`Baseline request failed: ${code}`)
    this.name = 'IncrementalTransportError'
  }
}
function reject(code: IncrementalErrorCode = 'invalid_response'): never {
  throw new IncrementalTransportError(code)
}
const knownErrors: Partial<Record<IncrementalErrorCode, number>> = {
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
function errorResponse(response: Response, value: unknown, now: number): IncrementalTransportError {
  let code: IncrementalErrorCode = 'invalid_response'
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    const body = value as Record<string, unknown>
    if (
      Object.keys(body).length === 1 &&
      body.error &&
      typeof body.error === 'object' &&
      !Array.isArray(body.error)
    ) {
      const error = body.error as Record<string, unknown>
      const candidate = error.code
      if (
        Object.keys(error).length === 4 &&
        ['code', 'message', 'details', 'request_id'].every((key) => Object.hasOwn(error, key)) &&
        typeof error.message === 'string' &&
        error.details !== null &&
        typeof error.details === 'object' &&
        !Array.isArray(error.details) &&
        (error.request_id === null || typeof error.request_id === 'string') &&
        typeof candidate === 'string' &&
        Object.hasOwn(knownErrors, candidate) &&
        knownErrors[candidate as IncrementalErrorCode] === response.status
      )
        code = candidate as IncrementalErrorCode
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
  return new IncrementalTransportError(code, response.status, retryAfterMs)
}
export interface IncrementalTransportOptions {
  apiRealm: string
  fetch: typeof globalThis.fetch
  now: () => number
}
export interface IncrementalTransportRequest {
  /** Persisted exact body; validation never reserializes it for dispatch. */
  body: string
  identity: ContextRequestIdentity
  bearerToken: string
  isCurrent: (identity: Readonly<ContextRequestIdentity>) => boolean
  binding: IncrementalBinding
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
/** Exact captured transport for ongoing deltas, never initial activation validation. */
export function createIncrementalTransport(options: IncrementalTransportOptions) {
  const realm = canonicalRealm(options.apiRealm),
    fetchRequest = options.fetch,
    clock = options.now
  let sequence = 0
  return Object.freeze({
    invalidate() {
      sequence += 1
    },
    async request(request: IncrementalTransportRequest): Promise<IncrementalResponse> {
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
          isCurrent = request.isCurrent
        const binding: IncrementalBinding = structuredClone(request.binding)
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
          !Number.isFinite(started)
        )
          return reject('invalid_request')
        validateVerifiedContext(binding.context, started)
        if (
          binding.context.snapshotProtocol !== 'baseline-v1' ||
          !binding.context.capabilities.includes('sync.pull') ||
          binding.context.principal.apiRealm !== realm ||
          binding.context.principal.organizationId !== identity.organizationId ||
          binding.context.principal.userId !== identity.userId ||
          binding.context.selectedLocationId !== identity.selectedLocationId ||
          (identity.expectedAuthorizationEpoch !== undefined &&
            identity.expectedAuthorizationEpoch !== binding.context.authorizationEpoch)
        )
          return reject('invalid_request')
        const predecessor = validateIncrementalRequest({ kind: 'delta', body })
        if (predecessor !== binding.predecessor) return reject('invalid_request')
        const url = `${realm}/sync/deltas/page`
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
        const value = await readBoundedJson(
          response,
          response.ok ? BASELINE_RESPONSE_LIMIT : BASELINE_CONTROL_LIMIT,
        )
        if (!current()) return reject('stale_request')
        const finished = clock()
        if (!Number.isFinite(finished) || finished < started) return reject()
        if (!response.ok) throw errorResponse(response, value, finished)
        try {
          validateVerifiedContext(binding.context, finished)
          return validateIncrementalResponse(value, binding)
        } catch {
          return reject()
        }
      } catch (error) {
        if (error instanceof IncrementalTransportError) throw error
        if (error instanceof BoundedHttpError) return reject(error.code)
        if (current && !current()) return reject('stale_request')
        return reject(networkStarted ? 'network_error' : 'invalid_request')
      }
    },
  })
}

import { BoundedHttpError, cancelResponse, readBoundedJson } from './bounded-http.js'
import { canonicalJson, validateResults } from './operations.js'
import { principalKey, validateVerifiedContext } from './context.js'
import type { BaselineSession } from './baseline-coordinator.js'
import type { DispatchBatch } from './types.js'
import type { PushResponse } from '../sync/types.js'

export type PushErrorCode =
  | 'invalid_request'
  | 'invalid_response'
  | 'network_error'
  | 'stale_request'
  | 'invalid_session'
  | 'capability_denied'
  | 'client_upgrade_required'
  | 'authorization_context_changed'
  | 'temporary_unavailable'
export class PushTransportError extends Error {
  constructor(readonly code: PushErrorCode) {
    super(`Push request failed: ${code}`)
    this.name = 'PushTransportError'
  }
}
function reject(code: PushErrorCode = 'invalid_response'): never {
  throw new PushTransportError(code)
}
const keys = (value: unknown, expected: readonly string[]): value is Record<string, unknown> =>
  !!value &&
  typeof value === 'object' &&
  !Array.isArray(value) &&
  Object.keys(value).length === expected.length &&
  expected.every((k) => Object.hasOwn(value, k))
const resultCodes = new Set([
  'sync_conflict',
  'legacy_receipt_unverified',
  'receipt_integrity_conflict',
  'receipt_proof_conflict',
])
export interface PushRequest extends BaselineSession {
  batch: DispatchBatch
}
export function createPushTransport(options: {
  apiRealm: string
  fetch: typeof fetch
  now(): number
}) {
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
    reject('invalid_request')
  let sequence = 0
  return Object.freeze({
    invalidate() {
      sequence++
    },
    async push(source: PushRequest): Promise<PushResponse> {
      const call = ++sequence,
        identity = structuredClone(source.identity),
        context = structuredClone(source.context),
        batch = structuredClone(source.batch),
        bearer = source.bearerToken,
        check = source.isCurrent
      const current = () => {
        try {
          return call === sequence && check(identity)
        } catch {
          return false
        }
      }
      if (!current()) reject('stale_request')
      const start = options.now()
      try {
        validateVerifiedContext(context, start)
      } catch {
        reject('invalid_request')
      }
      if (
        identity.apiRealm !== options.apiRealm ||
        context.principal.apiRealm !== options.apiRealm ||
        identity.organizationId !== context.principal.organizationId ||
        identity.userId !== context.principal.userId ||
        identity.selectedLocationId !== context.selectedLocationId ||
        identity.deviceGeneration !== batch.ticket.deviceGeneration ||
        identity.tabAttemptId !== batch.ticket.tabAttemptId ||
        batch.ticket.authorizationEpoch !== context.authorizationEpoch ||
        batch.ticket.principalKey !== principalKey(context.principal) ||
        (identity.expectedAuthorizationEpoch !== undefined &&
          identity.expectedAuthorizationEpoch !== context.authorizationEpoch) ||
        canonicalJson(batch.ticket) !== canonicalJson(source.ticket) ||
        !bearer ||
        /\s/.test(bearer) ||
        batch.operations.length < 1 ||
        batch.operations.length > 100
      )
        reject('invalid_request')
      for (const op of batch.operations) {
        if (
          !keys(op.envelope, [
            'mutation_id',
            'entity_type',
            'entity_id',
            'operation',
            'organization_id',
            'location_id',
            'base_version',
            'occurred_at',
            'payload',
          ]) ||
          op.authoredDatasetIncarnation !== context.datasetIncarnation ||
          op.principalKey !== batch.ticket.principalKey ||
          op.envelope.organization_id !== identity.organizationId ||
          op.envelope.location_id !== identity.selectedLocationId
        )
          reject('invalid_request')
      }
      const body = JSON.stringify({ mutations: batch.operations.map((op) => op.envelope) })
      if (new TextEncoder().encode(body).byteLength > 262144) reject('invalid_request')
      const url = `${options.apiRealm}/sync/mutations`
      let response: Response
      try {
        if (!current()) reject('stale_request')
        response = await options.fetch(url, {
          method: 'POST',
          body,
          headers: {
            Authorization: `Bearer ${bearer}`,
            Accept: 'application/json',
            'Content-Type': 'application/json',
            'X-OCWP-Write-Protocol': '1',
            'X-OCWP-Authorization-Epoch': context.authorizationEpoch,
          },
          cache: 'no-store',
          redirect: 'error',
          credentials: 'omit',
          referrerPolicy: 'no-referrer',
        })
      } catch (error) {
        if (error instanceof PushTransportError) throw error
        reject(current() ? 'network_error' : 'stale_request')
      }
      if (!current()) {
        await cancelResponse(response)
        reject('stale_request')
      }
      if (
        response.redirected ||
        response.url !== url ||
        response.headers.get('content-type')?.split(';')[0]?.trim().toLowerCase() !==
          'application/json' ||
        !response.headers
          .get('cache-control')
          ?.split(',')
          .some((p) => p.trim().toLowerCase() === 'no-store')
      ) {
        await cancelResponse(response)
        reject()
      }
      let value: unknown
      try {
        value = await readBoundedJson(response, 262144)
      } catch (error) {
        reject(
          error instanceof BoundedHttpError && error.code === 'network_error'
            ? 'network_error'
            : 'invalid_response',
        )
      }
      if (!current()) reject('stale_request')
      if (!Number.isFinite(options.now()) || options.now() < start) reject()
      if (!response.ok) {
        if (
          keys(value, ['error']) &&
          keys(value.error, ['code', 'message', 'details', 'request_id']) &&
          typeof value.error.message === 'string'
        ) {
          const expected: Partial<Record<PushErrorCode, number>> = {
            client_upgrade_required: 409,
            authorization_context_changed: 409,
            invalid_session: 401,
            capability_denied: 403,
            temporary_unavailable: 503,
          }
          const code = value.error.code as PushErrorCode
          if (Object.hasOwn(expected, code) && expected[code] === response.status) reject(code)
        }
        if (
          keys(value, ['detail']) &&
          typeof value.detail === 'string' &&
          [401, 403].includes(response.status)
        )
          reject(response.status === 401 ? 'invalid_session' : 'capability_denied')
        reject()
      }
      if (!keys(value, ['results']) || !Array.isArray(value.results)) reject()
      for (const result of value.results) {
        if (
          !keys(result, [
            'mutation_id',
            'entity_id',
            'status',
            'entity_version',
            'error_code',
            'error_message',
          ])
        )
          reject()
        if (
          result.status === 'conflict' &&
          (!resultCodes.has(result.error_code as string) ||
            typeof result.error_message !== 'string' ||
            result.error_message.length > 2048)
        )
          reject()
      }
      try {
        return { results: validateResults(batch.operations, value) }
      } catch {
        reject()
      }
    },
  })
}

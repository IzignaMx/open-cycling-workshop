import { isDatasetIncarnation, validateVerifiedContext } from './context.js'
import type { VerifiedAccessContext, VerificationAttempt } from './types.js'

/** Routing expectation only; never a substitute for server authentication. */
export interface ContextRequestIdentity extends VerificationAttempt {
  apiRealm: string
  organizationId: string
  userId: string
  selectedLocationId: string
  /** Volatile opaque identifier for this exact authenticated session, not its credential. */
  sessionHandle: string
  expectedAuthorizationEpoch?: string
}
export interface ContextVerificationRequest {
  identity: ContextRequestIdentity
  bearerToken: string
  /** Compare all captured identity/session/generation fields to current state. */
  isCurrent: (captured: Readonly<ContextRequestIdentity>) => boolean
}
export interface ServerContextAdapterOptions {
  /** Explicit trusted configuration, never Host, a response field or login claims. */
  apiRealm: string
  fetch: typeof globalThis.fetch
  now: () => number
}

function reject(): never {
  // Never expose bearer, response body, URL or transport exception in errors.
  throw new Error('Server context verification failed')
}
function record(value: unknown, keys: readonly string[]): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return reject()
  const object = value as Record<string, unknown>
  if (Object.keys(object).length !== keys.length || keys.some((key) => !Object.hasOwn(object, key)))
    return reject()
  return object
}
function id(value: unknown): value is string {
  return (
    typeof value === 'string' &&
    value.length > 0 &&
    [...value].length <= 36 &&
    !value.includes('\0')
  )
}
function canonicalRealm(value: string): string {
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
    return reject()
  return value
}
function instant(value: unknown): string {
  // Server emits UTC RFC3339 with up to microsecond precision. Truncating the
  // expiry to milliseconds is conservative; reject calendar normalization.
  if (
    typeof value !== 'string' ||
    !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)$/.test(value)
  )
    return reject()
  const time = Date.parse(value)
  if (!Number.isFinite(time)) return reject()
  const normalized = new Date(time).toISOString()
  if (normalized.slice(0, 19) !== value.slice(0, 19)) return reject()
  return normalized
}
export function convertServerContext(
  value: unknown,
  identity: Readonly<ContextRequestIdentity>,
  now: number,
): VerifiedAccessContext {
  const body = record(value, [
    'protocol',
    'principal',
    'account_location_id',
    'selected_location_id',
    'capabilities',
    'authorization_epoch',
    'policy_revision',
    'dataset_incarnation',
    'verified_at',
    'offline_until',
    'snapshot_protocol',
  ])
  const principal = record(body.principal, ['api_realm', 'organization_id', 'user_id'])
  if (
    body.protocol !== 1 ||
    body.policy_revision !== 'ocwp-access-baseline-2' ||
    !isDatasetIncarnation(body.dataset_incarnation) ||
    (body.snapshot_protocol !== null && body.snapshot_protocol !== 'baseline-v1') ||
    principal.api_realm !== null ||
    !id(principal.organization_id) ||
    !id(principal.user_id) ||
    !id(body.selected_location_id) ||
    (body.account_location_id !== null && !id(body.account_location_id)) ||
    principal.organization_id !== identity.organizationId ||
    principal.user_id !== identity.userId ||
    body.selected_location_id !== identity.selectedLocationId ||
    typeof body.authorization_epoch !== 'string' ||
    !/^[A-Za-z0-9_-]{43}$/.test(body.authorization_epoch) ||
    (identity.expectedAuthorizationEpoch !== undefined &&
      body.authorization_epoch !== identity.expectedAuthorizationEpoch) ||
    !Array.isArray(body.capabilities) ||
    body.capabilities.some(
      (grant) =>
        typeof grant !== 'string' || !/^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$/.test(grant),
    )
  )
    return reject()
  const context: VerifiedAccessContext = {
    protocol: 1,
    principal: Object.freeze({
      apiRealm: identity.apiRealm,
      organizationId: principal.organization_id,
      userId: principal.user_id,
    }),
    accountLocationId: body.account_location_id,
    selectedLocationId: body.selected_location_id,
    capabilities: Object.freeze([...body.capabilities] as string[]),
    authorizationEpoch: body.authorization_epoch,
    policyRevision: body.policy_revision,
    datasetIncarnation: body.dataset_incarnation,
    verifiedAt: instant(body.verified_at),
    offlineUntil: instant(body.offline_until),
    snapshotProtocol: body.snapshot_protocol,
  }
  validateVerifiedContext(context, now)
  return Object.freeze(context)
}

/** Isolated transport prerequisite. Does not write storage or activate a kernel. */
export function createServerContextAdapter(options: ServerContextAdapterOptions) {
  const realm = canonicalRealm(options.apiRealm)
  const fetchContext = options.fetch
  const clock = options.now
  let sequence = 0
  return Object.freeze({
    /** Invalidate pending work on logout, context changes or disposal. */
    invalidate() {
      sequence += 1
    },
    async verify(request: ContextVerificationRequest): Promise<
      Readonly<{
        state: 'BASELINE_REQUIRED'
        context: VerifiedAccessContext
        identity: Readonly<ContextRequestIdentity>
      }>
    > {
      const attempt = ++sequence
      // Capture before any await; never consult a mutable token provider later.
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
      const token = request.bearerToken
      const isCurrent = request.isCurrent
      const current = () => attempt === sequence && isCurrent(identity)
      try {
        const started = clock()
        if (
          identity.apiRealm !== realm ||
          !id(identity.organizationId) ||
          !id(identity.userId) ||
          !id(identity.selectedLocationId) ||
          !Number.isSafeInteger(identity.deviceGeneration) ||
          identity.deviceGeneration < 0 ||
          !identity.tabAttemptId ||
          !identity.sessionHandle ||
          !Number.isFinite(started) ||
          typeof token !== 'string' ||
          !token ||
          /\s/.test(token) ||
          !current()
        )
          return reject()
        const url = new URL(`${realm}/auth/context`)
        url.searchParams.set('selected_location_id', identity.selectedLocationId)
        const response = await fetchContext(url.href, {
          method: 'GET',
          headers: { Authorization: `Bearer ${token}`, Accept: 'application/json' },
          cache: 'no-store',
          redirect: 'error',
          credentials: 'omit',
          referrerPolicy: 'no-referrer',
        })
        if (
          !current() ||
          !response.ok ||
          response.redirected ||
          response.url !== url.href ||
          !response.headers
            .get('cache-control')
            ?.split(',')
            .some((part) => part.trim().toLowerCase() === 'no-store') ||
          response.headers.get('content-type')?.split(';')[0]?.trim().toLowerCase() !==
            'application/json'
        )
          return reject()
        const body: unknown = await response.json()
        const finished = clock()
        if (!current() || !Number.isFinite(finished) || finished < started) return reject()
        const context = convertServerContext(body, identity, finished)
        return Object.freeze({ state: 'BASELINE_REQUIRED', context, identity })
      } catch {
        return reject()
      }
    },
  })
}

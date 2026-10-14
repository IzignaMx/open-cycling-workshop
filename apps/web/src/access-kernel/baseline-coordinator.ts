import { canonicalJson } from './operations.js'
import type { AccessKernel } from './kernel.js'
import type { ContextRequestIdentity } from './server-context.js'
import type { ContextTicket, VerifiedAccessContext } from './types.js'
import { BaselineTransportError, type createBaselineTransport } from './baseline-transport.js'
import { convertBaselineContext } from './baseline-wire.js'

export interface BaselineSession {
  ticket: ContextTicket
  context: VerifiedAccessContext
  identity: ContextRequestIdentity
  bearerToken: string
  isCurrent: (identity: Readonly<ContextRequestIdentity>) => boolean
}
export interface BaselineCoordinatorOptions {
  kernel: AccessKernel
  transport: ReturnType<typeof createBaselineTransport>
  now(): number
  random(): number
  online(): boolean
}
export interface BaselineOutcome {
  state: 'BASELINE_REQUIRED' | 'PROGRESSED' | 'READY' | 'HELD' | 'OFFLINE' | 'RETRY_LATER'
  ticket: ContextTicket
  reason?: string
  retryAt?: number
}
/** One bounded HTTP step per call. Scheduling is explicit; no timers or hidden loops.
 * Null-advertised contexts cannot enter this ordinary coordinator.
 */
export function createBaselineCoordinator(options: BaselineCoordinatorOptions) {
  let sequence = 0
  let disabledTicket: string | null = null
  const capture = (source: BaselineSession) => {
    const identity: ContextRequestIdentity = Object.freeze({
      apiRealm: source.identity.apiRealm,
      organizationId: source.identity.organizationId,
      userId: source.identity.userId,
      selectedLocationId: source.identity.selectedLocationId,
      deviceGeneration: source.identity.deviceGeneration,
      tabAttemptId: source.identity.tabAttemptId,
      sessionHandle: source.identity.sessionHandle,
      ...(source.identity.expectedAuthorizationEpoch === undefined
        ? {}
        : { expectedAuthorizationEpoch: source.identity.expectedAuthorizationEpoch }),
    })
    const check = source.isCurrent
    const attempt = ++sequence
    return {
      ticket: structuredClone(source.ticket),
      context: structuredClone(source.context),
      identity,
      bearerToken: source.bearerToken,
      current: () => {
        try {
          return attempt === sequence && check(identity)
        } catch {
          return false
        }
      },
    }
  }
  type Captured = ReturnType<typeof capture>
  const result = (
    captured: Captured,
    state: BaselineOutcome['state'],
    extra: Omit<BaselineOutcome, 'state' | 'ticket'> = {},
  ): BaselineOutcome => ({ state, ticket: structuredClone(captured.ticket), ...extra })
  async function step(captured: Captured): Promise<BaselineOutcome> {
    if (captured.context.snapshotProtocol !== 'baseline-v1')
      return result(captured, 'BASELINE_REQUIRED')
    if (!captured.current()) return result(captured, 'HELD', { reason: 'stale_request' })
    if (disabledTicket === canonicalJson(captured.ticket))
      return result(captured, 'HELD', { reason: 'verification_required' })
    if (!options.online()) return result(captured, 'OFFLINE')
    let pending
    try {
      pending = await options.kernel.pendingBaseline(captured.ticket)
    } catch {
      return result(captured, 'HELD', { reason: 'verification_required' })
    }
    if (!captured.current()) return result(captured, 'HELD', { reason: 'stale_request' })
    const { baseline } = pending
    const request = baseline.next
    if (!request) return result(captured, baseline.phase === 'active' ? 'READY' : 'HELD')
    if (baseline.hold) {
      if (baseline.hold.retryAt === null)
        return result(captured, 'HELD', { reason: baseline.hold.reason })
      if (baseline.hold.retryAt > options.now())
        return result(captured, 'RETRY_LATER', {
          reason: baseline.hold.reason,
          retryAt: baseline.hold.retryAt,
        })
      try {
        await options.kernel.retryBaseline(captured.ticket, request)
      } catch {
        return result(captured, 'HELD', { reason: 'verification_required' })
      }
    }
    try {
      if (!captured.current()) return result(captured, 'HELD', { reason: 'stale_request' })
      const body = JSON.parse(request.body) as { continuation?: string; checkpoint?: string }
      const response = await options.transport.request({
        kind: request.kind,
        body: request.body,
        identity: captured.identity,
        bearerToken: captured.bearerToken,
        isCurrent: captured.current,
        binding: {
          context: pending.context,
          identity: captured.identity,
          ...(baseline.baselineId ? { baselineId: baseline.baselineId } : {}),
          ...(body.continuation ? { predecessor: body.continuation } : {}),
          ...(body.checkpoint ? { checkpoint: body.checkpoint } : {}),
        },
      })
      if (!captured.current()) return result(captured, 'HELD', { reason: 'stale_request' })
      if (request.kind === 'activation') {
        // Require the exact closed server context again at activation.
        // Never overwrite a null advertisement with baseline-v1.
        if (!('context' in response)) throw new Error('Invalid activation response')
        const fresh = convertBaselineContext(response.context, captured.identity, options.now())
        await options.kernel.activateBaseline(
          captured.ticket,
          body.checkpoint!,
          fresh,
          captured.current,
        )
        return result(captured, 'READY')
      }
      await options.kernel.commitBaselinePage(
        captured.ticket,
        request,
        response,
        captured.identity,
        captured.current,
      )
      return result(captured, 'PROGRESSED')
    } catch (error) {
      if (!captured.current()) return result(captured, 'HELD', { reason: 'stale_request' })
      const storageCode =
        error instanceof DOMException || error instanceof Error
          ? error.name === 'QuotaExceededError'
            ? 'storage_full'
            : error.name === 'AbortError'
              ? 'storage_aborted'
              : null
          : null
      const code =
        error instanceof BaselineTransportError ? error.code : (storageCode ?? 'invalid_response')
      const transient = [
        'network_error',
        'baseline_in_progress',
        'baseline_capacity',
        'temporary_unavailable',
      ].includes(code)
      const retry = transient && baseline.retryCount < 7
      const random = options.random(),
        now = options.now()
      const delay =
        Math.min(300_000, 1000 * 2 ** baseline.retryCount) *
        (1 + (Number.isFinite(random) ? Math.min(1, Math.max(0, random)) : 0))
      const retryAt =
        retry && Number.isFinite(now)
          ? now +
            Math.max(delay, error instanceof BaselineTransportError ? (error.retryAfterMs ?? 0) : 0)
          : null
      const reason = transient && !retry ? 'retry_exhausted' : code
      try {
        const held = await options.kernel.holdBaseline(
          captured.ticket,
          request,
          reason,
          retryAt,
          captured.current,
        )
        if (!held) return result(captured, 'HELD', { reason: 'stale_request' })
      } catch {
        if (!captured.current()) return result(captured, 'HELD', { reason: 'stale_request' })
        disabledTicket = canonicalJson(captured.ticket)
        options.kernel.disableBaselineSession(captured.ticket, captured.current)
        return result(captured, 'HELD', { reason: 'storage_or_fence_failure' })
      }
      return retryAt === null
        ? result(captured, 'HELD', { reason })
        : result(captured, 'RETRY_LATER', { reason, retryAt })
    }
  }
  return Object.freeze({
    invalidate() {
      sequence += 1
      options.transport.invalidate()
    },
    async start(source: BaselineSession): Promise<BaselineOutcome> {
      const captured = capture(source)
      if (captured.context.snapshotProtocol !== 'baseline-v1')
        return result(captured, 'BASELINE_REQUIRED')
      if (!captured.current()) return result(captured, 'HELD', { reason: 'stale_request' })
      if (disabledTicket === canonicalJson(captured.ticket))
        return result(captured, 'HELD', { reason: 'verification_required' })
      if (!options.online()) return result(captured, 'OFFLINE')
      try {
        captured.ticket = await options.kernel.beginBaseline(captured.ticket)
      } catch {
        return result(captured, 'HELD', { reason: 'storage_or_fence_failure' })
      }
      return step(captured)
    },
    async resume(source: BaselineSession): Promise<BaselineOutcome> {
      const captured = capture(source)
      if (captured.context.snapshotProtocol !== 'baseline-v1')
        return result(captured, 'BASELINE_REQUIRED')
      if (!captured.current()) return result(captured, 'HELD', { reason: 'stale_request' })
      if (disabledTicket === canonicalJson(captured.ticket))
        return result(captured, 'HELD', { reason: 'verification_required' })
      try {
        await options.kernel.resumeBaseline(captured.ticket)
      } catch {
        return result(captured, 'HELD', { reason: 'fresh_baseline_required' })
      }
      return step(captured)
    },
    step(source: BaselineSession) {
      return step(capture(source))
    },
  })
}

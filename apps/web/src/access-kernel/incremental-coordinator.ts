import { canonicalJson } from './operations.js'
import { retryPlan } from '../sync/retry-policy.js'
import type { IncrementalMetadata, IncrementalRequest } from './incremental-state.js'
import type { BaselineSession } from './baseline-coordinator.js'
import type { ContextRequestIdentity } from './server-context.js'
import type { ContextTicket, VerifiedAccessContext } from './types.js'
import {
  IncrementalTransportError,
  type createIncrementalTransport,
} from './incremental-transport.js'

export interface IncrementalKernel {
  pendingIncremental(
    ticket: ContextTicket,
    current?: () => boolean,
  ): Promise<{ incremental: IncrementalMetadata; context: VerifiedAccessContext }>
  commitIncrementalPage(
    ticket: ContextTicket,
    request: IncrementalRequest,
    response: unknown,
    identity: ContextRequestIdentity,
    current?: () => boolean,
  ): Promise<'committed' | 'replayed'>
  retryIncremental(
    ticket: ContextTicket,
    request: IncrementalRequest,
    current?: () => boolean,
  ): Promise<void>
  holdIncremental(
    ticket: ContextTicket,
    request: IncrementalRequest,
    reason: string,
    retryAt: number | null,
    current?: () => boolean,
  ): Promise<boolean>
  disableIncrementalSession(ticket: ContextTicket, current?: () => boolean): void
}
export interface IncrementalCoordinatorOptions {
  kernel: IncrementalKernel
  transport: ReturnType<typeof createIncrementalTransport>
  now(): number
  random(): number
  online(): boolean
}
export interface IncrementalOutcome {
  state: 'BASELINE_REQUIRED' | 'PROGRESSED' | 'READY' | 'HELD' | 'OFFLINE' | 'RETRY_LATER'
  ticket: ContextTicket
  reason?: string
  retryAt?: number
}
/** One bounded HTTP step per call. Scheduling is explicit; no timers or hidden loops.
 * Null-advertised contexts cannot enter this ordinary coordinator.
 */
export function createIncrementalCoordinator(options: IncrementalCoordinatorOptions) {
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
    state: IncrementalOutcome['state'],
    extra: Omit<IncrementalOutcome, 'state' | 'ticket'> = {},
  ): IncrementalOutcome => ({ state, ticket: structuredClone(captured.ticket), ...extra })
  async function step(captured: Captured): Promise<IncrementalOutcome> {
    if (captured.context.snapshotProtocol !== 'baseline-v1')
      return result(captured, 'BASELINE_REQUIRED')
    if (!captured.current()) return result(captured, 'HELD', { reason: 'stale_request' })
    if (disabledTicket === canonicalJson(captured.ticket))
      return result(captured, 'HELD', { reason: 'verification_required' })
    if (!options.online()) return result(captured, 'OFFLINE')
    let pending
    try {
      pending = await options.kernel.pendingIncremental(captured.ticket, captured.current)
    } catch {
      return result(captured, 'HELD', {
        reason: captured.current() ? 'verification_required' : 'stale_request',
      })
    }
    if (!captured.current()) return result(captured, 'HELD', { reason: 'stale_request' })
    const { incremental } = pending
    const request = incremental.next
    if (incremental.hold) {
      if (incremental.hold.retryAt === null)
        return result(captured, 'HELD', { reason: incremental.hold.reason })
      if (incremental.hold.retryAt > options.now())
        return result(captured, 'RETRY_LATER', {
          reason: incremental.hold.reason,
          retryAt: incremental.hold.retryAt,
        })
      try {
        await options.kernel.retryIncremental(captured.ticket, request, captured.current)
      } catch {
        return result(captured, 'HELD', {
          reason: captured.current() ? 'verification_required' : 'stale_request',
        })
      }
    }
    try {
      if (!captured.current()) return result(captured, 'HELD', { reason: 'stale_request' })
      const body = JSON.parse(request.body) as { continuation: string }
      const response = await options.transport.request({
        body: request.body,
        identity: captured.identity,
        bearerToken: captured.bearerToken,
        isCurrent: captured.current,
        binding: {
          context: pending.context,
          predecessor: body.continuation,
        },
      })
      if (!captured.current()) return result(captured, 'HELD', { reason: 'stale_request' })
      await options.kernel.commitIncrementalPage(
        captured.ticket,
        request,
        response,
        captured.identity,
        captured.current,
      )
      if (!captured.current()) return result(captured, 'HELD', { reason: 'stale_request' })
      return result(captured, response.phase === 'complete' ? 'READY' : 'PROGRESSED')
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
        error instanceof IncrementalTransportError
          ? error.code
          : (storageCode ?? 'invalid_response')
      const transient = [
        'network_error',
        'baseline_in_progress',
        'baseline_capacity',
        'temporary_unavailable',
      ].includes(code)
      const plan = retryPlan(incremental.retryCount + 1)
      const retry = transient && !plan.exhausted
      const random = options.random(),
        now = options.now()
      const delay = Math.min(
        30_000,
        Math.ceil(
          plan.delayMs * (1 + (Number.isFinite(random) ? Math.min(1, Math.max(0, random)) : 0)),
        ),
      )
      const duration = Math.max(
        delay,
        error instanceof IncrementalTransportError ? (error.retryAfterMs ?? 0) : 0,
      )
      const retryAt = retry && Number.isSafeInteger(now + duration) ? now + duration : null
      const reason = transient && !retry ? 'retry_exhausted' : code
      try {
        const held = await options.kernel.holdIncremental(
          captured.ticket,
          request,
          reason,
          retryAt,
          captured.current,
        )
        if (!held || !captured.current())
          return result(captured, 'HELD', { reason: 'stale_request' })
      } catch {
        if (!captured.current()) return result(captured, 'HELD', { reason: 'stale_request' })
        disabledTicket = canonicalJson(captured.ticket)
        options.kernel.disableIncrementalSession(captured.ticket, captured.current)
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
    step(source: BaselineSession) {
      return step(capture(source))
    },
  })
}

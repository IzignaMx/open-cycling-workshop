import type { BaselineSession } from './baseline-coordinator.js'
import type { ContextTicket, DispatchBatch } from './types.js'
import type { PushResponse } from '../sync/types.js'
import { PushTransportError, type createPushTransport } from './push-transport.js'

interface PushKernel {
  listDispatchable(
    ticket: ContextTicket,
    limit: number,
    current: () => boolean,
  ): Promise<DispatchBatch>
  applyPushResult(
    ticket: ContextTicket,
    batch: DispatchBatch,
    response: PushResponse,
    current: () => boolean,
  ): Promise<void>
  deferDispatch(
    ticket: ContextTicket,
    batch: DispatchBatch,
    reason:
      'transient' | 'unauthorized' | 'forbidden' | 'upgrade' | 'context_changed' | 'integrity',
    current: () => boolean,
  ): Promise<void>
  disableBaselineSession(ticket: ContextTicket, current: () => boolean): void
}
export function createPushCoordinator(options: {
  kernel: PushKernel
  transport: ReturnType<typeof createPushTransport>
}) {
  let sequence = 0
  return Object.freeze({
    invalidate() {
      sequence++
      options.transport.invalidate()
    },
    async step(source: BaselineSession): Promise<{
      state: 'IDLE' | 'APPLIED' | 'RETRY_LATER' | 'HELD'
      reason?: string
      count?: number
    }> {
      // Capture the credential synchronously, before durable dispatch selection.
      const call = ++sequence,
        identity = structuredClone(source.identity),
        ticket = structuredClone(source.ticket),
        context = structuredClone(source.context),
        bearerToken = source.bearerToken,
        check = source.isCurrent
      const current = () => {
        try {
          return call === sequence && check(identity)
        } catch {
          return false
        }
      }
      if (!current()) return { state: 'HELD', reason: 'stale_request' }
      let batch: DispatchBatch
      try {
        batch = structuredClone(await options.kernel.listDispatchable(ticket, 50, current))
      } catch {
        return { state: 'HELD', reason: current() ? 'verification_required' : 'stale_request' }
      }
      if (!current()) return { state: 'HELD', reason: 'stale_request' }
      if (batch.operations.length === 0) return { state: 'IDLE' }
      try {
        const response = await options.transport.push({
          identity,
          ticket,
          context,
          bearerToken,
          isCurrent: current,
          batch,
        })
        if (!current()) return { state: 'HELD', reason: 'stale_request' }
        await options.kernel.applyPushResult(ticket, batch, response, current)
        if (!current()) return { state: 'HELD', reason: 'stale_request' }
        return { state: 'APPLIED', count: response.results.length }
      } catch (error) {
        if (!current()) return { state: 'HELD', reason: 'stale_request' }
        const code = error instanceof PushTransportError ? error.code : 'storage_or_fence_failure'
        const reason =
          code === 'network_error' || code === 'temporary_unavailable'
            ? 'transient'
            : code === 'invalid_session'
              ? 'unauthorized'
              : code === 'capability_denied'
                ? 'forbidden'
                : code === 'client_upgrade_required'
                  ? 'upgrade'
                  : code === 'authorization_context_changed'
                    ? 'context_changed'
                    : 'integrity'
        try {
          await options.kernel.deferDispatch(ticket, batch, reason, current)
        } catch {
          options.kernel.disableBaselineSession(ticket, current)
          return { state: 'HELD', reason: 'storage_or_fence_failure' }
        }
        if (!current()) return { state: 'HELD', reason: 'stale_request' }
        if (reason !== 'transient') options.kernel.disableBaselineSession(ticket, current)
        return { state: reason === 'transient' ? 'RETRY_LATER' : 'HELD', reason: code }
      }
    },
  })
}

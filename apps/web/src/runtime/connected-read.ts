import { cancelResponse, readBoundedJson } from '../access-kernel/bounded-http.js'
import { contextKey } from '../access-kernel/context.js'
import {
  convertServerContext,
  type ContextRequestIdentity,
} from '../access-kernel/server-context.js'
import type { VerifiedAccessContext } from '../access-kernel/types.js'
import type { AccountCapture } from './account-access.js'

export interface ConnectedReadSnapshot {
  phase: 'unverified' | 'verifying' | 'ready' | 'unavailable'
  context: VerifiedAccessContext | null
  generation: number
  message: string | null
}
export interface ConnectedReadCapture extends AccountCapture {
  readonly context: VerifiedAccessContext
  readonly generation: number
}
export interface ConnectedReadAccess {
  getSnapshot(): ConnectedReadSnapshot
  subscribe(listener: () => void): () => void
  verify(locationId?: string): Promise<void>
  capture(): ConnectedReadCapture
  check(): Promise<void>
  refuse(capture: ConnectedReadCapture, status: 401 | 403): void
  clear(): void
}

/** Runtime-owned routing and actual owner inspection; never creates a kernel owner. */
interface ConnectedReadSource {
  readonly account: AccountCapture
  readonly locationId: string
  readonly operationalContext: VerifiedAccessContext | null
  inspect(): Promise<void>
}
interface ConnectedReadOptions {
  fetch: typeof fetch
  now(): number
  source(locationId?: string): ConnectedReadSource
  refused(account: AccountCapture, status: 401 | 403): void
}
const unavailable = 'No se pudo verificar el acceso conectado. Verifica la cuenta y el taller.'
const expired = 'El acceso conectado venció o cambió. Verifica nuevamente antes de continuar.'

/** Volatile fresh-read authority only. No persistence, baseline or offline admission. */
export function createConnectedReadAccess(options: ConnectedReadOptions): ConnectedReadAccess {
  const fetchContext = options.fetch.bind(globalThis)
  const listeners = new Set<() => void>()
  const handles = new WeakSet<ConnectedReadCapture>()
  let snapshot: ConnectedReadSnapshot = Object.freeze({
    phase: 'unverified',
    context: null,
    generation: 0,
    message: null,
  })
  let source: ConnectedReadSource | null = null
  let abort = new AbortController()
  let observedAt = 0
  let requestUntil: number | null = null
  let leaseTimer: ReturnType<typeof setTimeout> | undefined
  const publish = (
    phase: ConnectedReadSnapshot['phase'],
    context: VerifiedAccessContext | null,
    message: string | null,
  ) => {
    snapshot = Object.freeze({ phase, context, generation: snapshot.generation, message })
    for (const listener of listeners) listener()
  }
  const reset = (phase: 'unverified' | 'unavailable', message: string | null) => {
    const old = abort
    abort = new AbortController()
    source = null
    requestUntil = null
    if (leaseTimer !== undefined) clearTimeout(leaseTimer)
    leaseTimer = undefined
    snapshot = Object.freeze({ phase, context: null, generation: snapshot.generation + 1, message })
    old.abort()
    for (const listener of listeners) listener()
  }
  const valid = (
    generation: number,
    captured: ConnectedReadSource,
    signal: AbortSignal,
  ): boolean => {
    if (generation !== snapshot.generation || source !== captured || signal.aborted) return false
    const now = options.now()
    if (
      !captured.account.isCurrent() ||
      !Number.isFinite(now) ||
      now < observedAt ||
      (requestUntil !== null && now >= requestUntil) ||
      (snapshot.context !== null && now >= Date.parse(snapshot.context.offlineUntil)) ||
      (captured.operationalContext !== null &&
        now >= Date.parse(captured.operationalContext.offlineUntil))
    ) {
      reset('unavailable', expired)
      return false
    }
    observedAt = now
    return true
  }
  const refuseSource = (
    captured: ConnectedReadSource,
    generation: number,
    signal: AbortSignal,
    status: 401 | 403,
  ) => {
    if (!valid(generation, captured, signal)) return
    // Invalidate the protected view before any caller could start another request.
    reset(
      'unavailable',
      status === 401 ? 'La sesión no es válida. Inicia sesión nuevamente.' : unavailable,
    )
    options.refused(captured.account, status)
  }
  const access: ConnectedReadAccess = {
    getSnapshot: () => snapshot,
    subscribe(listener) {
      listeners.add(listener)
      return () => {
        listeners.delete(listener)
      }
    },
    clear() {
      reset('unverified', null)
    },
    async verify(locationId) {
      const previousExpiry = snapshot.context ? Date.parse(snapshot.context.offlineUntil) : Infinity
      reset('unverified', null)
      const generation = snapshot.generation,
        signal = abort.signal,
        flight = abort
      let captured: ConnectedReadSource
      try {
        captured = options.source(locationId)
      } catch {
        publish(
          'unavailable',
          null,
          'Verifica la cuenta y selecciona un taller autorizado para consultar información conectada.',
        )
        return
      }
      source = captured
      observedAt = options.now()
      if (!valid(generation, captured, signal)) return
      const started = observedAt
      // These are metadata request identifiers, not a ContextTicket or durable lease owner.
      const identity: Readonly<ContextRequestIdentity> = Object.freeze({
        apiRealm: captured.account.apiRealm,
        organizationId: captured.account.user.organization_id,
        userId: captured.account.user.user_id,
        selectedLocationId: captured.locationId,
        deviceGeneration: generation,
        tabAttemptId: crypto.randomUUID(),
        sessionHandle: crypto.randomUUID(),
      })
      const current = () => valid(generation, captured, signal)
      const url = new URL(`${identity.apiRealm}/auth/context`)
      url.searchParams.set('selected_location_id', identity.selectedLocationId)
      const deadline = Math.min(
        10000,
        previousExpiry > started ? previousExpiry - started : Infinity,
        captured.operationalContext
          ? Date.parse(captured.operationalContext.offlineUntil) - started
          : Infinity,
      )
      requestUntil = started + deadline
      let timer: ReturnType<typeof setTimeout> | undefined
      let onAbort: (() => void) | undefined
      publish('verifying', null, null)
      try {
        if (!current() || deadline <= 0) throw new Error(unavailable)
        const request = async () => {
          await captured.inspect()
          if (!current()) throw new Error(unavailable)
          const response = await fetchContext(url.href, {
            method: 'GET',
            signal,
            headers: {
              Authorization: `Bearer ${captured.account.token}`,
              Accept: 'application/json',
            },
            cache: 'no-store',
            redirect: 'error',
            credentials: 'omit',
            referrerPolicy: 'no-referrer',
          })
          if (!current()) {
            void cancelResponse(response)
            throw new Error(unavailable)
          }
          // A current refusal wins even if headers are absent or its body never ends.
          if (response.status === 401 || response.status === 403) {
            void cancelResponse(response)
            refuseSource(captured, generation, signal, response.status)
            throw new Error(unavailable)
          }
          if (
            response.status !== 200 ||
            response.redirected ||
            response.url !== url.href ||
            response.headers.get('content-type')?.split(';')[0]?.trim().toLowerCase() !==
              'application/json' ||
            !response.headers
              .get('cache-control')
              ?.split(',')
              .some((value) => value.trim().toLowerCase() === 'no-store')
          ) {
            void cancelResponse(response)
            throw new Error(unavailable)
          }
          const body = await readBoundedJson(response, 16384, signal)
          if (!current()) throw new Error(unavailable)
          const context = convertServerContext(body, identity, options.now())
          if (
            context.accountLocationId !== captured.account.user.location_id ||
            JSON.stringify([...context.capabilities].sort()) !==
              JSON.stringify([...captured.account.user.capabilities].sort()) ||
            (captured.operationalContext &&
              contextKey(context) !== contextKey(captured.operationalContext))
          ) {
            refuseSource(captured, generation, signal, 403)
            throw new Error(unavailable)
          }
          await captured.inspect()
          if (!current()) throw new Error(unavailable)
          return context
        }
        const context = await Promise.race([
          request(),
          new Promise<never>((_, reject) => {
            onAbort = () => reject(new Error(unavailable))
            signal.addEventListener('abort', onAbort, { once: true })
            if (signal.aborted) onAbort()
            timer = setTimeout(() => {
              if (generation === snapshot.generation) reset('unavailable', unavailable)
              flight.abort()
              reject(new Error(unavailable))
            }, deadline)
          }),
        ])
        if (!current()) return
        const now = options.now(),
          until = Date.parse(context.offlineUntil)
        if (!Number.isFinite(now) || now < observedAt || until <= now) throw new Error(unavailable)
        observedAt = now
        requestUntil = null
        publish('ready', context, null)
        if (!current()) return
        leaseTimer = setTimeout(
          () => {
            if (generation === snapshot.generation) reset('unavailable', expired)
          },
          Math.max(0, until - now),
        )
      } catch {
        if (generation === snapshot.generation) reset('unavailable', unavailable)
      } finally {
        if (timer !== undefined) clearTimeout(timer)
        if (onAbort) signal.removeEventListener('abort', onAbort)
      }
    },
    capture() {
      const captured = source,
        generation = snapshot.generation,
        signal = abort.signal
      if (
        !captured ||
        snapshot.phase !== 'ready' ||
        !snapshot.context ||
        !valid(generation, captured, signal)
      )
        throw new Error(unavailable)
      const capture: ConnectedReadCapture = Object.freeze({
        token: captured.account.token,
        user: captured.account.user,
        apiRealm: captured.account.apiRealm,
        signal,
        context: snapshot.context,
        generation,
        isCurrent: () => valid(generation, captured, signal) && snapshot.phase === 'ready',
      })
      handles.add(capture)
      return capture
    },
    async check() {
      const captured = source,
        generation = snapshot.generation,
        signal = abort.signal
      if (!captured || !valid(generation, captured, signal)) return
      try {
        await captured.inspect()
        valid(generation, captured, signal)
      } catch {
        if (generation === snapshot.generation) reset('unavailable', unavailable)
      }
    },
    refuse(capture, status) {
      if (!handles.has(capture) || !capture.isCurrent() || !source) return
      refuseSource(source, capture.generation, capture.signal, status)
    },
  }
  return Object.freeze(access)
}

import { CustomerLookup, type CustomerLookupSnapshot } from './customer-lookup.js'
import { CaptureRecovery, type RecoveryAttempt } from './capture-recovery.js'
import { CaptureVisit, type CaptureVisitSnapshot, type CaptureVisitScope } from './capture-visit.js'
import { captureFeedback } from '../features/capture-feedback.js'
import { captureValidation } from './capture-outcome.js'
import { normalizeOrderIntake } from '../features/orders/order-model.js'
import type { CustomerDraftState, OrderDraftState } from '../features/draft-state.js'
import { TransitionProtection, type TransitionProtectionSnapshot } from './transition-protection.js'
import { orderTransitionFeedback } from '../features/orders/transition-feedback.js'
import type { CaptureSubmissionResult } from './capture-outcome.js'
import type { OrderTransitionResult } from './order-transition-outcome.js'
import { BrandingSnapshotRepository } from '../branding/cache.js'
import {
  BrandingDisplayController,
  type BrandingRuntimeCapture,
} from '../features/branding/runtime.js'
import { createBrandingTransport } from '../features/branding/transport.js'
import { liveQuery } from 'dexie'
import { AccessKernel } from '../access-kernel/kernel.js'
import { contextKey, principalKey } from '../access-kernel/context.js'
import { createKernelDatabase, type KernelDatabase } from '../access-kernel/database.js'
import { createServerContextAdapter } from '../access-kernel/server-context.js'
import { createBaselineTransport } from '../access-kernel/baseline-transport.js'
import {
  createBaselineCoordinator,
  type BaselineSession,
} from '../access-kernel/baseline-coordinator.js'
import { createIncrementalTransport } from '../access-kernel/incremental-transport.js'
import { createIncrementalCoordinator } from '../access-kernel/incremental-coordinator.js'
import { createPushTransport } from '../access-kernel/push-transport.js'
import { createPushCoordinator } from '../access-kernel/push-coordinator.js'
import type { ContextTicket, VerifiedAccessContext } from '../access-kernel/types.js'
import { SessionStore, type SessionSnapshot, type SessionUserSnapshot } from '../auth/session.js'
import type { LoginRequestPayload } from '../auth/login-model.js'
import { PreferenceRepository } from '../personalization/repository.js'
import { copyOwnedLegacyPreferences, inspectLegacyWork } from './legacy-preservation.js'
import { createRuntimeTransport, RuntimeHttpError, type WorkshopLocation } from './transport.js'
import { ReachabilityProbe, type ReachabilityResult } from './reachability-probe.js'
import { createConnectedReadAccess, type ConnectedReadAccess } from './connected-read.js'
import {
  sameAccountAuthority,
  type AccountAccessSnapshot,
  type AccountCapture,
  type AccountCommandOutcome,
} from './account-access.js'
import { WorkshopRepositories, type IntakeInput } from './repositories.js'
import type { LocalCustomer } from '../local/types.js'
import type { LocalServiceOrder, LocalServiceOrderEvent } from '../local/service-order-types.js'
import type { OrderAction } from '../features/orders/state-machine.js'

export interface RuntimeIssue {
  mutationId: string
  entityId: string
  entityType: string
  errorMessage: string | null
  state: string
  errorCode: string | null
}
export interface WorkshopSnapshot {
  phase: 'locked' | 'verifying' | 'selector' | 'baseline' | 'ready' | 'held'
  user: SessionUserSnapshot | null
  context: VerifiedAccessContext | null
  selectedLocationId: string | null
  message: string | null
  sync: 'local' | 'offline' | 'syncing' | 'synced' | 'conflict' | 'error'
  customerLookup: CustomerLookupSnapshot | null
  customers: LocalCustomer[]
  orders: LocalServiceOrder[]
  events: LocalServiceOrderEvent[]
  issues: RuntimeIssue[]
  locations: WorkshopLocation[]
  nextLocation: string | null
  customerAfter: string | null
  orderAfter: string | null
  issueAfter: number | null
  hasIssues: boolean
  hasPending: boolean
  nextRetryAt: number | null
  legacyPresent: boolean
  timelineMessage: string | null
  identityKey: string
  capture: CaptureVisitSnapshot | null
  captureRecoveryNotice: string | null
  transitionProtection: TransitionProtectionSnapshot
}
const empty = (): WorkshopSnapshot => ({
  phase: 'locked',
  capture: null,
  captureRecoveryNotice: null,
  user: null,
  context: null,
  selectedLocationId: null,
  message: null,
  sync: 'local',
  customerLookup: null,
  customers: [],
  orders: [],
  events: [],
  issues: [],
  locations: [],
  nextLocation: null,
  customerAfter: null,
  orderAfter: null,
  issueAfter: null,
  hasIssues: false,
  hasPending: false,
  nextRetryAt: null,
  legacyPresent: false,
  timelineMessage: null,
  identityKey: '',
  transitionProtection: Object.freeze({ states: new Map(), notice: null }),
})
const safeMessage = (reason: string) =>
  reason === 'client_upgrade_required'
    ? 'Este servidor requiere una actualización del cliente. El trabajo local se conserva.'
    : reason === 'offline_expired'
      ? 'El acceso sin conexión venció. Conéctate e inicia sesión para verificar tus permisos.'
      : reason === 'takeover'
        ? 'Este taller está abierto en otra pestaña. Inicia sesión aquí para retomarlo.'
        : reason === 'storage_or_fence_failure'
          ? 'No se pudo confirmar el almacenamiento local. El trabajo anterior se conserva.'
          : reason === 'recovery'
            ? 'Hay trabajo anterior a una recuperación del servidor. Se conserva sin reenviarlo.'
            : 'Se necesita verificar la sesión antes de continuar. El trabajo local se conserva.'
export interface RuntimeOptions {
  apiRealm: string
  storage: Storage
  fetch: typeof fetch
  online(): boolean
  now?(): number
  database?: KernelDatabase
  factory?: IDBFactory
}

/** The sole production owner of operational storage and session-bound repositories. */
export class WorkshopController {
  readonly database: KernelDatabase
  readonly kernel: AccessKernel
  readonly sessionStore: SessionStore
  readonly branding: BrandingDisplayController
  readonly connectedReads: ConnectedReadAccess
  readonly repositories: WorkshopRepositories
  #snapshot = empty()
  #listeners = new Set<() => void>()
  #account: AccountAccessSnapshot = Object.freeze({
    phase: 'unverified',
    user: null,
    generation: 0,
    message: null,
  })
  #accountListeners = new Set<() => void>()
  #accountAbort = new AbortController()
  #accountSaved: SessionSnapshot | null = null
  #accountSource: BaselineSession | null = null
  #accountSourceIdentity = ''
  #accountHandles = new WeakSet<AccountCapture>()
  #suspendedAccount: AccountCapture | null = null
  #accountFlight: AbortController | null = null
  #locationPage = 0
  #sessionGeneration = 0
  #locationsSessionGeneration = -1
  #locationsNetworkSequence = -1
  #disposed = false
  #sequence = 0
  readonly #customerLookup = new CustomerLookup(() => this.publish({}))
  readonly #captureVisit = new CaptureVisit()
  #captureSource: BaselineSession | null = null
  readonly #captureRecovery: CaptureRecovery
  #captureEnrollmentBinding: string | null = null
  readonly #transitionProtection = new TransitionProtection()
  #active: BaselineSession | null = null
  #working: BaselineSession | null = null
  #brandingAdmissionRefresh: BaselineSession | null = null
  #timer: ReturnType<typeof setTimeout> | null = null
  #leaseTimer: ReturnType<typeof setTimeout> | null = null
  #observedAt = 0
  #started = false
  #running = false
  #localSyncWake: { source: BaselineSession; networkSequence: number } | null = null
  #verifiedOnline = false
  #observedReachable = false
  #sessionSnapshots = new WeakMap<BaselineSession, { saved: SessionSnapshot }>()
  #networkSequence = 0
  #preferences: PreferenceRepository | null = null
  #observer: { unsubscribe(): void } | null = null
  readonly #now: () => number
  readonly #probe: ReachabilityProbe<SessionUserSnapshot>
  readonly #http: ReturnType<typeof createRuntimeTransport>
  readonly #context: ReturnType<typeof createServerContextAdapter>
  readonly #baseline: ReturnType<typeof createBaselineCoordinator>
  readonly #incremental: ReturnType<typeof createIncrementalCoordinator>
  readonly #push: ReturnType<typeof createPushCoordinator>
  constructor(private readonly options: RuntimeOptions) {
    this.#transitionProtection.startVisit()
    this.#now = options.now ?? Date.now
    this.#probe = new ReachabilityProbe({
      now: this.#now,
      set: (action, delay) => setTimeout(action, delay),
      clear: (handle) => clearTimeout(handle as ReturnType<typeof setTimeout>),
    })
    this.database = options.database ?? createKernelDatabase('ocwp-authenticated-v1')
    this.kernel = new AccessKernel(this.database, {
      now: this.#now,
      newId: () => crypto.randomUUID(),
    })
    // Observe session writes at the sole runtime owner, including same-token A→B→A.
    // Stored format and contents are unchanged; no connected-read metadata is persisted.
    this.sessionStore = new SessionStore({
      getItem: (key) => options.storage.getItem(key),
      setItem: (key, value) => {
        if (options.storage.getItem(key) !== value) {
          this.#sessionGeneration++
          this.connectedReads?.clear()
        }
        options.storage.setItem(key, value)
      },
      removeItem: (key) => {
        this.#sessionGeneration++
        this.connectedReads?.clear()
        options.storage.removeItem(key)
      },
    })
    this.#captureRecovery = new CaptureRecovery({
      kernel: this.kernel,
      db: this.database,
      storage: options.storage,
      now: this.#now,
      current: () => {
        const source = this.#captureSource
        if (!source || this.#active !== source || !source.isCurrent(source.identity)) return null
        return {
          ticket: source.ticket,
          scope: this.captureScope(source),
          source,
          isCurrent: () =>
            this.#captureSource === source &&
            this.#active === source &&
            source.isCurrent(source.identity),
        }
      },
      onLocalAdmissionComplete: (source) => {
        if (source === this.#captureSource && source === this.#active)
          this.branding.refreshOfflineAfterLocalActivity()
      },
      onChange: () => {
        if (!this.#disposed) this.publish({})
      },
    })
    this.repositories = new WorkshopRepositories(this.kernel, this.#now)
    this.#http = createRuntimeTransport(options)
    this.#context = createServerContextAdapter({ ...options, now: this.#now })
    const common = {
      kernel: this.kernel,
      now: this.#now,
      random: Math.random,
      online: () => this.#observedReachable || options.online(),
    }
    this.#baseline = createBaselineCoordinator({
      ...common,
      transport: createBaselineTransport({ ...options, now: this.#now }),
    })
    this.#incremental = createIncrementalCoordinator({
      ...common,
      transport: createIncrementalTransport({ ...options, now: this.#now }),
    })
    this.#push = createPushCoordinator({
      kernel: this.kernel,
      transport: createPushTransport({ ...options, now: this.#now }),
    })
    this.connectedReads = createConnectedReadAccess({
      fetch: options.fetch,
      now: this.#now,
      source: (selected) => {
        const account = this.captureAccount(),
          operational = this.#active
        if (['verifying', 'baseline'].includes(this.#snapshot.phase))
          throw new Error('Verifica el taller antes de continuar.')
        const location =
          selected ?? account.user.location_id ?? operational?.context.selectedLocationId
        if (
          !location ||
          (account.user.location_id !== null && account.user.location_id !== location)
        )
          throw new Error('Selecciona un taller autorizado.')
        if (
          operational &&
          (this.#snapshot.phase !== 'ready' || location !== operational.context.selectedLocationId)
        )
          throw new Error('El taller operativo cambió.')
        if (
          account.user.location_id === null &&
          !operational &&
          (!account.user.capabilities.includes('locations.read') ||
            this.#locationsSessionGeneration !== this.#sessionGeneration ||
            this.#locationsNetworkSequence !== this.#networkSequence ||
            !this.#snapshot.locations.some(
              (row) =>
                row.location_id === location &&
                row.organization_id === account.user.organization_id,
            ))
        )
          throw new Error('Selecciona un taller del directorio autorizado.')
        const expected = operational ? contextKey(operational.context) : null
        return Object.freeze({
          account,
          locationId: location,
          operationalContext: operational ? structuredClone(operational.context) : null,
          inspect: async () => {
            if (!account.isCurrent()) throw new Error('La cuenta cambió.')
            if (!operational) return
            try {
              const state = await this.kernel.inspectSession(operational.ticket, account.isCurrent)
              if (!account.isCurrent() || contextKey(state.context) !== expected)
                throw new Error('El contexto operativo cambió.')
            } catch {
              if (account.isCurrent()) this.held('verification_required')
              throw new Error('Verifica el taller antes de continuar.')
            }
          },
        })
      },
      refused: (account, status) => {
        if (!account.isCurrent()) return
        if (status === 401) this.invalidateAccount(account, 'invalid_session')
        else this.held('verification_required')
      },
    })
    this.branding = new BrandingDisplayController({
      capture: () => this.captureBranding(),
      validate: async (source) => {
        try {
          await this.kernel.inspectSession(source.ticket, source.isCurrent)
          return source.isCurrent()
        } catch {
          if (source.isCurrent()) this.held('verification_required')
          return false
        }
      },
      repository: new BrandingSnapshotRepository(this.database),
      transport: createBrandingTransport(options),
      now: this.#now,
      refused: (source, status) => {
        if (source.isCurrent()) {
          if (status === 401) void this.logout()
          else this.held('verification_required')
        }
      },
    })
  }
  private captureBranding(): BrandingRuntimeCapture | null {
    const source = this.#active
    if (
      !source ||
      this.#disposed ||
      this.#snapshot.phase !== 'ready' ||
      !source.context.capabilities.includes('branding.read') ||
      !source.isCurrent(source.identity)
    )
      return null
    const network = this.#networkSequence,
      online = this.#verifiedOnline
    const current = () =>
      !this.#disposed &&
      this.#active === source &&
      network === this.#networkSequence &&
      this.#snapshot.phase === 'ready' &&
      source.isCurrent(source.identity) &&
      this.#now() >= this.#observedAt &&
      this.#now() < Date.parse(source.context.offlineUntil)
    if (!current()) return null
    return Object.freeze({
      token: source.bearerToken,
      organizationId: source.context.principal.organizationId,
      locationId: source.context.selectedLocationId,
      datasetIncarnation: source.context.datasetIncarnation,
      ticket: structuredClone(source.ticket),
      context: structuredClone(source.context),
      online,
      binding: JSON.stringify([source.ticket, source.context, network, online]),
      isCurrent: current,
    })
  }
  getSnapshot = () => this.#snapshot
  getAccountSnapshot = () => this.#account
  subscribeAccount = (listener: () => void) => {
    this.#accountListeners.add(listener)
    return () => this.#accountListeners.delete(listener)
  }
  private publishAccount(
    phase: AccountAccessSnapshot['phase'],
    user: SessionUserSnapshot | null,
    message: string | null = null,
  ) {
    this.#account = Object.freeze({ phase, user, message, generation: this.#account.generation })
    for (const listener of this.#accountListeners) listener()
  }
  invalidateAccount(capture?: AccountCapture, reason?: string): void {
    if (capture && (!this.#accountHandles.has(capture) || !capture.isCurrent())) return
    this.#accountAbort.abort()
    this.#accountFlight?.abort()
    this.#accountAbort = new AbortController()
    this.#accountSaved = null
    this.#accountSource = null
    this.#suspendedAccount = null
    const message =
      !reason || reason === 'administration_closed'
        ? null
        : reason === 'owner_verification_required'
          ? 'Verifica la cuenta para confirmar la designación de propietario.'
          : reason === 'lock_failed'
            ? 'No se pudo bloquear el taller. No se envió la operación.'
            : reason === 'connection_verification_failed'
              ? 'No se pudo verificar la conexión. Inténtalo de nuevo.'
              : reason === 'invalid_session'
                ? 'La sesión no es válida. Inicia sesión nuevamente.'
                : 'Verifica la cuenta para confirmar tus permisos antes de continuar.'
    this.#account = Object.freeze({
      phase: 'unverified',
      user: null,
      generation: this.#account.generation + 1,
      message,
    })
    this.connectedReads.clear()
    for (const listener of this.#accountListeners) listener()
    if (reason === 'invalid_session') void this.logout()
  }
  invalidateBrandingAccount(capture: AccountCapture, status: 401 | 403): void {
    if (!this.#accountHandles.has(capture) || !capture.isCurrent()) return
    if (status === 401) this.invalidateAccount(capture, 'invalid_session')
    else this.held('verification_required')
  }
  private admitAccount(saved: SessionSnapshot) {
    if (
      !saved.user ||
      this.#disposed ||
      JSON.stringify(saved) !== JSON.stringify(this.sessionStore.getSnapshot()) ||
      (this.#active && !this.#active.isCurrent(this.#active.identity))
    )
      throw new Error('Se requiere verificar la cuenta.')
    this.#accountSaved = saved
    this.#accountSource = this.#active
    this.#accountSourceIdentity = this.#active
      ? JSON.stringify([this.#active.ticket, this.#active.context])
      : ''
    this.publishAccount('connected', saved.user)
  }
  captureAccount(): AccountCapture {
    const saved = this.#accountSaved
    if (this.#account.phase !== 'connected' || !saved?.user || this.#disposed)
      throw new Error('Se requiere verificar la cuenta.')
    const capture = this.makeAccountCapture(saved, false)
    if (!capture.isCurrent()) {
      this.invalidateAccount()
      throw new Error('La cuenta cambió. Verifica la sesión.')
    }
    return capture
  }
  private makeAccountCapture(saved: SessionSnapshot, suspended: boolean): AccountCapture {
    const sequence = this.#sequence,
      sessionGeneration = this.#sessionGeneration,
      network = this.#networkSequence,
      generation = this.#account.generation,
      abort = this.#accountAbort,
      source = this.#accountSource,
      identity = this.#accountSourceIdentity
    const capture: AccountCapture = Object.freeze({
      token: saved.token,
      user: saved.user!,
      apiRealm: this.options.apiRealm,
      signal: abort.signal,
      isCurrent: () =>
        !this.#disposed &&
        !abort.signal.aborted &&
        generation === this.#account.generation &&
        sessionGeneration === this.#sessionGeneration &&
        network === this.#networkSequence &&
        this.exactSession(sequence, saved) &&
        (suspended
          ? this.#suspendedAccount === capture && this.#account.phase === 'suspended'
          : this.#account.phase === 'connected' &&
            this.#active === source &&
            (!source ||
              (source.isCurrent(source.identity) &&
                JSON.stringify([source.ticket, source.context]) === identity))),
    })
    this.#accountHandles.add(capture)
    return capture
  }
  async verifyAccount(): Promise<void> {
    if (
      this.#disposed ||
      this.#accountFlight ||
      this.#account.phase === 'suspended' ||
      ['verifying', 'baseline'].includes(this.#snapshot.phase)
    )
      return
    const saved = this.sessionStore.getSnapshot()
    if (!saved) {
      this.invalidateAccount()
      return
    }
    const operational = this.#active
    if (operational && !operational.isCurrent(operational.identity)) {
      this.held('verification_required')
      return
    }
    const operationalIdentity = operational
      ? JSON.stringify([operational.ticket, operational.context])
      : ''
    this.invalidateAccount()
    this.publishAccount('verifying', null)
    const sequence = this.#sequence,
      network = this.#networkSequence,
      generation = this.#account.generation,
      sessionGeneration = this.#sessionGeneration
    const flight = new AbortController()
    this.#accountFlight = flight
    const current = () =>
      !this.#disposed &&
      !flight.signal.aborted &&
      generation === this.#account.generation &&
      sessionGeneration === this.#sessionGeneration &&
      network === this.#networkSequence &&
      this.exactSession(sequence, saved) &&
      this.#active === operational &&
      (!operational ||
        (operational.isCurrent(operational.identity) &&
          JSON.stringify([operational.ticket, operational.context]) === operationalIdentity))
    let timer: ReturnType<typeof setTimeout> | undefined
    const request = this.#http.me({ token: saved.token, signal: flight.signal, isCurrent: current })
    // Keep request ownership until even an abort-ignoring transport settles.
    void request
      .finally(() => {
        if (this.#accountFlight === flight) this.#accountFlight = null
      })
      .catch(() => undefined)
    try {
      const user = await Promise.race([
        request,
        new Promise<never>((_, reject) => {
          timer = setTimeout(() => {
            if (current()) this.invalidateAccount(undefined, 'connection_verification_failed')
            flight.abort()
            reject(new RuntimeHttpError('network_error'))
          }, 10000)
        }),
      ])
      if (!current()) return
      if (operational) {
        await this.kernel.inspectSession(operational.ticket, current)
        if (!current()) return
      }
      if (
        saved.user &&
        (user.user_id !== saved.user.user_id || user.organization_id !== saved.user.organization_id)
      ) {
        await this.logout()
        return
      }
      if (saved.user && !sameAccountAuthority(saved.user, user)) {
        const source = this.#active ?? this.#working
        const next = this.blank(
          'held',
          'Los permisos cambiaron. Verifica el taller antes de abrirlo.',
        )
        const nextNetwork = this.#networkSequence,
          nextAdmission = this.#account.generation,
          nextSession = this.#sessionGeneration
        if (source) await this.kernel.lockContext(source.ticket)
        if (
          !this.exactSession(next, saved) ||
          this.#disposed ||
          nextNetwork !== this.#networkSequence ||
          nextAdmission !== this.#account.generation ||
          nextSession !== this.#sessionGeneration
        )
          return
        // A changed authority cannot carry an older durable offline admission.
        this.maskCapture()
        this.#captureRecovery.close()
        this.sessionStore.clear()
        this.sessionStore.setToken(saved.token)
        this.sessionStore.setUser(user)
        this.admitAccount(this.sessionStore.getSnapshot()!)
        return
      }
      this.sessionStore.setUser(user)
      this.sessionStore.bindVerifiedSession(saved.token)
      const updated = this.sessionStore.getSnapshot()!
      const source = this.#active
      if (source) this.#sessionSnapshots.get(source)!.saved = updated
      if (this.#snapshot.user) this.publish({ user: updated.user })
      this.admitAccount(updated)
    } catch (error) {
      if (current()) {
        if (error instanceof RuntimeHttpError && error.code === 'invalid_session')
          await this.logout()
        else if (operational && !(error instanceof RuntimeHttpError))
          this.held('storage_or_fence_failure')
        else this.invalidateAccount(undefined, 'authority_verification_required')
      }
    } finally {
      if (timer !== undefined) clearTimeout(timer)
      if (
        sequence === this.#sequence &&
        operational &&
        this.#active === operational &&
        !operational.isCurrent(operational.identity)
      )
        this.held('verification_required')
      if (generation === this.#account.generation && this.#account.phase === 'verifying')
        this.invalidateAccount()
    }
  }
  async suspendAccountCommand(capture: AccountCapture): Promise<AccountCapture> {
    if (
      !this.#accountHandles.has(capture) ||
      !capture.isCurrent() ||
      this.#account.phase !== 'connected'
    )
      throw new Error('La cuenta cambió. Verifica la sesión.')
    const saved = this.#accountSaved!,
      source = this.#active ?? this.#working
    this.blank('held', 'La sesión está suspendida mientras se confirma el cambio de seguridad.')
    this.#accountSaved = saved
    this.publishAccount('suspended', null)
    const handle = this.makeAccountCapture(saved, true)
    this.#suspendedAccount = handle
    try {
      if (source) await this.kernel.lockContext(source.ticket)
      if (!handle.isCurrent()) throw new Error('La sesión cambió antes de enviar la operación.')
      return handle
    } catch (error) {
      if (handle.isCurrent()) this.invalidateAccount(undefined, 'lock_failed')
      throw error
    }
  }
  async completeAccountCommand(
    handle: AccountCapture,
    outcome: AccountCommandOutcome,
  ): Promise<void> {
    if (this.#suspendedAccount !== handle || !handle.isCurrent()) return
    if (outcome === 'success') await this.logout()
    else {
      this.invalidateAccount()
      this.publish({
        phase: 'held',
        message:
          outcome === 'uncertain'
            ? 'No se pudo confirmar el resultado. Verifica la cuenta o inicia sesión nuevamente.'
            : 'La operación fue rechazada. Verifica la cuenta antes de continuar.',
      })
    }
  }
  updateAccountName(capture: AccountCapture, name: string): void {
    if (
      !this.#accountHandles.has(capture) ||
      !capture.isCurrent() ||
      this.#account.phase !== 'connected' ||
      !name.trim() ||
      [...name].length > 200
    )
      throw new Error('No se pudo actualizar el nombre de esta sesión.')
    const sequence = this.#sequence,
      saved = this.#accountSaved!,
      source = this.#active
    this.sessionStore.setUser({ ...saved.user!, display_name: name })
    const updated = this.sessionStore.getSnapshot()!
    if (source) this.#sessionSnapshots.get(source)!.saved = updated
    this.invalidateAccount()
    this.admitAccount(updated)
    if (this.exactSession(sequence, updated) && this.#snapshot.user)
      this.publish({ user: updated.user })
  }
  subscribe = (listener: () => void) => {
    this.#listeners.add(listener)
    return () => this.#listeners.delete(listener)
  }
  get preferences() {
    return this.#preferences
  }
  private publish(patch: Partial<WorkshopSnapshot>) {
    const next = {
      ...this.#snapshot,
      ...patch,
      captureRecoveryNotice: this.#captureRecovery.getNotice(),
    }
    const source = this.#captureSource
    if (
      next.phase !== 'ready' ||
      !source ||
      this.#active !== source ||
      !source.isCurrent(source.identity)
    ) {
      this.#captureVisit.suspendView()
      this.#customerLookup.clear()
      next.customerLookup = null
      next.capture = null
    } else {
      const capture = this.#captureVisit.getSnapshot()
      if (capture && source.context.capabilities.includes('customers.read')) {
        this.#customerLookup.bind(capture.viewToken)
        this.#customerLookup.select(capture.order.draft.customerId)
        next.customerLookup = this.#customerLookup.snapshot()
      } else {
        this.#customerLookup.clear()
        next.customerLookup = null
      }
      const recovery = this.#captureRecovery.snapshot()
      next.capture = capture
        ? Object.freeze({
            ...capture,
            customer: Object.freeze({
              ...capture.customer,
              blocked: capture.customer.blocked || recovery.customer.blocked,
              recoveryMessage: recovery.customer.message,
            }),
            order: Object.freeze({
              ...capture.order,
              blocked: capture.order.blocked || recovery.order.blocked,
              recoveryMessage: recovery.order.message,
            }),
          })
        : null
    }
    this.#snapshot = Object.freeze(next)
    this.branding.reconcile()
    for (const listener of this.#listeners) listener()
  }
  private maskCapture(): void {
    this.#customerLookup.clear()
    this.#captureVisit.suspendView()
    this.#captureSource = null
    this.#snapshot = Object.freeze({ ...this.#snapshot, capture: null, customerLookup: null })
  }
  private cancel() {
    this.maskCapture()
    this.#captureRecovery.suspend()
    this.branding.clear()
    this.invalidateAccount()
    this.#locationPage++
    this.#observedReachable = false
    this.#probe.cancel()
    this.#sequence++
    this.#networkSequence++
    this.#context.invalidate()
    this.#baseline.invalidate()
    this.#incremental.invalidate()
    this.#push.invalidate()
    this.#active = null
    this.#working = null
    this.#brandingAdmissionRefresh = null
    this.#preferences = null
    this.#running = false
    this.#localSyncWake = null
    if (this.#timer !== null) clearTimeout(this.#timer)
    if (this.#leaseTimer !== null) clearTimeout(this.#leaseTimer)
    this.#timer = null
    this.#leaseTimer = null
  }
  private blank(phase: WorkshopSnapshot['phase'], message: string | null = null) {
    const legacyPresent = this.#snapshot.legacyPresent
    this.cancel()
    this.#snapshot = Object.freeze({
      ...empty(),
      phase,
      message,
      legacyPresent,
      identityKey: String(this.#sequence),
    })
    for (const listener of this.#listeners) listener()
    return this.#sequence
  }
  private current(sequence: number, session?: SessionSnapshot) {
    if (sequence !== this.#sequence) return false
    if (!session) return true
    const now = this.sessionStore.getSnapshot()
    return !!now && now.token === session.token && now.bindingId === session.bindingId
  }
  private schedule(action: () => Promise<void>, delay = 0) {
    if (this.#timer !== null) clearTimeout(this.#timer)
    const sequence = this.#sequence
    this.#timer = setTimeout(
      () => {
        this.#timer = null
        if (sequence === this.#sequence)
          void action().catch(() => {
            if (sequence === this.#sequence) this.held('storage_or_fence_failure')
          })
      },
      Math.max(0, delay),
    )
  }
  private scheduleSync(delay = 0) {
    const source = this.#active
    if (
      !this.#verifiedOnline ||
      !source ||
      this.#snapshot.phase !== 'ready' ||
      !source.isCurrent(source.identity)
    )
      return
    this.schedule(async () => {
      if (this.#verifiedOnline && this.#active === source && source.isCurrent(source.identity))
        await this.sync()
    }, delay)
  }
  // Only a committed local write requests an extra pass. Polls and repeated
  // manual sync calls must not turn a busy cycle into an unbounded drain loop.
  private wakeLocalSync(source: BaselineSession, networkSequence: number) {
    if (
      this.#active !== source ||
      this.#networkSequence !== networkSequence ||
      !this.#verifiedOnline ||
      !source.isCurrent(source.identity)
    )
      return
    if (this.#running) this.#localSyncWake = { source, networkSequence }
    else this.scheduleSync()
  }
  private held(reason: string) {
    const active = this.#active ?? this.#working
    this.blank('held', safeMessage(reason))
    if (active) void this.kernel.lockContext(active.ticket).catch(() => undefined)
  }
  async start(): Promise<void> {
    if (this.#started) return
    this.#started = true
    await this.#captureRecovery.cleanup()
    this.#observer = liveQuery(() => this.database.deviceControl.get('device')).subscribe({
      next: (control) => {
        const session = this.#active
        if (
          session &&
          (!control ||
            control.generation !== session.ticket.deviceGeneration ||
            control.tabAttemptId !== session.ticket.tabAttemptId ||
            control.activePartitionId !== session.ticket.partitionId ||
            !['READY', 'OFFLINE_READY'].includes(control.state))
        )
          this.held('takeover')
      },
      error: () => this.held('storage_or_fence_failure'),
    })
    void inspectLegacyWork(this.options.factory ?? indexedDB)
      .then((present) => {
        this.publish({ legacyPresent: present })
      })
      .catch(() => undefined)
    const saved = this.sessionStore.getSnapshot()
    if (!saved?.user) return
    if (
      !saved.admission &&
      !saved.user.capabilities.includes('sync.pull') &&
      !saved.user.capabilities.includes('*')
    ) {
      await this.verifyAccount()
      if (this.#account.phase === 'connected')
        this.publish({
          phase: 'selector',
          user: this.#account.user,
          message: 'Cuenta verificada. No hay un taller operativo abierto.',
        })
      return
    }
    if (this.options.online()) {
      await this.verifyStored(
        saved,
        saved.admission ? undefined : (saved.user.location_id ?? undefined),
        saved.admission?.owner,
        false,
        !!saved.admission,
      )
    } else if (saved.bindingId && saved.admission) {
      await this.resumeStoredOffline(saved, this.blank('verifying'))
    } else
      this.publish({
        message: 'Conéctate para verificar esta sesión antes de abrir datos locales.',
      })
  }
  private retainedScopeMatches(saved: SessionSnapshot): boolean {
    if (!saved.user || !saved.bindingId || !saved.admission) return false
    const expectedPrincipal = principalKey({
      apiRealm: this.options.apiRealm,
      organizationId: saved.user.organization_id,
      userId: saved.user.user_id,
    })
    try {
      const binding: unknown = JSON.parse(saved.admission.binding)
      return (
        saved.admission.owner.principalKey === expectedPrincipal &&
        Array.isArray(binding) &&
        binding.length === 8 &&
        binding[0] === expectedPrincipal &&
        binding[6] === saved.user.location_id &&
        (saved.user.location_id === null || binding[1] === saved.user.location_id)
      )
    } catch {
      return false
    }
  }
  private exactSession(sequence: number, saved: SessionSnapshot): boolean {
    return (
      this.current(sequence, saved) &&
      JSON.stringify(this.sessionStore.getSnapshot()) === JSON.stringify(saved)
    )
  }
  private async resumeStoredOffline(saved: SessionSnapshot, sequence: number): Promise<void> {
    let captured = saved
    const current = () => this.exactSession(sequence, captured)
    try {
      if (!this.retainedScopeMatches(saved)) throw new Error('Offline session scope changed')
      const resumed = await this.kernel.resumeOffline(
        saved.admission!,
        crypto.randomUUID(),
        current,
      )
      if (!current()) return
      this.sessionStore.remember(resumed.admission, saved.token)
      captured = this.sessionStore.getSnapshot()!
      const source = this.makeSession(captured, resumed.ticket, resumed.context, sequence)
      await this.ready(source, captured.user!, sequence, false)
    } catch {
      if (current()) this.held('offline_expired')
    }
  }
  private makeSession(
    saved: SessionSnapshot,
    ticket: ContextTicket,
    context: VerifiedAccessContext,
    sequence: number,
  ): BaselineSession {
    const identity = {
      apiRealm: this.options.apiRealm,
      organizationId: context.principal.organizationId,
      userId: context.principal.userId,
      selectedLocationId: context.selectedLocationId,
      deviceGeneration: ticket.deviceGeneration,
      tabAttemptId: ticket.tabAttemptId,
      sessionHandle: saved.bindingId!,
      expectedAuthorizationEpoch: context.authorizationEpoch,
    }
    const capture = { saved }
    const source: BaselineSession = {
      ticket: structuredClone(ticket),
      context: structuredClone(context),
      identity,
      bearerToken: saved.token,
      isCurrent: () => this.exactSession(sequence, capture.saved),
    }
    this.#sessionSnapshots.set(source, capture)
    return source
  }
  async login(input: LoginRequestPayload): Promise<void> {
    const previousBinding = this.sessionStore.getSnapshot()?.bindingId
    this.maskCapture()
    this.#captureRecovery.close()
    this.#captureRecovery.startVisit()
    this.#captureEnrollmentBinding = null
    this.#captureVisit.startVisit()
    this.#transitionProtection.startVisit()
    const previous = this.#active ?? this.#working
    const sequence = this.blank('verifying'),
      current = () => this.current(sequence)
    if (!this.options.online()) {
      this.publish({ phase: 'locked', message: 'El inicio de sesión requiere conexión.' })
      return
    }
    try {
      if (previous) await this.kernel.lockContext(previous.ticket)
      if (!current()) return
      const token = await this.#http.login(input, current)
      if (!current()) return
      this.sessionStore.setToken(token)
      const saved = this.sessionStore.getSnapshot()!
      if (saved.bindingId && saved.bindingId !== previousBinding)
        this.#captureEnrollmentBinding = saved.bindingId
      const user = await this.#http.me({
        token,
        isCurrent: () => this.exactSession(sequence, saved),
      })
      if (!this.exactSession(sequence, saved)) return
      this.sessionStore.setUser(user)
      if (!user.capabilities.includes('sync.pull') && !user.capabilities.includes('*')) {
        this.sessionStore.bindVerifiedSession(token)
        this.publish({
          phase: 'selector',
          user,
          message: 'Cuenta verificada. No hay un taller operativo abierto.',
        })
        await this.verifyAccount()
        return
      }
      await this.verifyStored(this.sessionStore.getSnapshot()!, user.location_id ?? undefined)
    } catch (error) {
      if (current()) {
        this.maskCapture()
        this.#captureRecovery.close()
        this.sessionStore.clear()
        this.publish({
          phase: 'locked',
          message:
            error instanceof RuntimeHttpError
              ? error.message
              : 'No se pudo iniciar una sesión verificada.',
        })
      }
    }
  }
  private async verifyStored(
    saved: SessionSnapshot,
    selected?: string,
    expectedOwner?: ContextTicket,
    freshBaseline = false,
    offlineReload = false,
    probe?: ReachabilityResult<SessionUserSnapshot>,
  ): Promise<void> {
    const sequence = this.blank('verifying'),
      networkSequence = this.#networkSequence,
      current = () =>
        networkSequence === this.#networkSequence && this.exactSession(sequence, saved)
    try {
      let user = probe && 'value' in probe ? probe.value : undefined
      let preflightFailure = probe && 'error' in probe ? probe.error : undefined
      if (offlineReload) {
        if (!this.retainedScopeMatches(saved)) throw new Error('Reload session scope changed')
        try {
          user = await this.#http.me({ token: saved.token, isCurrent: current })
        } catch (error) {
          if (!current()) return
          if (error instanceof RuntimeHttpError && error.code === 'network_error') {
            await this.resumeStoredOffline(saved, sequence)
            return
          }
          // Reachable refusal must still invalidate old admission below.
          preflightFailure = error
        }
      }
      const attempt = await this.kernel.beginVerification(
        crypto.randomUUID(),
        current,
        expectedOwner,
      )
      if (preflightFailure !== undefined) throw preflightFailure
      user ??= await this.#http.me({ token: saved.token, isCurrent: current })
      if (!current()) return
      if (
        saved.user &&
        (user.user_id !== saved.user.user_id || user.organization_id !== saved.user.organization_id)
      )
        throw new Error('Principal changed')
      if (probe && user.location_id !== saved.user?.location_id)
        throw new Error('Account scope changed')
      this.sessionStore.setUser(user)
      this.sessionStore.bindVerifiedSession(saved.token)
      saved = this.sessionStore.getSnapshot()!
      if (!user.capabilities.includes('sync.pull') && !user.capabilities.includes('*')) {
        this.publish({
          phase: 'selector',
          user,
          message: 'Cuenta verificada. No hay un taller operativo abierto.',
        })
        await this.verifyAccount()
        return
      }
      const location =
        user.location_id ??
        selected ??
        (saved.admission ? (JSON.parse(saved.admission.binding)[1] as string) : undefined)
      if (!location) {
        this.publish({
          phase: 'selector',
          user,
          message: 'Selecciona un taller para abrir su información.',
        })
        await this.loadLocations()
        return
      }
      if (user.location_id && user.location_id !== location) throw new Error('Location changed')
      const identity = {
        apiRealm: this.options.apiRealm,
        organizationId: user.organization_id,
        userId: user.user_id,
        selectedLocationId: location,
        ...attempt,
        sessionHandle: saved.bindingId!,
      }
      const verified = await this.#context.verify({
        identity,
        bearerToken: saved.token,
        isCurrent: current,
      })
      if (!current()) return
      const accepted = await this.kernel.acceptVerifiedContext(attempt, verified.context, current)
      if (!current()) return
      this.#observedReachable = true
      const source = this.makeSession(saved, accepted.ticket, verified.context, sequence)
      this.#working = source
      this.publish({
        user,
        context: verified.context,
        selectedLocationId: location,
        identityKey: `${saved.bindingId}:${location}`,
      })
      if (accepted.state === 'READY' && !freshBaseline) {
        await this.ready(source, user, sequence, true)
        this.scheduleSync()
        return
      }
      if (!accepted.baselineSupported) {
        this.held('client_upgrade_required')
        return
      }
      this.publish({
        phase: 'baseline',
        message: 'Preparando el conjunto autorizado del taller…',
        sync: 'syncing',
      })
      const outcome = await this.#baseline.start(source)
      if (!current()) return
      source.ticket = outcome.ticket
      this.#working = source
      await this.baselineOutcome(source, outcome, sequence)
    } catch (error) {
      if (current())
        this.held(
          error instanceof RuntimeHttpError && error.code === 'network_error'
            ? 'verification_required'
            : 'takeover',
        )
    }
  }
  private async baselineOutcome(
    source: BaselineSession,
    outcome: { state: string; reason?: string; retryAt?: number },
    sequence: number,
  ): Promise<void> {
    if (!source.isCurrent(source.identity)) return
    if (outcome.reason === 'network_error') this.#observedReachable = false
    if (outcome.state === 'READY') {
      const state = await this.kernel.inspectSession(source.ticket, () =>
        source.isCurrent(source.identity),
      )
      source.context = state.context
      await this.ready(source, this.#snapshot.user!, sequence, true)
      this.scheduleSync()
      return
    }
    if (outcome.state === 'PROGRESSED' || outcome.state === 'RETRY_LATER') {
      this.schedule(
        async () => {
          const next = await this.#baseline.step(source)
          await this.baselineOutcome(source, next, sequence)
        },
        outcome.retryAt === undefined ? 0 : outcome.retryAt - this.#now(),
      )
      return
    }
    this.held(outcome.reason ?? 'verification_required')
  }
  private async ready(
    source: BaselineSession,
    user: SessionUserSnapshot,
    sequence: number,
    online: boolean,
  ) {
    const current = () => source.isCurrent(source.identity)
    if (!current()) return
    const saved = this.sessionStore.getSnapshot()!
    if (online) {
      const admission = await this.kernel.rememberSession(source.ticket, saved.bindingId!, current)
      if (!current()) return
      this.sessionStore.remember(admission, saved.token)
      this.#sessionSnapshots.get(source)!.saved = this.sessionStore.getSnapshot()!
    }
    this.#active = source
    this.#working = null
    this.#verifiedOnline = online
    this.#observedAt = this.#now()
    const scope = {
      organizationId: source.context.principal.organizationId,
      userId: source.context.principal.userId,
      locationId: source.context.selectedLocationId,
    }
    this.#preferences = new PreferenceRepository({
      get: (key) => this.database.presentationPreferences.get(key),
      put: (record) =>
        this.database.transaction(
          'rw',
          [this.database.presentationPreferences, this.database.deviceControl],
          async () => {
            const control = await this.database.deviceControl.get('device')
            if (
              !current() ||
              control?.generation !== source.ticket.deviceGeneration ||
              control.tabAttemptId !== source.ticket.tabAttemptId ||
              control.activePartitionId !== source.ticket.partitionId
            )
              throw new Error('Preference session changed')
            await this.database.presentationPreferences.put(record)
            if (!current()) throw new Error('Preference session changed')
          },
        ),
    })
    try {
      await copyOwnedLegacyPreferences({
        factory: this.options.factory ?? indexedDB,
        database: this.database,
        scope,
        ticket: source.ticket,
        isCurrent: current,
      })
    } catch {
      /* Preference copy failure does not affect operational admission. */
    }
    if (!current()) return
    const connected = online && this.#verifiedOnline
    this.observeTransitionScope(source)
    this.#captureVisit.observeScope(this.captureScope(source))
    this.#captureSource = source
    const hydration = this.#captureVisit.hydrationToken()
    const recovered = await this.#captureRecovery.ready(
      this.#captureEnrollmentBinding === source.identity.sessionHandle,
    )
    if (!current() || this.#captureSource !== source) return
    this.#captureEnrollmentBinding = null
    this.#captureVisit.hydrate(recovered, hydration)
    this.#captureVisit.activateView()
    this.#brandingAdmissionRefresh = connected ? source : null
    this.publish({
      phase: 'ready',
      user,
      context: source.context,
      selectedLocationId: scope.locationId,
      message: connected ? null : 'Acceso local verificado hasta el vencimiento de la sesión.',
      sync: connected ? 'local' : 'offline',
      identityKey: `${saved.bindingId}:${scope.locationId}`,
      transitionProtection: this.#transitionProtection.getSnapshot(),
    })
    this.armLease(source)
    if (!connected) this.probeOffline(source)
    await this.refresh()
    const readyView = this.#snapshot.capture?.viewToken
    if (readyView && current()) void this.resolveCustomerSelection(readyView)
    // Initial operational reads advance the kernel's trusted observation time.
    // Recover an overlapping cache read once, after those reads have settled.
    if (!connected && this.#active === source && current()) void this.branding.refresh(true)
    void inspectLegacyWork(this.options.factory ?? indexedDB)
      .then((present) => {
        if (current()) this.publish({ legacyPresent: present })
      })
      .catch(() => undefined)
  }
  private probeOffline(source: BaselineSession) {
    if (this.#snapshot.phase !== 'ready') return
    const saved = this.sessionStore.getSnapshot()
    const captured = this.#sessionSnapshots.get(source)?.saved
    if (
      !saved ||
      !captured ||
      JSON.stringify(saved) !== JSON.stringify(captured) ||
      !this.retainedScopeMatches(saved) ||
      !saved.admission ||
      saved.token !== source.bearerToken ||
      saved.bindingId !== source.identity.sessionHandle ||
      saved.admission.datasetIncarnation !== source.context.datasetIncarnation ||
      Object.keys(source.ticket).some(
        (key) =>
          saved.admission!.owner[key as keyof ContextTicket] !==
          source.ticket[key as keyof ContextTicket],
      )
    )
      return
    const sequence = this.#sequence,
      networkSequence = this.#networkSequence
    const current = () =>
      this.#snapshot.phase === 'ready' &&
      !this.#verifiedOnline &&
      this.#active === source &&
      networkSequence === this.#networkSequence &&
      this.exactSession(sequence, saved) &&
      source.isCurrent(source.identity)
    this.#probe.start({
      expiresAt: Date.parse(source.context.offlineUntil),
      current,
      inspect: async () => {
        await this.kernel.inspectSession(source.ticket, current)
      },
      request: (signal, capture) =>
        this.#http.me({ token: saved.token, signal, isCurrent: capture }),
      complete: async (result, capture) => {
        if (!capture()) return
        await this.kernel.inspectSession(source.ticket, capture)
        if (capture())
          await this.verifyStored(
            saved,
            source.context.selectedLocationId,
            source.ticket,
            false,
            false,
            result,
          )
      },
      invalid: () => {
        if (current()) this.held('offline_expired')
      },
    })
  }
  private armLease(source: BaselineSession) {
    if (this.#leaseTimer !== null) clearTimeout(this.#leaseTimer)
    this.#leaseTimer = setTimeout(
      () => {
        if (this.#active === source) this.held('offline_expired')
      },
      Math.max(0, Date.parse(source.context.offlineUntil) - this.#now()),
    )
  }
  async checkLease(): Promise<void> {
    const connectedCheck = this.connectedReads.check()
    const source = this.#active
    if (!source) {
      await connectedCheck
      return
    }
    const now = this.#now()
    if (
      !Number.isFinite(now) ||
      now < this.#observedAt ||
      now >= Date.parse(source.context.offlineUntil)
    ) {
      this.held('offline_expired')
      return
    }
    this.#observedAt = now
    await connectedCheck
    if (this.#active !== source) return
    try {
      await this.kernel.inspectSession(source.ticket, () => source.isCurrent(source.identity))
    } catch {
      if (this.#active === source) this.held('takeover')
    }
  }
  async loadLocations(afterId?: string): Promise<void> {
    const sequence = this.#sequence,
      sessionGeneration = this.#sessionGeneration,
      pageSequence = ++this.#locationPage,
      networkSequence = this.#networkSequence,
      saved = this.sessionStore.getSnapshot(),
      phase = this.#snapshot.phase,
      metadataRecovery = phase === 'held' && !this.#active && this.#account.phase === 'connected',
      user = metadataRecovery ? this.#account.user : this.#snapshot.user
    if (
      (phase !== 'selector' && !metadataRecovery) ||
      !saved ||
      !user ||
      !user.capabilities.includes('locations.read')
    )
      return
    // A refused metadata-only reader can explicitly reverify and refresh its
    // directory without opening an operational kernel or starting a baseline.
    let account: AccountCapture | null = null
    if (metadataRecovery) {
      try {
        account = this.captureAccount()
      } catch {
        return
      }
    }
    const current = () =>
      this.#snapshot.phase === phase &&
      (!account || account.isCurrent()) &&
      sessionGeneration === this.#sessionGeneration &&
      pageSequence === this.#locationPage &&
      networkSequence === this.#networkSequence &&
      this.exactSession(sequence, saved)
    try {
      const page = await this.#http.locations(
        { token: saved.token, isCurrent: current },
        user.organization_id,
        afterId,
      )
      if (current()) {
        this.#locationsSessionGeneration = this.#sessionGeneration
        this.#locationsNetworkSequence = this.#networkSequence
        this.publish({
          locations: page.items,
          nextLocation: page.nextCursor,
          message: 'Selecciona un taller para abrir su información.',
        })
      }
    } catch (error) {
      if (current())
        this.publish({
          message:
            error instanceof RuntimeHttpError
              ? error.message
              : 'No se pudieron obtener los talleres.',
        })
    }
  }
  async selectWorkshop(locationId: string): Promise<void> {
    if (
      this.#snapshot.phase !== 'selector' ||
      !this.#snapshot.locations.some((row) => row.location_id === locationId)
    )
      return
    const saved = this.sessionStore.getSnapshot()
    if (saved) {
      this.#captureVisit.startVisit()
      this.#transitionProtection.startVisit()
      await this.verifyStored(saved, locationId)
    }
  }
  async changeWorkshop() {
    const saved = this.sessionStore.getSnapshot()
    if (saved?.user?.location_id === null) {
      this.maskCapture()
      const retirement = this.#captureRecovery.retireVisit()
      this.#captureVisit.endVisit()
      this.#transitionProtection.endVisit()
      const source = this.#active
      const sequence = this.blank('selector')
      if (source) await this.kernel.lockContext(source.ticket).catch(() => undefined)
      await retirement
      if (sequence !== this.#sequence) return
      this.publish({ user: saved.user, message: 'Selecciona un taller.' })
      await this.loadLocations()
    }
  }
  async reconnect() {
    const saved = this.sessionStore.getSnapshot(),
      source = this.#active
    if (!saved || !source) return
    await this.verifyStored(saved, source.context.selectedLocationId, source.ticket)
  }
  async offline() {
    this.#brandingAdmissionRefresh = null
    this.branding.clear()
    this.invalidateAccount()
    this.#locationPage++
    if (!this.#verifiedOnline && this.#active && this.#snapshot.sync === 'offline') {
      await this.checkLease()
      this.branding.reconcile()
      return
    }
    this.#observedReachable = false
    this.#probe.cancel()
    this.#verifiedOnline = false
    this.#networkSequence++
    this.#push.invalidate()
    this.#incremental.invalidate()
    this.#running = false
    this.#localSyncWake = null
    if (this.#timer !== null) clearTimeout(this.#timer)
    this.#timer = null
    const source = this.#active
    if (!source) return
    this.publish({ sync: 'offline' })
    try {
      await this.kernel.continueOffline(source.ticket)
      if (this.#active === source) {
        this.publish({ sync: 'offline' })
        void this.branding.refresh(true)
        this.probeOffline(source)
      }
    } catch {
      if (this.#active === source) this.held('verification_required')
    }
  }
  async retryVerification() {
    const saved = this.sessionStore.getSnapshot()
    if (saved && this.options.online()) await this.verifyStored(saved, undefined, undefined, true)
    else this.publish({ message: 'Conéctate para verificar la sesión y reintentar.' })
  }
  async logout() {
    this.maskCapture()
    this.#captureRecovery.close()
    this.#captureVisit.endVisit()
    this.#transitionProtection.endVisit()
    const source = this.#active ?? this.#working
    this.blank('locked')
    this.sessionStore.clear()
    if (source) await this.kernel.lockContext(source.ticket).catch(() => undefined)
  }
  async revoke() {
    let handle: AccountCapture | undefined
    try {
      if (this.#account.phase !== 'connected') await this.verifyAccount()
      handle = await this.suspendAccountCommand(this.captureAccount())
      await this.#http.revoke(handle)
      await this.completeAccountCommand(handle, 'success')
    } catch (error) {
      if (handle && error instanceof RuntimeHttpError && error.code === 'invalid_session')
        this.invalidateAccount(handle, 'invalid_session')
      else if (handle)
        await this.completeAccountCommand(
          handle,
          error instanceof RuntimeHttpError && error.code === 'capability_denied'
            ? 'refused'
            : 'uncertain',
        )
    }
  }
  private requireActive() {
    const source = this.#active
    if (!source || !source.isCurrent(source.identity) || this.#snapshot.phase !== 'ready')
      throw new Error('Se requiere una sesión verificada.')
    return source
  }
  async refresh(type?: 'customer' | 'service_order', afterId?: string): Promise<boolean> {
    const source = this.requireActive(),
      current = () => this.#active === source && source.isCurrent(source.identity)
    try {
      const context = source.context
      const [customers, orders, issues] = await Promise.all([
        context.capabilities.includes('customers.read') && type !== 'service_order'
          ? this.repositories.page(source, 'customer', afterId)
          : null,
        context.capabilities.includes('orders.read') && type !== 'customer'
          ? this.repositories.page(source, 'service_order', afterId)
          : null,
        this.repositories.issues(source),
      ])
      if (!current()) return false
      this.publish({
        ...(customers
          ? {
              customers: customers.items
                .map((row) => row.optimistic ?? row.confirmed)
                .filter(Boolean) as unknown as LocalCustomer[],
              customerAfter: customers.nextAfterId,
            }
          : {}),
        ...(orders
          ? {
              orders: orders.items
                .map((row) => row.optimistic ?? row.confirmed)
                .filter(Boolean) as unknown as LocalServiceOrder[],
              orderAfter: orders.nextAfterId,
            }
          : {}),
        issues: issues.items
          .filter(
            (row) =>
              row.delivery &&
              !['pending', 'inflight', 'retryable', 'applied'].includes(row.delivery.state),
          )
          .map((row) => ({
            mutationId: row.operation.mutationId,
            entityId: row.operation.entityId,
            entityType: row.operation.entityType,
            errorMessage: row.delivery!.result?.error_message ?? null,
            state: row.delivery!.state,
            errorCode: row.delivery!.result?.error_code ?? null,
          })),
        issueAfter: issues.nextAfterSequence,
        hasIssues: issues.hasIssues,
        hasPending: issues.hasPending,
        nextRetryAt: issues.nextRetryAt,
        ...(issues.hasIssues && this.#snapshot.sync === 'synced'
          ? { sync: 'conflict' as const }
          : {}),
      })
      return current()
    } catch {
      if (current()) this.held('storage_or_fence_failure')
      return false
    }
  }
  async loadIssues(afterSequence?: number) {
    const source = this.requireActive()
    const page = await this.repositories.issues(source, afterSequence)
    if (this.#active !== source || !source.isCurrent(source.identity)) return
    this.publish({
      issues: page.items
        .filter(
          (row) =>
            row.delivery &&
            !['pending', 'inflight', 'retryable', 'applied'].includes(row.delivery.state),
        )
        .map((row) => ({
          mutationId: row.operation.mutationId,
          entityId: row.operation.entityId,
          entityType: row.operation.entityType,
          errorMessage: row.delivery!.result?.error_message ?? null,
          state: row.delivery!.state,
          errorCode: row.delivery!.result?.error_code ?? null,
        })),
      issueAfter: page.nextAfterSequence,
      hasIssues: page.hasIssues,
      hasPending: page.hasPending,
      nextRetryAt: page.nextRetryAt,
      ...(page.hasIssues && this.#snapshot.sync === 'synced' ? { sync: 'conflict' as const } : {}),
    })
  }
  hasUnsentCaptures(): boolean {
    return this.#captureVisit.hasUnsent() || this.#captureRecovery.hasUnsent()
  }
  private captureSource(view: object): BaselineSession | null {
    const source = this.#captureSource
    return source &&
      this.#active === source &&
      this.#snapshot.phase === 'ready' &&
      source.isCurrent(source.identity) &&
      this.#captureVisit.isCurrentView(view)
      ? source
      : null
  }
  editCaptureCustomer<K extends keyof CustomerDraftState>(
    view: object,
    field: K,
    value: CustomerDraftState[K],
  ): void {
    if (this.captureSource(view) && this.#captureVisit.editCustomer(view, field, value)) {
      this.#captureRecovery.edit('customer', this.#captureVisit.projection('customer'))
      this.publish({})
    }
  }
  editCaptureOrder<K extends keyof OrderDraftState>(
    view: object,
    field: K,
    value: OrderDraftState[K],
  ): void {
    if (this.captureSource(view) && this.#captureVisit.editOrder(view, field, value)) {
      this.#captureRecovery.edit('order', this.#captureVisit.projection('order'))
      this.publish({})
      if (field === 'customerId') void this.resolveCustomerSelection(view)
    }
  }
  editCustomerQuery(view: object, query: string): void {
    const source = this.captureSource(view)
    if (!source?.context.capabilities.includes('customers.read')) return
    this.#customerLookup.edit(query)
    this.publish({})
  }
  async retryCustomerSelection(view: object): Promise<void> {
    if (!this.captureSource(view) || this.#customerLookup.snapshot().busy) return
    this.#customerLookup.retry()
    this.publish({})
    await this.resolveCustomerSelection(view)
  }
  private async resolveCustomerSelection(view: object): Promise<void> {
    const source = this.captureSource(view)
    if (!source?.context.capabilities.includes('customers.read')) return
    const id = this.#snapshot.capture?.order.draft.customerId ?? ''
    this.#customerLookup.select(id)
    const revision = this.#customerLookup.selectionRevision
    const current = () =>
      this.captureSource(view) === source &&
      this.#snapshot.capture?.order.draft.customerId === id &&
      this.#customerLookup.selectionRevision === revision
    while (this.#customerLookup.snapshot().busy) {
      await this.#customerLookup.wait()
      if (!current()) return
    }
    if (!id || !current() || this.#customerLookup.snapshot().selection.status === 'available')
      return
    let readCompleted = false
    await this.#customerLookup.run(
      async () => {
        const customer = await this.repositories.selectedCustomer(source, id)
        readCompleted = true
        return customer
      },
      (customer) => this.#customerLookup.selected(id, customer),
      current,
      () => this.#customerLookup.selectionRevision,
    )
    if (readCompleted && this.captureSource(view) === source)
      this.branding.refreshOfflineAfterLocalActivity()
  }
  async searchCustomers(view: object, action: 'restart' | 'continue'): Promise<void> {
    const source = this.captureSource(view)
    if (!source?.context.capabilities.includes('customers.read')) return
    const state = this.#customerLookup.snapshot()
    if (state.busy) return
    const query = state.query.trim().toLowerCase()
    if (!query || [...state.query].length > 200) {
      this.#customerLookup.message(
        !query
          ? 'Escribe un nombre para buscar en los clientes locales.'
          : 'La búsqueda no puede superar 200 caracteres.',
      )
      this.publish({})
      return
    }
    if (action === 'continue' && (!state.pages || state.nextAfterId === null)) return
    const selectedId = this.#snapshot.capture?.order.draft.customerId ?? ''
    const revision = this.#customerLookup.revision
    const current = () =>
      this.captureSource(view) === source &&
      this.#customerLookup.revision === revision &&
      this.#snapshot.capture?.order.draft.customerId === selectedId
    let readCompleted = false
    await this.#customerLookup.run(
      async () => {
        const page = await this.repositories.page(
          source,
          'customer',
          action === 'continue' ? state.nextAfterId! : undefined,
        )
        readCompleted = true
        if (!current()) return null
        const selected = selectedId
          ? await this.repositories.selectedCustomer(source, selectedId)
          : null
        const matches = page.items
          .map((row) => row.optimistic ?? row.confirmed)
          .filter((row): row is NonNullable<typeof row> => !!row)
          .filter(
            (row) =>
              typeof row.display_name === 'string' &&
              row.display_name.toLowerCase().includes(query),
          )
          .map((row) => ({
            customer_id: row.customer_id as string,
            display_name: row.display_name as string,
          }))
        return { matches, selected, nextAfterId: page.nextAfterId }
      },
      (result) => {
        if (!result) return
        this.#customerLookup.page(result.matches, result.nextAfterId, action === 'restart')
        if (selectedId) this.#customerLookup.selected(selectedId, result.selected)
      },
      current,
    )
    // Reads advance the shared observation fence even when their query became stale.
    // Check authority again after run's synchronous final publication, not query epoch.
    if (readCompleted && this.captureSource(view) === source)
      this.branding.refreshOfflineAfterLocalActivity()
  }
  async submitCaptureCustomer(view: object): Promise<void> {
    const source = this.captureSource(view)
    if (!source || !this.#captureRecovery.canSubmit('customer')) return
    const attempt = this.#captureVisit.begin(view, 'customer')
    if (!attempt) return
    this.publish({})
    let feedback
    let protection: RecoveryAttempt | null = null
    let dispatched = false
    try {
      // Subscribers may synchronously replace authority while observing busy.
      protection = await this.#captureRecovery.protect('customer')
      if (!protection || this.captureSource(view) !== source) {
        feedback = captureFeedback({
          kind: 'resolved',
          value: { status: 'not_saved', reason: 'write_failure' },
        })
      } else {
        dispatched = true
        const { displayName, email, phone } = attempt.input
        feedback = captureFeedback({
          kind: 'resolved',
          value: await this.createCustomer({
            displayName,
            email: email || null,
            phone: phone || null,
          }),
        })
      }
    } catch (error) {
      feedback = captureFeedback({ kind: 'rejected', error })
    }
    const finished = this.#captureVisit.finish(attempt.token, feedback)
    const completionSource = this.#captureSource
    if (finished && dispatched && protection && feedback.status !== 'unknown')
      await this.#captureRecovery.settle(
        protection,
        feedback.status,
        this.#captureVisit.projection('customer'),
      )
    if (finished) {
      this.publish({})
      if (
        protection &&
        completionSource &&
        this.#captureSource === completionSource &&
        this.#active === completionSource
      )
        this.branding.refreshOfflineAfterLocalActivity()
    }
  }
  async submitCaptureOrder(view: object): Promise<void> {
    const selection = this.#snapshot.customerLookup?.selection
    if (
      this.captureSource(view) &&
      selection?.status === 'unavailable' &&
      selection.id === this.#snapshot.capture?.order.draft.customerId
    )
      return
    const source = this.captureSource(view)
    if (!source || !this.#captureRecovery.canSubmit('order')) return
    const attempt = this.#captureVisit.begin(view, 'order')
    if (!attempt) return
    this.publish({})
    let feedback
    let protection: RecoveryAttempt | null = null
    let dispatched = false
    try {
      protection = await this.#captureRecovery.protect('order')
      if (!protection || this.captureSource(view) !== source) {
        feedback = captureFeedback({
          kind: 'resolved',
          value: { status: 'not_saved', reason: 'write_failure' },
        })
      } else {
        const draft = attempt.input
        let normalized
        try {
          normalized = normalizeOrderIntake({
            ...draft,
            brand: draft.withBicycle ? draft.brand : null,
            model: draft.withBicycle ? draft.model : null,
          })
        } catch (error) {
          const validation = captureValidation(error)
          if (!validation) throw error
          if (
            this.#captureVisit.finish(
              attempt.token,
              captureFeedback({ kind: 'resolved', value: validation }),
            )
          )
            this.publish({})
          if (protection)
            await this.#captureRecovery.settle(
              protection,
              'not_saved',
              this.#captureVisit.projection('order'),
            )
          return
        }
        dispatched = true
        feedback = captureFeedback({ kind: 'resolved', value: await this.createOrder(normalized) })
      }
    } catch (error) {
      feedback = captureFeedback({ kind: 'rejected', error })
    }
    const finished = this.#captureVisit.finish(attempt.token, feedback)
    const completionSource = this.#captureSource
    if (finished && dispatched && protection && feedback.status !== 'unknown')
      await this.#captureRecovery.settle(
        protection,
        feedback.status,
        this.#captureVisit.projection('order'),
      )
    if (finished) {
      this.publish({})
      if (
        protection &&
        completionSource &&
        this.#captureSource === completionSource &&
        this.#active === completionSource
      )
        this.branding.refreshOfflineAfterLocalActivity()
    }
  }
  async createCustomer(input: {
    displayName: string
    email?: string | null
    phone?: string | null
  }): Promise<CaptureSubmissionResult> {
    const source = this.requireActive(),
      networkSequence = this.#networkSequence
    const outcome = await this.repositories.createCustomer(source, input)
    if (outcome.status === 'not_saved') return outcome
    if (this.#active !== source) return { status: 'saved' }
    await this.refresh()
    this.wakeLocalSync(source, networkSequence)
    return { status: 'saved' }
  }
  async createOrder(input: IntakeInput): Promise<CaptureSubmissionResult> {
    const source = this.requireActive(),
      networkSequence = this.#networkSequence
    const outcome = await this.repositories.createOrder(source, input)
    if (outcome.status === 'not_saved') return outcome
    if (this.#active !== source) return { status: 'saved' }
    await this.refresh()
    this.wakeLocalSync(source, networkSequence)
    return { status: 'saved' }
  }
  private captureScope(source: BaselineSession): CaptureVisitScope {
    return {
      apiRealm: source.context.principal.apiRealm,
      organizationId: source.context.principal.organizationId,
      userId: source.context.principal.userId,
      selectedLocationId: source.context.selectedLocationId,
      datasetIncarnation: source.context.datasetIncarnation,
      authorizationEpoch: source.context.authorizationEpoch,
      policyRevision: source.context.policyRevision,
      capabilities: source.context.capabilities,
      sessionBindingId: source.identity.sessionHandle,
    }
  }
  private observeTransitionScope(source: BaselineSession): void {
    this.#transitionProtection.observeScope(this.captureScope(source))
  }
  async transition(orderId: string, action: OrderAction): Promise<OrderTransitionResult> {
    let source: BaselineSession
    try {
      source = this.requireActive()
    } catch {
      return { status: 'unknown' }
    }
    this.observeTransitionScope(source)
    const token = this.#transitionProtection.begin(orderId)
    if (!token) {
      this.publish({ transitionProtection: this.#transitionProtection.getSnapshot() })
      return { status: 'unknown' }
    }
    this.publish({ transitionProtection: this.#transitionProtection.getSnapshot() })
    let result: OrderTransitionResult
    try {
      result = await this.executeTransition(source, orderId, action)
    } catch {
      result = { status: 'unknown' }
    }
    const settled = this.#transitionProtection.finish(
      orderId,
      token,
      orderTransitionFeedback({ kind: 'resolved', value: result }),
    )
    const active = this.#active
    if (settled && active?.isCurrent(active.identity) && this.#snapshot.phase === 'ready') {
      this.observeTransitionScope(active)
      this.publish({ transitionProtection: this.#transitionProtection.getSnapshot() })
    }
    return result
  }
  private async executeTransition(
    source: BaselineSession,
    orderId: string,
    action: OrderAction,
  ): Promise<OrderTransitionResult> {
    const networkSequence = this.#networkSequence
    try {
      await this.repositories.transition(source, orderId, action)
    } catch {
      // Rejection can follow a native commit. Never infer rollback or replay.
      return { status: 'unknown' }
    }
    const unavailable: OrderTransitionResult = { status: 'committed', view: 'unavailable' }
    const current = () =>
      this.#active === source &&
      source.isCurrent(source.identity) &&
      this.#snapshot.phase === 'ready'
    try {
      if (!current()) return unavailable
      const refreshed = await this.refresh()
      if (refreshed !== true || !current()) return unavailable
      const history = await this.refreshTimeline(source, orderId)
      if (history !== true || !current()) return unavailable
      this.wakeLocalSync(source, networkSequence)
      return { status: 'committed', view: 'updated' }
    } catch {
      return unavailable
    }
  }
  async timeline(orderId: string) {
    await this.refreshTimeline(this.requireActive(), orderId)
  }
  private async refreshTimeline(source: BaselineSession, orderId: string): Promise<boolean> {
    const current = () => this.#active === source && source.isCurrent(source.identity)
    if (!current()) return false
    const authorizedOrder = await this.kernel.readEntity(
      source.ticket,
      'service_order',
      orderId,
      current,
    )
    if (!authorizedOrder || !current()) return false
    const local = await this.repositories.localTimeline(source, orderId)
    if (!current()) return false
    let events = local.events,
      message = local.partial
        ? 'Historial local parcial.'
        : 'Historial local de esta sesión; la copia inicial no incluye todo el historial.'
    if (this.options.online()) {
      try {
        const remote = await this.#http.timeline(
          { token: source.bearerToken, isCurrent: current },
          source.context.principal.organizationId,
          orderId,
        )
        const merged = new Map(remote.map((row) => [row.event_id, row]))
        for (const row of events) merged.set(row.event_id, row)
        events = [...merged.values()]
        message = local.partial
          ? 'Historial del servidor y página local parcial.'
          : 'Historial del servidor y cambios locales.'
      } catch {
        message =
          'El historial remoto no está disponible o excede el límite seguro. Se muestra solo el historial local.'
      }
    } else
      message = 'Sin conexión: el historial remoto no está disponible. Se muestran cambios locales.'
    if (!current()) return false
    this.publish({
      events: events.sort((a, b) => a.occurred_at.localeCompare(b.occurred_at)),
      timelineMessage: message,
    })
    return current()
  }
  async sync(): Promise<void> {
    const source = this.#active
    if (!source || this.#running) return
    if (!this.#observedReachable && !this.options.online()) {
      await this.offline()
      return
    }
    if (!this.#verifiedOnline) {
      await this.reconnect()
      return
    }
    this.#running = true
    this.publish({ sync: 'syncing' })
    const networkSequence = this.#networkSequence
    const current = () =>
      this.#verifiedOnline &&
      networkSequence === this.#networkSequence &&
      this.#active === source &&
      source.isCurrent(source.identity)
    const networkSession = { ...source, isCurrent: current }
    let canDrainLocalWake = false
    try {
      const push = source.context.capabilities.includes('sync.push')
        ? await this.#push.step(networkSession)
        : { state: 'IDLE' }
      if (!current()) return
      if ('reason' in push && push.reason === 'network_error') this.#observedReachable = false
      if (push.state === 'HELD') {
        this.held(
          'reason' in push ? (push.reason ?? 'verification_required') : 'verification_required',
        )
        return
      }
      const delta = await this.#incremental.step(networkSession)
      if (!current()) return
      if (delta.reason === 'network_error') this.#observedReachable = false
      if (delta.state === 'HELD' || delta.state === 'BASELINE_REQUIRED') {
        this.held(delta.reason ?? 'verification_required')
        return
      }
      await this.refresh()
      if (!current()) return
      canDrainLocalWake =
        (delta.state === 'READY' || delta.state === 'PROGRESSED') &&
        (push.state === 'IDLE' || push.state === 'APPLIED')
      if (delta.state === 'PROGRESSED' || push.state === 'APPLIED') {
        this.scheduleSync()
        return
      }
      if (delta.state === 'RETRY_LATER' || push.state === 'RETRY_LATER') {
        this.publish({ sync: 'error' })
        this.scheduleSync(
          Math.max(
            1000,
            Math.min(
              ...[delta.retryAt, this.#snapshot.nextRetryAt]
                .filter((value): value is number => typeof value === 'number')
                .map((value) => value - this.#now()),
              30000,
            ),
          ),
        )
        return
      }
      this.publish({
        sync:
          delta.state === 'OFFLINE'
            ? 'offline'
            : this.#snapshot.hasIssues
              ? 'conflict'
              : this.#snapshot.hasPending ||
                  ['customers', 'bicycles', 'orders'].some(
                    (entity) =>
                      source.context.capabilities.includes(`${entity}.write`) &&
                      !source.context.capabilities.includes(`${entity}.read`),
                  )
                ? this.#snapshot.nextRetryAt === null
                  ? 'local'
                  : 'error'
                : 'synced',
      })
      this.scheduleSync(
        this.#snapshot.nextRetryAt === null
          ? 30000
          : Math.max(1000, Math.min(30000, this.#snapshot.nextRetryAt - this.#now())),
      )
      // Admission's first settled sync can fence an overlapping branding write.
      // Request once after its final reads, never on every subsequent poll/page.
      if (current() && this.#brandingAdmissionRefresh === source) {
        this.#brandingAdmissionRefresh = null
        void this.branding.refresh(true)
      }
    } catch {
      if (current()) this.held('storage_or_fence_failure')
    } finally {
      if (current()) {
        this.#running = false
        const wake = this.#localSyncWake
        if (wake?.source === source && wake.networkSequence === networkSequence) {
          this.#localSyncWake = null
          if (canDrainLocalWake) this.scheduleSync()
        }
      }
    }
  }
  dispose() {
    this.#captureRecovery.dispose()
    this.#captureVisit.endVisit()
    this.#transitionProtection.endVisit()
    this.#disposed = true
    this.cancel()
    this.#observer?.unsubscribe()
    this.#observer = null
    this.#listeners.clear()
    this.#accountListeners.clear()
    this.database.close()
  }
}

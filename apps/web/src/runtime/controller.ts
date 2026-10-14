import { liveQuery } from 'dexie'
import { AccessKernel } from '../access-kernel/kernel.js'
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
}
const empty = (): WorkshopSnapshot => ({
  phase: 'locked',
  user: null,
  context: null,
  selectedLocationId: null,
  message: null,
  sync: 'local',
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
  readonly repositories: WorkshopRepositories
  #snapshot = empty()
  #listeners = new Set<() => void>()
  #sequence = 0
  #active: BaselineSession | null = null
  #working: BaselineSession | null = null
  #timer: ReturnType<typeof setTimeout> | null = null
  #leaseTimer: ReturnType<typeof setTimeout> | null = null
  #observedAt = 0
  #started = false
  #running = false
  #verifiedOnline = false
  #networkSequence = 0
  #preferences: PreferenceRepository | null = null
  #observer: { unsubscribe(): void } | null = null
  readonly #now: () => number
  readonly #http: ReturnType<typeof createRuntimeTransport>
  readonly #context: ReturnType<typeof createServerContextAdapter>
  readonly #baseline: ReturnType<typeof createBaselineCoordinator>
  readonly #incremental: ReturnType<typeof createIncrementalCoordinator>
  readonly #push: ReturnType<typeof createPushCoordinator>
  constructor(private readonly options: RuntimeOptions) {
    this.#now = options.now ?? Date.now
    this.database = options.database ?? createKernelDatabase('ocwp-authenticated-v1')
    this.kernel = new AccessKernel(this.database, {
      now: this.#now,
      newId: () => crypto.randomUUID(),
    })
    this.sessionStore = new SessionStore(options.storage)
    this.repositories = new WorkshopRepositories(this.kernel, this.#now)
    this.#http = createRuntimeTransport(options)
    this.#context = createServerContextAdapter({ ...options, now: this.#now })
    const common = {
      kernel: this.kernel,
      now: this.#now,
      random: Math.random,
      online: options.online,
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
  }
  getSnapshot = () => this.#snapshot
  subscribe = (listener: () => void) => {
    this.#listeners.add(listener)
    return () => this.#listeners.delete(listener)
  }
  get preferences() {
    return this.#preferences
  }
  private publish(patch: Partial<WorkshopSnapshot>) {
    this.#snapshot = Object.freeze({ ...this.#snapshot, ...patch })
    for (const listener of this.#listeners) listener()
  }
  private cancel() {
    this.#sequence++
    this.#networkSequence++
    this.#context.invalidate()
    this.#baseline.invalidate()
    this.#incremental.invalidate()
    this.#push.invalidate()
    this.#active = null
    this.#working = null
    this.#preferences = null
    this.#running = false
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
  private held(reason: string) {
    const active = this.#active ?? this.#working
    this.blank('held', safeMessage(reason))
    if (active) void this.kernel.lockContext(active.ticket).catch(() => undefined)
  }
  async start(): Promise<void> {
    if (this.#started) return
    this.#started = true
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
    if (this.options.online()) {
      await this.verifyStored(
        saved,
        saved.admission ? undefined : (saved.user.location_id ?? undefined),
        saved.admission?.owner,
      )
    } else if (saved.bindingId && saved.admission) {
      const sequence = this.blank('verifying'),
        current = () => this.current(sequence, saved)
      try {
        const resumed = await this.kernel.resumeOffline(
          saved.admission,
          crypto.randomUUID(),
          current,
        )
        if (!current()) return
        this.sessionStore.remember(resumed.admission, saved.token)
        const source = this.makeSession(saved, resumed.ticket, resumed.context, sequence)
        await this.ready(source, saved.user, sequence, false)
      } catch {
        if (current()) this.held('offline_expired')
      }
    } else
      this.publish({
        message: 'Conéctate para verificar esta sesión antes de abrir datos locales.',
      })
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
    return {
      ticket: structuredClone(ticket),
      context: structuredClone(context),
      identity,
      bearerToken: saved.token,
      isCurrent: () => this.current(sequence, saved),
    }
  }
  async login(input: LoginRequestPayload): Promise<void> {
    const sequence = this.blank('verifying'),
      current = () => this.current(sequence)
    if (!this.options.online()) {
      this.publish({ phase: 'locked', message: 'El inicio de sesión requiere conexión.' })
      return
    }
    try {
      await this.kernel.beginVerification(crypto.randomUUID(), current)
      const token = await this.#http.login(input, current)
      if (!current()) return
      this.sessionStore.setToken(token)
      const saved = this.sessionStore.getSnapshot()!
      const user = await this.#http.me({ token, isCurrent: () => this.current(sequence, saved) })
      if (!this.current(sequence, saved)) return
      this.sessionStore.setUser(user)
      await this.verifyStored(this.sessionStore.getSnapshot()!, user.location_id ?? undefined)
    } catch (error) {
      if (current()) {
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
  ): Promise<void> {
    const sequence = this.blank('verifying'),
      current = () => this.current(sequence, saved)
    try {
      const attempt = await this.kernel.beginVerification(
        crypto.randomUUID(),
        current,
        expectedOwner,
      )
      const user = await this.#http.me({ token: saved.token, isCurrent: current })
      if (!current()) return
      if (
        saved.user &&
        (user.user_id !== saved.user.user_id || user.organization_id !== saved.user.organization_id)
      )
        throw new Error('Principal changed')
      this.sessionStore.setUser(user)
      this.sessionStore.bindVerifiedSession(saved.token)
      saved = this.sessionStore.getSnapshot()!
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
        this.schedule(() => this.sync())
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
    if (outcome.state === 'READY') {
      const state = await this.kernel.inspectSession(source.ticket, () =>
        source.isCurrent(source.identity),
      )
      source.context = state.context
      await this.ready(source, this.#snapshot.user!, sequence, true)
      this.schedule(() => this.sync())
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
    if (!this.current(sequence, saved)) return
    this.publish({
      phase: 'ready',
      user,
      context: source.context,
      selectedLocationId: scope.locationId,
      message: online ? null : 'Acceso local verificado hasta el vencimiento de la sesión.',
      sync: online ? 'local' : 'offline',
      identityKey: `${saved.bindingId}:${scope.locationId}`,
    })
    this.armLease(source)
    await this.refresh()
    void inspectLegacyWork(this.options.factory ?? indexedDB)
      .then((present) => {
        if (current()) this.publish({ legacyPresent: present })
      })
      .catch(() => undefined)
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
    const source = this.#active
    if (!source) return
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
    try {
      await this.kernel.inspectSession(source.ticket, () => source.isCurrent(source.identity))
    } catch {
      if (this.#active === source) this.held('takeover')
    }
  }
  async loadLocations(afterId?: string): Promise<void> {
    const sequence = this.#sequence,
      saved = this.sessionStore.getSnapshot(),
      user = this.#snapshot.user
    if (this.#snapshot.phase !== 'selector' || !saved || !user) return
    try {
      const page = await this.#http.locations(
        { token: saved.token, isCurrent: () => this.current(sequence, saved) },
        user.organization_id,
        afterId,
      )
      if (this.current(sequence, saved))
        this.publish({
          locations: page.items,
          nextLocation: page.nextCursor,
          message: 'Selecciona un taller para abrir su información.',
        })
    } catch (error) {
      if (this.current(sequence, saved))
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
    if (saved) await this.verifyStored(saved, locationId)
  }
  async changeWorkshop() {
    const saved = this.sessionStore.getSnapshot()
    if (saved?.user?.location_id === null) {
      const source = this.#active
      const sequence = this.blank('selector')
      if (source) await this.kernel.lockContext(source.ticket).catch(() => undefined)
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
    this.#verifiedOnline = false
    this.#networkSequence++
    this.#push.invalidate()
    this.#incremental.invalidate()
    this.#running = false
    if (this.#timer !== null) clearTimeout(this.#timer)
    this.#timer = null
    const source = this.#active
    if (!source) return
    this.publish({ sync: 'offline' })
    try {
      await this.kernel.continueOffline(source.ticket)
      if (this.#active === source) this.publish({ sync: 'offline' })
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
    const source = this.#active ?? this.#working
    this.blank('locked')
    this.sessionStore.clear()
    if (source) await this.kernel.lockContext(source.ticket).catch(() => undefined)
  }
  async revoke() {
    const source = this.#active
    if (!source) return
    try {
      await this.#http.revoke({
        token: source.bearerToken,
        isCurrent: () => source.isCurrent(source.identity),
      })
      if (this.#active === source) await this.logout()
    } catch {
      if (this.#active === source)
        this.publish({ message: 'No se pudieron revocar las sesiones remotas.' })
    }
  }
  private requireActive() {
    const source = this.#active
    if (!source || !source.isCurrent(source.identity) || this.#snapshot.phase !== 'ready')
      throw new Error('Se requiere una sesión verificada.')
    return source
  }
  async refresh(type?: 'customer' | 'service_order', afterId?: string) {
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
      if (!current()) return
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
    } catch {
      if (current()) this.held('storage_or_fence_failure')
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
  async createCustomer(input: {
    displayName: string
    email?: string | null
    phone?: string | null
  }) {
    const source = this.requireActive()
    await this.repositories.createCustomer(source, input)
    if (this.#active !== source) return
    await this.refresh()
    this.schedule(() => this.sync())
  }
  async createOrder(input: IntakeInput) {
    const source = this.requireActive()
    await this.repositories.createOrder(source, input)
    if (this.#active !== source) return
    await this.refresh()
    this.schedule(() => this.sync())
  }
  async transition(orderId: string, action: OrderAction) {
    const source = this.requireActive()
    await this.repositories.transition(source, orderId, action)
    if (this.#active !== source) return
    await this.refresh()
    await this.timeline(orderId)
    this.schedule(() => this.sync())
  }
  async timeline(orderId: string) {
    const source = this.requireActive(),
      current = () => this.#active === source && source.isCurrent(source.identity)
    const authorizedOrder = await this.kernel.readEntity(
      source.ticket,
      'service_order',
      orderId,
      current,
    )
    if (!authorizedOrder || !current()) return
    const local = await this.repositories.localTimeline(source, orderId)
    if (!current()) return
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
    if (current())
      this.publish({
        events: events.sort((a, b) => a.occurred_at.localeCompare(b.occurred_at)),
        timelineMessage: message,
      })
  }
  async sync(): Promise<void> {
    const source = this.#active
    if (!source || this.#running) return
    if (!this.options.online()) {
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
    try {
      const push = source.context.capabilities.includes('sync.push')
        ? await this.#push.step(networkSession)
        : { state: 'IDLE' }
      if (!current()) return
      if (push.state === 'HELD') {
        this.held(
          'reason' in push ? (push.reason ?? 'verification_required') : 'verification_required',
        )
        return
      }
      const delta = await this.#incremental.step(networkSession)
      if (!current()) return
      if (delta.state === 'HELD' || delta.state === 'BASELINE_REQUIRED') {
        this.held(delta.reason ?? 'verification_required')
        return
      }
      await this.refresh()
      if (!current()) return
      if (delta.state === 'PROGRESSED' || push.state === 'APPLIED') {
        this.schedule(() => this.sync())
        return
      }
      if (delta.state === 'RETRY_LATER' || push.state === 'RETRY_LATER') {
        this.publish({ sync: 'error' })
        this.schedule(
          () => this.sync(),
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
      this.schedule(
        () => this.sync(),
        this.#snapshot.nextRetryAt === null
          ? 30000
          : Math.max(1000, Math.min(30000, this.#snapshot.nextRetryAt - this.#now())),
      )
    } catch {
      if (current()) this.held('storage_or_fence_failure')
    } finally {
      if (current()) this.#running = false
    }
  }
  dispose() {
    this.cancel()
    this.#observer?.unsubscribe()
    this.#observer = null
    this.#listeners.clear()
    this.database.close()
  }
}

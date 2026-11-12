import type { AccessKernel } from '../access-kernel/kernel.js'
import type { KernelDatabase } from '../access-kernel/database.js'
import type { ContextTicket } from '../access-kernel/types.js'
import type { SessionStorageLike } from '../auth/session.js'
import type { CaptureVisitScope } from './capture-visit.js'
import type {
  Channel,
  ContentProjection,
  CaptureCheckpoint,
  CaptureCheckpointCommand,
  CaptureCheckpointResult,
} from '../access-kernel/capture-checkpoint-types.js'
import {
  purgeCaptureContents,
  retireCaptureContents,
  sweepExpiredCaptureContents,
} from '../access-kernel/capture-checkpoint-store.js'
export type { Channel, ContentProjection }
export interface RecoveryContext {
  ticket: ContextTicket
  scope: CaptureVisitScope
  source: object
  isCurrent(): boolean
}
export interface RecoveryPresentation {
  blocked: boolean
  busy: boolean
  message: string | null
}
export interface RecoveryAttempt {
  readonly channel: Channel
  readonly attemptId: string
  readonly generation: string
  readonly checkpointId: string
  readonly scope: CaptureVisitScope
  readonly token: object
}
// Private completion evidence, never a persistence receipt or durable metadata.
type CompletedCheckpointResult = CaptureCheckpointResult & { admissionCompleted?: true }
interface Options {
  kernel: Pick<AccessKernel, 'checkpointCapture'>
  db: KernelDatabase
  storage: SessionStorageLike
  now: () => number
  current: () => RecoveryContext | null
  onLocalAdmissionComplete?: (source: object) => void
  onChange: () => void
}
const hintKey = 'ocwp.capture-checkpoint.v1',
  cleanupKey = 'ocwp.capture-cleanup.v1'
const messages = {
  unsupported:
    'Este borrador requiere una versión compatible de la aplicación. Se conserva en este dispositivo, pero no se puede recuperar ni enviar con esta versión.',
  persisting: 'Guardando el borrador en este dispositivo…',
  saved: 'Borrador guardado para recuperar al recargar esta sesión.',
  failed:
    'No se envió la captura. No se pudo asegurar su recuperación local; conserva este formulario.',
  protected:
    'Hay una captura anterior pendiente de confirmar. No la repitas; verifica el estado del taller antes de continuar.',
  unavailable:
    'La recuperación de capturas no está disponible en esta sesión. Cierra sesión e inicia una nueva para continuar; esto no confirma los envíos anteriores.',
  cleanup:
    'No se pudo confirmar la eliminación de los borradores locales. Sus datos podrían permanecer en este dispositivo.',
  oversize:
    'El borrador supera el límite local de 64 KiB. Conserva el formulario y reduce su tamaño antes de guardar.',
  savedFailure:
    'La captura se guardó localmente, pero no se pudo actualizar su protección de recuperación. No la repitas.',
  notSavedFailure:
    'La captura no se guardó, pero no se pudo actualizar su protección de recuperación. Conserva este formulario; no lo envíes de nuevo desde esta vista.',
}
const channels: Channel[] = ['customer', 'order']
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/
const scopeIdentity = (s: CaptureVisitScope) =>
  JSON.stringify([
    s.apiRealm,
    s.organizationId,
    s.userId,
    s.selectedLocationId,
    s.datasetIncarnation,
    s.authorizationEpoch,
    s.policyRevision,
    [...s.capabilities].sort(),
    s.sessionBindingId,
  ])
const sameScope = (a: CaptureVisitScope, b: CaptureVisitScope) =>
  scopeIdentity(a) === scopeIdentity(b)
interface LocalChannel {
  presentation: RecoveryPresentation
  queued: ContentProjection | null
  running: Promise<void> | null
  reserving: boolean
  attempt: RecoveryAttempt | null
  settlement: { outcome: 'saved' | 'not_saved'; content: ContentProjection | null } | null
  edit: number
  latest: ContentProjection | null
}
const local = (): LocalChannel => ({
  presentation: { blocked: true, busy: false, message: messages.unavailable },
  queued: null,
  running: null,
  reserving: false,
  attempt: null,
  settlement: null,
  edit: 0,
  latest: null,
})
/** Persistence only: this owner never invokes or retries a business command. */
export class CaptureRecovery {
  private head: CaptureCheckpoint | null = null
  private scope: CaptureVisitScope | null = null
  private active = false
  private closed = false
  private sequence = 0
  private lifetime = 0
  private clean = true
  private unsupported = false
  private cleanupFailures = new Set<string>()
  private forms: Record<Channel, LocalChannel> = { customer: local(), order: local() }
  constructor(private readonly options: Options) {}
  getNotice(): string | null {
    return this.cleanupFailures.size ? messages.cleanup : null
  }
  private cleanupFailed(key: string): void {
    this.cleanupFailures.add(key)
    this.clean = false
    channels.forEach((ch) => this.fail(ch, messages.cleanup))
  }
  private cleanupCompleted(key: string): void {
    this.cleanupFailures.delete(key)
    this.clean = this.cleanupFailures.size === 0
    this.notify()
  }
  snapshot(): Record<Channel, RecoveryPresentation> {
    return {
      customer: { ...this.forms.customer.presentation },
      order: { ...this.forms.order.presentation },
    }
  }
  hasUnsent(): boolean {
    if (this.closed) return false
    return (
      this.unsupported ||
      channels.some(
        (ch) =>
          !!this.forms[ch].attempt ||
          this.head?.[ch].state === 'PROTECTED' ||
          this.head?.[ch].state === 'UNAVAILABLE',
      )
    )
  }
  canSubmit(channel: Channel): boolean {
    const f = this.forms[channel]
    return this.active && !this.closed && !f.presentation.blocked && !f.reserving && !f.attempt
  }
  private localAdmissionCompleted(
    context: RecoveryContext,
    result: CompletedCheckpointResult,
  ): void {
    if (result.admissionCompleted && this.active && this.valid(context))
      this.options.onLocalAdmissionComplete?.(context.source)
  }
  private notify(): void {
    this.options.onChange()
  }
  private valid(c: RecoveryContext): boolean {
    const now = this.options.current()
    return (
      !this.closed && c.isCurrent() && now?.source === c.source && sameScope(now.scope, c.scope)
    )
  }
  private async command(
    c: RecoveryContext,
    command: CaptureCheckpointCommand,
  ): Promise<CompletedCheckpointResult> {
    if (!this.valid(c)) return { kind: 'refused', reason: 'unavailable' }
    try {
      const result = await this.options.kernel.checkpointCapture(c.ticket, command, () =>
        this.valid(c),
      )
      return { ...result, admissionCompleted: true }
    } catch {
      return { kind: 'refused', reason: 'unavailable' }
    }
  }
  private fail(channel: Channel, message: string = messages.failed): void {
    if (message === messages.unsupported) this.unsupported = true
    this.forms[channel].presentation = { blocked: true, busy: false, message }
    this.notify()
  }
  private accept(head: CaptureCheckpoint, channel?: Channel): void {
    if (channel && this.head?.generation === head.generation)
      this.head = {
        ...this.head,
        [channel]: head[channel],
        observedAt: Math.max(this.head.observedAt, head.observedAt),
      }
    else this.head = head
  }
  async ready(allowEnroll: boolean): Promise<Partial<Record<Channel, ContentProjection>>> {
    const c = this.options.current(),
      seq = ++this.sequence
    this.active = false
    if (!c || this.closed || !this.clean) return {}
    let id: string,
      enroll = false
    try {
      const raw = this.options.storage.getItem(hintKey)
      const hint = raw ? JSON.parse(raw) : null
      if (
        hint?.format === 1 &&
        hint.sessionBindingId === c.scope.sessionBindingId &&
        typeof hint.checkpointId === 'string' &&
        uuid.test(hint.checkpointId)
      )
        id = hint.checkpointId
      else if (
        allowEnroll &&
        (!hint ||
          (hint.format === 1 &&
            typeof hint.sessionBindingId === 'string' &&
            uuid.test(hint.checkpointId) &&
            hint.sessionBindingId !== c.scope.sessionBindingId))
      ) {
        id = crypto.randomUUID()
        this.options.storage.setItem(
          hintKey,
          JSON.stringify({
            format: 1,
            sessionBindingId: c.scope.sessionBindingId,
            checkpointId: id,
          }),
        )
        enroll = true
      } else return {}
    } catch {
      return {}
    }
    const prior = this.head,
      edits = channels.map((ch) => this.forms[ch].edit)
    let result = await this.command(
      c,
      enroll
        ? { kind: 'enroll', checkpointId: id, scope: c.scope, generation: crypto.randomUUID() }
        : { kind: 'load', checkpointId: id, scope: c.scope },
    )
    if (!this.valid(c) || seq !== this.sequence) return {}
    if (result.kind === 'scope_changed')
      result = await this.command(c, {
        kind: 'retireScope',
        checkpointId: id,
        scope: c.scope,
        generation: result.checkpoint.generation,
        nextGeneration: crypto.randomUUID(),
      })
    if (!this.valid(c) || seq !== this.sequence) return {}
    if (result.kind === 'refused' && result.reason === 'unsupported_format') {
      // Validated metadata is retained only for exact-generation discard/leave protection.
      // Opaque payload never enters the runtime projection and admission stays inactive.
      this.head = result.checkpoint
      this.scope = structuredClone(c.scope)
    }
    if ((result.kind !== 'ack' && result.kind !== 'loaded') || result.checkpoint.closed) {
      channels.forEach((ch) =>
        this.fail(
          ch,
          result.kind === 'refused' && result.reason === 'unsupported_format'
            ? messages.unsupported
            : messages.unavailable,
        ),
      )
      return {}
    }
    this.unsupported = false
    const continued =
      prior?.generation === result.checkpoint.generation &&
      this.scope !== null &&
      sameScope(this.scope, c.scope)
    const unchanged = channels.map((ch, index) => this.forms[ch].edit === edits[index])
    if (!continued)
      channels.forEach((ch) => {
        this.forms[ch] = local()
      })
    this.accept(result.checkpoint)
    this.scope = structuredClone(c.scope)
    this.active = true
    const restored: Partial<Record<Channel, ContentProjection>> = {}
    for (const [index, ch] of channels.entries()) {
      if (!this.valid(c) || seq !== this.sequence) return {}
      const f = this.forms[ch],
        state = this.head![ch].state
      const previous = f.presentation
      f.presentation = {
        blocked: state === 'PROTECTED' || state === 'UNAVAILABLE',
        busy: false,
        message: state === 'PROTECTED' || state === 'UNAVAILABLE' ? messages.protected : null,
      }
      if (
        continued &&
        previous.blocked &&
        !f.attempt &&
        state !== 'PROTECTED' &&
        state !== 'UNAVAILABLE'
      )
        f.presentation = previous
      if (!continued && result.kind === 'loaded' && unchanged[index] && state === 'UNSENT') {
        const row = result.contents[ch]
        if (row && row.channel === ch) {
          restored[ch] = structuredClone(
            row.channel === 'customer'
              ? { channel: row.channel, draft: row.draft }
              : {
                  channel: row.channel,
                  draft: row.draft,
                  retainedSelection: row.retainedSelection,
                },
          )
          f.presentation.message = messages.saved
        }
      }
      if (continued && f.attempt && f.settlement)
        await this.settle(f.attempt, f.settlement.outcome, f.settlement.content)
    }
    this.notify()
    return this.valid(c) && seq === this.sequence ? restored : {}
  }
  edit(channel: Channel, projection: ContentProjection): void {
    if (this.closed) return
    const f = this.forms[channel]
    f.edit++
    f.latest = structuredClone(projection)
    if (
      !this.active ||
      this.closed ||
      f.attempt ||
      f.reserving ||
      this.head?.[channel].state === 'PROTECTED'
    )
      return
    if (projection.channel !== channel) return
    f.queued = structuredClone(projection)
    if (f.presentation.blocked && f.presentation.message !== messages.oversize) return
    f.presentation = { blocked: false, busy: true, message: messages.persisting }
    this.notify()
    this.drain(channel)
  }
  private drain(channel: Channel): void {
    const f = this.forms[channel]
    if (
      f.running ||
      !f.queued ||
      !this.active ||
      this.closed ||
      f.attempt ||
      f.presentation.blocked
    )
      return
    f.running = this.flush(channel).finally(() => {
      f.running = null
      // A notification can queue an edit after flush's last loop check but before
      // this promise settles. It still needs a save without another UI event.
      if (this.forms[channel] === f) this.drain(channel)
    })
  }
  private async flush(channel: Channel): Promise<void> {
    const life = this.lifetime
    const f = this.forms[channel]
    while (f.queued && this.active && !this.closed && !f.attempt) {
      const content = f.queued
      f.queued = null
      const head = this.head,
        c = this.options.current()
      if (!head || !c) {
        this.fail(channel)
        return
      }
      const result = await this.command(c, {
        kind: 'save',
        checkpointId: head.checkpointId,
        generation: head.generation,
        scope: c.scope,
        channel,
        expectedRevision: head[channel].revision,
        content,
      })
      if (this.closed || life !== this.lifetime) return
      if (result.kind !== 'ack' || !this.valid(c)) {
        this.fail(
          channel,
          result.kind === 'refused' && result.reason === 'unsupported_format'
            ? messages.unsupported
            : result.kind === 'refused' && result.reason === 'oversize'
              ? messages.oversize
              : messages.failed,
        )
        f.queued = null
        this.localAdmissionCompleted(c, result)
        return
      }
      this.accept(result.checkpoint, channel)
      f.presentation = {
        blocked: false,
        busy: !!f.queued,
        message: f.queued ? messages.persisting : messages.saved,
      }
      this.notify()
      this.localAdmissionCompleted(c, result)
    }
  }
  async protect(channel: Channel): Promise<RecoveryAttempt | null> {
    if (!this.canSubmit(channel)) return null
    const life = this.lifetime
    const f = this.forms[channel]
    f.reserving = true
    while (f.running) await f.running
    const c = this.options.current(),
      head = this.head
    if (
      life !== this.lifetime ||
      !this.active ||
      this.closed ||
      f.presentation.blocked ||
      !head ||
      !c
    ) {
      f.reserving = false
      return null
    }
    const attempt: RecoveryAttempt = Object.freeze({
      channel,
      attemptId: crypto.randomUUID(),
      generation: head.generation,
      checkpointId: head.checkpointId,
      scope: structuredClone(c.scope),
      token: {},
    })
    f.presentation = { blocked: true, busy: true, message: messages.persisting }
    this.notify()
    const result = await this.command(c, {
      kind: 'protect',
      checkpointId: head.checkpointId,
      generation: head.generation,
      scope: c.scope,
      channel,
      expectedRevision: head[channel].revision,
      attemptId: attempt.attemptId,
    })
    f.reserving = false
    if (life !== this.lifetime) return null
    if (result.kind !== 'ack' || !this.valid(c) || !this.active) {
      this.fail(
        channel,
        result.kind === 'refused' && result.reason === 'unsupported_format'
          ? messages.unsupported
          : messages.failed,
      )
      this.localAdmissionCompleted(c, result)
      return null
    }
    this.accept(result.checkpoint, channel)
    f.attempt = attempt
    f.presentation = { blocked: true, busy: false, message: messages.protected }
    this.notify()
    this.localAdmissionCompleted(c, result)
    return this.valid(c) && this.active && f.attempt === attempt ? attempt : null
  }
  async settle(
    attempt: RecoveryAttempt,
    outcome: 'saved' | 'not_saved',
    projection: ContentProjection | null,
  ): Promise<boolean> {
    const life = this.lifetime
    const f = this.forms[attempt.channel]
    if (this.closed || f.attempt !== attempt || this.head?.generation !== attempt.generation)
      return false
    const edit = f.edit
    f.settlement = { outcome, content: projection ? structuredClone(projection) : null }
    const c = this.options.current(),
      head = this.head
    if (!c || !this.active || !sameScope(c.scope, attempt.scope)) {
      this.fail(
        attempt.channel,
        outcome === 'saved' ? messages.savedFailure : messages.notSavedFailure,
      )
      return false
    }
    const result = await this.command(c, {
      kind: 'settle',
      checkpointId: attempt.checkpointId,
      generation: attempt.generation,
      scope: c.scope,
      channel: attempt.channel,
      expectedRevision: head[attempt.channel].revision,
      attemptId: attempt.attemptId,
      outcome,
      content: f.settlement.content,
    })
    if (life !== this.lifetime || this.closed || f.attempt !== attempt) return false
    if (result.kind !== 'ack' || !this.valid(c)) {
      this.fail(
        attempt.channel,
        outcome === 'saved' ? messages.savedFailure : messages.notSavedFailure,
      )
      this.localAdmissionCompleted(c, result)
      return false
    }
    this.accept(result.checkpoint, attempt.channel)
    f.attempt = null
    f.settlement = null
    f.presentation = { blocked: false, busy: false, message: projection ? messages.saved : null }
    if (f.edit !== edit)
      f.presentation = { blocked: false, busy: true, message: messages.persisting }
    this.notify()
    if (f.edit !== edit && f.latest) this.edit(attempt.channel, f.latest)
    this.localAdmissionCompleted(c, result)
    return true
  }
  suspend(): void {
    this.active = false
    this.sequence++
    this.notify()
  }
  /** Forget private visit content without permanently closing this verified binding. */
  async retireVisit(): Promise<void> {
    const head = this.head,
      scope = this.scope
    const life = ++this.lifetime
    this.sequence++
    this.active = false
    this.forms = { customer: local(), order: local() }
    let hintRemoved = true
    try {
      this.options.storage.removeItem(hintKey)
    } catch {
      hintRemoved = false
    }
    const failureKey = head ? `retire:${head.checkpointId}:${head.generation}` : 'retire:missing'
    if (!hintRemoved) this.cleanupFailed(failureKey)
    this.notify()
    if (!head || !scope || this.closed) return
    try {
      const result = await retireCaptureContents(
        this.options.db,
        head.checkpointId,
        head.generation,
        crypto.randomUUID(),
      )
      if (result.kind !== 'retired') throw Error('unavailable')
      if (life !== this.lifetime || this.closed) return
      this.head = result.checkpoint
      if (!hintRemoved) return
      this.options.storage.setItem(
        hintKey,
        JSON.stringify({
          format: 1,
          checkpointId: head.checkpointId,
          sessionBindingId: scope.sessionBindingId,
        }),
      )
      this.unsupported = false
      this.cleanupCompleted(failureKey)
    } catch {
      if (life === this.lifetime && !this.closed) this.cleanupFailed(failureKey)
    }
  }
  startVisit(): void {
    this.unsupported = false
    this.lifetime++
    this.sequence++
    this.closed = false
    this.active = false
    this.head = null
    this.scope = null
    this.forms = { customer: local(), order: local() }
    this.notify()
  }
  dispose(): void {
    this.unsupported = false
    this.lifetime++
    this.closed = true
    this.active = false
    this.sequence++
    channels.forEach((ch) => {
      this.forms[ch] = local()
    })
  }
  close(): void {
    const head = this.head
    this.dispose()
    if (!head) {
      // Logout can occur before any verified hydration. Only inspect marker metadata;
      // never load a private payload or grant recovery from this deletion path.
      try {
        const raw = this.options.storage.getItem(hintKey)
        if (raw === null) return
        const hint = JSON.parse(raw)
        if (
          hint?.format !== 1 ||
          !uuid.test(hint.checkpointId) ||
          typeof hint.sessionBindingId !== 'string'
        )
          throw Error('invalid locator')
        void this.purgeUnhydrated(hint.checkpointId)
      } catch {
        this.cleanupFailed('unhydrated-locator')
      }
      return
    }
    this.requestPurge(head.checkpointId, head.generation)
  }
  private async purgeUnhydrated(checkpointId: string): Promise<void> {
    try {
      const metadata = await this.options.db.captureCheckpoints.get(checkpointId)
      if (!metadata || !uuid.test(metadata.generation)) throw Error('missing locator')
      this.requestPurge(checkpointId, metadata.generation)
    } catch {
      // Without a readable generation no unexpired retry can be promised. The
      // content-free warning remains; app-open expiry maintenance is independent.
      this.cleanupFailed('unhydrated-locator')
    }
  }
  private requestPurge(checkpointId: string, generation: string): void {
    const locator = { format: 1, checkpointId, generation }
    try {
      const old = this.options.storage.getItem(cleanupKey)
      if (!old) this.options.storage.setItem(cleanupKey, JSON.stringify(locator))
    } catch {
      this.cleanupFailed(`${locator.checkpointId}:${locator.generation}`)
    }
    void this.purge(locator)
  }
  private async purge(locator: { checkpointId: string; generation: string }): Promise<boolean> {
    try {
      const result = await purgeCaptureContents(
        this.options.db,
        locator.checkpointId,
        locator.generation,
      )
      if (result.kind !== 'complete') throw Error('unavailable')
      const raw = this.options.storage.getItem(cleanupKey),
        saved = raw ? JSON.parse(raw) : null
      if (saved?.checkpointId === locator.checkpointId && saved.generation === locator.generation)
        this.options.storage.removeItem(cleanupKey)
      this.cleanupCompleted(`${locator.checkpointId}:${locator.generation}`)
      return true
    } catch {
      this.cleanupFailed(`${locator.checkpointId}:${locator.generation}`)
      return false
    }
  }
  async cleanup(): Promise<void> {
    try {
      const raw = this.options.storage.getItem(cleanupKey),
        locator = raw ? JSON.parse(raw) : null
      if (
        locator &&
        (locator.format !== 1 || !uuid.test(locator.checkpointId) || !uuid.test(locator.generation))
      )
        throw Error('unavailable')
      if (locator) await this.purge(locator)
    } catch {
      this.cleanupFailed('locator')
    }
    try {
      if (
        (await sweepExpiredCaptureContents(this.options.db, this.options.now())).kind !== 'complete'
      )
        throw Error('unavailable')
      this.cleanupCompleted('sweep')
    } catch {
      this.cleanupFailed('sweep')
    }
  }
}

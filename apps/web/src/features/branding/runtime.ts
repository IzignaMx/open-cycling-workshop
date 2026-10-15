import type { ContextTicket, VerifiedAccessContext } from '../../access-kernel/types.js'
import type { BrandingSnapshotRepository } from '../../branding/cache.js'
import type { BrandingProfile } from './contracts.js'
import { BrandingHttpError, type BrandingCapture, type BrandingTransport } from './transport.js'

export interface BrandingRuntimeCapture extends BrandingCapture {
  readonly ticket: ContextTicket
  readonly context: VerifiedAccessContext
  readonly binding: string
  readonly online: boolean
}
export interface BrandingDisplaySnapshot {
  profile: BrandingProfile | null
  cached: boolean
  loading: boolean
  cacheError: boolean
  message: string | null
}
interface Options {
  capture(): BrandingRuntimeCapture | null
  validate(source: BrandingRuntimeCapture): Promise<boolean>
  repository: Pick<BrandingSnapshotRepository, 'read' | 'write'>
  transport: BrandingTransport
  refused(source: BrandingRuntimeCapture, status: 401 | 403): void
  now(): number
}
function revisionIdentity(profile: BrandingProfile): string {
  return JSON.stringify({
    ...profile,
    logo_state: undefined,
    logo_diagnostic: undefined,
    logo: profile.logo ? { ...profile.logo, png_base64: undefined } : null,
  })
}
const empty = (): BrandingDisplaySnapshot => ({
  profile: null,
  cached: false,
  loading: false,
  cacheError: false,
  message: null,
})
/** Runtime-owned admitted display cache. Never owns or creates an admission. */
export class BrandingDisplayController {
  #snapshot = empty()
  #listeners = new Set<() => void>()
  #binding = ''
  #generation = 0
  #flight: { followupAllowed: boolean; queued: boolean } | null = null
  #abort = new AbortController()
  #lastRefresh = -Infinity
  constructor(private readonly options: Options) {}
  getSnapshot = () => this.#snapshot
  subscribe = (listener: () => void) => {
    this.#listeners.add(listener)
    return () => this.#listeners.delete(listener)
  }
  private publish(patch: Partial<BrandingDisplaySnapshot>) {
    this.#snapshot = Object.freeze({ ...this.#snapshot, ...patch })
    for (const listener of this.#listeners) listener()
  }
  clear() {
    this.#generation++
    this.#abort.abort()
    this.#abort = new AbortController()
    this.#binding = ''
    this.#flight = null
    this.#lastRefresh = -Infinity
    this.#snapshot = Object.freeze(empty())
    for (const listener of this.#listeners) listener()
  }
  reconcile() {
    const source = this.options.capture()
    if (!source) {
      if (this.#binding || this.#snapshot.profile) this.clear()
      return
    }
    if (source.binding !== this.#binding) {
      this.clear()
      this.#binding = source.binding
      void this.refresh(true)
    }
  }
  async refresh(force = false): Promise<void> {
    await this.refreshOnce(force, true)
  }
  private async refreshOnce(force: boolean, followupAllowed: boolean): Promise<void> {
    const source = this.options.capture()
    if (!source) {
      this.clear()
      return
    }
    if (source.binding !== this.#binding) {
      this.clear()
      this.#binding = source.binding
    }
    const now = this.options.now()
    if (this.#flight) {
      if (force && this.#flight.followupAllowed) this.#flight.queued = true
      return
    }
    if (!force && now >= this.#lastRefresh && now - this.#lastRefresh < 30000) return
    const flight = { followupAllowed, queued: false },
      generation = this.#generation,
      abort = this.#abort
    const current = () =>
      generation === this.#generation &&
      !abort.signal.aborted &&
      source.isCurrent() &&
      this.options.capture()?.binding === source.binding
    const capture = {
      ...source,
      signal: source.signal ? AbortSignal.any([source.signal, abort.signal]) : abort.signal,
      isCurrent: current,
    }
    this.#flight = flight
    this.#lastRefresh = now
    this.publish({ loading: true })
    try {
      if (!(await this.options.validate(source))) {
        if (current()) this.clear()
        return
      }
      if (!current()) return
      if (!this.#snapshot.profile) {
        try {
          const cached = await this.options.repository.read(
            source.ticket,
            source.context,
            this.options.now(),
          )
          if (!current()) return
          if (cached && this.acceptable(cached)) this.publish({ profile: cached, cached: true })
        } catch {
          if (!current()) return
          this.publish({
            cacheError: true,
            message: 'No se pudo consultar la copia local de la marca.',
          })
        }
      }
      if (!source.online) {
        if (current())
          this.publish({
            cached: !!this.#snapshot.profile,
            message: this.#snapshot.profile
              ? 'Configuración del taller verificada anteriormente; disponible sin conexión.'
              : 'No hay una configuración compartida verificada para esta sesión.',
          })
        return
      }
      const profile = await this.options.transport.read(capture)
      if (!current() || !(await this.options.validate(source)) || !current()) return
      await this.accept(source, profile, current)
    } catch (error) {
      if (!current()) return
      if (error instanceof BrandingHttpError && (error.status === 401 || error.status === 403)) {
        this.clear()
        this.options.refused(source, error.status)
      } else
        this.publish({
          message:
            'No se pudo actualizar la configuración compartida. La última copia verificada se conserva durante esta sesión.',
        })
    } finally {
      if (this.#flight === flight) {
        if (current()) this.publish({ loading: false })
        if (this.#flight === flight) {
          this.#flight = null
          // Honor one coalesced explicit request with fresh admission/time.
          // The trailing flight cannot queue another, even if notifications
          // keep requesting refresh. A null cache result alone never retries.
          if (current() && flight.queued) void this.refreshOnce(true, false)
        }
      }
    }
  }
  private acceptable(profile: BrandingProfile): boolean {
    const existing = this.#snapshot.profile
    return (
      !existing ||
      existing.version < profile.version ||
      (existing.version === profile.version &&
        revisionIdentity(existing) === revisionIdentity(profile))
    )
  }
  private async accept(
    source: BrandingRuntimeCapture,
    profile: BrandingProfile,
    current: () => boolean,
  ) {
    if (
      !current() ||
      !source.context.capabilities.includes('branding.read') ||
      profile.organization_id !== source.organizationId ||
      profile.location_id !== source.locationId ||
      profile.dataset_incarnation !== source.datasetIncarnation
    )
      return
    if (!this.acceptable(profile)) return
    let cacheError = false
    try {
      const stored = await this.options.repository.write(
        source.ticket,
        source.context,
        profile,
        this.options.now(),
      )
      if (!stored) return
    } catch {
      cacheError = true
    }
    if (!current() || !(await this.options.validate(source)) || !current()) return
    if (!this.acceptable(profile)) return
    this.publish({
      profile,
      cached: false,
      cacheError,
      message: cacheError
        ? 'Configuración aplicada. No se pudo guardar la copia sin conexión; el trabajo pendiente no cambió.'
        : profile.logo_state === 'unavailable'
          ? 'El logo compartido no está disponible. Se muestra el nombre del taller.'
          : null,
    })
  }
  /** A confirmed save is refresh input only under this exact operational admission. */
  async confirmed(profile: BrandingProfile): Promise<void> {
    const source = this.options.capture()
    if (!source || !source.online || source.binding !== this.#binding) return
    const generation = this.#generation
    const current = () =>
      generation === this.#generation &&
      source.isCurrent() &&
      this.options.capture()?.binding === source.binding
    if ((await this.options.validate(source)) && current())
      await this.accept(source, profile, current)
  }
}

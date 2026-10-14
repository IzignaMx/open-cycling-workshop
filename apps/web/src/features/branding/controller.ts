import type { WorkshopController } from '../../runtime/controller.js'
import type { AccountAccessSnapshot, AccountCapture } from '../../runtime/account-access.js'
import { hasCapability } from '../../auth/capabilities.js'
import {
  AdministrationHttpError,
  createAdministrationTransport,
} from '../administration/transport.js'
import type { LocationResponse } from '../administration/contracts.js'
import type { BrandingProfile, BrandingPutRequest } from './contracts.js'
import {
  BrandingHttpError,
  createBrandingTransport,
  type BrandingCapture,
  type BrandingTransport,
} from './transport.js'

type Runtime = Pick<
  WorkshopController,
  | 'getAccountSnapshot'
  | 'subscribeAccount'
  | 'captureAccount'
  | 'verifyAccount'
  | 'invalidateBrandingAccount'
  | 'branding'
>
export interface BrandingEditorSnapshot {
  account: AccountAccessSnapshot
  generation: number
  locations: LocationResponse[]
  nextLocation: string | null
  reviewId: number
  targetId: string | null
  profile: BrandingProfile | null
  busy: boolean
  result: 'idle' | 'success' | 'error' | 'uncertain'
  message: string | null
}
/** Connected-only editor. Immutable review versions; no journal, cache admission or retries. */
export class BrandingEditorController {
  #snapshot: BrandingEditorSnapshot
  #listeners = new Set<() => void>()
  #generation = 0
  #read = 0
  #directory = 0
  #command = false
  #abort = new AbortController()
  #unsubscribe: () => void
  constructor(
    private readonly runtime: Runtime,
    private readonly transport?: BrandingTransport,
  ) {
    this.#snapshot = this.empty()
    this.#unsubscribe = runtime.subscribeAccount(() => {
      this.#abort.abort()
      this.#abort = new AbortController()
      this.#generation++
      this.#read++
      this.#directory++
      this.#snapshot = this.empty()
      for (const listener of this.#listeners) listener()
    })
  }
  private empty(): BrandingEditorSnapshot {
    return {
      account: this.runtime.getAccountSnapshot(),
      generation: this.#generation,
      locations: [],
      nextLocation: null,
      reviewId: 0,
      targetId: null,
      profile: null,
      busy: false,
      result: 'idle',
      message: null,
    }
  }
  getSnapshot = () => this.#snapshot
  subscribe = (listener: () => void) => {
    this.#listeners.add(listener)
    return () => this.#listeners.delete(listener)
  }
  private publish(patch: Partial<BrandingEditorSnapshot>) {
    this.#snapshot = Object.freeze({ ...this.#snapshot, ...patch })
    for (const listener of this.#listeners) listener()
  }
  verify = () => this.runtime.verifyAccount()
  private capture(locationId: string): { account: AccountCapture; request: BrandingCapture } {
    const account = this.runtime.captureAccount(),
      generation = this.#generation,
      signal = AbortSignal.any([account.signal, this.#abort.signal])
    if (
      !locationId ||
      locationId.length > 36 ||
      locationId.includes('\0') ||
      (account.user.location_id !== null && account.user.location_id !== locationId)
    )
      throw new BrandingHttpError('invalid_request')
    return {
      account,
      request: {
        token: account.token,
        organizationId: account.user.organization_id,
        locationId,
        datasetIncarnation: null,
        signal,
        isCurrent: () => !signal.aborted && generation === this.#generation && account.isCurrent(),
      },
    }
  }
  private http(account: AccountCapture) {
    return (
      this.transport ??
      createBrandingTransport({ apiRealm: account.apiRealm, fetch: globalThis.fetch })
    )
  }
  private failed(account: AccountCapture, request: BrandingCapture, error: unknown, write = false) {
    if (!request.isCurrent()) return
    if (error instanceof BrandingHttpError && (error.status === 401 || error.status === 403)) {
      this.runtime.branding.clear()
      this.runtime.invalidateBrandingAccount(account, error.status)
      return
    }
    const definite =
      error instanceof BrandingHttpError &&
      (error.code === 'invalid_request' ||
        (error.status !== null &&
          error.status >= 400 &&
          error.status < 500 &&
          error.code !== 'invalid_response'))
    this.publish({
      result: write && !definite ? 'uncertain' : 'error',
      message:
        error instanceof BrandingHttpError && error.status === 409
          ? 'La marca cambió. Tu borrador se conserva; vuelve a cargar y revisa la versión antes de guardar.'
          : write && !definite
            ? 'Resultado sin confirmar. Tu borrador se conserva; consulta el taller antes de decidir si debes enviar otro cambio.'
            : 'No se pudo completar la acción. Revisa los datos, los permisos y la conexión.',
    })
  }
  async loadLocations(afterId?: string): Promise<void> {
    let account: AccountCapture
    try {
      account = this.runtime.captureAccount()
    } catch {
      return
    }
    if (!hasCapability(account.user.capabilities, 'locations.read')) return
    const generation = this.#generation,
      page = ++this.#directory
    try {
      const http = createAdministrationTransport({
        apiRealm: account.apiRealm,
        fetch: globalThis.fetch,
      })
      const result = await http.locations(account, afterId === undefined ? {} : { afterId })
      if (account.isCurrent() && generation === this.#generation && page === this.#directory)
        this.publish({ locations: result.items, nextLocation: result.next_cursor })
    } catch (error) {
      if (account.isCurrent() && generation === this.#generation) {
        if (
          error instanceof AdministrationHttpError &&
          (error.status === 401 || error.status === 403)
        ) {
          this.runtime.branding.clear()
          this.runtime.invalidateBrandingAccount(account, error.status)
        } else this.publish({ message: 'No se pudo consultar el directorio de talleres.' })
      }
    }
  }
  async load(locationId: string): Promise<void> {
    let source: ReturnType<BrandingEditorController['capture']>
    try {
      source = this.capture(locationId)
    } catch {
      return
    }
    if (!source.account.user.capabilities.includes('branding.read')) return
    const page = ++this.#read
    this.publish({
      targetId: locationId,
      reviewId: page,
      profile: null,
      message: null,
      result: 'idle',
    })
    try {
      const profile = await this.http(source.account).read(source.request)
      if (source.request.isCurrent() && page === this.#read) this.publish({ profile })
    } catch (error) {
      if (page === this.#read) this.failed(source.account, source.request, error)
    }
  }
  async save(locationId: string, input: BrandingPutRequest): Promise<BrandingProfile | undefined> {
    if (this.#command) return
    let source: ReturnType<BrandingEditorController['capture']>
    try {
      source = this.capture(locationId)
    } catch {
      return
    }
    if (!source.account.user.capabilities.includes('branding.write')) return
    const payload = structuredClone(input)
    this.#command = true
    this.publish({ busy: true, result: 'idle', message: 'Guardando la marca compartida…' })
    try {
      const profile = await this.http(source.account).save(source.request, payload)
      if (!source.request.isCurrent()) return
      if (source.account.user.capabilities.includes('branding.read')) {
        this.publish({ targetId: locationId, profile })
        await this.runtime.branding.confirmed(profile)
      }
      if (!source.request.isCurrent()) return
      this.publish({
        result: 'success',
        message:
          'Marca compartida guardada. Otros dispositivos la verán al actualizar o volver a conectarse.',
      })
      return source.request.isCurrent() ? profile : undefined
    } catch (error) {
      this.failed(source.account, source.request, error, true)
    } finally {
      this.#command = false
      if (source.request.isCurrent()) this.publish({ busy: false })
    }
  }
  dispose() {
    this.#abort.abort()
    this.#unsubscribe()
    this.#listeners.clear()
  }
}

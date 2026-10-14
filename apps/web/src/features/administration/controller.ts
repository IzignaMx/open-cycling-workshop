import type { WorkshopController } from '../../runtime/controller.js'
import type { AccountAccessSnapshot, AccountCapture } from '../../runtime/account-access.js'
import type {
  CreateUserRequest,
  LocationResponse,
  OwnerHint,
  PatchUserRequest,
  RoleCatalogResponse,
  UserPageOptions,
  UserResponse,
} from './contracts.js'
import { hasCapability, isSelfSecurityChange, ownerHintFromPage, canAdminister } from './model.js'
import {
  AdministrationHttpError,
  createAdministrationTransport,
  type AdministrationTransport,
} from './transport.js'

type Runtime = Pick<
  WorkshopController,
  | 'subscribeAccount'
  | 'getAccountSnapshot'
  | 'verifyAccount'
  | 'captureAccount'
  | 'invalidateAccount'
  | 'suspendAccountCommand'
  | 'completeAccountCommand'
  | 'updateAccountName'
  | 'logout'
>
export interface AdministrationSnapshot {
  account: AccountAccessSnapshot
  users: UserResponse[]
  usersNext: string | null
  locations: LocationResponse[]
  locationsNext: string | null
  catalog: RoleCatalogResponse | null
  ownerHint: OwnerHint
  ownerNext: string | null
  busy: boolean
  message: string | null
  result: 'idle' | 'success' | 'uncertain' | 'error'
  generation: number
}
const cleared = () => ({
  users: [],
  usersNext: null,
  locations: [],
  locationsNext: null,
  catalog: null,
  ownerHint: 'unknown' as const,
  ownerNext: null,
  busy: false,
  message: null,
  result: 'idle' as const,
})
const uncertain = 'Resultado sin confirmar; revisa el estado antes de volver a enviar.'
const safeErrors: Record<string, string> = {
  stale_user_version:
    'La cuenta cambió. Conserva tu borrador, actualiza la lista y revisa la versión antes de volver a enviar.',
  last_owner: 'Debe permanecer al menos una persona propietaria activa con todos los permisos.',
  invalid_owner:
    'La designación de propietario requiere ámbito de organización y todos los permisos.',
  username_conflict: 'Ese nombre de usuario ya está en uso.',
  account_conflict: 'La cuenta entró en conflicto. Actualiza la lista antes de continuar.',
  user_not_found: 'La cuenta ya no está disponible en tu ámbito.',
  validation_error: 'Revisa los campos indicados y vuelve a introducir cualquier contraseña.',
  invalid_request: 'Revisa los campos antes de enviar.',
  client_upgrade_required:
    'Actualiza la aplicación antes de continuar; no se enviará con un protocolo anterior.',
  invalid_credentials: 'La contraseña actual no es válida. Vuelve a introducirla.',
}
/** Volatile connected directory state. No persistence, credentials or command retry queue. */
export class AdministrationController {
  #snapshot: AdministrationSnapshot
  #listeners = new Set<() => void>()
  #generation = 0
  #pages = { users: 0, locations: 0, catalog: 0, owner: 0 }
  #abort = new AbortController()
  #command = false
  #runtimeCaptures = new WeakMap<AccountCapture, AccountCapture>()
  #ownerStarted = false
  #ownerBusy = false
  #unsubscribe: () => void
  constructor(
    private readonly runtime: Runtime,
    private readonly transport?: AdministrationTransport,
    private confirmLogout: () => boolean = () => true,
  ) {
    this.#snapshot = { ...cleared(), account: runtime.getAccountSnapshot(), generation: 0 }
    this.#unsubscribe = runtime.subscribeAccount(() => {
      this.reset()
      this.publish({ account: runtime.getAccountSnapshot() })
    })
  }
  getSnapshot = () => this.#snapshot
  subscribe = (listener: () => void) => {
    this.#listeners.add(listener)
    return () => this.#listeners.delete(listener)
  }
  private publish(patch: Partial<AdministrationSnapshot>) {
    this.#snapshot = Object.freeze({ ...this.#snapshot, ...patch })
    for (const listener of this.#listeners) listener()
  }
  private reset() {
    this.#abort.abort()
    this.#abort = new AbortController()
    this.#generation++
    this.#ownerStarted = false
    this.publish({ ...cleared(), generation: this.#generation })
  }
  private capture(): AccountCapture {
    const source = this.runtime.captureAccount(),
      generation = this.#generation,
      signal = AbortSignal.any([source.signal, this.#abort.signal])
    const captured = {
      ...source,
      signal,
      isCurrent: () => !signal.aborted && generation === this.#generation && source.isCurrent(),
    }
    this.#runtimeCaptures.set(captured, source)
    return captured
  }
  private runtimeCapture(source: AccountCapture) {
    return this.#runtimeCaptures.get(source) ?? source
  }
  private http(source: AccountCapture) {
    return (
      this.transport ??
      createAdministrationTransport({ apiRealm: source.apiRealm, fetch: globalThis.fetch })
    )
  }
  private allowed(source: AccountCapture, grant: string) {
    return hasCapability(source.user, grant, this.#snapshot.catalog ?? undefined)
  }
  private readAllowed(source: AccountCapture, grant: string) {
    return source.user.capabilities.includes(grant) || source.user.capabilities.includes('*')
  }
  async enter() {
    if (this.#command) return
    await this.runtime.verifyAccount()
    if (this.runtime.getAccountSnapshot().phase !== 'connected') return
    await Promise.all([this.loadCatalog(), this.loadUsers(), this.loadLocations()])
  }
  close() {
    this.reset()
    this.runtime.invalidateAccount(undefined, 'administration_closed')
  }
  async loadCatalog() {
    let source: AccountCapture
    try {
      source = this.capture()
    } catch {
      return
    }
    if (!this.readAllowed(source, 'users.read')) return
    const page = ++this.#pages.catalog
    try {
      const catalog = await this.http(source).roles(source)
      if (source.isCurrent() && page === this.#pages.catalog) this.publish({ catalog })
    } catch (error) {
      if (source.isCurrent() && page === this.#pages.catalog) this.readError(source, error)
    }
  }
  async loadUsers(options: UserPageOptions = {}) {
    let source: AccountCapture
    try {
      source = this.capture()
    } catch {
      return
    }
    if (!this.readAllowed(source, 'users.read')) return
    const page = ++this.#pages.users,
      input = { ...options }
    this.publish({ users: [], usersNext: null })
    try {
      const value = await this.http(source).users(source, input)
      if (!source.isCurrent() || page !== this.#pages.users) return
      const hint = ownerHintFromPage(source.user, value, input.active !== undefined)
      if (
        input.active === undefined &&
        hint === 'unknown' &&
        value.items.some((row) => row.user_id === source.user.user_id)
      ) {
        this.runtime.invalidateAccount(this.runtimeCapture(source), 'owner_verification_required')
        return
      }
      this.publish({
        users: value.items,
        usersNext: value.next_cursor,
        ...(hint !== 'unknown' ? { ownerHint: hint } : {}),
      })
    } catch (error) {
      if (source.isCurrent() && page === this.#pages.users) this.readError(source, error)
    }
  }
  async loadLocations(afterId?: string) {
    let source: AccountCapture
    try {
      source = this.capture()
    } catch {
      return
    }
    if (!this.readAllowed(source, 'locations.read')) return
    const page = ++this.#pages.locations
    this.publish({ locations: [], locationsNext: null })
    try {
      const value = await this.http(source).locations(
        source,
        afterId === undefined ? {} : { afterId },
      )
      if (source.isCurrent() && page === this.#pages.locations)
        this.publish({ locations: value.items, locationsNext: value.next_cursor })
    } catch (error) {
      if (source.isCurrent() && page === this.#pages.locations) this.readError(source, error)
    }
  }
  async continueOwnerLookup() {
    if (this.#ownerBusy) return
    let source: AccountCapture
    try {
      source = this.capture()
    } catch {
      return
    }
    if (!this.readAllowed(source, 'users.read') || this.#snapshot.ownerHint !== 'unknown') return
    if (this.#ownerStarted && this.#snapshot.ownerNext === null) {
      this.runtime.invalidateAccount(this.runtimeCapture(source), 'owner_verification_required')
      return
    }
    this.#ownerBusy = true
    const page = ++this.#pages.owner,
      afterId = this.#snapshot.ownerNext ?? undefined
    try {
      const value = await this.http(source).users(
        source,
        afterId === undefined ? { limit: 50 } : { afterId, limit: 50 },
      )
      if (!source.isCurrent() || page !== this.#pages.owner) return
      this.#ownerStarted = true
      const hint = ownerHintFromPage(source.user, value)
      if (hint === 'unknown' && value.items.some((row) => row.user_id === source.user.user_id)) {
        this.runtime.invalidateAccount(this.runtimeCapture(source), 'owner_verification_required')
        return
      }
      this.publish({
        ownerHint: hint,
        ownerNext: value.next_cursor,
        message:
          hint === 'unknown'
            ? value.next_cursor
              ? 'Continúa la verificación de propietario en la siguiente página.'
              : 'No se encontró una identidad coherente. Verifica nuevamente el acceso.'
            : 'Identidad de propietario verificada.',
      })
      if (hint === 'unknown' && value.next_cursor === null)
        this.runtime.invalidateAccount(this.runtimeCapture(source), 'owner_verification_required')
    } catch (error) {
      if (source.isCurrent() && page === this.#pages.owner) this.readError(source, error)
    } finally {
      this.#ownerBusy = false
    }
  }
  private readError(source: AccountCapture, error: unknown) {
    if (!source.isCurrent()) return
    if (
      error instanceof AdministrationHttpError &&
      (error.status === 401 || error.status === 403)
    ) {
      this.runtime.invalidateAccount(
        this.runtimeCapture(source),
        error.status === 401 ? 'invalid_session' : 'authority_verification_required',
      )
      return
    }
    this.publish({
      message: 'No se pudo verificar la lista. Comprueba la conexión y actualiza explícitamente.',
      result: 'error',
    })
  }
  private async command<T>(
    run: (source: AccountCapture, http: AdministrationTransport) => Promise<T>,
    options: {
      self?: boolean
      allow?: (source: AccountCapture) => boolean
      success?: (value: T, source: AccountCapture) => void
    } = {},
  ) {
    if (this.#command) return
    let source: AccountCapture
    try {
      source = this.capture()
    } catch {
      return
    }
    if (options.allow && !options.allow(source)) {
      this.publish({ message: 'No tienes autoridad verificada para esta acción.', result: 'error' })
      return
    }
    this.#command = true
    this.publish({ busy: true, message: null, result: 'idle' })
    let suspended = false
    try {
      if (options.self) {
        source = await this.runtime.suspendAccountCommand(this.runtimeCapture(source))
        suspended = true
      }
      if (!source.isCurrent()) return
      const result = await run(source, this.http(source))
      if (!source.isCurrent()) return
      if (suspended) {
        await this.runtime.completeAccountCommand(source, 'success')
        return
      }
      options.success?.(result, source)
      // A name rebind deliberately invalidates the old capture; its runtime notification owns UI.
      if (source.isCurrent())
        this.publish({
          result: 'success',
          message: 'Operación confirmada. Actualiza la lista para consultar el estado actual.',
        })
    } catch (error) {
      if (!source.isCurrent()) return
      const definite =
        error instanceof AdministrationHttpError &&
        (error.code === 'invalid_request' ||
          (error.status !== null &&
            error.status >= 400 &&
            error.status < 500 &&
            error.code !== 'invalid_response'))
      if (suspended && error instanceof AdministrationHttpError && error.status === 401) {
        this.runtime.invalidateAccount(this.runtimeCapture(source), 'invalid_session')
        return
      }
      if (suspended) {
        await this.runtime.completeAccountCommand(source, definite ? 'refused' : 'uncertain')
        return
      }
      if (
        error instanceof AdministrationHttpError &&
        (error.status === 401 || error.status === 403)
      ) {
        this.runtime.invalidateAccount(
          this.runtimeCapture(source),
          error.status === 401 ? 'invalid_session' : 'authority_verification_required',
        )
        return
      }
      this.publish({
        result: definite ? 'error' : 'uncertain',
        message: definite
          ? (safeErrors[(error as AdministrationHttpError).code] ??
            'La acción fue rechazada. Verifica tus permisos y revisa el estado antes de continuar.')
          : uncertain,
      })
    } finally {
      this.#command = false
      if (source.isCurrent()) this.publish({ busy: false })
    }
  }
  private targetAllowed(
    source: AccountCapture,
    row: UserResponse,
    patch: PatchUserRequest,
    grant: string,
  ) {
    const catalog = this.#snapshot.catalog
    if (!catalog || !this.allowed(source, grant)) return false
    const proposed = {
      display_name: patch.display_name ?? row.display_name,
      location_id: Object.hasOwn(patch, 'location_id') ? patch.location_id! : row.location_id,
      capabilities:
        patch.capabilities ??
        (patch.role
          ? catalog.roles.find((role) => role.name === patch.role)?.capabilities
          : undefined) ??
        row.capabilities,
      is_active: patch.is_active ?? row.is_active,
      is_owner: patch.is_owner ?? row.is_owner,
    }
    return canAdminister(source.user, row, proposed, this.#snapshot.ownerHint, catalog)
  }
  createUser(input: CreateUserRequest) {
    const value = structuredClone(input)
    return this.command((source, http) => http.createUser(source, value), {
      allow: (source) => {
        const catalog = this.#snapshot.catalog
        if (
          !catalog ||
          !this.allowed(source, 'users.write') ||
          !this.allowed(source, 'users.grants.write')
        )
          return false
        const grants =
          value.capabilities ?? catalog.roles.find((role) => role.name === value.role)?.capabilities
        if (!grants) return false
        const proposed = {
          display_name: value.display_name,
          location_id: value.location_id,
          capabilities: grants,
          is_active: true,
          is_owner: value.is_owner ?? false,
        }
        return canAdminister(
          source.user,
          {
            ...proposed,
            user_id: 'new',
            organization_id: source.user.organization_id,
            username: value.username,
            version: 1,
          },
          proposed,
          this.#snapshot.ownerHint,
          catalog,
        )
      },
    })
  }
  updateUser(row: UserResponse, patch: PatchUserRequest) {
    const target = structuredClone(row),
      value = structuredClone(patch),
      actor = this.#snapshot.account.user
    if (!actor) return Promise.resolve()
    return this.command((source, http) => http.updateUser(source, target.user_id, value), {
      self: isSelfSecurityChange(actor, target, value),
      allow: (source) =>
        this.targetAllowed(source, target, value, 'users.write') &&
        (!['capabilities', 'role', 'location_id', 'is_owner'].some((key) =>
          Object.hasOwn(value, key),
        ) ||
          this.allowed(source, 'users.grants.write')),
      success: (result, source) => {
        if (
          result.user_id === source.user.user_id &&
          result.organization_id === source.user.organization_id
        )
          this.runtime.updateAccountName(this.runtimeCapture(source), result.display_name)
      },
    })
  }
  resetPassword(row: UserResponse, password: string) {
    const target = structuredClone(row)
    return this.command(
      (source, http) =>
        http.resetPassword(source, target.user_id, {
          expected_version: target.version,
          new_password: password,
        }),
      {
        self: target.user_id === this.#snapshot.account.user?.user_id,
        allow: (source) =>
          this.targetAllowed(
            source,
            target,
            { expected_version: target.version },
            'users.credentials.reset',
          ),
      },
    )
  }
  revokeSessions(row: UserResponse) {
    const target = structuredClone(row)
    return this.command(
      (source, http) =>
        http.revokeSessions(source, target.user_id, { expected_version: target.version }),
      {
        self: target.user_id === this.#snapshot.account.user?.user_id,
        allow: (source) =>
          this.targetAllowed(
            source,
            target,
            { expected_version: target.version },
            'users.sessions.revoke',
          ),
      },
    )
  }
  createLocation(name: string) {
    return this.command((source, http) => http.createLocation(source, { name }), {
      allow: (source) =>
        source.user.location_id === null && this.allowed(source, 'locations.create'),
    })
  }
  changePassword(current_password: string, new_password: string) {
    return this.command(
      (source, http) => http.changePassword(source, { current_password, new_password }),
      { self: true },
    )
  }
  logoutAll() {
    return this.command((source, http) => http.logoutAll(source), { self: true })
  }
  setLogoutGuard(guard: () => boolean) {
    this.confirmLogout = guard
  }
  logout() {
    return this.confirmLogout() ? this.runtime.logout() : Promise.resolve()
  }
  dispose() {
    this.reset()
    this.#unsubscribe()
    this.#listeners.clear()
  }
}

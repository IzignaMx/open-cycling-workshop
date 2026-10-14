export interface SessionStorageLike {
  getItem(key: string): string | null
  setItem(key: string, value: string): void
  removeItem(key: string): void
}

export interface SessionUserSnapshot {
  user_id: string
  organization_id: string
  location_id: string | null
  display_name: string
  capabilities: string[]
}

/** Noncredential reload proof. The kernel validates every field transactionally. */
export interface SessionAdmission {
  format: 1
  sessionBindingId: string
  owner: {
    deviceGeneration: number
    tabAttemptId: string
    principalKey: string
    partitionId: string
    authorizationEpoch: string
  }
  binding: string
}
export interface SessionSnapshot {
  readonly token: string
  readonly user: SessionUserSnapshot | null
  readonly bindingId: string | null
  readonly admission: SessionAdmission | null
}

const SESSION_KEY = 'ocwp.session.v2'

export function isUserSnapshot(value: unknown): value is SessionUserSnapshot {
  if (typeof value !== 'object' || value === null) return false
  const user = value as Record<string, unknown>
  return (
    typeof user.user_id === 'string' &&
    user.user_id.length > 0 &&
    user.user_id.length <= 36 &&
    typeof user.organization_id === 'string' &&
    user.organization_id.length > 0 &&
    user.organization_id.length <= 36 &&
    (typeof user.location_id === 'string' || user.location_id === null) &&
    typeof user.display_name === 'string' &&
    user.display_name.length <= 256 &&
    Array.isArray(user.capabilities) &&
    user.capabilities.length <= 100 &&
    user.capabilities.every(
      (capability) => typeof capability === 'string' && capability.length <= 128,
    )
  )
}

export class SessionStore {
  constructor(
    private readonly storage: SessionStorageLike,
    private readonly newBinding = () => crypto.randomUUID(),
  ) {}

  getSnapshot(): SessionSnapshot | null {
    const raw = this.storage.getItem(SESSION_KEY)
    if (!raw || raw.length > 65536) return null
    try {
      const parsed = JSON.parse(raw) as Record<string, unknown>
      if (typeof parsed.token !== 'string' || !parsed.token || parsed.token.length > 16384)
        return null
      if (parsed.user !== null && parsed.user !== undefined && !isUserSnapshot(parsed.user))
        return null
      const bindingId =
        typeof parsed.bindingId === 'string' &&
        parsed.bindingId.length > 0 &&
        parsed.bindingId.length <= 128
          ? parsed.bindingId
          : null
      const candidate = parsed.admission as SessionAdmission | null | undefined
      // Unknown proof remains in storage, but is never forwarded as admission.
      const admission =
        bindingId &&
        candidate?.format === 1 &&
        candidate.sessionBindingId === bindingId &&
        typeof candidate.binding === 'string' &&
        candidate.owner &&
        Number.isSafeInteger(candidate.owner.deviceGeneration)
          ? structuredClone(candidate)
          : null
      const user = parsed.user && isUserSnapshot(parsed.user) ? structuredClone(parsed.user) : null
      if (user) {
        Object.freeze(user.capabilities)
        Object.freeze(user)
      }
      if (admission) {
        Object.freeze(admission.owner)
        Object.freeze(admission)
      }
      return Object.freeze({ token: parsed.token, user, bindingId, admission })
    } catch {
      return null
    }
  }

  getToken(): string | null {
    return this.getSnapshot()?.token ?? null
  }

  setToken(token: string): void {
    if (!token || token.length > 16384 || /\s/.test(token)) throw new Error('Invalid session token')
    const current = this.getSnapshot()
    if (current?.token === token && current.bindingId) return
    this.storage.setItem(
      SESSION_KEY,
      JSON.stringify({ token, user: null, bindingId: this.newBinding(), admission: null }),
    )
  }

  setUser(user: SessionUserSnapshot): void {
    const current = this.getSnapshot()
    if (!current || !isUserSnapshot(user)) throw new Error('A valid authenticated user is required')
    this.storage.setItem(
      SESSION_KEY,
      JSON.stringify({
        ...current,
        user,
        admission:
          current.user?.user_id === user.user_id &&
          current.user.organization_id === user.organization_id
            ? current.admission
            : null,
      }),
    )
  }

  /** Upgrading an old snapshot is allowed only after successful online verification. */
  bindVerifiedSession(token: string): string {
    const current = this.getSnapshot()
    if (!current || current.token !== token) throw new Error('Session changed')
    const bindingId = current.bindingId ?? this.newBinding()
    this.storage.setItem(SESSION_KEY, JSON.stringify({ ...current, bindingId }))
    return bindingId
  }

  remember(admission: SessionAdmission, token: string): void {
    const current = this.getSnapshot()
    if (!current || current.token !== token || current.bindingId !== admission.sessionBindingId)
      throw new Error('Session changed')
    this.storage.setItem(SESSION_KEY, JSON.stringify({ ...current, admission }))
  }

  clear(): void {
    this.storage.removeItem(SESSION_KEY)
  }
}

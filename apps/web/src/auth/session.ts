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

export interface SessionSnapshot {
  token: string
  user: SessionUserSnapshot | null
}

const SESSION_KEY = 'ocwp.session.v2'

function isUserSnapshot(value: unknown): value is SessionUserSnapshot {
  if (typeof value !== 'object' || value === null) return false
  const user = value as Record<string, unknown>
  return (
    typeof user.user_id === 'string' &&
    typeof user.organization_id === 'string' &&
    (typeof user.location_id === 'string' || user.location_id === null) &&
    typeof user.display_name === 'string' &&
    Array.isArray(user.capabilities) &&
    user.capabilities.every((capability) => typeof capability === 'string')
  )
}

export class SessionStore {
  constructor(private readonly storage: SessionStorageLike) {}

  getSnapshot(): SessionSnapshot | null {
    const raw = this.storage.getItem(SESSION_KEY)
    if (!raw) return null
    try {
      const parsed = JSON.parse(raw) as Record<string, unknown>
      if (typeof parsed.token !== 'string' || !parsed.token) return null
      if (parsed.user !== null && parsed.user !== undefined && !isUserSnapshot(parsed.user)) return null
      return { token: parsed.token, user: parsed.user && isUserSnapshot(parsed.user) ? parsed.user : null }
    } catch {
      return null
    }
  }

  getToken(): string | null {
    return this.getSnapshot()?.token ?? null
  }

  setToken(token: string): void {
    if (!token) throw new Error('session token must not be empty')
    const current = this.getSnapshot()
    this.storage.setItem(SESSION_KEY, JSON.stringify({ token, user: current?.user ?? null }))
  }

  setUser(user: SessionUserSnapshot): void {
    const token = this.getToken()
    if (!token) throw new Error('cannot persist a session user without a token')
    this.storage.setItem(SESSION_KEY, JSON.stringify({ token, user }))
  }

  clear(): void {
    this.storage.removeItem(SESSION_KEY)
  }
}

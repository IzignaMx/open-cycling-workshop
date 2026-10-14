import type { SessionUserSnapshot } from '../auth/session.js'

/** Volatile, non-secret connected authority. Never an offline/kernel admission. */
export interface AccountAccessSnapshot {
  phase: 'unverified' | 'verifying' | 'connected' | 'suspended'
  user: SessionUserSnapshot | null
  generation: number
  message: string | null
}

/** Request-local credential capture. Never retain this in UI snapshots or drafts. */
export interface AccountCapture {
  readonly token: string
  readonly user: SessionUserSnapshot
  readonly apiRealm: string
  readonly signal: AbortSignal
  isCurrent(): boolean
}

export type AccountCommandOutcome = 'success' | 'uncertain' | 'refused'

export function sameAccountAuthority(a: SessionUserSnapshot, b: SessionUserSnapshot): boolean {
  return (
    a.user_id === b.user_id &&
    a.organization_id === b.organization_id &&
    a.location_id === b.location_id &&
    JSON.stringify([...a.capabilities].sort()) === JSON.stringify([...b.capabilities].sort())
  )
}

import type { ContextState, PrincipalKey, VerifiedAccessContext } from './types.js'

export function principalKey(principal: PrincipalKey): string {
  return JSON.stringify([principal.apiRealm, principal.organizationId, principal.userId])
}
export function contextKey(context: VerifiedAccessContext): string {
  return JSON.stringify([
    principalKey(context.principal),
    context.selectedLocationId,
    context.authorizationEpoch,
    context.policyRevision,
    context.accountLocationId,
    [...context.capabilities].sort(),
  ])
}
export function validateVerifiedContext(context: VerifiedAccessContext, now: number): void {
  const fields = [
    context.principal.apiRealm,
    context.principal.organizationId,
    context.principal.userId,
    context.selectedLocationId,
    context.authorizationEpoch,
    context.policyRevision,
  ]
  if (
    context.protocol !== 1 ||
    fields.some((value) => typeof value !== 'string' || !value.trim())
  ) {
    throw new Error('Invalid verified server context')
  }
  const realm = new URL(context.principal.apiRealm)
  if (
    !['http:', 'https:'].includes(realm.protocol) ||
    realm.username ||
    realm.password ||
    realm.search ||
    realm.hash ||
    context.principal.apiRealm.endsWith('/')
  ) {
    throw new Error('Invalid canonical API realm')
  }
  if (
    context.accountLocationId !== null &&
    context.accountLocationId !== context.selectedLocationId
  ) {
    throw new Error('Verified location scope mismatch')
  }
  if (
    !Array.isArray(context.capabilities) ||
    new Set(context.capabilities).size !== context.capabilities.length ||
    context.capabilities.some(
      (value) => typeof value !== 'string' || !value.trim() || value.includes('*'),
    )
  ) {
    throw new Error('Expected normalized concrete server capabilities')
  }
  const verified = Date.parse(context.verifiedAt)
  const until = Date.parse(context.offlineUntil)
  if (
    !Number.isFinite(now) ||
    !Number.isFinite(verified) ||
    !Number.isFinite(until) ||
    verified > now ||
    until <= now ||
    until <= verified ||
    until - verified > 8 * 60 * 60 * 1000
  ) {
    throw new Error('Expired or invalid server context lease')
  }
  if (context.snapshotProtocol !== null && context.snapshotProtocol !== 'baseline-v1') {
    throw new Error('Unsupported baseline protocol')
  }
}

export type ContextEvent =
  'verify' | 'needs_baseline' | 'verified_complete' | 'offline' | 'lock' | 'hold'
/** No snapshot/activation event exists until authoritative baseline integration is implemented. */
export function nextContextState(state: ContextState, event: ContextEvent): ContextState {
  if (event === 'lock') return 'LOCKED'
  if (event === 'verify') return 'VERIFYING'
  if (event === 'hold') return 'HELD'
  if (state === 'VERIFYING' && event === 'needs_baseline') return 'BASELINE_REQUIRED'
  if (state === 'VERIFYING' && event === 'verified_complete') return 'READY'
  if (state === 'READY' && event === 'offline') return 'OFFLINE_READY'
  throw new Error(`Invalid context transition: ${state}/${event}`)
}

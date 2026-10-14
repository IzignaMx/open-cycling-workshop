import type { KernelDatabase } from '../access-kernel/database.js'
import { contextKey, principalKey, validateVerifiedContext } from '../access-kernel/context.js'
import type { ContextTicket, VerifiedAccessContext } from '../access-kernel/types.js'
import { parseBrandingProfile, type BrandingProfile } from '../features/branding/contracts.js'

export interface BrandingSnapshot {
  format: 1
  partitionId: string
  principalKey: string
  apiRealm: string
  organizationId: string
  userId: string
  locationId: string
  authorizationEpoch: string
  policyRevision: string
  datasetIncarnation: string
  verifiedAt: string
  offlineUntil: string
  observedAt: number
  version: number
  /** Writer provenance only. Offline readmission obtains its own current ticket. */
  owner: ContextTicket
  profile: BrandingProfile
}
const FIELDS = [
  'format',
  'partitionId',
  'principalKey',
  'apiRealm',
  'organizationId',
  'userId',
  'locationId',
  'authorizationEpoch',
  'policyRevision',
  'datasetIncarnation',
  'verifiedAt',
  'offlineUntil',
  'observedAt',
  'version',
  'owner',
  'profile',
]
function boundProfile(profile: BrandingProfile, context: VerifiedAccessContext): boolean {
  return (
    profile.organization_id === context.principal.organizationId &&
    profile.location_id === context.selectedLocationId &&
    profile.dataset_incarnation === context.datasetIncarnation
  )
}
function snapshotBound(
  value: unknown,
  ticket: ContextTicket,
  context: VerifiedAccessContext,
  now: number,
  exactLease = true,
): value is BrandingSnapshot {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false
  const row = value as BrandingSnapshot
  return (
    Object.keys(row).length === FIELDS.length &&
    FIELDS.every((key) => Object.hasOwn(row, key)) &&
    row.format === 1 &&
    row.partitionId === ticket.partitionId &&
    row.principalKey === ticket.principalKey &&
    row.apiRealm === context.principal.apiRealm &&
    row.organizationId === context.principal.organizationId &&
    row.userId === context.principal.userId &&
    row.locationId === context.selectedLocationId &&
    row.authorizationEpoch === context.authorizationEpoch &&
    row.policyRevision === context.policyRevision &&
    row.datasetIncarnation === context.datasetIncarnation &&
    (!exactLease ||
      (row.verifiedAt === context.verifiedAt && row.offlineUntil === context.offlineUntil)) &&
    Number.isFinite(row.observedAt) &&
    row.observedAt >= Date.parse(row.verifiedAt) &&
    row.observedAt <= now &&
    row.observedAt < Date.parse(row.offlineUntil) &&
    Number.isSafeInteger(row.version) &&
    row.version >= 0 &&
    !!row.owner &&
    Object.keys(row.owner).length === 5 &&
    row.owner.partitionId === ticket.partitionId &&
    row.owner.principalKey === ticket.principalKey &&
    row.owner.authorizationEpoch === ticket.authorizationEpoch &&
    Number.isSafeInteger(row.owner.deviceGeneration) &&
    row.owner.deviceGeneration >= 0 &&
    typeof row.owner.tabAttemptId === 'string' &&
    !!row.owner.tabAttemptId &&
    !!row.profile &&
    row.profile.version === row.version &&
    boundProfile(row.profile, context)
  )
}
class BrandingCacheFenced extends Error {}
function elapsedClock(now: number): () => number {
  const started = performance.now()
  return () => now + Math.max(0, performance.now() - started)
}
function revisionIdentity(profile: BrandingProfile): string {
  return JSON.stringify({
    ...profile,
    logo_state: undefined,
    logo_diagnostic: undefined,
    logo: profile.logo === null ? null : { ...profile.logo, png_base64: undefined },
  })
}
/** Dedicated cache only: no tokens, operation entity types, journal writes or lease extension. */
export class BrandingSnapshotRepository {
  constructor(private readonly db: KernelDatabase) {}
  private tables() {
    return [
      this.db.deviceControl,
      this.db.accessContexts,
      this.db.cachePartitions,
      this.db.brandingSnapshots,
    ]
  }
  private async admitted(
    ticket: ContextTicket,
    context: VerifiedAccessContext,
    now: () => number,
    write: boolean,
  ): Promise<boolean> {
    try {
      validateVerifiedContext(context, now())
      if (
        !context.capabilities.includes('branding.read') ||
        context.snapshotProtocol !== 'baseline-v1' ||
        principalKey(context.principal) !== ticket.principalKey ||
        context.authorizationEpoch !== ticket.authorizationEpoch
      )
        return false
      const [control, partition, stored] = await Promise.all([
        this.db.deviceControl.get('device'),
        this.db.cachePartitions.get(ticket.partitionId),
        this.db.accessContexts.get(ticket.partitionId),
      ])
      if (
        !control ||
        !partition ||
        !stored ||
        control.generation !== ticket.deviceGeneration ||
        control.tabAttemptId !== ticket.tabAttemptId ||
        control.activePartitionId !== ticket.partitionId ||
        (write
          ? control.state !== 'READY'
          : control.state !== 'READY' && control.state !== 'OFFLINE_READY') ||
        !Number.isFinite(control.observedAt) ||
        control.observedAt > now() ||
        partition.partitionId !== ticket.partitionId ||
        partition.status !== 'active' ||
        !partition.baselineComplete ||
        partition.principalKey !== ticket.principalKey ||
        partition.locationId !== context.selectedLocationId ||
        partition.authorizationEpoch !== ticket.authorizationEpoch ||
        partition.policyRevision !== context.policyRevision ||
        stored.partitionId !== ticket.partitionId ||
        contextKey(stored.context) !== contextKey(context) ||
        stored.context.verifiedAt !== context.verifiedAt ||
        stored.context.offlineUntil !== context.offlineUntil
      )
        return false
      validateVerifiedContext(stored.context, now())
      return stored.context.capabilities.includes('branding.read')
    } catch {
      return false
    }
  }
  async read(
    suppliedTicket: ContextTicket,
    suppliedContext: VerifiedAccessContext,
    now: number,
  ): Promise<BrandingProfile | null> {
    const ticket = structuredClone(suppliedTicket),
      context = structuredClone(suppliedContext),
      currentTime = elapsedClock(now)
    const row = await this.db.transaction('r', this.tables(), async () => {
      if (!(await this.admitted(ticket, context, currentTime, false))) return null
      const value = await this.db.brandingSnapshots.get(ticket.partitionId)
      return snapshotBound(value, ticket, context, currentTime()) ? value : null
    })
    if (!row) return null
    let profile: BrandingProfile
    try {
      profile = await parseBrandingProfile(row.profile)
    } catch {
      return null
    }
    // WebCrypto cannot hold an IDB transaction. Recheck the exact row and owner
    // atomically after validation, so a late digest never publishes another session.
    return this.db.transaction('r', this.tables(), async () => {
      if (!(await this.admitted(ticket, context, currentTime, false))) return null
      const latest = await this.db.brandingSnapshots.get(ticket.partitionId)
      if (!(await this.admitted(ticket, context, currentTime, false))) return null
      return snapshotBound(latest, ticket, context, currentTime()) &&
        JSON.stringify(latest) === JSON.stringify(row)
        ? profile
        : null
    })
  }
  async write(
    suppliedTicket: ContextTicket,
    suppliedContext: VerifiedAccessContext,
    value: BrandingProfile,
    now: number,
  ): Promise<boolean> {
    const ticket = structuredClone(suppliedTicket),
      context = structuredClone(suppliedContext),
      currentTime = elapsedClock(now)
    const profile = await parseBrandingProfile(value)
    if (!boundProfile(profile, context)) return false
    try {
      return await this.db.transaction('rw', this.tables(), async () => {
        if (!(await this.admitted(ticket, context, currentTime, true))) return false
        const previous = await this.db.brandingSnapshots.get(ticket.partitionId)
        if (previous) {
          // Invalid provenance is never used to grant access or silently repair a cache.
          if (!snapshotBound(previous, ticket, context, currentTime(), false))
            throw new Error('Branding cache provenance invalid')
          if (
            previous.version > profile.version ||
            (previous.version === profile.version &&
              revisionIdentity(previous.profile) !== revisionIdentity(profile))
          )
            return false
        }
        const snapshot: BrandingSnapshot = {
          format: 1,
          partitionId: ticket.partitionId,
          principalKey: ticket.principalKey,
          apiRealm: context.principal.apiRealm,
          organizationId: context.principal.organizationId,
          userId: context.principal.userId,
          locationId: context.selectedLocationId,
          authorizationEpoch: context.authorizationEpoch,
          policyRevision: context.policyRevision,
          datasetIncarnation: context.datasetIncarnation,
          verifiedAt: context.verifiedAt,
          offlineUntil: context.offlineUntil,
          observedAt: currentTime(),
          version: profile.version,
          owner: ticket,
          profile,
        }
        await this.db.brandingSnapshots.put(snapshot)
        // Bounded branding-only maintenance. Never touch operational history or preferences.
        const older = await this.db.brandingSnapshots
          .where('principalKey')
          .equals(ticket.principalKey)
          .limit(8)
          .toArray()
        for (const candidate of older) {
          if (candidate.partitionId === ticket.partitionId) continue
          const partition = await this.db.cachePartitions.get(candidate.partitionId)
          if (partition?.status === 'superseded')
            await this.db.brandingSnapshots.delete(candidate.partitionId)
        }
        if (!(await this.admitted(ticket, context, currentTime, true)))
          throw new BrandingCacheFenced()
        return true
      })
    } catch (error) {
      if (error instanceof BrandingCacheFenced) return false
      throw error
    }
  }
}

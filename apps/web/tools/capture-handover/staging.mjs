// Synthetic custody prototype only. No operational import or activation authority.
import Dexie from 'dexie'
import { canonicalJson } from '../../.tmp-kernel/src/access-kernel/operations.js'
import {
  validCheckpoint,
  validContent,
  projectionBytes,
  MAX_CONTENT_UTF8_BYTES,
} from '../../.tmp-kernel/src/access-kernel/capture-checkpoint.js'
const refused = (reason) => ({ kind: 'refused', reason })
const exact = (v, keys) =>
  v !== null &&
  typeof v === 'object' &&
  !Array.isArray(v) &&
  Object.keys(v).length === keys.length &&
  keys.every((k) => Object.hasOwn(v, k))
const ownerKeys = [
  'apiRealm',
  'organizationId',
  'userId',
  'selectedLocationId',
  'datasetIncarnation',
]
const ownerValid = (o) =>
  exact(o, ownerKeys) &&
  ownerKeys.every((k) => typeof o[k] === 'string' && o[k].length > 0 && o[k].length <= 512)
function validBundle(b, owner, now) {
  if (
    !Number.isSafeInteger(now) ||
    now < 0 ||
    !ownerValid(owner) ||
    !exact(b, ['format', 'kind', 'owner', 'capturedAt', 'checkpoint', 'contents']) ||
    b.format !== 1 ||
    b.kind !== 'inert-capture-custody' ||
    !ownerValid(b.owner) ||
    canonicalJson(b.owner) !== canonicalJson(owner) ||
    !Number.isSafeInteger(b.capturedAt) ||
    b.capturedAt < 0 ||
    b.capturedAt > now ||
    !validCheckpoint(b.checkpoint) ||
    b.checkpoint.closed ||
    b.checkpoint.observedAt > b.capturedAt ||
    !Array.isArray(b.contents) ||
    b.contents.length < 1 ||
    b.contents.length > 2
  )
    return false
  if (new TextEncoder().encode(canonicalJson(b)).length > 150000) return false
  const seen = new Set()
  for (const row of b.contents) {
    if (
      !validContent(row) ||
      seen.has(row.channel) ||
      row.checkpointId !== b.checkpoint.checkpointId ||
      row.generation !== b.checkpoint.generation
    )
      return false
    seen.add(row.channel)
    const c = b.checkpoint[row.channel]
    if (
      c.state !== 'UNSENT' ||
      row.revision !== c.revision ||
      row.firstPersistedAt !== c.contentStartedAt ||
      row.expiresAt !== c.contentExpiresAt ||
      row.firstPersistedAt > b.capturedAt ||
      row.expiresAt <= now
    )
      return false
    const projection =
      row.channel === 'customer'
        ? { channel: row.channel, draft: row.draft }
        : { channel: row.channel, draft: row.draft, retainedSelection: row.retainedSelection }
    if (projectionBytes(projection) > MAX_CONTENT_UTF8_BYTES) return false
  }
  return ['customer', 'order'].every(
    (channel) => seen.has(channel) || b.checkpoint[channel].state === 'EMPTY',
  )
}
export function createCustodyStore(name, dependencies) {
  if (typeof name !== 'string' || !/^ocwp-synthetic-custody-[a-z0-9-]{1,100}$/.test(name))
    throw new Error('Synthetic custody database required')
  const db = new Dexie(name, dependencies)
  db.version(1).stores({ custody: 'transferId' })
  return db
}
function current(fn) {
  return typeof fn === 'function' && fn() === true
}
export async function stageCustody(db, transferId, bundle, owner, now, isCurrent) {
  if (Dexie.currentTransaction) return refused('nested_transaction')
  try {
    if (
      typeof transferId !== 'string' ||
      !transferId.trim() ||
      transferId.length > 128 ||
      !current(isCurrent)
    )
      return refused('admission')
    bundle = structuredClone(bundle)
    owner = structuredClone(owner)
    if (!validBundle(bundle, owner, now)) return refused('invalid')
    const canonical = canonicalJson(bundle)
    return await db.transaction('rw', db.custody, async () => {
      if (!current(isCurrent)) throw new Error('admission')
      const prior = await db.custody.get(transferId)
      if (prior && prior.canonical !== canonical) return refused('conflict')
      if (!prior) await db.custody.add({ transferId, canonical, bundle })
      const readback = await db.custody.get(transferId)
      if (
        !readback ||
        readback.canonical !== canonical ||
        canonicalJson(readback.bundle) !== canonical ||
        !current(isCurrent)
      )
        throw new Error('verification')
      return { kind: prior ? 'already_staged' : 'staged' }
    })
  } catch {
    return refused('unavailable')
  }
}
export async function readCustody(db, transferId, owner, now, isCurrent) {
  if (Dexie.currentTransaction) return refused('nested_transaction')
  try {
    owner = structuredClone(owner)
    if (!current(isCurrent)) return refused('admission')
    const row = await db.custody.get(transferId)
    if (
      !row ||
      !validBundle(row.bundle, owner, now) ||
      canonicalJson(row.bundle) !== row.canonical ||
      !current(isCurrent)
    )
      return refused('unavailable')
    return { kind: 'custody', bundle: structuredClone(row.bundle) }
  } catch {
    return refused('unavailable')
  }
}

import type { KernelDatabase } from '../access-kernel/database.js'
import type { ContextTicket } from '../access-kernel/types.js'
import {
  preferenceScopeKey,
  validatePreferences,
  validateLogoPreference,
  type PreferenceScope,
} from '../personalization/preferences.js'
import type { PreferenceRecord } from '../personalization/repository.js'

/** No version requested: old schemas are never upgraded; absent DB creation is aborted. */
async function openExisting(factory: IDBFactory, name: string): Promise<IDBDatabase | null> {
  return new Promise((resolve, reject) => {
    const request = factory.open(name)
    let absent = false
    request.onupgradeneeded = () => {
      absent = true
      request.transaction?.abort()
    }
    request.onsuccess = () => {
      const db = request.result
      db.onversionchange = () => db.close()
      resolve(db)
    }
    request.onerror = () =>
      absent ? resolve(null) : reject(new Error('Legacy storage unavailable'))
    request.onblocked = () => reject(new Error('Legacy storage unavailable'))
  })
}
function request<T>(value: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    value.onsuccess = () => resolve(value.result)
    value.onerror = () => reject(new Error('Legacy storage unavailable'))
  })
}
/** Counts only, no legacy operational record or identifier crosses this boundary. */
export async function inspectLegacyWork(factory: IDBFactory, name = 'ocwp'): Promise<boolean> {
  const db = await openExisting(factory, name)
  if (!db) return false
  try {
    const stores = [
      'customers',
      'mutationQueue',
      'syncState',
      'conflicts',
      'bicycles',
      'serviceOrders',
      'serviceOrderEvents',
    ].filter((s) => db.objectStoreNames.contains(s))
    if (!stores.length) return false
    const tx = db.transaction(stores, 'readonly')
    const counts = await Promise.all(stores.map((s) => request(tx.objectStore(s).count())))
    return counts.some((count) => count > 0)
  } finally {
    db.close()
  }
}
function checkedRecord(
  value: unknown,
  scope: PreferenceScope,
  kind: 'appearance' | 'logo',
): PreferenceRecord | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
  const row = value as Record<string, unknown>
  if (
    row.key !== preferenceScopeKey(scope, kind) ||
    row.organizationId !== scope.organizationId ||
    row.userId !== scope.userId ||
    row.kind !== kind ||
    row.locationId !== (kind === 'logo' ? scope.locationId : null)
  )
    return null
  const normalized = kind === 'appearance' ? validatePreferences(row.value) : null
  if (kind === 'appearance' && !normalized?.valid) return null
  if (kind === 'logo' && !validateLogoPreference(row.value)) return null
  // Copy validated owned records unchanged. Translation happens only on read;
  // neither source bytes nor historical intent are rewritten on first admission.
  return value as PreferenceRecord
}
export async function copyOwnedLegacyPreferences(options: {
  factory: IDBFactory
  name?: string
  database: KernelDatabase
  scope: PreferenceScope
  ticket: ContextTicket
  isCurrent(): boolean
}): Promise<void> {
  const { database, scope, ticket, isCurrent } = options
  if (!isCurrent()) throw new Error('Preference session changed')
  const source = await openExisting(options.factory, options.name ?? 'ocwp')
  if (!source) return
  let rows: unknown[]
  try {
    if (!source.objectStoreNames.contains('presentationPreferences')) return
    const store = source
      .transaction('presentationPreferences', 'readonly')
      .objectStore('presentationPreferences')
    rows = await Promise.all([
      request(store.get(preferenceScopeKey(scope))),
      request(store.get(preferenceScopeKey(scope, 'logo'))),
    ])
  } finally {
    source.close()
  }
  const records = rows
    .map((row, i) => checkedRecord(row, scope, i === 0 ? 'appearance' : 'logo'))
    .filter((row): row is PreferenceRecord => row !== null)
  await database.transaction(
    'rw',
    [database.presentationPreferences, database.deviceControl],
    async () => {
      const control = await database.deviceControl.get('device')
      const current = () =>
        isCurrent() &&
        control?.generation === ticket.deviceGeneration &&
        control.tabAttemptId === ticket.tabAttemptId &&
        control.activePartitionId === ticket.partitionId
      if (!current()) throw new Error('Preference session changed')
      for (const record of records) {
        if (!(await database.presentationPreferences.get(record.key)))
          await database.presentationPreferences.add(record)
      }
      if (!current()) throw new Error('Preference session changed')
    },
  )
}

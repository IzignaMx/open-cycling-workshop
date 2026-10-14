import test from 'node:test'
import assert from 'node:assert/strict'
import 'fake-indexeddb/auto'
import { createKernelDatabase } from '../../.tmp-runtime/src/access-kernel/database.js'
import {
  inspectLegacyWork,
  copyOwnedLegacyPreferences,
} from '../../.tmp-runtime/src/runtime/legacy-preservation.js'
import {
  DEFAULT_PREFERENCES,
  preferenceScopeKey,
} from '../../.tmp-runtime/src/personalization/preferences.js'
const rawOpen = (name, version, upgrade) =>
  new Promise((resolve, reject) => {
    const r = indexedDB.open(name, version)
    r.onupgradeneeded = () => upgrade(r.result)
    r.onsuccess = () => resolve(r.result)
    r.onerror = () => reject(r.error)
  })
const put = (db, store, row) =>
  new Promise((resolve, reject) => {
    const t = db.transaction(store, 'readwrite')
    t.objectStore(store).put(row)
    t.oncomplete = resolve
    t.onabort = () => reject(t.error)
  })
test('absent legacy database stays absent and raw old version never upgrades', async () => {
  const name = 'missing-' + crypto.randomUUID()
  assert.equal(await inspectLegacyWork(indexedDB, name), false)
  assert.ok(!(await indexedDB.databases()).some((x) => x.name === name))
  const old = await rawOpen(name, 1, (db) =>
    db.createObjectStore('mutationQueue', { keyPath: 'id' }),
  )
  await put(old, 'mutationQueue', { id: 'unknown', secret: 'never materialize' })
  assert.equal(await inspectLegacyWork(indexedDB, name), true)
  assert.equal(old.version, 1)
  old.close()
})
test('copies exactly owned appearance and workshop logo, preserves old bytes and newer destination', async () => {
  const name = 'legacy-' + crypto.randomUUID(),
    scope = { organizationId: 'org', userId: 'user', locationId: 'loc' }
  const source = await rawOpen(name, 4, (db) =>
    db.createObjectStore('presentationPreferences', { keyPath: 'key' }),
  )
  const record = {
    key: preferenceScopeKey(scope),
    organizationId: 'org',
    userId: 'user',
    locationId: null,
    kind: 'appearance',
    value: { ...DEFAULT_PREFERENCES, themeId: 'noche' },
    unknown: 'preserved',
  }
  await put(source, 'presentationPreferences', record)
  const db = createKernelDatabase('new-' + crypto.randomUUID())
  await db.open()
  const ticket = {
    deviceGeneration: 1,
    tabAttemptId: 'tab',
    partitionId: 'p',
    principalKey: 'k',
    authorizationEpoch: 'epoch',
  }
  await db.deviceControl.put({
    key: 'device',
    generation: 1,
    tabAttemptId: 'tab',
    activePartitionId: 'p',
  })
  await copyOwnedLegacyPreferences({
    factory: indexedDB,
    name,
    database: db,
    scope,
    ticket,
    isCurrent: () => true,
  })
  assert.equal((await db.presentationPreferences.get(record.key)).value.themeId, 'noche')
  await db.presentationPreferences.put({
    ...record,
    value: { ...DEFAULT_PREFERENCES, themeId: 'plano' },
  })
  await copyOwnedLegacyPreferences({
    factory: indexedDB,
    name,
    database: db,
    scope,
    ticket,
    isCurrent: () => true,
  })
  assert.equal((await db.presentationPreferences.get(record.key)).value.themeId, 'plano')
  const old = await new Promise((resolve) => {
    const r = source
      .transaction('presentationPreferences')
      .objectStore('presentationPreferences')
      .get(record.key)
    r.onsuccess = () => resolve(r.result)
  })
  assert.deepEqual(old, record)
  source.close()
  db.close()
})

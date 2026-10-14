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

test('first authenticated copy preserves v1 default palette and missing/null/raster provenance without rewriting either source', async () => {
  const { PreferenceRepository } =
    await import('../../.tmp-runtime/src/personalization/repository.js')
  const logo =
    'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNQCbD7DwADAAGyeEyo+gAAAABJRU5ErkJggg=='
  for (const [storedLogo, mode] of [
    [undefined, 'workshop'],
    [null, 'none'],
    [logo, 'local'],
  ]) {
    const scope = { organizationId: 'org', userId: 'user', locationId: 'loc' }
    const name = 'legacy-v1-branding-' + crypto.randomUUID()
    const source = await rawOpen(name, 40, (db) =>
      db.createObjectStore('presentationPreferences', { keyPath: 'key' }),
    )
    const appearance = {
      ...scope,
      locationId: null,
      kind: 'appearance',
      key: preferenceScopeKey(scope),
      value: {
        schemaVersion: 1,
        themeId: 'ritmo',
        paletteId: 'bosque',
        scheme: 'dark',
        density: 'workshop',
        logoDataUrl: null,
      },
      unknown: { retained: true },
    }
    const records = [appearance]
    if (storedLogo !== undefined)
      records.push({
        ...scope,
        kind: 'logo',
        key: preferenceScopeKey(scope, 'logo'),
        value: storedLogo,
      })
    for (const record of records) await put(source, 'presentationPreferences', record)
    const db = createKernelDatabase('first-admission-branding-' + crypto.randomUUID())
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
    try {
      await copyOwnedLegacyPreferences({
        factory: indexedDB,
        name,
        database: db,
        scope,
        ticket,
        isCurrent: () => true,
      })
      const loaded = await new PreferenceRepository(db.presentationPreferences).load(scope)
      assert.equal(loaded.preferences.paletteSource, 'personal')
      assert.equal(loaded.preferences.paletteId, 'bosque')
      assert.equal(loaded.preferences.logoMode, mode)
      assert.equal(loaded.preferences.themeId, 'ritmo')
      assert.equal(loaded.preferences.density, 'workshop')
      assert.equal(loaded.preferences.scheme, 'dark')
      for (const record of records)
        assert.deepEqual(await db.presentationPreferences.get(record.key), record)
      const old = await new Promise((resolve) => {
        const request = source
          .transaction('presentationPreferences')
          .objectStore('presentationPreferences')
          .getAll()
        request.onsuccess = () => resolve(request.result)
      })
      assert.deepEqual(
        old,
        [...records].sort((a, b) => a.key.localeCompare(b.key)),
      )
      assert.equal(source.version, 40)
      assert.equal(await db.operationJournal.count(), 0)
    } finally {
      source.close()
      db.close()
      await db.delete()
    }
  }
})

test('first admission leaves malformed/future/wrong-scope preferences and absent logo records untouched', async () => {
  const scope = { organizationId: 'org', userId: 'user', locationId: 'loc' },
    name = 'legacy-invalid-branding-' + crypto.randomUUID()
  const source = await rawOpen(name, 40, (db) =>
    db.createObjectStore('presentationPreferences', { keyPath: 'key' }),
  )
  const original = {
    ...scope,
    locationId: null,
    kind: 'appearance',
    key: preferenceScopeKey(scope),
    value: { ...DEFAULT_PREFERENCES, schemaVersion: 99 },
  }
  await put(source, 'presentationPreferences', original)
  await put(source, 'presentationPreferences', {
    ...scope,
    userId: 'foreign',
    kind: 'logo',
    key: preferenceScopeKey(scope, 'logo'),
    value: null,
  })
  const db = createKernelDatabase('admission-invalid-' + crypto.randomUUID())
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
  try {
    await copyOwnedLegacyPreferences({
      factory: indexedDB,
      name,
      database: db,
      scope,
      ticket,
      isCurrent: () => true,
    })
    assert.equal(await db.presentationPreferences.count(), 0)
    assert.equal(source.version, 40)
  } finally {
    source.close()
    db.close()
    await db.delete()
  }
})

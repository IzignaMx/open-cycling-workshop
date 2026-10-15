import 'fake-indexeddb/auto'
import test from 'node:test'
import assert from 'node:assert/strict'
import Dexie from 'dexie'
import { createKernelDatabase } from '../../.tmp-kernel/src/access-kernel/database.js'
import { OcwpDatabase } from '../../.tmp-kernel/src/local/database.js'

const SCHEMAS = {
  customers: ['customer_id', 'organization_id', 'location_id', 'display_name', 'updated_at'],
  mutationQueue: [
    'mutation_id',
    'state',
    'organization_id',
    'location_id',
    'entity_type',
    'queued_at',
  ],
  syncState: ['key'],
  conflicts: ['mutation_id', 'entity_type', 'entity_id', 'recorded_at'],
  bicycles: ['bicycle_id', 'organization_id', 'location_id', 'customer_id', 'updated_at'],
  serviceOrders: [
    'order_id',
    'organization_id',
    'location_id',
    'customer_id',
    'state',
    'updated_at',
  ],
  serviceOrderEvents: ['event_id', 'order_id', 'organization_id', 'occurred_at'],
  presentationPreferences: ['key'],
}
const ROWS = {
  customers: [
    {
      customer_id: 'customer',
      organization_id: 'org',
      location_id: 'loc',
      display_name: 'original',
      unknown: { from_future: [null, false, 7] },
    },
  ],
  mutationQueue: [
    {
      mutation_id: 'operation',
      organization_id: 'org',
      location_id: 'loc',
      entity_type: 'service_order',
      state: 'retrying',
      base_version: 11,
      occurred_at: 'original-time',
      payload: { transition: { actor_id: 'A', action: 'start_repair' } },
      untouched: { mystery: 'keep' },
    },
  ],
  syncState: [{ key: 'cursor:org:loc', cursor: 900, unknown: 'do not adopt' }],
  conflicts: [
    {
      mutation_id: 'old-conflict',
      entity_type: 'customer',
      entity_id: 'order',
      reason: 'legacy unknown provenance',
      preserved: [1, 2],
    },
  ],
  bicycles: [{ bicycle_id: 'bicycle', unknown: 'bicycle-data' }],
  serviceOrders: [
    { order_id: 'order', organization_id: 'org2', location_id: 'loc2', unknown: 'other scope' },
  ],
  serviceOrderEvents: [
    { event_id: 'event', actor_id: 'claimed-A', action: 'keep evidence', unknown: true },
  ],
  presentationPreferences: [
    { key: '["org","A"]', theme: 'ritmo', density: 'compact', unknown: { persisted: true } },
    { key: '["org","A","loc"]', logo: new Blob(['original-logo-bytes'], { type: 'image/png' }) },
    { key: '["org","B","loc"]', logo: null, independent: true },
  ],
}
function requestResult(request) {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error)
  })
}
async function seed(name, nativeVersion) {
  const logical = nativeVersion === 1 ? 1 : nativeVersion / 10
  const request = indexedDB.open(name, nativeVersion)
  request.onupgradeneeded = () => {
    for (const [name, fields] of Object.entries(SCHEMAS)) {
      if (
        (['bicycles', 'serviceOrders', 'serviceOrderEvents'].includes(name) && logical < 3) ||
        (name === 'presentationPreferences' && logical < 4)
      )
        continue
      const store = request.result.createObjectStore(name, { keyPath: fields[0] })
      for (const field of fields.slice(1)) store.createIndex(field, field)
      if (logical >= 2 && ['syncState', 'conflicts'].includes(name)) {
        for (const field of ['scope_key', 'organization_id', 'location_id'])
          store.createIndex(field, field)
      }
    }
  }
  const db = await requestResult(request)
  const names = Array.from(db.objectStoreNames)
  const tx = db.transaction(names, 'readwrite')
  for (const name of names) for (const row of ROWS[name]) tx.objectStore(name).add(row)
  await new Promise((resolve, reject) => {
    tx.oncomplete = resolve
    tx.onabort = () => reject(tx.error)
  })
  db.close()
  return names
}
async function assertRows(db, names) {
  for (const name of names) {
    const rows = await db.table(name).toArray()
    assert.deepEqual(
      rows,
      [...ROWS[name]].sort((a, b) =>
        String(a[SCHEMAS[name][0]]).localeCompare(String(b[SCHEMAS[name][0]])),
      ),
    )
    for (const row of rows)
      if (row.logo instanceof Blob) assert.equal(await row.logo.text(), 'original-logo-bytes')
  }
}
for (const nativeVersion of [1, 10, 20, 30, 40])
  test(`native ${nativeVersion} upgrades losslessly to actual native70/logical7 without attribution`, async () => {
    const name = `migration-${crypto.randomUUID()}`
    const names = await seed(name, nativeVersion)
    const db = createKernelDatabase(name)
    try {
      await db.open()
      assert.equal(db.verno, 7)
      assert.equal(db.backendDB().version, 70)
      assert.equal(db.tables.length, 17)
      await assertRows(db, names)
      assert.deepEqual(await db.localMigrationState.get('identity-kernel-v5'), {
        key: 'identity-kernel-v5',
        protocol: 1,
        legacyPresent: true,
        legacyAttribution: 'unknown',
      })
      assert.equal(await db.operationJournal.count(), 0)
      assert.equal(await db.cacheRecords.count(), 0)
      assert.equal(await db.cachePartitions.count(), 0)
      assert.equal(await db.deviceControl.count(), 0)
      assert.deepEqual(db.cacheRecords.schema.primKey.keyPath, [
        'partitionId',
        'entityType',
        'entityId',
      ])
      assert.ok(db.operationJournal.schema.idxByName['[principalKey+locationId]'])
    } finally {
      db.close()
      await db.delete()
    }
  })
for (const failure of ['abort', 'quota'])
  test(`failed v5 ${failure} rolls back complete schema and legacy rows`, async () => {
    const name = `abort-${crypto.randomUUID()}`
    const names = await seed(name, 40)
    const candidate = createKernelDatabase(name)
    if (failure === 'abort') candidate.version(5).upgrade((transaction) => transaction.abort())
    else
      candidate.localMigrationState.hook('creating', () => {
        throw new DOMException('simulated quota pressure', 'QuotaExceededError')
      })
    try {
      await assert.rejects(candidate.open(), /abort|quota/i)
      candidate.close()
      const original = new OcwpDatabase(name)
      try {
        await original.open()
        assert.equal(original.backendDB().version, 40)
        assert.equal(original.tables.length, 8)
        await assertRows(original, names)
      } finally {
        original.close()
      }
      const retry = createKernelDatabase(name)
      try {
        await retry.open()
        await assertRows(retry, names)
      } finally {
        retry.close()
      }
    } finally {
      candidate.close()
      await candidate.delete()
    }
  })
test('versionchange closes the old connection; simulated future v8 carries all v7 data', async () => {
  const name = `future-${crypto.randomUUID()}`
  const names = await seed(name, 40)
  const db = createKernelDatabase(name)
  await db.open()
  const journal = {
    mutationId: 'owned',
    principalKey: '["realm","org","A"]',
    envelope: { payload: { original: true } },
    unknown: { intact: true },
  }
  await db.operationJournal.add(journal)
  await db.cacheRecords.add({
    partitionId: 'partition',
    entityType: 'customer',
    entityId: 'customer',
    payload: { intact: true },
    version: 1,
  })
  const future = createKernelDatabase(name)
  // Fixture only, never a reserved production store/migration.
  future.version(8).stores({ futureQuoteFixture: 'id' })
  try {
    await future.open()
    assert.equal(db.isOpen(), false)
    assert.equal(future.backendDB().version, 80)
    await assertRows(future, names)
    assert.deepEqual(await future.operationJournal.get('owned'), journal)
    assert.equal(await future.cacheRecords.count(), 1)
  } finally {
    db.close()
    future.close()
    await future.delete()
  }
})
test('authenticated factory cannot open legacy name; legacy class remains v4', async () => {
  assert.throws(() => createKernelDatabase('ocwp'), /distinct authenticated database name/)
  const database = new OcwpDatabase(`production-v4-${crypto.randomUUID()}`)
  try {
    await database.open()
    assert.equal(database.verno, 4)
    assert.equal(database.tables.length, 8)
  } finally {
    database.close()
    await database.delete()
  }
  assert.equal(typeof Dexie, 'function')
})

test('activation blocker: legacy v4 Dexie opens v7 and can still write sealed legacy stores', async () => {
  const name = `old-bundle-${crypto.randomUUID()}`
  const upgraded = createKernelDatabase(name)
  await upgraded.open()
  upgraded.close()
  const oldBundle = new OcwpDatabase(name)
  try {
    await oldBundle.open()
    assert.equal(oldBundle.backendDB().version, 70)
    await oldBundle.mutationQueue.add({
      mutation_id: 'old-bundle-write',
      payload: { preserved: true },
    })
    assert.equal((await oldBundle.mutationQueue.get('old-bundle-write')).payload.preserved, true)
  } finally {
    oldBundle.close()
    upgraded.close()
    await upgraded.delete()
  }
})

test('isolated database names must be primitive strings before native coercion', () => {
  for (const name of [new String('ocwp'), { toString: () => 'ocwp' }, null, undefined, 7]) {
    assert.throws(() => createKernelDatabase(name), /isolated|name/i)
  }
})

test('v5 to v7 adds pagination indices and branding cache without attributing or rewriting any retained bytes', async () => {
  const name = `v5-v6-${crypto.randomUUID()}`
  const v5 = new OcwpDatabase(name)
  v5.version(5).stores({
    deviceControl: 'key',
    accessContexts: 'partitionId',
    cachePartitions: 'partitionId, principalKey',
    cacheRecords: '[partitionId+entityType+entityId], [partitionId+entityType]',
    operationJournal:
      'mutationId, [principalKey+locationId], localSequence, [principalKey+locationId+entityType+entityId]',
    operationDelivery:
      'mutationId, state, [principalKey+locationId+dispatchable+localSequence], [principalKey+locationId+entityType+entityId+unresolved+localSequence], [attemptId+deviceGeneration+state], [principalKey+locationId+entityType+entityId+dispatchable+localSequence], [principalKey+locationId+entityType+entityId+blocked+localSequence], [principalKey+locationId+entityType+entityId+resultVersion]',
    operationEvents: '++sequence, mutationId',
    localMigrationState: 'key',
  })
  const journal = {
    mutationId: 'original',
    principalKey: 'principal',
    locationId: 'location',
    entityType: 'customer',
    entityId: 'entity',
    localSequence: 7,
    envelope: { unknown: { exact: [1, null, 'retain'] } },
    future: { retain: true },
  }
  const delivery = {
    mutationId: 'original',
    principalKey: 'principal',
    locationId: 'location',
    entityType: 'customer',
    entityId: 'entity',
    localSequence: 7,
    state: 'applied',
    result: { status: 'applied', unknown: 'original result' },
    unknown: { retained: true },
  }
  const event = {
    sequence: 12,
    mutationId: 'original',
    kind: 'result',
    details: { unchanged: [null, 7] },
    unknown: 'original event',
  }
  await v5.open()
  await v5.table('operationJournal').add(journal)
  await v5.table('operationDelivery').add(delivery)
  await v5.table('operationEvents').add(event)
  v5.close()
  const current = createKernelDatabase(name)
  try {
    await current.open()
    assert.equal(current.backendDB().version, 70)
    assert.deepEqual(await current.operationJournal.toArray(), [journal])
    assert.deepEqual(await current.operationDelivery.toArray(), [delivery])
    assert.deepEqual(await current.operationEvents.toArray(), [event])
    assert.ok(current.operationJournal.schema.idxByName['[principalKey+locationId+localSequence]'])
    assert.ok(current.operationEvents.schema.idxByName['[mutationId+sequence]'])
    assert.ok(
      current.operationDelivery.schema.idxByName[
        '[principalKey+locationId+entityType+state+localSequence]'
      ],
    )
    assert.ok(
      current.operationDelivery.schema.idxByName[
        '[principalKey+locationId+entityType+state+retryAt]'
      ],
    )
    assert.deepEqual(
      await current.operationDelivery
        .where('[principalKey+locationId+entityType+state+localSequence]')
        .between(
          ['principal', 'location', 'customer', 'applied', 0],
          ['principal', 'location', 'customer', 'applied', 99],
        )
        .toArray(),
      [delivery],
    )
    assert.equal(
      (await current.operationJournal.get('original')).authoredDatasetIncarnation,
      undefined,
    )
  } finally {
    current.close()
    await current.delete()
  }
})

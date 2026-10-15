import { expect, test } from '@playwright/test'
import type {} from '../../tools/kernel-browser/main.js'
import type { QueuedMutation } from '../../src/local/types.js'
import type { ContextTicket, DispatchBatch, LocalCommand } from '../../src/access-kernel/types.js'

for (const nativeVersion of [1, 10, 20, 30, 40]) {
  test(`real IndexedDB: native${nativeVersion} preserves legacy queue/preferences without attribution`, async ({
    page,
  }) => {
    await page.goto('/')
    const result = await page.evaluate(async (nativeVersion) => {
      const name = `kernel-browser-${crypto.randomUUID()}`
      await window.kernelHarness.seedLegacyFixture(name, nativeVersion)
      const original = {
        mutation_id: 'legacy',
        entity_type: 'service_order',
        state: 'retrying',
        payload: { transition: { actor_id: 'claimed-A' }, unknown: ['keep', null, 7] },
        untouched: true,
      }
      const db = window.kernelHarness.createKernelDatabase(name)
      try {
        await db.open()
        const logo = (await db.presentationPreferences.get('["org","A","loc"]')) as unknown as
          { logo: Blob } | undefined
        return {
          nativeVersion: db.backendDB().version,
          stores: db.tables.length,
          original,
          preserved: await db.mutationQueue.get('legacy'),
          journalCount: await db.operationJournal.count(),
          partitions: await db.cachePartitions.count(),
          legacy: await db.localMigrationState.get('identity-kernel-v5'),
          logo: logo ? await logo.logo.text() : null,
        }
      } finally {
        db.close()
        await db.delete()
      }
    }, nativeVersion)
    expect(result.nativeVersion).toBe(70)
    expect(result.stores).toBe(17)
    expect(result.preserved).toEqual(result.original)
    expect(result.journalCount).toBe(0)
    expect(result.partitions).toBe(0)
    expect(result.legacy?.legacyAttribution).toBe('unknown')
    expect(result.logo).toBe(nativeVersion >= 40 ? 'preserved-logo' : null)
  })
}

test('real two-tab IndexedDB generation fences old commands and ACKs with unchanged journals', async ({
  page,
  context,
}) => {
  const other = await context.newPage()
  await page.goto('/')
  await other.goto('/')
  const name = `kernel-two-tab-${crypto.randomUUID()}`
  const initial = await page.evaluate(async (name) => {
    const { createKernelDatabase, AccessKernel } = window.kernelHarness
    const db = createKernelDatabase(name)
    const kernel = new AccessKernel(db)
    const now = Date.now()
    const value = {
      protocol: 1 as const,
      principal: { apiRealm: 'https://example.test/api/v1', organizationId: 'org', userId: 'A' },
      accountLocationId: 'loc',
      selectedLocationId: 'loc',
      capabilities: ['customers.read', 'customers.write', 'sync.push'],
      authorizationEpoch: 'A'.padEnd(43, '_'),
      policyRevision: 'ocwp-access-baseline-2',
      datasetIncarnation: '0199ba00-0000-7000-8000-000000000001',
      verifiedAt: new Date(now).toISOString(),
      offlineUntil: new Date(now + 3_600_000).toISOString(),
      snapshotProtocol: 'baseline-v1' as const,
    }
    const first = await kernel.acceptVerifiedContext(await kernel.beginVerification('tab-A'), value)
    await db.cachePartitions.update(first.ticket.partitionId, {
      baselineComplete: true,
      status: 'active',
      cursor: 'fixture-only',
      baseline: window.kernelHarness.completedMetadata(first.ticket, value, 'fixture-only'),
    })
    const ready = await kernel.acceptVerifiedContext(
      await kernel.beginVerification('tab-A-verified'),
      value,
    )
    const command = {
      envelope: {
        mutation_id: 'A-work',
        entity_type: 'customer' as const,
        entity_id: 'shared',
        operation: 'create' as const,
        organization_id: 'org',
        location_id: 'loc',
        base_version: null,
        occurred_at: value.verifiedAt,
        payload: { display_name: 'Private A' },
      },
      optimistic: {
        customer_id: 'shared',
        organization_id: 'org',
        location_id: 'loc',
        version: 1,
        display_name: 'Private A',
      },
      dependsOn: [],
      localEvents: [],
    }
    await kernel.commitLocalCommand(ready.ticket, command)
    const batch = await kernel.listDispatchable(ready.ticket, 10)
    // Keep the original live session to exercise a real late continuation in the first tab.
    Object.assign(window, {
      isolatedKernelFixture: { db, kernel, ticket: ready.ticket, batch, command },
    })
    return { envelope: batch.operations[0]!.envelope }
  }, name)
  const switched = await other.evaluate(async (name) => {
    const db = window.kernelHarness.createKernelDatabase(name)
    const kernel = new window.kernelHarness.AccessKernel(db)
    const now = Date.now()
    const value = {
      protocol: 1 as const,
      principal: { apiRealm: 'https://example.test/api/v1', organizationId: 'org', userId: 'B' },
      accountLocationId: 'loc',
      selectedLocationId: 'loc',
      capabilities: ['customers.read', 'customers.write', 'sync.push'],
      authorizationEpoch: 'B'.padEnd(43, '_'),
      policyRevision: 'ocwp-access-baseline-2',
      datasetIncarnation: '0199ba00-0000-7000-8000-000000000001',
      verifiedAt: new Date(now).toISOString(),
      offlineUntil: new Date(now + 3_600_000).toISOString(),
      snapshotProtocol: 'baseline-v1' as const,
    }
    const first = await kernel.acceptVerifiedContext(await kernel.beginVerification('tab-B'), value)
    await db.cachePartitions.update(first.ticket.partitionId, {
      baselineComplete: true,
      status: 'active',
      cursor: 'fixture-only',
      baseline: window.kernelHarness.completedMetadata(first.ticket, value, 'fixture-only'),
    })
    const ready = await kernel.acceptVerifiedContext(
      await kernel.beginVerification('tab-B-verified'),
      value,
    )
    const dispatch = await kernel.listDispatchable(ready.ticket, 10)
    const row = await kernel.readEntity(ready.ticket, 'customer', 'shared')
    db.close()
    return { count: dispatch.operations.length, visible: row !== undefined }
  }, name)
  expect(switched).toEqual({ count: 0, visible: false })
  const late = await page.evaluate(async () => {
    type Fixture = {
      db: ReturnType<typeof window.kernelHarness.createKernelDatabase>
      kernel: InstanceType<typeof window.kernelHarness.AccessKernel>
      ticket: ContextTicket
      batch: DispatchBatch
      command: LocalCommand
    }
    const { db, kernel, ticket, batch, command } = (
      window as unknown as { isolatedKernelFixture: Fixture }
    ).isolatedKernelFixture
    const errors: string[] = []
    for (const action of [
      () =>
        kernel.commitLocalCommand(ticket, {
          ...command,
          envelope: { ...command.envelope, mutation_id: 'late-A' },
        }),
      () =>
        kernel.applyPushResult(ticket, batch, {
          results: [
            { mutation_id: 'A-work', entity_id: 'shared', status: 'applied', entity_version: 1 },
          ],
        }),
    ]) {
      try {
        await action()
      } catch (error) {
        errors.push(String(error))
      }
    }
    const original = await db.operationJournal.get('A-work')
    const count = await db.operationJournal.count()
    const state = await db.operationDelivery.get('A-work')
    db.close()
    await db.delete()
    return { errors, envelope: original?.envelope, count, state: state?.state }
  })
  expect(late.errors).toHaveLength(2)
  expect(late.errors.every((error) => /fenced/.test(error))).toBe(true)
  expect(late.envelope).toEqual(initial.envelope)
  expect(late.count).toBe(1)
  expect(late.state).toBe('inflight')
})

test('real IndexedDB upgrade abort leaves the original native40 database recoverable', async ({
  page,
}) => {
  await page.goto('/')
  const result = await page.evaluate(async () => {
    const name = `kernel-abort-${crypto.randomUUID()}`
    await window.kernelHarness.seedLegacyFixture(name, 40)
    const candidate = window.kernelHarness.createKernelDatabase(name)
    let abortReached = false
    candidate.version(5).upgrade((transaction) => {
      abortReached = true
      transaction.abort()
    })
    let rejected = false
    try {
      await candidate.open()
    } catch {
      rejected = true
    } finally {
      candidate.close()
    }
    const reopen = indexedDB.open(name)
    const db = await new Promise<IDBDatabase>((resolve, reject) => {
      reopen.onsuccess = () => resolve(reopen.result)
      reopen.onerror = () => reject(reopen.error)
    })
    const query = db.transaction('mutationQueue').objectStore('mutationQueue').get('legacy')
    const row = await new Promise((resolve, reject) => {
      query.onsuccess = () => resolve(query.result)
      query.onerror = () => reject(query.error)
    })
    const version = db.version
    db.close()
    await candidate.delete()
    return { rejected, row, version, abortReached }
  })
  expect(result).toEqual({
    rejected: true,
    row: {
      mutation_id: 'legacy',
      entity_type: 'service_order',
      state: 'retrying',
      payload: { transition: { actor_id: 'claimed-A' }, unknown: ['keep', null, 7] },
      untouched: true,
    },
    abortReached: true,
    version: 40,
  })
})

test('real IndexedDB records the old-bundle activation blocker without pretending v4 fails closed', async ({
  page,
}) => {
  await page.goto('/')
  const result = await page.evaluate(async () => {
    const name = `kernel-old-bundle-${crypto.randomUUID()}`
    const candidate = window.kernelHarness.createKernelDatabase(name)
    await candidate.open()
    candidate.close()
    const old = new window.kernelHarness.OcwpDatabase(name)
    try {
      await old.open()
      await old.mutationQueue.add({ mutation_id: 'legacy-write' } as QueuedMutation)
      return { version: old.backendDB().version, legacyWrites: await old.mutationQueue.count() }
    } finally {
      old.close()
      await candidate.delete()
    }
  })
  expect(result).toEqual({ version: 70, legacyWrites: 1 })
})

test('real IndexedDB native50 to native70 preserves journal and unknown evidence exactly', async ({
  page,
}) => {
  await page.goto('/')
  const result = await page.evaluate(async () => {
    const name = `kernel-v5-upgrade-${crypto.randomUUID()}`
    const old = new window.kernelHarness.OcwpDatabase(name)
    old.version(5).stores({
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
      mutationId: 'retained',
      principalKey: 'author',
      locationId: 'workshop',
      entityType: 'customer',
      entityId: 'customer',
      localSequence: 7,
      envelope: { unknown: [1, null, 'preserve'] },
      future: { untouched: true },
    }
    const delivery = {
      mutationId: 'retained',
      principalKey: 'author',
      locationId: 'workshop',
      entityType: 'customer',
      entityId: 'customer',
      localSequence: 7,
      state: 'applied',
      unknown: { exact: true },
    }
    const event = {
      sequence: 12,
      mutationId: 'retained',
      kind: 'result',
      details: { unknown: [null, 7] },
    }
    await old.open()
    const beforeVersion = old.backendDB().version
    await old.table('operationJournal').add(journal)
    await old.table('operationDelivery').add(delivery)
    await old.table('operationEvents').add(event)
    old.close()
    const current = window.kernelHarness.createKernelDatabase(name)
    try {
      await current.open()
      return {
        beforeVersion,
        afterVersion: current.backendDB().version,
        original: { journal, delivery, event },
        retained: {
          journal: await current.operationJournal.get('retained'),
          delivery: await current.operationDelivery.get('retained'),
          event: await current.operationEvents.get(12),
        },
        indexed: Boolean(
          current.operationJournal.schema.idxByName['[principalKey+locationId+localSequence]'],
        ),
      }
    } finally {
      current.close()
      await current.delete()
    }
  })
  expect(result.beforeVersion).toBe(50)
  expect(result.afterVersion).toBe(70)
  expect(result.retained).toEqual(result.original)
  expect(result.retained.journal).not.toHaveProperty('authoredDatasetIncarnation')
  expect(result.indexed).toBe(true)
})

test('real IndexedDB native60 to native70 retains every original store and closes the old connection', async ({
  page,
}) => {
  await page.goto('/')
  const result = await page.evaluate(async () => {
    const name = `branding-v6-upgrade-${crypto.randomUUID()}`
    const candidate = window.kernelHarness.createKernelDatabase(name)
    const schemas = candidate.tables
      .filter((table) => table.name !== 'brandingSnapshots')
      .map((table) => ({ name: table.name, schema: table.schema }))
    const open = indexedDB.open(name, 60)
    open.onupgradeneeded = () => {
      for (const { name, schema } of schemas) {
        const store = open.result.createObjectStore(name, {
          keyPath: schema.primKey.keyPath!,
          autoIncrement: schema.primKey.auto === true,
        })
        for (const index of schema.indexes)
          store.createIndex(index.name, index.keyPath!, {
            unique: index.unique === true,
            multiEntry: index.multi === true,
          })
      }
    }
    const old = await new Promise<IDBDatabase>((resolve, reject) => {
      open.onsuccess = () => resolve(open.result)
      open.onerror = () => reject(open.error)
    })
    const originals: Record<string, unknown>[] = []
    const tx = old.transaction(
      schemas.map((item) => item.name),
      'readwrite',
    )
    for (const { name, schema } of schemas) {
      const row: Record<string, unknown> = { unknown: { exact: ['keep', null, 7] } }
      for (const key of Array.isArray(schema.primKey.keyPath)
        ? schema.primKey.keyPath
        : [schema.primKey.keyPath!])
        row[key] = key === 'sequence' ? 7 : `original-${key}`
      originals.push({ name, rows: [row] })
      tx.objectStore(name).add(row)
    }
    await new Promise<void>((resolve, reject) => {
      tx.oncomplete = () => resolve()
      tx.onabort = () => reject(tx.error)
    })
    let closed = false
    old.onversionchange = () => {
      closed = true
      old.close()
    }
    try {
      await candidate.open()
      const retained = await Promise.all(
        schemas.map(async ({ name }) => ({ name, rows: await candidate.table(name).toArray() })),
      )
      return {
        closed,
        nativeVersion: candidate.backendDB().version,
        stores: candidate.tables.length,
        originalStores: schemas.length,
        originals,
        retained,
        snapshots: await candidate.brandingSnapshots.count(),
      }
    } finally {
      old.close()
      candidate.close()
      await candidate.delete()
    }
  })
  expect(result.closed).toBe(true)
  expect(result.nativeVersion).toBe(70)
  expect(result.originalStores).toBe(16)
  expect(result.stores).toBe(17)
  expect(result.retained).toEqual(result.originals)
  expect(result.snapshots).toBe(0)
})

test('real native first admission copies personal v1 default palette and preserves missing/null/local provenance', async ({
  page,
}) => {
  await page.goto('/')
  const result = await page.evaluate(async () => {
    const results = []
    const png =
      'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNQCbD7DwADAAGyeEyo+gAAAABJRU5ErkJggg=='
    for (const value of [undefined, null, png]) {
      const scope = { organizationId: 'org', userId: 'A', locationId: 'loc' }
      const source = new window.kernelHarness.OcwpDatabase(`legacy-branding-${crypto.randomUUID()}`)
      const target = window.kernelHarness.createKernelDatabase(
        `admitted-branding-${crypto.randomUUID()}`,
      )
      const appearance = {
        ...scope,
        locationId: null,
        key: '["appearance","org","A"]',
        kind: 'appearance' as const,
        value: {
          schemaVersion: 1,
          themeId: 'noche',
          paletteId: 'bosque',
          scheme: 'dark',
          density: 'workshop',
          logoDataUrl: null,
        },
        unknown: { retained: true },
      }
      await source.open()
      await source.presentationPreferences.put(appearance)
      if (value !== undefined)
        await source.presentationPreferences.put({
          ...scope,
          key: '["logo","org","A","loc"]',
          kind: 'logo',
          value,
        })
      const original = await source.presentationPreferences.toArray()
      await target.open()
      const ticket = {
        deviceGeneration: 1,
        tabAttemptId: 'tab',
        partitionId: 'p',
        principalKey: 'k',
        authorizationEpoch: 'epoch',
      }
      await target.deviceControl.put({
        key: 'device',
        generation: 1,
        tabAttemptId: 'tab',
        activePartitionId: 'p',
        state: 'READY',
        observedAt: Date.now(),
        localSequence: 0,
        dispatchAttemptId: null,
        dispatchScanAfter: 0,
      })
      try {
        await window.kernelHarness.copyOwnedLegacyPreferences({
          factory: indexedDB,
          name: source.name,
          database: target,
          scope,
          ticket,
          isCurrent: () => true,
        })
        const loaded = await new window.kernelHarness.PreferenceRepository(
          target.presentationPreferences,
        ).load(scope)
        results.push({
          original,
          preserved: await source.presentationPreferences.toArray(),
          copied: await target.presentationPreferences.toArray(),
          version: source.backendDB().version,
          preferences: loaded.preferences,
          journal: await target.operationJournal.count(),
        })
      } finally {
        source.close()
        target.close()
        await source.delete()
        await target.delete()
      }
    }
    return results
  })
  for (const [index, entry] of result.entries()) {
    expect(entry.preserved).toEqual(entry.original)
    expect(entry.copied).toEqual(entry.original)
    expect(entry.version).toBe(40)
    expect(entry.journal).toBe(0)
    expect(entry.preferences.paletteSource).toBe('personal')
    expect(entry.preferences.paletteId).toBe('bosque')
    expect(entry.preferences.logoMode).toBe(['workshop', 'none', 'local'][index])
    expect(entry.preferences.themeId).toBe('noche')
  }
})

test('real native branding cache uses admitted offline reload and fences late digest after takeover', async ({
  page,
}) => {
  await page.goto('/')
  const result = await page.evaluate(async () => {
    const { AccessKernel, createKernelDatabase, BrandingSnapshotRepository, completedMetadata } =
      window.kernelHarness
    const db = createKernelDatabase(`native-branding-cache-${crypto.randomUUID()}`)
    let now = Date.now()
    const kernel = new AccessKernel(db, { now: () => now, newId: () => crypto.randomUUID() })
    const context = {
      protocol: 1 as const,
      principal: { apiRealm: 'https://example.test/api/v1', organizationId: 'org', userId: 'A' },
      selectedLocationId: 'loc',
      accountLocationId: 'loc',
      capabilities: ['branding.read'],
      authorizationEpoch: 'A'.repeat(43),
      policyRevision: 'ocwp-access-baseline-2',
      datasetIncarnation: '0199ba00-0000-7000-8000-000000000001',
      verifiedAt: new Date(now).toISOString(),
      offlineUntil: new Date(now + 3600000).toISOString(),
      snapshotProtocol: 'baseline-v1' as const,
    }
    await db.open()
    const first = await kernel.acceptVerifiedContext(
      await kernel.beginVerification('native-tab'),
      context,
    )
    await db.cachePartitions.update(first.ticket.partitionId, {
      baselineComplete: true,
      status: 'active',
      cursor: 'fixture',
      baseline: completedMetadata(first.ticket, context, 'fixture'),
    })
    const ready = await kernel.acceptVerifiedContext(
      await kernel.beginVerification('native-verified'),
      context,
    )
    const encoded =
      'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNQCbD7DwADAAGyeEyo+gAAAABJRU5ErkJggg=='
    const bytes = Uint8Array.from(atob(encoded), (character) => character.charCodeAt(0))
    const digest = Array.from(
      new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)),
      (byte) => byte.toString(16).padStart(2, '0'),
    ).join('')
    const brand = {
      schema_version: 1 as const,
      organization_id: 'org',
      location_id: 'loc',
      dataset_incarnation: context.datasetIncarnation,
      version: 1,
      display_name: 'Synthetic workshop',
      palette_id: 'arcilla' as const,
      logo_state: 'available' as const,
      logo: {
        sha256: digest,
        byte_count: bytes.length,
        width: 1,
        height: 1,
        mime_type: 'image/png' as const,
        png_base64: encoded,
      },
      logo_diagnostic: null,
      updated_at: context.verifiedAt,
      updated_by: 'A',
    }
    const repo = new BrandingSnapshotRepository(db)
    try {
      const written = await repo.write(ready.ticket, context, brand, now)
      const admission = await kernel.rememberSession(ready.ticket, 'native-branding-binding')
      const reloaded = new AccessKernel(db, { now: () => now, newId: () => crypto.randomUUID() })
      const offline = await reloaded.resumeOffline(admission, 'offline-reload')
      const read = await repo.read(offline.ticket, context, now)
      const offlineWrite = await repo.write(offline.ticket, context, { ...brand, version: 2 }, now)
      const crossUser = await repo.read(
        offline.ticket,
        { ...context, principal: { ...context.principal, userId: 'B' } },
        now,
      )
      const originalDigest = crypto.subtle.digest.bind(crypto.subtle)
      let release!: () => void, entered!: () => void
      const gate = new Promise<void>((resolve) => {
        release = resolve
      })
      const started = new Promise<void>((resolve) => {
        entered = resolve
      })
      crypto.subtle.digest = async (...args) => {
        entered()
        await gate
        return originalDigest(...args)
      }
      let late
      try {
        const pending = repo.read(offline.ticket, context, now)
        await started
        await new AccessKernel(db).beginVerification('takeover')
        release()
        late = await pending
      } finally {
        crypto.subtle.digest = originalDigest
      }
      now += 3600000
      const expired = await repo.read(offline.ticket, context, now)
      return {
        written,
        read,
        brand,
        offlineWrite,
        crossUser,
        late,
        expired,
        journal: await db.operationJournal.count(),
      }
    } finally {
      db.close()
      await db.delete()
    }
  })
  expect(result.written).toBe(true)
  expect(result.read).toEqual(result.brand)
  expect(result.offlineWrite).toBe(false)
  expect(result.crossUser).toBeNull()
  expect(result.late).toBeNull()
  expect(result.expired).toBeNull()
  expect(result.journal).toBe(0)
})

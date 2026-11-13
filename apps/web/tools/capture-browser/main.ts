import { createKernelDatabase } from '../../src/access-kernel/database.js'
import type { CaptureDraftContent } from '../../src/access-kernel/capture-checkpoint-types.js'
import * as current from '../../src/access-kernel/capture-checkpoint-store.js'
import * as historical from './.tmp-legacy/capture-checkpoint-store.js'
import provenance from './.tmp-legacy/provenance.json'
const databases = new Map<string, ReturnType<typeof createKernelDatabase>>()
const id = '11111111-1111-4111-8111-111111111111'
const generation = '22222222-2222-4222-8222-222222222222'
const now = 1000,
  binding = 'a'.repeat(64),
  scopeKey = 'b'.repeat(64)
async function open(name: string) {
  if (!/^capture-native-[a-z0-9-]+$/.test(name))
    throw Error('Synthetic capture boundary name required')
  let db = databases.get(name)
  if (!db) {
    db = createKernelDatabase(name)
    databases.set(name, db)
  }
  await db.open()
  return db
}
const harness = {
  provenance,
  async seed(name: string, label: string) {
    const db = await open(name)
    if (await db.captureCheckpoints.count()) throw Error('Never overwrite an existing fixture')
    await db.deviceControl.put({
      key: 'device',
      generation: 1,
      tabAttemptId: null,
      activePartitionId: null,
      state: 'LOCKED',
      localSequence: 0,
      observedAt: now,
      dispatchAttemptId: null,
      dispatchScanAfter: 0,
    })
    const call = (command: Parameters<typeof current.applyCaptureCheckpoint>[1]) =>
      db.transaction('rw', [db.deviceControl, db.captureCheckpoints, db.captureDraftContents], () =>
        current.applyCaptureCheckpoint(db, command, binding, scopeKey, now),
      )
    const scope = {} as Parameters<typeof current.applyCaptureCheckpoint>[1]['scope']
    if ((await call({ kind: 'enroll', checkpointId: id, generation, scope })).kind !== 'ack')
      throw Error('Enrollment failed')
    for (const content of [
      { channel: 'customer' as const, draft: { displayName: label, phone: '', email: '' } },
      {
        channel: 'order' as const,
        draft: {
          customerId: 'synthetic',
          priority: 'normal' as const,
          reportedProblem: label,
          intakeCondition: '',
          accessories: '',
          withBicycle: false,
          brand: '',
          model: '',
        },
        retainedSelection: { customerId: '', priority: 'normal' as const },
      },
    ])
      if (
        (
          await call({
            kind: 'save',
            checkpointId: id,
            generation,
            scope,
            channel: content.channel,
            expectedRevision: 0,
            content,
          })
        ).kind !== 'ack'
      )
        throw Error('Save failed')
    const row = await db.captureDraftContents.get([id, 'order'])
    if (!row) throw Error('Missing fixture')
    await db.captureDraftContents.put({
      ...row,
      format: 2,
      draft: { opaqueFuture: label },
    } as unknown as CaptureDraftContent)
    return this.snapshot(name)
  },
  async snapshot(name: string) {
    const db = await open(name)
    return {
      contents: await db.captureDraftContents.toArray(),
      checkpoints: await db.captureCheckpoints.toArray(),
    }
  },
  async sweep(name: string, reader: 'current' | 'historical') {
    const db = await open(name)
    return (reader === 'current' ? current : historical).sweepExpiredCaptureContents(db, now)
  },
  async load(name: string, reader: 'current' | 'historical') {
    const db = await open(name)
    return db.transaction(
      'rw',
      [db.deviceControl, db.captureCheckpoints, db.captureDraftContents],
      () =>
        (reader === 'current' ? current : historical).applyCaptureCheckpoint(
          db,
          {
            kind: 'load',
            checkpointId: id,
            scope: {} as Parameters<typeof current.applyCaptureCheckpoint>[1]['scope'],
          },
          binding,
          scopeKey,
          now,
        ),
    )
  },
  async upgrade(name: string) {
    const db = await open(name)
    let changed = false
    db.on('versionchange', () => {
      changed = true
      db.close()
    })
    const newer = createKernelDatabase(name)
    newer.version(9).stores({})
    await newer.open()
    const version = newer.backendDB().version
    newer.close()
    await db.open()
    return { changed, version, reopenedVersion: db.backendDB().version }
  },
}
declare global {
  interface Window {
    captureBoundaryHarness: typeof harness
  }
}
window.captureBoundaryHarness = harness

import { createKernelDatabase } from '../../.tmp-kernel/src/access-kernel/database.js'
import { AccessKernel } from '../../.tmp-kernel/src/access-kernel/kernel.js'
import { canonicalJson } from '../../.tmp-kernel/src/access-kernel/operations.js'
import { completedMetadata } from '../../tests/access-kernel/baseline-fixture.mjs'
import { snapshotSource, revalidateSource } from '../capture-handover/source.mjs'
import { createCustodyStore, stageCustody, readCustody } from '../capture-handover/staging.mjs'
import { observeSource, recheckObservation } from '../source-transition/diagnostic.mjs'
import { stageObservedDraft } from '../capture-handover/coordinator.mjs'

// This entry imports the same prototype modules as the Node suite. Only the
// synthetic fixture and explicit driver transport live here; no authority bypass.
const sources = new Map(),
  targets = new Map(),
  observations = new Map(),
  syntheticDispatches = new Map()
const sourceName = (name) => {
  if (!/^ocwp-synthetic-custody-source-[a-z0-9-]{1,60}$/.test(name))
    throw Error('Synthetic source name required')
}
const targetName = (name) => {
  if (!/^ocwp-synthetic-custody-target-[a-z0-9-]{1,60}$/.test(name))
    throw Error('Synthetic target name required')
}
const exists = async (name) =>
  (await globalThis.indexedDB.databases()).some((entry) => entry.name === name)
async function source(descriptor) {
  sourceName(descriptor.name)
  if (!sources.has(descriptor.name)) {
    if (!(await exists(descriptor.name))) throw Error('Existing synthetic source required')
    const db = createKernelDatabase(descriptor.name)
    await db.open()
    const clock = { now: descriptor.now }
    sources.set(descriptor.name, {
      db,
      clock,
      kernel: new AccessKernel(db, {
        now: () => clock.now,
        newId: () => globalThis.crypto.randomUUID(),
      }),
    })
  }
  return sources.get(descriptor.name)
}
async function target(name, create = false) {
  targetName(name)
  if (!targets.has(name)) {
    if (!create && !(await exists(name))) throw Error('Existing synthetic custody required')
    const db = createCustodyStore(name)
    await db.open()
    targets.set(name, db)
  }
  return targets.get(name)
}
const sourceOptions = (db, descriptor) => ({
  db,
  ticket: descriptor.ticket,
  scope: descriptor.scope,
  checkpointId: descriptor.checkpointId,
  now: descriptor.now,
  isCurrent: () => true,
})
const syntheticContext = (now) => ({
  protocol: 1,
  principal: {
    apiRealm: 'https://synthetic.invalid/api/v1',
    organizationId: 'synthetic-org',
    userId: 'synthetic-user',
  },
  accountLocationId: 'synthetic-location',
  selectedLocationId: 'synthetic-location',
  capabilities: ['customers.read', 'customers.write', 'orders.write', 'sync.push'],
  authorizationEpoch: 'synthetic-epoch'.padEnd(43, '_'),
  policyRevision: 'ocwp-access-baseline-2',
  datasetIncarnation: '0199ba00-0000-7000-8000-000000000001',
  verifiedAt: new Date(now).toISOString(),
  offlineUntil: new Date(now + 3600000).toISOString(),
  snapshotProtocol: 'baseline-v1',
})

const harness = {
  async advanceSyntheticClock(descriptor, now) {
    const { clock } = await source(descriptor)
    if (!Number.isSafeInteger(now) || now < clock.now)
      throw Error('Monotonic synthetic clock required')
    clock.now = now
    return { ...descriptor, now }
  },
  async observeWork(descriptor) {
    const { db } = await source(descriptor)
    const result = await observeSource(sourceOptions(db, descriptor))
    if (result.kind !== 'observation') return result
    const observationId = globalThis.crypto.randomUUID()
    observations.set(observationId, { name: descriptor.name, witness: result.witness })
    return { kind: result.kind, receipt: result.receipt, observationId }
  },
  async recheckWork(descriptor, observationId) {
    const { db } = await source(descriptor)
    const prior = observations.get(observationId)
    if (!prior || prior.name !== descriptor.name) return { kind: 'refused', reason: 'witness' }
    return recheckObservation(sourceOptions(db, descriptor), prior.witness)
  },
  async createSyntheticPending(descriptor) {
    const { kernel } = await source(descriptor)
    return kernel.commitLocalCommand(descriptor.ticket, {
      envelope: {
        mutation_id: 'synthetic-diagnostic-operation',
        entity_type: 'customer',
        entity_id: 'synthetic-diagnostic-customer',
        operation: 'create',
        organization_id: descriptor.owner.organizationId,
        location_id: descriptor.owner.selectedLocationId,
        base_version: null,
        occurred_at: new Date(descriptor.now).toISOString(),
        payload: { display_name: 'Synthetic private diagnostic customer' },
      },
      optimistic: {
        customer_id: 'synthetic-diagnostic-customer',
        organization_id: descriptor.owner.organizationId,
        location_id: descriptor.owner.selectedLocationId,
        version: 1,
        display_name: 'Synthetic private diagnostic customer',
      },
      dependsOn: [],
      localEvents: [{ action: 'synthetic-diagnostic' }],
    })
  },
  async claimSyntheticPending(descriptor) {
    const { kernel } = await source(descriptor)
    const batch = await kernel.listDispatchable(descriptor.ticket, 1)
    if (
      batch.operations.length !== 1 ||
      batch.operations[0].mutationId !== 'synthetic-diagnostic-operation'
    )
      throw Error('Exact synthetic operation required')
    syntheticDispatches.set(descriptor.name, batch)
    return batch.operations.length
  },
  async acknowledgeSyntheticApplied(descriptor) {
    const { kernel } = await source(descriptor)
    const batch = syntheticDispatches.get(descriptor.name)
    if (!batch) throw Error('Synthetic dispatch required')
    // Fabricated server result in an owned test fixture, never a network request.
    await kernel.applyPushResult(descriptor.ticket, batch, {
      results: [
        {
          mutation_id: 'synthetic-diagnostic-operation',
          entity_id: 'synthetic-diagnostic-customer',
          status: 'applied',
          entity_version: 1,
        },
      ],
    })
    syntheticDispatches.delete(descriptor.name)
  },
  async verifyEditor(descriptor) {
    const { kernel } = await source(descriptor)
    const accepted = await kernel.acceptVerifiedContext(
      await kernel.beginVerification(globalThis.crypto.randomUUID(), () => true, descriptor.ticket),
      syntheticContext(descriptor.now),
    )
    if (accepted.state !== 'READY') throw Error('Synthetic editor admission refused')
    await kernel.rememberSession(accepted.ticket, 'synthetic-binding')
    return { ...descriptor, ticket: accepted.ticket }
  },
  async releaseSource(descriptor) {
    sourceName(descriptor.name)
    sources.get(descriptor.name)?.db.close()
    sources.delete(descriptor.name)
    syntheticDispatches.delete(descriptor.name)
    for (const [id, value] of observations)
      if (value.name === descriptor.name) observations.delete(id)
  },
  async seedSource(name, now) {
    sourceName(name)
    if (await exists(name)) throw Error('Never reseed an existing database')
    const db = createKernelDatabase(name)
    const clock = { now }
    const kernel = new AccessKernel(db, {
      now: () => clock.now,
      newId: () => globalThis.crypto.randomUUID(),
    })
    await db.open()
    sources.set(name, { db, kernel, clock })
    const value = syntheticContext(now)
    const verify = async () =>
      kernel.acceptVerifiedContext(
        await kernel.beginVerification(globalThis.crypto.randomUUID()),
        value,
      )
    const initial = await verify()
    await db.cachePartitions.update(initial.ticket.partitionId, {
      baselineComplete: true,
      status: 'active',
      cursor: 'synthetic-checkpoint',
      baseline: completedMetadata(initial.ticket, value, 'synthetic-checkpoint'),
    })
    const accepted = await verify()
    if (accepted.state !== 'READY') throw Error('Synthetic completion refused')
    const ticket = accepted.ticket
    await kernel.rememberSession(ticket, 'synthetic-binding')
    const scope = {
      ...value.principal,
      selectedLocationId: value.selectedLocationId,
      datasetIncarnation: value.datasetIncarnation,
      authorizationEpoch: value.authorizationEpoch,
      policyRevision: value.policyRevision,
      capabilities: value.capabilities,
      sessionBindingId: 'synthetic-binding',
    }
    const checkpointId = globalThis.crypto.randomUUID(),
      generation = globalThis.crypto.randomUUID()
    if (
      (await kernel.checkpointCapture(ticket, { kind: 'enroll', checkpointId, generation, scope }))
        .kind !== 'ack'
    )
      throw Error('Enrollment refused')
    for (const content of [
      {
        channel: 'customer',
        draft: { displayName: '  Synthetic\n\t二 ', email: '', phone: ' 123 ' },
      },
      {
        channel: 'order',
        draft: {
          customerId: 'synthetic-customer',
          priority: 'normal',
          reportedProblem: 'Synthetic brake\nnoise',
          intakeCondition: '',
          accessories: '',
          withBicycle: false,
          brand: '',
          model: '',
        },
        retainedSelection: { customerId: 'synthetic-customer', priority: 'normal' },
      },
    ]) {
      const result = await kernel.checkpointCapture(ticket, {
        kind: 'save',
        checkpointId,
        generation,
        scope,
        channel: content.channel,
        expectedRevision: 0,
        content,
      })
      if (result.kind !== 'ack') throw Error('Synthetic save refused')
    }
    return {
      name,
      now,
      ticket,
      scope,
      checkpointId,
      generation,
      owner: {
        ...value.principal,
        selectedLocationId: value.selectedLocationId,
        datasetIncarnation: value.datasetIncarnation,
      },
    }
  },
  async sourceBytes(descriptor) {
    const { db } = await source(descriptor)
    return db.transaction('r', db.tables, async () =>
      canonicalJson(
        Object.fromEntries(
          await Promise.all(db.tables.map(async (table) => [table.name, await table.toArray()])),
        ),
      ),
    )
  },
  async snapshot(descriptor) {
    const { db } = await source(descriptor)
    const result = await snapshotSource(sourceOptions(db, descriptor))
    // Opaque witnesses are deliberately not exported to the driver or another origin.
    return result.kind === 'snapshot' ? { kind: result.kind, bundle: result.bundle } : result
  },
  async editSource(descriptor, displayName) {
    const { db, kernel } = await source(descriptor)
    const checkpoint = await db.captureCheckpoints.get(descriptor.checkpointId)
    return kernel.checkpointCapture(descriptor.ticket, {
      kind: 'save',
      checkpointId: descriptor.checkpointId,
      generation: descriptor.generation,
      scope: descriptor.scope,
      channel: 'customer',
      expectedRevision: checkpoint.customer.revision,
      content: { channel: 'customer', draft: { displayName, email: '', phone: ' 123 ' } },
    })
  },
  async run(descriptor) {
    const { db } = await source(descriptor)
    const options = sourceOptions(db, descriptor)
    if (typeof globalThis.window.custodyTransport !== 'function')
      throw Error('Explicit test driver transport required')
    return stageObservedDraft({
      snapshot: () => snapshotSource(options),
      stage: (bundle) => globalThis.window.custodyTransport(bundle),
      recheck: (witness) => revalidateSource(options, witness),
    })
  },
  async initializeTarget(name) {
    if (await exists(name)) throw Error('Never reseed an existing custody database')
    await target(name, true)
  },
  async stage(name, transferId, bundle, owner, now) {
    return stageCustody(await target(name), transferId, bundle, owner, now, () => true)
  },
  async read(name, transferId, owner, now) {
    return readCustody(await target(name), transferId, owner, now, () => true)
  },
  async targetBytes(name) {
    const db = await target(name)
    return canonicalJson(await db.custody.toArray())
  },
  async targetStores(name) {
    return (await target(name)).tables.map((table) => table.name)
  },
  async corrupt(name, transferId) {
    const db = await target(name)
    await db.custody.update(transferId, { canonical: 'synthetic-corruption' })
  },
  async outerAbort(name, transferId, bundle, owner, now, mode) {
    const db = await target(name)
    let result,
      aborted = false
    try {
      await db.transaction('rw', db.custody, async () => {
        if (mode === 'read')
          await db.custody.add({ transferId, bundle, canonical: canonicalJson(bundle) })
        result = await (mode === 'read'
          ? readCustody(db, transferId, owner, now, () => true)
          : stageCustody(db, transferId, bundle, owner, now, () => true))
        throw Error('synthetic-outer-abort')
      })
    } catch (error) {
      if (error.message !== 'synthetic-outer-abort') throw error
      aborted = true
    }
    return { result, aborted, rows: await db.custody.count() }
  },
  async cleanup(descriptor, targetDbName) {
    if (descriptor) {
      const { db } = await source(descriptor)
      db.close()
      await db.delete()
      sources.delete(descriptor.name)
      syntheticDispatches.delete(descriptor.name)
      for (const [id, value] of observations)
        if (value.name === descriptor.name) observations.delete(id)
    }
    if (targetDbName) {
      const db = await target(targetDbName)
      db.close()
      await db.delete()
      targets.delete(targetDbName)
    }
  },
}
globalThis.window.custodyHarness = harness

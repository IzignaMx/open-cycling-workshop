import test from 'node:test'
import assert from 'node:assert/strict'
import { IDBFactory, IDBKeyRange } from 'fake-indexeddb'
import {
  setup,
  context,
  completedBaseline,
  NOW,
} from '../../tests/access-kernel/client-fixture.mjs'
import { snapshotSource, revalidateSource } from './source.mjs'
import { createCustodyStore, stageCustody, readCustody } from './staging.mjs'
import { stageObservedDraft } from './coordinator.mjs'

async function fixture(t) {
  const { db, kernel } = await setup(t),
    value = context()
  const ticket = await completedBaseline(db, kernel, value)
  await kernel.rememberSession(ticket, 'binding-A')
  const scope = {
    ...value.principal,
    selectedLocationId: value.selectedLocationId,
    datasetIncarnation: value.datasetIncarnation,
    authorizationEpoch: value.authorizationEpoch,
    policyRevision: value.policyRevision,
    capabilities: value.capabilities,
    sessionBindingId: 'binding-A',
  }
  const checkpointId = crypto.randomUUID(),
    generation = crypto.randomUUID()
  const base = { checkpointId, generation, scope }
  await kernel.checkpointCapture(ticket, { ...base, kind: 'enroll' })
  const save = (text, expectedRevision) =>
    kernel.checkpointCapture(ticket, {
      ...base,
      kind: 'save',
      channel: 'customer',
      expectedRevision,
      content: { channel: 'customer', draft: { displayName: text, email: '', phone: '' } },
    })
  await save('original', 0)
  const target = createCustodyStore('ocwp-synthetic-custody-' + crypto.randomUUID(), {
    indexedDB: new IDBFactory(),
    IDBKeyRange,
  })
  await target.open()
  t.after(() => target.delete())
  const owner = {
    ...value.principal,
    selectedLocationId: value.selectedLocationId,
    datasetIncarnation: value.datasetIncarnation,
  }
  const options = { db, ticket, scope, checkpointId, now: NOW, isCurrent: () => true }
  return { db, target, owner, options, save }
}
async function sourceBytes(db) {
  return JSON.stringify(await Promise.all(db.tables.map((t) => t.toArray())))
}
for (const phase of ['none', 'before_stage', 'before_recheck', 'after_recheck']) {
  test(`real source/staging protocol preserves ${phase} writes and never activates`, async (t) => {
    const { db, target, owner, options, save } = await fixture(t)
    let expectedBytes = await sourceBytes(db)
    const edit = async () => {
      assert.equal((await save('later edit', 1)).kind, 'ack')
      expectedBytes = await sourceBytes(db)
    }
    const result = await stageObservedDraft({
      snapshot: () => snapshotSource(options),
      stage: async (bundle) => {
        if (phase === 'before_stage') await edit()
        return stageCustody(target, 'transfer', bundle, owner, NOW, () => true)
      },
      recheck: async (witness) => {
        if (phase === 'before_recheck') await edit()
        const observed = await revalidateSource(options, witness)
        if (phase === 'after_recheck') await edit()
        return observed
      },
    })
    assert.deepEqual(result, {
      kind: 'custody_retained',
      observation: ['before_stage', 'before_recheck'].includes(phase)
        ? 'source_changed'
        : 'source_unchanged_at_check',
      operationalUse: 'forbidden',
    })
    assert.equal(await sourceBytes(db), expectedBytes)
    const retained = await readCustody(target, 'transfer', owner, NOW, () => true)
    assert.equal(retained.bundle.contents[0].draft.displayName, 'original')
    assert.equal(
      (await db.captureDraftContents.get([options.checkpointId, 'customer'])).draft.displayName,
      phase === 'none' ? 'original' : 'later edit',
    )
    assert.deepEqual(
      target.tables.map((table) => table.name),
      ['custody'],
    )
  })
}
test('source history appearing after staging preserves inert custody and refuses recheck', async (t) => {
  const { db, target, owner, options } = await fixture(t)
  let expectedBytes
  const result = await stageObservedDraft({
    snapshot: () => snapshotSource(options),
    stage: (bundle) => stageCustody(target, 'transfer', bundle, owner, NOW, () => true),
    recheck: async (witness) => {
      await db.operationDelivery.add({ mutationId: 'uncertain', state: 'inflight' })
      expectedBytes = await sourceBytes(db)
      return revalidateSource(options, witness)
    },
  })
  assert.deepEqual(result, {
    kind: 'custody_retained',
    observation: 'unavailable',
    operationalUse: 'forbidden',
  })
  assert.equal(await sourceBytes(db), expectedBytes)
  assert.equal((await readCustody(target, 'transfer', owner, NOW, () => true)).kind, 'custody')
})

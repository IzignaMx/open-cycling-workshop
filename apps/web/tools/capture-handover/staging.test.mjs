import test from 'node:test'
import assert from 'node:assert/strict'
import { IDBFactory, IDBKeyRange } from 'fake-indexeddb'
import { createCustodyStore, stageCustody, readCustody } from './staging.mjs'
import { captureFixture } from '../capture-app/fixture.mjs'
import { canonicalJson } from '../../.tmp-kernel/src/access-kernel/operations.js'
import { CAPTURE_TTL_MS } from '../../.tmp-kernel/src/access-kernel/capture-checkpoint.js'
const now = 1000000
const owner = {
  apiRealm: 'https://synthetic.invalid',
  organizationId: 'org',
  userId: 'user',
  selectedLocationId: 'loc',
  datasetIncarnation: 'dataset',
}
function bundle() {
  const f = captureFixture(now, CAPTURE_TTL_MS, canonicalJson)
  f.checkpoint.order = {
    revision: 0,
    state: 'EMPTY',
    attemptId: null,
    contentStartedAt: null,
    contentExpiresAt: null,
  }
  return {
    format: 1,
    kind: 'inert-capture-custody',
    owner: { ...owner },
    capturedAt: now,
    checkpoint: f.checkpoint,
    contents: [f.customer],
  }
}
async function setup(t) {
  const db = createCustodyStore('ocwp-synthetic-custody-' + crypto.randomUUID(), {
    indexedDB: new IDBFactory(),
    IDBKeyRange,
  })
  await db.open()
  t.after(() => db.delete())
  return db
}
test('custody stores exact bytes once, reloads without operational stores and never extends TTL', async (t) => {
  const db = await setup(t),
    b = bundle()
  b.contents[0].draft.displayName = '  línea\n\t二 '
  assert.equal((await stageCustody(db, 'transfer-1', b, owner, now, () => true)).kind, 'staged')
  assert.deepEqual((await readCustody(db, 'transfer-1', owner, now, () => true)).bundle, b)
  assert.equal(
    (await stageCustody(db, 'transfer-1', b, owner, now, () => true)).kind,
    'already_staged',
  )
  db.close()
  await db.open()
  assert.deepEqual((await readCustody(db, 'transfer-1', owner, now, () => true)).bundle, b)
  assert.deepEqual(
    db.tables.map((x) => x.name),
    ['custody'],
  )
  assert.equal(
    (await readCustody(db, 'transfer-1', owner, now + CAPTURE_TTL_MS, () => true)).kind,
    'refused',
  )
  assert.equal(await db.custody.count(), 1, 'expiry refuses use, does not silently purge')
})
test('same transfer ID with different bytes conflicts, and wrong principal cannot read', async (t) => {
  const db = await setup(t),
    b = bundle()
  await stageCustody(db, 'id', b, owner, now, () => true)
  b.contents[0].draft.displayName = 'changed'
  assert.equal((await stageCustody(db, 'id', b, owner, now, () => true)).reason, 'conflict')
  const r = await readCustody(db, 'id', { ...owner, userId: 'other' }, now, () => true)
  assert.equal(r.kind, 'refused')
  assert.equal('bundle' in r, false)
})
for (const [label, mutate] of [
  ['future', (b) => (b.contents[0].format = 2)],
  ['protected', (b) => (b.checkpoint.customer.state = 'PROTECTED')],
  ['extra secret', (b) => (b.token = 'secret')],
  ['row mismatch', (b) => b.contents[0].revision++],
  ['expired', (b) => (b.capturedAt = now + CAPTURE_TTL_MS)],
  ['missing', (b) => (b.contents = [])],
  ['duplicate', (b) => b.contents.push(b.contents[0])],
  ['owner extra', (b) => (b.owner.password = 'secret')],
  ['oversize', (b) => (b.contents[0].draft.displayName = 'x'.repeat(70000))],
])
  test('rejects ' + label + ' without partial stage', async (t) => {
    const db = await setup(t),
      b = bundle()
    mutate(b)
    assert.equal((await stageCustody(db, 'id', b, owner, now, () => true)).kind, 'refused')
    assert.equal(await db.custody.count(), 0)
  })
test('quota abort and session loss cannot acknowledge staging', async (t) => {
  const db = await setup(t)
  const fail = () => {
    throw new DOMException('synthetic quota', 'QuotaExceededError')
  }
  db.custody.hook('creating', fail)
  assert.equal((await stageCustody(db, 'id', bundle(), owner, now, () => true)).kind, 'refused')
  assert.equal(await db.custody.count(), 0)
  db.custody.hook('creating').unsubscribe(fail)
  let current = true
  const revoke = () => {
    current = false
  }
  db.custody.hook('creating', revoke)
  assert.equal((await stageCustody(db, 'id', bundle(), owner, now, () => current)).kind, 'refused')
  assert.equal(await db.custody.count(), 0)
})
test('clock rollback, corrupted readback, and stale session never expose content', async (t) => {
  const db = await setup(t)
  await stageCustody(db, 'id', bundle(), owner, now, () => true)
  for (const [time, current] of [
    [now - 1, () => true],
    [now, () => false],
  ])
    assert.equal((await readCustody(db, 'id', owner, time, current)).kind, 'refused')
  await db.custody.update('id', { canonical: 'tampered' })
  assert.equal((await readCustody(db, 'id', owner, now, () => true)).kind, 'refused')
})
test('ordinary or production-like database names are rejected before open', () => {
  assert.throws(() => createCustodyStore('ocwp-authenticated', {}))
})

test('readback mismatch aborts the transaction rather than acknowledging damaged custody', async (t) => {
  const db = await setup(t)
  const corrupt = (_key, row) => {
    row.bundle.contents[0].draft.displayName = 'damaged'
  }
  db.custody.hook('creating', corrupt)
  assert.equal((await stageCustody(db, 'id', bundle(), owner, now, () => true)).kind, 'refused')
  assert.equal(await db.custody.count(), 0)
})
test('concurrent identical retries yield one retained bundle and collision never overwrites it', async (t) => {
  const db = await setup(t),
    b = bundle()
  const results = await Promise.all([
    stageCustody(db, 'id', b, owner, now, () => true),
    stageCustody(db, 'id', b, owner, now, () => true),
  ])
  assert.deepEqual(results.map((r) => r.kind).sort(), ['already_staged', 'staged'])
  assert.equal(await db.custody.count(), 1)
  assert.deepEqual((await readCustody(db, 'id', owner, now, () => true)).bundle, b)
})

test('nested outer transaction cannot receive durable staging acknowledgement before outer abort', async (t) => {
  const db = await setup(t)
  let result
  await assert.rejects(
    db.transaction('rw', db.custody, async () => {
      result = await stageCustody(db, 'id', bundle(), owner, now, () => true)
      throw new Error('outer abort')
    }),
  )
  assert.deepEqual(result, { kind: 'refused', reason: 'nested_transaction' })
  assert.equal(await db.custody.count(), 0)
})

test('nested read cannot expose custody which its outer transaction later aborts', async (t) => {
  const db = await setup(t),
    b = bundle()
  let result
  await assert.rejects(
    db.transaction('rw', db.custody, async () => {
      await db.custody.add({ transferId: 'id', bundle: b, canonical: canonicalJson(b) })
      result = await readCustody(db, 'id', owner, now, () => true)
      throw new Error('outer abort')
    }),
  )
  assert.deepEqual(result, { kind: 'refused', reason: 'nested_transaction' })
  assert.equal(await db.custody.count(), 0)
})

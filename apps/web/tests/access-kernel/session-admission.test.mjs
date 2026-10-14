import test from 'node:test'
import assert from 'node:assert/strict'
import { AccessKernel } from '../../.tmp-kernel/src/access-kernel/kernel.js'
import { setup, context, completedBaseline, NOW } from './client-fixture.mjs'

test('eligible same-session reload binds one exact owner without persisting bearer', async (t) => {
  const { db, kernel } = await setup(t)
  const ticket = await completedBaseline(db, kernel)
  const before = (await db.cachePartitions.get(ticket.partitionId)).baseline
  const admission = await kernel.rememberSession(ticket, 'session-binding')
  const reload = new AccessKernel(db, { now: () => NOW, newId: () => crypto.randomUUID() })
  const resumed = await reload.resumeOffline(admission, 'reloaded', () => true)
  assert.equal(resumed.ticket.deviceGeneration, ticket.deviceGeneration + 1)
  assert.equal(resumed.context.datasetIncarnation, context().datasetIncarnation)
  assert.equal((await reload.inspectSession(resumed.ticket)).state, 'OFFLINE_READY')
  assert.deepEqual(
    (await db.cachePartitions.get(ticket.partitionId)).baseline.origin,
    before.origin,
  )
  await assert.rejects(kernel.inspectSession(ticket), /fenced/)
  await assert.rejects(
    new AccessKernel(db, { now: () => NOW, newId: () => crypto.randomUUID() }).resumeOffline(
      admission,
      'clone',
      () => true,
    ),
    /admission|fenced/,
  )
  const raw = JSON.stringify(await db.cachePartitions.toArray())
  assert.equal(raw.includes('bearer'), false)
})

test('missing, replaced, malformed admission and expired/backward clocks fail closed', async (t) => {
  const { db, kernel } = await setup(t)
  const ticket = await completedBaseline(db, kernel)
  const admission = await kernel.rememberSession(ticket, 'binding')
  for (const remembered of [
    null,
    {},
    { ...admission, format: 2 },
    { ...admission, sessionBindingId: 'replaced' },
  ])
    await assert.rejects(
      new AccessKernel(db, { now: () => NOW, newId: () => crypto.randomUUID() }).resumeOffline(
        remembered,
        'reload',
        () => true,
      ),
    )
  for (const now of [NaN, NOW - 1, NOW + 3600000])
    await assert.rejects(
      new AccessKernel(db, { now: () => now, newId: () => crypto.randomUUID() }).resumeOffline(
        admission,
        'reload',
        () => true,
      ),
    )
  assert.equal((await db.deviceControl.get('device')).generation, ticket.deviceGeneration)
})

test('offline claim quota failure and synchronous session change roll back durable owner', async (t) => {
  const { db, kernel } = await setup(t)
  const ticket = await completedBaseline(db, kernel)
  const admission = await kernel.rememberSession(ticket, 'binding')
  let current = true
  const switchSession = () => {
    current = false
  }
  db.deviceControl.hook('updating', switchSession)
  const reload = new AccessKernel(db, { now: () => NOW, newId: () => crypto.randomUUID() })
  await assert.rejects(
    reload.resumeOffline(admission, 'reload', () => current),
    /fenced/,
  )
  assert.equal((await db.deviceControl.get('device')).generation, ticket.deviceGeneration)
  db.deviceControl.hook('updating').unsubscribe(switchSession)
  const quota = () => {
    throw new DOMException('quota', 'QuotaExceededError')
  }
  db.cachePartitions.hook('updating', quota)
  await assert.rejects(
    reload.resumeOffline(admission, 'reload', () => true),
    /quota/,
  )
  assert.equal((await db.deviceControl.get('device')).generation, ticket.deviceGeneration)
})

test('simultaneous cloned session claims admit exactly one generation and preserve initial evidence', async (t) => {
  const { db, kernel } = await setup(t)
  const ticket = await completedBaseline(db, kernel)
  const admission = await kernel.rememberSession(ticket, 'binding')
  const a = new AccessKernel(db, { now: () => NOW, newId: () => crypto.randomUUID() })
  const b = new AccessKernel(db, { now: () => NOW, newId: () => crypto.randomUUID() })
  const outcomes = await Promise.allSettled([
    a.resumeOffline(admission, 'clone-a'),
    b.resumeOffline(admission, 'clone-b'),
  ])
  assert.equal(outcomes.filter((x) => x.status === 'fulfilled').length, 1)
  assert.equal(outcomes.filter((x) => x.status === 'rejected').length, 1)
  assert.equal((await db.deviceControl.get('device')).generation, ticket.deviceGeneration + 1)
})

test('postcommit session replacement never installs a resumed volatile ticket', async (t) => {
  const { db, kernel } = await setup(t)
  const ticket = await completedBaseline(db, kernel)
  const admission = await kernel.rememberSession(ticket, 'binding')
  let current = true
  const reload = new AccessKernel(db, { now: () => NOW, newId: () => crypto.randomUUID() })
  const transaction = db.transaction.bind(db)
  db.transaction = async (...args) => {
    const result = await transaction(...args)
    if (args[0] === 'r') current = false
    return result
  }
  await assert.rejects(
    reload.resumeOffline(admission, 'reload', () => current),
    /fenced/,
  )
  const owner = (await db.cachePartitions.get(ticket.partitionId)).sessionAdmission.owner
  await assert.rejects(reload.inspectSession(owner), /fenced/)
})

test('unknown or incomplete baseline and stale reconnect compare-and-swap cannot admit or take over', async (t) => {
  const { db, kernel } = await setup(t)
  const ticket = await completedBaseline(db, kernel)
  const admission = await kernel.rememberSession(ticket, 'binding')
  const original = await db.cachePartitions.get(ticket.partitionId)
  for (const patch of [
    { baselineComplete: false },
    { baseline: { ...original.baseline, format: 999 } },
  ]) {
    await db.cachePartitions.put({ ...original, ...patch })
    await assert.rejects(
      new AccessKernel(db, { now: () => NOW, newId: () => crypto.randomUUID() }).resumeOffline(
        admission,
        'reload',
      ),
      /proof/,
    )
  }
  await db.cachePartitions.put(original)
  const winner = new AccessKernel(db, { now: () => NOW, newId: () => crypto.randomUUID() })
  const active = await winner.resumeOffline(admission, 'winner')
  await assert.rejects(
    kernel.beginVerification('stale-reconnect', () => true, ticket),
    /owner fenced/,
  )
  assert.equal((await winner.inspectSession(active.ticket)).state, 'OFFLINE_READY')
})

test('equivalent verification and offline resume rebind incremental owner but preserve anchor and receipt', async (t) => {
  const { db, kernel } = await setup(t)
  const ctx = context('A', {
    capabilities: ['customers.read', 'customers.write', 'sync.push', 'sync.pull'],
  })
  let ticket = await completedBaseline(db, kernel, ctx)
  await kernel.pendingIncremental(ticket)
  const original = await db.cachePartitions.get(ticket.partitionId)
  const next = await kernel.beginVerification('renewed', () => true, ticket)
  ticket = (await kernel.acceptVerifiedContext(next, ctx)).ticket
  const rebound = await db.cachePartitions.get(ticket.partitionId)
  assert.deepEqual(rebound.baseline.origin, original.baseline.origin)
  assert.deepEqual(rebound.baseline.receipt, original.baseline.receipt)
  assert.deepEqual(rebound.incremental, { ...original.incremental, owner: ticket })
  const admission = await kernel.rememberSession(ticket, 'binding')
  const reload = new AccessKernel(db, { now: () => NOW, newId: () => crypto.randomUUID() })
  const resumed = await reload.resumeOffline(admission, 'reload')
  assert.deepEqual(
    (await db.cachePartitions.get(ticket.partitionId)).incremental.owner,
    resumed.ticket,
  )
  assert.equal(
    (await reload.pendingIncremental(resumed.ticket)).incremental.initialCheckpoint,
    original.baseline.checkpoint,
  )
})

import test from 'node:test'
import assert from 'node:assert/strict'
import { setup, context, completedBaseline } from './client-fixture.mjs'

const scope = (value, binding) => ({
  ...value.principal,
  selectedLocationId: value.selectedLocationId,
  datasetIncarnation: value.datasetIncarnation,
  authorizationEpoch: value.authorizationEpoch,
  policyRevision: value.policyRevision,
  capabilities: value.capabilities,
  sessionBindingId: binding,
})
async function fixture(t) {
  const { db, kernel } = await setup(t)
  const value = context()
  const ticket = await completedBaseline(db, kernel, value)
  await kernel.rememberSession(ticket, 'binding-A')
  const command = {
    kind: 'enroll',
    checkpointId: crypto.randomUUID(),
    generation: crypto.randomUUID(),
    scope: scope(value, 'binding-A'),
  }
  return { db, kernel, ticket, command }
}
test('checkpoint enrollment derives exact admitted binding and denies forged scope', async (t) => {
  const { db, kernel, ticket, command } = await fixture(t)
  for (const patch of [
    { sessionBindingId: 'binding-B' },
    { userId: 'B' },
    { capabilities: ['orders.write', 'customers.read'] },
  ]) {
    await assert.rejects(
      kernel.checkpointCapture(ticket, { ...command, scope: { ...command.scope, ...patch } }),
    )
  }
  assert.equal(await db.captureCheckpoints.count(), 0)
  const result = await kernel.checkpointCapture(ticket, command)
  assert.equal(result.kind, 'ack')
  assert.match(result.checkpoint.bindingKey, /^[0-9a-f]{64}$/)
  assert.equal(await db.operationJournal.count(), 0)
})
test('checkpoint CAS and current owner are fenced in the same transaction', async (t) => {
  const { db, kernel, ticket, command } = await fixture(t)
  const enrolled = await kernel.checkpointCapture(ticket, command)
  const save = {
    ...command,
    kind: 'save',
    channel: 'customer',
    expectedRevision: 0,
    content: { channel: 'customer', draft: { displayName: 'Private', email: '', phone: '' } },
  }
  await db.deviceControl.update('device', { generation: ticket.deviceGeneration + 1 })
  await assert.rejects(kernel.checkpointCapture(ticket, save), /fenced/)
  assert.equal(await db.captureDraftContents.count(), 0)
  assert.equal(
    (await db.captureCheckpoints.get(command.checkpointId)).customer.revision,
    enrolled.checkpoint.customer.revision,
  )
})
test('checkpoint content channel requires actual capture capabilities', async (t) => {
  const { db, kernel, ticket, command } = await fixture(t)
  await kernel.checkpointCapture(ticket, command)
  await assert.rejects(
    kernel.checkpointCapture(ticket, {
      ...command,
      kind: 'save',
      channel: 'order',
      expectedRevision: 0,
      content: {
        channel: 'order',
        draft: {
          customerId: '',
          priority: 'normal',
          reportedProblem: 'x',
          intakeCondition: '',
          accessories: '',
          withBicycle: false,
          brand: '',
          model: '',
        },
        retainedSelection: { customerId: '', priority: 'normal' },
      },
    }),
  )
  assert.equal(await db.captureDraftContents.count(), 0)
})

test('new command writer covers sequence atomically and old writer gap never heals an old checkpoint', async (t) => {
  const { command: localCommand } = await import('./client-fixture.mjs')
  const { db, kernel, ticket, command } = await fixture(t)
  const enrolled = await kernel.checkpointCapture(ticket, command)
  const initial = (await db.deviceControl.get('device')).captureWriter
  assert.ok(initial, 'enrollment establishes shared writer')
  assert.equal(enrolled.checkpoint.writerEpoch, initial.epoch)
  await kernel.commitLocalCommand(ticket, localCommand('new-1', 'entity-1'))
  let control = await db.deviceControl.get('device')
  assert.equal(control.captureWriter.epoch, initial.epoch)
  assert.equal(control.captureWriter.coveredSequence, control.localSequence)
  // Exact old-v7 behavior: append increments sequence without covering writer metadata.
  await db.deviceControl.update('device', { localSequence: control.localSequence + 1 })
  assert.equal(
    (
      await kernel.checkpointCapture(ticket, {
        kind: 'load',
        checkpointId: command.checkpointId,
        scope: command.scope,
      })
    ).kind,
    'refused',
  )
  await kernel.commitLocalCommand(ticket, localCommand('new-1', 'entity-1'))
  control = await db.deviceControl.get('device')
  assert.notEqual(
    control.captureWriter.coveredSequence,
    control.localSequence,
    'exact-ID no-op cannot repair gap',
  )
  await kernel.commitLocalCommand(ticket, localCommand('new-2', 'entity-2'))
  control = await db.deviceControl.get('device')
  assert.notEqual(control.captureWriter.epoch, initial.epoch)
  assert.equal(control.captureWriter.coveredSequence, control.localSequence)
  assert.equal(
    (
      await kernel.checkpointCapture(ticket, {
        kind: 'load',
        checkpointId: command.checkpointId,
        scope: command.scope,
      })
    ).kind,
    'refused',
    'new writer must not wash away old checkpoint invalidity',
  )
})

test('grouped new commands keep one healthy writer epoch; aborted group rolls back writer and journal', async (t) => {
  const { command: localCommand } = await import('./client-fixture.mjs')
  const { db, kernel, ticket } = await fixture(t)
  await kernel.commitLocalCommands(ticket, [
    localCommand('group-1', 'entity-1'),
    localCommand('group-2', 'entity-2'),
  ])
  const before = await db.deviceControl.get('device'),
    journal = await db.operationJournal.toArray()
  assert.equal(before.captureWriter?.coveredSequence, 2)
  assert.match(before.captureWriter.epoch, /^[0-9a-f-]{36}$/)
  await assert.rejects(
    kernel.commitLocalCommands(ticket, [
      localCommand('group-3', 'entity-3'),
      localCommand('group-1', 'collision'),
    ]),
  )
  assert.deepEqual(await db.deviceControl.get('device'), before)
  assert.deepEqual(await db.operationJournal.toArray(), journal)
})

test('healthy exact-ID no-op and authorized read preserve the writer epoch and covered sequence', async (t) => {
  const { command: localCommand } = await import('./client-fixture.mjs')
  const { db, kernel, ticket, command } = await fixture(t)
  await kernel.checkpointCapture(ticket, command)
  const input = localCommand('stable-noop', 'stable-entity')
  await kernel.commitLocalCommand(ticket, input)
  const before = (await db.deviceControl.get('device')).captureWriter
  await kernel.commitLocalCommand(ticket, input)
  await kernel.inspectSession(ticket)
  assert.deepEqual((await db.deviceControl.get('device')).captureWriter, before)
  assert.equal(
    (
      await kernel.checkpointCapture(ticket, {
        kind: 'load',
        checkpointId: command.checkpointId,
        scope: command.scope,
      })
    ).kind,
    'loaded',
  )
})

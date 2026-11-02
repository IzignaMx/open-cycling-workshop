import assert from 'node:assert/strict'
import { readFileSync, existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import test from 'node:test'
import ts from 'typescript'
const source = fileURLToPath(new URL('../../src/runtime/capture-recovery.ts', import.meta.url))
let maintenance
function load() {
  assert.ok(existsSync(source), 'recovery adapter exists')
  const module = { exports: {} }
  new Function(
    'require',
    'module',
    'exports',
    ts.transpileModule(readFileSync(source, 'utf8'), {
      compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS },
    }).outputText,
  )(() => maintenance, module, module.exports)
  return module.exports.CaptureRecovery
}
const projection = { channel: 'customer', draft: { displayName: 'Private', email: '', phone: '' } }
const scope = {
  apiRealm: 'realm',
  organizationId: 'org',
  userId: 'user',
  selectedLocationId: 'location',
  datasetIncarnation: 'dataset',
  authorizationEpoch: 'epoch',
  policyRevision: 'policy',
  capabilities: ['customers.write'],
  sessionBindingId: 'binding',
}
const empty = () => ({
  revision: 0,
  state: 'EMPTY',
  attemptId: null,
  contentStartedAt: null,
  contentExpiresAt: null,
})
function fixture() {
  const calls = [],
    values = new Map()
  let checkpoint,
    current = { ticket: {}, scope, source: {}, isCurrent: () => true },
    fail = null,
    notify = () => {}
  maintenance = {
    sweepExpiredCaptureContents: async () => ({ kind: 'complete' }),
    purgeCaptureContents: async () => ({ kind: 'complete' }),
  }
  const kernel = {
    async checkpointCapture(ticket, command) {
      calls.push(structuredClone(command))
      if (fail) return { kind: 'refused', reason: fail }
      if (command.kind === 'enroll')
        checkpoint = {
          format: 1,
          checkpointId: command.checkpointId,
          generation: command.generation,
          bindingKey: 'a'.repeat(64),
          scopeKey: 'b'.repeat(64),
          closed: false,
          observedAt: 1,
          customer: empty(),
          order: empty(),
        }
      else if (command.kind === 'load')
        return { kind: 'loaded', checkpoint: structuredClone(checkpoint), contents: {} }
      else {
        assert.equal(
          command.expectedRevision,
          checkpoint[command.channel].revision,
          'uses acknowledged revision',
        )
        const row = checkpoint[command.channel]
        row.revision++
        row.state = command.kind === 'protect' ? 'PROTECTED' : 'UNSENT'
        row.attemptId = command.kind === 'protect' ? command.attemptId : null
      }
      return { kind: 'ack', checkpoint: structuredClone(checkpoint) }
    },
  }
  const storage = {
    getItem: (k) => values.get(k) ?? null,
    setItem: (k, v) => values.set(k, v),
    removeItem: (k) => values.delete(k),
  }
  const adapter = new (load())({
    kernel,
    db: {},
    storage,
    now: () => 1,
    current: () => current,
    onChange: () => notify(),
  })
  return {
    adapter,
    calls,
    storage,
    values,
    setCurrent: (v) => (current = v),
    getCurrent: () => current,
    setNotify: (callback) => {
      notify = callback
    },
    fail: (v) => (fail = v),
    kernel,
  }
}
test('retained session without hint never enrolls', async () => {
  const f = fixture()
  assert.deepEqual(await f.adapter.ready(false), {})
  assert.equal(f.calls.length, 0)
  assert.equal(f.adapter.canSubmit('customer'), false)
})
test('hint is written before enrollment; storage failure never enrolls', async () => {
  const f = fixture()
  f.storage.setItem = () => {
    throw Error('quota')
  }
  await f.adapter.ready(true)
  assert.equal(f.calls.length, 0)
  assert.equal(f.adapter.canSubmit('customer'), false)
})
test('immediate edit then submit drains save and protects acknowledged revision', async () => {
  const f = fixture()
  await f.adapter.ready(true)
  f.adapter.edit('customer', projection)
  const attempt = await f.adapter.protect('customer')
  assert.ok(attempt)
  assert.deepEqual(
    f.calls.map((x) => x.kind),
    ['enroll', 'save', 'protect'],
  )
  assert.equal(f.adapter.canSubmit('customer'), false)
})
test('synchronous duplicate protection never dispatches a second attempt', async () => {
  const f = fixture()
  await f.adapter.ready(true)
  const a = f.adapter.protect('customer'),
    b = f.adapter.protect('customer')
  assert.equal(await b, null)
  assert.ok(await a)
  assert.equal(f.calls.filter((x) => x.kind === 'protect').length, 1)
})
test('external save conflict blocks protection without rebasing', async () => {
  const f = fixture()
  await f.adapter.ready(true)
  f.fail('conflict')
  f.adapter.edit('customer', projection)
  assert.equal(await f.adapter.protect('customer'), null)
  assert.equal(f.calls.filter((x) => x.kind === 'protect').length, 0)
})
test('protected edits remain volatile and trusted settlement alone releases gate', async () => {
  const f = fixture()
  await f.adapter.ready(true)
  const a = await f.adapter.protect('customer')
  f.adapter.edit('customer', projection)
  assert.equal(await f.adapter.settle(a, 'saved', projection), true)
  assert.deepEqual(
    f.calls.map((x) => x.kind),
    ['enroll', 'protect', 'settle'],
  )
  assert.equal(f.adapter.canSubmit('customer'), true)
})
test('known settlement retained while masked then finalized on same-scope ready', async () => {
  const f = fixture()
  await f.adapter.ready(true)
  const a = await f.adapter.protect('customer'),
    current = f.getCurrent()
  f.adapter.suspend()
  f.setCurrent(null)
  assert.equal(await f.adapter.settle(a, 'saved', null), false)
  f.setCurrent({ ...current, source: {} })
  await f.adapter.ready(false)
  assert.equal(f.calls.filter((x) => x.kind === 'settle').length, 1)
  assert.equal(f.adapter.canSubmit('customer'), true)
})
test('failed known saved settlement has truthful fixed copy and cannot retry', async () => {
  const f = fixture()
  await f.adapter.ready(true)
  const a = await f.adapter.protect('customer')
  f.fail('unavailable')
  assert.equal(await f.adapter.settle(a, 'saved', null), false)
  assert.match(f.adapter.snapshot().customer.message, /se guardó localmente/)
  assert.equal(f.adapter.canSubmit('customer'), false)
})
test('dispose never purges; close invalidates stale attempt and retains cleanup locator on failure', async () => {
  const f = fixture()
  await f.adapter.ready(true)
  const a = await f.adapter.protect('customer')
  maintenance.purgeCaptureContents = async () => ({ kind: 'unavailable' })
  f.adapter.close()
  assert.equal(await f.adapter.settle(a, 'saved', projection), false)
  assert.ok(f.values.has('ocwp.capture-cleanup.v1'))
  assert.equal(f.adapter.canSubmit('customer'), false)
})

test('late load never restores over a newer in-memory edit', async () => {
  const f = fixture()
  await f.adapter.ready(true)
  f.adapter.dispose()
  f.adapter.startVisit()
  const original = f.kernel.checkpointCapture
  let release
  f.kernel.checkpointCapture = async (ticket, command) => {
    const result = await original(ticket, command)
    if (command.kind === 'load') {
      result.checkpoint.customer.state = 'UNSENT'
      result.contents.customer = {
        ...projection,
        format: 1,
        checkpointId: command.checkpointId,
        generation: result.checkpoint.generation,
        revision: 0,
        firstPersistedAt: 1,
        expiresAt: 100,
      }
      await new Promise((r) => (release = r))
    }
    return result
  }
  const loading = f.adapter.ready(false)
  await new Promise((r) => setImmediate(r))
  f.adapter.edit('customer', {
    ...projection,
    draft: { ...projection.draft, displayName: 'Newer' },
  })
  release()
  assert.deepEqual(await loading, {})
})
test('same-visit reverify never rebases a failed external conflict into fresh admission', async () => {
  const f = fixture()
  await f.adapter.ready(true)
  f.fail('conflict')
  f.adapter.edit('customer', projection)
  await f.adapter.protect('customer')
  f.fail(null)
  await f.adapter.ready(false)
  assert.equal(f.adapter.canSubmit('customer'), false)
})

test('reload of protected checkpoint never returns content or reopens admission', async () => {
  const f = fixture()
  await f.adapter.ready(true)
  await f.adapter.protect('customer')
  f.adapter.dispose()
  f.adapter.startVisit()
  assert.deepEqual(await f.adapter.ready(false), {})
  assert.equal(f.adapter.canSubmit('customer'), false)
  assert.match(f.adapter.snapshot().customer.message, /pendiente de confirmar/)
  assert.equal(f.adapter.canSubmit('order'), true)
})
test('cleanup failure prevents enrollment and restore', async () => {
  const f = fixture()
  maintenance.sweepExpiredCaptureContents = async () => ({ kind: 'unavailable' })
  await f.adapter.cleanup()
  await f.adapter.ready(true)
  assert.equal(f.calls.length, 0)
  assert.match(f.adapter.snapshot().customer.message, /podrían permanecer/)
})
test('dispose preserves durable checkpoint and does not request cleanup', async () => {
  const f = fixture()
  await f.adapter.ready(true)
  let purges = 0
  maintenance.purgeCaptureContents = async () => {
    purges++
    return { kind: 'complete' }
  }
  f.adapter.dispose()
  await Promise.resolve()
  assert.equal(purges, 0)
  assert.equal(f.values.has('ocwp.capture-cleanup.v1'), false)
})
test('old pending save cannot alter replacement visit after close and new binding', async () => {
  const f = fixture()
  await f.adapter.ready(true)
  const original = f.kernel.checkpointCapture
  let release
  f.kernel.checkpointCapture = async (t, c) => {
    const result = await original(t, c)
    if (c.kind === 'save') await new Promise((r) => (release = r))
    return result
  }
  f.adapter.edit('customer', projection)
  await new Promise((r) => setImmediate(r))
  f.adapter.close()
  f.adapter.startVisit()
  const c = f.getCurrent()
  f.setCurrent({ ...c, source: {}, scope: { ...scope, sessionBindingId: 'new-binding' } })
  await f.adapter.ready(true)
  release()
  await new Promise((r) => setImmediate(r))
  assert.equal(f.adapter.snapshot().customer.message, null)
  assert.equal(f.adapter.canSubmit('customer'), true)
})
test('edit during settlement is not reported acknowledged and saves after settlement', async () => {
  const f = fixture()
  await f.adapter.ready(true)
  const attempt = await f.adapter.protect('customer'),
    original = f.kernel.checkpointCapture
  let release
  f.kernel.checkpointCapture = async (t, c) => {
    const result = await original(t, c)
    if (c.kind === 'settle') await new Promise((r) => (release = r))
    return result
  }
  const settling = f.adapter.settle(attempt, 'saved', null)
  await new Promise((r) => setImmediate(r))
  f.adapter.edit('customer', projection)
  release()
  assert.equal(await settling, true)
  await new Promise((r) => setImmediate(r))
  assert.deepEqual(
    f.calls.map((c) => c.kind),
    ['enroll', 'protect', 'settle', 'save'],
  )
  assert.equal(f.calls.at(-1).content.draft.displayName, 'Private')
})
test('coalesced own edits persist latest projection before protect', async () => {
  const f = fixture()
  await f.adapter.ready(true)
  const original = f.kernel.checkpointCapture
  let release,
    first = true
  f.kernel.checkpointCapture = async (t, c) => {
    const result = await original(t, c)
    if (c.kind === 'save' && first) {
      first = false
      await new Promise((r) => (release = r))
    }
    return result
  }
  f.adapter.edit('customer', projection)
  f.adapter.edit('customer', {
    ...projection,
    draft: { ...projection.draft, displayName: 'Latest' },
  })
  const protecting = f.adapter.protect('customer')
  await new Promise((r) => setImmediate(r))
  release()
  assert.ok(await protecting)
  assert.deepEqual(
    f.calls.map((c) => c.kind),
    ['enroll', 'save', 'save', 'protect'],
  )
  assert.equal(f.calls[2].content.draft.displayName, 'Latest')
})

test('order restore includes hidden bicycle inputs and retained selection without writes', async () => {
  const f = fixture()
  await f.adapter.ready(true)
  f.adapter.dispose()
  f.adapter.startVisit()
  const original = f.kernel.checkpointCapture
  const order = {
    channel: 'order',
    draft: {
      customerId: 'customer',
      priority: 'high',
      reportedProblem: 'brake',
      intakeCondition: 'wet',
      accessories: 'light',
      withBicycle: false,
      brand: 'hidden brand',
      model: 'hidden model',
    },
    retainedSelection: { customerId: 'prior', priority: 'normal' },
  }
  f.kernel.checkpointCapture = async (t, c) => {
    const result = await original(t, c)
    if (c.kind === 'load') {
      result.checkpoint.order.state = 'UNSENT'
      result.contents.order = {
        ...order,
        format: 1,
        checkpointId: c.checkpointId,
        generation: result.checkpoint.generation,
        revision: 0,
        firstPersistedAt: 1,
        expiresAt: 100,
      }
    }
    return result
  }
  assert.deepEqual(await f.adapter.ready(false), { order })
  assert.deepEqual(
    f.calls.map((c) => c.kind),
    ['enroll', 'load'],
  )
})
test('expected missing checkpoint never enrolls even if caller permits enrollment', async () => {
  const f = fixture()
  await f.adapter.ready(true)
  f.adapter.dispose()
  f.adapter.startVisit()
  f.fail('missing')
  await f.adapter.ready(true)
  assert.deepEqual(
    f.calls.map((c) => c.kind),
    ['enroll', 'load'],
  )
  assert.equal(f.adapter.canSubmit('customer'), false)
})
test('malformed cleanup locator cannot prevent expiry sweep, but blocks recovery', async () => {
  const f = fixture()
  f.values.set('ocwp.capture-cleanup.v1', '{broken')
  let sweeps = 0
  maintenance.sweepExpiredCaptureContents = async () => {
    sweeps++
    return { kind: 'complete' }
  }
  await f.adapter.cleanup()
  assert.equal(sweeps, 1)
  await f.adapter.ready(true)
  assert.equal(f.calls.length, 0)
})

test('dirty protection is distinct from missing enrollment and confirmed closure', async () => {
  const f = fixture()
  assert.equal(f.adapter.hasUnsent(), false)
  await f.adapter.ready(true)
  assert.equal(f.adapter.hasUnsent(), false)
  await f.adapter.protect('customer')
  assert.equal(f.adapter.hasUnsent(), true)
  f.adapter.close()
  assert.equal(f.adapter.hasUnsent(), false)
})

test('failed logout purge exposes global notice across closed view and new visit', async () => {
  const f = fixture()
  await f.adapter.ready(true)
  maintenance.purgeCaptureContents = async () => ({ kind: 'unavailable' })
  f.adapter.close()
  await new Promise((resolve) => setImmediate(resolve))
  assert.match(f.adapter.getNotice(), /No se pudo confirmar la eliminación/)
  f.adapter.startVisit()
  assert.match(f.adapter.getNotice(), /podrían permanecer/)
  maintenance.purgeCaptureContents = async () => ({ kind: 'complete' })
  await f.adapter.cleanup()
  assert.equal(f.adapter.getNotice(), null)
})
test('successful expiry sweep cannot hide missing-locator failed logout purge', async () => {
  const f = fixture()
  await f.adapter.ready(true)
  maintenance.purgeCaptureContents = async () => ({ kind: 'unavailable' })
  f.adapter.close()
  await new Promise((resolve) => setImmediate(resolve))
  f.values.delete('ocwp.capture-cleanup.v1')
  await f.adapter.cleanup()
  assert.match(f.adapter.getNotice(), /podrían permanecer/)
})
test('startup expiry failure is global and clears only after positive cleanup', async () => {
  const f = fixture()
  maintenance.sweepExpiredCaptureContents = async () => ({ kind: 'unavailable' })
  await f.adapter.cleanup()
  assert.match(f.adapter.getNotice(), /podrían permanecer/)
  f.adapter.startVisit()
  assert.match(f.adapter.getNotice(), /podrían permanecer/)
  maintenance.sweepExpiredCaptureContents = async () => ({ kind: 'complete' })
  await f.adapter.cleanup()
  assert.equal(f.adapter.getNotice(), null)
})
test('malformed startup locator remains globally visible despite successful expiry sweep', async () => {
  const f = fixture()
  f.values.set('ocwp.capture-cleanup.v1', '{broken')
  await f.adapter.cleanup()
  assert.match(f.adapter.getNotice(), /podrían permanecer/)
  f.adapter.startVisit()
  assert.match(f.adapter.getNotice(), /podrían permanecer/)
})

test('microtask edit after final save acknowledgement drains without another event', async () => {
  const f = fixture()
  await f.adapter.ready(true)
  let queued = false
  f.setNotify(() => {
    if (!queued && f.adapter.snapshot().customer.message?.startsWith('Borrador guardado')) {
      queued = true
      queueMicrotask(() =>
        f.adapter.edit('customer', {
          ...projection,
          draft: { ...projection.draft, displayName: 'Microtask latest' },
        }),
      )
    }
  })
  f.adapter.edit('customer', projection)
  await new Promise((r) => setImmediate(r))
  assert.equal(f.calls.filter((c) => c.kind === 'save').length, 2)
  assert.equal(f.calls.at(-1).content.draft.displayName, 'Microtask latest')
  assert.equal(f.adapter.snapshot().customer.busy, false)
})

test('protect waits for restarted microtask-tail save before reading acknowledged CAS', async () => {
  const f = fixture()
  await f.adapter.ready(true)
  let queued = false,
    protection
  f.setNotify(() => {
    if (!queued && f.adapter.snapshot().customer.message?.startsWith('Borrador guardado')) {
      queued = true
      queueMicrotask(() => {
        f.adapter.edit('customer', {
          ...projection,
          draft: { ...projection.draft, displayName: 'Tail before protect' },
        })
        protection = f.adapter.protect('customer')
      })
    }
  })
  f.adapter.edit('customer', projection)
  await new Promise((resolve) => setImmediate(resolve))
  assert.ok(await protection)
  assert.deepEqual(
    f.calls.map((command) => command.kind),
    ['enroll', 'save', 'save', 'protect'],
  )
  assert.equal(f.calls.at(-1).expectedRevision, 2)
})

test('retirement synchronously removes hint and restores same checkpoint only after positive deletion', async () => {
  const f = fixture()
  await f.adapter.ready(true)
  const old = JSON.parse(f.values.get('ocwp.capture-checkpoint.v1'))
  let release
  maintenance.retireCaptureContents = async (db, id, generation, nextGeneration) => {
    await new Promise((r) => (release = r))
    return {
      kind: 'retired',
      checkpoint: {
        format: 1,
        checkpointId: id,
        generation: nextGeneration,
        bindingKey: 'a'.repeat(64),
        scopeKey: 'b'.repeat(64),
        closed: false,
        observedAt: 1,
        customer: empty(),
        order: empty(),
      },
    }
  }
  const retiring = f.adapter.retireVisit()
  assert.equal(f.values.has('ocwp.capture-checkpoint.v1'), false)
  assert.equal(f.adapter.canSubmit('customer'), false)
  release()
  await retiring
  assert.deepEqual(JSON.parse(f.values.get('ocwp.capture-checkpoint.v1')), old)
  assert.equal(f.adapter.canSubmit('customer'), false)
})
test('failed retirement leaves no recoverable hint and exposes cleanup warning', async () => {
  const f = fixture()
  await f.adapter.ready(true)
  maintenance.retireCaptureContents = async () => ({ kind: 'unavailable' })
  await f.adapter.retireVisit()
  assert.equal(f.values.has('ocwp.capture-checkpoint.v1'), false)
  assert.equal(f.adapter.canSubmit('customer'), false)
  assert.match(f.adapter.getNotice(), /podrían permanecer/)
})
test('late retirement cannot recreate old hint after close and replacement visit', async () => {
  const f = fixture()
  await f.adapter.ready(true)
  let release
  maintenance.retireCaptureContents = async (db, id, generation, nextGeneration) => {
    await new Promise((r) => (release = r))
    return {
      kind: 'retired',
      checkpoint: {
        format: 1,
        checkpointId: id,
        generation: nextGeneration,
        bindingKey: 'a'.repeat(64),
        scopeKey: 'b'.repeat(64),
        closed: false,
        observedAt: 1,
        customer: empty(),
        order: empty(),
      },
    }
  }
  const retiring = f.adapter.retireVisit()
  f.adapter.close()
  f.adapter.startVisit()
  const current = f.getCurrent()
  f.setCurrent({ ...current, source: {}, scope: { ...scope, sessionBindingId: 'replacement' } })
  await f.adapter.ready(true)
  const replacement = f.values.get('ocwp.capture-checkpoint.v1')
  release()
  await retiring
  assert.equal(f.values.get('ocwp.capture-checkpoint.v1'), replacement)
})
test('failed synchronous hint removal never enables old restored content', async () => {
  const f = fixture()
  await f.adapter.ready(true)
  f.storage.removeItem = () => {
    throw Error('storage unavailable')
  }
  maintenance.retireCaptureContents = async () => ({ kind: 'unavailable' })
  await f.adapter.retireVisit()
  await f.adapter.ready(false)
  assert.equal(f.adapter.canSubmit('customer'), false)
  assert.match(f.adapter.getNotice(), /podrían permanecer/)
})

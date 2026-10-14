import test from 'node:test'
import assert from 'node:assert/strict'
import { ReachabilityProbe } from '../../.tmp-runtime/src/runtime/reachability-probe.js'
import { RuntimeHttpError } from '../../.tmp-runtime/src/runtime/transport.js'
const flush = async () => {
  for (let i = 0; i < 12; i++) await Promise.resolve()
}
function harness() {
  let now = 0,
    id = 0
  const timers = new Map()
  const clock = {
    now: () => now,
    set: (action, delay) => {
      timers.set(++id, { action, due: now + delay })
      return id
    },
    clear: (handle) => timers.delete(handle),
  }
  return {
    probe: new ReachabilityProbe(clock),
    timers,
    jump: (value) => {
      now = value
    },
    async advance(ms) {
      const end = now + ms
      for (;;) {
        const next = [...timers].sort((a, b) => a[1].due - b[1].due)[0]
        if (!next || next[1].due > end) break
        now = next[1].due
        timers.delete(next[0])
        next[1].action()
        await flush()
      }
      now = end
      await flush()
    },
  }
}
function task(overrides = {}) {
  return {
    expiresAt: 3600000,
    current: () => true,
    inspect: async () => {},
    request: async () => {
      throw new RuntimeHttpError('network_error')
    },
    complete: async () => {
      assert.fail('unexpected authority completion')
    },
    invalid: () => {
      assert.fail('unexpected lease invalidation')
    },
    ...overrides,
  }
}
test('probe backoff is 2/4/8/16/30 seconds, capped for the unchanged original lease', async () => {
  const h = harness(),
    calls = []
  let invalid = 0
  h.probe.start(
    task({
      expiresAt: 100000,
      request: async () => {
        calls.push(1)
        throw new RuntimeHttpError('network_error')
      },
      invalid: () => {
        invalid++
      },
    }),
  )
  await h.advance(1999)
  assert.equal(calls.length, 0)
  let expected = 0
  for (const ms of [1, 4000, 8000, 16000, 30000, 30000]) {
    await h.advance(ms)
    assert.equal(calls.length, ++expected)
  }
  assert.equal(calls.length, 6)
  await h.advance(10000)
  assert.equal(invalid, 1)
  assert.equal(calls.length, 6)
  assert.equal(h.timers.size, 0)
})
test('deadline fences late success and retains physical single flight until abort-ignoring request settles', async () => {
  const h = harness()
  let release,
    count = 0,
    signal
  h.probe.start(
    task({
      request: async (captured) => {
        count++
        signal = captured
        return new Promise((resolve) => {
          release = resolve
        })
      },
    }),
  )
  await h.advance(2000)
  await h.advance(10000)
  assert.equal(signal.aborted, true)
  await h.advance(60000)
  assert.equal(count, 1)
  assert.equal(h.timers.size, 0)
  release({ user: 'late' })
  await flush()
  await h.advance(3999)
  assert.equal(count, 1)
  await h.advance(1)
  assert.equal(count, 2)
  h.probe.cancel()
  release({ user: 'later' })
  await flush()
  assert.equal(h.timers.size, 0)
})
test('cancel and replacement do not overlap an abort-ignoring prior transport', async () => {
  const h = harness()
  let release,
    oldSignal,
    calls = 0
  h.probe.start(
    task({
      request: async (signal) => {
        oldSignal = signal
        return new Promise((resolve) => {
          release = resolve
        })
      },
    }),
  )
  await h.advance(2000)
  h.probe.start(
    task({
      request: async () => {
        calls++
        throw new RuntimeHttpError('network_error')
      },
    }),
  )
  assert.equal(oldSignal.aborted, true)
  await h.advance(60000)
  assert.equal(calls, 0)
  release('stale')
  await flush()
  await h.advance(2000)
  assert.equal(calls, 1)
  h.probe.cancel()
})
for (const code of ['invalid_session', 'capability_denied', 'invalid_response', 'stale_request'])
  test(`terminal ${code} reaches owner-fenced verification exactly once without retrying me`, async () => {
    const h = harness(),
      refusal = new RuntimeHttpError(code)
    let calls = 0,
      completions = 0
    h.probe.start(
      task({
        request: async () => {
          calls++
          throw refusal
        },
        complete: async (result, current) => {
          assert.equal(current(), true)
          assert.equal(result.error, refusal)
          completions++
        },
      }),
    )
    await h.advance(60000)
    assert.equal(calls, 1)
    assert.equal(completions, 1)
    assert.equal(h.timers.size, 0)
  })
test('changed capture or expired/rolled-back clock cannot consume a late probe success', async () => {
  for (const mode of ['capture', 'expiry', 'rollback']) {
    const h = harness()
    let current = true,
      release,
      invalid = 0
    h.probe.start(
      task({
        current: () => current,
        expiresAt: 5000,
        request: async () =>
          new Promise((resolve) => {
            release = resolve
          }),
        invalid: () => {
          invalid++
        },
      }),
    )
    await h.advance(2000)
    if (mode === 'capture') current = false
    else h.jump(mode === 'expiry' ? 5000 : 0)
    release('late')
    await flush()
    assert.equal(invalid, mode === 'capture' ? 0 : 1)
    assert.equal(h.timers.size, 0)
  }
})
test('owner inspection failure is terminal, including failure just before authoritative handoff', async () => {
  for (const failure of ['inspect', 'complete']) {
    const h = harness()
    let invalid = 0,
      calls = 0
    h.probe.start(
      task({
        inspect: async () => {
          if (failure === 'inspect') throw new Error('owner changed')
        },
        request: async () => {
          calls++
          return 'hint'
        },
        complete: async () => {
          throw new Error('owner changed')
        },
        invalid: () => {
          invalid++
        },
      }),
    )
    await h.advance(2000)
    assert.equal(calls, failure === 'inspect' ? 0 : 1)
    assert.equal(invalid, 1)
    assert.equal(h.timers.size, 0)
  }
})

test('deadline is clamped to the original lease and detects clock failure without transport settlement', async () => {
  for (const clock of ['expired', 'rollback', 'invalid']) {
    const h = harness()
    let invalid = 0,
      signal
    h.probe.start(
      task({
        expiresAt: 5000,
        request: async (captured) => {
          signal = captured
          return new Promise(() => {})
        },
        invalid: () => {
          invalid++
        },
      }),
    )
    await h.advance(2000)
    const deadline = [...h.timers.values()][0]
    assert.equal(deadline.due, 5000)
    h.jump(clock === 'expired' ? 5000 : clock === 'rollback' ? 0 : NaN)
    deadline.action()
    assert.equal(invalid, 1)
    assert.equal(signal.aborted, true)
  }
})

test('valid long-offline admission can recover beyond eight unreachable probes without a new lease', async () => {
  const h = harness()
  let calls = 0,
    completed = 0
  const admission = task({
    request: async () => {
      if (++calls <= 12) throw new RuntimeHttpError('network_error')
      return 'reachable'
    },
    complete: async (result) => {
      assert.equal(result.value, 'reachable')
      completed++
    },
  })
  h.probe.start(admission)
  await h.advance(300000)
  assert.equal(calls, 13)
  assert.equal(completed, 1)
  assert.equal(admission.expiresAt, 3600000)
  assert.equal(h.timers.size, 0)
})

test('settled probe releases its flight before authoritative handoff and cannot clear a newer pending probe', async () => {
  const h = harness()
  let finishHandoff,
    finishProbe,
    count = 0,
    signal
  h.probe.start(
    task({
      request: async () => 'hint',
      complete: async () =>
        new Promise((resolve) => {
          finishHandoff = resolve
        }),
    }),
  )
  await h.advance(2000)
  h.probe.start(
    task({
      request: async (captured) => {
        count++
        signal = captured
        return new Promise((resolve) => {
          finishProbe = resolve
        })
      },
    }),
  )
  await h.advance(2000)
  assert.equal(count, 1)
  finishHandoff()
  await flush()
  await h.advance(60000)
  assert.equal(signal.aborted, true)
  assert.equal(count, 1)
  h.probe.cancel()
  finishProbe('late')
  await flush()
  assert.equal(h.timers.size, 0)
})

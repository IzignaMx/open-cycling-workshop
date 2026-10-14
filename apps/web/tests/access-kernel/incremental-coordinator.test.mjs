import test from 'node:test'
import assert from 'node:assert/strict'
import { createIncrementalCoordinator } from '../../.tmp-kernel/src/access-kernel/incremental-coordinator.js'
import { IncrementalTransportError } from '../../.tmp-kernel/src/access-kernel/incremental-transport.js'
function fixture(overrides = {}) {
  const requests = [],
    commits = [],
    holds = [],
    disabled = []
  const next = { kind: 'delta', body: '{"continuation":"previous","protocol":1}' }
  const context = { snapshotProtocol: 'baseline-v1' },
    ticket = {
      partitionId: 'partition',
      deviceGeneration: 1,
      tabAttemptId: 'tab',
      principalKey: 'principal',
      authorizationEpoch: 'epoch',
    }
  const input = {
    context,
    ticket,
    identity: {
      apiRealm: 'https://example.test/api/v1',
      organizationId: 'org',
      userId: 'A',
      selectedLocationId: 'loc',
      deviceGeneration: 1,
      tabAttemptId: 'tab',
      sessionHandle: 'session-A',
    },
    bearerToken: 'token-A',
    isCurrent: () => true,
  }
  const pending = { context, incremental: { next, phase: 'complete', retryCount: 0, hold: null } }
  const kernel = {
    pendingIncremental: async () => pending,
    commitIncrementalPage: async (...args) => {
      commits.push(args)
      return 'committed'
    },
    holdIncremental: async (...args) => {
      holds.push(args)
      return true
    },
    retryIncremental: async () => {},
    disableIncrementalSession: (...args) => disabled.push(args),
    ...overrides.kernel,
  }
  const transport = {
    request: async (request) => {
      requests.push(request)
      return { phase: 'complete' }
    },
    invalidate() {},
    ...overrides.transport,
  }
  const coordinator = createIncrementalCoordinator({
    kernel,
    transport,
    now: () => 1000,
    random: () => 0,
    online: () => true,
    ...overrides.options,
  })
  return { input, pending, requests, commits, holds, disabled, coordinator, next }
}
test('coordinator captures immutable token before awaited durable request lookup', async () => {
  let release
  const pause = new Promise((r) => {
    release = r
  })
  let f
  f = fixture({
    kernel: {
      pendingIncremental: async () => {
        await pause
        return f.pending
      },
    },
  })
  const pending = f.coordinator.step(f.input)
  f.input.bearerToken = 'token-B'
  f.input.identity.userId = 'B'
  release()
  assert.equal((await pending).state, 'READY')
  assert.equal(f.requests[0].bearerToken, 'token-A')
  assert.equal(f.requests[0].identity.userId, 'A')
  assert.equal(f.requests[0].body, f.next.body)
  assert.equal(typeof f.commits[0][4], 'function')
})
for (const boundary of ['pending', 'transport', 'commit', 'hold'])
  test(`session change during ${boundary} cannot publish, dispatch or hold current session`, async () => {
    let release,
      entered,
      current = true
    const pause = new Promise((r) => {
        release = r
      }),
      ready = new Promise((r) => {
        entered = r
      })
    let f
    const blocker = async (result) => {
      entered()
      await pause
      return result
    }
    f = fixture(
      boundary === 'pending'
        ? { kernel: { pendingIncremental: () => blocker(f.pending) } }
        : boundary === 'transport'
          ? { transport: { request: () => blocker({ phase: 'complete' }) } }
          : boundary === 'commit'
            ? { kernel: { commitIncrementalPage: () => blocker('committed') } }
            : {
                kernel: { holdIncremental: () => blocker(true) },
                transport: {
                  request: async () => {
                    throw new IncrementalTransportError('network_error')
                  },
                },
              },
    )
    f.input.isCurrent = () => current
    const pending = f.coordinator.step(f.input)
    await ready
    current = false
    release()
    assert.equal((await pending).reason, 'stale_request')
    assert.equal(f.disabled.length, 0)
    if (boundary === 'pending') assert.equal(f.requests.length, 0)
  })
test('one call consumes one page and distinguishes catching up from round completion', async () => {
  const f = fixture({ transport: { request: async () => ({ phase: 'catching_up' }) } })
  assert.equal((await f.coordinator.step(f.input)).state, 'PROGRESSED')
  assert.equal(f.commits.length, 1)
})
for (const code of [
  'checkpoint_expired',
  'dataset_changed',
  'context_changed',
  'invalid_session',
  'invalid_response',
])
  test(`${code} visibly holds exact predecessor without retry or acknowledgment`, async () => {
    const f = fixture({
      transport: {
        request: async () => {
          throw new IncrementalTransportError(code)
        },
      },
    })
    const outcome = await f.coordinator.step(f.input)
    assert.equal(outcome.state, 'HELD')
    assert.equal(outcome.reason, code)
    assert.deepEqual(f.holds[0][1], f.next)
    assert.equal(f.holds[0][3], null)
    assert.equal(f.commits.length, 0)
  })
test('network failure retries exact predecessor using bounded policy and exhausts budget', async () => {
  const f = fixture({
    transport: {
      request: async () => {
        throw new IncrementalTransportError('network_error')
      },
    },
  })
  assert.equal((await f.coordinator.step(f.input)).state, 'RETRY_LATER')
  assert.equal(f.holds[0][3], 5000)
  f.pending.incremental.retryCount = 7
  assert.equal((await f.coordinator.step(f.input)).reason, 'retry_exhausted')
  assert.equal(f.holds[1][3], null)
})
test('server long Retry-After honored and waiting hold emits no HTTP', async () => {
  const f = fixture({
    transport: {
      request: async () => {
        throw new IncrementalTransportError('baseline_capacity', 429, 1800000)
      },
    },
  })
  assert.equal((await f.coordinator.step(f.input)).retryAt, 1801000)
  f.pending.incremental.hold = { reason: 'network_error', retryAt: 2000 }
  assert.equal((await f.coordinator.step(f.input)).state, 'RETRY_LATER')
  assert.equal(f.holds.length, 1)
})
test('failed persisted hold disables exact volatile session and repeated step cannot send', async () => {
  const f = fixture({
    transport: {
      request: async () => {
        throw new IncrementalTransportError('network_error')
      },
    },
    kernel: {
      holdIncremental: async () => {
        throw new DOMException('Full', 'QuotaExceededError')
      },
    },
  })
  assert.equal((await f.coordinator.step(f.input)).reason, 'storage_or_fence_failure')
  assert.equal(f.disabled.length, 1)
  assert.equal((await f.coordinator.step(f.input)).reason, 'verification_required')
})
test('offline or null protocol emits zero requests and no checkpoint edits', async () => {
  const f = fixture({ options: { online: () => false } })
  assert.equal((await f.coordinator.step(f.input)).state, 'OFFLINE')
  f.input.context.snapshotProtocol = null
  assert.equal((await f.coordinator.step(f.input)).state, 'BASELINE_REQUIRED')
  assert.equal(f.requests.length, 0)
  assert.equal(f.commits.length, 0)
})

test('fractional jitter yields a finite scheduled millisecond retry', async () => {
  const f = fixture({
    transport: {
      request: async () => {
        throw new IncrementalTransportError('network_error')
      },
    },
    options: { random: () => 0.1234567 },
  })
  const result = await f.coordinator.step(f.input)
  assert.equal(result.state, 'RETRY_LATER')
  assert.ok(Number.isSafeInteger(result.retryAt))
})

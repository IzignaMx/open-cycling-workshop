import test from 'node:test'
import assert from 'node:assert/strict'
import { createBaselineCoordinator } from '../../.tmp-kernel/src/access-kernel/baseline-coordinator.js'
test('ordinary null protocol never starts/resumes/activates or emits HTTP', async () => {
  let calls = 0
  const rejectCall = () => {
    calls++
    throw new Error('Unexpected call')
  }
  const coordinator = createBaselineCoordinator({
    kernel: { beginBaseline: rejectCall },
    transport: { request: rejectCall },
    now: () => 1,
    random: () => 0,
    online: () => true,
  })
  const input = {
    context: { snapshotProtocol: null },
    ticket: {},
    identity: {},
    bearerToken: 'captured',
    isCurrent: () => true,
  }
  assert.equal((await coordinator.start(input)).state, 'BASELINE_REQUIRED')
  assert.equal((await coordinator.step(input)).state, 'BASELINE_REQUIRED')
  assert.equal(calls, 0)
})

import { BaselineTransportError } from '../../.tmp-kernel/src/access-kernel/baseline-transport.js'
function fixture(error, overrides = {}) {
  const requests = [],
    holds = [],
    commits = []
  const ticket = {
    partitionId: 'partition',
    deviceGeneration: 1,
    tabAttemptId: 'tab',
    principalKey: 'principal',
    authorizationEpoch: 'epoch',
  }
  const context = { snapshotProtocol: 'baseline-v1' }
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
      sessionHandle: 'session',
    },
    bearerToken: 'captured-A',
    isCurrent: () => true,
  }
  const next = { kind: 'scan', body: '{"protocol":1,"continuation":"original"}' }
  const kernel = {
    disableBaselineSession() {},
    pendingBaseline: async () => ({
      context,
      baseline: { next, baselineId: 'baseline', hold: null, retryCount: 0 },
    }),
    holdBaseline: async (...args) => {
      holds.push(args)
      return true
    },
    commitBaselinePage: async (...args) => {
      commits.push(args)
    },
    beginBaseline: async () => ticket,
    ...overrides.kernel,
  }
  const transport = {
    request: async (request) => {
      requests.push(request)
      if (error) throw error
      return {}
    },
    invalidate() {},
  }
  const coordinator = createBaselineCoordinator({
    transport,
    now: () => 1000,
    random: () => 0,
    online: () => true,
    ...overrides,
    kernel,
  })
  return { coordinator, input, requests, holds, commits, next }
}
for (const code of [
  'invalid_session',
  'capability_denied',
  'baseline_expired',
  'checkpoint_expired',
  'continuation_stale',
  'dataset_changed',
])
  test(`${code} holds original request without acknowledging work`, async () => {
    const f = fixture(new BaselineTransportError(code))
    const outcome = await f.coordinator.step(f.input)
    assert.equal(outcome.state, 'HELD')
    assert.equal(outcome.reason, code)
    assert.deepEqual(f.holds[0][1], f.next)
    assert.equal(f.holds[0][3], null)
    assert.equal(f.commits.length, 0)
  })
test('capacity preserves exact request and honors long server Retry-After', async () => {
  const f = fixture(new BaselineTransportError('baseline_capacity', 429, 1800000))
  const outcome = await f.coordinator.step(f.input)
  assert.equal(outcome.state, 'RETRY_LATER')
  assert.equal(outcome.retryAt, 1801000)
  assert.equal(f.requests[0].body, f.next.body)
})
test('quota failure in separate hold cannot claim durable HELD or erase evidence', async () => {
  const f = fixture(new DOMException('Full', 'QuotaExceededError'), {
    kernel: {
      holdBaseline: async () => {
        throw new DOMException('Full', 'QuotaExceededError')
      },
    },
  })
  const outcome = await f.coordinator.step(f.input)
  assert.equal(outcome.reason, 'storage_or_fence_failure')
  assert.equal(f.commits.length, 0)
})
test('offline stops before HTTP without changing pending work', async () => {
  const f = fixture(null, { online: () => false })
  assert.equal((await f.coordinator.step(f.input)).state, 'OFFLINE')
  assert.equal(f.requests.length, 0)
  assert.equal(f.holds.length, 0)
})
test('session and bearer are captured before durable start await', async () => {
  let release
  const pause = new Promise((resolve) => {
    release = resolve
  })
  const f = fixture(null, {
    kernel: {
      beginBaseline: async (ticket) => {
        await pause
        return ticket
      },
    },
  })
  const call = f.coordinator.start(f.input)
  f.input.bearerToken = 'B'
  f.input.identity.userId = 'B'
  f.input.identity.sessionHandle = 'B'
  release()
  await call
  assert.equal(f.requests[0].bearerToken, 'captured-A')
  assert.equal(f.requests[0].identity.userId, 'A')
})
test('session replacement after durable start prevents HTTP and leaves original pending request', async () => {
  let release,
    current = true
  const pause = new Promise((resolve) => {
    release = resolve
  })
  const f = fixture(null, {
    kernel: {
      beginBaseline: async (ticket) => {
        await pause
        return ticket
      },
    },
  })
  f.input.isCurrent = () => current
  const call = f.coordinator.start(f.input)
  current = false
  release()
  assert.equal((await call).reason, 'stale_request')
  assert.equal(f.requests.length, 0)
  assert.equal(f.holds.length, 0)
})

test('failed durable hold disables the matching local ticket until fresh verification', async () => {
  const f = fixture(new BaselineTransportError('invalid_response'), {
    kernel: {
      holdBaseline: async () => {
        throw new DOMException('Full', 'QuotaExceededError')
      },
    },
  })
  assert.equal((await f.coordinator.step(f.input)).reason, 'storage_or_fence_failure')
  assert.equal((await f.coordinator.step(f.input)).reason, 'verification_required')
  assert.equal(f.requests.length, 1)
})
test('stale failed hold cannot disable a newer coordinator request', async () => {
  let release, failHold
  const holding = new Promise((resolve) => {
    failHold = resolve
  })
  const pause = new Promise((resolve) => {
    release = resolve
  })
  const f = fixture(new BaselineTransportError('invalid_response'), {
    kernel: {
      holdBaseline: async () => {
        failHold()
        await pause
        throw new DOMException('Full', 'QuotaExceededError')
      },
    },
  })
  const first = f.coordinator.step(f.input)
  await holding
  f.coordinator.invalidate()
  release()
  assert.equal((await first).reason, 'stale_request')
})

test('actual Dexie-wrapped quota remains a storage hold rather than terminal integrity failure', async () => {
  const { default: Dexie } = await import('dexie')
  const quota = new Dexie.QuotaExceededError('Private quota detail')
  assert.equal(quota instanceof DOMException, false)
  const f = fixture(null, {
    kernel: {
      commitBaselinePage: async () => {
        throw quota
      },
    },
  })
  const outcome = await f.coordinator.step(f.input)
  assert.equal(outcome.reason, 'storage_full')
  assert.equal(f.holds[0][2], 'storage_full')
  assert.ok(!JSON.stringify(outcome).includes('Private quota'))
})

test('native and Dexie transaction aborts preserve a resumable storage-aborted hold', async () => {
  const { default: Dexie } = await import('dexie')
  for (const error of [
    new Dexie.AbortError('Private abort'),
    new DOMException('Private abort', 'AbortError'),
  ]) {
    const f = fixture(null, {
      kernel: {
        commitBaselinePage: async () => {
          throw error
        },
      },
    })
    const outcome = await f.coordinator.step(f.input)
    assert.equal(outcome.reason, 'storage_aborted')
    assert.equal(f.holds[0][2], 'storage_aborted')
    assert.equal(f.holds[0][3], null)
    assert.ok(!JSON.stringify(outcome).includes('Private abort'))
  }
})

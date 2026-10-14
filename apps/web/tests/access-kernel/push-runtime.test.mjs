import test from 'node:test'
import assert from 'node:assert/strict'
import { createPushCoordinator } from '../../.tmp-kernel/src/access-kernel/push-coordinator.js'
import {
  createPushTransport,
  PushTransportError,
} from '../../.tmp-kernel/src/access-kernel/push-transport.js'
const ticket = {
  deviceGeneration: 1,
  tabAttemptId: 'tab',
  partitionId: 'part',
  principalKey: JSON.stringify(['https://example.test/api/v1', 'org', 'user']),
  authorizationEpoch: 'a'.repeat(43),
}
const context = {
  protocol: 1,
  principal: { apiRealm: 'https://example.test/api/v1', organizationId: 'org', userId: 'user' },
  accountLocationId: 'loc',
  selectedLocationId: 'loc',
  capabilities: ['sync.push'],
  authorizationEpoch: 'a'.repeat(43),
  policyRevision: 'ocwp-access-baseline-2',
  datasetIncarnation: '00000000-0000-4000-8000-000000000001',
  verifiedAt: '2026-10-14T00:00:00.000Z',
  offlineUntil: '2026-10-14T08:00:00.000Z',
  snapshotProtocol: 'baseline-v1',
}
const identity = {
  apiRealm: context.principal.apiRealm,
  organizationId: 'org',
  userId: 'user',
  selectedLocationId: 'loc',
  deviceGeneration: 1,
  tabAttemptId: 'tab',
  sessionHandle: 'binding',
}
const envelope = {
  mutation_id: 'm',
  entity_type: 'customer',
  entity_id: 'c',
  operation: 'create',
  organization_id: 'org',
  location_id: 'loc',
  base_version: null,
  occurred_at: context.verifiedAt,
  payload: { display_name: 'Test' },
}
const operation = {
  principalKey: ticket.principalKey,
  mutationId: 'm',
  entityId: 'c',
  entityType: 'customer',
  envelope,
  authoredDatasetIncarnation: context.datasetIncarnation,
}
const batch = { ticket, attemptId: 'attempt', operations: [operation] }
const source = () => ({
  ticket,
  context,
  identity,
  bearerToken: 'captured-token',
  isCurrent: () => true,
})
const result = {
  results: [
    {
      mutation_id: 'm',
      entity_id: 'c',
      status: 'applied',
      entity_version: 1,
      error_code: null,
      error_message: null,
    },
  ],
}
const response = (body, status = 200) => {
  const r = new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json', 'cache-control': 'no-store' },
  })
  Object.defineProperty(r, 'url', { value: context.principal.apiRealm + '/sync/mutations' })
  return r
}
test('coordinator captures token before awaited selection and passes callback through ACK', async () => {
  let release
  const barrier = new Promise((r) => (release = r))
  const request = source()
  let seen,
    ack = 0
  const kernel = {
    async listDispatchable(t, n, current) {
      assert.ok(current())
      await barrier
      return batch
    },
    async applyPushResult(t, b, r, current) {
      assert.ok(current())
      ack++
    },
    async deferDispatch() {
      assert.fail('defer')
    },
  }
  const c = createPushCoordinator({
    kernel,
    transport: {
      invalidate() {},
      async push(r) {
        seen = r.bearerToken
        return result
      },
    },
  })
  const pending = c.step(request)
  request.bearerToken = 'replacement'
  release()
  assert.equal((await pending).state, 'APPLIED')
  assert.equal(seen, 'captured-token')
  assert.equal(ack, 1)
})
test('replacement at selection never dispatches or defers under a newer session', async () => {
  let current = true,
    calls = 0
  const kernel = {
    async listDispatchable() {
      current = false
      return batch
    },
    async applyPushResult() {
      calls++
    },
    async deferDispatch() {
      calls++
    },
  }
  const c = createPushCoordinator({
    kernel,
    transport: {
      invalidate() {},
      async push() {
        calls++
        return result
      },
    },
  })
  const request = source()
  request.isCurrent = () => current
  assert.equal((await c.step(request)).state, 'HELD')
  assert.equal(calls, 0)
})
test('strict push uses exact captured credential, protocol and epoch', async () => {
  let captured
  const transport = createPushTransport({
    apiRealm: context.principal.apiRealm,
    now: () => Date.parse(context.verifiedAt),
    fetch: async (url, init) => {
      captured = { url, init }
      return response(result)
    },
  })
  await transport.push({ ...source(), batch })
  assert.equal(captured.init.headers.Authorization, 'Bearer captured-token')
  assert.equal(captured.init.headers['X-OCWP-Write-Protocol'], '1')
  assert.equal(captured.init.headers['X-OCWP-Authorization-Epoch'], context.authorizationEpoch)
  assert.equal(captured.init.credentials, 'omit')
  assert.equal(captured.init.redirect, 'error')
  assert.deepEqual(JSON.parse(captured.init.body), { mutations: [envelope] })
})
test('whole refusal is typed and status-paired; oversized JSON never parsed', async () => {
  for (const [status, body, code] of [
    [
      409,
      {
        error: {
          code: 'client_upgrade_required',
          message: 'safe',
          details: {},
          request_id: 'request',
        },
      },
      'client_upgrade_required',
    ],
    [
      400,
      {
        error: {
          code: 'client_upgrade_required',
          message: 'safe',
          details: {},
          request_id: 'request',
        },
      },
      'invalid_response',
    ],
    [200, { padding: 'x'.repeat(300000) }, 'invalid_response'],
  ]) {
    const t = createPushTransport({
      apiRealm: context.principal.apiRealm,
      now: () => Date.parse(context.verifiedAt),
      fetch: async () => response(body, status),
    })
    await assert.rejects(
      t.push({ ...source(), batch }),
      (e) => e instanceof PushTransportError && e.code === code,
    )
  }
})

test('transport rejects ticket epoch or incarnation mismatches before any HTTP', async () => {
  let calls = 0
  const transport = createPushTransport({
    apiRealm: context.principal.apiRealm,
    now: () => Date.parse(context.verifiedAt),
    fetch: async () => {
      calls++
      return response(result)
    },
  })
  const request = { ...source(), batch: structuredClone(batch) }
  request.ticket = { ...request.ticket, authorizationEpoch: 'b'.repeat(43) }
  request.batch.ticket = request.ticket
  await assert.rejects(
    transport.push(request),
    (e) => e instanceof PushTransportError && e.code === 'invalid_request',
  )
  assert.equal(calls, 0)
  const wrongIncarnation = { ...source(), batch: structuredClone(batch) }
  wrongIncarnation.batch.operations[0].authoredDatasetIncarnation =
    '00000000-0000-4000-8000-000000000099'
  await assert.rejects(
    transport.push(wrongIncarnation),
    (e) => e instanceof PushTransportError && e.code === 'invalid_request',
  )
  assert.equal(calls, 0)
})

for (const scenario of [
  { name: 'closed private 503', malformed: false, private: true, retryable: true },
  { name: '503 with malformed body', malformed: true, private: true, retryable: false },
  { name: '503 without no-store', malformed: false, private: false, retryable: false },
]) {
  test(`${scenario.name} preserves the captured batch and uses the exact retry/hold class`, async () => {
    const original = structuredClone(batch)
    let deferred,
      disabled = 0,
      acknowledged = 0,
      requests = 0
    const transport = createPushTransport({
      apiRealm: context.principal.apiRealm,
      now: () => Date.parse(context.verifiedAt),
      fetch: async () => {
        requests++
        const r = response(
          scenario.malformed
            ? {}
            : {
                error: {
                  code: 'temporary_unavailable',
                  message: 'Synthetic temporary server failure',
                  details: {},
                  request_id: 'synthetic-transient-failure',
                },
              },
          503,
        )
        if (!scenario.private) r.headers.delete('cache-control')
        return r
      },
    })
    const coordinator = createPushCoordinator({
      transport,
      kernel: {
        async listDispatchable() {
          return batch
        },
        async applyPushResult() {
          acknowledged++
        },
        async deferDispatch(t, b, reason, current) {
          assert.ok(current())
          assert.deepEqual(t, ticket)
          assert.deepEqual(b, original)
          deferred = reason
        },
        disableBaselineSession(t, current) {
          assert.ok(current())
          assert.deepEqual(t, ticket)
          disabled++
        },
      },
    })
    assert.deepEqual(await coordinator.step(source()), {
      state: scenario.retryable ? 'RETRY_LATER' : 'HELD',
      reason: scenario.retryable ? 'temporary_unavailable' : 'invalid_response',
    })
    assert.equal(deferred, scenario.retryable ? 'transient' : 'integrity')
    assert.equal(disabled, scenario.retryable ? 0 : 1)
    assert.equal(acknowledged, 0)
    assert.equal(requests, 1)
    assert.deepEqual(batch, original)
  })
}

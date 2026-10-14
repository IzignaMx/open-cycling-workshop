import { createKernelDatabase } from '../../src/access-kernel/database.js'
import { createBaselineCoordinator } from '../../src/access-kernel/baseline-coordinator.js'
import { canonicalJson } from '../../src/access-kernel/operations.js'
import { AccessKernel } from '../../src/access-kernel/kernel.js'
import { BaselineTransactions } from '../../src/access-kernel/baseline-store.js'
import { createBaselineTransport } from '../../src/access-kernel/baseline-transport.js'
import {
  createServerContextAdapter,
  convertServerContext,
  type ContextRequestIdentity,
} from '../../src/access-kernel/server-context.js'

const organizationId = '00000000-0000-7000-8000-000000000001'
const userId = '00000000-0000-7000-8000-000000000003'
const selectedLocationId = '00000000-0000-7000-8000-000000000002'

/** Qualification composition only; actual null wire values are never rewritten. */
export async function openBaselineQualification(name: string, resume = false) {
  if (!name.startsWith('isolated-baseline-test-'))
    throw new Error('Isolated test database required')
  const apiRealm = `${location.origin}/api/v1`
  const login = await fetch(`${apiRealm}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      organization_id: organizationId,
      username: 'e2e-admin',
      password: 'ocwp-e2e-password',
    }),
  })
  if (!login.ok) throw new Error('Test login failed')
  const bearerToken = ((await login.json()) as { access_token: string }).access_token
  const db = createKernelDatabase(name)
  const kernel = new AccessKernel(db)
  const verification = await kernel.beginVerification(crypto.randomUUID())
  const identity: ContextRequestIdentity = {
    ...verification,
    apiRealm,
    organizationId,
    userId,
    selectedLocationId,
    sessionHandle: crypto.randomUUID(),
  }
  const adapter = createServerContextAdapter({ apiRealm, fetch, now: Date.now })
  const verified = await adapter.verify({ identity, bearerToken, isCurrent: () => true })
  if (verified.context.snapshotProtocol !== null)
    throw new Error('Qualification requires actual null advertisement')
  const accepted = await kernel.acceptVerifiedContext(verification, verified.context)
  // Ordinary admission must reject before a baseline HTTP call can be selected.
  let ordinaryRejected = false
  try {
    await kernel.beginBaseline(accepted.ticket)
  } catch {
    ordinaryRejected = true
  }
  if (!ordinaryRejected) throw new Error('Null advertisement admitted')
  let ordinaryCalls = 0
  const ordinaryTransport = createBaselineTransport({
    apiRealm,
    now: Date.now,
    fetch: async () => {
      ordinaryCalls += 1
      throw new Error('Null must not dispatch')
    },
  })
  const ordinary = createBaselineCoordinator({
    kernel,
    transport: ordinaryTransport,
    now: Date.now,
    random: () => 0,
    online: () => true,
  })
  const ordinarySession = {
    ticket: accepted.ticket,
    context: verified.context,
    identity,
    bearerToken,
    isCurrent: () => true,
  }
  for (const action of [ordinary.start, ordinary.resume, ordinary.step]) {
    if ((await action(ordinarySession)).state !== 'BASELINE_REQUIRED' || ordinaryCalls !== 0)
      throw new Error('Null coordinator dispatched')
  }
  const transactions = new BaselineTransactions(db, Date.now, () => crypto.randomUUID())
  const ticket = resume ? accepted.ticket : await transactions.begin(accepted.ticket)
  if (resume) await transactions.resume(ticket)
  Object.assign(identity, {
    deviceGeneration: ticket.deviceGeneration,
    tabAttemptId: ticket.tabAttemptId,
    expectedAuthorizationEpoch: ticket.authorizationEpoch,
  })
  let commitGate: Promise<void> | null = null
  let releaseCommit: (() => void) | null = null
  let responseWaiting = false
  let calls = 0
  let loseNext = false
  let loseReplay: string | null = null
  const requests: Array<{ kind: string; body: string; bearerMatches: boolean }> = []
  const transport = createBaselineTransport({
    apiRealm,
    now: Date.now,
    fetch: async (input, init) => {
      calls += 1
      requests.push({
        kind: String(input).split('/').at(-1)!,
        body: String(init?.body),
        bearerMatches: new Headers(init?.headers).get('Authorization') === `Bearer ${bearerToken}`,
      })
      const response = await fetch(input, init)
      if (loseNext) {
        loseNext = false
        // The real server has committed before its response is deliberately discarded.
        if (!response.ok) throw new Error('Expected committed server response')
        loseReplay = await response.clone().text()
        await response.body?.cancel()
        throw new Error('Injected response loss after server commit')
      }
      if (loseReplay !== null) {
        if ((await response.clone().text()) !== loseReplay) throw new Error('Server replay changed')
        loseReplay = null
      }
      return response
    },
  })
  async function snapshot() {
    return {
      partition: await db.cachePartitions.get(ticket.partitionId),
      control: await db.deviceControl.get('device'),
      records: await db.cacheRecords
        .filter((row) => row.partitionId === ticket.partitionId)
        .toArray(),
      history: JSON.stringify([
        await db.operationJournal.toArray(),
        await db.operationDelivery.toArray(),
        await db.operationEvents.toArray(),
      ]),
      credentialsPersisted: (await Promise.all(db.tables.map((table) => table.toArray()))).some(
        (rows) => JSON.stringify(rows).includes(bearerToken),
      ),
      requests,
      calls,
    }
  }
  return {
    db,
    kernel,
    ticket,
    identity,
    ordinaryRejected,
    ordinaryCalls,
    snapshot,
    delayNextCommit() {
      commitGate = new Promise<void>((resolve) => {
        releaseCommit = resolve
      })
      responseWaiting = false
    },
    responseWaiting() {
      return responseWaiting
    },
    releaseCommit() {
      releaseCommit?.()
      commitGate = null
    },
    async seedPendingHistory(entityId: string) {
      const mutationId = crypto.randomUUID(),
        createdAt = new Date().toISOString()
      const envelope = {
        mutation_id: mutationId,
        entity_type: 'customer' as const,
        entity_id: entityId,
        operation: 'update' as const,
        organization_id: organizationId,
        location_id: selectedLocationId,
        base_version: 1,
        occurred_at: createdAt,
        payload: { display_name: 'Preserved pending work' },
      }
      await db.operationJournal.add({
        mutationId,
        principalKey: ticket.principalKey,
        organizationId,
        locationId: selectedLocationId,
        entityType: 'customer',
        entityId,
        authoredUnderEpoch: ticket.authorizationEpoch,
        authoredDatasetIncarnation: verified.context.datasetIncarnation,
        localSequence: 1,
        dependsOn: [],
        envelope,
        envelopeCanonical: canonicalJson(envelope),
        optimistic: {
          customer_id: entityId,
          organization_id: organizationId,
          location_id: selectedLocationId,
          version: 2,
          display_name: 'Preserved pending work',
          email: null,
          phone: null,
          created_at: createdAt,
          updated_at: createdAt,
        },
        createdAt,
      })
      await db.operationDelivery.add({
        mutationId,
        principalKey: ticket.principalKey,
        locationId: selectedLocationId,
        entityType: 'customer',
        entityId,
        localSequence: 1,
        dispatchable: 1,
        unresolved: 1,
        blocked: 0,
        resultVersion: 0,
        state: 'pending',
        attemptId: null,
        deviceGeneration: null,
        attempts: 0,
        retryAt: 0,
        result: null,
      })
      await db.operationEvents.add({
        mutationId,
        kind: 'local',
        occurredAt: createdAt,
        attemptId: null,
        details: { preserved: true },
      })
    },
    async rest(path: string, body: unknown) {
      const response = await fetch(`${apiRealm}${path}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${bearerToken}` },
        body: JSON.stringify(body),
      })
      if (!response.ok) throw new Error(`Fixture REST failed ${response.status}`)
      return (await response.json()) as Record<string, unknown>
    },
    async step(lose = false) {
      const pending = await transactions.pending(ticket)
      const next = pending.baseline.next
      if (!next) throw new Error('No pending step')
      const body = JSON.parse(next.body) as { continuation?: string; checkpoint?: string }
      loseNext = lose
      const value = await transport.request({
        ...next,
        identity,
        bearerToken,
        isCurrent: () => true,
        binding: {
          context: pending.context,
          identity,
          ...(pending.baseline.baselineId ? { baselineId: pending.baseline.baselineId } : {}),
          ...('continuation' in body ? { predecessor: body.continuation } : {}),
          ...('checkpoint' in body ? { checkpoint: body.checkpoint } : {}),
        },
      })
      if (commitGate) {
        responseWaiting = true
        await commitGate
      }
      if (next.kind === 'activation') {
        const response = value as { context: unknown }
        const fresh = convertServerContext(response.context, identity, Date.now())
        let rejected = false
        try {
          await transactions.activate(ticket, body.checkpoint!, fresh)
        } catch {
          rejected = true
        }
        if (!rejected) throw new Error('Null activation accepted')
        return { kind: next.kind, nullActivationRejected: rejected }
      }
      await transactions.commit(ticket, next, value, identity)
      return { kind: next.kind, nullActivationRejected: false }
    },
    async rejectOrdinaryReuse() {
      const current = await db.cachePartitions.get(ticket.partitionId)
      if (!current?.baseline) throw new Error('Missing qualification evidence')
      // Adversarial flags cannot turn actual null wire evidence into authority.
      await db.cachePartitions.update(ticket.partitionId, {
        status: 'active',
        baselineComplete: true,
        cursor: current.baseline.checkpoint,
        baseline: { ...current.baseline, phase: 'active', next: null },
      })
      const attempt = await kernel.beginVerification(crypto.randomUUID())
      const freshIdentity = { ...identity, ...attempt }
      const fresh = await adapter.verify({
        identity: freshIdentity,
        bearerToken,
        isCurrent: () => true,
      })
      const result = await kernel.acceptVerifiedContext(attempt, fresh.context)
      let denied = false
      try {
        await kernel.readEntity(result.ticket, 'customer', 'untrusted')
      } catch {
        denied = true
      }
      return { state: result.state, denied }
    },
  }
}
export type BaselineQualification = Awaited<ReturnType<typeof openBaselineQualification>>
declare global {
  interface Window {
    baselineQualification: BaselineQualification
    delayedBaselineResult: Promise<string>
  }
}

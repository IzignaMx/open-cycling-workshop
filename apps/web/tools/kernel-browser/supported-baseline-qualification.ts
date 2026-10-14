import { createKernelDatabase } from '../../src/access-kernel/database.js'
import { AccessKernel } from '../../src/access-kernel/kernel.js'
import { createServerContextAdapter } from '../../src/access-kernel/server-context.js'
import { createBaselineCoordinator } from '../../src/access-kernel/baseline-coordinator.js'
import { createBaselineTransport } from '../../src/access-kernel/baseline-transport.js'

/** Isolated actual-HTTP qualification. The disposable server must genuinely enable
 * cutover and seed this separate floor-1 organization. Never rewrite wire support.
 */
export async function openSupportedBaselineQualification(name: string) {
  if (!name.startsWith('isolated-supported-baseline-test-'))
    throw new Error('Isolated supported test database required')
  const apiRealm = `${location.origin}/api/v1`
  const organizationId = '00000000-0000-7000-8000-000000000101'
  const selectedLocationId = '00000000-0000-7000-8000-000000000102'
  const userId = '00000000-0000-7000-8000-000000000103'
  const login = await fetch(`${apiRealm}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      organization_id: organizationId,
      username: 'e2e-admin',
      password: 'ocwp-e2e-password',
    }),
  })
  if (!login.ok) throw new Error('Supported fixture login failed')
  const bearerToken = ((await login.json()) as { access_token: string }).access_token
  const db = createKernelDatabase(name)
  const kernel = new AccessKernel(db)
  const verification = await kernel.beginVerification(crypto.randomUUID())
  const identity = {
    ...verification,
    apiRealm,
    organizationId,
    userId,
    selectedLocationId,
    sessionHandle: crypto.randomUUID(),
  }
  const adapter = createServerContextAdapter({ apiRealm, fetch, now: Date.now })
  const verified = await adapter.verify({ identity, bearerToken, isCurrent: () => true })
  if (verified.context.snapshotProtocol !== 'baseline-v1')
    throw new Error('Genuine supported server advertisement required')
  const accepted = await kernel.acceptVerifiedContext(verification, verified.context)
  const observations: Array<{
    path: string
    snapshotProtocol: unknown
    datasetIncarnation: unknown
    policyRevision: unknown
  }> = []
  const transport = createBaselineTransport({
    apiRealm,
    now: Date.now,
    fetch: async (url, init) => {
      const response = await fetch(url, init)
      const path = new URL(String(url)).pathname.split('/').at(-1)!
      if (response.ok && ['start', 'validate-activation'].includes(path)) {
        const value = (await response.clone().json()) as { context: Record<string, unknown> }
        observations.push({
          path,
          snapshotProtocol: value.context.snapshot_protocol,
          datasetIncarnation: value.context.dataset_incarnation,
          policyRevision: value.context.policy_revision,
        })
      }
      return response
    },
  })
  const coordinator = createBaselineCoordinator({
    kernel,
    transport,
    now: Date.now,
    random: () => 0,
    online: () => true,
  })
  const session = {
    ticket: accepted.ticket,
    context: verified.context,
    identity,
    bearerToken,
    isCurrent: () => true,
  }
  return {
    db,
    context: verified.context,
    initialState: accepted.state,
    async createCustomer() {
      const response = await fetch(`${apiRealm}/customers`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${bearerToken}`,
          'X-OCWP-Write-Protocol': '1',
        },
        body: JSON.stringify({
          location_id: selectedLocationId,
          display_name: 'Supported direct REST history',
        }),
      })
      if (!response.ok) throw new Error(`Supported fixture REST failed ${response.status}`)
      return (await response.json()) as { customer_id: string }
    },
    async start() {
      const outcome = await coordinator.start(session)
      session.ticket = outcome.ticket
      return outcome
    },
    async step() {
      return coordinator.step(session)
    },
    async reverify() {
      const attempt = await kernel.beginVerification(crypto.randomUUID())
      const freshIdentity = { ...identity, ...attempt }
      const fresh = await adapter.verify({
        identity: freshIdentity,
        bearerToken,
        isCurrent: () => true,
      })
      return kernel.acceptVerifiedContext(attempt, fresh.context)
    },
    async snapshot() {
      return {
        partition: await db.cachePartitions.get(session.ticket.partitionId),
        context: (await db.accessContexts.get(session.ticket.partitionId))?.context,
        control: await db.deviceControl.get('device'),
        records: await db.cacheRecords
          .filter((row) => row.partitionId === session.ticket.partitionId)
          .toArray(),
        observations,
        journalCount: await db.operationJournal.count(),
        credentialsPersisted: (await Promise.all(db.tables.map((table) => table.toArray()))).some(
          (rows) => JSON.stringify(rows).includes(bearerToken),
        ),
      }
    },
  }
}

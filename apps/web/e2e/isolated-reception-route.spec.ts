import { expect, test, type Page } from '@playwright/test'
import {
  apiLogin,
  createCaseIdentity,
  createCustomer,
  kernelSnapshot,
  login,
  sessionToken,
  waitForApplied,
  waitForConfirmed,
  waitForReady,
  writeHeaders,
} from './helpers/authenticated-workshop.js'
import { fillIntake } from './helpers/orders.js'

const A = 'http://127.0.0.1:5176'
const B = 'http://127.0.0.1:5173'
type Barrier = { closed: boolean; forwarded: number; active: number; blocked: number }

function getFromPage(page: Page, path: string, token: string) {
  return page.evaluate(
    async ({ path, token }) => {
      const response = await fetch(path, {
        cache: 'no-store',
        headers: { Authorization: `Bearer ${token}` },
      })
      const body: unknown = await response.json()
      return { status: response.status, body }
    },
    { path, token },
  )
}

test.describe.configure({ retries: 0 })
test.use({ trace: 'on' })

test('isolated workshop API route preserves and converges an inline reception', async ({
  browser,
  request,
}, info) => {
  test.setTimeout(120_000)
  const owner = await apiLogin(request, 'e2e-owner')
  const location = await request.post('/api/v1/locations', {
    headers: await writeHeaders(request, owner),
    data: { name: `Synthetic route isolation ${crypto.randomUUID()}` },
  })
  expect(location.status()).toBe(201)
  const { location_id: locationId } = (await location.json()) as { location_id: string }
  const identity = await createCaseIdentity(request, { locationId })
  const first = await browser.newContext({ baseURL: A })
  const second = await browser.newContext({ baseURL: B })
  const barrier = async (): Promise<Barrier> => {
    const response = await request.get(`${A}/__fixture/api-isolation`)
    expect(response.status()).toBe(200)
    return response.json() as Promise<Barrier>
  }
  const changeBarrier = async (action: 'close' | 'open') => {
    const response = await request.post(`${A}/__fixture/api-isolation/${action}`)
    expect(response.status()).toBe(200)
  }
  let closed = false
  const receipt: {
    route: string
    stage: string
    outcome: 'failed' | 'passed'
    physicalLan: 'not_assessed'
    wan: 'not_assessed'
    drained?: Barrier
    isolated?: Barrier
    reopened?: Barrier
    blockedProbe?: 'fetch_rejected'
    verifiedContext?: boolean
    browserOnlineUnchanged?: boolean
    clientBReachableDuringIsolation?: boolean
    beforeReopenEntityStatuses?: [404, 404]
    afterReopenEntityStatuses?: [200, 200]
    bicycleId?: string
    orderId?: string
    bicycleMutationId?: string
    orderMutationId?: string
    serverCreations?: number
  } = {
    route: 'synthetic_loopback_api_connection_drop',
    stage: 'verify_initial_sessions',
    outcome: 'failed',
    physicalLan: 'not_assessed',
    wan: 'not_assessed',
  }
  try {
    const a = await first.newPage()
    const b = await second.newPage()
    expect((await barrier()).closed).toBe(false)
    await login(a, identity)
    const customer = await createCustomer(a, `Synthetic route customer ${crypto.randomUUID()}`)
    await waitForApplied(a, customer.mutationId)
    await waitForConfirmed(a, customer)
    await login(b, identity)
    const tokenA = await sessionToken(a)
    const tokenB = await sessionToken(b)
    expect(Boolean(tokenA && tokenB && tokenA !== tokenB)).toBe(true)
    const initialA = await kernelSnapshot(a)
    const initialB = await kernelSnapshot(b)
    expect(initialB.context.datasetIncarnation).toBe(initialA.context.datasetIncarnation)
    expect(initialB.journal).toEqual([])
    for (const page of [a, b]) {
      await page.evaluate(() => navigator.serviceWorker.ready)
      await expect
        .poll(() => page.evaluate(() => Boolean(navigator.serviceWorker.controller)))
        .toBe(true)
      expect(await page.evaluate(() => navigator.onLine)).toBe(true)
    }
    const customerPath = `/api/v1/customers/${customer.entityId}`
    const assertCustomer = async (page: Page, token: string) => {
      expect(await getFromPage(page, customerPath, token)).toMatchObject({
        status: 200,
        body: { customer_id: customer.entityId, location_id: locationId, version: 1 },
      })
    }
    const assertServerContext = async (
      page: Page,
      token: string,
      local: typeof initialA.context,
    ) => {
      expect(
        await getFromPage(page, `/api/v1/auth/context?selected_location_id=${locationId}`, token),
      ).toMatchObject({
        status: 200,
        body: {
          principal: { organization_id: local.principal.organizationId, user_id: identity.userId },
          selected_location_id: locationId,
          dataset_incarnation: local.datasetIncarnation,
          authorization_epoch: local.authorizationEpoch,
          policy_revision: local.policyRevision,
          capabilities: expect.arrayContaining(['customers.read', 'bicycles.read', 'orders.read']),
        },
      })
    }
    await assertServerContext(a, tokenA, initialA.context)
    await assertServerContext(b, tokenB, initialB.context)
    await assertCustomer(a, tokenA)
    await assertCustomer(b, tokenB)
    receipt.verifiedContext = true
    receipt.stage = 'close_and_probe'
    await changeBarrier('close')
    closed = true
    await expect.poll(async () => (await barrier()).active).toBe(0)
    const drained = await barrier()
    expect(drained.closed).toBe(true)
    expect(drained.active).toBe(0)
    receipt.drained = drained

    // An injected connection drop is not a reachable HTTP refusal and does not
    // toggle browser connectivity. Absence of server effects is checked separately.
    const aProbe = await a.evaluate(
      async ({ path, token }) => {
        try {
          const response = await fetch(path, {
            cache: 'no-store',
            headers: { Authorization: `Bearer ${token}` },
          })
          return { transport: 'response', status: response.status }
        } catch (error) {
          if (!(error instanceof TypeError)) throw error
          return { transport: 'fetch_rejected' }
        }
      },
      { path: customerPath, token: tokenA },
    )
    expect(aProbe).toEqual({ transport: 'fetch_rejected' })
    receipt.blockedProbe = 'fetch_rejected'
    const afterProbe = await barrier()
    expect(afterProbe.blocked).toBeGreaterThan(drained.blocked)
    expect(afterProbe.forwarded).toBe(drained.forwarded)
    await assertCustomer(b, tokenB)

    receipt.clientBReachableDuringIsolation = true
    receipt.stage = 'author_isolated'
    const problem = `Synthetic isolated intake ${crypto.randomUUID()}`
    await fillIntake(a, customer.entityId, problem)
    await a.getByRole('button', { name: 'Guardar orden', exact: true }).click()
    await expect(a.getByText('Orden guardada localmente', { exact: true })).toBeVisible()
    await expect.poll(async () => (await kernelSnapshot(a)).journal.length).toBe(3)
    const held = await kernelSnapshot(a)
    const order = held.journal.find(
      (row) =>
        row.entityType === 'service_order' &&
        row.envelope.operation === 'create' &&
        row.envelope.payload.reported_problem === problem,
    )!
    expect(order).toBeDefined()
    expect(held.journal).toHaveLength(3)
    const bicycle = held.journal.find((row) => row.entityType === 'bicycle')!
    expect(bicycle).toBeDefined()
    expect(order.dependsOn).toContain(bicycle.mutationId)
    expect(order.envelope.payload.bicycle_id).toBe(bicycle.entityId)
    expect(order.envelope.payload.customer_id).toBe(customer.entityId)
    expect(bicycle.envelope.payload.customer_id).toBe(customer.entityId)
    const assertPending = (snapshot: typeof held) => {
      for (const operation of [bicycle, order]) {
        expect(['pending', 'inflight', 'retryable', 'awaiting_confirmation']).toContain(
          snapshot.delivery.find((row) => row.mutationId === operation.mutationId)?.state,
        )
        expect(snapshot.records.some((row) => row.entityId === operation.entityId)).toBe(false)
      }
    }
    assertPending(held)
    Object.assign(receipt, {
      bicycleId: bicycle.entityId,
      orderId: order.entityId,
      bicycleMutationId: bicycle.mutationId,
      orderMutationId: order.mutationId,
    })
    receipt.stage = 'verify_absence_and_reload'
    const paths = [
      `/api/v1/bicycles/${bicycle.entityId}`,
      `/api/v1/service-orders/${order.entityId}`,
    ]
    const assertAbsent = async () => {
      // These routers return FastAPI detail strings, not custom ApiError codes.
      expect(await getFromPage(b, paths[0]!, tokenB)).toEqual({
        status: 404,
        body: { detail: 'bicycle not found' },
      })
      expect(await getFromPage(b, paths[1]!, tokenB)).toEqual({
        status: 404,
        body: { detail: 'order not found' },
      })
    }
    await assertAbsent()
    const reloaded = await a.reload({ waitUntil: 'domcontentloaded' })
    expect(reloaded?.status()).toBe(200)
    await waitForReady(a)
    await expect(a.getByRole('listitem', { name: `Orden ${problem}`, exact: true })).toBeVisible()
    expect(await a.evaluate(() => navigator.onLine)).toBe(true)
    expect(await a.evaluate(() => Boolean(navigator.serviceWorker.controller))).toBe(true)
    const staticResponse = await request.get(`${A}/sw.js`)
    expect(staticResponse.status()).toBe(200)
    const restored = await kernelSnapshot(a)
    expect(restored.journal).toEqual(held.journal)
    expect(restored.context.datasetIncarnation).toBe(initialA.context.datasetIncarnation)
    assertPending(restored)
    await assertServerContext(b, tokenB, initialB.context)
    await assertAbsent()
    receipt.beforeReopenEntityStatuses = [404, 404]
    await assertCustomer(b, tokenB)
    expect(await b.evaluate(() => navigator.onLine)).toBe(true)
    const isolated = await barrier()
    expect(isolated).toMatchObject({ closed: true, active: 0, forwarded: drained.forwarded })
    expect(isolated.blocked).toBeGreaterThan(drained.blocked)
    receipt.isolated = isolated
    receipt.stage = 'ordinary_recovery'
    await changeBarrier('open')
    closed = false

    // These are durable-state polls, not event listeners; a fast application
    // immediately after reopening cannot be missed.
    for (const operation of [bicycle, order]) {
      await waitForApplied(a, operation.mutationId, 40_000)
      await waitForConfirmed(a, operation)
    }
    expect((await kernelSnapshot(a)).journal).toEqual(held.journal)
    const reopened = await barrier()
    expect(reopened.closed).toBe(false)
    expect(reopened.forwarded).toBeGreaterThan(isolated.forwarded)
    receipt.reopened = reopened
    expect(await a.evaluate(() => navigator.onLine)).toBe(true)
    expect(await getFromPage(b, paths[0]!, tokenB)).toMatchObject({
      status: 200,
      body: {
        bicycle_id: bicycle.entityId,
        customer_id: customer.entityId,
        location_id: locationId,
        version: 1,
      },
    })
    expect(await getFromPage(b, paths[1]!, tokenB)).toMatchObject({
      status: 200,
      body: {
        order_id: order.entityId,
        bicycle_id: bicycle.entityId,
        customer_id: customer.entityId,
        location_id: locationId,
        reported_problem: problem,
        version: 1,
      },
    })
    receipt.afterReopenEntityStatuses = [200, 200]
    receipt.browserOnlineUnchanged = true
    receipt.stage = 'confirm_convergence'
    await b.reload()
    await waitForReady(b)
    await expect
      .poll(
        async () =>
          (await kernelSnapshot(b)).records.some((row) => row.entityId === order.entityId),
        { timeout: 20_000 },
      )
      .toBe(true)
    await expect(b.getByRole('listitem', { name: `Orden ${problem}`, exact: true })).toBeVisible()
    const converged = await kernelSnapshot(b)
    expect(converged.journal).toEqual([])
    expect(converged.context.datasetIncarnation).toBe(initialB.context.datasetIncarnation)
    for (const operation of [bicycle, order]) {
      expect(converged.records.find((row) => row.entityId === operation.entityId)).toMatchObject({
        entityType: operation.entityType,
        version: 1,
      })
    }
    const changes = await getFromPage(
      b,
      `/api/v1/sync/changes?cursor=0&location_id=${locationId}&limit=100`,
      tokenB,
    )
    expect(changes.status).toBe(200)
    const feed = changes.body as {
      has_more: boolean
      items: {
        entity_id: string
        entity_type: string
        operation: string
        entity_version: number
        location_id: string
      }[]
    }
    expect(feed.has_more).toBe(false)
    expect(
      feed.items.every(
        (row) =>
          row.location_id === locationId && row.operation === 'create' && row.entity_version === 1,
      ),
    ).toBe(true)
    expect(feed.items.map((row) => [row.entity_type, row.entity_id]).sort()).toEqual(
      [
        ['customer', customer.entityId],
        ['bicycle', bicycle.entityId],
        ['service_order', order.entityId],
      ].sort(),
    )
    receipt.serverCreations = feed.items.length
    receipt.stage = 'verified'
    receipt.outcome = 'passed'
  } finally {
    try {
      // Close test-owned sessions before reopening on failure; no recovery replay.
      await Promise.all([first.close(), second.close()])
        .then(async () => {
          if (closed) await changeBarrier('open')
        })
        .catch((error: unknown) => {
          if (receipt.outcome === 'passed') {
            receipt.stage = 'cleanup'
            receipt.outcome = 'failed'
          }
          throw error
        })
    } finally {
      // A partial receipt reports completed observations only. The trace
      // retains the actual error; do not copy arbitrary error text or tokens.
      await info.attach('isolated-reception-route', {
        body: JSON.stringify(receipt),
        contentType: 'application/json',
      })
    }
  }
})

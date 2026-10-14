import { expect, test, type Page } from '@playwright/test'
import {
  createCaseIdentity,
  createCustomer,
  holdJournalCompletion,
  kernelSnapshot,
  login,
  pendingMutationCount,
  releaseJournalCompletion,
  sessionToken,
  strictPush,
  waitForApplied,
  waitForConfirmed,
  waitForJournalBarrier,
  waitForReady,
} from './helpers/authenticated-workshop.js'
import type { MutationEnvelope } from '../src/sync/types.js'

async function readyCustomer(page: Page, name: string, timeout = 10_000) {
  await expect(page.getByText('Cliente guardado localmente', { exact: true })).toBeVisible({
    timeout,
  })
  const operation = (await kernelSnapshot(page)).journal.find(
    (item) => item.envelope.payload.display_name === name,
  )!
  expect(operation).toBeDefined()
  await waitForApplied(page, operation.mutationId, timeout)
  await waitForConfirmed(page, operation)
  return operation
}

test('duplicate mutation delivery applies exactly once and preserves the journal across lost ACK and reload', async ({
  page,
  request,
  browser,
}) => {
  const identity = await createCaseIdentity(request)
  await login(page, identity)
  const name = `Cliente Caos Duplicado ${crypto.randomUUID()}`
  const token = await sessionToken(page)
  let originalBody = '',
    originalHeaders: Record<string, string> = {},
    deliveries = 0
  let releaseLost = () => {}
  const lostGate = new Promise<void>((resolve) => {
    releaseLost = resolve
  })
  const receipts: unknown[] = []
  await page.route('**/api/v1/sync/mutations', async (route) => {
    deliveries += 1
    if (deliveries === 1) {
      originalHeaders = route.request().headers()
      originalBody = route.request().postData()!
      for (const mutation of (JSON.parse(originalBody) as { mutations: MutationEnvelope[] })
        .mutations)
        expect(Object.keys(mutation).sort()).toEqual(
          [
            'mutation_id',
            'entity_type',
            'entity_id',
            'operation',
            'organization_id',
            'location_id',
            'base_version',
            'occurred_at',
            'payload',
          ].sort(),
        )
      expect(originalHeaders['x-ocwp-write-protocol']).toBe('1')
      expect(originalHeaders['x-ocwp-authorization-epoch']).toBeTruthy()
      for (let i = 0; i < 2; i += 1) {
        const replay = await request.post('/api/v1/sync/mutations', {
          headers: originalHeaders,
          data: originalBody,
        })
        expect(replay.status()).toBe(200)
        receipts.push(await replay.json())
      }
      await lostGate
      await route.abort('connectionreset')
      return
    }
    expect(route.request().postData()).toBe(originalBody)
    await route.continue()
  })
  try {
    const original = await createCustomer(page, name)
    await expect.poll(() => receipts.length).toBe(2)
    expect(receipts[1]).toEqual(receipts[0])
    expect(
      (await kernelSnapshot(page)).delivery.find((item) => item.mutationId === original.mutationId)
        ?.state,
    ).toBe('inflight')
    expect((await kernelSnapshot(page)).journal).toContainEqual(original)
    // The browser actually reloads with no ACK. The exact known-author operation,
    // not a reconstructed legacy queue row, must be reclaimed and replayed.
    const reload = page.reload({ waitUntil: 'domcontentloaded' })
    releaseLost()
    await reload
    await waitForReady(page)
    await waitForApplied(page, original.mutationId, 25_000)
    await waitForConfirmed(page, original)
    expect(deliveries).toBeGreaterThanOrEqual(2)
    expect((await kernelSnapshot(page)).journal).toContainEqual(original)
    const server = await request.get(`/api/v1/customers/${original.entityId}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    expect(server.status()).toBe(200)
    expect(await server.json()).toMatchObject({
      customer_id: original.entityId,
      display_name: name,
      version: 1,
    })
    const second = await browser.newContext()
    try {
      const other = await second.newPage()
      await login(other, identity)
      expect(
        (await kernelSnapshot(other)).records.filter((item) => item.entityId === original.entityId),
      ).toHaveLength(1)
    } finally {
      await second.close()
    }
  } finally {
    releaseLost()
    await page.unrouteAll({ behavior: 'wait' })
  }
})

test('temporary server failure retries with backoff and converges', async ({ page, request }) => {
  const identity = await createCaseIdentity(request)
  await login(page, identity)
  let failures = 0
  const attempts: Array<{ body: string; at: number }> = []
  await page.route('**/api/v1/sync/mutations', async (route) => {
    attempts.push({ body: route.request().postData()!, at: Date.now() })
    if (failures < 2) {
      failures += 1
      await route.fulfill({
        status: 503,
        headers: { 'Cache-Control': 'no-store' },
        json: {
          error: {
            code: 'temporary_unavailable',
            message: 'Synthetic temporary server failure',
            details: {},
            request_id: 'synthetic-transient-failure',
          },
        },
      })
    } else await route.continue()
  })
  const original = await createCustomer(page, `Cliente Caos 503 ${crypto.randomUUID()}`)
  await waitForApplied(page, original.mutationId, 30_000)
  await waitForConfirmed(page, original)
  expect(failures).toBe(2)
  expect(attempts).toHaveLength(3)
  expect(new Set(attempts.map((item) => item.body)).size).toBe(1)
  expect(attempts[1]!.at - attempts[0]!.at).toBeGreaterThanOrEqual(100)
  expect(attempts[2]!.at - attempts[1]!.at).toBeGreaterThanOrEqual(100)
  const snapshot = await kernelSnapshot(page)
  expect(snapshot.journal).toContainEqual(original)
  expect(snapshot.delivery.find((item) => item.mutationId === original.mutationId)?.attempts).toBe(
    3,
  )
  expect(
    snapshot.events.filter(
      (item) => item.mutationId === original.mutationId && item.kind === 'dispatch',
    ),
  ).toHaveLength(3)
  await page.unrouteAll()
})

test('baseline setup rejects stale synced state and a withheld create acknowledgement', async ({
  page,
  request,
}) => {
  const identity = await createCaseIdentity(request)
  await login(page, identity)
  const name = `Cliente Barrera Base ${crypto.randomUUID()}`
  await holdJournalCompletion(page, {
    entityType: 'customer',
    payloadKey: 'display_name',
    value: name,
  })
  let releaseAck = () => {}
  const ackGate = new Promise<void>((resolve) => {
    releaseAck = resolve
  })
  let ackHeld = false
  await page.route('**/api/v1/sync/mutations', async (route) => {
    const response = await route.fetch()
    expect(response.status()).toBe(200)
    expect(await response.json()).toMatchObject({
      results: [{ status: 'applied', entity_version: 1 }],
    })
    ackHeld = true
    await ackGate
    await route.fulfill({ response })
  })
  try {
    await page.getByLabel('Nombre', { exact: true }).fill(name)
    await page.getByRole('button', { name: 'Guardar cliente', exact: true }).click()
    await waitForJournalBarrier(page)
    await expect(page.getByLabel('Estado de sincronización')).toContainText('Sincronizado')
    await expect(page.getByRole('button', { name: 'Guardando…', exact: true })).toBeDisabled()
    expect(
      (await kernelSnapshot(page)).journal.some(
        (item) => item.envelope.payload.display_name === name,
      ),
    ).toBe(true)
    expect(await pendingMutationCount(page)).toBe(1)
    await expect(readyCustomer(page, name, 250)).rejects.toThrow('Cliente guardado localmente')
    await releaseJournalCompletion(page)
    await expect.poll(() => ackHeld).toBe(true)
    expect(await pendingMutationCount(page)).toBe(1)
    await expect(readyCustomer(page, name, 250)).rejects.toThrow('matching immutable operation')
    releaseAck()
    const original = await readyCustomer(page, name)
    expect((await kernelSnapshot(page)).journal).toContainEqual(original)
    expect(await pendingMutationCount(page)).toBe(0)
  } finally {
    await releaseJournalCompletion(page)
    releaseAck()
    await page.unrouteAll({ behavior: 'wait' })
  }
})

test('large reconnect batch keeps every valid operation when one mutation conflicts', async ({
  page,
  request,
}) => {
  const identity = await createCaseIdentity(request)
  await login(page, identity)
  const runId = crypto.randomUUID()
  await page.context().setOffline(true)
  const a = await createCustomer(page, `Cliente Lote Valido A ${runId}`)
  const collision = await createCustomer(page, `Cliente Lote Colisión ${runId}`)
  const b = await createCustomer(page, `Cliente Lote Valido B ${runId}`)
  expect(await pendingMutationCount(page)).toBe(3)
  const token = await sessionToken(page)
  const winning = `Cliente Lote Remoto ${runId}`
  const remote = await strictPush(request, token, [
    {
      ...collision.envelope,
      mutation_id: crypto.randomUUID(),
      payload: { display_name: winning },
    },
  ])
  expect(remote.results[0]?.status).toBe('applied')
  const batches: MutationEnvelope[][] = []
  page.on('request', (request) => {
    if (new URL(request.url()).pathname === '/api/v1/sync/mutations')
      batches.push((request.postDataJSON() as { mutations: MutationEnvelope[] }).mutations)
  })
  await page.context().setOffline(false)
  await waitForApplied(page, a.mutationId)
  await waitForApplied(page, b.mutationId)
  await waitForConfirmed(page, a)
  await waitForConfirmed(page, b)
  await expect(page.getByLabel('Estado de sincronización')).toContainText('Requiere atención')
  const snapshot = await kernelSnapshot(page)
  expect(snapshot.journal).toEqual([a, collision, b])
  expect(snapshot.delivery.find((item) => item.mutationId === collision.mutationId)?.state).toBe(
    'rejected',
  )
  expect(
    batches.some((batch) =>
      [a, collision, b].every((operation) =>
        batch.some((item) => item.mutation_id === operation.mutationId),
      ),
    ),
  ).toBe(true)
  expect(
    snapshot.records.find((item) => item.entityId === collision.entityId)?.payload.display_name,
  ).toBe(winning)
  for (const operation of [a, b]) {
    const response = await request.get(`/api/v1/customers/${operation.entityId}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    expect(response.status()).toBe(200)
    expect(await response.json()).toMatchObject({
      display_name: operation.envelope.payload.display_name,
      version: 1,
    })
  }
  await expect(
    page
      .locator('section[aria-labelledby="conflict-center-title"]')
      .getByText(/customer already exists/),
  ).toBeVisible()
})

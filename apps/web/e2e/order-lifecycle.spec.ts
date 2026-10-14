import { expect, test } from '@playwright/test'
import {
  createCaseIdentity,
  createCustomer,
  holdJournalCompletion,
  kernelSnapshot,
  login,
  pendingMutationCount,
  releaseJournalCompletion,
  revealOrder,
  sessionToken,
  waitForApplied,
  waitForConfirmed,
  waitForJournalBarrier,
  waitForReady,
  writeHeaders,
} from './helpers/authenticated-workshop.js'
import { appliedOrder, fillIntake, savedOrder } from './helpers/orders.js'

test('order lifecycle: offline intake, transitions, conflict and convergence', async ({
  page,
  request,
  browser,
}) => {
  const identity = await createCaseIdentity(request)
  await login(page, identity)
  const runId = crypto.randomUUID()
  const problem = `Falla de frenos delanteros ${runId}`
  const token = await sessionToken(page)
  const customer = await createCustomer(page, `Cliente Orden E2E ${runId}`)
  await waitForApplied(page, customer.mutationId)
  await waitForConfirmed(page, customer)

  // Both inline bicycle and order are authored together, with durable dependency.
  await page.context().setOffline(true)
  await fillIntake(page, customer.entityId, problem)
  await page.getByRole('button', { name: 'Guardar orden', exact: true }).click()
  const originalOrder = await savedOrder(page, problem)
  const intake = await kernelSnapshot(page)
  const bicycle = intake.journal.find((item) => item.entityType === 'bicycle')!
  expect(bicycle).toBeDefined()
  expect(originalOrder.dependsOn).toContain(bicycle.mutationId)
  expect(originalOrder.envelope.payload.bicycle_id).toBe(bicycle.entityId)
  expect(bicycle.envelope.payload.customer_id).toBe(customer.entityId)
  expect(await pendingMutationCount(page)).toBe(2)
  const card = page.getByRole('listitem', { name: `Orden ${problem}`, exact: true })
  await expect(card.getByText('Recibida', { exact: true })).toBeVisible()
  await page.reload({ waitUntil: 'domcontentloaded' })
  await waitForReady(page)
  await revealOrder(page, problem)
  await expect(card.getByText('Recibida', { exact: true })).toBeVisible()
  expect((await kernelSnapshot(page)).journal).toEqual(intake.journal)
  await page.context().setOffline(false)
  await waitForApplied(page, bicycle.mutationId)
  await waitForApplied(page, originalOrder.mutationId)
  await waitForConfirmed(page, originalOrder)
  const server = await request.get(`/api/v1/service-orders/${originalOrder.entityId}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  expect(server.status()).toBe(200)
  expect(await server.json()).toMatchObject({
    order_id: originalOrder.entityId,
    customer_id: customer.entityId,
    bicycle_id: bicycle.entityId,
    reported_problem: problem,
    intake_condition: 'Manubrio rayado',
    accessories: 'Canasto',
    priority: 'high',
    state: 'INTAKE',
    version: 1,
  })

  await page.context().setOffline(true)
  await revealOrder(page, problem)
  await card.getByRole('button', { name: 'Iniciar diagnóstico', exact: true }).click()
  await expect(page.locator('.order-actions button:disabled')).toHaveCount(0)
  await revealOrder(page, problem)
  await expect(card.getByText('En diagnóstico', { exact: true })).toBeVisible()
  await page.reload({ waitUntil: 'domcontentloaded' })
  await waitForReady(page)
  await revealOrder(page, problem)
  await expect(card.getByText('En diagnóstico', { exact: true })).toBeVisible()
  for (const action of ['start_diagnosis', 'authorize']) {
    const remote = await request.post(
      `/api/v1/service-orders/${originalOrder.entityId}/transitions`,
      {
        headers: await writeHeaders(request, token),
        data: { action },
      },
    )
    expect(remote.status(), await remote.text()).toBe(200)
  }
  await card.getByRole('button', { name: 'Autorizar', exact: true }).click()
  await expect(page.locator('.order-actions button:disabled')).toHaveCount(0)
  await revealOrder(page, problem)
  await expect(card.getByText('Autorizada', { exact: true })).toBeVisible()
  const beforeConflict = await kernelSnapshot(page)
  const transitions = beforeConflict.journal.filter(
    (item) => item.entityId === originalOrder.entityId && item.envelope.operation === 'update',
  )
  expect(transitions).toHaveLength(2)
  expect(transitions.map((item) => item.envelope.base_version)).toEqual([1, 2])
  await page.context().setOffline(false)
  await expect(page.getByLabel('Estado de sincronización')).toContainText('Requiere atención')
  const center = page.locator('section[aria-labelledby="conflict-center-title"]')
  await expect(
    center
      .getByRole('listitem')
      .filter({ hasText: originalOrder.entityId })
      .first()
      .getByText(/base version/),
  ).toBeVisible()
  await waitForConfirmed(page, originalOrder, 3)
  const after = await kernelSnapshot(page)
  expect(after.journal).toEqual(beforeConflict.journal)
  expect(after.delivery.find((item) => item.mutationId === transitions[0]!.mutationId)?.state).toBe(
    'rejected',
  )
  expect(after.delivery.find((item) => item.mutationId === transitions[1]!.mutationId)?.state).toBe(
    'held_dependency',
  )
  expect(
    after.records.find((item) => item.entityId === originalOrder.entityId)?.payload.state,
  ).toBe('AUTHORIZED')
  await revealOrder(page, problem)
  await expect(card.getByText('Autorizada', { exact: true })).toBeVisible()
  const events = await request.get(`/api/v1/service-orders/${originalOrder.entityId}/events`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  expect(events.status()).toBe(200)
  expect(((await events.json()) as Array<{ action: string }>).map((event) => event.action)).toEqual(
    ['start_diagnosis', 'authorize'],
  )
  await card.getByRole('button', { name: 'Ver historial', exact: true }).click()
  await expect(card.locator('.order-history')).toBeVisible()

  const second = await browser.newContext()
  try {
    const other = await second.newPage()
    await login(other, identity)
    const confirmed = (await kernelSnapshot(other)).records.find(
      (item) => item.entityId === originalOrder.entityId,
    )
    expect(confirmed).toMatchObject({
      version: 3,
      payload: {
        state: 'AUTHORIZED',
        bicycle_id: bicycle.entityId,
        customer_id: customer.entityId,
      },
    })
  } finally {
    await second.close()
  }
})

test('order baseline rejects stale synced state, withheld create and withheld acknowledgement', async ({
  page,
  request,
}) => {
  const identity = await createCaseIdentity(request)
  await login(page, identity)
  const runId = crypto.randomUUID()
  const problem = `Orden barrera ${runId}`
  const token = await sessionToken(page)
  const customer = await createCustomer(page, `Cliente barrera orden ${runId}`)
  await waitForApplied(page, customer.mutationId)
  await waitForConfirmed(page, customer)
  await expect(page.getByLabel('Estado de sincronización')).toContainText('Sincronizado')
  await fillIntake(page, customer.entityId, problem)
  await holdJournalCompletion(page, {
    entityType: 'service_order',
    payloadKey: 'reported_problem',
    value: problem,
  })
  let releaseCreate = () => {},
    releaseAck = () => {}
  const createGate = new Promise<void>((resolve) => {
    releaseCreate = resolve
  })
  const ackGate = new Promise<void>((resolve) => {
    releaseAck = resolve
  })
  let requestHeld = false,
    ackHeld = false
  await page.route('**/api/v1/sync/mutations', async (route) => {
    const body = route.request().postDataJSON() as { mutations: Array<{ entity_type: string }> }
    if (!body.mutations.some((item) => item.entity_type === 'service_order'))
      return route.continue()
    requestHeld = true
    await createGate
    const response = await route.fetch()
    expect(response.status()).toBe(200)
    ackHeld = true
    await ackGate
    await route.fulfill({ response })
  })
  try {
    await page.getByRole('button', { name: 'Guardar orden', exact: true }).click()
    await waitForJournalBarrier(page)
    const snapshot = await kernelSnapshot(page)
    const order = snapshot.journal.find(
      (item) => item.envelope.payload.reported_problem === problem,
    )!
    const bike = snapshot.journal.find((item) => item.entityType === 'bicycle')!
    expect(order).toBeDefined()
    expect(bike).toBeDefined()
    expect(order.dependsOn).toContain(bike.mutationId)
    expect(await pendingMutationCount(page)).toBe(2)
    await expect(page.getByLabel('Estado de sincronización')).toContainText('Sincronizado')
    await expect(appliedOrder(page, problem, 250)).rejects.toThrow('Orden guardada localmente')
    await releaseJournalCompletion(page)
    await expect.poll(() => requestHeld).toBe(true)
    const absent = await request.get(`/api/v1/service-orders/${order.entityId}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    expect(absent.status()).toBe(404)
    await expect(appliedOrder(page, problem, 250)).rejects.toThrow('matching immutable operation')
    releaseCreate()
    await expect.poll(() => ackHeld).toBe(true)
    const applied = await request.get(`/api/v1/service-orders/${order.entityId}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    expect(applied.status()).toBe(200)
    expect(
      (await kernelSnapshot(page)).delivery.find((item) => item.mutationId === order.mutationId)
        ?.state,
    ).toBe('inflight')
    await expect(appliedOrder(page, problem, 250)).rejects.toThrow('matching immutable operation')
    releaseAck()
    expect((await appliedOrder(page, problem)).mutationId).toBe(order.mutationId)
    expect((await kernelSnapshot(page)).journal).toContainEqual(order)
  } finally {
    await releaseJournalCompletion(page)
    releaseCreate()
    releaseAck()
    await page.unrouteAll({ behavior: 'wait' })
  }
})

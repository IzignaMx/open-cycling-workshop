import { expect, test } from '@playwright/test'
import {
  apiLogin,
  createCaseIdentity,
  createCustomer,
  kernelSnapshot,
  login,
  revealOrder,
  sessionToken,
  waitForApplied,
  waitForConfirmed,
  waitForReady,
  writeHeaders,
} from './helpers/authenticated-workshop.js'
import { appliedOrder, fillIntake } from './helpers/orders.js'

const READ_ONLY = ['customers.read', 'bicycles.read', 'orders.read', 'sync.pull']

test.describe.configure({ retries: 0 })

// Prueba sintética de relevo; la cuenta de consulta no representa el rol Mechanic completo.
test('reception and an independent reader see the same confirmed order without writing a diagnosis', async ({
  page: reception,
  browser,
  request,
}) => {
  test.setTimeout(120_000)
  const owner = await apiLogin(request, 'e2e-owner')
  const location = await request.post('/api/v1/locations', {
    headers: await writeHeaders(request, owner),
    data: { name: `Synthetic reception readback ${crypto.randomUUID()}` },
  })
  expect(location.status()).toBe(201)
  const locationId = ((await location.json()) as { location_id: string }).location_id
  const writer = await createCaseIdentity(request, { locationId })
  const reader = await createCaseIdentity(request, { locationId, capabilities: READ_ONLY })
  expect(reader.userId).not.toBe(writer.userId)

  await login(reception, writer)
  const problem = 'El cliente reporta ruido al frenar'
  const customerName = 'Cliente sintético de recepción'
  const customer = await createCustomer(reception, customerName)
  await waitForApplied(reception, customer.mutationId)
  await waitForConfirmed(reception, customer)
  await fillIntake(reception, customer.entityId, problem)
  await reception.getByRole('button', { name: 'Guardar orden', exact: true }).click()
  const order = await appliedOrder(reception, problem)
  await revealOrder(reception, problem)
  const receptionCard = reception.getByRole('listitem', { name: `Orden ${problem}`, exact: true })
  await expect(
    receptionCard.getByText(`Orden · ${order.entityId.slice(-8)}`, { exact: true }),
  ).toBeVisible()
  await expect(receptionCard.getByText('Recibida', { exact: true })).toBeVisible()
  const source = await kernelSnapshot(reception)
  const bicycles = source.journal.filter((row) => row.entityType === 'bicycle')
  expect(bicycles).toHaveLength(1)
  const bicycle = bicycles[0]
  if (!bicycle) throw new Error('Falta la bicicleta creada en recepción.')
  expect(order.dependsOn).toContain(bicycle.mutationId)
  expect(source.journal.filter((row) => row.entityType === 'service_order')).toHaveLength(1)
  const expected = {
    order_id: order.entityId,
    customer_id: customer.entityId,
    bicycle_id: bicycle.entityId,
    location_id: locationId,
    reported_problem: problem,
    intake_condition: 'Manubrio rayado',
    accessories: 'Canasto',
    diagnosis: null,
    state: 'INTAKE',
    priority: 'high',
    version: 1,
  }

  // Un contexto nuevo obtiene una línea base propia: no comparte sesión o IndexedDB.
  const readerContext = await browser.newContext({
    baseURL: new URL(reception.url()).origin,
    viewport: { width: 800, height: 1200 },
    hasTouch: true,
  })
  try {
    const consultation = await readerContext.newPage()
    await login(consultation, reader)
    const readerToken = await sessionToken(consultation)
    const sourceToken = await sessionToken(reception)
    expect(readerToken !== sourceToken).toBe(true)
    const assertServerRead = async () => {
      const response = await request.get(`/api/v1/service-orders/${order.entityId}`, {
        headers: { Authorization: `Bearer ${readerToken}` },
      })
      expect(response.status()).toBe(200)
      expect(await response.json()).toMatchObject(expected)
    }
    const assertReaderView = async () => {
      const snapshot = await kernelSnapshot(consultation)
      expect(snapshot.context.principal.userId).toBe(reader.userId)
      expect(snapshot.context.selectedLocationId).toBe(locationId)
      expect(snapshot.context.datasetIncarnation).toBe(source.context.datasetIncarnation)
      expect([...snapshot.context.capabilities].sort()).toEqual([...READ_ONLY].sort())
      expect(snapshot.journal).toHaveLength(0)
      const record = snapshot.records.filter(
        (row) => row.entityType === 'service_order' && row.entityId === order.entityId,
      )
      expect(record).toHaveLength(1)
      expect(record[0]?.payload).toMatchObject(expected)
      await revealOrder(consultation, problem)
      const card = consultation.getByRole('listitem', { name: `Orden ${problem}`, exact: true })
      await expect(
        card.getByText(`Orden · ${order.entityId.slice(-8)}`, { exact: true }),
      ).toBeVisible()
      await expect(card.getByText(problem, { exact: true })).toBeVisible()
      await expect(card.getByText('Recibida', { exact: true })).toBeVisible()
      await expect(card.getByText('Solo lectura:', { exact: false })).toBeVisible()
      const details = card.locator('.order-intake-details')
      await details.locator('summary').click()
      await expect(details.getByText('Condición al recibir', { exact: true })).toBeVisible()
      await expect(details.getByText(expected.intake_condition, { exact: true })).toBeVisible()
      await expect(details.getByText(expected.accessories, { exact: true })).toBeVisible()
      await expect(details.getByText(problem, { exact: true })).toHaveCount(0)
      await card.getByRole('button', { name: 'Ver cliente y bicicleta', exact: true }).click()
      const associations = card.locator('.order-associations')
      for (const value of [customerName, customer.entityId, 'Trek Marlin', '7', bicycle.entityId]) {
        await expect(associations.getByText(value, { exact: true })).toBeVisible()
      }
      expect((await kernelSnapshot(consultation)).journal).toHaveLength(0)
    }
    await assertServerRead()
    await assertReaderView()
    await consultation.reload({ waitUntil: 'domcontentloaded' })
    await waitForReady(consultation)
    await assertReaderView()
    await assertServerRead()
    expect((await sessionToken(reception)) === sourceToken).toBe(true)
    expect((await kernelSnapshot(reception)).journal).toEqual(source.journal)
  } finally {
    await readerContext.close()
  }
})

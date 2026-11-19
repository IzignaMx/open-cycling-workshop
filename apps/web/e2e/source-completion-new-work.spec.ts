import { captureResponseDuring } from './helpers/response-capture.js'
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
import { appliedOrder, fillIntake } from './helpers/orders.js'
import { captureSnapshot } from './helpers/capture-snapshot.js'

const DESTINATION = 'http://127.0.0.1:5175'
const STORED = 'Borrador guardado para recuperar al recargar esta sesión.'
const orderForm = (page: Page) => page.locator('form[aria-describedby~="order-intake-status"]')

// Retain successful causal evidence too, not only failed native runs.
test.use({ trace: 'on' })

// This is connected source completion and genuinely new authoring, NOT migration,
// retirement of A, production-origin selection, or safety for unknown outcomes.
test('resolve an unsent source capture then author distinct new work at another origin', async ({
  page: source,
  context,
  request,
}, info) => {
  test.setTimeout(120_000)
  const owner = await apiLogin(request, 'e2e-owner')
  const location = await request.post('/api/v1/locations', {
    headers: await writeHeaders(request, owner),
    data: { name: `Synthetic source completion ${crypto.randomUUID()}` },
  })
  expect(location.status()).toBe(201)
  const locationId = ((await location.json()) as { location_id: string }).location_id
  const identity = await createCaseIdentity(request, { locationId })
  await login(source, identity)
  const sourceOrigin = new URL(source.url()).origin
  expect(sourceOrigin).not.toBe(DESTINATION)
  await source.evaluate(() => navigator.serviceWorker.ready)
  await expect
    .poll(() => source.evaluate(() => Boolean(navigator.serviceWorker.controller)))
    .toBe(true)
  const customer = await createCustomer(source, `Synthetic source customer ${crypto.randomUUID()}`)
  await waitForApplied(source, customer.mutationId)
  await waitForConfirmed(source, customer)
  const sourceProblem = `Source capture ${crypto.randomUUID()}`
  const destinationProblem = `New destination work ${crypto.randomUUID()}`
  await fillIntake(source, customer.entityId, sourceProblem, false)
  await expect(orderForm(source).getByText(STORED, { exact: true })).toBeVisible()
  await expect
    .poll(async () =>
      (await captureSnapshot(source)).contents.some(
        (row) => row.channel === 'order' && row.draft.reportedProblem === sourceProblem,
      ),
    )
    .toBe(true)
  const unsent = await captureSnapshot(source)
  const draft = unsent.contents.find((row) => row.channel === 'order')!
  expect(draft).toBeDefined()
  expect(
    unsent.checkpoints.find((row) => row.checkpointId === draft.checkpointId)?.order.state,
  ).toBe('UNSENT')
  expect(draft.expiresAt - draft.firstPersistedAt).toBe(86_400_000)
  const beforeReload = await kernelSnapshot(source)
  expect(beforeReload.journal).toHaveLength(1)
  await source.reload()
  await waitForReady(source)
  await expect(orderForm(source)).toHaveAttribute('data-dirty', 'true')
  await expect(source.getByLabel('Problema reportado')).toHaveValue(sourceProblem)
  await expect(source.getByLabel('Condición al recibir')).toHaveValue('Manubrio rayado')
  await expect(source.getByLabel('Accesorios', { exact: true })).toHaveValue('Canasto')
  await expect(source.getByRole('combobox', { name: 'Cliente', exact: true })).toHaveValue(
    customer.entityId,
  )
  await expect(source.getByLabel('Agregar bicicleta')).not.toBeChecked()
  const restored = await captureSnapshot(source)
  expect(restored).toEqual(unsent)
  expect((await kernelSnapshot(source)).journal).toEqual(beforeReload.journal)
  await source.getByRole('button', { name: 'Guardar orden', exact: true }).click()
  const sourceOrder = await appliedOrder(source, sourceProblem)
  const token = await sessionToken(source)
  const assertServerContext = async (page: Page, session: string) => {
    const url = new URL('/api/v1/auth/context', page.url())
    url.searchParams.set('selected_location_id', locationId)
    const response = await request.get(url.href, {
      headers: { Authorization: `Bearer ${session}` },
    })
    expect(response.status()).toBe(200)
    const server = (await response.json()) as {
      principal: { organization_id: string; user_id: string }
      selected_location_id: string
      dataset_incarnation: string
      authorization_epoch: string
      policy_revision: string
    }
    const local = (await kernelSnapshot(page)).context
    expect(server.principal.organization_id).toBe(local.principal.organizationId)
    expect(server.principal.user_id).toBe(identity.userId)
    expect(server.principal.user_id).toBe(local.principal.userId)
    expect(server.selected_location_id).toBe(locationId)
    expect(server.selected_location_id).toBe(local.selectedLocationId)
    expect(server.dataset_incarnation).toBe(local.datasetIncarnation)
    expect(server.authorization_epoch).toBe(local.authorizationEpoch)
    expect(server.policy_revision).toBe(local.policyRevision)
    expect(local.principal.apiRealm).toBe(new URL('/api/v1', page.url()).href)
  }
  await assertServerContext(source, token)
  const assertServerOrder = async (id: string, problem: string) => {
    const response = await request.get(`/api/v1/service-orders/${id}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    expect(response.status()).toBe(200)
    expect(await response.json()).toMatchObject({
      order_id: id,
      customer_id: customer.entityId,
      bicycle_id: null,
      location_id: locationId,
      reported_problem: problem,
      intake_condition: 'Manubrio rayado',
      accessories: 'Canasto',
      priority: 'high',
      version: 1,
    })
  }
  await assertServerOrder(sourceOrder.entityId, sourceProblem)
  await expect(orderForm(source)).toHaveAttribute('data-dirty', 'false')
  await expect(source.getByLabel('Problema reportado')).toHaveValue('')
  const sourceCompleted = await kernelSnapshot(source)
  expect(sourceCompleted.journal).toHaveLength(2)
  expect(sourceCompleted.delivery.every((row) => row.state === 'applied')).toBe(true)
  // Clean retained defaults may remain UNSENT by contract; no purge/EMPTY claim.
  await expect(orderForm(source).getByText(STORED, { exact: true })).toBeVisible()
  const sourceCaptureCompleted = await captureSnapshot(source)
  expect(
    sourceCaptureCompleted.contents.some(
      (row) => row.channel === 'order' && row.draft.reportedProblem === sourceProblem,
    ),
  ).toBe(false)

  const destination = await context.newPage()
  await destination.goto(DESTINATION)
  expect(await destination.evaluate(() => sessionStorage.getItem('ocwp.session.v2'))).toBeNull()
  const destinationLogin = destination.waitForResponse(
    (response) =>
      response.url() === `${DESTINATION}/api/v1/auth/login` &&
      response.request().method() === 'POST',
  )
  const issued = await captureResponseDuring(
    destinationLogin,
    () => login(destination, identity, undefined, 'synced', DESTINATION),
    async (loginResponse) => {
      expect(loginResponse.status()).toBe(200)
      const body: unknown = await loginResponse.json()
      // Fail closed without including a token or arbitrary body in assertions.
      const valid =
        typeof body === 'object' &&
        body !== null &&
        'access_token' in body &&
        typeof body.access_token === 'string' &&
        body.access_token.trim().length > 0
      expect(valid).toBe(true)
      return body as { access_token: string }
    },
  )
  const destinationToken = await sessionToken(destination)
  // Only booleans reach assertions/receipt; never print bearer values.
  expect(destinationToken === issued.access_token).toBe(true)
  expect(destinationToken !== token).toBe(true)
  expect((await sessionToken(source)) === token).toBe(true)
  await assertServerContext(destination, destinationToken)
  expect(new URL(destination.url()).origin).toBe(DESTINATION)
  await destination.evaluate(() => navigator.serviceWorker.ready)
  await expect
    .poll(() => destination.evaluate(() => Boolean(navigator.serviceWorker.controller)))
    .toBe(true)
  const sourceModule = await source.locator('script[type="module"][src]').getAttribute('src')
  expect(sourceModule).toMatch(/^\/assets\/index-.*\.js$/)
  expect(await destination.locator('script[type="module"][src]').getAttribute('src')).toBe(
    sourceModule,
  )
  for (const asset of [sourceModule!, '/sw.js']) {
    const [a, b] = await Promise.all([
      request.get(`${sourceOrigin}${asset}`),
      request.get(`${DESTINATION}${asset}`),
    ])
    expect(a.status()).toBe(200)
    expect(b.status()).toBe(200)
    expect(await b.body()).toEqual(await a.body())
  }
  const destinationBefore = await kernelSnapshot(destination)
  expect(destinationBefore.journal).toEqual([])
  expect(destinationBefore.delivery).toEqual([])
  expect(destinationBefore.events).toEqual([])
  expect(destinationBefore.context.principal.organizationId).toBe(
    sourceCompleted.context.principal.organizationId,
  )
  expect(destinationBefore.context.principal.userId).toBe(sourceCompleted.context.principal.userId)
  expect(destinationBefore.context.principal.apiRealm).not.toBe(
    sourceCompleted.context.principal.apiRealm,
  )
  expect(destinationBefore.context.selectedLocationId).toBe(locationId)
  expect(destinationBefore.context.datasetIncarnation).toBe(
    sourceCompleted.context.datasetIncarnation,
  )
  expect(
    destinationBefore.records.find((row) => row.entityId === sourceOrder.entityId)?.payload,
  ).toMatchObject({ reported_problem: sourceProblem })
  const destinationCaptureBefore = await captureSnapshot(destination)
  expect(destinationCaptureBefore.contents).toEqual([])
  expect(
    destinationCaptureBefore.checkpoints.every(
      (row) => row.customer.state === 'EMPTY' && row.order.state === 'EMPTY',
    ),
  ).toBe(true)
  for (const row of destinationCaptureBefore.checkpoints)
    expect(
      unsent.checkpoints.some(
        (old) => old.checkpointId === row.checkpointId || old.generation === row.generation,
      ),
    ).toBe(false)
  await expect(destination.getByLabel('Problema reportado')).toHaveValue('')
  await expect(orderForm(destination)).toHaveAttribute('data-dirty', 'false')
  await fillIntake(destination, customer.entityId, destinationProblem, false)
  await destination.getByRole('button', { name: 'Guardar orden', exact: true }).click()
  const destinationOrder = await appliedOrder(destination, destinationProblem)
  expect(destinationOrder.entityId).not.toBe(sourceOrder.entityId)
  expect(destinationOrder.mutationId).not.toBe(sourceOrder.mutationId)
  expect(destinationOrder.authoredDatasetIncarnation).toBe(sourceOrder.authoredDatasetIncarnation)
  await assertServerOrder(destinationOrder.entityId, destinationProblem)
  const destinationAfter = await kernelSnapshot(destination)
  expect(destinationAfter.journal).toEqual([destinationOrder])
  expect(destinationAfter.delivery).toHaveLength(1)
  expect(destinationAfter.delivery[0]?.state).toBe('applied')
  await source.reload()
  await waitForReady(source)
  await waitForConfirmed(source, sourceOrder)
  const sourceAfter = await kernelSnapshot(source)
  expect(sourceAfter.journal).toEqual(sourceCompleted.journal)
  expect(sourceAfter.delivery).toEqual(sourceCompleted.delivery)
  expect(await captureSnapshot(source)).toEqual(sourceCaptureCompleted)
  await assertServerOrder(sourceOrder.entityId, sourceProblem)
  await assertServerOrder(destinationOrder.entityId, destinationProblem)
  const listing = await request.get(
    `/api/v1/sync/changes?cursor=0&location_id=${locationId}&limit=100`,
    {
      headers: { Authorization: `Bearer ${token}` },
    },
  )
  expect(listing.status()).toBe(200)
  const changes = (await listing.json()) as {
    items: {
      entity_id: string
      entity_type: string
      operation: string
      entity_version: number
      location_id: string
    }[]
    has_more: boolean
  }
  expect(changes.has_more).toBe(false)
  expect(changes.items.every((row) => row.location_id === locationId)).toBe(true)
  const orders = changes.items.filter((row) => row.entity_type === 'service_order')
  expect(orders.every((row) => row.operation === 'create' && row.entity_version === 1)).toBe(true)
  expect(orders.map((row) => row.entity_id).sort()).toEqual(
    [sourceOrder.entityId, destinationOrder.entityId].sort(),
  )
  await info.attach('source-completion-new-work-receipt', {
    body: JSON.stringify({
      observedAt: new Date().toISOString(),
      sourceOrigin,
      destinationOrigin: DESTINATION,
      sourceCheckpointId: draft.checkpointId,
      originalExpiry: draft.expiresAt,
      restoredPayloadAndIdentityExact: true,
      sourceOrderId: sourceOrder.entityId,
      sourceMutationId: sourceOrder.mutationId,
      destinationOrderId: destinationOrder.entityId,
      destinationMutationId: destinationOrder.mutationId,
      independentlyIssuedDestinationSession: true,
      serverContextMatchesKernel: true,
      destinationInitialLocalJournal: 0,
      destinationInitialCaptureContents: 0,
      sourceJournalPreserved: true,
      serverOrderCreationCount: orders.length,
      migration: 'not_performed',
      activation: 'not_assessed',
      oldWriterExclusion: 'not_claimed',
    }),
    contentType: 'application/json',
  })
})

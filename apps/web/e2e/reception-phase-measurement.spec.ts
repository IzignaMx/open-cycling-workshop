import { expect, test } from '@playwright/test'
import { captureSnapshot } from './helpers/capture-snapshot.js'
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
import {
  buildReceipt,
  phaseDuration,
  type ReceptionSample,
  type ReceptionFailure,
} from './helpers/reception-measurement.js'

// No retry selection, warmup discard, fake clock, latency SLA or local-browser bypass.
test.describe.configure({ retries: 0 })
test.use({ trace: 'on' })
test('measure three verified App receptions by durable and server boundaries', async ({
  page,
  request,
  browser,
}, info) => {
  test.setTimeout(180_000)
  const owner = await apiLogin(request, 'e2e-owner')
  const createdLocation = await request.post('/api/v1/locations', {
    headers: await writeHeaders(request, owner),
    data: { name: `Synthetic reception measurement ${crypto.randomUUID()}` },
  })
  expect(createdLocation.status()).toBe(201)
  const locationId = ((await createdLocation.json()) as { location_id: string }).location_id
  const identity = await createCaseIdentity(request, { locationId })
  await login(page, identity)
  await page.evaluate(() => navigator.serviceWorker.ready)
  await expect
    .poll(() => page.evaluate(() => Boolean(navigator.serviceWorker.controller)))
    .toBe(true)
  const artifact = await page.evaluate(async () => {
    const module = document.querySelector<HTMLScriptElement>('script[type="module"][src]')?.src
    if (!module) throw new Error('Missing observed App module')
    const digest = async (url: string) => {
      const response = await fetch(url)
      if (!response.ok) throw new Error('Artifact not available')
      return [
        ...new Uint8Array(await crypto.subtle.digest('SHA-256', await response.arrayBuffer())),
      ]
        .map((value) => value.toString(16).padStart(2, '0'))
        .join('')
    }
    return { appSha256: await digest(module), swSha256: await digest('/sw.js') }
  })
  const customer = await createCustomer(page, `Synthetic measured customer ${crypto.randomUUID()}`)
  await waitForApplied(page, customer.mutationId)
  await waitForConfirmed(page, customer)
  const token = await sessionToken(page)
  const counts = async () => {
    const snapshot = await kernelSnapshot(page)
    return {
      customers: snapshot.records.filter((row) => row.entityType === 'customer').length,
      bicycles: snapshot.records.filter((row) => row.entityType === 'bicycle').length,
      orders: snapshot.records.filter((row) => row.entityType === 'service_order').length,
    }
  }
  const datasetBefore = await counts()
  expect(datasetBefore).toEqual({ customers: 1, bicycles: 0, orders: 0 })
  const samples: ReceptionSample[] = []
  let datasetAfter: typeof datasetBefore | null = null
  await info.attach('reception-measurement-context', {
    body: JSON.stringify({
      browserVersion: browser.version(),
      viewport: page.viewportSize(),
      origin: new URL(page.url()).origin,
      nativeProject: info.project.name,
      deviceUnderTest: 'hosted_or_local_authorized_runner_not_LIBERTAD',
      network: 'connected_loopback_no_throttling',
      concurrency: 1,
      setupLoginAndCustomerCreationExcluded: true,
      trialOrder: [1, 2, 3],
      coldStart: 'not_measured',
      timingIncludes: 'driver_polling_and_assertion_observation',
    }),
    contentType: 'application/json',
  })
  try {
    for (let trial = 1; trial <= 3; trial += 1) {
      const phases: ReceptionSample['phases'] = {}
      let stage: ReceptionFailure = 'draftDurable'
      let identities:
        | { orderId: string; bicycleId: string; orderMutationId: string; bicycleMutationId: string }
        | undefined
      try {
        const problem = `Measured reception ${trial} ${crypto.randomUUID()}`
        // Untimed earlier fields; the final problem edit is the draft boundary.
        await fillIntake(page, customer.entityId, 'Preparation before final edit', true)
        const draftStart = performance.now()
        await page.getByLabel('Problema reportado').fill(problem)
        await expect
          .poll(async () =>
            (await captureSnapshot(page)).contents.some(
              (row) =>
                row.channel === 'order' &&
                row.draft.reportedProblem === problem &&
                row.draft.brand === 'Trek Marlin' &&
                row.draft.model === '7' &&
                row.draft.withBicycle,
            ),
          )
          .toBe(true)
        const original = await captureSnapshot(page)
        const draft = original.contents.find((row) => row.channel === 'order')!
        expect(
          original.checkpoints.find((row) => row.checkpointId === draft.checkpointId)?.order.state,
        ).toBe('UNSENT')
        phases.draftDurable = phaseDuration(draftStart, performance.now())
        const before = await kernelSnapshot(page)
        expect(before.journal).toHaveLength(1 + (trial - 1) * 2)

        stage = 'reloadRecovered'
        const reloadStart = performance.now()
        await page.reload()
        await waitForReady(page)
        await expect(page.getByLabel('Problema reportado')).toHaveValue(problem)
        await expect(page.getByLabel('Marca', { exact: true })).toHaveValue('Trek Marlin')
        await expect(page.getByLabel('Modelo', { exact: true })).toHaveValue('7')
        expect(await captureSnapshot(page)).toEqual(original)
        expect((await kernelSnapshot(page)).journal).toEqual(before.journal)
        phases.reloadRecovered = phaseDuration(reloadStart, performance.now())

        stage = 'localCommit'
        const submitStart = performance.now()
        await page.getByRole('button', { name: 'Guardar orden', exact: true }).click()
        // Boundary is readonly IndexedDB journal evidence, NOT the UI success label.
        await expect
          .poll(async () => {
            const current = await kernelSnapshot(page)
            const order = current.journal.find(
              (row) =>
                row.entityType === 'service_order' &&
                row.envelope.payload.reported_problem === problem,
            )
            const bicycle = current.journal.find(
              (row) =>
                row.entityType === 'bicycle' && row.entityId === order?.envelope.payload.bicycle_id,
            )
            return Boolean(order && bicycle && order.dependsOn.includes(bicycle.mutationId))
          })
          .toBe(true)
        const committed = await kernelSnapshot(page)
        const order = committed.journal.find(
          (row) =>
            row.entityType === 'service_order' && row.envelope.payload.reported_problem === problem,
        )!
        const bicycle = committed.journal.find(
          (row) =>
            row.entityType === 'bicycle' && row.entityId === order.envelope.payload.bicycle_id,
        )!
        expect(order.envelope.payload.customer_id).toBe(customer.entityId)
        expect(bicycle.envelope.payload.customer_id).toBe(customer.entityId)
        expect(committed.journal).toHaveLength(before.journal.length + 2)
        identities = {
          orderId: order.entityId,
          bicycleId: bicycle.entityId,
          orderMutationId: order.mutationId,
          bicycleMutationId: bicycle.mutationId,
        }
        phases.localCommit = phaseDuration(submitStart, performance.now())
        await expect(page.getByText('Orden guardada localmente', { exact: true })).toBeVisible()

        stage = 'serverConfirmed'
        await waitForApplied(page, bicycle.mutationId)
        await waitForApplied(page, order.mutationId)
        await waitForConfirmed(page, order)
        await waitForConfirmed(page, bicycle)
        const serverOrder = await request.get(`/api/v1/service-orders/${order.entityId}`, {
          headers: { Authorization: `Bearer ${token}` },
        })
        expect(serverOrder.status()).toBe(200)
        expect(await serverOrder.json()).toMatchObject({
          order_id: order.entityId,
          customer_id: customer.entityId,
          bicycle_id: bicycle.entityId,
          location_id: locationId,
          reported_problem: problem,
          intake_condition: 'Manubrio rayado',
          accessories: 'Canasto',
          priority: 'high',
          version: 1,
        })
        const serverBicycle = await request.get(`/api/v1/bicycles/${bicycle.entityId}`, {
          headers: { Authorization: `Bearer ${token}` },
        })
        expect(serverBicycle.status()).toBe(200)
        expect(await serverBicycle.json()).toMatchObject({
          bicycle_id: bicycle.entityId,
          customer_id: customer.entityId,
          location_id: locationId,
          brand: 'Trek Marlin',
          model: '7',
          version: 1,
        })
        phases.serverConfirmed = phaseDuration(submitStart, performance.now())
        stage = 'verification'
        expect((await kernelSnapshot(page)).journal).toEqual(committed.journal)
        samples.push({ trial, status: 'passed', phases, identities })
      } catch (error) {
        samples.push({
          trial,
          status: 'failed',
          reason: stage,
          phases,
          ...(identities ? { identities } : {}),
        })
        throw error
      }
    }
    // Complete private-location feed, never truncated counts, proves no extra creations.
    const changesResponse = await request.get(
      `/api/v1/sync/changes?cursor=0&location_id=${locationId}&limit=100`,
      { headers: { Authorization: `Bearer ${token}` } },
    )
    expect(changesResponse.status()).toBe(200)
    const changes = (await changesResponse.json()) as {
      has_more: boolean
      items: {
        entity_id: string
        entity_type: string
        operation: string
        entity_version: number
        location_id: string
      }[]
    }
    expect(changes.has_more).toBe(false)
    expect(changes.items).toHaveLength(7)
    expect(
      changes.items.every(
        (row) =>
          row.location_id === locationId && row.operation === 'create' && row.entity_version === 1,
      ),
    ).toBe(true)
    expect(changes.items.map((row) => row.entity_id).sort()).toEqual(
      [
        customer.entityId,
        ...samples.flatMap((sample) =>
          sample.status === 'passed'
            ? [sample.identities.orderId, sample.identities.bicycleId]
            : [],
        ),
      ].sort(),
    )
    datasetAfter = await counts()
    expect(datasetAfter).toEqual({ customers: 1, bicycles: 3, orders: 3 })
  } catch (error) {
    // A final global correctness failure invalidates the last completion too.
    const last = samples.at(-1)
    if (last?.status === 'passed')
      samples[samples.length - 1] = { ...last, status: 'failed', reason: 'verification' }
    throw error
  } finally {
    await info.attach('reception-attempts-raw', {
      body: JSON.stringify({ samples, datasetBefore, datasetAfter }),
      contentType: 'application/json',
    })
    await info.attach('reception-phase-measurement', {
      body: JSON.stringify(
        buildReceipt(samples, {
          browserVersion: browser.version(),
          ...artifact,
          datasetBefore,
          datasetAfter,
        }),
      ),
      contentType: 'application/json',
    })
  }
})

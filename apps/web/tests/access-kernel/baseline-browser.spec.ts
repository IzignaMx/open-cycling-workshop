import { expect, test } from '@playwright/test'
import type {} from '../../tools/kernel-browser/main.js'

// This actual-auth fixture avoids persisting live test bearer material in traces.
// Existing kernel journeys retain their original failure traces.
test.use({ trace: 'off' })

const locationId = '00000000-0000-7000-8000-000000000002'
const organizationId = '00000000-0000-7000-8000-000000000001'

test('isolated real-server null-protocol staging survives lost commit response and reload without activation', async ({
  page,
  context,
}) => {
  test.setTimeout(90_000)
  await page.goto('/')
  const name = `isolated-baseline-test-${crypto.randomUUID()}`
  const initial = await page.evaluate(
    async ({ name, locationId }) => {
      const h = await window.kernelHarness.openBaselineQualification(name)
      window.baselineQualification = h
      const customer = await h.rest('/customers', {
        location_id: locationId,
        display_name: 'Historical direct REST',
      })
      const bicycle = await h.rest('/bicycles', {
        location_id: locationId,
        customer_id: customer.customer_id,
        brand: 'Historical bike',
      })
      const order = await h.rest('/service-orders', {
        location_id: locationId,
        customer_id: customer.customer_id,
        bicycle_id: bicycle.bicycle_id,
        reported_problem: 'Historical repair',
      })
      for (let index = 0; index < 101; index += 1)
        await h.rest('/customers', { location_id: locationId, display_name: `Historical ${index}` })
      await h.seedPendingHistory(String(customer.customer_id))
      const before = await h.snapshot()
      await h.step()
      const start = await h.snapshot()
      let lost = false
      try {
        await h.step(true)
      } catch {
        lost = true
      }
      const afterLost = await h.snapshot()
      await h.step() // Exact predecessor replay from a committed real server response.
      const firstPage = await h.snapshot()
      return {
        customerId: customer.customer_id,
        bicycleId: bicycle.bicycle_id,
        orderId: order.order_id,
        before,
        start,
        lost,
        afterLost,
        firstPage,
        ordinaryRejected: h.ordinaryRejected,
        ordinaryCalls: h.ordinaryCalls,
      }
    },
    { name, locationId },
  )
  expect(initial.ordinaryRejected).toBe(true)
  expect(initial.ordinaryCalls).toBe(0)
  expect(initial.before.partition?.baseline?.phase).toBe('start_pending')
  expect(initial.before.calls).toBe(0)
  expect(initial.lost).toBe(true)
  expect(initial.afterLost.partition).toEqual(initial.start.partition)
  expect(initial.afterLost.records).toEqual([])
  expect(initial.firstPage.records.length).toBeGreaterThan(0)
  expect(initial.firstPage.requests[1]?.body).toBe(initial.firstPage.requests[2]?.body)
  await page.evaluate(
    async ({ customerId, locationId, organizationId }) => {
      await window.baselineQualification.rest('/sync/mutations', {
        mutations: [
          {
            mutation_id: crypto.randomUUID(),
            entity_type: 'customer',
            entity_id: customerId,
            operation: 'update',
            organization_id: organizationId,
            location_id: locationId,
            base_version: 1,
            occurred_at: new Date().toISOString(),
            payload: { display_name: 'Updated during scan' },
          },
        ],
      })
    },
    { customerId: initial.customerId, locationId, organizationId },
  )
  const aborted = await page.evaluate(async () => {
    const h = window.baselineQualification
    const before = await h.snapshot()
    const abort = (
      _changes: object,
      _key: unknown,
      _row: unknown,
      transaction: { abort(): void },
    ) => {
      transaction.abort()
    }
    h.db.cachePartitions.hook('updating', abort)
    let rejected = false
    try {
      await h.step()
    } catch {
      rejected = true
    }
    h.db.cachePartitions.hook('updating').unsubscribe(abort)
    return { rejected, before, after: await h.snapshot() }
  })
  expect(aborted.rejected).toBe(true)
  expect(aborted.after.partition).toEqual(aborted.before.partition)
  expect(aborted.after.records).toEqual(aborted.before.records)
  expect(aborted.after.history).toBe(initial.before.history)
  await page.evaluate(() => {
    const h = window.baselineQualification
    h.delayNextCommit()
    window.delayedBaselineResult = h.step().then(
      () => 'unexpected commit',
      () => 'fenced',
    )
  })
  await expect
    .poll(() => page.evaluate(() => window.baselineQualification.responseWaiting()))
    .toBe(true)
  const other = await context.newPage()
  await other.goto('/')
  const winner = await other.evaluate(async (name) => {
    const h = await window.kernelHarness.openBaselineQualification(name, true)
    window.baselineQualification = h
    return await h.snapshot()
  }, name)
  expect(
    await page.evaluate(async () => {
      window.baselineQualification.releaseCommit()
      const result = await window.delayedBaselineResult
      window.baselineQualification.db.close()
      return result
    }),
  ).toBe('fenced')
  const afterStale = await other.evaluate(async () => {
    const result = await window.baselineQualification.snapshot()
    window.baselineQualification.db.close()
    return result
  })
  expect(afterStale.partition).toEqual(winner.partition)
  expect(afterStale.control).toEqual(winner.control)
  expect(afterStale.history).toBe(initial.before.history)
  await other.close()
  await page.reload()
  const completed = await page.evaluate(async (name) => {
    const h = await window.kernelHarness.openBaselineQualification(name, true)
    window.baselineQualification = h
    const resumed = await h.snapshot()
    const kinds: string[] = []
    for (let index = 0; index < 30; index += 1) {
      const phase = (await h.snapshot()).partition?.baseline?.phase
      if (phase === 'activation_pending') break
      kinds.push((await h.step()).kind)
    }
    const beforeActivation = await h.snapshot()
    const activation = await h.step()
    const afterActivation = await h.snapshot()
    const reuse = await h.rejectOrdinaryReuse()
    const final = await h.snapshot()
    h.db.close()
    return { resumed, kinds, beforeActivation, activation, afterActivation, reuse, final }
  }, name)
  expect(completed.resumed.partition?.partitionId).toBe(initial.firstPage.partition?.partitionId)
  expect(completed.resumed.partition?.baseline?.requestId).toBe(
    initial.before.partition?.baseline?.requestId,
  )
  expect(completed.resumed.partition?.baseline?.origin).toEqual(
    initial.before.partition?.baseline?.origin,
  )
  expect(completed.resumed.partition?.baseline?.owner.deviceGeneration).toBeGreaterThan(
    initial.before.partition!.baseline!.owner.deviceGeneration,
  )
  expect(completed.kinds).toContain('scan')
  expect(completed.kinds).toContain('finalize')
  expect(completed.kinds).toContain('delta')
  expect(completed.beforeActivation.partition?.baseline?.phase).toBe('activation_pending')
  expect(
    completed.beforeActivation.records.find((row) => row.entityId === initial.customerId)?.payload
      .display_name,
  ).toBe('Updated during scan')
  expect(completed.beforeActivation.records.some((row) => row.entityId === initial.bicycleId)).toBe(
    true,
  )
  expect(completed.beforeActivation.records.some((row) => row.entityId === initial.orderId)).toBe(
    true,
  )
  expect(completed.activation.nullActivationRejected).toBe(true)
  expect(completed.afterActivation.partition).toEqual(completed.beforeActivation.partition)
  expect(completed.afterActivation.control?.state).toBe('CATCHING_UP')
  expect(completed.reuse).toEqual({ state: 'BASELINE_REQUIRED', denied: true })
  for (const snapshot of [
    initial.afterLost,
    initial.firstPage,
    completed.resumed,
    completed.beforeActivation,
    completed.afterActivation,
    completed.final,
  ]) {
    expect(snapshot.history).toBe(initial.before.history)
    expect(snapshot.credentialsPersisted).toBe(false)
    expect(snapshot.requests.every((request) => request.bearerMatches)).toBe(true)
  }
})

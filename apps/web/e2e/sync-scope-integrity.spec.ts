import { expect, test } from '@playwright/test'
import {
  createCaseIdentity,
  createCustomer,
  kernelSnapshot,
  login,
  partitionEvidence,
  sessionToken,
  strictPush,
  waitForApplied,
  waitForConfirmed,
  waitForReady,
} from './helpers/authenticated-workshop.js'

for (const entityType of ['bicycle', 'service_order'] as const) {
  test(`foreign ${entityType} payload rolls back the whole opaque delta page across reload`, async ({
    page,
    request,
  }) => {
    const identity = await createCaseIdentity(request)
    await login(page, identity)
    const customer = await createCustomer(page, `Original scoped customer ${crypto.randomUUID()}`)
    await waitForApplied(page, customer.mutationId)
    await waitForConfirmed(page, customer)
    await expect(page.getByLabel('Estado de sincronización')).toContainText('Sincronizado')
    await page.context().setOffline(true)
    const snapshot = await kernelSnapshot(page)
    const original = await partitionEvidence(page, snapshot.partition.partitionId)
    const entityId = crypto.randomUUID()
    const name = `Updated scoped customer ${crypto.randomUUID()}`
    const result = await strictPush(request, await sessionToken(page), [
      {
        ...customer.envelope,
        mutation_id: crypto.randomUUID(),
        operation: 'update',
        base_version: 1,
        payload: { display_name: name },
      },
      {
        ...customer.envelope,
        mutation_id: crypto.randomUUID(),
        entity_type: entityType,
        entity_id: entityId,
        payload:
          entityType === 'bicycle'
            ? { customer_id: customer.entityId, brand: 'Recovered bicycle' }
            : {
                customer_id: customer.entityId,
                bicycle_id: null,
                reported_problem: 'Recovered order',
              },
      },
    ])
    expect(result.results.map((item) => item.status)).toEqual(['applied', 'applied'])
    let corrupted = false
    const predecessors: string[] = []
    await page.route('**/api/v1/sync/deltas/page', async (route) => {
      const body = route.request().postDataJSON() as { protocol: number; continuation: string }
      expect(body.protocol).toBe(1)
      expect(typeof body.continuation).toBe('string')
      predecessors.push(body.continuation)
      const response = await route.fetch()
      expect(response.status()).toBe(200)
      const json = (await response.json()) as {
        baseline_id: string | null
        records: Array<{ entity_id: string; payload: Record<string, unknown> }>
      }
      if (
        json.baseline_id === null &&
        json.records.some((record) => record.entity_id === entityId)
      ) {
        expect(
          json.records.some(
            (record) =>
              record.entity_id === customer.entityId && record.payload.display_name === name,
          ),
        ).toBe(true)
        const record = json.records.find((record) => record.entity_id === entityId)!
        // Keep the genuine server opaque predecessor/successor and all other records.
        // Only the projection scope is fault-injected; no synthetic READY/cursor.
        record.payload.organization_id = 'ffffffff-ffff-7fff-8fff-ffffffffffff'
        record.payload.location_id = 'eeeeeeee-eeee-7eee-8eee-eeeeeeeeeeee'
        corrupted = true
        await route.fulfill({ response, json })
      } else await route.fulfill({ response })
    })
    await page.context().setOffline(false)
    await expect.poll(() => corrupted).toBe(true)
    await expect(page.locator('[data-runtime-state="HELD"]')).toBeVisible()
    expect(predecessors[0]).toBe(original.cursor)
    expect(await partitionEvidence(page, snapshot.partition.partitionId)).toEqual(original)
    await expect(page.getByText(name, { exact: true })).toHaveCount(0)
    await expect(page.locator('.order-card')).toHaveCount(0)

    await page.context().setOffline(true)
    await page.reload({ waitUntil: 'domcontentloaded' })
    await expect(page.locator('[data-runtime-state="HELD"]')).toBeVisible()
    expect(await partitionEvidence(page, snapshot.partition.partitionId)).toEqual(original)
    await page.unrouteAll({ behavior: 'wait' })
    await page.context().setOffline(false)
    await page.getByRole('button', { name: 'Verificar sesión y reintentar', exact: true }).click()
    await waitForReady(page)
    const recovered = await kernelSnapshot(page)
    expect(recovered.records.find((record) => record.entityId === customer.entityId)).toMatchObject(
      { version: 2, payload: { display_name: name } },
    )
    expect(recovered.records.find((record) => record.entityId === entityId)).toMatchObject({
      entityType,
      payload: {
        organization_id: snapshot.context.principal.organizationId,
        location_id: snapshot.context.selectedLocationId,
      },
    })
    expect(recovered.journal).toContainEqual(customer)
    expect(recovered.partition.cursor).not.toBe(original.cursor)
    await page.reload()
    await waitForReady(page)
    expect(
      (await kernelSnapshot(page)).records.find((record) => record.entityId === entityId)?.payload,
    ).toEqual(recovered.records.find((record) => record.entityId === entityId)?.payload)
  })
}

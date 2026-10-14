import { expect, test } from '@playwright/test'
import {
  createCaseIdentity,
  createCustomer,
  kernelSnapshot,
  login,
  pendingMutationCount,
  sessionToken,
  strictPush,
  waitForReady,
} from './helpers/authenticated-workshop.js'

test('competing customer create conflicts visibly, preserves immutable history and converges', async ({
  page,
  request,
}) => {
  const identity = await createCaseIdentity(request)
  await login(page, identity)
  await page.context().setOffline(true)
  const name = `Cliente Conflicto E2E ${crypto.randomUUID()}`
  const original = await createCustomer(page, name)
  expect(await pendingMutationCount(page)).toBe(1)
  // The shipped UI has no customer edit command. Use a real competing create,
  // rather than manufacturing a journal entry or trusting legacy attribution.
  // Stale-base update conflicts remain covered through the order transition UI.
  const remoteName = `Cliente ganador remoto ${crypto.randomUUID()}`
  const result = await strictPush(request, await sessionToken(page), [
    {
      ...original.envelope,
      mutation_id: crypto.randomUUID(),
      payload: { display_name: remoteName },
    },
  ])
  expect(result.results[0]).toMatchObject({ status: 'applied', entity_version: 1 })
  await page.context().setOffline(false)
  await expect
    .poll(
      async () =>
        (await kernelSnapshot(page)).delivery.find(
          (item) => item.mutationId === original.mutationId,
        )?.state,
    )
    .toBe('rejected')
  await expect(page.getByLabel('Estado de sincronización')).toContainText('Requiere atención')
  const center = page.locator('section[aria-labelledby="conflict-center-title"]')
  await expect(center.getByText('Cliente con conflicto')).toBeVisible()
  await expect(center.getByText(`ID: ${original.entityId}`, { exact: true })).toBeVisible()
  await expect(center.getByText(/customer already exists/)).toBeVisible()
  await expect
    .poll(
      async () =>
        (await kernelSnapshot(page)).records.find((row) => row.entityId === original.entityId)
          ?.payload.display_name,
    )
    .toBe(remoteName)
  const conflict = await kernelSnapshot(page)
  expect(conflict.journal).toContainEqual(original)
  expect(
    conflict.delivery.find((item) => item.mutationId === original.mutationId)?.result,
  ).toMatchObject({ status: 'conflict' })
  expect(
    conflict.events.some(
      (event) => event.mutationId === original.mutationId && event.kind === 'result',
    ),
  ).toBe(true)
  expect(await pendingMutationCount(page)).toBe(0)
  await expect(page.getByText(name, { exact: true })).toHaveCount(0)

  await page.reload({ waitUntil: 'domcontentloaded' })
  await waitForReady(page)
  await expect(center.getByText('Cliente con conflicto')).toBeVisible()
  await expect(center.getByText(`ID: ${original.entityId}`, { exact: true })).toBeVisible()
  expect((await kernelSnapshot(page)).journal).toContainEqual(original)
})

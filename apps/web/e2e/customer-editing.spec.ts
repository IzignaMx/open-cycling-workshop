import AxeBuilder from '@axe-core/playwright'
import { expect, test, type APIRequestContext, type Page } from '@playwright/test'
import {
  createCaseIdentity,
  apiLogin,
  writeHeaders,
  kernelSnapshot,
  login,
  waitForReady,
  waitForApplied,
  waitForConfirmed,
  strictPush,
  sessionToken,
} from './helpers/authenticated-workshop.js'

/** Each case admits its own API-created customer; shared baseline fixtures remain untouched. */
async function isolatedCustomer(page: Page, request: APIRequestContext) {
  const owner = await apiLogin(request, 'e2e-owner')
  const locationResponse = await request.post('/api/v1/locations', {
    headers: await writeHeaders(request, owner),
    data: { name: `Customer edit ${crypto.randomUUID()}` },
  })
  expect(locationResponse.status()).toBe(201)
  const { location_id: locationId } = (await locationResponse.json()) as { location_id: string }
  const name = `Isolated customer ${crypto.randomUUID()}`
  const response = await request.post('/api/v1/customers', {
    headers: await writeHeaders(request, owner, locationId),
    data: { location_id: locationId, display_name: name },
  })
  expect(response.status()).toBe(201)
  const { customer_id: customerId } = (await response.json()) as { customer_id: string }
  await login(page, await createCaseIdentity(request, { locationId }))
  const admitted = await kernelSnapshot(page)
  const customer = admitted.records.find(
    (row) => row.entityType === 'customer' && row.entityId === customerId,
  )
  expect(customer).toBeDefined()
  expect(customer!.payload).toMatchObject({
    customer_id: customerId,
    location_id: locationId,
    display_name: name,
  })
  return { customer: customer!, locationId, name }
}

test('unsaved edit is discarded on reload while saved offline update persists and synchronizes', async ({
  page,
  request,
}) => {
  const { customer, name } = await isolatedCustomer(page, request)
  await page.getByRole('button', { name: `Editar cliente ${name}`, exact: true }).click()
  const form = page.locator('form[aria-describedby="customer-edit-status customer-edit-lifetime"]')
  const edited = `Editado ${crypto.randomUUID()}`
  await page.context().setOffline(true)
  await form.getByLabel('Nombre', { exact: true }).fill(edited)
  await form.getByLabel('Correo', { exact: true }).fill('edited@example.test')
  await expect(form.locator('#customer-edit-lifetime')).toContainText('Se pierde al recargar')
  await page.evaluate(async () => {
    await navigator.serviceWorker.ready
  })
  page.once('dialog', (dialog) => dialog.accept())
  await page.reload({ waitUntil: 'domcontentloaded' })
  await waitForReady(page)
  await expect(form).toHaveCount(0)
  expect((await kernelSnapshot(page)).journal).toHaveLength(0)
  await page.getByRole('button', { name: `Editar cliente ${name}`, exact: true }).click()
  await expect(form.getByLabel('Nombre', { exact: true })).toHaveValue(name)
  await form.getByLabel('Nombre', { exact: true }).fill(edited)
  await form.getByLabel('Correo', { exact: true }).fill('edited@example.test')
  const accessibility = await new AxeBuilder({ page })
    .include('section[aria-labelledby="customer-edit-title"]')
    .analyze()
  expect(
    accessibility.violations.filter((v) => ['serious', 'critical'].includes(v.impact ?? '')),
  ).toEqual([])
  await form.getByRole('button', { name: 'Guardar cambios', exact: true }).click()
  await expect(form).toHaveCount(0)
  const local = await kernelSnapshot(page)
  const updates = local.journal.filter(
    (row) => row.entityId === customer.entityId && row.envelope.operation === 'update',
  )
  expect(updates).toHaveLength(1)
  const operation = updates[0]!
  expect(operation.envelope.base_version).toBe(customer.version)
  expect(operation.envelope.payload).toMatchObject({
    display_name: edited,
    email: 'edited@example.test',
  })
  await page.reload({ waitUntil: 'domcontentloaded' })
  await waitForReady(page)
  expect(
    (await kernelSnapshot(page)).journal.filter((row) => row.mutationId === operation.mutationId),
  ).toEqual([operation])
  await page.context().setOffline(false)
  await waitForApplied(page, operation.mutationId)
  await waitForConfirmed(page, operation, customer.version + 1)
})

test('cancel refuses silent discard and read-only users have no editing controls', async ({
  page,
  request,
}) => {
  const { name, locationId } = await isolatedCustomer(page, request)
  await page.getByRole('button', { name: `Editar cliente ${name}`, exact: true }).click()
  const form = page.locator('form[aria-describedby="customer-edit-status customer-edit-lifetime"]')
  await form.getByLabel('Teléfono', { exact: true }).fill('555123')
  page.once('dialog', (dialog) => dialog.dismiss())
  await form.getByRole('button', { name: 'Cancelar edición' }).click()
  await expect(form.getByLabel('Teléfono', { exact: true })).toHaveValue('555123')
  page.once('dialog', (dialog) => dialog.accept())
  await form.getByRole('button', { name: 'Cancelar edición' }).click()
  await expect(form).toHaveCount(0)
  expect((await kernelSnapshot(page)).journal).toHaveLength(0)
  await page.getByRole('button', { name: 'Cerrar esta sesión', exact: true }).click()
  await login(
    page,
    await createCaseIdentity(request, {
      locationId,
      capabilities: ['customers.read', 'sync.pull'],
    }),
  )
  await expect(page.getByRole('button', { name: /^Editar cliente / })).toHaveCount(0)
})

test('competing server update surfaces conflict and preserves the exact local mutation', async ({
  page,
  request,
}) => {
  const { customer } = await isolatedCustomer(page, request)
  await page
    .getByRole('button', {
      name: `Editar cliente ${String(customer.payload.display_name)}`,
      exact: true,
    })
    .click()
  await page.context().setOffline(true)
  const form = page.locator('form[aria-describedby="customer-edit-status customer-edit-lifetime"]')
  await form.getByLabel('Nombre', { exact: true }).fill(`Local ${crypto.randomUUID()}`)
  await form.getByRole('button', { name: 'Guardar cambios', exact: true }).click()
  await expect(form).toHaveCount(0)
  const operation = (await kernelSnapshot(page)).journal.find(
    (row) => row.entityId === customer.entityId && row.envelope.operation === 'update',
  )!
  const remoteName = `Remoto ${crypto.randomUUID()}`
  const result = await strictPush(request, await sessionToken(page), [
    {
      ...operation.envelope,
      mutation_id: crypto.randomUUID(),
      payload: { ...operation.envelope.payload, display_name: remoteName },
    },
  ])
  expect(result.results[0]).toMatchObject({ status: 'applied' })
  await page.context().setOffline(false)
  await expect
    .poll(
      async () =>
        (await kernelSnapshot(page)).delivery.find((row) => row.mutationId === operation.mutationId)
          ?.result?.status,
    )
    .toBe('conflict')
  const center = page.locator('section[aria-labelledby="conflict-center-title"]')
  await expect(center.getByText('Cliente con conflicto')).toBeVisible()
  await expect(center.getByText(`ID: ${customer.entityId}`, { exact: true })).toBeVisible()
  expect((await kernelSnapshot(page)).journal).toContainEqual(operation)
  await expect
    .poll(
      async () =>
        (await kernelSnapshot(page)).records.find((row) => row.entityId === customer.entityId)
          ?.payload.display_name,
    )
    .toBe(remoteName)
})

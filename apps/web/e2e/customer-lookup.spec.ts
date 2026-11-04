import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'
import {
  apiLogin,
  createCaseIdentity,
  kernelSnapshot,
  login,
  writeHeaders,
} from './helpers/authenticated-workshop.js'

test('offline name lookup continues beyond one local page and keeps explicit selection while querying', async ({
  page,
  request,
}, info) => {
  // Real REST history before genuine baseline admission, not fabricated local projections.
  const owner = await apiLogin(request, 'e2e-owner')
  const locationResponse = await request.post('/api/v1/locations', {
    headers: await writeHeaders(request, owner),
    data: { name: `Lookup ${crypto.randomUUID()}` },
  })
  expect(locationResponse.status()).toBe(201)
  const { location_id: locationId } = (await locationResponse.json()) as { location_id: string }
  const headers = await writeHeaders(request, owner, locationId)
  const customers: { customer_id: string; display_name: string }[] = []
  for (let i = 0; i < 51; i++) {
    const response = await request.post('/api/v1/customers', {
      headers,
      data: { location_id: locationId, display_name: `Lookup ${crypto.randomUUID()}` },
    })
    expect(response.status()).toBe(201)
    customers.push((await response.json()) as { customer_id: string; display_name: string })
  }
  customers.sort((a, b) => a.customer_id.localeCompare(b.customer_id))
  const target = customers[50]!
  await login(page, await createCaseIdentity(request, { locationId }))
  await page.evaluate(async () => {
    await navigator.serviceWorker.ready
  })
  await page.context().setOffline(true)
  await expect(page.getByLabel('Estado de sincronización')).toContainText('Sin conexión')
  const before = (await kernelSnapshot(page)).journal
  const form = page.locator('form[aria-describedby~="order-intake-status"]')
  const query = form.getByLabel('Buscar cliente por nombre', { exact: true })
  const selected = form.getByLabel('Cliente', { exact: true })
  await query.fill(target.display_name)
  await query.press('Enter')
  await expect(form.locator('#customer-lookup-status')).toContainText('1 página')
  await expect(selected.locator(`option[value="${target.customer_id}"]`)).toHaveCount(0)
  await expect(
    form.getByRole('button', { name: 'Continuar búsqueda local', exact: true }),
  ).toBeEnabled()
  expect((await kernelSnapshot(page)).journal).toEqual(before)
  await form.getByRole('button', { name: 'Continuar búsqueda local', exact: true }).click()
  await expect(selected.locator(`option[value="${target.customer_id}"]`)).toHaveText(
    `${target.display_name} · ${target.customer_id}`,
  )
  await expect(selected).toHaveValue('')
  await selected.selectOption(target.customer_id)
  await expect(
    form.getByRole('button', { name: 'Verificar cliente seleccionado', exact: true }),
  ).toBeEnabled()
  await query.fill('no local match')
  await form.getByRole('button', { name: 'Buscar clientes locales', exact: true }).click()
  await expect(selected).toHaveValue(target.customer_id)
  await expect(selected.locator(`option[value="${target.customer_id}"]`)).toContainText(
    target.display_name,
  )
  await form
    .getByLabel('Problema reportado', { exact: true })
    .fill('Revisión mediante selección explícita')
  await expect(form.locator('button[type="submit"]')).toBeEnabled()
  await form.locator('button[type="submit"]').click()
  await expect.poll(async () => (await kernelSnapshot(page)).journal.length).toBe(before.length + 1)
  const operation = (await kernelSnapshot(page)).journal.at(-1)!
  expect(operation.entityType).toBe('service_order')
  expect(operation.envelope.payload.customer_id).toBe(target.customer_id)
  const accessibility = await new AxeBuilder({ page }).analyze()
  expect(
    accessibility.violations.filter((v) => ['critical', 'serious'].includes(v.impact ?? '')),
  ).toEqual([])
  await page.screenshot({ path: info.outputPath('customer-lookup-offline.png'), fullPage: true })
})

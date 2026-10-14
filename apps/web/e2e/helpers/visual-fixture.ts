import { expect, type APIRequestContext, type Page } from '@playwright/test'
import {
  apiLogin,
  createCustomer,
  kernelSnapshot,
  LOCATION_ID,
  login,
  PASSWORD,
  writeHeaders,
} from './authenticated-workshop.js'

export const READ_CAPABILITIES = ['customers.read', 'bicycles.read', 'orders.read', 'sync.pull']
export const FULL_CAPABILITIES = [
  ...READ_CAPABILITIES,
  'customers.write',
  'bicycles.write',
  'orders.write',
  'sync.push',
]

/** Real scoped REST history before genuine baseline, with a private synthetic workshop per case. */
export async function seedWorkshop(
  page: Page,
  request: APIRequestContext,
  capabilities = FULL_CAPABILITIES,
) {
  const token = await apiLogin(request, 'e2e-owner')
  const locationResponse = await request.post('/api/v1/locations', {
    headers: await writeHeaders(request, token),
    data: { name: `Taller visual ${crypto.randomUUID()}` },
  })
  expect(locationResponse.status(), await locationResponse.text()).toBe(201)
  const locationId = ((await locationResponse.json()) as { location_id: string }).location_id
  const username = `visual-${crypto.randomUUID()}`
  const userResponse = await request.post('/api/v1/admin/users', {
    headers: await writeHeaders(request, token, locationId),
    data: {
      username,
      display_name: 'Usuario de prueba visual',
      location_id: locationId,
      password: PASSWORD,
      capabilities,
    },
  })
  expect(userResponse.status(), await userResponse.text()).toBe(201)
  const userId = ((await userResponse.json()) as { user_id: string }).user_id
  const post = async (path: string, data: unknown, expected = 201) => {
    const response = await request.post(`/api/v1/${path}`, {
      headers: await writeHeaders(request, token, locationId),
      data,
    })
    expect(response.status(), await response.text()).toBe(expected)
    return response.json() as Promise<Record<string, string>>
  }
  const customer = await post('customers', {
    location_id: locationId,
    display_name: 'Cliente de prueba visual',
  })
  const bicycle = await post('bicycles', {
    location_id: locationId,
    customer_id: customer.customer_id,
    brand: 'Prueba',
    model: 'Visual',
  })
  const orders: string[] = []
  const paths = [
    ['start_diagnosis', 'authorize', 'start_work'],
    ['start_diagnosis', 'authorize', 'start_work', 'request_parts'],
    ['start_diagnosis', 'authorize', 'start_work', 'mark_ready'],
    [],
  ]
  for (const [index, actions] of paths.entries()) {
    const order = await post('service-orders', {
      location_id: locationId,
      customer_id: customer.customer_id,
      bicycle_id: bicycle.bicycle_id,
      reported_problem: `Caso visual ${index + 1}: revisión de frenos y transmisión`,
    })
    orders.push(order.order_id!)
    for (const action of actions)
      await post(`service-orders/${order.order_id}/transitions`, { action }, 200)
  }
  await login(page, username)
  expect((await kernelSnapshot(page)).context.selectedLocationId).toBe(locationId)
  if (capabilities.includes('orders.read')) {
    await expect(page.locator('.order-card')).toHaveCount(4)
    await page.locator('.order-card').first().getByRole('button', { name: 'Ver historial' }).click()
    await expect(page.getByText('Historial (3)', { exact: true })).toBeVisible()
  }
  await page.evaluate(async () => {
    await navigator.serviceWorker.ready
  })
  await page.context().setOffline(true)
  await expect(page.getByLabel('Estado de sincronización')).toContainText('Sin conexión')
  if (capabilities.includes('customers.write') && capabilities.includes('customers.read'))
    await createCustomer(page, 'Cliente pendiente de prueba visual')
  return {
    username,
    userId,
    locationId,
    customerId: customer.customer_id!,
    bicycleId: bicycle.bicycle_id!,
    orders,
  }
}

export async function addScopedVisualUser(
  request: APIRequestContext,
  locationId: string,
  capabilities: string[],
) {
  const token = await apiLogin(request, 'e2e-owner'),
    username = `visual-other-${crypto.randomUUID()}`
  const response = await request.post('/api/v1/admin/users', {
    headers: await writeHeaders(request, token, LOCATION_ID),
    data: {
      username,
      display_name: 'Usuario sin lectura',
      location_id: locationId,
      password: PASSWORD,
      capabilities: [...capabilities, 'sync.pull'],
    },
  })
  expect(response.status(), await response.text()).toBe(201)
  return username
}

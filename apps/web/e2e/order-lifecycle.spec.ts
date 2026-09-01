import { expect, test, type Page } from '@playwright/test'

const ORGANIZATION_ID = '00000000-0000-7000-8000-000000000001'
const USERNAME = 'e2e-admin'
const PASSWORD = 'ocwp-e2e-password'

async function login(page: Page) {
  await page.goto('/')
  await page.getByLabel('Organización').fill(ORGANIZATION_ID)
  await page.getByLabel('Usuario').fill(USERNAME)
  await page.getByLabel('Contraseña').fill(PASSWORD)
  await page.getByRole('button', { name: 'Iniciar sesión' }).click()
  await expect(page.getByText('Sesión:')).toBeVisible()
}

async function sessionToken(page: Page): Promise<string> {
  return page.evaluate(
    () =>
      (JSON.parse(window.sessionStorage.getItem('ocwp.session.v2') ?? '{}').token ?? '') as string,
  )
}

async function orderIdByProblem(page: Page, problem: string): Promise<string | null> {
  return page.evaluate(
    async ({ problem }) => {
      const request = indexedDB.open('ocwp')
      const database = await new Promise<IDBDatabase>((resolve, reject) => {
        request.onsuccess = () => resolve(request.result)
        request.onerror = () => reject(request.error)
      })
      try {
        const rows = await new Promise<
          { order_id: string; reported_problem: string; state: string; version: number }[]
        >((resolve, reject) => {
          const all = database
            .transaction('serviceOrders', 'readonly')
            .objectStore('serviceOrders')
            .getAll()
          all.onsuccess = () => resolve(all.result)
          all.onerror = () => reject(all.error)
        })
        return rows.find((row) => row.reported_problem === problem)?.order_id ?? null
      } finally {
        database.close()
      }
    },
    { problem },
  )
}

test('order lifecycle: offline intake, transitions, conflict and convergence', async ({
  page,
  request,
}) => {
  await login(page)
  await expect(page.getByLabel('Estado de sincronización')).toContainText('Sincronizado', {
    timeout: 15_000,
  })

  // 1. Customer first (the intake needs one).
  await page.getByLabel('Nombre').fill('Cliente Orden E2E')
  await page.getByLabel('Correo').fill('order-e2e@example.test')
  await page.getByRole('button', { name: 'Guardar cliente' }).click()
  await expect(page.getByText('Cliente guardado localmente')).toBeVisible()
  await expect(page.getByLabel('Estado de sincronización')).toContainText('Sincronizado', {
    timeout: 15_000,
  })

  // 2. Intake with an inline bicycle.
  await page.getByLabel('Cliente').selectOption({ label: 'Cliente Orden E2E' })
  await page.getByLabel('Problema reportado').fill('Falla de frenos delanteros')
  await page.getByLabel('Condición al recibir').fill('Manubrio rayado')
  await page.getByLabel('Accesorios').fill('Canasto')
  await page.getByLabel('Prioridad').selectOption('high')
  await page.getByLabel('Agregar bicicleta').check()
  await page.getByLabel('Marca').fill('Trek Marlin')
  await page.getByLabel('Modelo').fill('7')
  await page.getByRole('button', { name: 'Guardar orden' }).click()
  await expect(page.getByText('Orden guardada localmente')).toBeVisible()
  await expect(page.getByLabel('Estado de sincronización')).toContainText('Sincronizado', {
    timeout: 15_000,
  })

  const orderCard = page
    .getByRole('list', { name: 'Órdenes de servicio' })
    .getByText('Falla de frenos delanteros')
  await expect(orderCard).toBeVisible()
  await expect(page.getByText('Recibida', { exact: true })).toBeVisible()

  const orderId = await orderIdByProblem(page, 'Falla de frenos delanteros')
  expect(orderId).toBeTruthy()

  // 3. Offline: advance the state machine and survive a reload.
  await page.context().setOffline(true)
  await expect(page.getByLabel('Estado de sincronización')).toContainText('Sin conexión')

  await page.getByRole('button', { name: 'Iniciar diagnóstico' }).click()
  await expect(page.getByText('En diagnóstico', { exact: true })).toBeVisible()

  await page.reload({ waitUntil: 'domcontentloaded' })
  await expect(page.getByText('Sesión:')).toBeVisible()
  await expect(page.getByText('En diagnóstico', { exact: true })).toBeVisible({
    timeout: 15_000,
  })

  // 4. Concurrent remote transitions while this device stays offline: the
  //    server independently advances the same order through DIAGNOSIS to
  //    AUTHORIZED (its own start_diagnosis + authorize, out-of-band).
  const token = await sessionToken(page)
  for (const action of ['start_diagnosis', 'authorize'] as const) {
    const remote = await request.post(`/api/v1/service-orders/${orderId}/transitions`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { action },
    })
    expect(remote.ok()).toBeTruthy()
  }
  const remoteState = await request.get(`/api/v1/service-orders/${orderId}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  const remoteBody = (await remoteState.json()) as { version: number; state: string }
  expect(remoteBody.version).toBe(3)
  expect(remoteBody.state).toBe('AUTHORIZED')

  // 5. The offline device also authorizes from its stale version 2.
  await page.getByRole('button', { name: 'Autorizar', exact: true }).click()
  await expect(page.getByText('Autorizada', { exact: true })).toBeVisible()

  // 6. Reconnect: the stale transition conflicts visibly and the device
  //    converges to the server's winning state.
  await page.context().setOffline(false)
  await page.getByRole('button', { name: 'Sincronizar ahora' }).click()

  await expect(page.getByLabel('Estado de sincronización')).toContainText('Requiere atención', {
    timeout: 20_000,
  })
  const center = page.locator('section[aria-labelledby="conflict-center-title"]')
  await expect(center.getByText(/base version/, { exact: false }).first()).toBeVisible()

  const state = await page.evaluate(
    async ({ orderId }) => {
      const request = indexedDB.open('ocwp')
      const database = await new Promise<IDBDatabase>((resolve, reject) => {
        request.onsuccess = () => resolve(request.result)
        request.onerror = () => reject(request.error)
      })
      try {
        const rows = await new Promise<{ order_id: string; state: string }[]>((resolve, reject) => {
          const all = database
            .transaction('serviceOrders', 'readonly')
            .objectStore('serviceOrders')
            .getAll()
          all.onsuccess = () => resolve(all.result)
          all.onerror = () => reject(all.error)
        })
        return rows.find((row) => row.order_id === orderId)?.state ?? null
      } finally {
        database.close()
      }
    },
    { orderId },
  )
  expect(state).toBe('AUTHORIZED')

  // 7. The server timeline records exactly one event per applied transition.
  const events = await request.get(`/api/v1/service-orders/${orderId}/events`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  const eventBody = (await events.json()) as { action: string }[]
  expect(eventBody.map((event) => event.action)).toEqual(['start_diagnosis', 'authorize'])
})

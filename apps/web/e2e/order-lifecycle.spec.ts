import { expect, test, type APIRequestContext, type Page, type Response } from '@playwright/test'

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

interface LocalOrder {
  order_id: string
  reported_problem: string
  customer_id: string
  bicycle_id: string | null
}
interface QueuedCreate {
  mutation_id: string
  entity_id: string
  entity_type: string
  operation: string
  payload: { reported_problem?: string }
}

async function readRows<T>(page: Page, storeName: string): Promise<T[]> {
  return page.evaluate(async (name) => {
    const request = indexedDB.open('ocwp')
    const database = await new Promise<IDBDatabase>((resolve, reject) => {
      request.onsuccess = () => resolve(request.result)
      request.onerror = () => reject(request.error)
    })
    try {
      return await new Promise<T[]>((resolve, reject) => {
        const all = database.transaction(name, 'readonly').objectStore(name).getAll()
        all.onsuccess = () => resolve(all.result)
        all.onerror = () => reject(all.error)
      })
    } finally {
      database.close()
    }
  }, storeName)
}

function observeOrderCreate(page: Page, problem: string) {
  const observation = {
    received: null as null | {
      mutation: QueuedCreate
      status: number
      body: {
        results?: {
          mutation_id: string
          entity_id: string
          status: string
          entity_version: number
        }[]
      }
    },
    error: null as string | null,
  }
  const listener = (response: Response) => {
    if (!response.url().endsWith('/api/v1/sync/mutations')) return
    const mutation = (
      response.request().postDataJSON() as { mutations: QueuedCreate[] }
    ).mutations.find(
      (item) =>
        item.entity_type === 'service_order' &&
        item.operation === 'create' &&
        item.payload.reported_problem === problem,
    )
    if (!mutation) return
    void response
      .json()
      .then((body) => {
        observation.received = { mutation, status: response.status(), body }
      })
      .catch((error: unknown) => {
        observation.error = String(error)
      })
  }
  page.on('response', listener)
  return { observation, stop: () => page.off('response', listener) }
}

async function waitForBaselineOrder(
  page: Page,
  request: APIRequestContext,
  token: string,
  problem: string,
  capture: ReturnType<typeof observeOrderCreate>,
  timeout = 10_000,
): Promise<LocalOrder> {
  await expect(page.getByText('Orden guardada localmente')).toBeVisible({ timeout })
  await expect
    .poll(() => capture.observation.received ?? capture.observation.error, {
      timeout,
      message: 'matching order create acknowledgement must arrive',
    })
    .not.toBeNull()
  expect(capture.observation.error).toBeNull()
  const ack = capture.observation.received!
  expect(ack.status, `order create HTTP ${ack.status}: ${JSON.stringify(ack.body)}`).toBe(200)
  expect(ack.body.results?.filter((item) => item.mutation_id === ack.mutation.mutation_id)).toEqual(
    [
      {
        mutation_id: ack.mutation.mutation_id,
        entity_id: ack.mutation.entity_id,
        status: 'applied',
        entity_version: 1,
      },
    ].map((item) => expect.objectContaining(item)),
  )
  await expect
    .poll(
      async () =>
        (await readRows<QueuedCreate>(page, 'mutationQueue')).filter(
          (item) => item.mutation_id === ack.mutation.mutation_id,
        ).length,
      {
        timeout,
        message: 'matching order create acknowledgement must drain its durable queue entry',
      },
    )
    .toBe(0)
  const rows = (await readRows<LocalOrder>(page, 'serviceOrders')).filter(
    (row) => row.order_id === ack.mutation.entity_id && row.reported_problem === problem,
  )
  expect(rows).toHaveLength(1)
  const order = rows[0]!
  const response = await request.get(`/api/v1/service-orders/${order.order_id}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  const body = await response.text()
  expect(response.status(), `baseline order HTTP ${response.status()}: ${body}`).toBe(200)
  expect(JSON.parse(body)).toMatchObject({
    order_id: order.order_id,
    customer_id: order.customer_id,
    bicycle_id: order.bicycle_id,
    reported_problem: problem,
    state: 'INTAKE',
    version: 1,
  })
  await expect(page.getByLabel('Estado de sincronización')).toContainText('Sincronizado', {
    timeout,
  })
  return order
}

async function createCustomer(page: Page, request: APIRequestContext, token: string, name: string) {
  await page.getByLabel('Nombre').fill(name)
  await page.getByRole('button', { name: 'Guardar cliente' }).click()
  await expect(page.getByText('Cliente guardado localmente')).toBeVisible()
  const rows = (
    await readRows<{ customer_id: string; display_name: string }>(page, 'customers')
  ).filter((row) => row.display_name === name)
  expect(rows).toHaveLength(1)
  const customerId = rows[0]!.customer_id
  await expect
    .poll(
      async () =>
        (await readRows<QueuedCreate>(page, 'mutationQueue')).filter(
          (row) => row.entity_id === customerId,
        ).length,
    )
    .toBe(0)
  const response = await request.get(`/api/v1/customers/${customerId}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  const body = await response.text()
  expect(response.status(), `baseline customer HTTP ${response.status()}: ${body}`).toBe(200)
  expect(JSON.parse(body)).toMatchObject({
    customer_id: customerId,
    display_name: name,
    version: 1,
  })
  await expect(page.getByLabel('Estado de sincronización')).toContainText('Sincronizado')
  return customerId
}

test('order lifecycle: offline intake, transitions, conflict and convergence', async ({
  page,
  request,
}) => {
  await login(page)
  await expect(page.getByLabel('Estado de sincronización')).toContainText('Sincronizado', {
    timeout: 15_000,
  })

  const runId = crypto.randomUUID()
  const customerName = `Cliente Orden E2E ${runId}`
  const problem = `Falla de frenos delanteros ${runId}`
  const token = await sessionToken(page)

  // 1. Customer first (the intake needs one).
  const customerId = await createCustomer(page, request, token, customerName)

  // 2. Intake with an inline bicycle.
  await page.getByLabel('Cliente').selectOption(customerId)
  await page.getByLabel('Problema reportado').fill(problem)
  await page.getByLabel('Condición al recibir').fill('Manubrio rayado')
  await page.getByLabel('Accesorios').fill('Canasto')
  await page.getByLabel('Prioridad').selectOption('high')
  await page.getByLabel('Agregar bicicleta').check()
  await page.getByLabel('Marca').fill('Trek Marlin')
  await page.getByLabel('Modelo').fill('7')
  const capture = observeOrderCreate(page, problem)
  await page.getByRole('button', { name: 'Guardar orden' }).click()
  const order = await waitForBaselineOrder(page, request, token, problem, capture)
  capture.stop()
  const orderId = order.order_id
  const orderCard = page.getByRole('listitem', { name: `Orden ${problem}`, exact: true })
  await expect(orderCard).toBeVisible()
  await expect(orderCard.getByText('Recibida', { exact: true })).toBeVisible()

  // 3. Offline: advance the state machine and survive a reload.
  await page.context().setOffline(true)
  await expect(page.getByLabel('Estado de sincronización')).toContainText('Sin conexión')

  await orderCard.getByRole('button', { name: 'Iniciar diagnóstico' }).click()
  await expect(orderCard.getByText('En diagnóstico', { exact: true })).toBeVisible()

  await page.reload({ waitUntil: 'domcontentloaded' })
  await expect(page.getByText('Sesión:')).toBeVisible()
  await expect(orderCard.getByText('En diagnóstico', { exact: true })).toBeVisible({
    timeout: 15_000,
  })

  // 4. Concurrent remote transitions while this device stays offline: the
  //    server independently advances the same order through DIAGNOSIS to
  //    AUTHORIZED (its own start_diagnosis + authorize, out-of-band).
  for (const action of ['start_diagnosis', 'authorize'] as const) {
    const remote = await request.post(`/api/v1/service-orders/${orderId}/transitions`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { action },
    })
    const body = await remote.text()
    expect(
      remote.status(),
      `remote ${action} for ${orderId}: HTTP ${remote.status()}: ${body}`,
    ).toBe(200)
  }
  const remoteState = await request.get(`/api/v1/service-orders/${orderId}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  const remoteText = await remoteState.text()
  expect(remoteState.status(), `remote order HTTP ${remoteState.status()}: ${remoteText}`).toBe(200)
  const remoteBody = JSON.parse(remoteText) as { version: number; state: string }
  expect(remoteBody.version).toBe(3)
  expect(remoteBody.state).toBe('AUTHORIZED')

  // 5. The offline device also authorizes from its stale version 2.
  await orderCard.getByRole('button', { name: 'Autorizar', exact: true }).click()
  await expect(orderCard.getByText('Autorizada', { exact: true })).toBeVisible()

  // 6. Reconnect: the stale transition conflicts visibly and the device
  //    converges to the server's winning state.
  await page.context().setOffline(false)
  await page.getByRole('button', { name: 'Sincronizar ahora' }).click()

  await expect(page.getByLabel('Estado de sincronización')).toContainText('Requiere atención', {
    timeout: 20_000,
  })
  const center = page.locator('section[aria-labelledby="conflict-center-title"]')
  const orderConflicts = center.getByRole('listitem').filter({ hasText: orderId })
  await expect(orderConflicts.first().getByText(/base version/, { exact: false })).toBeVisible()

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
  const eventText = await events.text()
  expect(events.status(), `timeline for ${orderId}: HTTP ${events.status()}: ${eventText}`).toBe(
    200,
  )
  const eventBody = JSON.parse(eventText) as { action: string }[]
  expect(eventBody.map((event) => event.action)).toEqual(['start_diagnosis', 'authorize'])
})

async function holdOrderCompletion(page: Page): Promise<void> {
  await page.evaluate(() => {
    const prototype = IDBTransaction.prototype
    const descriptor = Object.getOwnPropertyDescriptor(prototype, 'oncomplete')!
    const gate = { held: false, release: () => {} }
    Object.assign(window, { orderCompletionGate: gate })
    Object.defineProperty(prototype, 'oncomplete', {
      configurable: true,
      get: descriptor.get,
      set(callback: (this: IDBTransaction, event: Event) => void) {
        descriptor.set!.call(this, function (this: IDBTransaction, event: Event) {
          if (
            this.mode === 'readwrite' &&
            this.objectStoreNames.length === 2 &&
            this.objectStoreNames.contains('serviceOrders') &&
            this.objectStoreNames.contains('mutationQueue')
          ) {
            Object.defineProperty(prototype, 'oncomplete', descriptor)
            gate.held = true
            gate.release = () => {
              gate.release = () => {}
              callback.call(this, event)
            }
          } else {
            callback.call(this, event)
          }
        })
      },
    })
  })
}

async function releaseOrderCompletion(page: Page): Promise<void> {
  await page.evaluate(() => {
    ;(
      window as unknown as { orderCompletionGate: { release(): void } }
    ).orderCompletionGate.release()
  })
}

test('order baseline rejects stale synced state, withheld create and withheld acknowledgement', async ({
  page,
  request,
}) => {
  const runId = crypto.randomUUID()
  const problem = `Orden barrera ${runId}`
  await login(page)
  await expect(page.getByLabel('Estado de sincronización')).toContainText('Sincronizado')
  const token = await sessionToken(page)
  const customerId = await createCustomer(page, request, token, `Cliente barrera orden ${runId}`)
  await page.getByLabel('Cliente').selectOption(customerId)
  await page.getByLabel('Problema reportado').fill(problem)
  await holdOrderCompletion(page)
  const capture = observeOrderCreate(page, problem)
  let releaseCreate = () => {}
  let releaseAck = () => {}
  const createGate = new Promise<void>((resolve) => {
    releaseCreate = resolve
  })
  const ackGate = new Promise<void>((resolve) => {
    releaseAck = resolve
  })
  let requestHeld = false
  let ackHeld = false
  await page.route('**/api/v1/sync/mutations', async (route) => {
    const mutations = (route.request().postDataJSON() as { mutations: QueuedCreate[] }).mutations
    if (
      !mutations.some(
        (item) =>
          item.entity_type === 'service_order' &&
          item.operation === 'create' &&
          item.payload.reported_problem === problem,
      )
    ) {
      await route.continue()
      return
    }
    requestHeld = true
    await createGate
    const response = await route.fetch()
    expect(response.status(), await response.text()).toBe(200)
    ackHeld = true
    await ackGate
    await route.fulfill({ response })
  })
  try {
    await page.getByRole('button', { name: 'Guardar orden' }).click()
    await page.waitForFunction(
      () =>
        (window as unknown as { orderCompletionGate: { held: boolean } }).orderCompletionGate.held,
    )
    // The previous empty-sync label passes while the new order is only local.
    await expect(page.getByLabel('Estado de sincronización')).toContainText('Sincronizado')
    const rows = (await readRows<LocalOrder>(page, 'serviceOrders')).filter(
      (row) => row.reported_problem === problem,
    )
    expect(rows).toHaveLength(1)
    const orderId = rows[0]!.order_id
    const pending = () =>
      readRows<QueuedCreate>(page, 'mutationQueue').then(
        (items) => items.filter((item) => item.entity_id === orderId).length,
      )
    expect(await pending()).toBe(1)
    await expect(waitForBaselineOrder(page, request, token, problem, capture, 250)).rejects.toThrow(
      'Orden guardada localmente',
    )

    await releaseOrderCompletion(page)
    await expect(page.getByText('Orden guardada localmente')).toBeVisible()
    await expect.poll(() => requestHeld).toBe(true)
    const missing = await request.get(`/api/v1/service-orders/${orderId}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    // This 404 is controlled evidence, not a claim about the lost original trace.
    expect(missing.status(), await missing.text()).toBe(404)
    await expect(waitForBaselineOrder(page, request, token, problem, capture, 250)).rejects.toThrow(
      'matching order create acknowledgement must arrive',
    )

    releaseCreate()
    await expect.poll(() => ackHeld).toBe(true)
    const committed = await request.get(`/api/v1/service-orders/${orderId}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    expect(committed.status(), await committed.text()).toBe(200)
    expect(await pending()).toBe(1)
    await expect(waitForBaselineOrder(page, request, token, problem, capture, 250)).rejects.toThrow(
      'matching order create acknowledgement must arrive',
    )

    releaseAck()
    expect((await waitForBaselineOrder(page, request, token, problem, capture)).order_id).toBe(
      orderId,
    )
    expect(await pending()).toBe(0)
  } finally {
    await releaseOrderCompletion(page)
    releaseCreate()
    releaseAck()
    await page.unrouteAll({ behavior: 'wait' })
    capture.stop()
  }
})

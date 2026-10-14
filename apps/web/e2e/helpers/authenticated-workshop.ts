import { expect, type APIRequestContext, type Page } from '@playwright/test'
import type { MutationEnvelope } from '../../src/sync/types.js'
import type {
  AccessContextRecord,
  CachePartition,
  CacheRecord,
  DeviceControl,
  OperationDelivery,
  OperationEvent,
  OwnedOperation,
} from '../../src/access-kernel/types.js'

export const DATABASE = 'ocwp-authenticated-v1'
export const ORGANIZATION_ID = '00000000-0000-7000-8000-000000000001'
export const LOCATION_ID = '00000000-0000-7000-8000-000000000002'
export const USER_ID = '00000000-0000-7000-8000-000000000003'
export const SECOND_LOCATION_ID = '00000000-0000-7000-8000-000000000004'
export const PASSWORD = 'ocwp-e2e-password'
export type JournalOperation = OwnedOperation & { authoredDatasetIncarnation: string }
export interface KernelSnapshot {
  version: number
  control: DeviceControl
  partition: CachePartition
  context: AccessContextRecord['context']
  records: CacheRecord[]
  journal: JournalOperation[]
  delivery: OperationDelivery[]
  events: OperationEvent[]
}

/** Read-only evidence from the selected partition and author. Never create/upgrade a DB. */
export async function kernelSnapshot(page: Page, partitionId?: string): Promise<KernelSnapshot> {
  return page.evaluate(
    async ({ name, partitionId }) => {
      const open = indexedDB.open(name)
      open.onupgradeneeded = () => open.transaction!.abort()
      const db = await new Promise<IDBDatabase>((resolve, reject) => {
        open.onsuccess = () => resolve(open.result)
        open.onerror = () => reject(open.error)
      })
      const read = <T>(request: IDBRequest<T>) =>
        new Promise<T>((resolve, reject) => {
          request.onsuccess = () => resolve(request.result)
          request.onerror = () => reject(request.error)
        })
      try {
        const tx = db.transaction(
          [
            'deviceControl',
            'cachePartitions',
            'accessContexts',
            'cacheRecords',
            'operationJournal',
            'operationDelivery',
            'operationEvents',
          ],
          'readonly',
        )
        const control = (await read(tx.objectStore('deviceControl').get('device'))) as DeviceControl
        const selected = partitionId ?? control?.activePartitionId
        if (!selected) throw new Error('No admitted active partition')
        const partition = (await read(
          tx.objectStore('cachePartitions').get(selected),
        )) as CachePartition
        const context = (
          (await read(tx.objectStore('accessContexts').get(selected))) as AccessContextRecord
        ).context
        const records = (
          await Promise.all(
            ['customer', 'bicycle', 'service_order'].map((type) =>
              read(
                tx
                  .objectStore('cacheRecords')
                  .index('[partitionId+entityType]')
                  .getAll([partition.partitionId, type]),
              ),
            ),
          )
        ).flat() as CacheRecord[]
        const journal = (await read(
          tx
            .objectStore('operationJournal')
            .index('[principalKey+locationId]')
            .getAll([partition.principalKey, partition.locationId]),
        )) as JournalOperation[]
        journal.sort((a, b) => a.localSequence - b.localSequence)
        const delivery = (await Promise.all(
          journal.map((operation) =>
            read(tx.objectStore('operationDelivery').get(operation.mutationId)),
          ),
        )) as OperationDelivery[]
        const events = (
          await Promise.all(
            journal.map((operation) =>
              read(
                tx.objectStore('operationEvents').index('mutationId').getAll(operation.mutationId),
              ),
            ),
          )
        ).flat() as OperationEvent[]
        return {
          version: db.version,
          control,
          partition,
          context,
          records,
          journal,
          delivery,
          events,
        }
      } finally {
        db.close()
      }
    },
    { name: DATABASE, partitionId },
  )
}

export async function waitForReady(page: Page) {
  await expect(page.locator('[data-runtime-state="READY"]')).toBeVisible({ timeout: 20_000 })
  await expect
    .poll(
      async () => {
        const snapshot = await kernelSnapshot(page)
        return (
          snapshot.partition.baselineComplete &&
          snapshot.partition.status === 'active' &&
          typeof snapshot.partition.cursor === 'string' &&
          snapshot.partition.cursor.length > 0 &&
          ['READY', 'OFFLINE_READY'].includes(snapshot.control.state)
        )
      },
      { message: 'genuine complete baseline and current durable admission', timeout: 20_000 },
    )
    .toBe(true)
}

export async function login(page: Page, username = 'e2e-admin', workshop?: string) {
  await page.goto('/')
  await page.getByLabel('Organización', { exact: true }).fill(ORGANIZATION_ID)
  await page.getByLabel('Usuario', { exact: true }).fill(username)
  await page.getByLabel('Contraseña', { exact: true }).fill(PASSWORD)
  await page.getByRole('button', { name: 'Iniciar sesión', exact: true }).click()
  if (workshop) {
    await expect(page.getByRole('heading', { name: 'Selecciona un taller' })).toBeVisible()
    await page.getByRole('button', { name: workshop, exact: true }).click()
  }
  await waitForReady(page)
  const snapshot = await kernelSnapshot(page)
  expect(snapshot.context.snapshotProtocol).toBe('baseline-v1')
  expect(snapshot.context.policyRevision).toBe('ocwp-access-baseline-2')
  expect(snapshot.context.datasetIncarnation).toBeTruthy()
  expect(snapshot.context.principal.organizationId).toBe(ORGANIZATION_ID)
  await expect(page.getByLabel('Estado de sincronización')).toContainText('Sincronizado')
}

export async function sessionToken(page: Page): Promise<string> {
  return page.evaluate(() => JSON.parse(sessionStorage.getItem('ocwp.session.v2')!).token as string)
}

export async function apiLogin(request: APIRequestContext, username = 'e2e-admin') {
  const response = await request.post('/api/v1/auth/login', {
    data: {
      organization_id: ORGANIZATION_ID,
      username,
      password: PASSWORD,
    },
  })
  expect(response.status()).toBe(200)
  return ((await response.json()) as { access_token: string }).access_token
}

/** Every fixture write obtains the actual current epoch, never a copied/fabricated context. */
export async function writeHeaders(
  request: APIRequestContext,
  token: string,
  locationId = LOCATION_ID,
) {
  const context = await request.get(`/api/v1/auth/context?selected_location_id=${locationId}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  expect(context.status()).toBe(200)
  const body = (await context.json()) as { authorization_epoch: string; snapshot_protocol: string }
  expect(body.snapshot_protocol).toBe('baseline-v1')
  return {
    Authorization: `Bearer ${token}`,
    'X-OCWP-Write-Protocol': '1',
    'X-OCWP-Authorization-Epoch': body.authorization_epoch,
  }
}

export async function strictPush(
  request: APIRequestContext,
  token: string,
  mutations: MutationEnvelope[],
) {
  const response = await request.post('/api/v1/sync/mutations', {
    headers: await writeHeaders(request, token, mutations[0]!.location_id),
    data: { mutations },
  })
  expect(response.status(), await response.text()).toBe(200)
  return response.json() as Promise<{
    results: Array<{
      mutation_id: string
      status: string
      entity_version?: number
      reason?: string
    }>
  }>
}

export async function createCustomer(page: Page, name: string) {
  await page.getByLabel('Nombre', { exact: true }).fill(name)
  await page.getByRole('button', { name: 'Guardar cliente', exact: true }).click()
  await expect(page.getByText('Cliente guardado localmente', { exact: true })).toBeVisible()
  await expect
    .poll(async () =>
      (await kernelSnapshot(page)).journal.some(
        (operation) =>
          operation.entityType === 'customer' && operation.envelope.payload.display_name === name,
      ),
    )
    .toBe(true)
  return (await kernelSnapshot(page)).journal.find(
    (operation) =>
      operation.entityType === 'customer' && operation.envelope.payload.display_name === name,
  )!
}

export async function waitForApplied(page: Page, mutationId: string, timeout = 15_000) {
  await expect
    .poll(
      async () =>
        (await kernelSnapshot(page)).delivery.find((item) => item.mutationId === mutationId)?.state,
      {
        timeout,
        message: 'matching immutable operation must have an applied durable acknowledgement',
      },
    )
    .toBe('applied')
  const snapshot = await kernelSnapshot(page)
  const operation = snapshot.journal.find((item) => item.mutationId === mutationId)!
  expect(operation).toBeDefined()
  expect(operation.authoredDatasetIncarnation).toBe(snapshot.context.datasetIncarnation)
  expect(snapshot.delivery.find((item) => item.mutationId === mutationId)?.result).toMatchObject({
    status: 'applied',
  })
  return operation
}

export async function waitForConfirmed(page: Page, operation: JournalOperation, version = 1) {
  await expect
    .poll(
      async () =>
        (await kernelSnapshot(page)).records.find(
          (record) =>
            record.entityType === operation.entityType && record.entityId === operation.entityId,
        )?.version,
      { timeout: 20_000, message: 'authoritative delta must cover the retained journal operation' },
    )
    .toBe(version)
  expect(
    (await kernelSnapshot(page)).journal.find((item) => item.mutationId === operation.mutationId),
  ).toEqual(operation)
}

export async function pendingMutationCount(page: Page) {
  return (await kernelSnapshot(page)).delivery.filter((item) =>
    ['pending', 'inflight', 'retryable', 'awaiting_confirmation'].includes(item.state),
  ).length
}

/** Deterministic post-commit notification barrier, not a manufactured transaction or sleep. */
export async function holdJournalCompletion(page: Page) {
  await page.evaluate(() => {
    const prototype = IDBTransaction.prototype
    const descriptor = Object.getOwnPropertyDescriptor(prototype, 'oncomplete')!
    const gate = { held: false, release: () => {} }
    Object.assign(window, { journalCompletionGate: gate })
    Object.defineProperty(prototype, 'oncomplete', {
      configurable: true,
      get: descriptor.get,
      set(callback: (this: IDBTransaction, event: Event) => void) {
        descriptor.set!.call(this, function (this: IDBTransaction, event: Event) {
          if (
            this.mode === 'readwrite' &&
            this.objectStoreNames.contains('operationJournal') &&
            this.objectStoreNames.contains('operationDelivery') &&
            this.objectStoreNames.contains('operationEvents')
          ) {
            Object.defineProperty(prototype, 'oncomplete', descriptor)
            gate.held = true
            gate.release = () => {
              gate.release = () => {}
              callback.call(this, event)
            }
          } else callback.call(this, event)
        })
      },
    })
  })
}
export async function releaseJournalCompletion(page: Page) {
  await page.evaluate(() =>
    (
      window as unknown as { journalCompletionGate?: { release(): void } }
    ).journalCompletionGate?.release(),
  )
}
export async function waitForJournalBarrier(page: Page) {
  await page.waitForFunction(
    () =>
      (window as unknown as { journalCompletionGate: { held: boolean } }).journalCompletionGate
        .held,
  )
}

export async function createScopedUser(request: APIRequestContext, capabilities: string[]) {
  const token = await apiLogin(request, 'e2e-owner')
  const username = `e2e-browser-${crypto.randomUUID()}`
  const response = await request.post('/api/v1/admin/users', {
    headers: await writeHeaders(request, token),
    data: {
      username,
      display_name: username,
      location_id: LOCATION_ID,
      password: PASSWORD,
      capabilities,
    },
  })
  expect(response.status(), await response.text()).toBe(201)
  return { username, userId: ((await response.json()) as { user_id: string }).user_id }
}

/** Inspect a previously admitted partition after a hold without choosing a replacement. */
export async function partitionEvidence(page: Page, partitionId: string) {
  return page.evaluate(
    async ({ name, partitionId }) => {
      const open = indexedDB.open(name)
      open.onupgradeneeded = () => open.transaction!.abort()
      const db = await new Promise<IDBDatabase>((resolve, reject) => {
        open.onsuccess = () => resolve(open.result)
        open.onerror = () => reject(open.error)
      })
      const read = <T>(request: IDBRequest<T>) =>
        new Promise<T>((resolve, reject) => {
          request.onsuccess = () => resolve(request.result)
          request.onerror = () => reject(request.error)
        })
      try {
        const tx = db.transaction(['cachePartitions', 'cacheRecords'], 'readonly')
        const partition = (await read(
          tx.objectStore('cachePartitions').get(partitionId),
        )) as CachePartition
        const records = (
          await Promise.all(
            ['customer', 'bicycle', 'service_order'].map((type) =>
              read(
                tx
                  .objectStore('cacheRecords')
                  .index('[partitionId+entityType]')
                  .getAll([partitionId, type]),
              ),
            ),
          )
        ).flat() as CacheRecord[]
        return { cursor: partition.cursor, records }
      } finally {
        db.close()
      }
    },
    { name: DATABASE, partitionId },
  )
}

/** Traverse the real bounded UI pages; repeated runs retain more than fifty server rows. */
export async function revealCustomer(page: Page, displayName: string) {
  const list = page.getByRole('list', { name: 'Clientes locales', exact: true })
  const target = list.getByText(displayName, { exact: true })
  while (!(await target.count())) {
    const previous = await list.textContent()
    await page.getByRole('button', { name: 'Más clientes', exact: true }).click()
    await expect
      .poll(() => list.textContent(), { message: 'next bounded customer page must render' })
      .not.toBe(previous)
  }
  await expect(target).toBeVisible()
}

export async function revealOrder(page: Page, problem: string) {
  const target = page.getByRole('listitem', { name: `Orden ${problem}`, exact: true })
  const list = page.getByRole('list', { name: 'Órdenes de servicio', exact: true })
  while (!(await target.count())) {
    const previous = await list.textContent()
    await page.getByRole('button', { name: 'Más órdenes', exact: true }).click()
    await expect
      .poll(() => list.textContent(), { message: 'next bounded order page must render' })
      .not.toBe(previous)
  }
  await expect(target).toBeVisible()
}

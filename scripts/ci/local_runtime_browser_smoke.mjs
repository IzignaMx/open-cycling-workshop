// Hosted-only production-PWA journey through the real Caddy edge. Credentials,
// old sessions and checkpoints remain in memory and stdin; never trace/artifact them.
import assert from 'node:assert/strict'
import { randomUUID } from 'node:crypto'
import { createRequire } from 'node:module'
import { pathToFileURL } from 'node:url'

export class PhaseInput {
  constructor(stream, { timeoutMs = 1_300_000, maxBytes = 16_384 } = {}) {
    this.iterator = stream[Symbol.asyncIterator]()
    this.buffer = Buffer.alloc(0)
    this.timeoutMs = timeoutMs
    this.maxBytes = maxBytes
  }

  async read() {
    const deadline = Date.now() + this.timeoutMs
    while (!this.buffer.includes(10)) {
      let timer
      try {
        const chunk = await Promise.race([
          this.iterator.next(),
          new Promise((_, reject) => {
            timer = setTimeout(
              () => reject(new Error('Phase input timed out')),
              Math.max(0, deadline - Date.now()),
            )
          }),
        ])
        if (chunk.done) throw new Error('Phase input closed')
        this.buffer = Buffer.concat([this.buffer, Buffer.from(chunk.value)])
        if (this.buffer.length > this.maxBytes) throw new Error('Phase input exceeds limit')
      } finally {
        clearTimeout(timer)
      }
    }
    const end = this.buffer.indexOf(10)
    const line = this.buffer.subarray(0, end)
    this.buffer = this.buffer.subarray(end + 1)
    try {
      return JSON.parse(line.toString('utf8'))
    } catch {
      throw new Error('Invalid phase input')
    }
  }
}

export function validateInput(input) {
  const keys = [
    'base',
    'organizationId',
    'locationId',
    'userId',
    'password',
    'datasetIncarnation',
    'historicalCustomerId',
  ]
  assert.equal(Boolean(input && typeof input === 'object' && !Array.isArray(input)), true)
  assert.deepEqual(Object.keys(input).sort(), keys.sort())
  assert.match(input.base, /^http:\/\/127\.0\.0\.1:[1-9][0-9]{0,4}$/)
  assert.equal(new URL(input.base).origin, input.base)
  assert.equal(typeof input.password, 'string')
  assert.equal(input.password.length > 0 && input.password.length <= 1024, true)
  for (const key of [
    'organizationId',
    'locationId',
    'userId',
    'datasetIncarnation',
    'historicalCustomerId',
  ]) {
    assert.match(input[key], /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/)
  }
  return input
}

// Reads inspect only the currently admitted principal/workshop and partition.
// Fixture bounds fail closed rather than silently truncating evidence.
async function snapshot(page) {
  return page.evaluate(async () => {
    const opened = indexedDB.open('ocwp-authenticated-v1')
    opened.onupgradeneeded = () => opened.transaction.abort()
    const take = (request) =>
      new Promise((resolve, reject) => {
        request.onsuccess = () => resolve(request.result)
        request.onerror = () => reject(new Error('Could not read scoped local data'))
      })
    const db = await take(opened)
    try {
      const tx = db.transaction(
        [
          'deviceControl',
          'accessContexts',
          'cachePartitions',
          'cacheRecords',
          'operationJournal',
          'operationDelivery',
          'operationEvents',
        ],
        'readonly',
      )
      const device = await take(tx.objectStore('deviceControl').get('device'))
      const partition = await take(tx.objectStore('cachePartitions').get(device.activePartitionId))
      const access = await take(tx.objectStore('accessContexts').get(device.activePartitionId))
      if (!partition || !access) throw new Error('No active partition')
      const cache = await take(
        tx
          .objectStore('cacheRecords')
          .index('[partitionId+entityType]')
          .getAll([partition.partitionId, 'customer'], 101),
      )
      const journal = await take(
        tx
          .objectStore('operationJournal')
          .index('[principalKey+locationId]')
          .getAll([partition.principalKey, partition.locationId], 101),
      )
      const delivery = await take(
        tx
          .objectStore('operationDelivery')
          .index('[principalKey+locationId+localSequence]')
          .getAll(
            IDBKeyRange.bound(
              [partition.principalKey, partition.locationId, 0],
              [partition.principalKey, partition.locationId, Number.MAX_SAFE_INTEGER],
            ),
            101,
          ),
      )
      const events = []
      for (const operation of journal) {
        events.push(
          ...(await take(
            tx.objectStore('operationEvents').index('mutationId').getAll(operation.mutationId, 101),
          )),
        )
      }
      if ([cache, journal, delivery, events].some((rows) => rows.length > 100))
        throw new Error('Disposable fixture bound exceeded')
      return { device, partition, access, cache, journal, delivery, events }
    } finally {
      db.close()
    }
  })
}

async function session(page) {
  return page.evaluate(() => JSON.parse(sessionStorage.getItem('ocwp.session.v2')))
}

async function run() {
  const phases = new PhaseInput(process.stdin)
  let step = 'fixture_input'
  let browser
  const report = (phase) => process.stdout.write(JSON.stringify({ phase }) + '\n')
  try {
    const input = validateInput(await phases.read())
    const require = createRequire(new URL('../../apps/web/package.json', import.meta.url))
    const { chromium, expect } = require('@playwright/test')
    step = 'launch_browser'
    browser = await chromium.launch()
    const context = await browser.newContext()
    const page = await context.newPage()
    page.setDefaultTimeout(45_000)
    const ready = (target) =>
      expect(target.locator('[data-runtime-state="READY"]')).toBeVisible({ timeout: 60_000 })
    const scoped = (state, incarnation) => {
      assert.equal(state.access.context.principal.organizationId, input.organizationId)
      assert.equal(state.access.context.principal.userId, input.userId)
      assert.equal(state.access.context.selectedLocationId, input.locationId)
      assert.equal(state.access.context.datasetIncarnation, incarnation)
      assert.equal(state.access.context.snapshotProtocol, 'baseline-v1')
      assert.equal(state.partition.baselineComplete, true)
      assert.equal(state.partition.status, 'active')
      assert.equal(state.partition.baseline.phase, 'active')
      assert.equal(state.partition.baseline.datasetIncarnation, incarnation)
      assert.equal(state.partition.sessionAdmission.datasetIncarnation, incarnation)
      assert.equal(
        state.cache.every((row) => row.partitionId === state.device.activePartitionId),
        true,
      )
    }
    const login = async (target) => {
      await target.goto(input.base)
      assert.equal(await target.evaluate(() => window.isSecureContext), true)
      await target.getByLabel('Organización').fill(input.organizationId)
      await target.getByLabel('Usuario', { exact: true }).fill('admin')
      await target.getByLabel('Contraseña').fill(input.password)
      await target.getByRole('button', { name: 'Iniciar sesión' }).click()
      await ready(target)
      await target.evaluate(() => navigator.serviceWorker.ready)
      await expect
        .poll(() => target.evaluate(() => Boolean(navigator.serviceWorker.controller)))
        .toBe(true)
    }
    const create = async (name) => {
      await page.getByLabel('Nombre', { exact: true }).fill(name)
      await page.getByLabel('Correo', { exact: true }).fill('caddy-smoke@example.test')
      await page.getByRole('button', { name: 'Guardar cliente' }).click()
      await expect(
        page.getByRole('list', { name: 'Clientes locales' }).getByText(name, { exact: true }),
      ).toBeVisible()
    }
    const applied = async (target, mutationId) => {
      await expect
        .poll(
          async () =>
            (await snapshot(target)).delivery.find((row) => row.mutationId === mutationId)?.state,
          { timeout: 60_000 },
        )
        .toBe('applied')
      const operation = (await snapshot(target)).journal.find(
        (row) => row.mutationId === mutationId,
      )
      assert.ok(operation)
      await expect
        .poll(
          async () =>
            (await snapshot(target)).cache.some((row) => row.entityId === operation.entityId),
          { timeout: 60_000 },
        )
        .toBe(true)
      return operation
    }
    const api = async (token, path, payload) => {
      // Playwright's request context remains online while the UI is intentionally
      // offline. It exercises the actual edge/API, with no route interception.
      const response = await context.request.fetch(`${input.base}/api/v1${path}`, {
        method: payload === undefined ? 'GET' : 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        data: payload,
        timeout: 30_000,
        maxRedirects: 0,
      })
      const body = await response.body()
      assert.equal(body.length <= 1_048_576, true)
      const result = { status: response.status(), body: JSON.parse(body.toString('utf8')) }
      await response.dispose()
      return result
    }
    const checkpoint = async (token) => {
      // A separate genuine family prevents the running UI's next incremental
      // request from making the retained checkpoint stale before backup.
      const context = await api(token, `/auth/context?selected_location_id=${input.locationId}`)
      assert.equal(context.status, 200)
      assert.equal(context.body.snapshot_protocol, 'baseline-v1')
      let result = await api(token, '/sync/baselines/start', {
        protocol: 1,
        selected_location_id: input.locationId,
        authorization_epoch: context.body.authorization_epoch,
        request_id: randomUUID(),
      })
      assert.equal(result.status, 200)
      for (let count = 0; count < 100; count++) {
        result = await api(token, '/sync/baselines/page', {
          protocol: 1,
          continuation: result.body.continuation,
        })
        assert.equal(result.status, 200)
        if (result.body.phase === 'scan_complete') break
        assert.equal(count < 99, true)
      }
      result = await api(token, '/sync/baselines/finalize', {
        protocol: 1,
        continuation: result.body.continuation,
      })
      assert.equal(result.status, 200)
      for (let count = 0; count < 100; count++) {
        result = await api(token, '/sync/deltas/page', {
          protocol: 1,
          continuation: result.body.continuation,
        })
        assert.equal(result.status, 200)
        if (result.body.phase === 'complete') break
        assert.equal(count < 99, true)
      }
      assert.equal(result.body.completion.checkpoint, result.body.continuation)
      const retained = result.body.continuation
      const activated = await api(token, '/sync/baselines/validate-activation', {
        protocol: 1,
        checkpoint: retained,
      })
      assert.equal(activated.status, 200)
      return retained
    }

    step = 'genuine_historical_baseline'
    await login(page)
    const initial = await snapshot(page)
    scoped(initial, input.datasetIncarnation)
    assert.equal(
      initial.cache.find((row) => row.entityId === input.historicalCustomerId)?.payload
        .display_name,
      'Disposable runtime customer',
    )
    await expect(
      page
        .getByRole('list', { name: 'Clientes locales' })
        .getByText('Disposable runtime customer', { exact: true }),
    ).toBeVisible()
    const initialSession = await session(page)
    assert.equal(typeof initialSession.bindingId, 'string')
    assert.equal(initialSession.admission.datasetIncarnation, input.datasetIncarnation)

    step = 'service_worker_backend_not_spa'
    const probe = await context.newPage()
    const notFound = await probe.goto(`${input.base}/api/does-not-exist`)
    assert.equal(notFound.status(), 404)
    assert.match(notFound.headers()['content-type'], /application\/json/)
    assert.equal(await probe.locator('#root').count(), 0)

    step = 'offline_create_reload'
    const customerName = 'Customer created offline through Caddy'
    await context.setOffline(true)
    await expect(page.getByLabel('Estado de sincronización')).toContainText('Sin conexión')
    await create(customerName)
    await expect.poll(async () => (await snapshot(page)).journal.length).toBe(1)
    const beforeReload = await snapshot(page)
    const first = beforeReload.journal[0]
    assert.equal(first.authoredDatasetIncarnation, input.datasetIncarnation)
    assert.equal(beforeReload.delivery[0].state, 'pending')
    await page.reload({ waitUntil: 'domcontentloaded' })
    await ready(page)
    await expect(page.getByLabel('Estado de sincronización')).toContainText('Sin conexión')
    await expect(
      page.getByRole('list', { name: 'Clientes locales' }).getByText(customerName, { exact: true }),
    ).toBeVisible()
    const afterReload = await snapshot(page)
    assert.deepEqual(afterReload.journal, beforeReload.journal)
    assert.deepEqual(afterReload.events, beforeReload.events)
    assert.equal(afterReload.delivery[0].state, 'pending')
    assert.equal((await session(page)).bindingId, initialSession.bindingId)
    let offlineApiFailed = false
    try {
      await probe.goto(`${input.base}/api/offline-probe`, { waitUntil: 'domcontentloaded' })
    } catch {
      offlineApiFailed = true
    }
    assert.equal(offlineApiFailed, true)
    assert.equal(await probe.locator('#root').count(), 0)
    await probe.close()

    step = 'reconnect_and_convergence'
    await context.setOffline(false)
    await applied(page, first.mutationId)
    await expect(page.getByLabel('Estado de sincronización')).toContainText('Sincronizado', {
      timeout: 60_000,
    })
    assert.deepEqual((await snapshot(page)).journal[0], first)
    const secondContext = await browser.newContext()
    const secondPage = await secondContext.newPage()
    await login(secondPage)
    await expect
      .poll(
        async () =>
          (await snapshot(secondPage)).cache.some((row) => row.entityId === first.entityId),
        { timeout: 60_000 },
      )
      .toBe(true)
    scoped(await snapshot(secondPage), input.datasetIncarnation)
    await expect(
      secondPage
        .getByRole('list', { name: 'Clientes locales' })
        .getByText(customerName, { exact: true }),
    ).toBeVisible()
    await secondContext.close()

    step = 'capture_backed_up_checkpoint'
    const oldSession = await session(page)
    const oldCheckpoint = await checkpoint(oldSession.token)
    await context.setOffline(true)
    await expect(page.getByLabel('Estado de sincronización')).toContainText('Sin conexión')
    report('ready_for_backup')
    step = 'wait_verified_backup'
    assert.deepEqual(await phases.read(), { phase: 'backup_verified' })

    step = 'preserve_post_backup_offline_work'
    const pendingName = 'Unsent work authored after verified backup'
    await create(pendingName)
    await expect.poll(async () => (await snapshot(page)).journal.length).toBe(2)
    const pendingState = await snapshot(page)
    const pending = pendingState.journal.find((row) => row.optimistic.display_name === pendingName)
    assert.ok(pending)
    const pendingDelivery = pendingState.delivery.find(
      (row) => row.mutationId === pending.mutationId,
    )
    assert.equal(pendingDelivery.state, 'pending')
    assert.equal(pendingDelivery.attempts, 0)
    const pendingSession = await session(page)
    const pendingEvents = pendingState.events.filter((row) => row.mutationId === pending.mutationId)
    report('pending_preserved')

    step = 'wait_restored_api'
    const recovered = await phases.read()
    assert.deepEqual(Object.keys(recovered).sort(), ['datasetIncarnation', 'phase'])
    assert.equal(recovered.phase, 'restored_api_ready')
    assert.notEqual(recovered.datasetIncarnation, input.datasetIncarnation)
    assert.deepEqual(await session(page), pendingSession)
    assert.deepEqual((await snapshot(page)).journal, pendingState.journal)
    assert.deepEqual((await snapshot(page)).delivery, pendingState.delivery)

    step = 'old_session_refused'
    assert.equal((await api(oldSession.token, '/auth/me')).status, 401)
    // Clear only the credential via the normal visible action, keeping the same
    // browser profile and every pending operation. No test writes to IndexedDB.
    await page.getByRole('button', { name: 'Cerrar esta sesión', exact: true }).click()
    await context.setOffline(false)
    step = 'fresh_same_principal_baseline'
    await login(page)
    const freshSession = await session(page)
    assert.equal(freshSession.user.user_id, pendingSession.user.user_id)
    assert.equal(freshSession.admission.datasetIncarnation, recovered.datasetIncarnation)
    scoped(await snapshot(page), recovered.datasetIncarnation)
    assert.equal((await api(freshSession.token, '/auth/me')).status, 200)

    step = 'backed_up_checkpoint_refused'
    const refused = await api(freshSession.token, '/sync/deltas/page', {
      protocol: 1,
      continuation: oldCheckpoint,
    })
    assert.equal(refused.status, 409)
    assert.equal(refused.body.error.code, 'context_changed')

    step = 'journal_recovery_hold_without_overlay'
    await expect
      .poll(
        async () =>
          (await snapshot(page)).delivery.find((row) => row.mutationId === pending.mutationId)
            ?.state,
      )
      .toBe('held_recovery')
    const held = await snapshot(page)
    assert.deepEqual(held.journal, pendingState.journal)
    const heldDelivery = held.delivery.find((row) => row.mutationId === pending.mutationId)
    assert.equal(heldDelivery.dispatchable, 0)
    assert.equal(heldDelivery.attempts, pendingDelivery.attempts)
    assert.deepEqual(heldDelivery.result, pendingDelivery.result)
    for (const event of pendingEvents)
      assert.deepEqual(
        held.events.find((row) => row.sequence === event.sequence),
        event,
      )
    assert.equal(
      held.cache.some((row) => row.entityId === pending.entityId),
      false,
    )
    await expect(
      page
        .getByRole('list', { name: 'Trabajo conservado' })
        .getByRole('listitem')
        .filter({ hasText: pending.mutationId }),
    ).toContainText('Recuperación pendiente')
    await expect(page.getByText(pendingName, { exact: true })).toHaveCount(0)
    assert.equal((await api(freshSession.token, `/customers/${pending.entityId}`)).status, 404)
    assert.equal((await api(freshSession.token, `/customers/${first.entityId}`)).status, 200)

    step = 'fresh_post_recovery_work'
    const freshName = 'Fresh independent work after restored recovery'
    await context.setOffline(true)
    await create(freshName)
    await expect.poll(async () => (await snapshot(page)).journal.length).toBe(3)
    const fresh = (await snapshot(page)).journal.find(
      (row) => row.optimistic.display_name === freshName,
    )
    assert.ok(fresh)
    assert.equal(fresh.authoredDatasetIncarnation, recovered.datasetIncarnation)
    await context.setOffline(false)
    await applied(page, fresh.mutationId)
    const remoteFresh = await api(freshSession.token, `/customers/${fresh.entityId}`)
    assert.equal(remoteFresh.status, 200)
    assert.equal(remoteFresh.body.display_name, freshName)
    const final = await snapshot(page)
    assert.deepEqual(
      final.journal.find((row) => row.mutationId === pending.mutationId),
      pending,
    )
    assert.equal(
      final.delivery.find((row) => row.mutationId === pending.mutationId).state,
      'held_recovery',
    )
    await expect(page.getByText(pendingName, { exact: true })).toHaveCount(0)
    assert.equal((await api(freshSession.token, `/customers/${pending.entityId}`)).status, 404)
    await context.close()
    await browser.close()
    browser = undefined
    report('recovery_verified')
  } catch {
    // Error values/stack traces may include credentials or whole session objects.
    process.stdout.write(JSON.stringify({ phase: 'failed', step }) + '\n')
    process.exitCode = 1
  } finally {
    if (browser) await browser.close()
    process.stdin.destroy()
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) await run()

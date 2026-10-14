import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'
import {
  createCustomer,
  kernelSnapshot,
  login,
  pendingMutationCount,
  revealCustomer,
  sessionToken,
  waitForApplied,
  waitForConfirmed,
  waitForReady,
} from './helpers/authenticated-workshop.js'

test('customer persists offline, syncs after reconnect, and converges in a second browser context', async ({
  browser,
}) => {
  const first = await browser.newContext()
  const second = await browser.newContext()
  try {
    const page = await first.newPage()
    await login(page)
    const initial = await kernelSnapshot(page)
    // These rows predate floor-1 activation and were created through REST, not sync.
    expect(initial.records).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          entityType: 'customer',
          payload: expect.objectContaining({ display_name: 'Cliente REST histórico 1' }),
        }),
        expect.objectContaining({
          entityType: 'bicycle',
          payload: expect.objectContaining({ brand: 'Bicicleta REST histórica 1' }),
        }),
        expect.objectContaining({
          entityType: 'service_order',
          payload: expect.objectContaining({ reported_problem: 'Orden REST histórica 1' }),
        }),
      ]),
    )
    const accessibility = await new AxeBuilder({ page }).analyze()
    expect(
      accessibility.violations.filter((item) =>
        ['critical', 'serious'].includes(item.impact ?? ''),
      ),
    ).toEqual([])
    await expect
      .poll(() => page.evaluate(async () => Boolean((await navigator.serviceWorker.ready).active)))
      .toBe(true)
    const name = `Cliente Offline E2E ${crypto.randomUUID()}`
    await first.setOffline(true)
    await expect(page.getByLabel('Estado de sincronización')).toContainText('Sin conexión')
    await page.getByLabel('Correo', { exact: true }).fill('offline@example.test')
    const original = await createCustomer(page, name)
    expect(original.envelope.payload.email).toBe('offline@example.test')
    await expect.poll(() => pendingMutationCount(page)).toBe(1)
    await revealCustomer(page, name)
    expect(
      (await kernelSnapshot(page)).records.some((row) => row.entityId === original.entityId),
    ).toBe(false)

    await page.reload({ waitUntil: 'domcontentloaded' })
    await waitForReady(page)
    await expect(page.getByLabel('Estado de sincronización')).toContainText('Sin conexión')
    await revealCustomer(page, name)
    const restored = await kernelSnapshot(page)
    expect(restored.journal).toContainEqual(original)
    expect(restored.partition.partitionId).toBe(initial.partition.partitionId)
    expect(restored.context.datasetIncarnation).toBe(initial.context.datasetIncarnation)
    expect(await pendingMutationCount(page)).toBe(1)

    const reconnectRequests: string[] = []
    page.on('request', (request) => {
      const path = new URL(request.url()).pathname
      if (path.includes('/auth/context') || path.includes('/sync/')) reconnectRequests.push(path)
    })
    await first.setOffline(false)
    await waitForApplied(page, original.mutationId)
    await waitForConfirmed(page, original)
    expect(reconnectRequests[0]).toBe('/api/v1/auth/context')
    expect(reconnectRequests).toContain('/api/v1/sync/deltas/page')
    expect(reconnectRequests).not.toContain('/api/v1/sync/changes')
    await expect(page.getByLabel('Estado de sincronización')).toContainText('Sincronizado')
    expect(await pendingMutationCount(page)).toBe(0)
    const synced = await kernelSnapshot(page)
    expect(JSON.stringify(synced)).not.toContain(await sessionToken(page))
    expect(synced.journal).toContainEqual(original)
    expect(
      synced.events.some(
        (event) => event.mutationId === original.mutationId && event.kind === 'result',
      ),
    ).toBe(true)

    const otherPage = await second.newPage()
    await login(otherPage)
    await revealCustomer(otherPage, name)
    const other = await kernelSnapshot(otherPage)
    expect(other.records.find((row) => row.entityId === original.entityId)).toMatchObject({
      version: 1,
      payload: { display_name: name },
    })
    expect(other.journal).toHaveLength(0)
  } finally {
    await second.close()
    await first.close()
  }
})

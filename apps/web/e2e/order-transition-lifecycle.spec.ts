import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Page, type Route } from '@playwright/test'
import {
  apiLogin,
  holdJournalCompletion,
  kernelSnapshot,
  ORGANIZATION_ID,
  PASSWORD,
  releaseJournalCompletion,
  waitForJournalBarrier,
  waitForReady,
  writeHeaders,
} from './helpers/authenticated-workshop.js'
import { FULL_CAPABILITIES, seedWorkshop } from './helpers/visual-fixture.js'
import {
  CANARY,
  COMMITTED,
  UNKNOWN,
  installFault,
  type ProbeWindow,
} from './helpers/order-transition-fault.js'

const problem = 'Caso visual 4: revisión de frenos y transmisión'
const orderCard = (page: Page) =>
  page.getByRole('listitem', { name: `Orden ${problem}`, exact: true })

/** Delay an unchanged REAL successful context response, never fabricate authority. */
async function pauseContext(page: Page) {
  let release!: () => void
  const waiting = new Promise<void>((resolve) => {
    release = resolve
  })
  let observed = false
  const handler = async (route: Route) => {
    const response = await route.fetch()
    expect(response.status()).toBe(200)
    observed = true
    await waiting
    await route.fulfill({ response })
  }
  await page.route('**/api/v1/auth/context?*', handler)
  return {
    observed: () => observed,
    release,
    async dispose() {
      release()
      await page.unroute('**/api/v1/auth/context?*', handler)
    },
  }
}
async function restoreFault(page: Page) {
  await page.evaluate(() => {
    ;(window as ProbeWindow).orderTransitionProbe?.restore()
  })
}
async function inPlaceLogin(page: Page, username: string) {
  // No navigation/reload: the original runtime and its old pending callback survive.
  await page.getByLabel('Organización', { exact: true }).fill(ORGANIZATION_ID)
  await page.getByLabel('Usuario', { exact: true }).fill(username)
  await page.getByLabel('Contraseña', { exact: true }).fill(PASSWORD)
  await page.getByRole('button', { name: 'Iniciar sesión', exact: true }).click()
  await waitForReady(page)
}

for (const outcome of ['pending', 'unknown', 'unavailable'] as const)
  test(`transition visit ${outcome} survives real reconnect verification`, async ({
    page,
    request,
  }, info) => {
    const seeded = await seedWorkshop(page, request)
    const id = seeded.orders[3]!
    const before = await kernelSnapshot(page)
    await installFault(
      page,
      id,
      outcome === 'unknown' ? 'quota' : outcome === 'unavailable' ? 'history' : 'none',
    )
    if (outcome === 'pending')
      await holdJournalCompletion(page, {
        entityType: 'service_order',
        orderId: id,
        transitionAction: 'start_diagnosis',
      })
    const barrier = await pauseContext(page)
    try {
      await orderCard(page)
        .getByRole('button', { name: 'Iniciar diagnóstico', exact: true })
        .click()
      if (outcome === 'pending') await waitForJournalBarrier(page)
      else
        await expect(orderCard(page).getByRole('alert')).toHaveText(
          outcome === 'unknown' ? UNKNOWN : COMMITTED,
        )
      await expect
        .poll(() =>
          page.evaluate(() => (window as ProbeWindow).orderTransitionProbe!.terminal.length),
        )
        .toBeGreaterThan(0)
      const native = await page.evaluate(() => {
        const p = (window as ProbeWindow).orderTransitionProbe!
        return { writes: p.writes, injected: p.injected, terminal: p.terminal }
      })
      expect(native.writes).toBe(1)
      expect(native.injected).toBe(outcome === 'pending' ? 0 : 1)
      expect(native.terminal).toContainEqual({
        type: outcome === 'unknown' ? 'abort' : 'complete',
        trusted: true,
      })
      expect(
        native.terminal.some((e) => e.type === (outcome === 'unknown' ? 'complete' : 'abort')),
      ).toBe(false)
      const committed = await kernelSnapshot(page)
      expect(committed.journal.length).toBe(before.journal.length + (outcome === 'unknown' ? 0 : 1))
      await restoreFault(page)
      await page.context().setOffline(false)
      await expect.poll(barrier.observed).toBe(true)
      await expect(page.locator('.workshop-shell')).toHaveCount(0)
      await expect(orderCard(page)).toHaveCount(0)
      barrier.release()
      await waitForReady(page)
      if (outcome === 'pending') await releaseJournalCompletion(page)
      // The native-completion barrier is before the kernel's posttransaction fence.
      // Re-verification invalidates that source, so pending returns UNKNOWN despite
      // the test independently observing committed journal bytes.
      await expect(orderCard(page).getByRole('alert')).toHaveText(
        outcome === 'unavailable' ? COMMITTED : UNKNOWN,
      )
      for (const button of await orderCard(page).locator('.order-actions button').all()) {
        await expect(button).toBeDisabled()
        await button.evaluate((el) => (el as HTMLButtonElement).click())
      }
      // Sync may append delivery events/update cache. Immutable authored journal
      // identity, not all mutable delivery/cache bytes, must remain unchanged.
      expect((await kernelSnapshot(page)).journal).toEqual(committed.journal)
      await expect(page.locator('body')).not.toContainText(CANARY)
      expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([])
      await info.attach(`transition-visit-${outcome}`, {
        body: await page.screenshot({ fullPage: true }),
        contentType: 'image/png',
      })
    } finally {
      await releaseJournalCompletion(page)
      await restoreFault(page)
      await barrier.dispose()
    }
  })

test('transition visit late native callback delivery preserves displayed new-login uncertainty', async ({
  page,
  request,
}, info) => {
  const seeded = await seedWorkshop(page, request)
  const id = seeded.orders[3]!
  await holdJournalCompletion(page, {
    entityType: 'service_order',
    orderId: id,
    transitionAction: 'start_diagnosis',
  })
  try {
    await orderCard(page).getByRole('button', { name: 'Iniciar diagnóstico', exact: true }).click()
    await waitForJournalBarrier(page)
    const committed = await kernelSnapshot(page)
    page.once('dialog', (dialog) => void dialog.accept())
    await page.getByRole('button', { name: 'Cerrar esta sesión', exact: true }).click()
    await expect(page.locator('.workshop-shell')).toHaveCount(0)
    await page.context().setOffline(false)
    await inPlaceLogin(page, seeded.username)
    await expect(
      orderCard(page).getByRole('button', { name: 'Autorizar', exact: true }),
    ).toBeEnabled()
    await installFault(page, id, 'preparation')
    await orderCard(page).getByRole('button', { name: 'Autorizar', exact: true }).click()
    await expect(orderCard(page).getByRole('alert')).toHaveText(UNKNOWN)
    expect(await page.evaluate(() => (window as ProbeWindow).orderTransitionProbe!.injected)).toBe(
      1,
    )
    await restoreFault(page)
    await releaseJournalCompletion(page)
    // Observe old native callback delivery and the next rendered frame only.
    // This is not full controller settlement/token-isolation proof: the new and
    // old UNKNOWN feedback are indistinguishable. The controller test awaits the
    // original promise and verifies the replacement snapshot exactly.
    await page.evaluate(
      () => new Promise<void>((resolve) => requestAnimationFrame(() => resolve())),
    )
    await expect(orderCard(page).getByRole('alert')).toHaveText(UNKNOWN)
    await expect(
      orderCard(page).getByRole('button', { name: 'Autorizar', exact: true }),
    ).toBeDisabled()
    expect((await kernelSnapshot(page)).journal).toEqual(committed.journal)
    await expect(page.locator('body')).not.toContainText(COMMITTED)
    await expect(page.locator('body')).not.toContainText(CANARY)
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([])
    await info.attach('transition-visit-new-login', {
      body: await page.screenshot({ fullPage: true }),
      contentType: 'image/png',
    })
  } finally {
    await releaseJournalCompletion(page)
    await restoreFault(page)
  }
})

test('transition visit real capability revocation preserves auth fence and hides old protection', async ({
  page,
  request,
}, info) => {
  const seeded = await seedWorkshop(page, request)
  const id = seeded.orders[3]!
  await installFault(page, id, 'quota')
  try {
    await orderCard(page).getByRole('button', { name: 'Iniciar diagnóstico', exact: true }).click()
    await expect(orderCard(page).getByRole('alert')).toHaveText(UNKNOWN)
    await restoreFault(page)
    const before = await kernelSnapshot(page)
    const partition = before.partition.partitionId
    const owner = await apiLogin(request, 'e2e-owner')
    const patch = await request.patch(`/api/v1/admin/users/${seeded.userId}`, {
      headers: await writeHeaders(request, owner, seeded.locationId),
      data: {
        expected_version: 1,
        capabilities: FULL_CAPABILITIES.filter((c) => c !== 'bicycles.write'),
      },
    })
    expect(patch.status(), await patch.text()).toBe(200)
    // Actual capability edits increment session_version and invalidate the bearer.
    // Do not forge a ready context to claim this is a same-session scope switch.
    await page.context().setOffline(false)
    await expect(page.locator('.workshop-shell')).toHaveCount(0)
    await expect(
      page.locator('[data-runtime-state="HELD"], [data-runtime-state="LOCKED"]'),
    ).toBeVisible()
    await expect(page.locator('body')).not.toContainText(UNKNOWN)
    await expect(page.locator('body')).not.toContainText(id)
    await expect(page.locator('body')).not.toContainText(CANARY)
    expect((await kernelSnapshot(page, partition)).journal).toEqual(before.journal)
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([])
    await info.attach('transition-visit-revoked', {
      body: await page.screenshot({ fullPage: true }),
      contentType: 'image/png',
    })
  } finally {
    await restoreFault(page)
  }
})

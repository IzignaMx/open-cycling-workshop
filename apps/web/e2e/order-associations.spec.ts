import { expect, test } from '@playwright/test'
import {
  createCaseIdentity,
  createCustomer,
  kernelSnapshot,
  login,
  revealOrder,
  waitForApplied,
  waitForConfirmed,
  waitForReady,
} from './helpers/authenticated-workshop.js'
import { fillIntake, savedOrder } from './helpers/orders.js'

test('saved order identifies its local customer and bicycle offline before and after reload without writes', async ({
  page,
  request,
}) => {
  const identity = await createCaseIdentity(request)
  await login(page, identity)
  const name = `Cliente lectura ${crypto.randomUUID()}`
  const customer = await createCustomer(page, name)
  await waitForApplied(page, customer.mutationId)
  await waitForConfirmed(page, customer)
  await page.context().setOffline(true)
  const problem = `Bicicleta lectura ${crypto.randomUUID()}`
  await fillIntake(page, customer.entityId, problem, true)
  await page.getByRole('button', { name: 'Guardar orden', exact: true }).click()
  const order = await savedOrder(page, problem)
  const before = (await kernelSnapshot(page)).journal
  const card = page.getByRole('listitem', { name: `Orden ${problem}`, exact: true })
  const button = card.getByRole('button', { name: 'Ver cliente y bicicleta', exact: true })
  await button.focus()
  await page.keyboard.press('Enter')
  await expect(card.locator('.order-associations')).toContainText(name)
  await expect(card.locator('.order-associations')).toContainText('Trek Marlin')
  await expect(card.locator('.order-associations')).toContainText(
    order.envelope.payload.bicycle_id as string,
  )
  expect((await kernelSnapshot(page)).journal).toEqual(before)
  await card
    .getByRole('button', { name: 'Cerrar datos de cliente y bicicleta', exact: true })
    .click()
  await expect(button).toHaveAttribute('aria-expanded', 'false')
  await expect(button).toBeFocused()
  await expect(card.locator('.order-associations')).not.toContainText(name)
  await button.click()
  await expect(button).toHaveAttribute('aria-expanded', 'true')
  await expect(card.locator('.order-associations')).toContainText(name)

  for (const label of ['Banco de trabajo', 'Plano técnico', 'Ritmo modular', 'Turno nocturno']) {
    await page.getByRole('button', { name: 'Personalización', exact: true }).click()
    await page.getByRole('radio', { name: new RegExp(label) }).check()
    await page.getByRole('button', { name: 'Cerrar personalización' }).click()
    await expect(card.locator('.order-associations')).toContainText(name)
    for (const width of [1280, 320]) {
      await page.setViewportSize({ width, height: 900 })
      const box = await card.locator('.order-associations').boundingBox()
      expect(box!.x).toBeGreaterThanOrEqual(0)
      expect(box!.x + box!.width).toBeLessThanOrEqual(width + 1)
    }
    await page.setViewportSize({ width: 1280, height: 900 })
  }
  const positions = await card.evaluate((el) => ({
    actions: el.querySelector('.order-actions')!.getBoundingClientRect().top,
    details: el.querySelector('.order-associations')!.getBoundingClientRect().top,
  }))
  expect(positions.details).toBeGreaterThan(positions.actions)
  await page.reload({ waitUntil: 'domcontentloaded' })
  await waitForReady(page)
  await revealOrder(page, problem)
  await expect(card.locator('.order-associations')).not.toContainText(name)
  await button.click()
  await expect(card.locator('.order-associations')).toContainText(name)
  await expect(card.locator('.order-associations')).toContainText('Trek Marlin')
  expect((await kernelSnapshot(page)).journal).toEqual(before)
})

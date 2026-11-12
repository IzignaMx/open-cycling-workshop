import { expect, test } from '@playwright/test'
import {
  createCaseIdentity,
  createCustomer,
  kernelSnapshot,
  login,
  revealOrder,
  sessionToken,
  waitForApplied,
  waitForConfirmed,
  waitForReady,
} from './helpers/authenticated-workshop.js'
import { appliedOrder, fillIntake } from './helpers/orders.js'

test('optional transition note survives view replacement and saved offline reload, then syncs once', async ({
  page,
  request,
}) => {
  const identity = await createCaseIdentity(request)
  await login(page, identity)
  const problem = `Nota de cambio ${crypto.randomUUID()}`
  const customer = await createCustomer(page, `Cliente ${problem}`)
  await waitForApplied(page, customer.mutationId)
  await waitForConfirmed(page, customer)
  await fillIntake(page, customer.entityId, problem, false)
  await page.getByRole('button', { name: 'Guardar orden', exact: true }).click()
  const order = await appliedOrder(page, problem)
  const token = await sessionToken(page)
  await page.context().setOffline(true)
  await revealOrder(page, problem)
  const card = page.getByRole('listitem', { name: `Orden ${problem}`, exact: true })
  const note = card.getByLabel('Nota para el próximo cambio (opcional)', { exact: true })
  await note.fill('  Revisar\n  cadena <roja>  ')
  const before = (await kernelSnapshot(page)).journal
  await page.getByLabel('Buscar órdenes', { exact: true }).fill('sin-coincidencias')
  await expect(card).toHaveCount(0)
  await page.getByRole('button', { name: 'Limpiar filtros', exact: true }).click()
  await expect(note).toHaveValue('  Revisar\n  cadena <roja>  ')
  const dismissal = page.waitForEvent('dialog').then(async (dialog) => {
    await dialog.dismiss()
    return dialog.message()
  })
  await page.getByRole('button', { name: 'Cerrar esta sesión', exact: true }).click()
  expect(await dismissal).toContain('formularios')
  await expect(note).toHaveValue('  Revisar\n  cadena <roja>  ')
  expect((await kernelSnapshot(page)).journal).toEqual(before)
  await card.getByRole('button', { name: 'Iniciar diagnóstico', exact: true }).focus()
  await page.keyboard.press('Enter')
  await expect(note).toHaveValue('')
  await expect(card.getByText('En diagnóstico', { exact: true })).toBeVisible()
  const snapshot = await kernelSnapshot(page)
  const transition = snapshot.journal.find(
    (row) => row.entityId === order.entityId && row.envelope.operation === 'update',
  )!
  expect(transition.envelope.payload.transition).toMatchObject({
    action: 'start_diagnosis',
    note: 'Revisar cadena <roja>',
  })
  await page.reload({ waitUntil: 'domcontentloaded' })
  await waitForReady(page)
  await revealOrder(page, problem)
  await card.getByRole('button', { name: 'Ver historial', exact: true }).click()
  await card.locator('.order-history summary').click()
  await expect(card.locator('.order-history-note')).toHaveText(
    'Nota del cambio: Revisar cadena <roja>',
  )
  await expect(card.locator('roja')).toHaveCount(0)
  expect((await kernelSnapshot(page)).journal).toEqual(snapshot.journal)
  await page.context().setOffline(false)
  await waitForApplied(page, transition.mutationId)
  const events = await request.get(`/api/v1/service-orders/${order.entityId}/events`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  expect(events.status()).toBe(200)
  const saved = (await events.json()).filter(
    (event: { action: string }) => event.action === 'start_diagnosis',
  )
  expect(saved).toHaveLength(1)
  expect(saved[0]).toMatchObject({ note: 'Revisar cadena <roja>', actor_id: identity.userId })
})

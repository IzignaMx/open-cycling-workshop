import { expect, test } from '@playwright/test'
import {
  createCaseIdentity,
  createCustomer,
  kernelSnapshot,
  login,
  waitForApplied,
  waitForConfirmed,
} from './helpers/authenticated-workshop.js'
import { fillIntake, savedOrder } from './helpers/orders.js'

test('local order filters combine, clear and follow offline transitions without writing data', async ({
  page,
  request,
}) => {
  const identity = await createCaseIdentity(request)
  await login(page, identity)
  const problem = `Filtro frenos ${crypto.randomUUID()}`
  const customer = await createCustomer(page, `Cliente ${problem}`)
  await waitForApplied(page, customer.mutationId)
  await waitForConfirmed(page, customer)
  await page.context().setOffline(true)
  await fillIntake(page, customer.entityId, problem, false)
  await page.getByRole('button', { name: 'Guardar orden', exact: true }).click()
  await savedOrder(page, problem)
  const card = page.getByRole('listitem', { name: `Orden ${problem}`, exact: true })
  const state = page.getByRole('combobox', { name: 'Estado de la orden', exact: true })
  const priority = page.getByRole('combobox', { name: 'Prioridad de la orden', exact: true })
  const search = page.getByRole('searchbox', { name: 'Buscar órdenes', exact: true })
  const clear = page.getByRole('button', { name: 'Limpiar filtros', exact: true })
  const before = (await kernelSnapshot(page)).journal
  await state.selectOption('INTAKE')
  await priority.selectOption('urgent')
  await expect(card).toHaveCount(0)
  await expect(
    page.getByText('No hay órdenes que coincidan. Cambia o limpia los filtros.'),
  ).toBeVisible()
  await priority.selectOption('high')
  await expect(card).toBeVisible()
  await search.fill(` ${problem.toUpperCase()} `)
  await expect(card).toBeVisible()
  await state.selectOption('WAITING_FOR_PARTS')
  await expect(card).toHaveCount(0)
  await clear.click()
  await expect(state).toHaveValue('')
  await expect(priority).toHaveValue('')
  await expect(search).toHaveValue('')
  await expect(clear).toBeDisabled()
  await expect(card).toBeVisible()
  expect((await kernelSnapshot(page)).journal).toEqual(before)
  await state.selectOption('INTAKE')
  await search.fill(problem)
  await card.getByRole('button', { name: 'Iniciar diagnóstico', exact: true }).click()
  await expect(card).toHaveCount(0)
  await state.selectOption('DIAGNOSIS')
  await expect(card).toBeVisible()
  await expect(card.getByText('En diagnóstico', { exact: true })).toBeVisible()
})

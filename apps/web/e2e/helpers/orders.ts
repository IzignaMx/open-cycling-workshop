import { expect, type Page } from '@playwright/test'
import { kernelSnapshot, waitForApplied, waitForConfirmed } from './authenticated-workshop.js'

export async function fillIntake(page: Page, customerId: string, problem: string, bicycle = true) {
  await page.getByLabel('Cliente', { exact: true }).selectOption(customerId)
  await page.getByLabel('Problema reportado').fill(problem)
  await page.getByLabel('Condición al recibir').fill('Manubrio rayado')
  await page.getByLabel('Accesorios', { exact: true }).fill('Canasto')
  await page.getByLabel('Prioridad', { exact: true }).selectOption('high')
  if (bicycle) {
    await page.getByLabel('Agregar bicicleta').check()
    await page.getByLabel('Marca', { exact: true }).fill('Trek Marlin')
    await page.getByLabel('Modelo', { exact: true }).fill('7')
  }
}

export async function savedOrder(page: Page, problem: string) {
  await expect(page.getByText('Orden guardada localmente', { exact: true })).toBeVisible()
  await expect
    .poll(async () =>
      (await kernelSnapshot(page)).journal.some(
        (item) =>
          item.entityType === 'service_order' &&
          item.envelope.operation === 'create' &&
          item.envelope.payload.reported_problem === problem,
      ),
    )
    .toBe(true)
  return (await kernelSnapshot(page)).journal.find(
    (item) =>
      item.entityType === 'service_order' &&
      item.envelope.operation === 'create' &&
      item.envelope.payload.reported_problem === problem,
  )!
}

export async function appliedOrder(page: Page, problem: string, timeout = 15_000) {
  await expect(page.getByText('Orden guardada localmente', { exact: true })).toBeVisible({
    timeout,
  })
  const operation = (await kernelSnapshot(page)).journal.find(
    (item) =>
      item.entityType === 'service_order' &&
      item.envelope.operation === 'create' &&
      item.envelope.payload.reported_problem === problem,
  )
  expect(operation, 'durable authored order must exist').toBeDefined()
  await waitForApplied(page, operation!.mutationId, timeout)
  await waitForConfirmed(page, operation!)
  return operation!
}

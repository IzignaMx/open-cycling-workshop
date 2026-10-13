import { expect, test, type Page } from '@playwright/test'

const ORGANIZATION_ID = '00000000-0000-7000-8000-000000000001'
const LOCATION_ID = '00000000-0000-7000-8000-000000000002'
const CUSTOMER_ID = '00000000-0000-7000-8000-000000000101'
const ENTITY_ID = '00000000-0000-7000-8000-000000000102'

async function snapshot(page: Page) {
  return page.evaluate(async () => {
    const request = indexedDB.open('ocwp')
    const database = await new Promise<IDBDatabase>((resolve, reject) => {
      request.onsuccess = () => resolve(request.result)
      request.onerror = () => reject(request.error)
    })
    try {
      const stores = ['customers', 'bicycles', 'serviceOrders', 'syncState']
      const transaction = database.transaction(stores, 'readonly')
      return await Promise.all(
        stores.map(
          (name) =>
            new Promise<Record<string, unknown>[]>((resolve, reject) => {
              const all = transaction.objectStore(name).getAll()
              all.onsuccess = () => resolve(all.result)
              all.onerror = () => reject(all.error)
            }),
        ),
      )
    } finally {
      database.close()
    }
  })
}

for (const entityType of ['bicycle', 'service_order']) {
  test(`foreign ${entityType} payload rolls back the whole pull page across reload`, async ({
    page,
  }) => {
    // Only the change feed is fault-injected. Login, app shell, Dexie and its
    // IndexedDB transactions use the normal production-PWA journey.
    let phase: 'initial' | 'invalid' | 'corrected' = 'initial'
    const observedCursors: number[] = []
    const common = {
      organization_id: ORGANIZATION_ID,
      location_id: LOCATION_ID,
      created_at: '2026-10-13T10:00:00Z',
      updated_at: '2026-10-13T10:00:00Z',
      version: 1,
    }
    const customer = {
      cursor: 1,
      entity_type: 'customer',
      entity_id: CUSTOMER_ID,
      organization_id: ORGANIZATION_ID,
      location_id: LOCATION_ID,
      payload: { ...common, customer_id: CUSTOMER_ID, display_name: 'Original scoped customer' },
    }
    await page.route('**/api/v1/sync/changes?**', async (route) => {
      const cursor = Number(new URL(route.request().url()).searchParams.get('cursor'))
      observedCursors.push(cursor)
      if (phase === 'initial') {
        await route.fulfill({
          json: { items: cursor < 1 ? [customer] : [], next_cursor: 1, has_more: false },
        })
        return
      }
      const payload = {
        ...common,
        // Exercise both isolation dimensions against correctly scoped envelopes.
        organization_id: phase === 'invalid' ? 'foreign-organization' : ORGANIZATION_ID,
        location_id: phase === 'invalid' ? 'foreign-location' : LOCATION_ID,
        customer_id: CUSTOMER_ID,
        bicycle_id: ENTITY_ID,
        order_id: ENTITY_ID,
        brand: 'Recovered bicycle',
        state: 'INTAKE',
        reported_problem: 'Recovered order',
      }
      await route.fulfill({
        json: {
          items:
            cursor < 3
              ? [
                  {
                    ...customer,
                    cursor: 2,
                    payload: { ...customer.payload, display_name: 'Updated scoped customer' },
                  },
                  {
                    cursor: 3,
                    entity_type: entityType,
                    entity_id: ENTITY_ID,
                    organization_id: ORGANIZATION_ID,
                    location_id: LOCATION_ID,
                    payload,
                  },
                ]
              : [],
          next_cursor: 3,
          has_more: false,
        },
      })
    })

    await page.goto('/')
    await page.getByLabel('Organización').fill(ORGANIZATION_ID)
    await page.getByLabel('Usuario').fill('e2e-admin')
    await page.getByLabel('Contraseña').fill('ocwp-e2e-password')
    await page.getByRole('button', { name: 'Iniciar sesión' }).click()
    await expect(page.getByLabel('Estado de sincronización')).toContainText('Sincronizado')
    const baseline = await snapshot(page)
    expect(baseline[0][0].display_name).toBe('Original scoped customer')
    expect(baseline[3][0].cursor).toBe(1)

    phase = 'invalid'
    await page.getByRole('button', { name: 'Sincronizar ahora' }).click()
    await expect(page.getByLabel('Estado de sincronización')).toContainText(
      'Sincronización interrumpida',
    )
    // The earlier valid update must roll back along with the foreign row and cursor.
    expect(await snapshot(page)).toEqual(baseline)
    await page.reload()
    await expect(page.getByLabel('Estado de sincronización')).toContainText(
      'Sincronización interrumpida',
    )
    expect(await snapshot(page)).toEqual(baseline)
    expect(observedCursors.at(-1)).toBe(1)

    phase = 'corrected'
    await page.getByRole('button', { name: 'Sincronizar ahora' }).click()
    await expect(page.getByLabel('Estado de sincronización')).toContainText('Sincronizado')
    const recovered = await snapshot(page)
    expect(recovered[0][0].display_name).toBe('Updated scoped customer')
    const rows = recovered[entityType === 'bicycle' ? 1 : 2]
    expect(rows).toHaveLength(1)
    expect(rows[0].organization_id).toBe(ORGANIZATION_ID)
    expect(rows[0].location_id).toBe(LOCATION_ID)
    expect(recovered[3][0].cursor).toBe(3)
    await page.reload()
    await expect(page.getByLabel('Estado de sincronización')).toContainText('Sincronizado')
    expect(await snapshot(page)).toEqual(recovered)
  })
}

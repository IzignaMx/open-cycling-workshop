/** Explicit historical physical schemas; independent of the migration under test. */
export async function seedLegacyFixture(name: string, nativeVersion: number): Promise<void> {
  const logical = nativeVersion === 1 ? 1 : nativeVersion / 10
  const schemas: Record<string, string[]> = {
    customers: ['customer_id', 'organization_id', 'location_id', 'display_name', 'updated_at'],
    mutationQueue: [
      'mutation_id',
      'state',
      'organization_id',
      'location_id',
      'entity_type',
      'queued_at',
    ],
    syncState: ['key'],
    conflicts: ['mutation_id', 'entity_type', 'entity_id', 'recorded_at'],
  }
  if (logical >= 2) {
    schemas.syncState!.push('scope_key', 'organization_id', 'location_id')
    schemas.conflicts!.push('scope_key', 'organization_id', 'location_id')
  }
  if (logical >= 3)
    Object.assign(schemas, {
      bicycles: ['bicycle_id', 'organization_id', 'location_id', 'customer_id', 'updated_at'],
      serviceOrders: [
        'order_id',
        'organization_id',
        'location_id',
        'customer_id',
        'state',
        'updated_at',
      ],
      serviceOrderEvents: ['event_id', 'order_id', 'organization_id', 'occurred_at'],
    })
  if (logical >= 4) schemas.presentationPreferences = ['key']
  const request = indexedDB.open(name, nativeVersion)
  request.onupgradeneeded = () => {
    for (const [store, [keyPath, ...indexes]] of Object.entries(schemas)) {
      const table = request.result.createObjectStore(store, { keyPath: keyPath! })
      for (const index of indexes) table.createIndex(index, index)
    }
    const transaction = request.transaction!
    transaction.objectStore('mutationQueue').add({
      mutation_id: 'legacy',
      entity_type: 'service_order',
      state: 'retrying',
      payload: { transition: { actor_id: 'claimed-A' }, unknown: ['keep', null, 7] },
      untouched: true,
    })
    transaction.objectStore('conflicts').add({ mutation_id: 'old-conflict', unknown: true })
    transaction.objectStore('syncState').add({ key: 'legacy-cursor', cursor: 1000 })
    transaction
      .objectStore('customers')
      .add({ customer_id: 'legacy-customer', unknown: { keep: true } })
    if (logical >= 3) {
      transaction.objectStore('bicycles').add({ bicycle_id: 'legacy-bicycle', unknown: true })
      transaction.objectStore('serviceOrders').add({ order_id: 'legacy-order', unknown: true })
      transaction.objectStore('serviceOrderEvents').add({ event_id: 'legacy-event', unknown: true })
    }
    if (logical >= 4)
      transaction.objectStore('presentationPreferences').add({
        key: '["org","A","loc"]',
        logo: new Blob(['preserved-logo'], { type: 'image/png' }),
        unknown: true,
      })
  }
  const database = await new Promise<IDBDatabase>((resolve, reject) => {
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error)
  })
  database.close()
}

const id = '11111111-1111-4111-8111-111111111111'
const generation = '22222222-2222-4222-8222-222222222222'
export const witnessId = 'ffffffff-ffff-4fff-8fff-ffffffffffff'
export function captureFixture(now, CAPTURE_TTL_MS, canonicalJson) {
  const channel = {
    revision: 1,
    state: 'UNSENT',
    attemptId: null,
    contentStartedAt: now,
    contentExpiresAt: now + CAPTURE_TTL_MS,
  }
  const checkpoint = {
    format: 1,
    writerEpoch: generation,
    checkpointId: id,
    bindingKey: 'a'.repeat(64),
    scopeKey: 'b'.repeat(64),
    generation,
    closed: false,
    observedAt: now,
    customer: { ...channel },
    order: { ...channel },
  }
  const envelope = {
    format: 1,
    checkpointId: id,
    generation,
    revision: 1,
    firstPersistedAt: now,
    expiresAt: now + CAPTURE_TTL_MS,
  }
  const customer = {
    ...envelope,
    channel: 'customer',
    draft: { displayName: 'Synthetic control', email: '', phone: '' },
  }
  const future = {
    ...envelope,
    format: 2,
    channel: 'order',
    draft: { opaqueFuture: 'Synthetic future bytes', nested: ['preserve', 2] },
    retainedSelection: { customerId: '', priority: 'normal' },
  }
  // An expired orphan sorts after the target row. Its removal witnesses that real
  // App startup maintenance has run, including in the preservation control.
  const witness = {
    ...customer,
    checkpointId: witnessId,
    firstPersistedAt: now - 2 * CAPTURE_TTL_MS,
    expiresAt: now - CAPTURE_TTL_MS,
  }
  const mutation = {
    mutation_id: '33333333-3333-4333-8333-333333333333',
    entity_type: 'customer',
    entity_id: '44444444-4444-4444-8444-444444444444',
    operation: 'create',
    organization_id: 'synthetic-org',
    location_id: 'synthetic-location',
    base_version: null,
    occurred_at: new Date(now).toISOString(),
    payload: { display_name: 'Synthetic journal', email: '', phone: '' },
  }
  const journal = {
    mutationId: mutation.mutation_id,
    principalKey: JSON.stringify(['https://synthetic.invalid', 'synthetic-org', 'synthetic-user']),
    organizationId: mutation.organization_id,
    locationId: mutation.location_id,
    entityType: mutation.entity_type,
    entityId: mutation.entity_id,
    authoredUnderEpoch: 'a'.repeat(43),
    authoredDatasetIncarnation: generation,
    localSequence: 1,
    dependsOn: [],
    envelope: mutation,
    envelopeCanonical: canonicalJson(mutation),
    optimistic: {
      customer_id: mutation.entity_id,
      organization_id: mutation.organization_id,
      location_id: mutation.location_id,
      version: 1,
      ...mutation.payload,
    },
    createdAt: mutation.occurred_at,
  }
  return { checkpoint, customer, future, witness, journal }
}

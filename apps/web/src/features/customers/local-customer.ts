import type { LocalCustomer, QueuedMutation } from '../../local/types.js'

export interface CreateCustomerInput {
  organizationId: string
  locationId: string
  displayName: string
  email?: string | null
  phone?: string | null
}

export interface LocalCustomerCreateDependencies {
  now(): string
  newId(): string
}

export interface LocalCustomerCreateResult {
  customer: LocalCustomer
  mutation: QueuedMutation
}

function normalizeName(value: string): string {
  const normalized = value.trim().replace(/\s+/g, ' ')
  if (!normalized) throw new Error('El nombre es obligatorio')
  return normalized
}

export function buildLocalCustomerCreate(
  input: CreateCustomerInput,
  dependencies: LocalCustomerCreateDependencies,
): LocalCustomerCreateResult {
  const now = dependencies.now()
  const customerId = dependencies.newId()
  const customer: LocalCustomer = {
    customer_id: customerId,
    organization_id: input.organizationId,
    location_id: input.locationId,
    display_name: normalizeName(input.displayName),
    email: input.email?.trim().toLowerCase() || null,
    phone: input.phone?.trim() || null,
    created_at: now,
    updated_at: now,
    version: 1,
  }
  const mutation: QueuedMutation = {
    mutation_id: dependencies.newId(),
    entity_type: 'customer',
    entity_id: customerId,
    operation: 'create',
    organization_id: input.organizationId,
    location_id: input.locationId,
    base_version: null,
    occurred_at: now,
    payload: {
      display_name: customer.display_name,
      email: customer.email,
      phone: customer.phone,
    },
    state: 'pending',
    queued_at: now,
  }
  return { customer, mutation }
}

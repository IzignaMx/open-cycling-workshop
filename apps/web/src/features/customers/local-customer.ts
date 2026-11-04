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
  // Count Unicode codepoints in the existing prepared value, not UTF-16 units.
  // Reject before allocating IDs or constructing a durable command; never truncate a draft.
  const displayName = normalizeName(input.displayName)
  const email = input.email?.trim().toLowerCase() || null
  const phone = input.phone?.trim() || null
  if ([...displayName].length > 200) throw new Error('El nombre no puede superar 200 caracteres')
  if (email !== null && [...email].length > 320)
    throw new Error('El correo no puede superar 320 caracteres')
  if (phone !== null && [...phone].length > 64)
    throw new Error('El teléfono no puede superar 64 caracteres')
  const now = dependencies.now()
  const customerId = dependencies.newId()
  const customer: LocalCustomer = {
    customer_id: customerId,
    organization_id: input.organizationId,
    location_id: input.locationId,
    display_name: displayName,
    email,
    phone,
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

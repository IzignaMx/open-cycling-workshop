import { pythonWhitespace, hasPythonText } from '../../shared/python-whitespace.js'
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

const serverEdgeWhitespace = new RegExp(`^[${pythonWhitespace}]+|[${pythonWhitespace}]+$`, 'gu')
const serverEmail = new RegExp(
  `^[^@${pythonWhitespace}]+@[^@${pythonWhitespace}]+\\.[^@${pythonWhitespace}]+$`,
  'u',
)

function normalizeName(value: string): string {
  const normalized = value.trim().replace(/\s+/g, ' ')
  if (!hasPythonText(normalized)) throw new Error('El nombre es obligatorio')
  return normalized
}

export type CustomerFieldsInput = Pick<CreateCustomerInput, 'displayName' | 'email' | 'phone'>

function prepareCustomerFields(input: CustomerFieldsInput) {
  // JSON preserves lone UTF-16 surrogates, but the server/storage text boundary does not.
  // Iterate code points so valid surrogate pairs (including astral names) remain accepted.
  for (const value of [input.displayName, input.email, input.phone]) {
    if (value == null) continue
    for (const character of value) {
      const point = character.codePointAt(0)!
      if (point === 0 || (point >= 0xd800 && point <= 0xdfff))
        throw new Error('Los datos del cliente contienen caracteres no válidos')
    }
  }
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
  const emailProjection = email?.replace(serverEdgeWhitespace, '') || null
  if (emailProjection !== null && !serverEmail.test(emailProjection))
    throw new Error('El correo no es válido')
  return { display_name: displayName, email, phone }
}

export function buildLocalCustomerCreate(
  input: CreateCustomerInput,
  dependencies: LocalCustomerCreateDependencies,
): LocalCustomerCreateResult {
  const fields = prepareCustomerFields(input)
  const now = dependencies.now()
  const customerId = dependencies.newId()
  const customer: LocalCustomer = {
    customer_id: customerId,
    organization_id: input.organizationId,
    location_id: input.locationId,
    ...fields,
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

/** Full replacement of the three editable fields; identity and scope come from the admitted row. */
export function buildLocalCustomerUpdate(
  previous: LocalCustomer,
  input: CustomerFieldsInput,
  dependencies: LocalCustomerCreateDependencies,
): LocalCustomerCreateResult {
  const fields = prepareCustomerFields(input)
  if (
    !Number.isSafeInteger(previous.version) ||
    previous.version < 1 ||
    !Number.isSafeInteger(previous.version + 1)
  )
    throw new Error('Invalid customer base version')
  const now = dependencies.now()
  const customer: LocalCustomer = {
    ...previous,
    ...fields,
    updated_at: now,
    version: previous.version + 1,
  }
  return {
    customer,
    mutation: {
      mutation_id: dependencies.newId(),
      entity_type: 'customer',
      entity_id: previous.customer_id,
      operation: 'update',
      organization_id: previous.organization_id,
      location_id: previous.location_id,
      base_version: previous.version,
      occurred_at: now,
      payload: fields,
      state: 'pending',
      queued_at: now,
    },
  }
}

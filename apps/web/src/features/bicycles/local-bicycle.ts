import { hasPythonText } from '../../shared/python-whitespace.js'
import type { LocalBicycle } from '../../local/bicycle-types.js'
import type { QueuedMutation } from '../../local/types.js'

export interface CreateBicycleInput {
  organizationId: string
  locationId: string
  customerId: string
  brand: string
  model?: string | null
  bicycleType?: string | null
  wheelSize?: string | null
  notes?: string | null
}

export interface LocalBicycleCreateDependencies {
  now(): string
  newId(): string
}

export interface LocalBicycleCreateResult {
  bicycle: LocalBicycle
  mutation: QueuedMutation
}

function collapse(value: string): string {
  return value.trim().replace(/\s+/g, ' ')
}

export function buildLocalBicycleCreate(
  input: CreateBicycleInput,
  dependencies: LocalBicycleCreateDependencies,
): LocalBicycleCreateResult {
  const brand = collapse(input.brand)
  if (!hasPythonText(brand)) throw new Error('La marca de la bicicleta es obligatoria')
  const model = input.model?.trim() ? collapse(input.model) : null
  const bicycleType = input.bicycleType?.trim() || null
  const wheelSize = input.wheelSize?.trim() || null
  const notes = input.notes?.trim() || null
  if ([...brand].length > 120) throw new Error('La marca no puede superar 120 caracteres')
  if (model !== null && [...model].length > 120)
    throw new Error('El modelo no puede superar 120 caracteres')
  if (bicycleType !== null && [...bicycleType].length > 60)
    throw new Error('El tipo de bicicleta no puede superar 60 caracteres')
  if (wheelSize !== null && [...wheelSize].length > 30)
    throw new Error('El tamaño de rueda no puede superar 30 caracteres')
  if (notes !== null && [...notes].length > 2000)
    throw new Error('Las notas de la bicicleta no pueden superar 2000 caracteres')
  const now = dependencies.now()
  const bicycleId = dependencies.newId()
  const bicycle: LocalBicycle = {
    bicycle_id: bicycleId,
    customer_id: input.customerId,
    organization_id: input.organizationId,
    location_id: input.locationId,
    brand,
    model,
    bicycle_type: bicycleType,
    wheel_size: wheelSize,
    notes,
    created_at: now,
    updated_at: now,
    version: 1,
  }
  const mutation: QueuedMutation = {
    mutation_id: dependencies.newId(),
    entity_type: 'bicycle',
    entity_id: bicycleId,
    operation: 'create',
    organization_id: input.organizationId,
    location_id: input.locationId,
    base_version: null,
    occurred_at: now,
    payload: {
      customer_id: input.customerId,
      brand,
      model,
      bicycle_type: bicycle.bicycle_type,
      wheel_size: bicycle.wheel_size,
      notes: bicycle.notes,
    },
    state: 'pending',
    queued_at: now,
  }
  return { bicycle, mutation }
}

import type { EntityType, MutationResult } from '../sync/types.js'
import type { LocalCommand, OwnedOperation, VerifiedAccessContext } from './types.js'

/** Reject non-JSON values instead of silently dropping undefined, NaN, dates or prototypes. */
export function canonicalJson(value: unknown): string {
  if (value === null || typeof value === 'string' || typeof value === 'boolean')
    return JSON.stringify(value)
  if (typeof value === 'number' && Number.isFinite(value)) return JSON.stringify(value)
  if (Array.isArray(value)) return `[${Array.from(value, canonicalJson).join(',')}]`
  if (
    typeof value === 'object' &&
    value !== null &&
    Object.getPrototypeOf(value) === Object.prototype
  ) {
    return `{${Object.keys(value)
      .sort()
      .map(
        (key) => `${JSON.stringify(key)}:${canonicalJson((value as Record<string, unknown>)[key])}`,
      )
      .join(',')}}`
  }
  throw new Error('Invalid JSON value in immutable operation')
}

export function entityCapability(entityType: string, action: 'read' | 'write'): string {
  const entity = new Map([
    ['customer', 'customers'],
    ['bicycle', 'bicycles'],
    ['service_order', 'orders'],
  ]).get(entityType)
  if (!entity) throw new Error('Unknown entity capability')
  return `${entity}.${action}`
}
export function requireCapability(context: VerifiedAccessContext, capability: string): void {
  if (!context.capabilities.includes(capability))
    throw new Error(`Missing capability: ${capability}`)
}
export function validateProjection(
  entityType: EntityType,
  entityId: string,
  payload: Record<string, unknown>,
  context: VerifiedAccessContext,
): void {
  const idField = { customer: 'customer_id', bicycle: 'bicycle_id', service_order: 'order_id' }[
    entityType
  ]
  if (
    payload[idField] !== entityId ||
    payload.organization_id !== context.principal.organizationId ||
    payload.location_id !== context.selectedLocationId ||
    !Number.isSafeInteger(payload.version) ||
    (payload.version as number) < 1
  ) {
    throw new Error('Projection identity, scope or version mismatch')
  }
  canonicalJson(payload)
}
export function validateCommand(command: LocalCommand, context: VerifiedAccessContext): string {
  const envelope = command.envelope
  const canonical = canonicalJson(envelope)
  requireCapability(context, entityCapability(envelope.entity_type, 'write'))
  if (
    !envelope.mutation_id ||
    !envelope.entity_id ||
    envelope.organization_id !== context.principal.organizationId ||
    envelope.location_id !== context.selectedLocationId ||
    !['create', 'update'].includes(envelope.operation) ||
    !Number.isFinite(Date.parse(envelope.occurred_at)) ||
    (envelope.operation === 'create'
      ? envelope.base_version !== null
      : !Number.isSafeInteger(envelope.base_version) || (envelope.base_version ?? 0) < 1)
  ) {
    throw new Error('Invalid command identity, scope or base version')
  }
  validateProjection(envelope.entity_type, envelope.entity_id, command.optimistic, context)
  if (command.optimistic.version !== (envelope.base_version ?? 0) + 1)
    throw new Error('Optimistic command version mismatch')
  if (
    new Set(command.dependsOn).size !== command.dependsOn.length ||
    command.dependsOn.some((id) => typeof id !== 'string' || !id || id === envelope.mutation_id)
  )
    throw new Error('Invalid dependencies')
  canonicalJson(command.localEvents)
  return canonical
}
export function operationIntact(operation: OwnedOperation): boolean {
  const envelope = operation.envelope
  return (
    canonicalJson(envelope) === operation.envelopeCanonical &&
    envelope.mutation_id === operation.mutationId &&
    envelope.entity_type === operation.entityType &&
    envelope.entity_id === operation.entityId &&
    envelope.organization_id === operation.organizationId &&
    envelope.location_id === operation.locationId
  )
}
export function validateResults(
  operations: readonly OwnedOperation[],
  response: unknown,
): MutationResult[] {
  if (
    typeof response !== 'object' ||
    response === null ||
    !('results' in response) ||
    !Array.isArray(response.results) ||
    response.results.length !== operations.length
  )
    throw new Error('Invalid acknowledgement result count')
  const requested = new Map(operations.map((operation) => [operation.mutationId, operation]))
  const seen = new Set<string>()
  const results: MutationResult[] = []
  for (const raw of response.results as unknown[]) {
    if (typeof raw !== 'object' || raw === null) throw new Error('Invalid acknowledgement result')
    const result = raw as Record<string, unknown>
    const operation =
      typeof result.mutation_id === 'string' ? requested.get(result.mutation_id) : undefined
    if (!operation || seen.has(operation.mutationId) || result.entity_id !== operation.entityId)
      throw new Error('Acknowledgement identity mismatch')
    seen.add(operation.mutationId)
    if (result.status === 'applied') {
      if (
        !Number.isSafeInteger(result.entity_version) ||
        (result.entity_version as number) !== (operation.envelope.base_version ?? 0) + 1 ||
        result.error_code != null ||
        result.error_message != null
      )
        throw new Error('Invalid applied acknowledgement version')
    } else if (result.status === 'conflict') {
      if (
        result.entity_version !== null ||
        typeof result.error_code !== 'string' ||
        !result.error_code ||
        typeof result.error_message !== 'string'
      )
        throw new Error('Invalid conflict acknowledgement')
    } else throw new Error('Invalid acknowledgement status')
    // v1 has no scope/operation fields. If supplied, they must still agree with the batch.
    for (const field of ['organization_id', 'location_id', 'entity_type', 'operation'] as const) {
      if (field in result && result[field] !== operation.envelope[field])
        throw new Error('Acknowledgement scope/operation mismatch')
    }
    canonicalJson(result)
    results.push(structuredClone(result) as unknown as MutationResult)
  }
  return results
}

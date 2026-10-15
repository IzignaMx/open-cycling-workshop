/** Closed, volatile connected reads. Never a local inventory replica. */
export const INVENTORY_PAGE_SIZE = 50
export const MAX_INVENTORY_BODY_BYTES = 1024 * 1024
export type InventoryErrorCode =
  | 'stale_request'
  | 'invalid_session'
  | 'capability_denied'
  | 'network_error'
  | 'invalid_response'
  | 'unsupported_quantity'
  | 'unavailable'
export class InventoryHttpError extends Error {
  constructor(
    readonly code: InventoryErrorCode,
    readonly status: number | null = null,
  ) {
    super('No se pudo consultar el inventario.')
    this.name = 'InventoryHttpError'
  }
}
export function failInventory(
  code: InventoryErrorCode = 'invalid_response',
  status: number | null = null,
): never {
  throw new InventoryHttpError(code, status)
}
export interface InventoryScope {
  organizationId: string
  locationId: string
}
export interface InventoryProduct {
  product_id: string
  organization_id: string
  location_id: string
  sku: string
  name: string
  unit: string
  created_at: string
  updated_at: string
  version: number
}
export interface InventoryStock {
  product_id: string
  organization_id: string
  location_id: string
  available_quantity: number
}
export interface InventoryMovement {
  movement_id: string
  product_id: string
  organization_id: string
  location_id: string
  kind: 'ADJUST' | 'RESERVE' | 'RELEASE' | 'CONSUME'
  quantity: number
  occurred_at: string
}
export interface InventoryMovementPage {
  items: InventoryMovement[]
  next_cursor: string | null
}
export interface InventoryCursor {
  before_movement_id: string
  before_occurred_at: string
  location_id: string
  organization_id: string
  product_id: string
  version: 1
}
const scalar = (s: string) =>
  !/[\uD800-\uDBFF](?![\uDC00-\uDFFF])|(?<![\uD800-\uDBFF])[\uDC00-\uDFFF]/u.test(s)
export const validInventoryId = (v: unknown): v is string =>
  typeof v === 'string' &&
  [...v].length >= 1 &&
  [...v].length <= 36 &&
  !v.includes('\0') &&
  scalar(v)
const label = (v: unknown, max: number): v is string =>
  typeof v === 'string' &&
  [...v].length >= 1 &&
  [...v].length <= max &&
  !v.includes('\0') &&
  scalar(v)
function object(value: unknown, fields: string[]): Record<string, unknown> {
  if (
    !value ||
    typeof value !== 'object' ||
    Array.isArray(value) ||
    Object.keys(value).sort().join(',') !== [...fields].sort().join(',')
  )
    failInventory()
  return value as Record<string, unknown>
}
function scoped(value: Record<string, unknown>, scope: InventoryScope, productId?: string) {
  if (
    !validInventoryId(value.organization_id) ||
    !validInventoryId(value.location_id) ||
    !validInventoryId(value.product_id) ||
    value.organization_id !== scope.organizationId ||
    value.location_id !== scope.locationId ||
    (productId !== undefined && value.product_id !== productId)
  )
    failInventory()
}
/** Validate JSON lexemes and duplicate object keys before any number coercion.
 * A depth bound avoids adversarial recursion within the finite body budget. */
function safeJson(raw: string, stock = false): unknown {
  if (new TextEncoder().encode(raw).length > MAX_INVENTORY_BODY_BYTES) failInventory()
  let position = 0
  const whitespace = () => {
    while (/[\t\n\r ]/.test(raw[position] ?? 'x')) position++
  }
  const string = (): string => {
    const start = position++
    while (position < raw.length) {
      const character = raw[position++]
      if (character === '\\') position++
      else if (character === '"') {
        try {
          return JSON.parse(raw.slice(start, position)) as string
        } catch {
          return failInventory()
        }
      }
    }
    return failInventory()
  }
  const value = (depth: number, path: string[]) => {
    if (depth > 20) failInventory()
    whitespace()
    const character = raw[position]
    if (character === '"') {
      string()
      return
    }
    if (character === '{') {
      position++
      whitespace()
      const keys = new Set<string>()
      if (raw[position] === '}') {
        position++
        return
      }
      while (position < raw.length) {
        if (raw[position] !== '"') failInventory()
        const key = string()
        if (keys.has(key)) failInventory()
        keys.add(key)
        whitespace()
        if (raw[position++] !== ':') failInventory()
        value(depth + 1, [...path, key])
        whitespace()
        if (raw[position] === '}') {
          position++
          return
        }
        if (raw[position++] !== ',') failInventory()
        whitespace()
      }
      failInventory()
    }
    if (character === '[') {
      position++
      whitespace()
      if (raw[position] === ']') {
        position++
        return
      }
      while (position < raw.length) {
        value(depth + 1, [...path, '[]'])
        whitespace()
        if (raw[position] === ']') {
          position++
          return
        }
        if (raw[position++] !== ',') failInventory()
      }
      failInventory()
    }
    for (const literal of ['true', 'false', 'null']) {
      if (raw.startsWith(literal, position)) {
        position += literal.length
        return
      }
    }
    const match = /^-?[0-9][0-9.eE+-]*/.exec(raw.slice(position))
    if (!match || !/^(?:0|-?[1-9][0-9]*)$/.test(match[0])) failInventory()
    const number = Number(match[0])
    if (!Number.isSafeInteger(number))
      failInventory(
        stock && path.length === 1 && path[0] === 'available_quantity'
          ? 'unsupported_quantity'
          : 'invalid_response',
      )
    position += match[0].length
  }
  value(0, [])
  whitespace()
  if (position !== raw.length) failInventory()
  try {
    return JSON.parse(raw)
  } catch {
    return failInventory()
  }
}
function calendarDate(year: number, month: number, day: number) {
  const leap = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0)
  return (
    year >= 1 &&
    year <= 9999 &&
    month >= 1 &&
    month <= 12 &&
    day >= 1 &&
    day <= ([31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1] ?? 0)
  )
}
export function validMovementTime(value: unknown): value is string {
  if (typeof value !== 'string') return false
  const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})\.\d{6}Z$/.exec(value)
  return (
    !!m &&
    calendarDate(Number(m[1]), Number(m[2]), Number(m[3])) &&
    Number(m[4]) < 24 &&
    Number(m[5]) < 60 &&
    Number(m[6]) < 60
  )
}
function oldTime(value: unknown): value is string {
  if (typeof value !== 'string' || value.length > 40 || !Number.isFinite(Date.parse(value)))
    return false
  const m =
    /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})?$/.exec(
      value,
    )
  return (
    !!m &&
    calendarDate(Number(m[1]), Number(m[2]), Number(m[3])) &&
    Number(m[4]) < 24 &&
    Number(m[5]) < 60 &&
    Number(m[6]) < 60
  )
}
export function parseCatalog(raw: string, scope: InventoryScope): InventoryProduct[] {
  const values = safeJson(raw)
  if (!Array.isArray(values) || values.length > INVENTORY_PAGE_SIZE) failInventory()
  const seen = new Set<string>()
  return (values as unknown[]).map((value) => {
    const row = object(value, [
      'product_id',
      'organization_id',
      'location_id',
      'sku',
      'name',
      'unit',
      'created_at',
      'updated_at',
      'version',
    ])
    scoped(row, scope)
    if (
      !label(row.sku, 80) ||
      !label(row.name, 200) ||
      !label(row.unit, 30) ||
      !oldTime(row.created_at) ||
      !oldTime(row.updated_at) ||
      !Number.isSafeInteger(row.version) ||
      (row.version as number) < 1 ||
      seen.has(row.product_id as string)
    )
      failInventory()
    seen.add(row.product_id as string)
    return row as unknown as InventoryProduct
  })
}
export function parseStock(raw: string, scope: InventoryScope, productId: string): InventoryStock {
  const row = object(safeJson(raw, true), [
    'product_id',
    'organization_id',
    'location_id',
    'available_quantity',
  ])
  scoped(row, scope, productId)
  if (!Number.isSafeInteger(row.available_quantity)) failInventory()
  return row as unknown as InventoryStock
}
/** UTF-8/C ordering for valid Unicode scalar IDs, without UTF-16 or locale collation. */
export function compareCodePoints(a: string, b: string): number {
  const left = [...a],
    right = [...b]
  for (let i = 0; i < Math.min(left.length, right.length); i++) {
    const difference = left[i]!.codePointAt(0)! - right[i]!.codePointAt(0)!
    if (difference) return difference
  }
  return left.length - right.length
}
function compareTuple(
  a: { occurred_at: string; movement_id: string },
  b: { occurred_at: string; movement_id: string },
) {
  return a.occurred_at === b.occurred_at
    ? compareCodePoints(a.movement_id, b.movement_id)
    : a.occurred_at < b.occurred_at
      ? -1
      : 1
}
export function encodeCursor(cursor: InventoryCursor): string {
  const canonical = JSON.stringify({
    before_movement_id: cursor.before_movement_id,
    before_occurred_at: cursor.before_occurred_at,
    location_id: cursor.location_id,
    organization_id: cursor.organization_id,
    product_id: cursor.product_id,
    version: cursor.version,
  })
  return btoa(String.fromCharCode(...new TextEncoder().encode(canonical)))
    .replaceAll('+', '-')
    .replaceAll('/', '_')
    .replace(/=+$/, '')
}
export function decodeCursor(
  token: string,
  scope: InventoryScope,
  productId: string,
): InventoryCursor {
  if (token.length < 1 || token.length > 2048 || !/^[A-Za-z0-9_-]+$/.test(token)) failInventory()
  let raw: string
  try {
    const bytes = Uint8Array.from(atob(token.replaceAll('-', '+').replaceAll('_', '/')), (c) =>
      c.charCodeAt(0),
    )
    if (bytes.length > 1024) failInventory()
    raw = new TextDecoder('utf-8', { fatal: true }).decode(bytes)
  } catch {
    return failInventory()
  }
  const row = object(safeJson(raw), [
    'before_movement_id',
    'before_occurred_at',
    'location_id',
    'organization_id',
    'product_id',
    'version',
  ])
  scoped(row, scope, productId)
  if (
    row.version !== 1 ||
    !validInventoryId(row.before_movement_id) ||
    !validMovementTime(row.before_occurred_at)
  )
    failInventory()
  const cursor = row as unknown as InventoryCursor
  if (encodeCursor(cursor) !== token) failInventory()
  return cursor
}
export function parseMovementPage(
  raw: string,
  scope: InventoryScope,
  productId: string,
  before?: string,
  limit = INVENTORY_PAGE_SIZE,
): InventoryMovementPage {
  const page = object(safeJson(raw), ['items', 'next_cursor'])
  if (
    !Number.isSafeInteger(limit) ||
    limit < 1 ||
    limit > 100 ||
    !Array.isArray(page.items) ||
    page.items.length > limit ||
    (page.next_cursor !== null && typeof page.next_cursor !== 'string')
  )
    failInventory()
  const incoming = before === undefined ? null : decodeCursor(before, scope, productId)
  let previous =
    incoming === null
      ? null
      : { occurred_at: incoming.before_occurred_at, movement_id: incoming.before_movement_id }
  const seen = new Set<string>()
  const items = (page.items as unknown[]).map((value) => {
    const row = object(value, [
      'movement_id',
      'product_id',
      'organization_id',
      'location_id',
      'kind',
      'quantity',
      'occurred_at',
    ])
    scoped(row, scope, productId)
    if (
      !validInventoryId(row.movement_id) ||
      !['ADJUST', 'RESERVE', 'RELEASE', 'CONSUME'].includes(row.kind as string) ||
      !Number.isSafeInteger(row.quantity) ||
      !validMovementTime(row.occurred_at) ||
      seen.has(row.movement_id as string)
    )
      failInventory()
    const item = row as unknown as InventoryMovement
    if (previous !== null && compareTuple(item, previous) >= 0) failInventory()
    previous = item
    seen.add(item.movement_id)
    return item
  })
  if (page.next_cursor !== null) {
    const next = decodeCursor(page.next_cursor as string, scope, productId),
      last = items.at(-1)
    if (
      items.length !== limit ||
      !last ||
      next.before_movement_id !== last.movement_id ||
      next.before_occurred_at !== last.occurred_at
    )
      failInventory()
  }
  return { items, next_cursor: page.next_cursor as string | null }
}

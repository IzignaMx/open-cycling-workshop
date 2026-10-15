import type { BrandingLogoResponse, BrandingProfileResponse } from '@ocwp/api-client'
import { PALETTES } from '../../personalization/catalog.js'
import { isDatasetIncarnation } from '../../access-kernel/context.js'

export const MAX_BRANDING_BODY_BYTES = 393216
export const MAX_BRANDING_PNG_BYTES = 262144
export type { BrandingPutRequest } from '@ocwp/api-client'
export type BrandingLogo = BrandingLogoResponse
export type BrandingProfile = BrandingProfileResponse
function invalid(): never {
  throw new Error('Invalid branding profile')
}
function object(value: unknown, fields: readonly string[]): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return invalid()
  const record = value as Record<string, unknown>
  if (
    Object.keys(record).length !== fields.length ||
    !fields.every((key) => Object.hasOwn(record, key))
  )
    return invalid()
  return record
}
function integer(value: unknown, min: number, max: number): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < min || value > max)
    return invalid()
  return value
}
function identifier(value: unknown): string {
  if (typeof value !== 'string' || !value || [...value].length > 36 || value.includes('\0'))
    return invalid()
  return value
}
export function isNormalizedBrandingName(value: unknown): value is string {
  return (
    typeof value === 'string' &&
    value === value.trim() &&
    value === value.normalize('NFC') &&
    [...value].length >= 1 &&
    [...value].length <= 160 &&
    new TextEncoder().encode(value).byteLength <= 640 &&
    !/\p{C}/u.test(value)
  )
}
function timestamp(value: unknown): value is string {
  if (typeof value !== 'string') return false
  const matched =
    /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d{1,6})?(?:Z|([+-])(\d{2}):(\d{2}))$/.exec(
      value,
    )
  if (!matched) return false
  const year = Number(matched[1]),
    month = Number(matched[2]),
    day = Number(matched[3])
  const days = [
    31,
    year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0) ? 29 : 28,
    31,
    30,
    31,
    30,
    31,
    31,
    30,
    31,
    30,
    31,
  ]
  return (
    year >= 1 &&
    month >= 1 &&
    month <= 12 &&
    day >= 1 &&
    day <= days[month - 1]! &&
    Number(matched[4]) <= 23 &&
    Number(matched[5]) <= 59 &&
    Number(matched[6]) <= 59 &&
    (matched[7] === undefined || (Number(matched[8]) <= 23 && Number(matched[9]) <= 59)) &&
    Number.isFinite(Date.parse(value))
  )
}

/** Strict metadata-free server output. This checks bytes/CRC; safe decoding remains the server's job. */
function canonicalPng(bytes: Uint8Array): { width: number; height: number } {
  const signature = [137, 80, 78, 71, 13, 10, 26, 10]
  if (bytes.length < 45 || !signature.every((byte, i) => bytes[i] === byte)) return invalid()
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength)
  let offset = 8,
    chunks = 0,
    pixels = 0,
    width = 0,
    height = 0
  while (offset + 12 <= bytes.length && ++chunks <= 1024) {
    const length = view.getUint32(offset),
      end = offset + length + 12,
      type = view.getUint32(offset + 4)
    if (end > bytes.length) return invalid()
    let crc = 0xffffffff
    for (let i = offset + 4; i < end - 4; i++) {
      crc ^= bytes[i]!
      for (let bit = 0; bit < 8; bit++) crc = (crc >>> 1) ^ (crc & 1 ? 0xedb88320 : 0)
    }
    if ((crc ^ 0xffffffff) >>> 0 !== view.getUint32(end - 4)) return invalid()
    if (offset === 8) {
      if (type !== 0x49484452 || length !== 13) return invalid()
      width = integer(view.getUint32(offset + 8), 1, 512)
      height = integer(view.getUint32(offset + 12), 1, 512)
      if (
        bytes[offset + 16] !== 8 ||
        ![2, 6].includes(bytes[offset + 17]!) ||
        bytes[offset + 18] !== 0 ||
        bytes[offset + 19] !== 0 ||
        bytes[offset + 20] !== 0
      )
        return invalid()
    } else if (type === 0x49444154) {
      pixels += length
    } else if (type === 0x49454e44) {
      if (length !== 0 || pixels === 0 || end !== bytes.length) return invalid()
      return { width, height }
    } else return invalid()
    offset = end
  }
  return invalid()
}
async function parseLogo(
  value: unknown,
  state: 'available' | 'unavailable',
): Promise<BrandingLogo> {
  const input = object(value, [
    'sha256',
    'byte_count',
    'width',
    'height',
    'mime_type',
    'png_base64',
  ])
  if (
    typeof input.sha256 !== 'string' ||
    !/^[a-f0-9]{64}$/.test(input.sha256) ||
    input.mime_type !== 'image/png'
  )
    return invalid()
  const logo: BrandingLogo = {
    sha256: input.sha256,
    byte_count: integer(input.byte_count, 1, MAX_BRANDING_PNG_BYTES),
    width: integer(input.width, 1, 512),
    height: integer(input.height, 1, 512),
    mime_type: 'image/png',
    png_base64: null,
  }
  if (state === 'unavailable') {
    if (input.png_base64 !== null) return invalid()
    return logo
  }
  const encoded = input.png_base64
  if (
    typeof encoded !== 'string' ||
    encoded.length > Math.ceil(MAX_BRANDING_PNG_BYTES / 3) * 4 ||
    encoded.length % 4 !== 0 ||
    !/^[A-Za-z0-9+/]+={0,2}$/.test(encoded)
  )
    return invalid()
  let binary: string
  try {
    binary = atob(encoded)
  } catch {
    return invalid()
  }
  if (binary.length !== logo.byte_count || btoa(binary) !== encoded) return invalid()
  const bytes = Uint8Array.from(binary, (value) => value.charCodeAt(0))
  const dimensions = canonicalPng(bytes)
  if (dimensions.width !== logo.width || dimensions.height !== logo.height) return invalid()
  const digest = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)), (byte) =>
    byte.toString(16).padStart(2, '0'),
  ).join('')
  if (digest !== logo.sha256) return invalid()
  return { ...logo, png_base64: encoded }
}
export async function parseBrandingProfile(value: unknown): Promise<BrandingProfile> {
  // Bound cached/constructed input as well as the streaming HTTP body's raw bytes.
  let serialized: string | undefined
  try {
    serialized = JSON.stringify(value)
  } catch {
    return invalid()
  }
  if (
    !serialized ||
    serialized.length > MAX_BRANDING_BODY_BYTES ||
    new TextEncoder().encode(serialized).byteLength > MAX_BRANDING_BODY_BYTES
  )
    return invalid()
  const input = object(value, [
    'schema_version',
    'organization_id',
    'location_id',
    'dataset_incarnation',
    'version',
    'display_name',
    'palette_id',
    'logo_state',
    'logo',
    'logo_diagnostic',
    'updated_at',
    'updated_by',
  ])
  if (
    input.schema_version !== 1 ||
    !isDatasetIncarnation(input.dataset_incarnation) ||
    !isNormalizedBrandingName(input.display_name) ||
    !PALETTES.some((palette) => palette.id === input.palette_id)
  )
    return invalid()
  const version = integer(input.version, 0, Number.MAX_SAFE_INTEGER)
  if (
    input.logo_state !== 'none' &&
    input.logo_state !== 'available' &&
    input.logo_state !== 'unavailable'
  )
    return invalid()
  if (version === 0) {
    if (
      input.palette_id !== 'bosque' ||
      input.logo_state !== 'none' ||
      input.updated_at !== null ||
      input.updated_by !== null
    )
      return invalid()
  } else if (!timestamp(input.updated_at)) return invalid()
  const updatedBy = version === 0 ? null : identifier(input.updated_by)
  const organizationId = identifier(input.organization_id),
    locationId = identifier(input.location_id)
  const logoState = input.logo_state
  if (
    (logoState === 'unavailable'
      ? input.logo_diagnostic !== 'asset_unavailable'
      : input.logo_diagnostic !== null) ||
    (logoState === 'none' && input.logo !== null)
  )
    return invalid()
  // Capture the complete validated scalar document before awaiting the digest.
  const result: BrandingProfile = {
    schema_version: 1,
    organization_id: organizationId,
    location_id: locationId,
    dataset_incarnation: input.dataset_incarnation,
    version,
    display_name: input.display_name,
    palette_id: input.palette_id as BrandingProfile['palette_id'],
    logo_state: logoState,
    logo: null,
    logo_diagnostic: logoState === 'unavailable' ? 'asset_unavailable' : null,
    updated_at: input.updated_at as string | null,
    updated_by: updatedBy,
  }
  return { ...result, logo: logoState === 'none' ? null : await parseLogo(input.logo, logoState) }
}
export async function parseBrandingProfileJson(raw: string): Promise<BrandingProfile> {
  if (
    typeof raw !== 'string' ||
    raw.length > MAX_BRANDING_BODY_BYTES ||
    new TextEncoder().encode(raw).byteLength > MAX_BRANDING_BODY_BYTES
  )
    return invalid()
  let value: unknown
  try {
    value = JSON.parse(raw)
  } catch {
    return invalid()
  }
  return parseBrandingProfile(value)
}

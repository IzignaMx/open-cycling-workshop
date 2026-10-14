import { createHash } from 'node:crypto'
export const PNG =
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNQCbD7DwADAAGyeEyo+gAAAABJRU5ErkJggg=='
export const INCARNATION = '0199ba00-0000-7000-8000-000000000001'
export const NOW = Date.parse('2026-10-14T10:00:00.000Z')
export function profile(overrides = {}) {
  return {
    schema_version: 1,
    organization_id: 'org',
    location_id: 'loc',
    dataset_incarnation: INCARNATION,
    version: 1,
    display_name: 'Taller Álamo',
    palette_id: 'arcilla',
    logo_state: 'none',
    logo: null,
    logo_diagnostic: null,
    updated_at: '2026-10-14T09:00:00Z',
    updated_by: 'A',
    ...overrides,
  }
}
export function withLogo(overrides = {}) {
  const bytes = Buffer.from(PNG, 'base64')
  return profile({
    logo_state: 'available',
    logo: {
      sha256: createHash('sha256').update(bytes).digest('hex'),
      byte_count: bytes.length,
      width: 1,
      height: 1,
      mime_type: 'image/png',
      png_base64: PNG,
    },
    ...overrides,
  })
}
export function chunk(type, data) {
  const result = Buffer.alloc(data.length + 12)
  result.writeUInt32BE(data.length)
  result.write(type, 4)
  data.copy(result, 8)
  let crc = 0xffffffff
  for (const byte of result.subarray(4, -4)) {
    crc ^= byte
    for (let bit = 0; bit < 8; bit++) crc = (crc >>> 1) ^ (crc & 1 ? 0xedb88320 : 0)
  }
  result.writeUInt32BE((crc ^ 0xffffffff) >>> 0, result.length - 4)
  return result
}
export function encodedProfile(bytes) {
  const p = withLogo()
  p.logo.png_base64 = bytes.toString('base64')
  p.logo.byte_count = bytes.length
  p.logo.sha256 = createHash('sha256').update(bytes).digest('hex')
  return p
}

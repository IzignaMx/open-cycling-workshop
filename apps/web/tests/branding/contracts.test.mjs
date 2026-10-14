import test from 'node:test'
import assert from 'node:assert/strict'
import {
  parseBrandingProfile,
  parseBrandingProfileJson,
  MAX_BRANDING_BODY_BYTES,
} from '../../.tmp-branding/src/features/branding/contracts.js'
import { DEFAULT_PREFERENCES } from '../../.tmp-branding/src/personalization/preferences.js'
import { resolvePresentation } from '../../.tmp-branding/src/personalization/resolution.js'
import { profile, withLogo, PNG, chunk, encodedProfile } from './fixture.mjs'

test('closed profile accepts complete absent, available and unavailable representations', async () => {
  const available = withLogo()
  const unavailable = profile({
    logo_state: 'unavailable',
    logo: { ...available.logo, png_base64: null },
    logo_diagnostic: 'asset_unavailable',
  })
  for (const value of [
    profile(),
    available,
    unavailable,
    profile({ version: 0, palette_id: 'bosque', updated_at: null, updated_by: null }),
  ]) {
    assert.deepEqual(await parseBrandingProfile(value), value)
    assert.deepEqual(await parseBrandingProfileJson(JSON.stringify(value)), value)
  }
})
test('strict profile rejects scope, enum, name, version, timestamp and extra-field violations', async () => {
  for (const overrides of [
    { schema_version: 2 },
    { version: -1 },
    { version: 1.5 },
    { version: Number.MAX_SAFE_INTEGER + 1 },
    { organization_id: '' },
    { location_id: null },
    { dataset_incarnation: 'old' },
    { display_name: ' Taller' },
    { display_name: 'A\u0301lamo' },
    { display_name: '\u0000Taller' },
    { display_name: 'a'.repeat(161) },
    { display_name: '\ud800' },
    { palette_id: 'evil' },
    { updated_at: null },
    { updated_at: 'yesterday' },
    { updated_by: null },
    { updated_by: '' },
    { extra: 'no' },
    { logo_state: 'none', logo_diagnostic: 'asset_unavailable' },
    { version: 0 },
    { version: 0, updated_at: null, updated_by: null },
    { version: 0, palette_id: 'bosque', updated_at: null, updated_by: null, display_name: ' ' },
  ])
    await assert.rejects(parseBrandingProfile(profile(overrides)), /branding/i)
  for (const value of [null, [], 1, {}, 'text']) await assert.rejects(parseBrandingProfile(value))
  assert.equal(
    (await parseBrandingProfile(profile({ display_name: '🚲'.repeat(160) }))).display_name.length,
    320,
  )
})
test('logo state cannot carry contradictory bytes, old data, unknown URLs or bad digest descriptors', async () => {
  for (const overrides of [
    { logo_state: 'none' },
    { logo_state: 'available', logo_diagnostic: 'asset_unavailable' },
    { logo_state: 'unavailable' },
    { logo_state: 'available', logo: null },
  ])
    await assert.rejects(parseBrandingProfile(withLogo(overrides)))
  for (const overrides of [
    { width: 2 },
    { width: 0 },
    { height: 513 },
    { byte_count: 1 },
    { byte_count: 262145 },
    { sha256: 'a'.repeat(64) },
    { sha256: 'A'.repeat(64) },
    { mime_type: 'image/svg+xml' },
    { png_base64: null },
    { png_base64: 'https://evil.test/logo.png' },
    { extra: true },
  ])
    await assert.rejects(
      parseBrandingProfile(withLogo({ logo: { ...withLogo().logo, ...overrides } })),
    )
})
test('canonical PNG checks framing CRC terminal bytes, animation, metadata and RGB dimensions', async () => {
  const original = Buffer.from(PNG, 'base64')
  const corrupt = Buffer.from(original)
  corrupt[45] ^= 255
  const badHeader = Buffer.from(original.subarray(16, 29))
  badHeader[8] = 16
  const badDimensions = Buffer.from(original.subarray(16, 29))
  badDimensions.writeUInt32BE(513, 0)
  for (const bytes of [
    Buffer.concat([original, Buffer.from('trailing')]),
    original.subarray(0, -1),
    corrupt,
    Buffer.concat([original.subarray(0, 8), chunk('IHDR', badHeader), original.subarray(33)]),
    Buffer.concat([original.subarray(0, 8), chunk('IHDR', badDimensions), original.subarray(33)]),
    ...['acTL', 'fcTL', 'fdAT', 'tEXt', 'iCCP'].map((kind) =>
      Buffer.concat([
        original.subarray(0, 33),
        chunk(kind, Buffer.alloc(8)),
        original.subarray(33),
      ]),
    ),
  ])
    await assert.rejects(parseBrandingProfile(encodedProfile(bytes)))
})
test('raw and reconstructed response caps reject oversized bodies before acceptance', async () => {
  await assert.rejects(parseBrandingProfileJson(' '.repeat(MAX_BRANDING_BODY_BYTES + 1)))
  await assert.rejects(parseBrandingProfileJson('{'))
  await assert.rejects(
    parseBrandingProfile(profile({ display_name: 'a'.repeat(MAX_BRANDING_BODY_BYTES) })),
  )
})
test('pure composition inherits workshop palette/logo without modifying preferences or protected personal choices', () => {
  const personal = {
    ...DEFAULT_PREFERENCES,
    themeId: 'noche',
    density: 'workshop',
    scheme: 'light',
  }
  const unchanged = structuredClone(personal),
    shared = withLogo()
  const resolved = resolvePresentation(personal, shared, 'Permitted location')
  assert.deepEqual(personal, unchanged)
  assert.equal(resolved.displayName, 'Taller Álamo')
  assert.equal(resolved.shared, true)
  assert.equal(resolved.preferences.paletteId, 'arcilla')
  assert.equal(resolved.preferences.logoDataUrl, `data:image/png;base64,${PNG}`)
  assert.equal(resolved.preferences.themeId, 'noche')
  assert.equal(resolved.preferences.density, 'workshop')
  assert.equal(resolved.preferences.scheme, 'light')
  for (const mode of ['none', 'local']) {
    const own = {
      ...personal,
      paletteSource: 'personal',
      paletteId: 'tinta',
      logoMode: mode,
      logoDataUrl: mode === 'local' ? `data:image/png;base64,${PNG}` : null,
    }
    const value = resolvePresentation(own, shared, 'Fallback')
    assert.equal(value.preferences.paletteId, 'tinta')
    assert.equal(value.preferences.logoDataUrl, own.logoDataUrl)
  }
  const unavailable = {
    ...shared,
    logo_state: 'unavailable',
    logo: { ...shared.logo, png_base64: null },
    logo_diagnostic: 'asset_unavailable',
  }
  assert.equal(resolvePresentation(personal, unavailable, 'Fallback').preferences.logoDataUrl, null)
  assert.equal(resolvePresentation(personal, null, 'Fallback').displayName, 'Fallback')
  assert.equal(resolvePresentation(personal, null, '').displayName, 'OCWP')
  assert.equal(resolvePresentation(personal, profile({ version: 0 }), 'Fallback').shared, false)
})

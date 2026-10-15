import test from 'node:test'
import assert from 'node:assert/strict'
import {
  DEFAULT_PREFERENCES,
  validatePreferences,
  preferenceScopeKey,
} from '../../.tmp-personalization/src/personalization/preferences.js'
import { PreferenceRepository } from '../../.tmp-personalization/src/personalization/repository.js'
import {
  validateLogoFile,
  isSafeStoredLogo,
} from '../../.tmp-personalization/src/personalization/logo.js'

const scope = { organizationId: 'org', userId: 'user', locationId: 'loc' }
export const PNG =
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNQCbD7DwADAAGyeEyo+gAAAABJRU5ErkJggg=='
const logo = `data:image/png;base64,${PNG}`
const v1 = {
  schemaVersion: 1,
  themeId: 'noche',
  paletteId: 'bosque',
  scheme: 'dark',
  density: 'workshop',
  logoDataUrl: null,
}
function fixture() {
  const rows = new Map(),
    writes = []
  const repo = new PreferenceRepository({
    async get(key) {
      return rows.get(key)
    },
    async put(row) {
      writes.push(row)
      rows.set(row.key, row)
    },
  })
  const set = (kind, value) =>
    rows.set(preferenceScopeKey(scope, kind), {
      ...scope,
      locationId: kind === 'appearance' ? null : scope.locationId,
      key: preferenceScopeKey(scope, kind),
      kind,
      value,
    })
  return { rows, writes, repo, set }
}
test('v1 default-valued palette remains explicit personal; missing records inherit without writes', async () => {
  const { repo, set, writes } = fixture()
  const missing = await repo.load(scope)
  assert.equal(missing.preferences.schemaVersion, 2)
  assert.equal(missing.preferences.paletteSource, 'workshop')
  assert.equal(missing.preferences.logoMode, 'workshop')
  set('appearance', v1)
  const existing = await repo.load(scope)
  assert.equal(existing.preferences.paletteSource, 'personal')
  assert.equal(existing.preferences.paletteId, 'bosque')
  assert.equal(existing.preferences.themeId, 'noche')
  assert.equal(existing.preferences.scheme, 'dark')
  assert.equal(existing.preferences.density, 'workshop')
  assert.equal(existing.preferences.logoMode, 'workshop')
  assert.deepEqual(writes, [])
})
test('legacy missing, explicit null and raster logo preserve distinct provenance', async () => {
  const { repo, set, writes } = fixture()
  for (const [value, mode] of [
    [null, 'none'],
    [logo, 'local'],
  ]) {
    set('logo', value)
    const result = await repo.load(scope)
    assert.equal(result.valid, true)
    assert.equal(result.preferences.logoMode, mode)
    assert.equal(result.preferences.logoDataUrl, value)
    assert.equal(
      (await repo.load({ ...scope, locationId: 'other' })).preferences.logoMode,
      'workshop',
    )
  }
  assert.equal(writes.length, 0)
})
test('v2 logo changes are local and reset appearance never changes local logo mode', async () => {
  const { repo, rows } = fixture()
  await repo.saveLogo(scope, logo)
  assert.equal((await repo.load(scope)).preferences.logoMode, 'local')
  await repo.saveAppearance(scope, DEFAULT_PREFERENCES)
  assert.equal((await repo.load(scope)).preferences.logoMode, 'local')
  await repo.saveLogo(scope, null)
  assert.equal((await repo.load(scope)).preferences.logoMode, 'none')
  await repo.saveLogoMode(scope, 'workshop')
  assert.equal((await repo.load(scope)).preferences.logoMode, 'workshop')
  assert.equal(rows.get(preferenceScopeKey(scope, 'logo')).value.schemaVersion, 2)
  await assert.rejects(repo.saveLogoMode(scope, 'local'))
})
test('closed v1/v2 codecs reject unknown fields and contradictory local-image modes', () => {
  assert.equal(validatePreferences(v1).valid, true)
  for (const value of [
    { ...v1, unknown: true },
    { ...DEFAULT_PREFERENCES, schemaVersion: 3 },
    { ...DEFAULT_PREFERENCES, paletteSource: 'url' },
    { ...DEFAULT_PREFERENCES, logoMode: 'local', logoDataUrl: null },
    { ...DEFAULT_PREFERENCES, logoMode: 'none', logoDataUrl: logo },
    { ...DEFAULT_PREFERENCES, logoMode: 'workshop', logoDataUrl: logo },
  ])
    assert.equal(validatePreferences(value).valid, false)
})
function chunk(type, data) {
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
test('PNG animation chunks are rejected before browser decode and on local restore', () => {
  const original = Buffer.from(PNG, 'base64')
  for (const type of ['acTL', 'fcTL', 'fdAT']) {
    const animated = Buffer.concat([
      original.subarray(0, 33),
      chunk(type, Buffer.alloc(8)),
      original.subarray(33),
    ])
    assert.throws(
      () => validateLogoFile({ type: 'image/png', size: animated.length }, animated),
      /animad|contenido/,
    )
    assert.equal(isSafeStoredLogo('data:image/png;base64,' + animated.toString('base64')), false)
  }
})

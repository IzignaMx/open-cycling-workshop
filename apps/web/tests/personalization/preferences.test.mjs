import test from 'node:test'
import assert from 'node:assert/strict'

import {
  THEMES,
  PALETTES,
  presentationTokens,
  SEMANTIC_TOKENS,
} from '../../.tmp-personalization/src/personalization/catalog.js'
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

const scope = { organizationId: 'org', userId: 'user', locationId: 'workshop' }

test('Banco is the safe default and structural themes have twelve curated palettes', () => {
  assert.equal(DEFAULT_PREFERENCES.themeId, 'banco')
  assert.equal(DEFAULT_PREFERENCES.paletteId, 'bosque')
  assert.deepEqual(
    THEMES.map((theme) => theme.id),
    ['banco', 'plano', 'ritmo', 'noche'],
  )
  assert.equal(PALETTES.length, 12)
  for (const theme of THEMES) {
    for (const palette of PALETTES) {
      const result = validatePreferences({
        ...DEFAULT_PREFERENCES,
        themeId: theme.id,
        paletteId: palette.id,
      })
      assert.equal(result.valid, true)
      assert.equal(result.preferences.themeId, theme.id)
    }
  }
})

test('corrupt, future, mismatched and unsafe preferences fall back to Banco', () => {
  for (const value of [
    null,
    [],
    'noche',
    {},
    { ...DEFAULT_PREFERENCES, schemaVersion: 2 },
    { ...DEFAULT_PREFERENCES, themeId: '__proto__' },
    { ...DEFAULT_PREFERENCES, paletteId: 'unknown' },
    { ...DEFAULT_PREFERENCES, scheme: 'url(https://evil.test)' },
    { ...DEFAULT_PREFERENCES, density: 'zero' },
    { ...DEFAULT_PREFERENCES, logoDataUrl: 'data:image/svg+xml;base64,PHN2Zz4=' },
  ]) {
    const result = validatePreferences(value)
    assert.equal(result.valid, false)
    assert.deepEqual(result.preferences, DEFAULT_PREFERENCES)
  }
  const result = validatePreferences({
    ...DEFAULT_PREFERENCES,
    danger: 'green',
    arbitraryCss: 'display:none',
  })
  assert.equal(result.valid, true)
  assert.deepEqual(result.preferences, DEFAULT_PREFERENCES)
})

test('appearance is isolated by user and organization; logos also by workshop', () => {
  const keys = [
    scope,
    { ...scope, organizationId: 'other' },
    { ...scope, userId: 'other' },
    { ...scope, locationId: 'other' },
    { ...scope, locationId: null },
    { organizationId: 'a:b', userId: 'c', locationId: 'd' },
    { organizationId: 'a', userId: 'b:c', locationId: 'd' },
  ].map((item) => preferenceScopeKey(item, 'logo'))
  assert.equal(new Set(keys).size, keys.length)
  assert.equal(preferenceScopeKey(scope), preferenceScopeKey({ ...scope, locationId: 'other' }))
})

test('repository validates scopes and config and never touches operational stores', async () => {
  const values = new Map()
  const table = {
    async get(key) {
      return values.get(key)
    },
    async put(row) {
      values.set(row.key, row)
      return row.key
    },
  }
  const repository = new PreferenceRepository(table)
  assert.deepEqual((await repository.load(scope)).preferences, DEFAULT_PREFERENCES)
  const next = { ...DEFAULT_PREFERENCES, themeId: 'ritmo', paletteId: 'malva' }
  await repository.saveAppearance(scope, next)
  assert.deepEqual((await repository.load(scope)).preferences, next)
  assert.deepEqual((await repository.load({ ...scope, locationId: 'other' })).preferences, next)
  assert.deepEqual(
    (await repository.load({ ...scope, userId: 'other' })).preferences,
    DEFAULT_PREFERENCES,
  )
  const key = preferenceScopeKey(scope)
  values.set(key, { ...values.get(key), userId: 'foreign' })
  assert.equal((await repository.load(scope)).valid, false)
  await assert.rejects(
    repository.saveAppearance(scope, { ...next, paletteId: 'unknown' }),
    /inválida/,
  )
})

test('quota failures are surfaced and never overwrite the last valid preference', async () => {
  const repository = new PreferenceRepository({
    async get() {
      return undefined
    },
    async put() {
      throw new Error('QuotaExceededError')
    },
  })
  await assert.rejects(repository.saveAppearance(scope, DEFAULT_PREFERENCES), /QuotaExceededError/)
})

function luminance(hex) {
  const channels = hex
    .replace('#', '')
    .match(/../g)
    .map((v) => parseInt(v, 16) / 255)
    .map((v) => (v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4))
  return channels[0] * 0.2126 + channels[1] * 0.7152 + channels[2] * 0.0722
}
function contrast(a, b) {
  const x = luminance(a),
    y = luminance(b)
  return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05)
}

test('all palettes and schemes preserve contrast and protected semantic tokens', () => {
  for (const theme of THEMES)
    for (const palette of PALETTES)
      for (const scheme of ['theme', 'light', 'dark']) {
        const tokens = presentationTokens({
          ...DEFAULT_PREFERENCES,
          themeId: theme.id,
          paletteId: palette.id,
          scheme,
        })
        for (const [fg, bg] of [
          ['ink', 'canvas'],
          ['ink', 'surface'],
          ['muted', 'canvas'],
          ['muted', 'surface'],
          ['accentInk', 'accent'],
          ['navInk', 'nav'],
          ['accentText', 'surface'],
        ]) {
          assert.ok(
            contrast(tokens[fg], tokens[bg]) >= 4.5,
            `${theme.id}/${palette.id}/${scheme}: ${fg}/${bg}`,
          )
        }
        assert.ok(contrast(tokens.focus, tokens.canvas) >= 3)
        assert.ok(contrast(tokens.focus, tokens.surface) >= 3)
        assert.deepEqual(tokens.semantic, SEMANTIC_TOKENS)
      }
})

test('logo validation rejects SVG, false MIME, oversized files, remote URLs and corrupt persisted payloads', () => {
  assert.throws(
    () =>
      validateLogoFile({ type: 'image/svg+xml', size: 10 }, new Uint8Array([60, 115, 118, 103])),
    /PNG/,
  )
  assert.throws(
    () => validateLogoFile({ type: 'image/png', size: 3 * 1024 * 1024 }, new Uint8Array()),
    /2 MB/,
  )
  assert.throws(
    () => validateLogoFile({ type: 'image/png', size: 10 }, new Uint8Array([60, 115, 118, 103])),
    /contenido/,
  )
  for (const value of [
    'https://evil.test/logo.png',
    'data:image/svg+xml;base64,PHN2Zz4=',
    'data:image/png;base64,AAAA',
    'data:image/png;base64,' + 'A'.repeat(400000),
  ])
    assert.equal(isSafeStoredLogo(value), false)
})

const VALID_LOGO =
  'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNQCbD7DwADAAGyeEyo+gAAAABJRU5ErkJggg=='

test('raster logos persist only in the current user, organization and location', async () => {
  const rows = new Map()
  const repository = new PreferenceRepository({
    async get(key) {
      return rows.get(key)
    },
    async put(row) {
      rows.set(row.key, row)
    },
  })
  await repository.saveAppearance(scope, {
    ...DEFAULT_PREFERENCES,
    themeId: 'noche',
    paletteId: 'lima',
  })
  await repository.saveLogo(scope, VALID_LOGO)
  assert.equal((await repository.load(scope)).preferences.logoDataUrl, VALID_LOGO)
  const other = (await repository.load({ ...scope, locationId: 'second' })).preferences
  assert.equal(other.themeId, 'noche')
  assert.equal(other.paletteId, 'lima')
  assert.equal(other.logoDataUrl, null)
  assert.equal(
    (await repository.load({ ...scope, userId: 'second' })).preferences.logoDataUrl,
    null,
  )
  await repository.saveAppearance(scope, DEFAULT_PREFERENCES)
  assert.equal((await repository.load(scope)).preferences.logoDataUrl, VALID_LOGO)
  const key = preferenceScopeKey(scope, 'logo')
  rows.set(key, { ...rows.get(key), value: 'data:image/svg+xml;base64,PHN2Zz4=' })
  assert.equal((await repository.load(scope)).valid, false)
  await repository.saveLogo(scope, null)
  assert.equal((await repository.load(scope)).valid, true)
})

test('well-formed tiny PNG is accepted; corrupt PNG body and excessive decoded dimensions are rejected', () => {
  assert.equal(isSafeStoredLogo(VALID_LOGO), true)
  const binary = Buffer.from(VALID_LOGO.slice(22), 'base64')
  binary[45] ^= 255
  assert.equal(isSafeStoredLogo('data:image/png;base64,' + binary.toString('base64')), false)
  const excessive = Buffer.from(VALID_LOGO.slice(22), 'base64')
  excessive.writeUInt32BE(9999, 16)
  assert.throws(
    () => validateLogoFile({ type: 'image/png', size: excessive.length }, excessive),
    /4096/,
  )
})

test('untrusted object values never invoke string conversion while validating', () => {
  for (const field of ['scheme', 'density']) {
    const input = { ...DEFAULT_PREFERENCES, [field]: { toString: null } }
    assert.equal(validatePreferences(input).valid, false)
  }
})

test('new repository mounts join prior scoped writes before loading or saving', async () => {
  const rows = new Map()
  let releaseFirst
  const firstGate = new Promise((resolve) => {
    releaseFirst = resolve
  })
  let writes = 0
  const table = {
    async get(key) {
      return rows.get(key)
    },
    async put(record) {
      writes++
      if (writes === 1) await firstGate
      rows.set(record.key, record)
    },
  }
  const oldMount = new PreferenceRepository(table)
  const newerMount = new PreferenceRepository(table)
  const first = oldMount.saveAppearance(scope, { ...DEFAULT_PREFERENCES, themeId: 'noche' })
  let loadFinished = false
  const loaded = newerMount.load(scope).then((result) => {
    loadFinished = true
    return result
  })
  const latest = newerMount.saveAppearance(scope, { ...DEFAULT_PREFERENCES, themeId: 'ritmo' })
  await new Promise((resolve) => setTimeout(resolve, 0))
  assert.equal(loadFinished, false)
  assert.equal(writes, 1)
  releaseFirst()
  await Promise.all([first, latest, loaded])
  assert.equal((await newerMount.load(scope)).preferences.themeId, 'ritmo')
})

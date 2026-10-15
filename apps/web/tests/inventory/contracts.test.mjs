import test from 'node:test'
import assert from 'node:assert/strict'
import {
  parseCatalog,
  parseStock,
  parseMovementPage,
  encodeCursor,
  decodeCursor,
} from '../../.tmp-inventory/src/features/inventory/contracts.js'
const scope = { organizationId: 'org', locationId: 'loc' }
const product = {
  product_id: 'part',
  organization_id: 'org',
  location_id: 'loc',
  sku: '<script>',
  name: 'Part',
  unit: 'pieza',
  version: 1,
  created_at: '2026-10-15T00:00:00Z',
  updated_at: '2026-10-15T00:00:00Z',
}
const stock = {
  product_id: 'part',
  organization_id: 'org',
  location_id: 'loc',
  available_quantity: -4,
}
const movement = {
  movement_id: 'move',
  product_id: 'part',
  organization_id: 'org',
  location_id: 'loc',
  kind: 'CONSUME',
  quantity: 1,
  occurred_at: '2026-10-15T00:00:00.000001Z',
}
const cursor = (row = movement) => ({
  before_movement_id: row.movement_id,
  before_occurred_at: row.occurred_at,
  location_id: 'loc',
  organization_id: 'org',
  product_id: 'part',
  version: 1,
})
const json = JSON.stringify
const fails = (fn, code = 'invalid_response') => assert.throws(fn, (e) => e.code === code)
test('closed legacy catalog and stock preserve literal labels and signed safe boundaries', () => {
  assert.deepEqual(parseCatalog(json([product]), scope), [product])
  assert.deepEqual(parseStock(json(stock), scope, 'part'), stock)
  for (const n of [Number.MAX_SAFE_INTEGER, -Number.MAX_SAFE_INTEGER, 0])
    assert.equal(
      parseStock(json({ ...stock, available_quantity: n }), scope, 'part').available_quantity,
      n,
    )
  assert.deepEqual(
    parseCatalog(
      json([
        { ...product, name: 'z' },
        { ...product, product_id: 'a', name: 'Á' },
      ]),
      scope,
    ).length,
    2,
  )
})
test('raw numeric lexemes cannot round, underflow or disguise fractions before JSON parse', () => {
  for (const raw of [
    '9007199254740991.1',
    '1.0000000000000001',
    '1e-999',
    '1e0',
    '-0',
    'true',
    '"1"',
  ]) {
    fails(() => parseStock(json(stock).replace('-4', raw), scope, 'part'))
    fails(() => parseCatalog(json([product]).replace('"version":1', `"version":${raw}`), scope))
    fails(() =>
      parseMovementPage(
        json({ items: [movement], next_cursor: null }).replace('"quantity":1', `"quantity":${raw}`),
        scope,
        'part',
      ),
    )
  }
  for (const raw of [
    '9007199254740992',
    '-9007199254740992',
    '999999999999999999999999999999999999',
  ])
    fails(() => parseStock(json(stock).replace('-4', raw), scope, 'part'), 'unsupported_quantity')
  assert.equal(
    parseCatalog(json([{ ...product, name: 'escaped "1e-999" and 9007199254740991.1' }]), scope)
      .length,
    1,
  )
})
test('exact fields, scope, duplicates and row bounds fail closed', () => {
  for (const row of [
    { ...product, actor_id: 'secret' },
    { ...product, organization_id: 'other' },
    { ...product, version: 0 },
    { ...product, product_id: '\ud800' },
  ])
    fails(() => parseCatalog(json([row]), scope))
  fails(() => parseCatalog(json([product, product]), scope))
  fails(() =>
    parseCatalog(
      json(Array.from({ length: 51 }, (_, i) => ({ ...product, product_id: String(i) }))),
      scope,
    ),
  )
  fails(() => parseStock(json({ ...stock, note: null }), scope, 'part'))
  fails(() =>
    parseStock(
      json(stock).replace(
        '"available_quantity":-4',
        '"available_quantity":3,"available_quantity":-4',
      ),
      scope,
      'part',
    ),
  )
  for (const row of [
    { ...movement, note: null },
    { ...movement, kind: 'BOGUS' },
    { ...movement, location_id: 'other' },
    { ...movement, occurred_at: '2026-02-30T00:00:00.000000Z' },
    { ...movement, occurred_at: '2026-10-15T00:00:00Z' },
    { ...movement, occurred_at: '0000-10-15T00:00:00.000000Z' },
  ])
    fails(() => parseMovementPage(json({ items: [row], next_cursor: null }), scope, 'part'))
})
test('movement order uses microseconds and Unicode code points, not locale or UTF16', () => {
  const items = [
    { ...movement, movement_id: '𐀀' },
    { ...movement, movement_id: '\uffff' },
    { ...movement, movement_id: 'z', occurred_at: '2026-10-15T00:00:00.000000Z' },
  ]
  assert.deepEqual(
    parseMovementPage(json({ items, next_cursor: null }), scope, 'part').items,
    items,
  )
  fails(() =>
    parseMovementPage(json({ items: [...items].reverse(), next_cursor: null }), scope, 'part'),
  )
  fails(() =>
    parseMovementPage(json({ items: [movement, movement], next_cursor: null }), scope, 'part'),
  )
})
test('canonical cursor binds exact scope and last returned tuple, requires full page and strict incoming progress', () => {
  const token = encodeCursor(cursor())
  assert.deepEqual(decodeCursor(token, scope, 'part'), cursor())
  assert.equal(
    parseMovementPage(json({ items: [movement], next_cursor: token }), scope, 'part', undefined, 1)
      .next_cursor,
    token,
  )
  fails(() => parseMovementPage(json({ items: [movement], next_cursor: token }), scope, 'part'))
  fails(() =>
    parseMovementPage(json({ items: [movement], next_cursor: token }), scope, 'part', token, 1),
  )
  const older = { ...movement, movement_id: 'older', occurred_at: '2026-10-15T00:00:00.000000Z' }
  assert.equal(
    parseMovementPage(json({ items: [older], next_cursor: null }), scope, 'part', token).items
      .length,
    1,
  )
  fails(() =>
    parseMovementPage(
      json({ items: [movement], next_cursor: encodeCursor(cursor(older)) }),
      scope,
      'part',
      undefined,
      1,
    ),
  )
  for (const bad of [
    token + '=',
    '!',
    encodeCursor({ ...cursor(), product_id: 'other' }),
    Buffer.from(
      json({ ...cursor(), version: 1.0 }).replace('"version":1', '"version":1.0'),
    ).toString('base64url'),
    Buffer.from(json({ version: 1, ...cursor() })).toString('base64url'),
  ])
    fails(() => decodeCursor(bad, scope, 'part'))
})

test('cursor exact canonical wire bytes, Unicode IDs and legal calendar boundaries', () => {
  const exact = {
    before_movement_id: 'move-a',
    before_occurred_at: '2026-10-15T00:00:00.000001Z',
    location_id: 'loc-a',
    organization_id: 'org-a',
    product_id: 'product-a',
    version: 1,
  }
  assert.equal(
    encodeCursor(exact),
    'eyJiZWZvcmVfbW92ZW1lbnRfaWQiOiJtb3ZlLWEiLCJiZWZvcmVfb2NjdXJyZWRfYXQiOiIyMDI2LTEwLTE1VDAwOjAwOjAwLjAwMDAwMVoiLCJsb2NhdGlvbl9pZCI6ImxvYy1hIiwib3JnYW5pemF0aW9uX2lkIjoib3JnLWEiLCJwcm9kdWN0X2lkIjoicHJvZHVjdC1hIiwidmVyc2lvbiI6MX0',
  )
  for (const occurred_at of [
    '0001-01-01T00:00:00.000000Z',
    '2000-02-29T23:59:59.999999Z',
    '9999-12-31T23:59:59.999999Z',
  ]) {
    const row = {
      ...movement,
      movement_id: '𐀀'.repeat(36),
      occurred_at,
      quantity: -Number.MAX_SAFE_INTEGER,
    }
    const token = encodeCursor(cursor(row))
    assert.equal(decodeCursor(token, scope, 'part').before_movement_id, row.movement_id)
    assert.equal(
      parseMovementPage(json({ items: [row], next_cursor: token }), scope, 'part', undefined, 1)
        .items[0].quantity,
      -Number.MAX_SAFE_INTEGER,
    )
  }
  for (const occurred_at of [
    '1900-02-29T00:00:00.000000Z',
    '2026-01-01T24:00:00.000000Z',
    '2026-01-01T00:00:60.000000Z',
    '2026-01-01T00:00:00.000000+00:00',
  ])
    fails(() =>
      decodeCursor(encodeCursor({ ...cursor(), before_occurred_at: occurred_at }), scope, 'part'),
    )
})
test('cursor rejects malformed UTF8, padded/noncanonical bytes and all nonclosed variants', () => {
  for (const raw of [
    json(cursor()).replace('"version":1', '"version":true'),
    json(cursor()).replace('"version":1', '"version":1e0'),
    json(cursor()).replace('"version":1', '"version":1,"version":1'),
    json({ ...cursor(), version: 2 }),
    json({ ...cursor(), note: 'private' }),
    json(cursor()).replace('"move"', '"\\u006dove"'),
    json(cursor()).replace('"organization_id":"org",', ''),
    json({ ...cursor(), before_movement_id: 'a\0b' }),
    json({ ...cursor(), before_movement_id: '\udfff' }),
    json({ ...cursor(), before_movement_id: '𐀀'.repeat(37) }),
    ' '.repeat(1025),
  ])
    fails(() => decodeCursor(Buffer.from(raw).toString('base64url'), scope, 'part'))
  for (const token of [Buffer.from([0xff]).toString('base64url'), 'A', 'a'.repeat(2049)])
    fails(() => decodeCursor(token, scope, 'part'))
})

import test from 'node:test'
import assert from 'node:assert/strict'

import { buildLocalCustomerCreate } from '../../.tmp-customer/src/features/customers/local-customer.js'

test('buildLocalCustomerCreate normalizes contact data and creates a queued mutation', () => {
  const ids = ['018f0000-0000-7000-8000-000000000001', '018f0000-0000-7000-8000-000000000002']
  const result = buildLocalCustomerCreate(
    {
      organizationId: 'org-1',
      locationId: 'loc-1',
      displayName: '  Ana   López  ',
      email: ' ANA@EXAMPLE.COM ',
      phone: ' 55 1234 5678 ',
    },
    {
      now: () => '2026-08-07T00:00:00.000Z',
      newId: () => ids.shift(),
    },
  )

  assert.equal(result.customer.display_name, 'Ana López')
  assert.equal(result.customer.email, 'ana@example.com')
  assert.equal(result.customer.phone, '55 1234 5678')
  assert.equal(result.mutation.entity_id, result.customer.customer_id)
  assert.equal(result.mutation.state, 'pending')
  assert.equal(result.mutation.operation, 'create')
})

test('buildLocalCustomerCreate rejects a blank display name before persistence', () => {
  assert.throws(
    () =>
      buildLocalCustomerCreate(
        { organizationId: 'org-1', locationId: 'loc-1', displayName: '   ' },
        {
          now: () => '2026-08-07T00:00:00.000Z',
          newId: () => '018f0000-0000-7000-8000-000000000001',
        },
      ),
    /nombre es obligatorio/i,
  )
})

const prepare = (input, dependencies = {}) =>
  buildLocalCustomerCreate(
    { organizationId: 'org-1', locationId: 'loc-1', displayName: 'Synthetic', ...input },
    { now: () => '2026-08-07T00:00:00Z', newId: () => 'synthetic', ...dependencies },
  )
for (const [field, value, message] of [
  ['displayName', 'a'.repeat(201), 'El nombre no puede superar 200 caracteres'],
  ['email', 'a'.repeat(309) + '@example.com', 'El correo no puede superar 320 caracteres'],
  ['email', 'x'.repeat(321), 'El correo no puede superar 320 caracteres'],
  ['phone', '1'.repeat(65), 'El teléfono no puede superar 64 caracteres'],
  ['email', 'İ'.repeat(308) + '@example.com', 'El correo no puede superar 320 caracteres'],
]) {
  test(`customer prepared ${field} overflow rejects without allocating identifiers (${value.length})`, () => {
    let calls = 0
    assert.throws(
      () =>
        prepare(
          { [field]: value },
          {
            newId: () => {
              calls++
              return 'synthetic'
            },
          },
        ),
      (error) => error instanceof Error && error.message === message,
    )
    assert.equal(calls, 0)
  })
}
test('customer limits count prepared Unicode codepoints without truncation or normalization changes', () => {
  const name = '😀'.repeat(200),
    email = 'a'.repeat(308) + '@example.com',
    phone = '1'.repeat(64)
  const { customer, mutation } = prepare({
    displayName: `  ${name}  `,
    email: `  ${email.toUpperCase()}  `,
    phone: ` ${phone} `,
  })
  assert.equal(customer.display_name, name)
  assert.equal(customer.email, email)
  assert.equal(customer.phone, phone)
  assert.equal(mutation.payload.display_name, name)
  assert.equal(prepare({ displayName: ' a   b ', phone: ' 12 34 ' }).customer.phone, '12 34')
  assert.equal(prepare({ displayName: ' a   b ' }).customer.display_name, 'a b')
  assert.equal(
    prepare({ displayName: 'e\u0301'.repeat(100) }).customer.display_name,
    'e\u0301'.repeat(100),
  )
  assert.throws(() => prepare({ displayName: 'e\u0301'.repeat(101) }))
})

for (const [label, input, message] of [
  ['single-label email', { email: 'person@localhost' }, 'El correo no es válido'],
  [
    'internal Python whitespace email',
    { email: 'per\u0085son@example.test' },
    'El correo no es válido',
  ],
  ['NEXT LINE blank name', { displayName: '\u0085' }, 'El nombre es obligatorio'],
  [
    'control separators blank name',
    { displayName: '\u001c\u001d\u001e\u001f' },
    'El nombre es obligatorio',
  ],
]) {
  test(`customer refuses server-inadmissible ${label} before allocating IDs`, () => {
    let allocated = 0
    assert.throws(
      () =>
        prepare(input, {
          newId: () => {
            allocated++
            return 'synthetic'
          },
        }),
      (error) => error instanceof Error && error.message === message,
    )
    assert.equal(allocated, 0)
  })
}
test('customer admissibility checks backend projection without rewriting prepared input', () => {
  for (const [input, expected] of [
    [{ displayName: '\u0085Ana\u0085' }, { display_name: '\u0085Ana\u0085' }],
    [{ displayName: 'A\u001cB' }, { display_name: 'A\u001cB' }],
    [{ displayName: '\u200b' }, { display_name: '\u200b' }],
    [{ email: '\u0085PERSON@EXAMPLE.TEST\u001c' }, { email: '\u0085person@example.test\u001c' }],
    [{ email: '\u0085' }, { email: '\u0085' }],
    [{ email: 'A@B.C' }, { email: 'a@b.c' }],
  ]) {
    const { customer, mutation } = prepare(input)
    for (const [field, value] of Object.entries(expected)) {
      assert.equal(customer[field], value)
      assert.equal(mutation.payload[field], value)
    }
  }
})

test('customer update preserves identity, advances one version and captures the exact base', async () => {
  const { buildLocalCustomerUpdate } =
    await import('../../.tmp-customer/src/features/customers/local-customer.js')
  assert.equal(typeof buildLocalCustomerUpdate, 'function')
  const original = prepare({ displayName: 'Before', email: 'old@example.test' }).customer
  const snapshot = structuredClone(original)
  let ids = 0
  const result = buildLocalCustomerUpdate(
    original,
    {
      displayName: ' After ',
      email: '',
      phone: ' 123 ',
    },
    { now: () => '2026-11-08T00:00:00Z', newId: () => `mutation-${++ids}` },
  )
  assert.deepEqual(original, snapshot)
  assert.equal(result.customer.customer_id, original.customer_id)
  assert.equal(result.customer.created_at, original.created_at)
  assert.equal(result.customer.version, 2)
  assert.equal(result.customer.display_name, 'After')
  assert.equal(result.customer.email, null)
  assert.equal(result.customer.phone, '123')
  assert.equal(result.mutation.operation, 'update')
  assert.equal(result.mutation.base_version, 1)
  assert.equal(result.mutation.entity_id, original.customer_id)
  assert.equal(ids, 1)
})

for (const [label, input] of [
  ['empty name', { displayName: '' }],
  ['Python blank name', { displayName: '\u0085' }],
  ['name cap', { displayName: '😀'.repeat(201) }],
  ['email cap', { email: 'İ'.repeat(158) + '@x.co' }],
  ['email grammar', { email: 'x@local' }],
  ['phone cap', { phone: '1'.repeat(65) }],
]) {
  test(`customer update rejects ${label} before allocating an operation`, async () => {
    const { buildLocalCustomerUpdate } =
      await import('../../.tmp-customer/src/features/customers/local-customer.js')
    const previous = prepare({ displayName: 'Original' }).customer
    let allocations = 0
    assert.throws(() =>
      buildLocalCustomerUpdate(
        previous,
        { displayName: 'New', ...input },
        {
          now: () => '2026-11-08T00:00:00Z',
          newId: () => {
            allocations++
            return 'must-not-allocate'
          },
        },
      ),
    )
    assert.equal(allocations, 0)
    assert.equal(previous.version, 1)
    assert.equal(previous.display_name, 'Original')
  })
}

test('customer update rejects exhausted or invalid base versions before operation allocation', async () => {
  const { buildLocalCustomerUpdate } =
    await import('../../.tmp-customer/src/features/customers/local-customer.js')
  for (const version of [0, -1, 1.5, NaN, Number.MAX_SAFE_INTEGER]) {
    let allocations = 0
    const previous = { ...prepare({}).customer, version }
    assert.throws(() =>
      buildLocalCustomerUpdate(
        previous,
        { displayName: 'New' },
        {
          now: () => '2026-11-08T00:00:00Z',
          newId: () => {
            allocations++
            return 'must-not-allocate'
          },
        },
      ),
    )
    assert.equal(allocations, 0)
  }
})

for (const field of ['displayName', 'email', 'phone']) {
  for (const value of ['\0', '\ud800', '\udfff']) {
    test(`customer create and edit reject unrepresentable text in ${field} ${value.charCodeAt(0)}`, async () => {
      const { buildLocalCustomerUpdate } =
        await import('../../.tmp-customer/src/features/customers/local-customer.js')
      let allocations = 0
      const deps = {
        now: () => '2026-11-08T00:00:00Z',
        newId: () => {
          allocations++
          return 'unexpected'
        },
      }
      const input = {
        displayName: 'Valid',
        [field]: field === 'email' ? `a${value}@b.test` : `a${value}`,
      }
      assert.throws(() => prepare(input, deps), /caracteres no válidos/)
      assert.throws(
        () => buildLocalCustomerUpdate(prepare({}).customer, input, deps),
        /caracteres no válidos/,
      )
      assert.equal(allocations, 0)
    })
  }
}

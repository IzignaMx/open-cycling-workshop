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

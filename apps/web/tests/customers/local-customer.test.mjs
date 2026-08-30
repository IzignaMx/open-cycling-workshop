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
        { now: () => '2026-08-07T00:00:00.000Z', newId: () => '018f0000-0000-7000-8000-000000000001' },
      ),
    /nombre es obligatorio/i,
  )
})

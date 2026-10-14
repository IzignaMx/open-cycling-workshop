import test from 'node:test'
import assert from 'node:assert/strict'
import { validateIncrementalResponse } from '../../.tmp-kernel/src/access-kernel/incremental-wire.js'
import { validateBaselineResponse } from '../../.tmp-kernel/src/access-kernel/baseline-wire.js'
const context = {
  principal: { organizationId: 'org', userId: 'A' },
  selectedLocationId: 'loc',
  capabilities: ['customers.read'],
  authorizationEpoch: 'a'.repeat(43),
}
const page = () => ({
  protocol: 1,
  baseline_id: null,
  authorization_epoch: context.authorizationEpoch,
  predecessor: 'initial',
  continuation: 'next',
  page_id: 'page',
  records: [],
  phase: 'complete',
  completion: {
    baseline_id: null,
    authorization_epoch: context.authorizationEpoch,
    checkpoint: 'next',
  },
})
const validate = (value) => validateIncrementalResponse(value, { context, predecessor: 'initial' })
test('incremental complete and catching-up pages require their own explicit null baseline contract', () => {
  assert.equal(validate(page()).completion.baseline_id, null)
  assert.equal(validate({ ...page(), phase: 'catching_up', completion: null }).completion, null)
  assert.throws(() =>
    validateBaselineResponse('delta', page(), { context, predecessor: 'initial' }, 0),
  )
})
for (const [name, mutate] of [
  [
    'initial baseline',
    (p) => {
      p.baseline_id = '00000000-0000-0000-0000-000000000001'
    },
  ],
  [
    'initial completion',
    (p) => {
      p.completion.baseline_id = '00000000-0000-0000-0000-000000000001'
    },
  ],
  [
    'unknown key',
    (p) => {
      p.extra = true
    },
  ],
  [
    'unknown phase',
    (p) => {
      p.phase = 'scan'
    },
  ],
  [
    'wrong predecessor',
    (p) => {
      p.predecessor = 'other'
    },
  ],
  [
    'unchanged cursor',
    (p) => {
      p.continuation = 'initial'
    },
  ],
  [
    'wrong epoch',
    (p) => {
      p.authorization_epoch = 'b'.repeat(43)
    },
  ],
  [
    'contradictory completion',
    (p) => {
      p.completion.checkpoint = 'wrong'
    },
  ],
  [
    'unbounded records',
    (p) => {
      p.records = Array(101).fill({})
    },
  ],
  [
    'unbounded bytes',
    (p) => {
      p.page_id = 'a'.repeat(1048577)
    },
  ],
  [
    'mixed scope',
    (p) => {
      p.records = [
        {
          entity_type: 'customer',
          entity_id: 'id',
          entity_version: 1,
          payload: { organization_id: 'foreign' },
        },
      ]
    },
  ],
])
  test(`incremental wire rejects ${name}`, () => {
    const p = page()
    mutate(p)
    assert.throws(() => validate(p))
  })

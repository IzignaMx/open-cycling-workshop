import test from 'node:test'
import assert from 'node:assert/strict'
import { stageObservedDraft } from './coordinator.mjs'
test('coordinator refuses staging after source refusal and never offers activation', async () => {
  let stages = 0
  const r = await stageObservedDraft({
    snapshot: async () => ({ kind: 'refused', reason: 'journal' }),
    stage: async () => {
      stages++
    },
    recheck: async () => {
      throw new Error('unexpected')
    },
  })
  assert.deepEqual(r, { kind: 'refused', reason: 'journal' })
  assert.equal(stages, 0)
})
for (const status of ['source_changed', 'source_unchanged_at_check'])
  test('staged custody remains inert after ' + status, async () => {
    const witness = {},
      bundle = { test: 'synthetic' },
      calls = []
    const r = await stageObservedDraft({
      snapshot: async () => ({ kind: 'snapshot', bundle, witness }),
      stage: async (b) => {
        assert.equal(b, bundle)
        calls.push('stage')
        return { kind: 'staged' }
      },
      recheck: async (w) => {
        assert.equal(w, witness)
        calls.push('recheck')
        return { kind: status }
      },
    })
    assert.deepEqual(calls, ['stage', 'recheck'])
    assert.deepEqual(r, {
      kind: 'custody_retained',
      observation: status,
      operationalUse: 'forbidden',
    })
  })
test('interrupted or failed staging does not report source checked; no cleanup fallback', async () => {
  const r = await stageObservedDraft({
    snapshot: async () => ({ kind: 'snapshot', bundle: {}, witness: {} }),
    stage: async () => ({ kind: 'refused', reason: 'quota' }),
    recheck: async () => {
      throw new Error('unexpected')
    },
  })
  assert.deepEqual(r, { kind: 'refused', reason: 'quota' })
})
test('recheck refusal retains custody but never returns its payload', async () => {
  const r = await stageObservedDraft({
    snapshot: async () => ({ kind: 'snapshot', bundle: { private: 'value' }, witness: {} }),
    stage: async () => ({ kind: 'already_staged' }),
    recheck: async () => ({ kind: 'refused', reason: 'expired' }),
  })
  assert.deepEqual(r, {
    kind: 'custody_retained',
    observation: 'unavailable',
    operationalUse: 'forbidden',
  })
  assert.equal(JSON.stringify(r).includes('private'), false)
})

import test from 'node:test'
import assert from 'node:assert/strict'

import { buildConflictCenterItems } from '../../.tmp-conflict/src/features/sync/conflict-center-model.js'

test('conflict center sorts newest issues first and exposes actionable labels', () => {
  const items = buildConflictCenterItems([
    {
      mutation_id: 'mutation-old',
      entity_type: 'customer',
      entity_id: 'customer-1',
      reason: 'base version is stale',
      recorded_at: '2026-08-07T00:00:00.000Z',
    },
    {
      mutation_id: 'mutation-new',
      entity_type: 'customer',
      entity_id: 'customer-2',
      reason: 'customer location scope mismatch',
      recorded_at: '2026-08-07T00:05:00.000Z',
    },
  ])

  assert.deepEqual(items.map((item) => item.mutationId), ['mutation-new', 'mutation-old'])
  assert.equal(items[0].title, 'Cliente con conflicto')
  assert.match(items[0].description, /customer location scope mismatch/i)
  assert.equal(items[0].statusLabel, 'Requiere atención')
})

test('sync status model communicates local-first states without relying on color', async () => {
  const { syncStatusPresentation } = await import('../../.tmp-conflict/src/features/sync/status-model.js')
  assert.deepEqual(syncStatusPresentation('offline'), { label: 'Sin conexión', detail: 'El trabajo sigue guardándose en este dispositivo.' })
  assert.deepEqual(syncStatusPresentation('syncing'), { label: 'Sincronizando', detail: 'Enviando y recibiendo cambios pendientes.' })
  assert.deepEqual(syncStatusPresentation('conflict'), { label: 'Requiere atención', detail: 'Hay cambios que necesitan resolución manual.' })
})

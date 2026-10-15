import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
const source = (name) => readFileSync(new URL(`../../src/${name}`, import.meta.url), 'utf8')
test('inventory uses plain-text closed fields, independent freshness and truthful ledger semantics', () => {
  const panel = source('features/inventory/InventoryPanel.tsx')
  assert.match(panel, /aria-label="Cantidad disponible"/)
  assert.match(panel, /aria-label="Movimientos de inventario"/)
  assert.match(panel, /Cantidad recibida/)
  assert.match(panel, /Movimientos recibidos/)
  assert.match(panel, /RESERVE/)
  assert.match(panel, /CONSUME/)
  assert.match(panel, /otra página/)
  assert.match(panel, /históricos sin vínculo/)
  assert.doesNotMatch(
    panel,
    /dangerouslySetInnerHTML|innerHTML|reference_movement_id|actor_id|order_id/,
  )
  assert.match(panel, /tabIndex={-1}/)
  assert.match(panel, /aria-live="polite"/)
})
test('in-page inventory entry preserves mounted operational forms and uses all-theme tokens', () => {
  assert.match(source('personalization/WorkshopShell.tsx'), /href="#workshop-inventory"/)
  assert.equal((source('App.tsx').match(/<InventoryPanel /g) ?? []).length, 3)
  const css = source('features/inventory/inventory.css')
  assert.match(css, /min-height: 44px/)
  assert.match(css, /min-height: 56px/)
  assert.match(css, /overflow-wrap: anywhere/)
  assert.match(css, /--ocwp-color-/)
  assert.doesNotMatch(css, /#[0-9a-f]{6}/i)
})

test('read controls keep whole words while long labels reflow; scope change synchronously clears', () => {
  const css = source('features/inventory/inventory.css'),
    panel = source('features/inventory/InventoryPanel.tsx')
  const controls = css.split('.inventory-panel button,')[1].split('}')[0]
  assert.match(controls, /overflow-wrap: normal/)
  assert.match(controls, /word-break: normal/)
  assert.match(controls, /min-inline-size: min-content/)
  assert.match(panel, /controller.clearSelection\(\)[\s\S]*?setLocation/)
})

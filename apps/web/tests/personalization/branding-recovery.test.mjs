import test from 'node:test'
import assert from 'node:assert/strict'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { WorkshopShell } from '../../.tmp-personalization/src/personalization/WorkshopShell.js'

const notice =
  'No se pudo confirmar la marca compartida para esta vista. Puedes volver a consultarla.'
let refreshes = 0
const render = (patch = {}) =>
  renderToStaticMarkup(
    createElement(WorkshopShell, {
      scope: { organizationId: 'org', userId: 'user', locationId: 'loc' },
      repository: {},
      userName: 'Synthetic reader',
      canCreateOrders: false,
      brandingRefreshSuggested: true,
      brandingMessage: notice,
      onRefreshBranding: () => {
        refreshes++
      },
      children: createElement('input', {
        'aria-label': 'Borrador operativo',
        defaultValue: 'Pendiente',
      }),
      ...patch,
    }),
  )
const main = (html) => html.slice(html.indexOf('<main '), html.indexOf('</main>'))

test('current unconfirmed branding has a main-view status and explicit manual action outside settings', () => {
  const html = render()
  assert.match(main(html), /aria-label="Recuperar marca compartida"/)
  assert.match(main(html), /role="status"[^>]*>No se pudo confirmar la marca compartida/)
  assert.match(
    main(html),
    /<button[^>]*class="secondary-button"[^>]*>Volver a consultar la marca<\/button>/,
  )
  assert.doesNotMatch(main(html), /disabled=""/)
  assert.equal((html.match(/>Actualizar marca compartida<\/button>/g) ?? []).length, 1)
  assert.equal((html.match(/>Volver a consultar la marca<\/button>/g) ?? []).length, 1)
  assert.match(html, /id="personalization-panel"[^>]*hidden=""/)
  assert.match(main(html), /aria-label="Borrador operativo" value="Pendiente"/)
  assert.equal(refreshes, 0, 'rendering a notice cannot initiate refresh')
})

test('loading disables the main recovery action while preserving the settings refresh control', () => {
  const html = render({ brandingLoading: true })
  assert.match(html, /<button[^>]*disabled=""[^>]*>Volver a consultar la marca<\/button>/)
  assert.match(html, /<button type="button">Actualizar marca compartida<\/button>/)
  assert.match(main(html), /No se pudo confirmar la marca compartida/)
})

for (const [label, patch] of [
  ['no suggested recovery', { brandingRefreshSuggested: false }],
  ['no recovery message', { brandingMessage: null }],
  [
    'an accepted profile',
    {
      sharedBranding: {
        display_name: 'Verified workshop',
        palette_id: 'arcilla',
        logo_state: 'none',
        logo: null,
      },
    },
  ],
]) {
  test(`the main recovery action is absent with ${label}`, () => {
    const html = render(patch)
    assert.doesNotMatch(main(html), /Recuperar marca compartida|Volver a consultar la marca/)
    assert.match(html, />Actualizar marca compartida<\/button>/)
    assert.match(main(html), /aria-label="Borrador operativo" value="Pendiente"/)
    assert.equal(refreshes, 0)
  })
}

test('recovery notice is rendered as plain text without exposing markup or changing fallback identity', () => {
  const html = render({ brandingMessage: '<img src=x onerror=alert(1)>' })
  assert.match(main(html), /&lt;img src=x onerror=alert\(1\)&gt;/)
  assert.doesNotMatch(main(html), /<img/)
  assert.match(html, /class="workshop-identity" aria-label="OCWP, taller activo"/)
})

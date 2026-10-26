import { expect, test, type Page } from '@playwright/test'
import { checkedInOpenBranding } from '../tests/branding/readiness-helper.mjs'

// Synthetic DOM only: no credentials, API mutations, storage or fixture tenants.
test.use({ trace: 'off', video: 'off', screenshot: 'off' })

type State = 'connected' | 'verifying' | 'enabled' | 'absent'
async function render(page: Page, state: State) {
  await page.setContent(
    state === 'connected'
      ? '<h2>Mi sesión</h2><section aria-label="Marca compartida del taller"><h2>Marca compartida del taller</h2></section>'
      : state === 'absent'
        ? '<main></main>'
        : `<button ${state === 'verifying' ? 'disabled' : ''}>Verificar acceso a administración</button>`,
  )
}

for (const [name, initial, transition, expectedClicks] of [
  ['already connected', 'connected', undefined, 0],
  ['explicit verification', 'enabled', undefined, 1],
  ['automatic admission replaces disabled verification', 'verifying', 'connected', 0],
  ['verification becomes available', 'verifying', 'enabled', 1],
] as const) {
  test(`branding helper readiness: ${name}`, async ({ page }) => {
    await render(page, initial)
    let clicks = 0
    let transitioned = false
    // Hold the read's return value while the real DOM makes the interleaving
    // explicit. This is not a timer race, fake assertion or product-state edit.
    const controlledPage = new Proxy(page, {
      get(target, property) {
        if (property === 'getByRole')
          return (...args: Parameters<Page['getByRole']>) => {
            const locator = target.getByRole(...args)
            if (args[0] === 'heading' && args[1]?.name === 'Mi sesión')
              return new Proxy(locator, {
                get(target, property) {
                  if (property === 'isVisible')
                    return async () => {
                      const visible = await target.isVisible()
                      if (transition && !transitioned) {
                        transitioned = true
                        await render(page, transition)
                      }
                      return visible
                    }
                  const value = Reflect.get(target, property)
                  return typeof value === 'function' ? value.bind(target) : value
                },
              })
            if (args[0] === 'button')
              return new Proxy(locator, {
                get(target, property) {
                  if (property === 'click')
                    return async () => {
                      await target.click()
                      clicks++
                      await render(page, 'connected')
                    }
                  const value = Reflect.get(target, property)
                  return typeof value === 'function' ? value.bind(target) : value
                },
              })
            return locator
          }
        const value = Reflect.get(target, property)
        return typeof value === 'function' ? value.bind(target) : value
      },
    })
    await checkedInOpenBranding()(controlledPage)
    expect(clicks).toBe(expectedClicks)
    if (transition) expect(transitioned).toBe(true)
    await expect(page.getByRole('heading', { name: 'Mi sesión', exact: true })).toBeVisible()
    await expect(
      page.getByRole('region', { name: 'Marca compartida del taller', exact: true }),
    ).toBeVisible()
  })
}

for (const state of ['verifying', 'absent'] as const) {
  test(`branding helper readiness rejects permanently ${state} administration`, async ({
    page,
  }) => {
    await render(page, state)
    await expect(checkedInOpenBranding()(page)).rejects.toThrow(/Timeout/)
    await expect(page.getByRole('heading', { name: 'Mi sesión', exact: true })).toHaveCount(0)
  })
}

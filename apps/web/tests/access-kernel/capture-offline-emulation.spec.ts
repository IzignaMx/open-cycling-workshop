import { test, expect } from '@playwright/test'

// Isolates Chromium emulation from App/SW/storage. The document response is
// synthetic; only the uncached probe below tests network failure. No runtime
// getter is overridden and offline is never reapplied after navigation.
test('offline from context creation survives blank and cross-origin documents', async ({
  browser,
}, info) => {
  const context = await browser.newContext({ offline: true, serviceWorkers: 'block' })
  const observations: { url: string; firstScript: boolean; evaluated: boolean }[] = []
  const failures: { url: string; error: string | null }[] = []
  try {
    await context.route('**/offline-emulation-document', (route) =>
      route.fulfill({
        contentType: 'text/html',
        body: '<script>document.documentElement.dataset.initialOnline = String(navigator.onLine)</script>',
      }),
    )
    const page = await context.newPage()
    page.on('requestfailed', (request) =>
      failures.push({ url: request.url(), error: request.failure()?.errorText ?? null }),
    )
    expect(await page.evaluate(() => navigator.onLine)).toBe(false)
    for (const origin of ['http://localhost:5180', 'http://127.0.0.1:5180']) {
      await page.goto(`${origin}/offline-emulation-document`)
      const observation = await page.evaluate(() => ({
        url: location.href,
        firstScript: document.documentElement.dataset.initialOnline === 'true',
        evaluated: navigator.onLine,
      }))
      observations.push(observation)
      expect(await page.locator('html').getAttribute('data-initial-online')).toBe('false')
      expect(observation.evaluated).toBe(false)
    }
    const probe = `http://127.0.0.1:5180/offline-emulation-probe-${Date.now()}`
    expect(
      await page.evaluate(async (url) => {
        try {
          await fetch(url, { cache: 'no-store' })
          return false
        } catch {
          return true
        }
      }, probe),
    ).toBe(true)
    await expect.poll(() => failures.some((failure) => failure.url === probe)).toBe(true)
  } finally {
    await info.attach('offline-emulation-control', {
      body: JSON.stringify({ browser: browser.version(), observations, failures }),
      contentType: 'application/json',
    })
    await context.close()
  }
})

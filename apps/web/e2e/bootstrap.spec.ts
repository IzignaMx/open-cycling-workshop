import { expect, test } from '@playwright/test'

// Actual browser security classification, not an isSecureContext override.
// Reserved name is fulfilled locally; no DNS, TLS bypass or external traffic.
test('insecure document blocks runtime before storage and API access', async ({
  page,
  request,
}) => {
  const apiRequests: string[] = []
  await page.route('**/*', async (route) => {
    const url = new URL(route.request().url())
    if (url.pathname.startsWith('/api/')) {
      apiRequests.push(url.pathname)
      await route.abort()
      return
    }
    expect(url.origin).toBe('http://ocwp-bootstrap.invalid')
    expect(
      url.pathname === '/' ||
        /^\/assets\/[a-zA-Z0-9_.-]+$/.test(url.pathname) ||
        ['/registerSW.js', '/manifest.webmanifest'].includes(url.pathname),
    ).toBe(true)
    // Fetch only current local preview bytes; never forward the reserved host.
    const response = await request.get(`http://127.0.0.1:5173${url.pathname}`)
    expect(response.ok()).toBe(true)
    await route.fulfill({ response })
  })
  await page.addInitScript(() => {
    let reads = 0
    Object.defineProperty(window, '__bootstrapStorageReads', { get: () => reads })
    Object.defineProperty(window, 'sessionStorage', {
      get() {
        reads += 1
        throw new Error('storage must not be read')
      },
    })
  })
  await page.goto('http://ocwp-bootstrap.invalid/')
  expect(await page.evaluate(() => window.isSecureContext)).toBe(false)
  await expect(
    page.getByRole('heading', { name: 'No se puede iniciar el taller aquí' }),
  ).toBeVisible()
  await expect(page.getByRole('alert')).toContainText('HTTPS confiable')
  await expect(page.getByRole('alert')).toContainText('no transfiere borradores')
  await expect(page.locator('input[type="password"]')).toHaveCount(0)
  expect(await page.evaluate(() => Reflect.get(window, '__bootstrapStorageReads'))).toBe(0)
  expect(apiRequests).toEqual([])
})

test('secure loopback with inaccessible session storage shows safe startup failure', async ({
  page,
}) => {
  const apiRequests: string[] = []
  await page.route('**/api/**', async (route) => {
    apiRequests.push(route.request().url())
    await route.abort()
  })
  await page.addInitScript(() => {
    Object.defineProperty(window, 'sessionStorage', {
      get() {
        throw new Error('private storage failure')
      },
    })
  })
  await page.goto('/')
  expect(await page.evaluate(() => window.isSecureContext)).toBe(true)
  await expect(page.getByRole('alert')).toContainText('almacenamiento de sesión')
  await expect(page.getByRole('alert')).not.toContainText('private storage failure')
  await expect(page.locator('input[type="password"]')).toHaveCount(0)
  expect(apiRequests).toEqual([])
})

import type { BrowserContext } from '@playwright/test'

/** The live caller separately pins baseURL to the approved HTTPS project URL. */
export async function guardPublicSiteNetwork(
  context: BrowserContext,
  baseURL: string,
  rejected: string[],
): Promise<void> {
  let requests = 0
  await context.route('**/*', async (route) => {
    const request = route.request()
    if (!request.url().startsWith(baseURL) || request.method() !== 'GET') {
      rejected.push('destination')
      await route.abort()
      return
    }
    requests += 1
    if (requests > 32) {
      rejected.push('request-budget')
      await route.abort()
      return
    }
    // route.continue follows redirects without calling this guard again.
    // Fetch at most this one destination, and preserve its actual response.
    const response = await route.fetch({ maxRedirects: 0, maxRetries: 0, timeout: 5000 })
    try {
      if (response.status() !== 200 || response.url() !== request.url()) {
        rejected.push('redirect-or-status')
        await route.abort()
        return
      }
      await route.fulfill({ response })
    } finally {
      await response.dispose()
    }
  })
}

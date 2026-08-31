import { createRequire } from 'node:module'

// Resolve Playwright from the web workspace regardless of where this script
// file lives (it is invoked with an absolute path from the Python runner).
const webPackage = new URL('../../apps/web/package.json', import.meta.url)
const require = createRequire(webPackage)
const { chromium } = require('@playwright/test')

const url = process.argv[2]
const timeoutMs = Number(process.env.OCWP_BENCHMARK_TIMEOUT_MS ?? '300000')

if (!url) {
  console.error('usage: node run_indexeddb_benchmark_browser.mjs <url>')
  process.exit(2)
}

const browser = await chromium.launch({ headless: true })
try {
  const page = await browser.newPage()
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60_000 })
  // The benchmark page signals completion by setting the document title.
  await page.waitForFunction(() => document.title === 'DONE', null, {
    timeout: timeoutMs,
  })
  const text = await page.locator('#result').textContent()
  console.log(text)
} finally {
  await browser.close()
}

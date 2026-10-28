import { defineConfig } from '@playwright/test'
import preview from './playwright.public-site.config'

if (process.env.PUBLIC_SITE_URL !== 'https://izignamx.github.io/open-cycling-workshop/') {
  throw new Error('Live public presentation destination is not the approved Pages URL')
}

export default defineConfig({
  ...preview,
  outputDir: './test-results/public-site-live',
  reporter: [
    ['line'],
    ['html', { open: 'never', outputFolder: './playwright-report/public-site-live' }],
  ],
  use: { ...preview.use, baseURL: process.env.PUBLIC_SITE_URL, serviceWorkers: 'block' },
  webServer: undefined,
})

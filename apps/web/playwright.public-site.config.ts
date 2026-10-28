import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tools/public-site',
  outputDir: './test-results/public-site',
  timeout: 30_000,
  retries: 0,
  workers: 1,
  reporter: [
    ['line'],
    ['html', { open: 'never', outputFolder: './playwright-report/public-site' }],
  ],
  use: { baseURL: 'http://127.0.0.1:5181/open-cycling-workshop/', trace: 'retain-on-failure' },
  webServer: {
    command: 'python3 -m http.server 5181 --bind 127.0.0.1 --directory ../../artifacts/public-site',
    url: 'http://127.0.0.1:5181/open-cycling-workshop/',
    reuseExistingServer: false,
    timeout: 15_000,
  },
})

import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './tests/access-kernel',
  testMatch: 'browser.spec.ts',
  timeout: 30_000,
  retries: 0,
  workers: 1,
  reporter: 'line',
  use: { baseURL: 'http://127.0.0.1:5175', trace: 'retain-on-failure' },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command:
      'node node_modules/vite/bin/vite.js preview --config tools/kernel-browser/vite.config.ts --host 127.0.0.1 --port 5175',
    url: 'http://127.0.0.1:5175',
    reuseExistingServer: false,
  },
})

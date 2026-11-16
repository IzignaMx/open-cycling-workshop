import { defineConfig, devices } from '@playwright/test'
const env = (globalThis as unknown as { process: { env: Record<string, string | undefined> } })
  .process.env
export default defineConfig({
  testDir: './tests/access-kernel',
  testMatch: 'capture-app-origin-isolation.spec.ts',
  workers: 1,
  retries: 0,
  timeout: 90000,
  outputDir: '.tmp-capture-origin-results',
  reporter: [['line'], ['json', { outputFile: '.tmp-capture-origin-results/results.json' }]],
  use: {
    trace: 'on',
    launchOptions: env.OCWP_CHROMIUM_EXECUTABLE
      ? { executablePath: env.OCWP_CHROMIUM_EXECUTABLE }
      : {},
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  // The spec owns both fixed-port servers to exercise live failed replacement.
})

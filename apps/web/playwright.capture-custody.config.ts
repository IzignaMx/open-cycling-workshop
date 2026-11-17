import { defineConfig, devices } from '@playwright/test'
const env = (globalThis as unknown as { process: { env: Record<string, string | undefined> } })
  .process.env
export default defineConfig({
  testDir: './tests/access-kernel',
  testMatch: 'capture-custody-native.spec.ts',
  workers: 1,
  retries: 0,
  timeout: 60000,
  outputDir: '.tmp-capture-custody-results',
  reporter: [['line'], ['json', { outputFile: '.tmp-capture-custody-results/results.json' }]],
  use: {
    trace: 'on',
    serviceWorkers: 'block',
    launchOptions: env.OCWP_CHROMIUM_EXECUTABLE
      ? { executablePath: env.OCWP_CHROMIUM_EXECUTABLE }
      : {},
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [5182, 5183].map((port) => ({
    command: `node node_modules/vite/bin/vite.js preview --config tools/capture-custody-browser/vite.config.ts --host 127.0.0.1 --port ${port} --strictPort`,
    url: `http://127.0.0.1:${port}`,
    reuseExistingServer: false,
  })),
})

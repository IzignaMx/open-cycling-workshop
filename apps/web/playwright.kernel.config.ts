import { defineConfig, devices } from '@playwright/test'

const env = (globalThis as unknown as { process: { env: Record<string, string | undefined> } })
  .process.env

export default defineConfig({
  testDir: './tests/access-kernel',
  testMatch: ['browser.spec.ts', 'baseline-browser.spec.ts'],
  timeout: 30_000,
  retries: 0,
  workers: 1,
  outputDir: '.tmp-kernel-browser-results',
  reporter: [['line'], ['json', { outputFile: '.tmp-kernel-browser-results/results.json' }]],
  use: {
    baseURL: 'http://127.0.0.1:5175',
    trace: 'retain-on-failure',
    launchOptions: env.OCWP_CHROMIUM_EXECUTABLE
      ? { executablePath: env.OCWP_CHROMIUM_EXECUTABLE }
      : {},
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      command: `${env.OCWP_KERNEL_PYTHON ?? 'uv run python'} tools/kernel-browser/baseline-server.py`,
      url: 'http://127.0.0.1:8007/health/ready',
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command:
        'node node_modules/vite/bin/vite.js preview --config tools/kernel-browser/vite.config.ts --host 127.0.0.1 --port 5175',
      url: 'http://127.0.0.1:5175',
      reuseExistingServer: false,
    },
  ],
})

import { defineConfig, devices } from '@playwright/test'
const env = (globalThis as unknown as { process: { env: Record<string, string | undefined> } })
  .process.env
export default defineConfig({
  testDir: './tests/access-kernel',
  testMatch: 'capture-app-native.spec.ts',
  workers: 1,
  retries: 0,
  timeout: 60000,
  outputDir: '.tmp-capture-app-results',
  reporter: [['line'], ['json', { outputFile: '.tmp-capture-app-results/results.json' }]],
  use: {
    trace: 'on',
    launchOptions: env.OCWP_CHROMIUM_EXECUTABLE
      ? { executablePath: env.OCWP_CHROMIUM_EXECUTABLE }
      : {},
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: (['old', 'current'] as const).map((kind, index) => ({
    command: `node ../../scripts/e2e/capture_app_server.mjs ../../artifacts/capture-app-${kind} ${5180 + index}`,
    url: `http://127.0.0.1:${5180 + index}/evidence.json`,
    reuseExistingServer: false,
  })),
})

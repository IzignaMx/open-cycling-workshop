import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  timeout: 45_000,
  expect: { timeout: 10_000 },
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? [['line'], ['html', { open: 'never' }]] : 'line',
  use: {
    baseURL: 'http://127.0.0.1:5173',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: [
    {
      command:
        'cd ../.. && uv run uvicorn cycling_workshop.runtime:app --app-dir services/platform/src --host 127.0.0.1 --port 8000',
      url: 'http://127.0.0.1:8000/health/ready',
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
      env: {
        OCWP_DATABASE_URL: process.env.OCWP_E2E_DATABASE_URL ?? '',
        OCWP_AUTH_SECRET: process.env.OCWP_AUTH_SECRET ?? 'e2e-only-secret-00000000000000000000000000000000',
        OCWP_ENVIRONMENT: 'test',
      },
    },
    {
      command: process.env.CI ? 'pnpm exec vite preview --host 127.0.0.1 --port 5173' : 'pnpm dev -- --host 127.0.0.1',
      url: 'http://127.0.0.1:5173',
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
  ],
})

import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e-real',
  testMatch: 'direction.spec.ts',
  workers: 1,
  timeout: 45_000,
  use: { baseURL: 'http://127.0.0.1:4183', viewport: { width: 390, height: 844 }, trace: 'off' },
  webServer: {
    command: 'npm run dev -- --host 127.0.0.1 --port 4183 --strictPort',
    url: 'http://127.0.0.1:4183',
    reuseExistingServer: false,
    env: { VITE_API_MODE: 'http', VITE_API_PROXY_TARGET: process.env.SITRAP_TEST_API! },
  },
})

import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e-real',
  testMatch: 'sales.spec.ts',
  workers: 1,
  timeout: 120000,
  outputDir: '../.local/playwright-sales',
  use: { baseURL: 'http://127.0.0.1:4182', headless: true, viewport: { width: 390, height: 844 }, trace: 'off' },
  webServer: {
    command: 'npm run dev -- --host 127.0.0.1 --port 4182 --strictPort',
    url: 'http://127.0.0.1:4182',
    reuseExistingServer: false,
    env: { VITE_API_MODE: 'http', VITE_API_PROXY_TARGET: process.env.SITRAP_TEST_API! },
  },
})

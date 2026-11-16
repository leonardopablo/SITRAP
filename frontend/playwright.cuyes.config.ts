import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e-real',
  workers: 1,
  timeout: 90000,
  outputDir: '../.local/playwright-cuyes',
  use: { baseURL: 'http://127.0.0.1:4181', headless: true, viewport: { width: 390, height: 844 }, trace: 'retain-on-failure' },
  webServer: {
    command: 'npm run dev -- --host 127.0.0.1 --port 4181 --strictPort',
    url: 'http://127.0.0.1:4181',
    reuseExistingServer: false,
    env: { VITE_API_MODE: 'http', VITE_API_PROXY_TARGET: process.env.SITRAP_TEST_API! },
  },
})

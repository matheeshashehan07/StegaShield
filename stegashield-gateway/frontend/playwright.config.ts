import { defineConfig } from '@playwright/test'
export default defineConfig({
  testDir: './e2e', fullyParallel: false, workers: 1,
  use: { baseURL: 'http://127.0.0.1:5173', headless: true, screenshot: 'only-on-failure', channel: process.env.PLAYWRIGHT_CHANNEL || undefined },
  webServer: { command: 'npm run dev', url: 'http://127.0.0.1:5173', reuseExistingServer: !process.env.CI },
})

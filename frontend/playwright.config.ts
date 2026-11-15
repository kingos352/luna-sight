import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  timeout: 180_000,
  expect: { timeout: 25_000 },
  workers: 1,
  use: {
    baseURL: process.env.LUNA_APP_URL || 'http://127.0.0.1:8511',
    channel: 'msedge',
    headless: true,
    actionTimeout: 20_000,
    viewport: { width: 1600, height: 1200 },
    launchOptions: { args: ['--enable-unsafe-swiftshader'] },
    screenshot: 'only-on-failure',
  },
});

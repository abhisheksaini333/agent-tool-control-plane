import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './e2e', workers: 1, timeout: 90000, fullyParallel: false,
  use: { baseURL: 'http://localhost:5294', viewport: { width: 1440, height: 1000 },
    launchOptions: process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {} },
  reporter: [['list']],
});

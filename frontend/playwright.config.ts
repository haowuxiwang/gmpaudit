import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'html',
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:18000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        channel: 'chromium',
      },
    },
  ],
  webServer: [
    {
      // Build frontend and copy to backend static directory
      command: 'npm run build && rm -rf ../backend/static && cp -r build ../backend/static',
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
    {
      // Start backend on port 18000 (serves API + frontend static files)
      command: 'python -m uvicorn app.main:app --host 127.0.0.1 --port 18000',
      cwd: '../backend',
      url: 'http://localhost:18000/api/health',
      reuseExistingServer: !process.env.CI,
      timeout: 30_000,
    },
  ],
});

import { test, expect } from '@playwright/test';

test.describe('API Health Checks', () => {
  test('health endpoint returns ok', async ({ request }) => {
    const response = await request.get('/api/health');
    expect(response.ok()).toBeTruthy();
    const body = await response.json();
    expect(body.status).toBe('ok');
    expect(body.service).toBe('AuditBee');
  });

  test('health/db endpoint returns database status', async ({ request }) => {
    const response = await request.get('/api/health/db');
    expect(response.ok()).toBeTruthy();
    const body = await response.json();
    expect(body.status).toBe('ok');
    expect(body.journal_mode).toBeDefined();
  });
});

test.describe('API Endpoint Smoke Tests', () => {
  const endpoints = [
    { name: 'documents list', path: '/api/documents/' },
    { name: 'audit tasks list', path: '/api/audit/tasks' },
    { name: 'reports list', path: '/api/reports/' },
    { name: 'config', path: '/api/config/' },
    { name: 'alerts list', path: '/api/alerts/' },
    { name: 'dashboard stats', path: '/api/audit/dashboard' },
    { name: 'KG status', path: '/api/kg/status' },
  ];

  for (const ep of endpoints) {
    test(`${ep.name} endpoint responds`, async ({ request }) => {
      const response = await request.get(ep.path);
      expect(response.ok(), `${ep.name} should return 2xx`).toBeTruthy();
    });
  }
});

test.describe('Static Frontend Serving', () => {
  test('root path serves the SPA', async ({ page }) => {
    const response = await page.goto('/');
    expect(response?.ok()).toBeTruthy();
    await expect(page).toHaveTitle(/AuditBee|React/i);
  });

  test('SPA route /documents works', async ({ page }) => {
    await page.goto('/documents');
    await expect(page.locator('.ant-layout')).toBeVisible({ timeout: 10000 });
  });

  test('SPA route /audit works', async ({ page }) => {
    await page.goto('/audit');
    await expect(page.locator('.ant-layout')).toBeVisible({ timeout: 10000 });
  });
});

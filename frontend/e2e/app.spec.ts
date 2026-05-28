import { test, expect } from '@playwright/test';

test.describe('AuditBee App', () => {
  test('should load dashboard page', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveTitle(/AuditBee|React/i);
  });

  test('should navigate to documents page', async ({ page }) => {
    await page.goto('/');
    await page.click('a[href="/documents"], text=文档');
    await expect(page).toHaveURL(/\/documents/);
  });

  test('should navigate to audit tasks page', async ({ page }) => {
    await page.goto('/');
    await page.click('a[href="/audit"], text=审计');
    await expect(page).toHaveURL(/\/audit/);
  });

  test('should navigate to reports page', async ({ page }) => {
    await page.goto('/');
    await page.click('a[href="/reports"], text=报告');
    await expect(page).toHaveURL(/\/reports/);
  });

  test('should navigate to settings page', async ({ page }) => {
    await page.goto('/');
    await page.click('a[href="/settings"], text=设置');
    await expect(page).toHaveURL(/\/settings/);
  });

  test('should show 404 for unknown routes', async ({ page }) => {
    await page.goto('/nonexistent-page');
    await expect(page.locator('text=404')).toBeVisible();
  });
});

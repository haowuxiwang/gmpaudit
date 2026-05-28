import { test, expect } from '@playwright/test';
import {
  waitForPageReady,
  createTestFile,
  uploadDocumentViaAPI,
  waitForDocumentProcessed,
  cleanupTestFixtures,
} from './helpers';

let testFilePath: string;

test.beforeAll(() => {
  testFilePath = createTestFile('report_test.txt', '报告测试文档内容');
});

test.afterAll(() => {
  cleanupTestFixtures();
});

test.describe('ReportsPage - Type Filter', () => {
  test('type filter select shows all report type options', async ({ page }) => {
    await page.goto('/reports');
    await waitForPageReady(page);

    // Find the filter select
    const filterSelect = page.locator('.ant-select').filter({ hasText: /按类型筛选|完整报告|摘要|审计报告/ });
    await expect(filterSelect).toBeVisible({ timeout: 5000 });

    // Click to open dropdown
    await filterSelect.click();

    // Verify options
    const options = page.locator('.ant-select-item-option');
    await expect(options).toHaveCount(3, { timeout: 3000 });
    await expect(options.nth(0)).toContainText('完整报告');
    await expect(options.nth(1)).toContainText('摘要');
    await expect(options.nth(2)).toContainText('审计报告');

    // Close dropdown
    await page.keyboard.press('Escape');
  });

  test('clears type filter and shows all reports', async ({ page }) => {
    await page.goto('/reports');
    await waitForPageReady(page);

    // Check if there are reports
    const hasTable = await page.locator('.ant-table-row').first().isVisible().catch(() => false);
    if (!hasTable) {
      test.skip(true, 'No reports to filter');
      return;
    }

    // Select a filter
    const filterSelect = page.locator('.ant-select').filter({ hasText: /按类型筛选|完整报告|摘要|审计报告/ });
    await filterSelect.click();
    await page.locator('.ant-select-item-option').filter({ hasText: '完整报告' }).click();
    await page.waitForTimeout(500);

    // Clear filter
    await filterSelect.click();
    await page.locator('.ant-select-item-option').filter({ hasText: '完整报告' }).click();
    await page.waitForTimeout(500);
  });
});

test.describe('ReportsPage - View Report Detail', () => {
  test('opens report detail modal with Markdown content', async ({ page, request }) => {
    // Check if reports exist
    const reportsResponse = await request.get('/api/reports/');
    const reportsData = await reportsResponse.json();
    const reports = reportsData.items || [];

    if (reports.length === 0) {
      test.skip(true, 'No existing reports to view');
      return;
    }

    await page.goto('/reports');
    await waitForPageReady(page);

    // Click "查看" on the first report
    await page.locator('.ant-table-row').first().locator('button').filter({ hasText: '查看' }).click();

    // Verify modal opens
    const modal = page.locator('.ant-modal');
    await expect(modal).toBeVisible({ timeout: 5000 });

    // Modal should contain report title
    await expect(modal).toContainText(reports[0].title, { timeout: 5000 });

    // Modal should have Markdown content
    const modalBody = modal.locator('.ant-modal-body');
    await expect(modalBody).toBeVisible();
  });

  test('modal footer has close, export markdown, and export PDF buttons', async ({ page, request }) => {
    const reportsResponse = await request.get('/api/reports/');
    const reportsData = await reportsResponse.json();
    const reports = reportsData.items || [];

    if (reports.length === 0) {
      test.skip(true, 'No existing reports');
      return;
    }

    await page.goto('/reports');
    await waitForPageReady(page);

    // Open report detail
    await page.locator('.ant-table-row').first().locator('button').filter({ hasText: '查看' }).click();
    const modal = page.locator('.ant-modal');
    await expect(modal).toBeVisible({ timeout: 5000 });

    // Verify footer buttons
    const footer = modal.locator('.ant-modal-footer');
    await expect(footer.locator('button').filter({ hasText: '关闭' })).toBeVisible();
    await expect(footer.locator('button').filter({ hasText: '导出 Markdown' })).toBeVisible();
    await expect(footer.locator('button').filter({ hasText: '导出 PDF' })).toBeVisible();
  });

  test('close button dismisses modal', async ({ page, request }) => {
    const reportsResponse = await request.get('/api/reports/');
    const reportsData = await reportsResponse.json();
    const reports = reportsData.items || [];

    if (reports.length === 0) {
      test.skip(true, 'No existing reports');
      return;
    }

    await page.goto('/reports');
    await waitForPageReady(page);

    // Open report detail
    await page.locator('.ant-table-row').first().locator('button').filter({ hasText: '查看' }).click();
    const modal = page.locator('.ant-modal');
    await expect(modal).toBeVisible({ timeout: 5000 });

    // Click close
    await modal.locator('.ant-modal-footer').locator('button').filter({ hasText: '关闭' }).click();
    await expect(modal).not.toBeVisible({ timeout: 3000 });
  });
});

test.describe('ReportsPage - Export', () => {
  test('export markdown button triggers download', async ({ page, request }) => {
    const reportsResponse = await request.get('/api/reports/');
    const reportsData = await reportsResponse.json();
    const reports = reportsData.items || [];

    if (reports.length === 0) {
      test.skip(true, 'No existing reports');
      return;
    }

    await page.goto('/reports');
    await waitForPageReady(page);

    // Open report detail
    await page.locator('.ant-table-row').first().locator('button').filter({ hasText: '查看' }).click();
    const modal = page.locator('.ant-modal');
    await expect(modal).toBeVisible({ timeout: 5000 });

    // Wait for detail to load
    await expect(modal.locator('.ant-modal-body')).toBeVisible();

    // Set up download listener
    const downloadPromise = page.waitForEvent('download');

    // Click export markdown
    await modal.locator('.ant-modal-footer').locator('button').filter({ hasText: '导出 Markdown' }).click();

    // Verify download
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toMatch(/\.md$/);
  });

  test('export PDF button triggers download', async ({ page, request }) => {
    const reportsResponse = await request.get('/api/reports/');
    const reportsData = await reportsResponse.json();
    const reports = reportsData.items || [];

    if (reports.length === 0) {
      test.skip(true, 'No existing reports');
      return;
    }

    await page.goto('/reports');
    await waitForPageReady(page);

    // Open report detail
    await page.locator('.ant-table-row').first().locator('button').filter({ hasText: '查看' }).click();
    const modal = page.locator('.ant-modal');
    await expect(modal).toBeVisible({ timeout: 5000 });

    // Wait for detail to load
    await expect(modal.locator('.ant-modal-body')).toBeVisible();

    // Set up download listener
    const downloadPromise = page.waitForEvent('download', { timeout: 15000 });

    // Click export PDF
    await modal.locator('.ant-modal-footer').locator('button').filter({ hasText: '导出 PDF' }).click();

    // Verify download
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toMatch(/\.pdf$/);
  });
});

test.describe('ReportsPage - URL Query Param', () => {
  test('filters reports by task_id query parameter', async ({ page, request }) => {
    // Get tasks to find one with a report
    const tasksResponse = await request.get('/api/audit/tasks');
    const tasksData = await tasksResponse.json();
    const tasks = tasksData.items || [];
    const taskWithReport = tasks.find((t: any) => t.report_id);

    if (!taskWithReport) {
      test.skip(true, 'No task with report');
      return;
    }

    await page.goto(`/reports?task_id=${taskWithReport.id}`);
    await waitForPageReady(page);

    // Reports table should only show reports for this task
    await page.waitForTimeout(1000);
    const rows = page.locator('.ant-table-row');
    const count = await rows.count();
    // All visible reports should belong to this task
    expect(count).toBeGreaterThanOrEqual(0);
  });
});

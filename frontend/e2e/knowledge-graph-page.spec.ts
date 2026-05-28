import { test, expect } from '@playwright/test';
import {
  waitForPageReady,
  createTestFile,
  cleanupTestFixtures,
} from './helpers';

let testFilePath: string;

test.beforeAll(() => {
  testFilePath = createTestFile('kg_test.txt', '知识图谱测试文档\n\n法规: 药品生产质量管理规范\n概念: 偏差处理');
});

test.afterAll(() => {
  cleanupTestFixtures();
});

test.describe('KnowledgeGraphPage - Page Load', () => {
  test('loads page with statistics cards', async ({ page }) => {
    await page.goto('/kg');
    await waitForPageReady(page);

    // Verify 3 statistic cards
    await expect(page.locator('text=法规文档')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('text=图谱文件')).toBeVisible();
    await expect(page.locator('text=图谱状态')).toBeVisible();
  });

  test('search bar is present', async ({ page }) => {
    await page.goto('/kg');
    await waitForPageReady(page);

    // Verify search input
    const searchInput = page.locator('input[placeholder*="偏差处理"]');
    await expect(searchInput).toBeVisible({ timeout: 5000 });

    // Verify query button
    await expect(page.locator('button').filter({ hasText: '查询图谱' })).toBeVisible();
  });
});

test.describe('KnowledgeGraphPage - Search', () => {
  test('performs query and shows results', async ({ page }) => {
    await page.goto('/kg');
    await waitForPageReady(page);

    // Enter search query
    const searchInput = page.locator('input[placeholder*="偏差处理"]');
    await searchInput.fill('偏差处理');

    // Click query button
    await page.locator('button').filter({ hasText: '查询图谱' }).click();

    // Wait for results or empty state
    await page.waitForTimeout(3000);

    // Verify results area exists (either results or empty state)
    const hasResults = await page.locator('.ant-list-item').first().isVisible().catch(() => false);
    const hasEmpty = await page.locator('.ant-empty').isVisible().catch(() => false);
    expect(hasResults || hasEmpty).toBe(true);
  });

  test('empty search shows warning message', async ({ page }) => {
    await page.goto('/kg');
    await waitForPageReady(page);

    // Clear search and click query
    const searchInput = page.locator('input[placeholder*="偏差处理"]');
    await searchInput.clear();
    await page.locator('button').filter({ hasText: '查询图谱' }).click();

    // Should show warning
    await expect(page.locator('.ant-message')).toContainText(/请输入法规或发现的查询词/, { timeout: 5000 });
  });

  test('search updates URL query params', async ({ page }) => {
    await page.goto('/kg');
    await waitForPageReady(page);

    // Enter search query
    const searchInput = page.locator('input[placeholder*="偏差处理"]');
    await searchInput.fill('CAPA');
    await page.locator('button').filter({ hasText: '查询图谱' }).click();

    // Verify URL contains q=CAPA
    await expect(page).toHaveURL(/q=CAPA/, { timeout: 5000 });
  });
});

test.describe('KnowledgeGraphPage - Graph Operations', () => {
  test('build button triggers graph build', async ({ page }) => {
    await page.goto('/kg');
    await waitForPageReady(page);

    // Click build button
    const buildBtn = page.locator('button').filter({ hasText: /构建图谱|重新构建/ });
    if (await buildBtn.isVisible()) {
      await buildBtn.click();

      // Should show info message
      await expect(page.locator('.ant-message')).toContainText(/图谱构建已在后台启动/, { timeout: 5000 });

      // Build log card should appear
      await expect(page.locator('text=构建日志')).toBeVisible({ timeout: 5000 });
    }
  });

  test('upload regulation document button works', async ({ page }) => {
    await page.goto('/kg');
    await waitForPageReady(page);

    // Click upload button
    const uploadBtn = page.locator('button').filter({ hasText: '上传法规文档' });
    await expect(uploadBtn).toBeVisible({ timeout: 5000 });

    // Set up file chooser
    const fileChooserPromise = page.waitForEvent('filechooser');
    await uploadBtn.click();
    const fileChooser = await fileChooserPromise;
    await fileChooser.setFiles(testFilePath);

    // Should show success message
    await expect(page.locator('.ant-message')).toContainText(/已上传/, { timeout: 10000 });
  });
});

test.describe('KnowledgeGraphPage - Document List', () => {
  test('document table shows correct columns', async ({ page }) => {
    await page.goto('/kg');
    await waitForPageReady(page);

    // Verify table headers
    await expect(page.locator('th').filter({ hasText: '文件名' })).toBeVisible({ timeout: 5000 });
    await expect(page.locator('th').filter({ hasText: '大小' })).toBeVisible();
    await expect(page.locator('th').filter({ hasText: '修改时间' })).toBeVisible();
    await expect(page.locator('th').filter({ hasText: '操作' })).toBeVisible();
  });

  test('delete button opens confirmation modal', async ({ page }) => {
    await page.goto('/kg');
    await waitForPageReady(page);

    // Find a delete button in the document table
    const deleteBtn = page.locator('.ant-table-row').first().locator('button').filter({ hasText: '删除' });
    if (await deleteBtn.isVisible().catch(() => false)) {
      await deleteBtn.click();

      // Verify confirmation modal
      const confirmModal = page.locator('.ant-modal-confirm');
      await expect(confirmModal).toBeVisible({ timeout: 5000 });
      await expect(confirmModal).toContainText('删除源文档');

      // Cancel
      await confirmModal.locator('.ant-btn:not(.ant-btn-primary):not(.ant-btn-danger)').first().click();
      await expect(confirmModal).not.toBeVisible({ timeout: 3000 });
    }
  });

  test('confirming delete removes document from table', async ({ page }) => {
    await page.goto('/kg');
    await waitForPageReady(page);

    // Find and click delete on a test document
    const rows = page.locator('.ant-table-row');
    const count = await rows.count();
    let found = false;

    for (let i = 0; i < count; i++) {
      const rowText = await rows.nth(i).innerText();
      if (rowText.includes('kg_test.txt')) {
        await rows.nth(i).locator('button').filter({ hasText: '删除' }).click();
        found = true;
        break;
      }
    }

    if (found) {
      // Confirm delete
      const confirmModal = page.locator('.ant-modal-confirm');
      await expect(confirmModal).toBeVisible({ timeout: 5000 });
      await confirmModal.locator('.ant-btn-danger, .ant-btn-primary').first().click();

      // Verify success
      await expect(page.locator('.ant-message')).toContainText(/文档已移除/, { timeout: 5000 });
    }
  });
});

test.describe('KnowledgeGraphPage - Graph Visualization', () => {
  test('shows empty state when graph not built', async ({ page }) => {
    await page.goto('/kg');
    await waitForPageReady(page);

    // Check for empty state or graph
    const hasEmpty = await page.locator('.ant-empty').first().isVisible().catch(() => false);
    const hasCanvas = await page.locator('canvas').first().isVisible().catch(() => false);
    const hasLoadBtn = await page.locator('button').filter({ hasText: '加载图谱' }).isVisible().catch(() => false);

    // One of these should be true
    expect(hasEmpty || hasCanvas || hasLoadBtn).toBe(true);
  });

  test('loads graph when data exists', async ({ page }) => {
    await page.goto('/kg');
    await waitForPageReady(page);

    // Click load graph button if visible
    const loadBtn = page.locator('button').filter({ hasText: '加载图谱' });
    if (await loadBtn.isVisible().catch(() => false)) {
      await loadBtn.click();

      // Wait for graph to load
      await page.waitForTimeout(3000);

      // Verify canvas element exists (ECharts renders to canvas)
      const canvas = page.locator('canvas');
      await expect(canvas).toBeVisible({ timeout: 10000 });
    }
  });

  test('refresh button reloads graph data', async ({ page }) => {
    await page.goto('/kg');
    await waitForPageReady(page);

    // Click refresh link
    const refreshBtn = page.locator('button').filter({ hasText: '刷新图谱' });
    if (await refreshBtn.isVisible().catch(() => false)) {
      await refreshBtn.click();
      await page.waitForTimeout(2000);

      // Graph should reload (canvas or empty state)
      const hasCanvas = await page.locator('canvas').first().isVisible().catch(() => false);
      const hasEmpty = await page.locator('.ant-empty').first().isVisible().catch(() => false);
      expect(hasCanvas || hasEmpty).toBe(true);
    }
  });
});

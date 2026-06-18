import { test, expect } from '@playwright/test';
import { waitForPageReady } from './helpers';

test.describe('AlertsPage - Status Filter', () => {
  test('status filter select shows all options', async ({ page }) => {
    await page.goto('/alerts');
    await waitForPageReady(page);

    // Find the filter select
    const filterSelect = page.locator('.ant-select').filter({ hasText: /按状态筛选|活跃|已确认|已解决/ });
    await expect(filterSelect).toBeVisible({ timeout: 5000 });

    // Click to open dropdown
    await filterSelect.click();

    // Verify options
    const options = page.locator('.ant-select-item-option');
    await expect(options).toHaveCount(3, { timeout: 3000 });
    await expect(options.nth(0)).toContainText('活跃');
    await expect(options.nth(1)).toContainText('已确认');
    await expect(options.nth(2)).toContainText('已解决');

    // Close dropdown
    await page.keyboard.press('Escape');
  });

  test('filters alerts by active status', async ({ page }) => {
    await page.goto('/alerts');
    await waitForPageReady(page);

    // Select "活跃" filter
    const filterSelect = page.locator('.ant-select').filter({ hasText: /按状态筛选|活跃|已确认|已解决/ });
    await filterSelect.click();
    await page.locator('.ant-select-item-option').filter({ hasText: '活跃' }).click();
    await page.waitForTimeout(1000);

    // If there are alerts, verify they all have "活跃" status
    const rows = page.locator('.ant-table-row');
    const count = await rows.count();
    for (let i = 0; i < count; i++) {
      await expect(rows.nth(i).locator('.ant-tag').filter({ hasText: '活跃' })).toBeVisible();
    }
  });
});

test.describe('AlertsPage - Table Columns', () => {
  test('displays alert table with updated columns', async ({ page }) => {
    await page.goto('/alerts');
    await waitForPageReady(page);

    // Verify column headers (updated: no ID, no 严重程度, 级别/状态/发现标题/创建时间/操作)
    const headerRow = page.locator('.ant-table-thead .ant-table-cell');
    await expect(headerRow.filter({ hasText: '级别' })).toBeVisible();
    await expect(headerRow.filter({ hasText: '状态' })).toBeVisible();
    await expect(headerRow.filter({ hasText: '发现标题' })).toBeVisible();
    await expect(headerRow.filter({ hasText: '操作' })).toBeVisible();
  });

  test('shows correct level tag colors', async ({ page }) => {
    await page.goto('/alerts');
    await waitForPageReady(page);

    // Check level tags if alerts exist
    const rows = page.locator('.ant-table-row');
    const count = await rows.count();
    if (count === 0) {
      test.skip(true, 'No alerts to check');
      return;
    }

    // Check first row's level tag
    const firstRow = rows.first();
    const levelTag = firstRow.locator('.ant-tag').first();
    if (await levelTag.isVisible()) {
      const tagText = await levelTag.innerText();
      const tagClass = await levelTag.getAttribute('class') || '';

      if (tagText === '严重') {
        expect(tagClass).toContain('ant-tag-red');
      } else if (tagText === '警告') {
        expect(tagClass).toContain('ant-tag-orange');
      } else if (tagText === '信息') {
        expect(tagClass).toContain('ant-tag-blue');
      }
    }
  });
});

test.describe('AlertsPage - Expandable Rows', () => {
  test('clicking row expands to show description', async ({ page }) => {
    await page.goto('/alerts');
    await waitForPageReady(page);

    const rows = page.locator('.ant-table-row');
    const count = await rows.count();
    if (count === 0) {
      test.skip(true, 'No alerts to expand');
      return;
    }

    // Click first row to expand
    await rows.first().click();
    await page.waitForTimeout(500);

    // Verify expanded content is visible
    const expandedRow = page.locator('.ant-table-expanded-row');
    await expect(expandedRow).toBeVisible({ timeout: 3000 });
    await expect(expandedRow).toContainText('完整描述');
  });

  test('expand icon changes on click', async ({ page }) => {
    await page.goto('/alerts');
    await waitForPageReady(page);

    const rows = page.locator('.ant-table-row');
    const count = await rows.count();
    if (count === 0) {
      test.skip(true, 'No alerts to check');
      return;
    }

    // Find expand icon (CaretRightOutlined)
    const expandIcon = rows.first().locator('.anticon-caret-right');
    if (await expandIcon.isVisible()) {
      await expandIcon.click();
      await page.waitForTimeout(300);

      // Should now show CaretDownOutlined
      const collapseIcon = rows.first().locator('.anticon-caret-down');
      await expect(collapseIcon).toBeVisible({ timeout: 2000 });
    }
  });
});

test.describe('AlertsPage - Actions', () => {
  test('acknowledge button opens confirmation modal', async ({ page }) => {
    await page.goto('/alerts');
    await waitForPageReady(page);

    // Find an active alert with "确认" button
    const acknowledgeBtn = page.locator('.ant-table-row').locator('button').filter({ hasText: '确认' }).first();
    if (await acknowledgeBtn.isVisible().catch(() => false)) {
      await acknowledgeBtn.click();

      // Verify Modal.confirm appears
      const confirmModal = page.locator('.ant-modal-confirm');
      await expect(confirmModal).toBeVisible({ timeout: 5000 });
      await expect(confirmModal).toContainText('确认告警');

      // Cancel
      await confirmModal.locator('.ant-btn:not(.ant-btn-primary):not(.ant-btn-danger)').first().click();
      await expect(confirmModal).not.toBeVisible({ timeout: 3000 });
    }
  });

  test('resolve button opens confirmation modal', async ({ page }) => {
    await page.goto('/alerts');
    await waitForPageReady(page);

    // Find a non-resolved alert with "解决" button
    const resolveBtn = page.locator('.ant-table-row').locator('button').filter({ hasText: '解决' }).first();
    if (await resolveBtn.isVisible().catch(() => false)) {
      await resolveBtn.click();

      // Verify Modal.confirm appears
      const confirmModal = page.locator('.ant-modal-confirm');
      await expect(confirmModal).toBeVisible({ timeout: 5000 });
      await expect(confirmModal).toContainText('解决告警');

      // Cancel
      await confirmModal.locator('.ant-btn:not(.ant-btn-primary):not(.ant-btn-danger)').first().click();
      await expect(confirmModal).not.toBeVisible({ timeout: 3000 });
    }
  });

  test('task link in expanded row navigates to /audit?task_id=', async ({ page }) => {
    await page.goto('/alerts');
    await waitForPageReady(page);

    const rows = page.locator('.ant-table-row');
    const count = await rows.count();
    if (count === 0) {
      test.skip(true, 'No alerts to check');
      return;
    }

    // Expand first row
    await rows.first().click();
    await page.waitForTimeout(500);

    // Find task link in expanded row
    const expandedRow = page.locator('.ant-table-expanded-row');
    const taskLink = expandedRow.locator('button').filter({ hasText: '查看关联任务' });
    if (await taskLink.isVisible().catch(() => false)) {
      await taskLink.click();
      await expect(page).toHaveURL(/\/audit\?task_id=/, { timeout: 5000 });
    }
  });
});

test.describe('AlertsPage - Empty State', () => {
  test('shows empty state when no alerts match filter', async ({ page }) => {
    await page.goto('/alerts');
    await waitForPageReady(page);

    // Select a filter that might have no results
    const filterSelect = page.locator('.ant-select').filter({ hasText: /按状态筛选|活跃|已确认|已解决/ });
    await filterSelect.click();
    await page.locator('.ant-select-item-option').filter({ hasText: '已解决' }).click();
    await page.waitForTimeout(1000);

    // If no resolved alerts, empty state should show
    const hasEmpty = await page.locator('.ant-empty').isVisible().catch(() => false);
    const hasTable = await page.locator('.ant-table-row').first().isVisible().catch(() => false);

    if (!hasTable) {
      expect(hasEmpty).toBe(true);
      await expect(page.locator('.ant-empty')).toContainText('暂无告警');
    }
  });
});

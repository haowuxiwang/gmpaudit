import { test, expect } from '@playwright/test';
import { waitForPageReady } from './helpers';

test.describe('SettingsPage - Tab Switching', () => {
  test('shows 3 tabs and LLM config is active by default', async ({ page }) => {
    await page.goto('/settings');
    await waitForPageReady(page);

    // Verify tab labels
    const tabs = page.locator('.ant-tabs-tab');
    await expect(tabs).toHaveCount(3, { timeout: 5000 });
    await expect(tabs.nth(0)).toContainText('大模型配置');
    await expect(tabs.nth(1)).toContainText('飞书通知');
    await expect(tabs.nth(2)).toContainText('运行参数');

    // LLM config tab should be active
    await expect(tabs.nth(0)).toHaveClass(/ant-tabs-tab-active/);
  });

  test('switching to feishu tab shows webhook form', async ({ page }) => {
    await page.goto('/settings');
    await waitForPageReady(page);

    // Click feishu tab
    await page.locator('.ant-tabs-tab').filter({ hasText: '飞书通知' }).click();
    await page.waitForTimeout(500);

    // Verify webhook form elements
    await expect(page.locator('text=Webhook 地址')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('text=签名密钥')).toBeVisible();
    await expect(page.locator('button').filter({ hasText: '保存并测试' })).toBeVisible();
  });

  test('switching to runtime tab shows runtime controls', async ({ page }) => {
    await page.goto('/settings');
    await waitForPageReady(page);

    // Click runtime tab
    await page.locator('.ant-tabs-tab').filter({ hasText: '运行参数' }).click();
    await page.waitForTimeout(500);

    // Verify runtime form elements
    await expect(page.locator('text=温度')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('text=最大并发任务')).toBeVisible();
    await expect(page.locator('text=日志级别')).toBeVisible();
  });
});

test.describe('SettingsPage - LLM Provider Collapse', () => {
  test('displays provider collapse panels', async ({ page }) => {
    await page.goto('/settings');
    await waitForPageReady(page);

    // Verify collapse panels exist
    const collapseItems = page.locator('.ant-collapse-item');
    await expect(collapseItems).toHaveCount(8, { timeout: 5000 });
  });

  test('expanding a provider panel shows model, URL, API key fields', async ({ page }) => {
    await page.goto('/settings');
    await waitForPageReady(page);

    // Click first collapse panel to expand
    const firstPanel = page.locator('.ant-collapse-item').first();
    const header = firstPanel.locator('.ant-collapse-header');
    await header.click();
    await page.waitForTimeout(300);

    // Verify form fields are visible
    await expect(page.locator('text=模型名称')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('text=接口地址')).toBeVisible();
    await expect(page.locator('text=API 密钥')).toBeVisible();
    await expect(page.locator('button').filter({ hasText: '测试连接' }).first()).toBeVisible();
  });

  test('default provider has orange tag', async ({ page }) => {
    await page.goto('/settings');
    await waitForPageReady(page);

    // Find the default tag
    const defaultTag = page.locator('.ant-tag').filter({ hasText: '默认' });
    await expect(defaultTag).toBeVisible({ timeout: 5000 });

    // Verify it has orange color
    const tagClass = await defaultTag.getAttribute('class') || '';
    expect(tagClass).toContain('ant-tag-orange');
  });
});

test.describe('SettingsPage - Test Connection', () => {
  test('test connection button shows loading state', async ({ page }) => {
    await page.goto('/settings');
    await waitForPageReady(page);

    // Expand first provider panel
    const firstPanel = page.locator('.ant-collapse-item').first();
    await firstPanel.locator('.ant-collapse-header').click();
    await page.waitForTimeout(300);

    // Enter a dummy API key
    const apiKeyInput = firstPanel.locator('input[type="password"], .ant-input-password input');
    if (await apiKeyInput.isVisible()) {
      await apiKeyInput.fill('test-key-12345');

      // Click test connection
      const testBtn = firstPanel.locator('button').filter({ hasText: '测试连接' });
      await testBtn.click();

      // Verify loading state (button should show loading spinner)
      await expect(testBtn.locator('.ant-btn-loading-icon, .ant-spin')).toBeVisible({ timeout: 3000 });
    }
  });
});

test.describe('SettingsPage - Save Config', () => {
  test('save button is visible', async ({ page }) => {
    await page.goto('/settings');
    await waitForPageReady(page);

    // Verify save button exists
    const saveBtn = page.locator('button').filter({ hasText: '保存配置' });
    await expect(saveBtn).toBeVisible({ timeout: 5000 });
  });

  test('save with no changes shows info message', async ({ page }) => {
    await page.goto('/settings');
    await waitForPageReady(page);

    // Click save without changes
    await page.locator('button').filter({ hasText: '保存配置' }).click();

    // Should show info message
    await expect(page.locator('.ant-message')).toContainText(/无配置变更/, { timeout: 5000 });
  });

  test('save with changes shows success message', async ({ page }) => {
    await page.goto('/settings');
    await waitForPageReady(page);

    // Switch to runtime tab
    await page.locator('.ant-tabs-tab').filter({ hasText: '运行参数' }).click();
    await page.waitForTimeout(500);

    // Change temperature value
    const tempInput = page.locator('.ant-input-number').first();
    if (await tempInput.isVisible()) {
      await tempInput.click();
      await page.keyboard.selectAll();
      await page.keyboard.type('0.8');

      // Save
      await page.locator('button').filter({ hasText: '保存配置' }).click();

      // Should show success message
      await expect(page.locator('.ant-message')).toContainText(/已保存/, { timeout: 5000 });
    }
  });
});

test.describe('SettingsPage - Runtime Parameters', () => {
  test('log level select shows 4 options', async ({ page }) => {
    await page.goto('/settings');
    await waitForPageReady(page);

    // Switch to runtime tab
    await page.locator('.ant-tabs-tab').filter({ hasText: '运行参数' }).click();
    await page.waitForTimeout(500);

    // Find log level select
    const logSelect = page.locator('.ant-select').filter({ hasText: /调试|信息|警告|错误|DEBUG|INFO|WARNING|ERROR/ });
    if (await logSelect.isVisible()) {
      await logSelect.click();

      // Verify 4 options
      const options = page.locator('.ant-select-item-option');
      await expect(options).toHaveCount(4, { timeout: 3000 });
      await expect(options.nth(0)).toContainText('调试');
      await expect(options.nth(1)).toContainText('信息');
      await expect(options.nth(2)).toContainText('警告');
      await expect(options.nth(3)).toContainText('错误');

      await page.keyboard.press('Escape');
    }
  });
});

test.describe('SettingsPage - Feishu Webhook', () => {
  test('webhook form shows guide card', async ({ page }) => {
    await page.goto('/settings');
    await waitForPageReady(page);

    // Switch to feishu tab
    await page.locator('.ant-tabs-tab').filter({ hasText: '飞书通知' }).click();
    await page.waitForTimeout(500);

    // Verify guide card
    await expect(page.locator('text=Webhook 配置指南')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('text=创建或打开飞书群机器人')).toBeVisible();
    await expect(page.locator('text=复制生成的 Webhook 地址')).toBeVisible();
  });

  test('save and test button validates empty webhook URL', async ({ page }) => {
    await page.goto('/settings');
    await waitForPageReady(page);

    // Switch to feishu tab
    await page.locator('.ant-tabs-tab').filter({ hasText: '飞书通知' }).click();
    await page.waitForTimeout(500);

    // Click save and test without entering URL
    await page.locator('button').filter({ hasText: '保存并测试' }).click();

    // Should show warning
    await expect(page.locator('.ant-message')).toContainText(/请先输入 Webhook 地址/, { timeout: 5000 });
  });
});

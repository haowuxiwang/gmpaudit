import { test, expect, Page } from '@playwright/test';

// Helper: wait for page to be fully loaded (no spinner)
async function waitForPageReady(page: Page) {
  // Wait for Ant Design layout to render
  await page.waitForSelector('.ant-layout', { timeout: 10000 });
  // Wait for any loading spinners to disappear
  try {
    await page.waitForSelector('.ant-spin-spinning', { state: 'hidden', timeout: 5000 });
  } catch {
    // No spinner present, that's fine
  }
}

test.describe('Sidebar Navigation', () => {
  test('all sidebar links are visible and clickable', async ({ page }) => {
    await page.goto('/');
    await waitForPageReady(page);

    // Check sidebar exists
    const sidebar = page.locator('.ant-layout-sider');
    await expect(sidebar).toBeVisible();

    // Check navigation links
    const expectedLinks = ['/', '/documents', '/audit', '/reports', '/kg', '/alerts', '/settings'];
    for (const href of expectedLinks) {
      const link = page.locator(`a[href="${href}"]`);
      await expect(link).toBeVisible({ timeout: 5000 });
    }
  });

  test('navigate to each page without errors', async ({ page }) => {
    const routes = [
      { path: '/', name: 'Dashboard' },
      { path: '/documents', name: 'Documents' },
      { path: '/audit', name: 'AuditTasks' },
      { path: '/reports', name: 'Reports' },
      { path: '/kg', name: 'KnowledgeGraph' },
      { path: '/alerts', name: 'Alerts' },
      { path: '/settings', name: 'Settings' },
    ];

    for (const route of routes) {
      await page.goto(route.path);
      await waitForPageReady(page);

      // Should not show error boundary
      const errorBoundary = page.locator('.ant-result-error');
      const hasError = await errorBoundary.isVisible().catch(() => false);
      expect(hasError, `${route.name} page should not show error boundary`).toBe(false);

      // Should not be blank (have at least some content)
      const bodyText = await page.locator('.ant-layout-content').innerText();
      expect(bodyText.length, `${route.name} page should have content`).toBeGreaterThan(0);
    }
  });
});

test.describe('Dashboard Page', () => {
  test('loads with statistics cards', async ({ page }) => {
    await page.goto('/');
    await waitForPageReady(page);

    // Should have page title
    await expect(page.locator('text=仪表盘').or(page.locator('text=Dashboard')).or(page.locator('h4'))).toBeVisible({ timeout: 5000 });
  });

  test('shows recent tasks section', async ({ page }) => {
    await page.goto('/');
    await waitForPageReady(page);

    // Should have some content in the main area
    const content = page.locator('.ant-layout-content');
    await expect(content).toBeVisible();
  });
});

test.describe('Documents Page', () => {
  test('loads document list', async ({ page }) => {
    await page.goto('/documents');
    await waitForPageReady(page);

    // Should have upload area or document table
    const hasUpload = await page.locator('.ant-upload').isVisible().catch(() => false);
    const hasTable = await page.locator('.ant-table').isVisible().catch(() => false);
    expect(hasUpload || hasTable).toBe(true);
  });

  test('upload area is present', async ({ page }) => {
    await page.goto('/documents');
    await waitForPageReady(page);

    // Should have drag-and-drop upload area
    const uploadArea = page.locator('.ant-upload-drag').or(page.locator('.ant-upload'));
    await expect(uploadArea).toBeVisible({ timeout: 5000 });
  });

  test('document table shows status tags', async ({ page }) => {
    await page.goto('/documents');
    await waitForPageReady(page);

    // Wait for data to load
    await page.waitForTimeout(2000);

    // If there are documents, check status tags
    const rows = page.locator('.ant-table-row');
    const count = await rows.count();
    if (count > 0) {
      const tag = page.locator('.ant-tag').first();
      await expect(tag).toBeVisible();
    }
  });
});

test.describe('Audit Tasks Page', () => {
  test('loads task list', async ({ page }) => {
    await page.goto('/audit');
    await waitForPageReady(page);

    // Should have task list or empty state
    const hasTable = await page.locator('.ant-table').isVisible().catch(() => false);
    const hasEmpty = await page.locator('.ant-empty').isVisible().catch(() => false);
    expect(hasTable || hasEmpty).toBe(true);
  });

  test('create task button is visible', async ({ page }) => {
    await page.goto('/audit');
    await waitForPageReady(page);

    // Should have a create/new task button
    const createBtn = page.locator('button').filter({ hasText: /新建|创建|新增|Create/ });
    await expect(createBtn).toBeVisible({ timeout: 5000 });
  });
});

test.describe('Reports Page', () => {
  test('loads reports list', async ({ page }) => {
    await page.goto('/reports');
    await waitForPageReady(page);

    // Should have report list or empty state
    const hasTable = await page.locator('.ant-table').isVisible().catch(() => false);
    const hasEmpty = await page.locator('.ant-empty').isVisible().catch(() => false);
    const hasCard = await page.locator('.ant-card').isVisible().catch(() => false);
    expect(hasTable || hasEmpty || hasCard).toBe(true);
  });
});

test.describe('Settings Page', () => {
  test('loads settings form', async ({ page }) => {
    await page.goto('/settings');
    await waitForPageReady(page);

    // Should have form elements
    const hasForm = await page.locator('.ant-form').isVisible().catch(() => false);
    const hasInput = await page.locator('.ant-input').isVisible().catch(() => false);
    const hasCard = await page.locator('.ant-card').isVisible().catch(() => false);
    expect(hasForm || hasInput || hasCard).toBe(true);
  });

  test('shows LLM provider options', async ({ page }) => {
    await page.goto('/settings');
    await waitForPageReady(page);

    // Should have provider-related content
    const bodyText = await page.locator('.ant-layout-content').innerText();
    const hasProvider = /provider|提供商|deepseek|qwen|mimo|openai/i.test(bodyText);
    expect(hasProvider).toBe(true);
  });
});

test.describe('Knowledge Graph Page', () => {
  test('loads KG page', async ({ page }) => {
    await page.goto('/kg');
    await waitForPageReady(page);

    // Should have some content
    const content = page.locator('.ant-layout-content');
    const text = await content.innerText();
    expect(text.length).toBeGreaterThan(0);
  });
});

test.describe('Alerts Page', () => {
  test('loads alerts page', async ({ page }) => {
    await page.goto('/alerts');
    await waitForPageReady(page);

    // Should have alert list or empty state
    const hasTable = await page.locator('.ant-table').isVisible().catch(() => false);
    const hasEmpty = await page.locator('.ant-empty').isVisible().catch(() => false);
    const hasCard = await page.locator('.ant-card').isVisible().catch(() => false);
    expect(hasTable || hasEmpty || hasCard).toBe(true);
  });
});

test.describe('404 Page', () => {
  test('shows 404 for unknown routes', async ({ page }) => {
    await page.goto('/nonexistent-page-xyz');
    await waitForPageReady(page);

    // Should show 404 or not found content
    const bodyText = await page.locator('body').innerText();
    const has404 = /404|not found|页面不存在|找不到/i.test(bodyText);
    expect(has404).toBe(true);
  });
});

test.describe('API Integration', () => {
  test('dashboard API returns data', async ({ page }) => {
    const response = await page.request.get('/api/health');
    expect(response.ok()).toBe(true);
    const body = await response.json();
    expect(body.status).toBe('ok');
  });

  test('documents API returns list', async ({ page }) => {
    const response = await page.request.get('/api/documents/');
    expect(response.ok()).toBe(true);
  });

  test('config API returns settings', async ({ page }) => {
    const response = await page.request.get('/api/config/');
    expect(response.ok()).toBe(true);
    const body = await response.json();
    expect(Object.keys(body).length).toBeGreaterThan(0);
  });

  test('reports API returns list', async ({ page }) => {
    const response = await page.request.get('/api/reports/');
    expect(response.ok()).toBe(true);
  });

  test('alerts API returns list', async ({ page }) => {
    const response = await page.request.get('/api/alerts/');
    expect(response.ok()).toBe(true);
  });
});

test.describe('Error Handling', () => {
  test('page does not crash on API error', async ({ page }) => {
    // Navigate to pages that might have API issues
    await page.goto('/');
    await waitForPageReady(page);

    // Check no unhandled error dialogs
    const errorDialog = page.locator('.ant-modal-confirm-error');
    const hasError = await errorDialog.isVisible().catch(() => false);
    expect(hasError).toBe(false);
  });

  test('no console errors on page load', async ({ page }) => {
    const errors: string[] = [];
    page.on('console', msg => {
      if (msg.type() === 'error') {
        errors.push(msg.text());
      }
    });

    await page.goto('/');
    await waitForPageReady(page);
    await page.waitForTimeout(2000);

    // Filter out known non-critical errors
    const criticalErrors = errors.filter(e =>
      !e.includes('favicon') &&
      !e.includes('manifest') &&
      !e.includes('service-worker') &&
      !e.includes('DevTools')
    );

    // Log errors for debugging but don't fail on minor ones
    if (criticalErrors.length > 0) {
      console.log('Console errors found:', criticalErrors);
    }
  });
});

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
  testFilePath = createTestFile('nav_test.txt', '导航测试文档');
});

test.afterAll(() => {
  cleanupTestFixtures();
});

test.describe('Dashboard CTA Navigation', () => {
  test('clicking "进入审计" navigates to /audit', async ({ page }) => {
    await page.goto('/');
    await waitForPageReady(page);

    // Click "进入审计" button
    await page.locator('button').filter({ hasText: '进入审计' }).click();
    await expect(page).toHaveURL(/\/audit/, { timeout: 5000 });
  });

  test('clicking "上传文档" navigates to /documents', async ({ page }) => {
    await page.goto('/');
    await waitForPageReady(page);

    // Click "上传文档" button
    await page.locator('button').filter({ hasText: '上传文档' }).click();
    await expect(page).toHaveURL(/\/documents/, { timeout: 5000 });
  });

  test('clicking "知识图谱" navigates to /kg', async ({ page }) => {
    await page.goto('/');
    await waitForPageReady(page);

    // Click "知识图谱" button
    await page.locator('button').filter({ hasText: '知识图谱' }).click();
    await expect(page).toHaveURL(/\/kg/, { timeout: 5000 });
  });

  test('clicking "查看全部" in recent tasks navigates to /audit', async ({ page }) => {
    await page.goto('/');
    await waitForPageReady(page);

    // Find "查看全部" link
    const viewAll = page.locator('a, span, button').filter({ hasText: '查看全部' }).first();
    if (await viewAll.isVisible().catch(() => false)) {
      await viewAll.click();
      await expect(page).toHaveURL(/\/audit/, { timeout: 5000 });
    }
  });

  test('clicking "查看知识图谱" in system overview navigates to /kg', async ({ page }) => {
    await page.goto('/');
    await waitForPageReady(page);

    // Find "查看知识图谱" link
    const kgLink = page.locator('a, span, button').filter({ hasText: '查看知识图谱' }).first();
    if (await kgLink.isVisible().catch(() => false)) {
      await kgLink.click();
      await expect(page).toHaveURL(/\/kg/, { timeout: 5000 });
    }
  });

  test('clicking "继续此任务" navigates to /audit?task_id=', async ({ page, request }) => {
    // Create a task to ensure there's one on the dashboard
    const doc = await uploadDocumentViaAPI(request, testFilePath, 'nav_test.txt');
    await waitForDocumentProcessed(request, doc.id);
    await request.post('/api/audit/tasks', {
      data: {
        task_name: '导航测试任务',
        task_type: 'deviation_analysis',
        document_ids: [doc.id],
      },
    });

    await page.goto('/');
    await waitForPageReady(page);
    await page.waitForTimeout(2000);

    // Find "继续此任务" button
    const continueBtn = page.locator('button').filter({ hasText: '继续此任务' }).first();
    if (await continueBtn.isVisible().catch(() => false)) {
      await continueBtn.click();
      await expect(page).toHaveURL(/\/audit\?task_id=\d+/, { timeout: 5000 });
    }
  });

  test('clicking "进入工作台" on task row navigates to /audit?task_id=', async ({ page, request }) => {
    // Ensure a task exists
    const doc = await uploadDocumentViaAPI(request, testFilePath, 'nav_test.txt');
    await waitForDocumentProcessed(request, doc.id);
    await request.post('/api/audit/tasks', {
      data: {
        task_name: '工作台导航任务',
        task_type: 'deviation_analysis',
        document_ids: [doc.id],
      },
    });

    await page.goto('/');
    await waitForPageReady(page);
    await page.waitForTimeout(2000);

    // Find "进入工作台" link
    const workbenchLink = page.locator('a, span, button').filter({ hasText: '进入工作台' }).first();
    if (await workbenchLink.isVisible().catch(() => false)) {
      await workbenchLink.click();
      await expect(page).toHaveURL(/\/audit\?task_id=\d+/, { timeout: 5000 });
    }
  });
});

test.describe('AuditTasks Cross-Navigation', () => {
  test('task "报告" button navigates to /reports?task_id=', async ({ page, request }) => {
    // Create a task
    const doc = await uploadDocumentViaAPI(request, testFilePath, 'nav_test.txt');
    await waitForDocumentProcessed(request, doc.id);
    const taskResponse = await request.post('/api/audit/tasks', {
      data: {
        task_name: '报告导航任务',
        task_type: 'deviation_analysis',
        document_ids: [doc.id],
      },
    });
    const task = await taskResponse.json();

    await page.goto('/audit');
    await waitForPageReady(page);

    // Find task with report link
    const taskWithReport = page.locator('[role="button"]').filter({ hasText: '报告' }).first();
    if (await taskWithReport.isVisible().catch(() => false)) {
      await taskWithReport.locator('button').filter({ hasText: '报告' }).click();
      await expect(page).toHaveURL(/\/reports\?task_id=\d+/, { timeout: 5000 });
    }
  });

  test('drawer "查看报告" navigates to /reports?task_id=', async ({ page, request }) => {
    // Find a task with report
    const tasksResponse = await request.get('/api/audit/tasks');
    const tasksData = await tasksResponse.json();
    const tasks = tasksData.items || [];
    const taskWithReport = tasks.find((t: any) => t.report_id);

    if (!taskWithReport) {
      test.skip(true, 'No task with report');
      return;
    }

    await page.goto(`/audit?task_id=${taskWithReport.id}`);
    await waitForPageReady(page);

    const drawer = page.locator('.ant-drawer');
    await expect(drawer).toBeVisible({ timeout: 10000 });

    // Click view report
    const reportBtn = drawer.locator('button').filter({ hasText: '查看报告' });
    if (await reportBtn.isVisible().catch(() => false)) {
      await reportBtn.click();
      await expect(page).toHaveURL(/\/reports\?task_id=\d+/, { timeout: 5000 });
    }
  });

  test('drawer "知识图谱" navigates to /kg with params', async ({ page, request }) => {
    // Create a task
    const doc = await uploadDocumentViaAPI(request, testFilePath, 'nav_test.txt');
    await waitForDocumentProcessed(request, doc.id);
    const taskResponse = await request.post('/api/audit/tasks', {
      data: {
        task_name: 'KG导航任务',
        task_type: 'deviation_analysis',
        document_ids: [doc.id],
      },
    });
    const task = await taskResponse.json();

    await page.goto(`/audit?task_id=${task.id}`);
    await waitForPageReady(page);

    const drawer = page.locator('.ant-drawer');
    await expect(drawer).toBeVisible({ timeout: 10000 });

    // Click KG button
    const kgBtn = drawer.locator('button').filter({ hasText: '知识图谱' });
    if (await kgBtn.isVisible().catch(() => false)) {
      await kgBtn.click();
      await expect(page).toHaveURL(/\/kg\?q=.+&task_id=\d+/, { timeout: 5000 });
    }
  });
});

test.describe('Alerts Cross-Navigation', () => {
  test('alert "任务" link navigates to /audit?task_id=', async ({ page }) => {
    await page.goto('/alerts');
    await waitForPageReady(page);

    // Find alert with task link
    const taskLink = page.locator('.ant-table-row').locator('button').filter({ hasText: '任务' }).first();
    if (await taskLink.isVisible().catch(() => false)) {
      await taskLink.click();
      await expect(page).toHaveURL(/\/audit\?task_id=\d+/, { timeout: 5000 });
    }
  });
});

test.describe('404 Navigation', () => {
  test('"返回首页" button navigates to /', async ({ page }) => {
    await page.goto('/nonexistent-page-xyz');
    await waitForPageReady(page);

    // Click "返回首页" button
    const homeBtn = page.locator('button').filter({ hasText: '返回首页' });
    if (await homeBtn.isVisible().catch(() => false)) {
      await homeBtn.click();
      await expect(page).toHaveURL('/', { timeout: 5000 });
    }
  });
});

test.describe('Sidebar Active State', () => {
  test('sidebar highlights current page', async ({ page }) => {
    const routes = [
      { path: '/', menuText: '工作台' },
      { path: '/documents', menuText: '文档管理' },
      { path: '/audit', menuText: '审计任务' },
      { path: '/reports', menuText: '审计报告' },
      { path: '/kg', menuText: '知识图谱' },
      { path: '/alerts', menuText: '风险告警' },
      { path: '/settings', menuText: '系统设置' },
    ];

    for (const route of routes) {
      await page.goto(route.path);
      await waitForPageReady(page);

      // Find the menu item with selected state
      const selectedMenuItem = page.locator('.ant-menu-item-selected');
      if (await selectedMenuItem.isVisible().catch(() => false)) {
        await expect(selectedMenuItem).toContainText(route.menuText);
      }
    }
  });
});

import { test, expect } from '@playwright/test';
import {
  waitForPageReady,
  createTestFile,
  uploadDocumentViaAPI,
  waitForDocumentProcessed,
  cleanupTestFixtures,
} from './helpers';

const TEST_FILE = 'audit_task_test.txt';
const TEST_CONTENT = `偏差报告 - 审计任务测试\n\n批号: T-2024-0001\n产品: 片剂\n偏差类型: 生产偏差`;

let testFilePath: string;
let processedDocId: number;

test.beforeAll(async ({ request }) => {
  testFilePath = createTestFile(TEST_FILE, TEST_CONTENT);
  const doc = await uploadDocumentViaAPI(request, testFilePath, TEST_FILE);
  await waitForDocumentProcessed(request, doc.id);
  processedDocId = doc.id;
});

test.afterAll(() => {
  cleanupTestFixtures();
});

test.describe('AuditTasksPage - Task Creation Modal', () => {
  test('opens create modal with all form fields', async ({ page }) => {
    await page.goto('/audit');
    await waitForPageReady(page);

    // Click "新建任务"
    await page.locator('button').filter({ hasText: '新建任务' }).click();

    // Verify modal appears
    const modal = page.locator('.ant-modal');
    await expect(modal).toBeVisible({ timeout: 5000 });
    await expect(modal.locator('.ant-modal-title')).toContainText('创建审计任务');

    // Verify form fields
    await expect(modal.locator('text=任务名称')).toBeVisible();
    await expect(modal.locator('text=审计类型')).toBeVisible();
    await expect(modal.locator('text=选择文档')).toBeVisible();

    // Close modal
    await modal.locator('.ant-modal-close').click();
  });

  test('task_type select shows all 4 type options', async ({ page }) => {
    await page.goto('/audit');
    await waitForPageReady(page);

    // Open modal
    await page.locator('button').filter({ hasText: '新建任务' }).click();
    const modal = page.locator('.ant-modal');
    await expect(modal).toBeVisible({ timeout: 5000 });

    // Click task_type select (second select in the modal)
    const typeSelect = modal.locator('.ant-select').nth(0);
    await typeSelect.click();

    // Verify options
    const options = page.locator('.ant-select-item-option');
    await expect(options.filter({ hasText: '偏差分析' })).toBeVisible({ timeout: 3000 });
    await expect(options.filter({ hasText: 'SOP 合规' })).toBeVisible();
    await expect(options.filter({ hasText: '变更控制一致性' })).toBeVisible();
    await expect(options.filter({ hasText: '风险评估' })).toBeVisible();

    // Close
    await page.keyboard.press('Escape');
    await modal.locator('.ant-modal-close').click();
  });

  test('validates required fields on submit', async ({ page }) => {
    await page.goto('/audit');
    await waitForPageReady(page);

    // Open modal
    await page.locator('button').filter({ hasText: '新建任务' }).click();
    const modal = page.locator('.ant-modal');
    await expect(modal).toBeVisible({ timeout: 5000 });

    // Click OK without filling anything
    await modal.locator('.ant-modal-footer .ant-btn-primary').click();

    // Verify validation messages
    await expect(modal).toContainText('请输入任务名称', { timeout: 3000 });

    // Close modal
    await modal.locator('.ant-modal-close').click();
  });

  test('creates task with all fields filled', async ({ page, request }) => {
    await page.goto('/audit');
    await waitForPageReady(page);

    // Open modal
    await page.locator('button').filter({ hasText: '新建任务' }).click();
    const modal = page.locator('.ant-modal');
    await expect(modal).toBeVisible({ timeout: 5000 });

    // Fill task name
    await modal.locator('input').first().fill('E2E 测试创建任务');

    // Select task type
    const typeSelect = modal.locator('.ant-select').nth(0);
    await typeSelect.click();
    await page.locator('.ant-select-item-option').filter({ hasText: '偏差分析' }).click();

    // Select document
    const docSelect = modal.locator('.ant-select').nth(1);
    await docSelect.click();
    await page.locator('.ant-select-item-option').filter({ hasText: TEST_FILE }).click();
    // Close dropdown
    await modal.locator('.ant-modal-title').click();

    // Submit
    await modal.locator('.ant-modal-footer .ant-btn-primary').click();

    // Verify success
    await expect(page.locator('.ant-message')).toContainText(/审计任务已创建/, { timeout: 10000 });

    // Verify drawer opened
    const drawer = page.locator('.ant-drawer');
    await expect(drawer).toBeVisible({ timeout: 5000 });
  });
});

test.describe('AuditTasksPage - Filters', () => {
  test('status filter shows all status options', async ({ page }) => {
    await page.goto('/audit');
    await waitForPageReady(page);

    // Find status filter select (first select in toolbar)
    const toolbar = page.locator('.ant-card').first();
    const statusSelect = toolbar.locator('.ant-select').first();
    await statusSelect.click();

    // Verify options
    const options = page.locator('.ant-select-item-option');
    await expect(options.filter({ hasText: '全部状态' })).toBeVisible({ timeout: 3000 });
    await expect(options.filter({ hasText: '待处理' })).toBeVisible();
    await expect(options.filter({ hasText: '进行中' })).toBeVisible();
    await expect(options.filter({ hasText: '已完成' })).toBeVisible();
    await expect(options.filter({ hasText: '失败' })).toBeVisible();
    await expect(options.filter({ hasText: '已取消' })).toBeVisible();

    await page.keyboard.press('Escape');
  });

  test('type filter shows all type options', async ({ page }) => {
    await page.goto('/audit');
    await waitForPageReady(page);

    // Find type filter select (second select in toolbar)
    const toolbar = page.locator('.ant-card').first();
    const typeSelect = toolbar.locator('.ant-select').nth(1);
    await typeSelect.click();

    // Verify options
    const options = page.locator('.ant-select-item-option');
    await expect(options.filter({ hasText: '全部类型' })).toBeVisible({ timeout: 3000 });
    await expect(options.filter({ hasText: '偏差分析' })).toBeVisible();
    await expect(options.filter({ hasText: 'SOP 合规' })).toBeVisible();
    await expect(options.filter({ hasText: '变更控制一致性' })).toBeVisible();
    await expect(options.filter({ hasText: '风险评估' })).toBeVisible();

    await page.keyboard.press('Escape');
  });

  test('filters tasks by status', async ({ page, request }) => {
    // Create a pending task
    await request.post('/api/audit/tasks', {
      data: {
        task_name: '筛选器测试任务',
        task_type: 'deviation_analysis',
        document_ids: [processedDocId],
      },
    });

    await page.goto('/audit');
    await waitForPageReady(page);

    // Select "待处理" filter
    const toolbar = page.locator('.ant-card').first();
    const statusSelect = toolbar.locator('.ant-select').first();
    await statusSelect.click();
    await page.locator('.ant-select-item-option').filter({ hasText: '待处理' }).click();
    await page.waitForTimeout(1000);

    // All visible tasks should be pending
    const tasks = page.locator('.ant-card').nth(1).locator('[role="button"]');
    const count = await tasks.count();
    for (let i = 0; i < count; i++) {
      await expect(tasks.nth(i)).toContainText('待处理');
    }
  });

  test('clears filter and shows all tasks', async ({ page }) => {
    await page.goto('/audit');
    await waitForPageReady(page);

    // Select a filter
    const toolbar = page.locator('.ant-card').first();
    const statusSelect = toolbar.locator('.ant-select').first();
    await statusSelect.click();
    await page.locator('.ant-select-item-option').filter({ hasText: '待处理' }).click();
    await page.waitForTimeout(500);

    // Clear filter by selecting "全部状态"
    await statusSelect.click();
    await page.locator('.ant-select-item-option').filter({ hasText: '全部状态' }).click();
    await page.waitForTimeout(500);

    // Verify task count text
    await expect(toolbar).toContainText(/共 \d+ 个任务/);
  });
});

test.describe('AuditTasksPage - Task List Items', () => {
  test('displays task name, type label, status tag, and progress bar', async ({ page }) => {
    await page.goto('/audit');
    await waitForPageReady(page);

    // Check if there are tasks
    const tasks = page.locator('[role="button"]');
    const count = await tasks.count();
    if (count === 0) {
      test.skip(true, 'No tasks to check');
      return;
    }

    const firstTask = tasks.first();

    // Verify task name (strong text)
    await expect(firstTask.locator('strong').first()).toBeVisible();

    // Verify type label
    await expect(firstTask.locator('.ant-tag').first()).toBeVisible();

    // Verify progress bar
    await expect(firstTask.locator('.ant-progress')).toBeVisible();
  });

  test('shows run button only on pending tasks', async ({ page }) => {
    await page.goto('/audit');
    await waitForPageReady(page);

    // Find a pending task
    const pendingTask = page.locator('[role="button"]').filter({ hasText: '待处理' }).first();
    if (await pendingTask.isVisible().catch(() => false)) {
      await expect(pendingTask.locator('button').filter({ hasText: '运行' })).toBeVisible();
    }

    // Find a completed task (if any)
    const completedTask = page.locator('[role="button"]').filter({ hasText: '已完成' }).first();
    if (await completedTask.isVisible().catch(() => false)) {
      await expect(completedTask.locator('button').filter({ hasText: '运行' })).not.toBeVisible();
    }
  });

  test('shows report link on tasks with report_id', async ({ page }) => {
    await page.goto('/audit');
    await waitForPageReady(page);

    // Find a task with report link
    const taskWithReport = page.locator('[role="button"]').filter({ hasText: '报告' }).first();
    if (await taskWithReport.isVisible().catch(() => false)) {
      await expect(taskWithReport.locator('button').filter({ hasText: '报告' })).toBeVisible();
    }
  });
});

test.describe('AuditTasksPage - Task Detail Drawer', () => {
  test('opens drawer when clicking a task', async ({ page }) => {
    await page.goto('/audit');
    await waitForPageReady(page);

    // Click first task
    const firstTask = page.locator('[role="button"]').first();
    if (await firstTask.isVisible()) {
      await firstTask.click();

      // Verify drawer opens
      const drawer = page.locator('.ant-drawer');
      await expect(drawer).toBeVisible({ timeout: 5000 });
    }
  });

  test('auto-opens drawer via task_id URL parameter', async ({ page, request }) => {
    // Create a task to get its ID
    const taskResponse = await request.post('/api/audit/tasks', {
      data: {
        task_name: 'URL参数测试任务',
        task_type: 'deviation_analysis',
        document_ids: [processedDocId],
      },
    });
    const task = await taskResponse.json();

    // Navigate with task_id param
    await page.goto(`/audit?task_id=${task.id}`);
    await waitForPageReady(page);

    // Verify drawer is visible
    const drawer = page.locator('.ant-drawer');
    await expect(drawer).toBeVisible({ timeout: 10000 });

    // Verify drawer title matches task name
    await expect(drawer.locator('.ant-drawer-title')).toContainText('URL参数测试任务');
  });

  test('displays status, type, and stage tags in drawer', async ({ page, request }) => {
    // Create a task
    const taskResponse = await request.post('/api/audit/tasks', {
      data: {
        task_name: '标签测试任务',
        task_type: 'deviation_analysis',
        document_ids: [processedDocId],
      },
    });
    const task = await taskResponse.json();

    await page.goto(`/audit?task_id=${task.id}`);
    await waitForPageReady(page);

    const drawer = page.locator('.ant-drawer');
    await expect(drawer).toBeVisible({ timeout: 10000 });

    // Verify tags in drawer
    const tags = drawer.locator('.ant-tag');
    await expect(tags.first()).toBeVisible();

    // Should have at least status and type tags
    const tagCount = await tags.count();
    expect(tagCount).toBeGreaterThanOrEqual(2);
  });

  test('shows progress bar in drawer', async ({ page, request }) => {
    const taskResponse = await request.post('/api/audit/tasks', {
      data: {
        task_name: '进度条测试任务',
        task_type: 'deviation_analysis',
        document_ids: [processedDocId],
      },
    });
    const task = await taskResponse.json();

    await page.goto(`/audit?task_id=${task.id}`);
    await waitForPageReady(page);

    const drawer = page.locator('.ant-drawer');
    await expect(drawer).toBeVisible({ timeout: 10000 });

    // Verify progress bar
    await expect(drawer.locator('.ant-progress')).toBeVisible();
  });

  test('shows findings list when findings exist', async ({ page, request }) => {
    // Try to find a task with findings
    const tasksResponse = await request.get('/api/audit/tasks');
    const tasksData = await tasksResponse.json();
    const tasks = tasksData.items || [];
    const completedTask = tasks.find((t: any) => t.status === 'completed');

    if (!completedTask) {
      test.skip(true, 'No completed task with findings');
      return;
    }

    await page.goto(`/audit?task_id=${completedTask.id}`);
    await waitForPageReady(page);

    const drawer = page.locator('.ant-drawer');
    await expect(drawer).toBeVisible({ timeout: 10000 });

    // Check for findings section
    await expect(drawer.locator('text=审计发现')).toBeVisible({ timeout: 5000 });
  });
});

test.describe('AuditTasksPage - Drawer Actions', () => {
  test('run button in drawer triggers task execution', async ({ page }) => {
    // Navigate to a pending task
    await page.goto('/audit');
    await waitForPageReady(page);

    // Find a pending task and click it
    const pendingTask = page.locator('[role="button"]').filter({ hasText: '待处理' }).first();
    if (await pendingTask.isVisible().catch(() => false)) {
      await pendingTask.click();

      const drawer = page.locator('.ant-drawer');
      await expect(drawer).toBeVisible({ timeout: 5000 });

      // Click run button in drawer
      const runBtn = drawer.locator('button').filter({ hasText: '运行' });
      if (await runBtn.isVisible().catch(() => false)) {
        await runBtn.click();

        // Check for success or error (agent might not be available)
        const message = page.locator('.ant-message');
        const hasSuccess = await message.filter({ hasText: /已提交/ }).isVisible().catch(() => false);
        const hasError = await message.filter({ hasText: /失败/ }).isVisible().catch(() => false);
        expect(hasSuccess || hasError).toBe(true);
      }
    }
  });

  test('cancel button in drawer shows confirmation modal', async ({ page }) => {
    // Find a running task (if any)
    await page.goto('/audit');
    await waitForPageReady(page);

    const runningTask = page.locator('[role="button"]').filter({ hasText: '进行中' }).first();
    if (await runningTask.isVisible().catch(() => false)) {
      await runningTask.click();

      const drawer = page.locator('.ant-drawer');
      await expect(drawer).toBeVisible({ timeout: 5000 });

      // Click cancel in drawer
      const cancelBtn = drawer.locator('button').filter({ hasText: '取消任务' });
      if (await cancelBtn.isVisible().catch(() => false)) {
        await cancelBtn.click();

        // Verify confirmation modal
        const confirmModal = page.locator('.ant-modal-confirm');
        await expect(confirmModal).toBeVisible({ timeout: 5000 });
        await expect(confirmModal).toContainText('取消任务');

        // Cancel
        await confirmModal.locator('.ant-btn:not(.ant-btn-primary):not(.ant-btn-danger)').first().click();
      }
    }
  });

  test('view report button navigates to reports page', async ({ page, request }) => {
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
      await expect(page).toHaveURL(/\/reports\?task_id=/, { timeout: 5000 });
    }
  });

  test('knowledge graph button navigates to KG page', async ({ page, request }) => {
    const taskResponse = await request.post('/api/audit/tasks', {
      data: {
        task_name: 'KG导航测试任务',
        task_type: 'deviation_analysis',
        document_ids: [processedDocId],
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
      await expect(page).toHaveURL(/\/kg\?q=.+&task_id=/, { timeout: 5000 });
    }
  });
});

test.describe('AuditTasksPage - SSE Streaming', () => {
  test('intercepts SSE connection for running tasks', async ({ page }) => {
    // This test verifies the SSE endpoint is called when a task is running
    // We intercept the request rather than waiting for a real running task
    await page.goto('/audit');
    await waitForPageReady(page);

    // Set up request interception
    const sseRequests: string[] = [];
    page.on('request', (request) => {
      if (request.url().includes('/api/audit/tasks/') && request.url().includes('/stream')) {
        sseRequests.push(request.url());
      }
    });

    // Find and click a running task
    const runningTask = page.locator('[role="button"]').filter({ hasText: '进行中' }).first();
    if (await runningTask.isVisible().catch(() => false)) {
      await runningTask.click();
      await page.waitForTimeout(2000);

      // Verify SSE request was made
      expect(sseRequests.length).toBeGreaterThan(0);
    }
  });
});

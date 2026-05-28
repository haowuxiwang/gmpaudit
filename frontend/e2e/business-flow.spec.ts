import { test, expect } from '@playwright/test';
import {
  waitForPageReady,
  createTestFile,
  uploadDocumentViaAPI,
  waitForDocumentProcessed,
  cleanupTestFixtures,
} from './helpers';

const TEST_FILE_NAME = 'test_deviation_report.txt';
const TEST_FILE_CONTENT = `
偏差报告 - 批号 A-2024-0017

产品: 片剂 100mg
批号: A-2024-0017
偏差类型: 生产过程偏差
发现日期: 2024-03-15

偏差描述:
在压片过程中发现片重差异超出标准范围。
标准范围: 95-105mg, 实际测量: 88-112mg。

可能原因:
1. 压片机冲头磨损
2. 颗粒流动性不佳
3. 填充深度设置不当

已采取措施:
1. 停止生产, 隔离该批次产品
2. 检查压片机冲头状态
3. 重新取样检测

影响评估:
需要对该批次产品进行全检,评估是否需要返工或报废。
`.trim();

let testFilePath: string;

test.beforeAll(() => {
  testFilePath = createTestFile(TEST_FILE_NAME, TEST_FILE_CONTENT);
});

test.afterAll(() => {
  cleanupTestFixtures();
});

test.describe('Document Upload Flow', () => {
  test('upload document via UI and verify in list', async ({ page }) => {
    await page.goto('/documents');
    await waitForPageReady(page);

    // Click the upload dragger to trigger file chooser
    const fileChooserPromise = page.waitForEvent('filechooser');
    await page.locator('.ant-upload-drag').click();
    const fileChooser = await fileChooserPromise;
    await fileChooser.setFiles(testFilePath);

    // Wait for upload success message
    await expect(page.locator('.ant-message')).toContainText(/上传成功/, { timeout: 10000 });

    // Verify document appears in the table
    await page.waitForTimeout(2000);
    await expect(page.locator('.ant-table')).toContainText(TEST_FILE_NAME, { timeout: 10000 });
  });

  test('document status transitions to processed', async ({ page, request }) => {
    // Upload via API for speed
    const doc = await uploadDocumentViaAPI(request, testFilePath, TEST_FILE_NAME);

    await page.goto('/documents');
    await waitForPageReady(page);

    // Wait for the document to appear in the table
    await expect(page.locator('.ant-table')).toContainText(TEST_FILE_NAME, { timeout: 10000 });

    // Poll for processed status (page auto-polls every 3s for pending docs)
    await expect(async () => {
      const statusTag = page.locator('.ant-tag-success').filter({ hasText: '已处理' });
      await expect(statusTag.first()).toBeVisible({ timeout: 5000 });
    }).toPass({ timeout: 60000 });
  });
});

test.describe('Audit Task Creation Flow', () => {
  test('create audit task via UI modal', async ({ page, request }) => {
    // Upload and wait for processing via API
    const doc = await uploadDocumentViaAPI(request, testFilePath, TEST_FILE_NAME);
    await waitForDocumentProcessed(request, doc.id);

    await page.goto('/audit');
    await waitForPageReady(page);

    // Click "新建任务" button
    await page.locator('button').filter({ hasText: '新建任务' }).click();

    // Wait for modal to appear
    const modal = page.locator('.ant-modal');
    await expect(modal).toBeVisible({ timeout: 5000 });

    // Fill in task name (Input inside Form.Item name="task_name")
    await modal.locator('input').first().fill('E2E 测试偏差分析任务');

    // Select document in the multiple-select (last Select in the modal)
    const docSelect = modal.locator('.ant-select').last();
    await docSelect.click();
    await page.locator('.ant-select-item-option').filter({ hasText: TEST_FILE_NAME }).click();
    // Close dropdown by clicking elsewhere
    await modal.locator('.ant-modal-title').click();

    // Click OK to submit
    await modal.locator('.ant-modal-footer .ant-btn-primary').click();

    // Verify success message
    await expect(page.locator('.ant-message')).toContainText(/审计任务已创建/, { timeout: 10000 });

    // Verify task appears in the list (task name in a strong text element)
    await expect(page.locator('.ant-card')).toContainText('E2E 测试偏差分析任务', { timeout: 10000 });
  });

  test('audit task appears with pending status via API', async ({ page, request }) => {
    // Upload and process
    const doc = await uploadDocumentViaAPI(request, testFilePath, TEST_FILE_NAME);
    await waitForDocumentProcessed(request, doc.id);

    // Create task via API
    const response = await request.post('/api/audit/tasks', {
      data: {
        task_name: 'API 创建的测试任务',
        task_type: 'deviation_analysis',
        document_ids: [doc.id],
      },
    });
    expect(response.ok()).toBeTruthy();

    // Navigate to audit page and verify
    await page.goto('/audit');
    await waitForPageReady(page);

    await expect(page.locator('.ant-card')).toContainText('API 创建的测试任务');
    // Check for pending status tag
    await expect(page.locator('.ant-tag').filter({ hasText: '待处理' }).first()).toBeVisible();
  });
});

test.describe('Audit Task Execution Flow', () => {
  test('run task and observe status in UI', async ({ page, request }) => {
    test.setTimeout(300_000);

    // Setup: upload, process, create task via API
    const doc = await uploadDocumentViaAPI(request, testFilePath, TEST_FILE_NAME);
    await waitForDocumentProcessed(request, doc.id);

    const taskResponse = await request.post('/api/audit/tasks', {
      data: {
        task_name: '执行测试任务',
        task_type: 'deviation_analysis',
        document_ids: [doc.id],
      },
    });
    const task = await taskResponse.json();

    // Start the task via API
    const runResponse = await request.post(`/api/audit/tasks/${task.id}/run`);

    // If agent is not available, skip
    if (!runResponse.ok()) {
      const body = await runResponse.json();
      if (JSON.stringify(body).includes('unavailable') || JSON.stringify(body).includes('not available')) {
        test.skip(true, 'Agent audit system not available in test environment');
        return;
      }
    }

    // Navigate to audit page
    await page.goto(`/audit?task_id=${task.id}`);
    await waitForPageReady(page);

    // The drawer should auto-open via URL param; verify it's visible
    const drawer = page.locator('.ant-drawer');
    await expect(drawer).toBeVisible({ timeout: 10000 });

    // Wait for the task to complete or fail
    await expect(async () => {
      const completed = await drawer.locator('.ant-tag-success').filter({ hasText: '已完成' }).isVisible().catch(() => false);
      const failed = await drawer.locator('.ant-tag-error').filter({ hasText: '失败' }).isVisible().catch(() => false);
      const cancelled = await drawer.locator('.ant-tag').filter({ hasText: '已取消' }).isVisible().catch(() => false);
      expect(completed || failed || cancelled).toBe(true);
    }).toPass({ timeout: 240_000 });
  });
});

test.describe('Report Viewing Flow', () => {
  test('reports page loads with table or empty state', async ({ page }) => {
    await page.goto('/reports');
    await waitForPageReady(page);

    const hasTable = await page.locator('.ant-table').isVisible().catch(() => false);
    const hasEmpty = await page.locator('.ant-empty').isVisible().catch(() => false);
    expect(hasTable || hasEmpty).toBe(true);
  });

  test('view existing report detail via API + UI', async ({ page, request }) => {
    // Check if there are existing reports
    const reportsResponse = await request.get('/api/reports/');
    const reportsData = await reportsResponse.json();
    const reports = reportsData.items || [];

    if (reports.length === 0) {
      test.skip(true, 'No existing reports to view');
      return;
    }

    await page.goto('/reports');
    await waitForPageReady(page);

    // Click "查看" on the first report row
    await page.locator('button').filter({ hasText: '查看' }).first().click();

    // Verify modal opens with report content
    const modal = page.locator('.ant-modal');
    await expect(modal).toBeVisible({ timeout: 5000 });

    // Modal should contain the report title
    await expect(modal).toContainText(reports[0].title, { timeout: 5000 });
  });
});

test.describe('Full Pipeline E2E', () => {
  test('upload -> create task -> verify in UI', async ({ page, request }) => {
    test.setTimeout(120_000);

    // Step 1: Upload document via API
    const doc = await uploadDocumentViaAPI(request, testFilePath, TEST_FILE_NAME);
    await waitForDocumentProcessed(request, doc.id);

    // Step 2: Create audit task via UI
    await page.goto('/audit');
    await waitForPageReady(page);

    await page.locator('button').filter({ hasText: '新建任务' }).click();
    const modal = page.locator('.ant-modal');
    await expect(modal).toBeVisible({ timeout: 5000 });

    await modal.locator('input').first().fill('全流程 E2E 测试任务');

    const docSelect = modal.locator('.ant-select').last();
    await docSelect.click();
    await page.locator('.ant-select-item-option').filter({ hasText: TEST_FILE_NAME }).click();
    await modal.locator('.ant-modal-title').click();

    await modal.locator('.ant-modal-footer .ant-btn-primary').click();
    await expect(page.locator('.ant-message')).toContainText(/审计任务已创建/, { timeout: 10000 });

    // Step 3: Verify task appears in list
    await expect(page.locator('.ant-card')).toContainText('全流程 E2E 测试任务', { timeout: 10000 });

    // Step 4: Verify drawer opened with task details
    const drawer = page.locator('.ant-drawer');
    await expect(drawer).toBeVisible({ timeout: 5000 });

    // Step 5: Check task has pending status and run button is visible
    await expect(drawer.locator('.ant-tag').filter({ hasText: '待处理' })).toBeVisible();
    await expect(drawer.locator('button').filter({ hasText: '运行' })).toBeVisible();
  });
});

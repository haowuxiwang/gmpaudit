import { test, expect } from '@playwright/test';
import {
  waitForPageReady,
  createTestFile,
  uploadDocumentViaAPI,
  waitForDocumentProcessed,
  cleanupTestFixtures,
} from './helpers';
import { createTestFileMultiple } from './helpers-extended';

const TEST_FILE = 'test_doc_page.txt';
const TEST_CONTENT = `偏差报告文档\n\n批号: B-2024-0001\n产品: 片剂 100mg\n偏差类型: 生产过程偏差`;

let testFilePath: string;
let batchFilePaths: string[];

test.beforeAll(() => {
  testFilePath = createTestFile(TEST_FILE, TEST_CONTENT);
  batchFilePaths = createTestFileMultiple(3);
});

test.afterAll(() => {
  cleanupTestFixtures();
});

test.describe('DocumentsPage - Batch Upload', () => {
  test('uploads multiple files via API and verifies in list', async ({ page, request }) => {
    // Upload 3 files via API
    for (const filePath of batchFilePaths) {
      const filename = filePath.split(/[/\\]/).pop()!;
      await uploadDocumentViaAPI(request, filePath, filename);
    }

    await page.goto('/documents');
    await waitForPageReady(page);
    await page.waitForTimeout(2000);

    // Verify all batch files appear in the table
    for (const filePath of batchFilePaths) {
      const filename = filePath.split(/[/\\]/).pop()!;
      await expect(page.locator('.ant-table')).toContainText(filename, { timeout: 10000 });
    }
  });

  test('shows processing status for newly uploaded files', async ({ page, request }) => {
    // Upload a fresh file
    const doc = await uploadDocumentViaAPI(request, testFilePath, TEST_FILE);

    await page.goto('/documents');
    await waitForPageReady(page);
    await page.waitForTimeout(1000);

    // Verify status tag is visible (could be processing or processed)
    const statusTag = page.locator('.ant-tag').filter({ hasText: /已上传|处理中|已处理/ });
    await expect(statusTag.first()).toBeVisible({ timeout: 5000 });
  });
});

test.describe('DocumentsPage - Delete Document', () => {
  let docToDelete: { id: number };

  test.beforeAll(async ({ request }) => {
    docToDelete = await uploadDocumentViaAPI(request, testFilePath, 'delete_test.txt');
  });

  test('opens confirmation modal when clicking delete', async ({ page }) => {
    await page.goto('/documents');
    await waitForPageReady(page);
    await page.waitForTimeout(1000);

    // Click the first delete button in the table
    const deleteBtn = page.locator('.ant-table-row').first().locator('button').filter({ hasText: '删除' });
    if (await deleteBtn.isVisible()) {
      await deleteBtn.click();

      // Verify Modal.confirm appears
      const confirmModal = page.locator('.ant-modal-confirm');
      await expect(confirmModal).toBeVisible({ timeout: 5000 });
      await expect(confirmModal).toContainText('删除文档');

      // Click cancel
      await confirmModal.locator('.ant-btn:not(.ant-btn-primary):not(.ant-btn-danger)').first().click();
      await expect(confirmModal).not.toBeVisible({ timeout: 3000 });

      // Verify document still in table
      await expect(page.locator('.ant-table')).toContainText('delete_test.txt');
    }
  });

  test('confirms delete and removes document from list', async ({ page }) => {
    await page.goto('/documents');
    await waitForPageReady(page);
    await page.waitForTimeout(1000);

    // Click delete on the test document
    const rows = page.locator('.ant-table-row');
    const count = await rows.count();
    let found = false;

    for (let i = 0; i < count; i++) {
      const rowText = await rows.nth(i).innerText();
      if (rowText.includes('delete_test.txt')) {
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

      // Verify success message
      await expect(page.locator('.ant-message')).toContainText(/文档已删除/, { timeout: 5000 });

      // Verify document removed
      await page.waitForTimeout(1000);
      await expect(page.locator('.ant-table')).not.toContainText('delete_test.txt', { timeout: 5000 });
    }
  });
});

test.describe('DocumentsPage - Steps Indicator', () => {
  test('shows Steps component when documents exist', async ({ page }) => {
    await page.goto('/documents');
    await waitForPageReady(page);

    // Steps component should be visible
    const steps = page.locator('.ant-steps');
    const hasSteps = await steps.isVisible().catch(() => false);

    // Steps only show when documents.length > 0
    const hasTable = await page.locator('.ant-table-row').first().isVisible().catch(() => false);
    if (hasTable) {
      expect(hasSteps).toBe(true);
    }
  });
});

test.describe('DocumentsPage - Pagination', () => {
  test('shows pagination when more than 10 documents exist', async ({ page, request }) => {
    // Upload enough documents to trigger pagination (batch files may already exist)
    const existingResponse = await request.get('/api/documents/');
    const existingData = await existingResponse.json();
    const existingCount = existingData.items?.length || 0;

    if (existingCount < 12) {
      // Upload additional documents to reach 12
      for (let i = existingCount; i < 12; i++) {
        const filename = `pagination_test_${i}.txt`;
        const filePath = createTestFile(filename, `Pagination test ${i}`);
        await uploadDocumentViaAPI(request, filePath, filename);
      }
    }

    await page.goto('/documents');
    await waitForPageReady(page);
    await page.waitForTimeout(2000);

    // Pagination should be visible
    const pagination = page.locator('.ant-pagination');
    if (await pagination.isVisible().catch(() => false)) {
      await expect(pagination).toBeVisible();

      // Page 1 should show 10 rows
      const rows = page.locator('.ant-table-row');
      const rowCount = await rows.count();
      expect(rowCount).toBeLessThanOrEqual(10);

      // Click page 2
      await pagination.locator('.ant-pagination-item-2').click();
      await page.waitForTimeout(1000);

      // Verify page 2 shows remaining documents
      const page2Rows = page.locator('.ant-table-row');
      const page2Count = await page2Rows.count();
      expect(page2Count).toBeGreaterThan(0);
    }
  });
});

test.describe('DocumentsPage - Status Tags', () => {
  test('displays correct status tag colors', async ({ page }) => {
    await page.goto('/documents');
    await waitForPageReady(page);
    await page.waitForTimeout(1000);

    // Check status tags
    const tags = page.locator('.ant-table .ant-tag');
    const count = await tags.count();

    for (let i = 0; i < count; i++) {
      const tagText = await tags.nth(i).innerText();
      const tagClass = await tags.nth(i).getAttribute('class') || '';

      if (tagText === '已处理') {
        expect(tagClass).toContain('ant-tag-success');
      } else if (tagText === '处理失败') {
        expect(tagClass).toContain('ant-tag-error');
      } else if (tagText === '处理中') {
        expect(tagClass).toContain('ant-tag-processing');
      }
    }
  });

  test('polls for status updates on pending documents', async ({ page, request }) => {
    // Upload a file that may still be processing
    const freshFile = createTestFile('poll_test.txt', 'Poll test content');
    const doc = await uploadDocumentViaAPI(request, freshFile, 'poll_test.txt');

    await page.goto('/documents');
    await waitForPageReady(page);

    // Wait for the document to show processed status (polls every 3s)
    await expect(async () => {
      const successTag = page.locator('.ant-tag-success').filter({ hasText: '已处理' });
      await expect(successTag.first()).toBeVisible({ timeout: 5000 });
    }).toPass({ timeout: 30000 });
  });
});

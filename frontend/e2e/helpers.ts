import { Page, APIRequestContext, expect } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';

/**
 * Wait for Ant Design layout to render and any loading spinners to disappear.
 */
export async function waitForPageReady(page: Page) {
  await page.waitForSelector('.ant-layout', { timeout: 10000 });
  try {
    await page.waitForSelector('.ant-spin-spinning', { state: 'hidden', timeout: 5000 });
  } catch {
    // No spinner present, that's fine
  }
}

/**
 * Create a temporary test file for upload tests.
 * Returns the absolute path to the created file.
 */
export function createTestFile(filename: string, content: string): string {
  const tmpDir = path.join(process.cwd(), 'test-fixtures');
  fs.mkdirSync(tmpDir, { recursive: true });
  const filePath = path.join(tmpDir, filename);
  fs.writeFileSync(filePath, content, 'utf-8');
  return filePath;
}

/**
 * Upload a file via the documents API endpoint.
 */
export async function uploadDocumentViaAPI(
  request: APIRequestContext,
  filePath: string,
  filename: string,
) {
  const content = fs.readFileSync(filePath);
  const response = await request.post('/api/documents/upload', {
    multipart: {
      file: {
        name: filename,
        mimeType: 'text/plain',
        buffer: content,
      },
    },
  });
  expect(response.ok()).toBeTruthy();
  return response.json();
}

/**
 * Poll a document until it reaches 'processed' status.
 * Throws if the document fails or times out.
 */
export async function waitForDocumentProcessed(
  request: APIRequestContext,
  documentId: number,
  timeoutMs = 30000,
) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const response = await request.get(`/api/documents/${documentId}`);
    const doc = await response.json();
    if (doc.process_status === 'processed') return doc;
    if (doc.process_status === 'failed') {
      throw new Error(`Document ${documentId} processing failed`);
    }
    await new Promise((r) => setTimeout(r, 1000));
  }
  throw new Error(`Document ${documentId} not processed within ${timeoutMs}ms`);
}

/**
 * Clean up test fixtures directory.
 */
export function cleanupTestFixtures() {
  const tmpDir = path.join(process.cwd(), 'test-fixtures');
  if (fs.existsSync(tmpDir)) {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
}

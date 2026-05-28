import * as fs from 'fs';
import * as path from 'path';

/**
 * Create multiple temporary test files for batch upload tests.
 * Returns an array of absolute file paths.
 */
export function createTestFileMultiple(count: number): string[] {
  const tmpDir = path.join(process.cwd(), 'test-fixtures');
  fs.mkdirSync(tmpDir, { recursive: true });

  const files: string[] = [];
  for (let i = 0; i < count; i++) {
    const filename = `batch_test_${i + 1}.txt`;
    const filePath = path.join(tmpDir, filename);
    fs.writeFileSync(
      filePath,
      `批次测试文档 ${i + 1}\n\n这是一个用于批量上传测试的临时文档。\n包含基础 GMP 合规内容。\n`,
      'utf-8',
    );
    files.push(filePath);
  }
  return files;
}

/**
 * Clean up KG test files from the input directory.
 */
export function cleanupKGTestFiles(): void {
  const kgInputDir = path.resolve(process.cwd(), '..', 'graphrag_index', 'input');
  if (!fs.existsSync(kgInputDir)) return;

  const files = fs.readdirSync(kgInputDir);
  for (const file of files) {
    if (file.startsWith('test_') || file.startsWith('batch_test_')) {
      fs.unlinkSync(path.join(kgInputDir, file));
    }
  }
}

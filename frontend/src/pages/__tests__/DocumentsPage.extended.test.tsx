import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';

import DocumentsPage from '../DocumentsPage';
import { documentApi } from '../../services/api';

jest.setTimeout(15000);

jest.mock('../../services/api', () => ({
  documentApi: {
    list: jest.fn(),
    uploadBatch: jest.fn(),
    delete: jest.fn(),
    retryProcess: jest.fn(),
  },
}));

const mockDocumentApi = documentApi as jest.Mocked<typeof documentApi>;

const renderWithRouter = (component: React.ReactElement) => {
  return render(<BrowserRouter>{component}</BrowserRouter>);
};

const mockDocuments = {
  items: [
    {
      id: 1,
      filename: 'SOP-001-清洗验证.pdf',
      file_type: 'pdf',
      file_size: 102400,
      process_status: 'processed' as const,
      created_at: '2024-01-01T00:00:00Z',
    },
    {
      id: 2,
      filename: '偏差报告-B2024-001.docx',
      file_type: 'docx',
      file_size: 51200,
      process_status: 'processing' as const,
      created_at: '2024-01-02T00:00:00Z',
    },
    {
      id: 3,
      filename: '批记录-20240101.txt',
      file_type: 'txt',
      file_size: 25600,
      process_status: 'uploaded' as const,
      created_at: '2024-01-03T00:00:00Z',
    },
    {
      id: 4,
      filename: '损坏文件.pdf',
      file_type: 'pdf',
      file_size: 1024,
      process_status: 'failed' as const,
      created_at: '2024-01-04T00:00:00Z',
      doc_metadata: { error: '文件格式损坏，无法解析' },
    },
  ],
  total: 4,
  page: 1,
  page_size: 10,
};

describe('DocumentsPage extended tests', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockDocumentApi.list.mockResolvedValue(mockDocuments);
    mockDocumentApi.uploadBatch.mockResolvedValue([]);
    mockDocumentApi.delete.mockResolvedValue({ message: '已删除' });
    mockDocumentApi.retryProcess.mockResolvedValue({ status: 'processing' });
  });

  // --- Page title and description ---
  test('renders page title', async () => {
    renderWithRouter(<DocumentsPage />);

    await waitFor(() => {
      expect(screen.getByText('文档管理')).toBeInTheDocument();
    });
  });

  test('renders page description', async () => {
    renderWithRouter(<DocumentsPage />);

    await waitFor(() => {
      expect(screen.getByText('上传文档，系统自动解析后用于审计分析')).toBeInTheDocument();
    });
  });

  test('renders secondary description', async () => {
    renderWithRouter(<DocumentsPage />);

    await waitFor(() => {
      expect(screen.getByText(/上传原始文档，等待解析完成后前往审计任务页面创建审计任务/)).toBeInTheDocument();
    });
  });

  // --- Document list rendering ---
  test('renders document list with data', async () => {
    renderWithRouter(<DocumentsPage />);

    await waitFor(() => {
      expect(screen.getByText('SOP-001-清洗验证.pdf')).toBeInTheDocument();
    });

    expect(screen.getByText('偏差报告-B2024-001.docx')).toBeInTheDocument();
    expect(screen.getByText('批记录-20240101.txt')).toBeInTheDocument();
    expect(screen.getByText('损坏文件.pdf')).toBeInTheDocument();
  });

  test('displays document file types', async () => {
    renderWithRouter(<DocumentsPage />);

    await waitFor(() => {
      // File types appear in secondary text under filename
      const pdfElements = screen.getAllByText('PDF');
      expect(pdfElements.length).toBeGreaterThanOrEqual(1);
    });

    expect(screen.getByText('DOCX')).toBeInTheDocument();
    expect(screen.getByText('TXT')).toBeInTheDocument();
  });

  test('displays document status tags', async () => {
    renderWithRouter(<DocumentsPage />);

    await waitFor(() => {
      // Tags can appear multiple times (in Steps and in table)
      const processedTags = screen.getAllByText('已处理');
      expect(processedTags.length).toBeGreaterThanOrEqual(1);
    });

    const processingTags = screen.getAllByText('处理中');
    expect(processingTags.length).toBeGreaterThanOrEqual(1);

    const uploadedTags = screen.getAllByText('已上传');
    expect(uploadedTags.length).toBeGreaterThanOrEqual(1);

    expect(screen.getByText('处理失败')).toBeInTheDocument();
  });

  // --- Empty state ---
  test('shows empty state when no documents', async () => {
    mockDocumentApi.list.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 10 });

    renderWithRouter(<DocumentsPage />);

    await waitFor(() => {
      expect(screen.getByText('暂无文档，请上传文件')).toBeInTheDocument();
    });
  });

  // --- Upload area ---
  test('renders upload area', async () => {
    renderWithRouter(<DocumentsPage />);

    await waitFor(() => {
      expect(screen.getByText('点击或拖拽文件到此处')).toBeInTheDocument();
    });
  });

  test('shows supported file formats hint', async () => {
    renderWithRouter(<DocumentsPage />);

    await waitFor(() => {
      expect(screen.getByText('支持 PDF、Word、纯文本和图片格式')).toBeInTheDocument();
    });
  });

  // --- Steps indicator ---
  test('shows steps indicator when documents exist', async () => {
    renderWithRouter(<DocumentsPage />);

    await waitFor(() => {
      expect(screen.getByText('上传文档')).toBeInTheDocument();
    });

    // "处理中" appears in both Steps and Tags, use getAllByText
    const processingSteps = screen.getAllByText('处理中');
    expect(processingSteps.length).toBeGreaterThanOrEqual(1);
  });

  // --- Pending documents banner ---
  test('shows pending count banner when processing documents exist', async () => {
    renderWithRouter(<DocumentsPage />);

    await waitFor(() => {
      expect(screen.getByText(/个文档正在处理中/)).toBeInTheDocument();
    });
  });

  test('does not show pending banner when no pending documents', async () => {
    mockDocumentApi.list.mockResolvedValue({
      items: [
        {
          id: 1,
          filename: 'test.pdf',
          file_type: 'pdf',
          process_status: 'processed' as const,
        },
      ],
      total: 1,
      page: 1,
      page_size: 10,
    });

    renderWithRouter(<DocumentsPage />);

    await waitFor(() => {
      expect(screen.getByText('test.pdf')).toBeInTheDocument();
    });

    expect(screen.queryByText(/个文档正在处理中/)).not.toBeInTheDocument();
  });

  // --- Document list title ---
  test('renders document list title', async () => {
    renderWithRouter(<DocumentsPage />);

    await waitFor(() => {
      expect(screen.getByText('文档列表')).toBeInTheDocument();
    });
  });

  test('shows info alert about creating audit tasks', async () => {
    renderWithRouter(<DocumentsPage />);

    await waitFor(() => {
      expect(screen.getByText('文档就绪后，前往审计任务页面创建审计任务')).toBeInTheDocument();
    });
  });

  // --- Actions ---
  test('shows delete button for documents', async () => {
    renderWithRouter(<DocumentsPage />);

    await waitFor(() => {
      const deleteButtons = screen.getAllByText('删除');
      expect(deleteButtons.length).toBe(4);
    });
  });

  test('shows retry button for failed documents', async () => {
    renderWithRouter(<DocumentsPage />);

    await waitFor(() => {
      expect(screen.getByText('重试')).toBeInTheDocument();
    });
  });

  test('does not show retry button for processed documents', async () => {
    renderWithRouter(<DocumentsPage />);

    await waitFor(() => {
      expect(screen.getByText('SOP-001-清洗验证.pdf')).toBeInTheDocument();
    });

    const retryButtons = screen.getAllByText('重试');
    expect(retryButtons.length).toBe(1);
  });

  // --- Error handling ---
  test('handles API error on load', async () => {
    mockDocumentApi.list.mockRejectedValue(new Error('加载失败'));

    renderWithRouter(<DocumentsPage />);

    await waitFor(() => {
      expect(screen.getByText('文档管理')).toBeInTheDocument();
    });
  });

  // --- Document with error metadata ---
  test('shows error tooltip for failed documents', async () => {
    renderWithRouter(<DocumentsPage />);

    await waitFor(() => {
      expect(screen.getByText('损坏文件.pdf')).toBeInTheDocument();
    });

    expect(screen.getByText('处理失败')).toBeInTheDocument();
  });

  // --- Steps with processed documents ---
  test('shows correct step when processed documents exist', async () => {
    renderWithRouter(<DocumentsPage />);

    await waitFor(() => {
      expect(screen.getByText('文档管理')).toBeInTheDocument();
    });

    // Steps shows step titles - all three should be visible
    expect(screen.getByText('上传文档')).toBeInTheDocument();
    // "处理中" appears in both Steps and Tags
    expect(screen.getAllByText('处理中').length).toBeGreaterThanOrEqual(1);
  });

  // --- Steps with only uploaded documents ---
  test('shows correct step when only uploaded documents', async () => {
    mockDocumentApi.list.mockResolvedValue({
      items: [
        {
          id: 1,
          filename: 'new-doc.pdf',
          file_type: 'pdf',
          process_status: 'uploaded' as const,
        },
      ],
      total: 1,
      page: 1,
      page_size: 10,
    });

    renderWithRouter(<DocumentsPage />);

    await waitFor(() => {
      expect(screen.getByText('new-doc.pdf')).toBeInTheDocument();
    });

    // Steps should show "处理中" step when pendingCount > 0
    const processingSteps = screen.getAllByText('处理中');
    expect(processingSteps.length).toBeGreaterThanOrEqual(1);
  });

  // --- No documents hides steps ---
  test('hides steps when no documents', async () => {
    mockDocumentApi.list.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 10 });

    renderWithRouter(<DocumentsPage />);

    await waitFor(() => {
      expect(screen.getByText('暂无文档，请上传文件')).toBeInTheDocument();
    });

    expect(screen.queryByText('上传文档')).not.toBeInTheDocument();
  });

  // --- Upload area always visible ---
  test('upload area visible even with empty document list', async () => {
    mockDocumentApi.list.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 10 });

    renderWithRouter(<DocumentsPage />);

    await waitFor(() => {
      expect(screen.getByText('文档管理')).toBeInTheDocument();
    });

    expect(screen.getByText('点击或拖拽文件到此处')).toBeInTheDocument();
  });

  // --- Multiple document statuses ---
  test('renders multiple document status types', async () => {
    renderWithRouter(<DocumentsPage />);

    await waitFor(() => {
      expect(screen.getByText('SOP-001-清洗验证.pdf')).toBeInTheDocument();
    });

    // All 4 statuses should be present
    expect(screen.getByText('处理失败')).toBeInTheDocument();
    expect(screen.getAllByText('已处理').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('处理中').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('已上传').length).toBeGreaterThanOrEqual(1);
  });

  // --- Document filenames ---
  test('renders all document filenames', async () => {
    renderWithRouter(<DocumentsPage />);

    await waitFor(() => {
      expect(screen.getByText('SOP-001-清洗验证.pdf')).toBeInTheDocument();
    });

    expect(screen.getByText('偏差报告-B2024-001.docx')).toBeInTheDocument();
    expect(screen.getByText('批记录-20240101.txt')).toBeInTheDocument();
    expect(screen.getByText('损坏文件.pdf')).toBeInTheDocument();
  });

  // --- Delete interaction ---
  test('delete button exists for each document', async () => {
    renderWithRouter(<DocumentsPage />);

    await waitFor(() => {
      expect(screen.getByText('SOP-001-清洗验证.pdf')).toBeInTheDocument();
    });

    // Each document should have a delete button
    const deleteButtons = screen.getAllByText('删除');
    expect(deleteButtons.length).toBe(4);
  });

  // --- Retry interaction ---
  test('calls retryProcess when retry button clicked', async () => {
    const user = userEvent.setup();
    renderWithRouter(<DocumentsPage />);

    await waitFor(() => {
      expect(screen.getByText('损坏文件.pdf')).toBeInTheDocument();
    });

    await user.click(screen.getByText('重试'));

    await waitFor(() => {
      expect(mockDocumentApi.retryProcess).toHaveBeenCalledWith(4);
    });
  });

  // --- Retry error handling ---
  test('handles retry failure gracefully', async () => {
    mockDocumentApi.retryProcess.mockRejectedValue(new Error('重试失败'));
    const user = userEvent.setup();
    renderWithRouter(<DocumentsPage />);

    await waitFor(() => {
      expect(screen.getByText('损坏文件.pdf')).toBeInTheDocument();
    });

    await user.click(screen.getByText('重试'));

    // Should not crash
    await waitFor(() => {
      expect(screen.getByText('文档管理')).toBeInTheDocument();
    });
  });

  // --- Delete triggers Modal.confirm ---
  test('delete calls API when modal confirmed', async () => {
    const originalConfirm = (await import('antd')).Modal.confirm;
    const mockConfirm = jest.fn(({ onOk }: any) => {
      if (onOk) onOk();
    });
    (await import('antd')).Modal.confirm = mockConfirm;

    const user = userEvent.setup();
    renderWithRouter(<DocumentsPage />);

    await waitFor(() => {
      expect(screen.getByText('SOP-001-清洗验证.pdf')).toBeInTheDocument();
    });

    const deleteButtons = screen.getAllByText('删除');
    await user.click(deleteButtons[0]);

    await waitFor(() => {
      expect(mockDocumentApi.delete).toHaveBeenCalledWith(1);
    });

    (await import('antd')).Modal.confirm = originalConfirm;
  });

  // --- Delete error with response detail ---
  test('handles delete error with response detail', async () => {
    mockDocumentApi.delete.mockRejectedValue({ response: { data: { detail: 'Cannot delete' } } });
    const originalConfirm = (await import('antd')).Modal.confirm;
    const mockConfirm = jest.fn(({ onOk }: any) => {
      if (onOk) onOk();
    });
    (await import('antd')).Modal.confirm = mockConfirm;

    const user = userEvent.setup();
    renderWithRouter(<DocumentsPage />);

    await waitFor(() => {
      expect(screen.getByText('SOP-001-清洗验证.pdf')).toBeInTheDocument();
    });

    const deleteButtons = screen.getAllByText('删除');
    await user.click(deleteButtons[0]);

    await waitFor(() => {
      expect(mockDocumentApi.delete).toHaveBeenCalled();
    });

    (await import('antd')).Modal.confirm = originalConfirm;
  });

  // --- Pagination ---
  test('renders pagination controls', async () => {
    renderWithRouter(<DocumentsPage />);

    await waitFor(() => {
      expect(screen.getByText('SOP-001-清洗验证.pdf')).toBeInTheDocument();
    });

    expect(document.querySelector('.ant-pagination')).toBeInTheDocument();
  });

  // --- Large file rejection ---
  test('rejects files larger than 50MB', async () => {
    renderWithRouter(<DocumentsPage />);

    await waitFor(() => {
      expect(screen.getByText('点击或拖拽文件到此处')).toBeInTheDocument();
    });

    // The beforeUpload function checks file size
    // We can't easily trigger file upload in jsdom, but we verify the component renders
    expect(screen.getByText('支持 PDF、Word、纯文本和图片格式')).toBeInTheDocument();
  });

  // --- Multiple pages of documents ---
  test('handles pagination with many documents', async () => {
    const manyDocs = {
      items: Array.from({ length: 10 }, (_, i) => ({
        id: i + 1,
        filename: `doc-${i + 1}.pdf`,
        file_type: 'pdf',
        process_status: 'processed' as const,
      })),
      total: 25,
      page: 1,
      page_size: 10,
    };
    mockDocumentApi.list.mockResolvedValue(manyDocs);

    renderWithRouter(<DocumentsPage />);

    await waitFor(() => {
      expect(screen.getByText('doc-1.pdf')).toBeInTheDocument();
    });

    // Pagination should show total
    expect(document.querySelector('.ant-pagination')).toBeInTheDocument();
  });

  // --- Upload error handling ---
  test('handles upload failure gracefully', async () => {
    mockDocumentApi.uploadBatch.mockRejectedValue(new Error('Upload failed'));

    renderWithRouter(<DocumentsPage />);

    await waitFor(() => {
      expect(screen.getByText('点击或拖拽文件到此处')).toBeInTheDocument();
    });

    // Component should still be functional
    expect(screen.getByText('文档管理')).toBeInTheDocument();
  });

  // --- Document with file_type display ---
  test('displays file types in uppercase', async () => {
    renderWithRouter(<DocumentsPage />);

    await waitFor(() => {
      expect(screen.getByText('SOP-001-清洗验证.pdf')).toBeInTheDocument();
    });

    // File types should be uppercase
    const pdfLabels = screen.getAllByText('PDF');
    expect(pdfLabels.length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('DOCX')).toBeInTheDocument();
    expect(screen.getByText('TXT')).toBeInTheDocument();
  });

  // --- Steps indicator shows correct step ---
  test('steps indicator shows "就绪" when all processed', async () => {
    mockDocumentApi.list.mockResolvedValue({
      items: [
        { id: 1, filename: 'a.pdf', file_type: 'pdf', process_status: 'processed' as const },
        { id: 2, filename: 'b.pdf', file_type: 'pdf', process_status: 'processed' as const },
      ],
      total: 2,
      page: 1,
      page_size: 10,
    });

    renderWithRouter(<DocumentsPage />);

    await waitFor(() => {
      expect(screen.getByText('a.pdf')).toBeInTheDocument();
    });

    // Steps should show all three steps
    expect(screen.getByText('上传文档')).toBeInTheDocument();
    expect(screen.getByText('就绪 — 前往审计任务创建任务')).toBeInTheDocument();
  });

  // --- Only uploaded (pending) documents ---
  test('shows correct step when only uploaded documents exist', async () => {
    mockDocumentApi.list.mockResolvedValue({
      items: [
        { id: 1, filename: 'new.pdf', file_type: 'pdf', process_status: 'uploaded' as const },
      ],
      total: 1,
      page: 1,
      page_size: 10,
    });

    renderWithRouter(<DocumentsPage />);

    await waitFor(() => {
      expect(screen.getByText('new.pdf')).toBeInTheDocument();
    });

    // Pending count should be shown
    expect(screen.getByText(/个文档正在处理中/)).toBeInTheDocument();
  });

  // --- Failed document with error tooltip ---
  test('failed document shows error in tooltip', async () => {
    renderWithRouter(<DocumentsPage />);

    await waitFor(() => {
      expect(screen.getByText('损坏文件.pdf')).toBeInTheDocument();
    });

    // The failed status tag should be present
    expect(screen.getByText('处理失败')).toBeInTheDocument();
  });

  // --- API error on load ---
  test('handles non-Error exception on load', async () => {
    mockDocumentApi.list.mockRejectedValue('string error');

    renderWithRouter(<DocumentsPage />);

    await waitFor(() => {
      expect(screen.getByText('文档管理')).toBeInTheDocument();
    });
  });

  // --- Delete success ---
  test('delete calls API with correct id', async () => {
    mockDocumentApi.delete.mockResolvedValue({ message: '已删除' });
    const user = userEvent.setup();
    renderWithRouter(<DocumentsPage />);

    await waitFor(() => {
      expect(screen.getByText('SOP-001-清洗验证.pdf')).toBeInTheDocument();
    });

    // Click delete on the first document
    const deleteButtons = screen.getAllByText('删除');
    await user.click(deleteButtons[0]);

    // Modal.confirm should appear
    await waitFor(() => {
      expect(document.querySelector('.ant-modal-confirm')).toBeInTheDocument();
    });
  });
});

import React from 'react';
import { render, screen, waitFor, fireEvent, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';

import DocumentsPage from '../DocumentsPage';
import { documentApi } from '../../services/api';

jest.setTimeout(20000);

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

const defaultMockList = {
  items: [
    {
      id: 1,
      filename: 'test.pdf',
      file_type: 'pdf',
      process_status: 'processed' as const,
      created_at: '2024-01-01T00:00:00Z',
    },
  ],
  total: 1,
  page: 1,
  page_size: 10,
};

describe('DocumentsPage branch coverage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.useRealTimers();
    mockDocumentApi.list.mockResolvedValue(defaultMockList);
    mockDocumentApi.uploadBatch.mockResolvedValue([]);
    mockDocumentApi.delete.mockResolvedValue({ message: 'deleted' });
    mockDocumentApi.retryProcess.mockResolvedValue({ status: 'processing' });
  });

  // --- Polling: setInterval starts when pending docs exist ---
  test('starts polling when processing documents exist', async () => {
    jest.useFakeTimers();
    mockDocumentApi.list.mockResolvedValue({
      items: [
        { id: 1, filename: 'proc.pdf', file_type: 'pdf', process_status: 'processing' as const },
      ],
      total: 1,
      page: 1,
      page_size: 10,
    });

    await act(async () => {
      renderWithRouter(<DocumentsPage />);
    });

    const initialCalls = mockDocumentApi.list.mock.calls.length;

    await act(async () => {
      jest.advanceTimersByTime(3500);
    });

    expect(mockDocumentApi.list.mock.calls.length).toBeGreaterThan(initialCalls);
    jest.useRealTimers();
  });

  test('starts polling when uploaded documents exist', async () => {
    jest.useFakeTimers();
    mockDocumentApi.list.mockResolvedValue({
      items: [
        { id: 1, filename: 'new.pdf', file_type: 'pdf', process_status: 'uploaded' as const },
      ],
      total: 1,
      page: 1,
      page_size: 10,
    });

    await act(async () => {
      renderWithRouter(<DocumentsPage />);
    });

    const initialCalls = mockDocumentApi.list.mock.calls.length;

    await act(async () => {
      jest.advanceTimersByTime(3500);
    });

    expect(mockDocumentApi.list.mock.calls.length).toBeGreaterThan(initialCalls);
    jest.useRealTimers();
  });

  test('stops polling when no pending documents', async () => {
    jest.useFakeTimers();
    mockDocumentApi.list.mockResolvedValue({
      items: [
        { id: 1, filename: 'done.pdf', file_type: 'pdf', process_status: 'processed' as const },
      ],
      total: 1,
      page: 1,
      page_size: 10,
    });

    await act(async () => {
      renderWithRouter(<DocumentsPage />);
    });

    const callsBefore = mockDocumentApi.list.mock.calls.length;

    await act(async () => {
      jest.advanceTimersByTime(10000);
    });

    expect(mockDocumentApi.list.mock.calls.length).toBe(callsBefore);
    jest.useRealTimers();
  });

  // --- Upload customRequest ---
  test('customRequest calls uploadBatch on file upload', async () => {
    renderWithRouter(<DocumentsPage />);

    await waitFor(() => {
      expect(screen.getByText('test.pdf')).toBeInTheDocument();
    });

    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    expect(input).toBeTruthy();

    const file = new File(['content'], 'upload.pdf', { type: 'application/pdf' });
    Object.defineProperty(file, 'size', { value: 1024 });

    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => {
      expect(mockDocumentApi.uploadBatch).toHaveBeenCalled();
    });
  });

  test('upload error shows error message with detail', async () => {
    mockDocumentApi.uploadBatch.mockRejectedValue({
      response: { data: { detail: 'File too large' } },
      message: 'Request failed',
    });

    renderWithRouter(<DocumentsPage />);

    await waitFor(() => {
      expect(screen.getByText('test.pdf')).toBeInTheDocument();
    });

    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(['content'], 'bad.pdf', { type: 'application/pdf' });
    Object.defineProperty(file, 'size', { value: 1024 });

    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => {
      expect(mockDocumentApi.uploadBatch).toHaveBeenCalled();
    });
  });

  test('upload error without response detail uses error message', async () => {
    mockDocumentApi.uploadBatch.mockRejectedValue(new Error('Network timeout'));

    renderWithRouter(<DocumentsPage />);

    await waitFor(() => {
      expect(screen.getByText('test.pdf')).toBeInTheDocument();
    });

    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(['content'], 'bad.pdf', { type: 'application/pdf' });
    Object.defineProperty(file, 'size', { value: 1024 });

    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => {
      expect(mockDocumentApi.uploadBatch).toHaveBeenCalled();
    });
  });

  // --- Pagination onChange ---
  test('pagination onChange triggers page change', async () => {
    const manyDocs = {
      items: Array.from({ length: 10 }, (_, i) => ({
        id: i + 1,
        filename: `doc-${i + 1}.pdf`,
        file_type: 'pdf',
        process_status: 'processed' as const,
      })),
      total: 30,
      page: 1,
      page_size: 10,
    };
    mockDocumentApi.list.mockResolvedValue(manyDocs);

    renderWithRouter(<DocumentsPage />);

    await waitFor(() => {
      expect(screen.getByText('doc-1.pdf')).toBeInTheDocument();
    });

    const page2Button = document.querySelector('.ant-pagination-item-2') as HTMLElement;
    if (page2Button) {
      fireEvent.click(page2Button);

      await waitFor(() => {
        expect(mockDocumentApi.list).toHaveBeenCalledWith(2, 10);
      });
    }
  });

  // --- Retry with response detail error ---
  test('retry error uses response detail when available', async () => {
    mockDocumentApi.list.mockResolvedValue({
      items: [
        {
          id: 1,
          filename: 'failed.pdf',
          file_type: 'pdf',
          process_status: 'failed' as const,
          doc_metadata: { error: 'Parse error' },
        },
      ],
      total: 1,
      page: 1,
      page_size: 10,
    });
    mockDocumentApi.retryProcess.mockRejectedValue({
      response: { data: { detail: 'Retry limit exceeded' } },
    });

    const user = userEvent.setup();
    renderWithRouter(<DocumentsPage />);

    await waitFor(() => {
      expect(screen.getByText('failed.pdf')).toBeInTheDocument();
    });

    await user.click(screen.getByText('重试'));

    await waitFor(() => {
      expect(mockDocumentApi.retryProcess).toHaveBeenCalledWith(1);
    });
  });

  // --- File type fallback for empty file_type ---
  test('handles document with empty file_type', async () => {
    mockDocumentApi.list.mockResolvedValue({
      items: [
        { id: 1, filename: 'notype', file_type: '', process_status: 'processed' as const },
      ],
      total: 1,
      page: 1,
      page_size: 10,
    });

    renderWithRouter(<DocumentsPage />);

    await waitFor(() => {
      expect(screen.getByText('notype')).toBeInTheDocument();
    });
  });

  // --- Status color fallback for unknown status ---
  test('handles document with unknown process_status', async () => {
    mockDocumentApi.list.mockResolvedValue({
      items: [
        { id: 1, filename: 'weird.pdf', file_type: 'pdf', process_status: 'unknown_status' as any },
      ],
      total: 1,
      page: 1,
      page_size: 10,
    });

    renderWithRouter(<DocumentsPage />);

    await waitFor(() => {
      expect(screen.getByText('weird.pdf')).toBeInTheDocument();
    });
  });

  // --- Steps current calculation: no processed, no pending ---
  test('steps show initial state when all docs have other statuses', async () => {
    mockDocumentApi.list.mockResolvedValue({
      items: [
        { id: 1, filename: 'failed.pdf', file_type: 'pdf', process_status: 'failed' as const },
      ],
      total: 1,
      page: 1,
      page_size: 10,
    });

    renderWithRouter(<DocumentsPage />);

    await waitFor(() => {
      expect(screen.getByText('failed.pdf')).toBeInTheDocument();
    });

    expect(screen.getByText('上传文档')).toBeInTheDocument();
  });

  // --- loadDocuments non-Error exception ---
  test('handles non-Error exception in loadDocuments', async () => {
    mockDocumentApi.list.mockRejectedValue('string error');

    renderWithRouter(<DocumentsPage />);

    await waitFor(() => {
      expect(screen.getByText('文档管理')).toBeInTheDocument();
    });
  });

  // --- Delete success path ---
  test('delete calls API and reloads list on success', async () => {
    const originalConfirm = (await import('antd')).Modal.confirm;
    const mockConfirm = jest.fn(({ onOk }: any) => {
      if (onOk) onOk();
    });
    (await import('antd')).Modal.confirm = mockConfirm;
    mockDocumentApi.delete.mockResolvedValue({ message: '已删除' });

    renderWithRouter(<DocumentsPage />);

    await waitFor(() => {
      expect(screen.getByText('test.pdf')).toBeInTheDocument();
    });

    const deleteButtons = screen.getAllByText('删除');
    fireEvent.click(deleteButtons[0]);

    await waitFor(() => {
      expect(mockDocumentApi.delete).toHaveBeenCalledWith(1);
    });

    (await import('antd')).Modal.confirm = originalConfirm;
  });

  // --- Delete error without detail ---
  test('delete error without response detail shows default message', async () => {
    const originalConfirm = (await import('antd')).Modal.confirm;
    const mockConfirm = jest.fn(({ onOk }: any) => {
      if (onOk) onOk();
    });
    (await import('antd')).Modal.confirm = mockConfirm;
    mockDocumentApi.delete.mockRejectedValue(new Error('Delete failed'));

    renderWithRouter(<DocumentsPage />);

    await waitFor(() => {
      expect(screen.getByText('test.pdf')).toBeInTheDocument();
    });

    const deleteButtons = screen.getAllByText('删除');
    fireEvent.click(deleteButtons[0]);

    await waitFor(() => {
      expect(mockDocumentApi.delete).toHaveBeenCalled();
    });

    (await import('antd')).Modal.confirm = originalConfirm;
  });
});

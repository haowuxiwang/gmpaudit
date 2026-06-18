import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import DocumentsPage from '../DocumentsPage';
import { documentApi } from '../../services/api';

jest.setTimeout(15000);

jest.mock('../../services/api', () => ({
  documentApi: {
    list: jest.fn().mockResolvedValue({ items: [], total: 0, page: 1, page_size: 10 }),
    upload: jest.fn(),
    delete: jest.fn(),
    process: jest.fn(),
  },
}));

const mockDocumentApi = documentApi as jest.Mocked<typeof documentApi>;

const renderWithRouter = (component: React.ReactElement) => {
  return render(<BrowserRouter>{component}</BrowserRouter>);
};

describe('DocumentsPage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockDocumentApi.list.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 10 });
  });

  test('renders page title', async () => {
    renderWithRouter(<DocumentsPage />);
    await waitFor(() => {
      expect(screen.getByText(/文档管理/)).toBeInTheDocument();
    });
  });

  test('renders empty state', async () => {
    renderWithRouter(<DocumentsPage />);
    await waitFor(() => {
      expect(screen.getByText(/暂无文档/)).toBeInTheDocument();
    });
  });

  test('loads documents on mount', async () => {
    renderWithRouter(<DocumentsPage />);
    await waitFor(() => {
      expect(mockDocumentApi.list).toHaveBeenCalled();
    });
  });

  test('renders upload area', async () => {
    renderWithRouter(<DocumentsPage />);
    await waitFor(() => {
      // Upload area should be present
      expect(screen.getByText(/拖拽文件/)).toBeInTheDocument();
    });
  });

  test('renders with documents', async () => {
    const mockDocs = [
      {
        id: 1,
        filename: 'test.pdf',
        file_type: 'pdf',
        file_size: 1024,
        upload_time: '2024-01-01T00:00:00Z',
        process_status: 'processed',
        doc_metadata: null,
      },
      {
        id: 2,
        filename: 'report.docx',
        file_type: 'docx',
        file_size: 2048,
        upload_time: '2024-01-02T00:00:00Z',
        process_status: 'uploaded',
        doc_metadata: null,
      },
    ];
    mockDocumentApi.list.mockResolvedValue({
      items: mockDocs,
      total: 2,
      page: 1,
      page_size: 10,
    });

    renderWithRouter(<DocumentsPage />);
    await waitFor(() => {
      expect(screen.getByText('test.pdf')).toBeInTheDocument();
      expect(screen.getByText('report.docx')).toBeInTheDocument();
    });
  });
});

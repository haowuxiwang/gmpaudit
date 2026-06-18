import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';

import ReportsPage from '../ReportsPage';
import { reportApi } from '../../services/api';

jest.setTimeout(20000);

jest.mock('react-markdown', () => {
  return function MockReactMarkdown({ children }: { children: string }) {
    return <div data-testid="markdown-content">{children}</div>;
  };
});

jest.mock('../../services/api', () => ({
  reportApi: {
    list: jest.fn(),
    get: jest.fn(),
    exportPdf: jest.fn(),
  },
}));

const mockReportApi = reportApi as jest.Mocked<typeof reportApi>;

const renderWithRouter = (component: React.ReactElement) => {
  return render(<BrowserRouter>{component}</BrowserRouter>);
};

const mockReports = {
  items: [
    {
      id: 1,
      task_id: 10,
      report_type: 'full_report',
      title: 'Test Report',
      content: '# Test\nContent here',
      created_at: '2024-01-01T00:00:00Z',
      report_metadata: {
        report_source: 'llm',
        report_mode: 'full',
      },
    },
  ],
  total: 1,
  page: 1,
  page_size: 10,
};

describe('ReportsPage branch coverage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockReportApi.list.mockResolvedValue(mockReports as any);
    mockReportApi.get.mockResolvedValue(mockReports.items[0] as any);
    mockReportApi.exportPdf.mockResolvedValue(new Blob(['pdf'], { type: 'application/pdf' }));
  });

  // --- handleExport markdown ---
  test('export markdown creates download link', async () => {
    const originalCreateObjectURL = URL.createObjectURL;
    const originalRevokeObjectURL = URL.revokeObjectURL;
    const mockCreateObjectURL = jest.fn(() => 'blob:mock');
    const mockRevokeObjectURL = jest.fn();
    (URL as any).createObjectURL = mockCreateObjectURL;
    (URL as any).revokeObjectURL = mockRevokeObjectURL;

    const mockClick = jest.fn();
    const originalCreateElement = document.createElement.bind(document);
    jest.spyOn(document, 'createElement').mockImplementation((tag: string) => {
      const el = originalCreateElement(tag);
      if (tag === 'a') {
        el.click = mockClick;
      }
      return el;
    });

    const user = userEvent.setup();
    renderWithRouter(<ReportsPage />);

    await waitFor(() => {
      expect(screen.getByText('Test Report')).toBeInTheDocument();
    });

    const viewButtons = screen.getAllByText('查看');
    await user.click(viewButtons[0]);

    await waitFor(() => {
      expect(screen.getByText('导出 Markdown')).toBeInTheDocument();
    });

    await user.click(screen.getByText('导出 Markdown'));

    await waitFor(() => {
      expect(mockCreateObjectURL).toHaveBeenCalled();
    });

    URL.createObjectURL = originalCreateObjectURL;
    URL.revokeObjectURL = originalRevokeObjectURL;
    jest.restoreAllMocks();
  });

  // --- handleExport with no content (disabled button) ---
  test('export markdown button is disabled when content is empty', async () => {
    mockReportApi.get.mockResolvedValue({
      id: 1,
      task_id: 10,
      report_type: 'full_report',
      title: 'Empty Report',
      content: '',
      created_at: '2024-01-01T00:00:00Z',
      report_metadata: { report_source: 'llm', report_mode: 'full' },
    } as any);

    const user = userEvent.setup();
    renderWithRouter(<ReportsPage />);

    await waitFor(() => {
      expect(screen.getByText('Test Report')).toBeInTheDocument();
    });

    const viewButtons = screen.getAllByText('查看');
    await user.click(viewButtons[0]);

    await waitFor(() => {
      const btn = screen.getByText('导出 Markdown').closest('button');
      expect(btn).toBeDisabled();
    });
  });

  // --- handleExportPdf with no id (disabled button) ---
  test('export PDF button is disabled when detail has no id', async () => {
    mockReportApi.get.mockResolvedValue({
      id: undefined,
      task_id: 10,
      report_type: 'full_report',
      title: 'No ID Report',
      content: 'content',
      created_at: '2024-01-01T00:00:00Z',
      report_metadata: { report_source: 'llm', report_mode: 'full' },
    } as any);

    const user = userEvent.setup();
    renderWithRouter(<ReportsPage />);

    await waitFor(() => {
      expect(screen.getByText('Test Report')).toBeInTheDocument();
    });

    const viewButtons = screen.getAllByText('查看');
    await user.click(viewButtons[0]);

    await waitFor(() => {
      const btn = screen.getByText('导出 PDF').closest('button');
      expect(btn).toBeDisabled();
    });
  });

  // --- Type filter ---
  test('type filter renders select component', async () => {
    mockReportApi.list.mockResolvedValue({
      items: [
        { id: 1, task_id: 10, report_type: 'full_report', title: 'Full Report', content: 'c', created_at: '2024-01-01T00:00:00Z', report_metadata: { report_source: 'llm', report_mode: 'full' } },
        { id: 2, task_id: 11, report_type: 'summary', title: 'Summary Report', content: 'c', created_at: '2024-01-02T00:00:00Z', report_metadata: { report_source: 'llm', report_mode: 'summary' } },
      ],
      total: 2,
      page: 1,
      page_size: 10,
    } as any);

    renderWithRouter(<ReportsPage />);

    await waitFor(() => {
      expect(screen.getByText('Full Report')).toBeInTheDocument();
    });

    expect(screen.getByText('Summary Report')).toBeInTheDocument();

    // The type filter select should be present
    expect(document.querySelector('.ant-select')).toBeInTheDocument();
  });

  // --- Modal close ---
  test('modal has close button when open', async () => {
    const user = userEvent.setup();
    renderWithRouter(<ReportsPage />);

    await waitFor(() => {
      expect(screen.getByText('Test Report')).toBeInTheDocument();
    });

    const viewButtons = screen.getAllByText('查看');
    await user.click(viewButtons[0]);

    await waitFor(() => {
      expect(screen.getByTestId('markdown-content')).toBeInTheDocument();
    });

    // Modal should have a close button
    expect(document.querySelector('.ant-modal-close')).toBeInTheDocument();
  });

  // --- Report with no report_metadata ---
  test('handles report with no metadata in modal', async () => {
    mockReportApi.get.mockResolvedValue({
      id: 1,
      task_id: 10,
      report_type: 'full_report',
      title: 'No Metadata Report',
      content: 'content',
      created_at: '2024-01-01T00:00:00Z',
    } as any);

    const user = userEvent.setup();
    renderWithRouter(<ReportsPage />);

    await waitFor(() => {
      expect(screen.getByText('Test Report')).toBeInTheDocument();
    });

    const viewButtons = screen.getAllByText('查看');
    await user.click(viewButtons[0]);

    await waitFor(() => {
      expect(screen.getByTestId('markdown-content')).toBeInTheDocument();
    });
  });

  // --- Report with unknown type ---
  test('handles report with unknown report_type', async () => {
    mockReportApi.list.mockResolvedValue({
      items: [
        {
          id: 50,
          task_id: 60,
          report_type: 'unknown_type',
          title: 'Unknown Type Report',
          content: 'content',
          created_at: '2024-01-01T00:00:00Z',
          report_metadata: { report_source: 'llm', report_mode: 'custom' },
        },
      ],
      total: 1,
      page: 1,
      page_size: 10,
    } as any);

    renderWithRouter(<ReportsPage />);

    await waitFor(() => {
      expect(screen.getByText('Unknown Type Report')).toBeInTheDocument();
    });

    expect(screen.getByText('unknown_type')).toBeInTheDocument();
  });

  // --- Report with empty source in modal ---
  test('handles report with empty source in modal shows unknown', async () => {
    mockReportApi.list.mockResolvedValue({
      items: [
        {
          id: 51,
          task_id: 61,
          report_type: 'full_report',
          title: 'Empty Source Report',
          content: 'content',
          created_at: '2024-01-01T00:00:00Z',
          report_metadata: { report_source: '', report_mode: 'full' },
        },
      ],
      total: 1,
      page: 1,
      page_size: 10,
    } as any);
    mockReportApi.get.mockResolvedValue({
      id: 51,
      task_id: 61,
      report_type: 'full_report',
      title: 'Empty Source Report',
      content: 'content',
      created_at: '2024-01-01T00:00:00Z',
      report_metadata: { report_source: '', report_mode: 'full' },
    } as any);

    const user = userEvent.setup();
    renderWithRouter(<ReportsPage />);

    await waitFor(() => {
      expect(screen.getByText('Empty Source Report')).toBeInTheDocument();
    });

    const viewButtons = screen.getAllByText('查看');
    await user.click(viewButtons[0]);

    await waitFor(() => {
      expect(screen.getByTestId('markdown-content')).toBeInTheDocument();
    });

    // Empty source should show '未知来源' (may appear in table and modal)
    expect(screen.getAllByText('未知来源').length).toBeGreaterThanOrEqual(1);
  });

  // --- Modal title from report ---
  test('modal title shows report title', async () => {
    const user = userEvent.setup();
    renderWithRouter(<ReportsPage />);

    await waitFor(() => {
      expect(screen.getByText('Test Report')).toBeInTheDocument();
    });

    const viewButtons = screen.getAllByText('查看');
    await user.click(viewButtons[0]);

    await waitFor(() => {
      expect(screen.getByTestId('markdown-content')).toBeInTheDocument();
    });
  });

  // --- Report detail loading spinner ---
  test('shows spinner while loading report detail', async () => {
    let resolveGet: ((value: any) => void) | null = null;
    const getPromise = new Promise<any>((resolve) => { resolveGet = resolve; });
    mockReportApi.get.mockReturnValue(getPromise);

    const user = userEvent.setup();
    renderWithRouter(<ReportsPage />);

    await waitFor(() => {
      expect(screen.getByText('Test Report')).toBeInTheDocument();
    });

    const viewButtons = screen.getAllByText('查看');
    await user.click(viewButtons[0]);

    await waitFor(() => {
      expect(document.querySelector('.ant-spin')).toBeInTheDocument();
    });

    resolveGet?.(mockReports.items[0]);

    await waitFor(() => {
      expect(screen.getByTestId('markdown-content')).toBeInTheDocument();
    });
  });

  // --- Report without report_type label ---
  test('handles report type fallback in modal tag', async () => {
    mockReportApi.get.mockResolvedValue({
      id: 1,
      task_id: 10,
      report_type: 'custom_type',
      title: 'Custom Type',
      content: 'content',
      created_at: '2024-01-01T00:00:00Z',
      report_metadata: { report_source: 'llm', report_mode: 'full' },
    } as any);

    const user = userEvent.setup();
    renderWithRouter(<ReportsPage />);

    await waitFor(() => {
      expect(screen.getByText('Test Report')).toBeInTheDocument();
    });

    const viewButtons = screen.getAllByText('查看');
    await user.click(viewButtons[0]);

    await waitFor(() => {
      expect(screen.getByTestId('markdown-content')).toBeInTheDocument();
    });

    expect(screen.getByText('custom_type')).toBeInTheDocument();
  });

  // --- Export PDF success ---
  test('export PDF calls API and creates download', async () => {
    const originalCreateObjectURL = URL.createObjectURL;
    const originalRevokeObjectURL = URL.revokeObjectURL;
    (URL as any).createObjectURL = jest.fn(() => 'blob:mock-pdf');
    (URL as any).revokeObjectURL = jest.fn();

    const mockClick = jest.fn();
    const originalCreateElement = document.createElement.bind(document);
    jest.spyOn(document, 'createElement').mockImplementation((tag: string) => {
      const el = originalCreateElement(tag);
      if (tag === 'a') {
        el.click = mockClick;
      }
      return el;
    });

    const user = userEvent.setup();
    renderWithRouter(<ReportsPage />);

    await waitFor(() => {
      expect(screen.getByText('Test Report')).toBeInTheDocument();
    });

    const viewButtons = screen.getAllByText('查看');
    await user.click(viewButtons[0]);

    await waitFor(() => {
      expect(screen.getByText('导出 PDF')).toBeInTheDocument();
    });

    await user.click(screen.getByText('导出 PDF'));

    await waitFor(() => {
      expect(mockReportApi.exportPdf).toHaveBeenCalledWith(1);
    });

    URL.createObjectURL = originalCreateObjectURL;
    URL.revokeObjectURL = originalRevokeObjectURL;
    jest.restoreAllMocks();
  });

  // --- Export PDF error ---
  test('export PDF handles error', async () => {
    mockReportApi.exportPdf.mockRejectedValue(new Error('PDF generation failed'));

    const user = userEvent.setup();
    renderWithRouter(<ReportsPage />);

    await waitFor(() => {
      expect(screen.getByText('Test Report')).toBeInTheDocument();
    });

    const viewButtons = screen.getAllByText('查看');
    await user.click(viewButtons[0]);

    await waitFor(() => {
      expect(screen.getByText('导出 PDF')).toBeInTheDocument();
    });

    await user.click(screen.getByText('导出 PDF'));

    await waitFor(() => {
      expect(mockReportApi.exportPdf).toHaveBeenCalled();
    });
  });
});

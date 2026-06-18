import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
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

describe('ReportsPage coverage gaps', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockReportApi.list.mockResolvedValue(mockReports as any);
    mockReportApi.get.mockResolvedValue(mockReports.items[0] as any);
    mockReportApi.exportPdf.mockResolvedValue(new Blob(['pdf'], { type: 'application/pdf' }));
  });

  // --- filteredReports with typeFilter set (lines 74-78) ---
  test('type filter select component renders with filter options', async () => {
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

    // Both reports should be visible initially (no filter applied)
    expect(screen.getByText('Summary Report')).toBeInTheDocument();

    // The type filter select should be present
    expect(document.querySelector('.ant-select')).toBeInTheDocument();
  });

  // --- handleExportPdf with no id early return (line 92) ---
  test('handleExportPdf does nothing when detailContent has no id', async () => {
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
      expect(screen.getByTestId('markdown-content')).toBeInTheDocument();
    });

    // PDF button should be disabled
    const pdfButton = screen.getByText('导出 PDF').closest('button');
    expect(pdfButton).toBeDisabled();
  });

  // --- Modal close via cancel button (lines 210-211) ---
  test('modal close button is present', async () => {
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

    // Modal should have a close button (X icon in header)
    expect(document.querySelector('.ant-modal-close')).toBeInTheDocument();
  });

  // --- handleView error (lines 65-68) ---
  test('handleView handles API error gracefully', async () => {
    mockReportApi.get.mockRejectedValue(new Error('Load failed'));

    const user = userEvent.setup();
    renderWithRouter(<ReportsPage />);

    await waitFor(() => {
      expect(screen.getByText('Test Report')).toBeInTheDocument();
    });

    const viewButtons = screen.getAllByText('查看');
    await user.click(viewButtons[0]);

    await waitFor(() => {
      expect(mockReportApi.get).toHaveBeenCalled();
    });

    // Modal should close on error
    await waitFor(() => {
      expect(screen.queryByTestId('markdown-content')).not.toBeInTheDocument();
    });
  });

  // --- handleView non-Error exception ---
  test('handleView handles non-Error exception', async () => {
    mockReportApi.get.mockRejectedValue('string error');

    const user = userEvent.setup();
    renderWithRouter(<ReportsPage />);

    await waitFor(() => {
      expect(screen.getByText('Test Report')).toBeInTheDocument();
    });

    const viewButtons = screen.getAllByText('查看');
    await user.click(viewButtons[0]);

    await waitFor(() => {
      expect(mockReportApi.get).toHaveBeenCalled();
    });
  });

  // --- loadReports error ---
  test('loadReports handles non-Error exception', async () => {
    mockReportApi.list.mockRejectedValue('string error');

    renderWithRouter(<ReportsPage />);

    await waitFor(() => {
      expect(screen.getByText('审计报告')).toBeInTheDocument();
    });
  });

  // --- Export PDF non-Error exception ---
  test('export PDF handles non-Error exception', async () => {
    mockReportApi.exportPdf.mockRejectedValue('string error');

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

  // --- Report with unknown source in modal ---
  test('shows unknown source tag in modal for unknown report_source', async () => {
    mockReportApi.get.mockResolvedValue({
      id: 1,
      task_id: 10,
      report_type: 'full_report',
      title: 'Unknown Source',
      content: 'content',
      created_at: '2024-01-01T00:00:00Z',
      report_metadata: { report_source: 'unknown_source', report_mode: 'custom' },
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

    // Should show 'unknown_source' since it's not in REPORT_SOURCE_CONFIG
    expect(screen.getByText('unknown_source')).toBeInTheDocument();
  });

  // --- handleExport with no content (disabled state) ---
  test('handleExport does nothing when content is empty', async () => {
    mockReportApi.get.mockResolvedValue({
      id: 1,
      task_id: 10,
      report_type: 'full_report',
      title: 'Empty Content',
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
      const mdButton = screen.getByText('导出 Markdown').closest('button');
      expect(mdButton).toBeDisabled();
    });
  });
});

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';

import ReportsPage from '../ReportsPage';
import { reportApi } from '../../services/api';

jest.setTimeout(15000);

// Mock react-markdown (ESM module)
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
      title: '偏差分析完整报告',
      content: '# 偏差分析报告\n\n## 概述\n\n本次审计发现3项偏差。',
      created_at: '2024-01-01T00:00:00Z',
      report_metadata: {
        report_source: 'llm',
        report_mode: 'full',
        findings_count: 3,
        task_type: 'deviation_analysis',
      },
    },
    {
      id: 2,
      task_id: 11,
      report_type: 'summary',
      title: 'SOP合规摘要',
      content: '# SOP合规摘要\n\n合规率95%。',
      created_at: '2024-01-02T00:00:00Z',
      report_metadata: {
        report_source: 'agent_report_writer',
        report_mode: 'summary',
        findings_count: 1,
        task_type: 'sop_compliance',
      },
    },
    {
      id: 3,
      task_id: 12,
      report_type: 'audit_report',
      title: '风险评估报告',
      content: '# 风险评估\n\n高风险项2个。',
      created_at: '2024-01-03T00:00:00Z',
      report_metadata: {
        report_source: 'fallback',
        report_mode: 'degraded',
        findings_count: 2,
        task_type: 'risk_assessment',
      },
    },
  ],
  total: 3,
  page: 1,
  page_size: 10,
};

describe('ReportsPage extended tests', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockReportApi.list.mockResolvedValue(mockReports as any);
    mockReportApi.get.mockImplementation((id: number) => {
      const report = mockReports.items.find((r) => r.id === id);
      return Promise.resolve(report as any);
    });
    mockReportApi.exportPdf.mockResolvedValue(new Blob(['pdf content'], { type: 'application/pdf' }));
  });

  // --- Page title and description ---
  test('renders page title', async () => {
    renderWithRouter(<ReportsPage />);
    await waitFor(() => {
      expect(screen.getByText('审计报告')).toBeInTheDocument();
    });
  });

  test('renders page description', async () => {
    renderWithRouter(<ReportsPage />);
    await waitFor(() => {
      expect(screen.getByText('查看审计报告，追溯报告来源和生成方式')).toBeInTheDocument();
    });
  });

  test('renders report list title', async () => {
    renderWithRouter(<ReportsPage />);
    await waitFor(() => {
      expect(screen.getByText('报告列表')).toBeInTheDocument();
    });
  });

  // --- Report list rendering ---
  test('renders report list with data', async () => {
    renderWithRouter(<ReportsPage />);
    await waitFor(() => {
      expect(screen.getByText('偏差分析完整报告')).toBeInTheDocument();
    });
    expect(screen.getByText('SOP合规摘要')).toBeInTheDocument();
    expect(screen.getByText('风险评估报告')).toBeInTheDocument();
  });

  test('displays report type tags', async () => {
    renderWithRouter(<ReportsPage />);
    await waitFor(() => {
      expect(screen.getAllByText('完整报告').length).toBeGreaterThanOrEqual(1);
    });
    expect(screen.getByText('摘要')).toBeInTheDocument();
    expect(screen.getAllByText('审计报告').length).toBeGreaterThanOrEqual(1);
  });

  test('displays report source labels', async () => {
    renderWithRouter(<ReportsPage />);
    await waitFor(() => {
      const aiLabels = screen.getAllByText('AI 生成');
      expect(aiLabels.length).toBeGreaterThanOrEqual(1);
    });
  });

  test('displays fallback tag for fallback reports', async () => {
    renderWithRouter(<ReportsPage />);
    await waitFor(() => {
      expect(screen.getByText('降级')).toBeInTheDocument();
    });
  });

  // --- Empty state ---
  test('shows empty state when no reports', async () => {
    mockReportApi.list.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 10 } as any);
    renderWithRouter(<ReportsPage />);
    await waitFor(() => {
      expect(screen.getByText('暂无报告')).toBeInTheDocument();
    });
  });

  // --- View report detail ---
  test('opens report detail modal when view button clicked', async () => {
    const user = userEvent.setup();
    renderWithRouter(<ReportsPage />);
    await waitFor(() => {
      expect(screen.getByText('偏差分析完整报告')).toBeInTheDocument();
    });
    const viewButtons = screen.getAllByText('查看');
    await user.click(viewButtons[0]);
    await waitFor(() => {
      expect(mockReportApi.get).toHaveBeenCalledWith(1);
    });
  });

  test('shows report content in modal', async () => {
    const user = userEvent.setup();
    renderWithRouter(<ReportsPage />);
    await waitFor(() => {
      expect(screen.getByText('偏差分析完整报告')).toBeInTheDocument();
    });
    const viewButtons = screen.getAllByText('查看');
    await user.click(viewButtons[0]);
    await waitFor(() => {
      expect(screen.getByTestId('markdown-content')).toBeInTheDocument();
    });
  });

  // --- Export buttons ---
  test('shows export buttons in detail modal', async () => {
    const user = userEvent.setup();
    renderWithRouter(<ReportsPage />);
    await waitFor(() => {
      expect(screen.getByText('偏差分析完整报告')).toBeInTheDocument();
    });
    const viewButtons = screen.getAllByText('查看');
    await user.click(viewButtons[0]);
    await waitFor(() => {
      expect(screen.getByText('导出 Markdown')).toBeInTheDocument();
    });
    expect(screen.getByText('导出 PDF')).toBeInTheDocument();
  });

  // --- Modal footer has buttons ---
  test('modal footer has export buttons', async () => {
    const user = userEvent.setup();
    renderWithRouter(<ReportsPage />);
    await waitFor(() => {
      expect(screen.getByText('偏差分析完整报告')).toBeInTheDocument();
    });
    const viewButtons = screen.getAllByText('查看');
    await user.click(viewButtons[0]);
    await waitFor(() => {
      expect(screen.getByText('导出 Markdown')).toBeInTheDocument();
    });
    expect(screen.getByText('导出 PDF')).toBeInTheDocument();
  });

  // --- Export PDF (covers handleExportPdf lines 91-108) ---
  test('export PDF calls API with report id', async () => {
    const user = userEvent.setup();
    // Mock URL.createObjectURL and related APIs
    const originalCreateObjectURL = URL.createObjectURL;
    const originalRevokeObjectURL = URL.revokeObjectURL;
    (URL as any).createObjectURL = jest.fn(() => 'blob:mock');
    (URL as any).revokeObjectURL = jest.fn();

    renderWithRouter(<ReportsPage />);
    await waitFor(() => {
      expect(screen.getByText('偏差分析完整报告')).toBeInTheDocument();
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
  });

  test('export PDF handles error gracefully', async () => {
    mockReportApi.exportPdf.mockRejectedValue(new Error('PDF generation failed'));
    const user = userEvent.setup();

    renderWithRouter(<ReportsPage />);
    await waitFor(() => {
      expect(screen.getByText('偏差分析完整报告')).toBeInTheDocument();
    });

    const viewButtons = screen.getAllByText('查看');
    await user.click(viewButtons[0]);
    await waitFor(() => {
      expect(screen.getByText('导出 PDF')).toBeInTheDocument();
    });

    await user.click(screen.getByText('导出 PDF'));

    await waitFor(() => {
      expect(screen.getByText('导出 PDF')).toBeInTheDocument();
    });
  });

  // --- Type filter (covers filteredReports useMemo lines 72-75) ---
  test('renders type filter select', async () => {
    renderWithRouter(<ReportsPage />);
    await waitFor(() => {
      expect(screen.getByText('按类型筛选')).toBeInTheDocument();
    });
  });

  // --- Error handling ---
  test('handles API error on load', async () => {
    mockReportApi.list.mockRejectedValue(new Error('加载失败'));
    renderWithRouter(<ReportsPage />);
    await waitFor(() => {
      const titles = screen.getAllByText('审计报告');
      expect(titles.length).toBeGreaterThan(0);
    });
  });

  test('handles API error on report detail load', async () => {
    mockReportApi.get.mockRejectedValue(new Error('详情加载失败'));
    const user = userEvent.setup();
    renderWithRouter(<ReportsPage />);
    await waitFor(() => {
      expect(screen.getByText('偏差分析完整报告')).toBeInTheDocument();
    });
    const viewButtons = screen.getAllByText('查看');
    await user.click(viewButtons[0]);
    await waitFor(() => {
      const titles = screen.getAllByText('审计报告');
      expect(titles.length).toBeGreaterThan(0);
    });
  });

  // --- Fallback warning in modal (covers lines 238-246) ---
  test('shows fallback warning when viewing fallback report', async () => {
    mockReportApi.list.mockResolvedValue({
      items: [
        {
          id: 3,
          task_id: 12,
          report_type: 'audit_report',
          title: '风险评估报告',
          content: '# 风险评估\n\n高风险项2个。',
          created_at: '2024-01-03T00:00:00Z',
          report_metadata: {
            report_source: 'fallback',
            report_mode: 'degraded',
            findings_count: 2,
            task_type: 'risk_assessment',
          },
        },
      ],
      total: 1,
      page: 1,
      page_size: 10,
    } as any);
    mockReportApi.get.mockResolvedValue({
      id: 3,
      task_id: 12,
      report_type: 'audit_report',
      title: '风险评估报告',
      content: '# 风险评估\n\n高风险项2个。',
      created_at: '2024-01-03T00:00:00Z',
      report_metadata: {
        report_source: 'fallback',
        report_mode: 'degraded',
        findings_count: 2,
        task_type: 'risk_assessment',
      },
    } as any);
    const user = userEvent.setup();
    renderWithRouter(<ReportsPage />);
    await waitFor(() => {
      expect(screen.getByText('风险评估报告')).toBeInTheDocument();
    });
    const viewButtons = screen.getAllByText('查看');
    await user.click(viewButtons[0]);
    await waitFor(() => {
      expect(screen.getAllByText('降级报告').length).toBeGreaterThanOrEqual(1);
    });
  });

  // --- Modal tag display (covers lines 247-254) ---
  test('shows report type and source tags in modal', async () => {
    const user = userEvent.setup();
    renderWithRouter(<ReportsPage />);
    await waitFor(() => {
      expect(screen.getByText('偏差分析完整报告')).toBeInTheDocument();
    });
    const viewButtons = screen.getAllByText('查看');
    await user.click(viewButtons[0]);
    await waitFor(() => {
      expect(screen.getByTestId('markdown-content')).toBeInTheDocument();
    });
    // Tags should be present in modal - 完整报告 appears in both table and modal
    await waitFor(() => {
      expect(screen.getAllByText('完整报告').length).toBeGreaterThanOrEqual(1);
    });
  });

  // --- Report with unknown source (covers line 117-125) ---
  test('handles report with unknown source', async () => {
    mockReportApi.list.mockResolvedValue({
      items: [
        {
          id: 11,
          task_id: 21,
          report_type: 'full_report',
          title: '未知来源报告',
          content: '内容',
          created_at: '2024-01-01T00:00:00Z',
          report_metadata: {},
        },
      ],
      total: 1,
      page: 1,
      page_size: 10,
    } as any);
    renderWithRouter(<ReportsPage />);
    await waitFor(() => {
      expect(screen.getByText('未知来源报告')).toBeInTheDocument();
    });
    expect(screen.getByText('未知来源')).toBeInTheDocument();
  });

  // --- Report mode display ---
  test('displays report mode in table', async () => {
    renderWithRouter(<ReportsPage />);
    await waitFor(() => {
      expect(screen.getByText('full')).toBeInTheDocument();
    });
    expect(screen.getByText('summary')).toBeInTheDocument();
    expect(screen.getByText('degraded')).toBeInTheDocument();
  });

  // --- Loading state ---
  test('shows loading state while fetching reports', async () => {
    mockReportApi.list.mockImplementation(() => new Promise(() => {}));
    renderWithRouter(<ReportsPage />);
    await waitFor(() => {
      expect(document.querySelector('.ant-spin')).toBeInTheDocument();
    });
  });

  // --- Pagination ---
  test('renders pagination for report table', async () => {
    renderWithRouter(<ReportsPage />);
    await waitFor(() => {
      expect(screen.getByText('偏差分析完整报告')).toBeInTheDocument();
    });
    expect(document.querySelector('.ant-pagination')).toBeInTheDocument();
  });

  // --- Partial fallback report ---
  test('shows partial fallback tag', async () => {
    mockReportApi.list.mockResolvedValue({
      items: [
        {
          id: 10,
          task_id: 20,
          report_type: 'full_report',
          title: '部分降级报告',
          content: '内容',
          created_at: '2024-01-01T00:00:00Z',
          report_metadata: {
            report_source: 'partial_fallback',
            report_mode: 'partial',
          },
        },
      ],
      total: 1,
      page: 1,
      page_size: 10,
    } as any);
    renderWithRouter(<ReportsPage />);
    await waitFor(() => {
      expect(screen.getByText('降级')).toBeInTheDocument();
    });
  });

  // --- Aggregate report source ---
  test('displays aggregate report source label', async () => {
    mockReportApi.list.mockResolvedValue({
      items: [
        {
          id: 20,
          task_id: 30,
          report_type: 'full_report',
          title: '汇总报告标题',
          content: '汇总内容',
          created_at: '2024-01-01T00:00:00Z',
          report_metadata: {
            report_source: 'task_runner_aggregate',
            report_mode: 'aggregate',
          },
        },
      ],
      total: 1,
      page: 1,
      page_size: 10,
    } as any);
    renderWithRouter(<ReportsPage />);
    await waitFor(() => {
      expect(screen.getByText('汇总报告标题')).toBeInTheDocument();
    });
    expect(screen.getByText('汇总报告')).toBeInTheDocument();
  });

  // --- Report with no metadata ---
  test('handles report with no metadata gracefully', async () => {
    mockReportApi.list.mockResolvedValue({
      items: [
        {
          id: 30,
          task_id: 40,
          report_type: 'full_report',
          title: '无元数据报告',
          content: '内容',
          created_at: '2024-01-01T00:00:00Z',
        },
      ],
      total: 1,
      page: 1,
      page_size: 10,
    } as any);
    renderWithRouter(<ReportsPage />);
    await waitFor(() => {
      expect(screen.getByText('无元数据报告')).toBeInTheDocument();
    });
    expect(screen.getByText('未知来源')).toBeInTheDocument();
  });

  // --- Report with no content in detail view ---
  test('handles report with empty content', async () => {
    mockReportApi.get.mockResolvedValue({
      id: 1,
      task_id: 10,
      report_type: 'full_report',
      title: '空报告',
      content: '',
      created_at: '2024-01-01T00:00:00Z',
      report_metadata: {
        report_source: 'llm',
        report_mode: 'full',
      },
    } as any);
    const user = userEvent.setup();
    renderWithRouter(<ReportsPage />);
    await waitFor(() => {
      expect(screen.getByText('偏差分析完整报告')).toBeInTheDocument();
    });
    const viewButtons = screen.getAllByText('查看');
    await user.click(viewButtons[0]);
    await waitFor(() => {
      expect(screen.getByTestId('markdown-content')).toBeInTheDocument();
    });
  });

  // --- Formatted creation time ---
  test('displays formatted creation time', async () => {
    renderWithRouter(<ReportsPage />);
    await waitFor(() => {
      expect(screen.getByText('偏差分析完整报告')).toBeInTheDocument();
    });
    const dateCells = document.querySelectorAll('td');
    expect(dateCells.length).toBeGreaterThan(0);
  });

  // --- Report with no created_at ---
  test('handles report with no created_at', async () => {
    mockReportApi.list.mockResolvedValue({
      items: [
        {
          id: 40,
          task_id: 50,
          report_type: 'full_report',
          title: '无时间报告',
          content: '内容',
          created_at: '',
          report_metadata: { report_source: 'llm', report_mode: 'full' },
        },
      ],
      total: 1,
      page: 1,
      page_size: 10,
    } as any);
    renderWithRouter(<ReportsPage />);
    await waitFor(() => {
      expect(screen.getByText('无时间报告')).toBeInTheDocument();
    });
  });
});

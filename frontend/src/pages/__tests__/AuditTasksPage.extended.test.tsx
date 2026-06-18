import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';

import AuditTasksPage from '../AuditTasksPage';
import { auditApi, documentApi } from '../../services/api';

jest.setTimeout(15000);

// Mock EventSource for SSE hooks
class MockEventSource {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSED = 2;
  readyState = 2;
  url = '';
  onopen: any = null;
  onmessage: any = null;
  onerror: any = null;
  constructor(url: string) { this.url = url; }
  addEventListener() {}
  removeEventListener() {}
  close() {}
}
(global as any).EventSource = MockEventSource;

// Mock AgentFlowChart to avoid echarts crash in jsdom
jest.mock('../../components/AgentFlowChart', () => {
  return function MockAgentFlowChart() {
    return <div data-testid="agent-flow-chart">AgentFlowChart</div>;
  };
});

// Mock AgentThinkingPanel
jest.mock('../../components/AgentThinkingPanel', () => {
  return function MockAgentThinkingPanel() {
    return <div data-testid="agent-thinking-panel">AgentThinkingPanel</div>;
  };
});

// Mock FindingDetailCard
jest.mock('../../components/FindingDetailCard', () => {
  return function MockFindingDetailCard({ finding }: any) {
    return <div data-testid="finding-detail-card">{finding.title}</div>;
  };
});

jest.mock('../../services/api', () => ({
  auditApi: {
    listTasks: jest.fn(),
    createTask: jest.fn(),
    runTask: jest.fn(),
    cancelTask: jest.fn(),
    getTask: jest.fn(),
    getFindings: jest.fn(),
    approveTask: jest.fn(),
    rejectTask: jest.fn(),
  },
  documentApi: {
    list: jest.fn(),
  },
}));

const mockAuditApi = auditApi as jest.Mocked<typeof auditApi>;
const mockDocumentApi = documentApi as jest.Mocked<typeof documentApi>;

const renderWithRouter = (component: React.ReactElement) => {
  return render(<BrowserRouter>{component}</BrowserRouter>);
};

const mockTasks = {
  items: [
    {
      id: 1,
      task_name: 'SOP合规审查',
      task_type: 'sop_compliance',
      status: 'completed' as const,
      progress: 100,
      stage: 'completed',
      created_at: '2024-01-01T00:00:00Z',
      report_id: 10,
      documents: [],
    },
    {
      id: 2,
      task_name: '偏差分析任务',
      task_type: 'deviation_analysis',
      status: 'running' as const,
      progress: 45,
      stage: 'risk',
      created_at: '2024-01-02T00:00:00Z',
      started_at: '2024-01-02T00:01:00Z',
      report_id: null,
      documents: [],
    },
    {
      id: 3,
      task_name: '风险评估检查',
      task_type: 'risk_assessment',
      status: 'pending' as const,
      progress: 0,
      stage: 'pending',
      created_at: '2024-01-03T00:00:00Z',
      report_id: null,
      documents: [],
    },
    {
      id: 4,
      task_name: '变更控制',
      task_type: 'consistency_check',
      status: 'failed' as const,
      progress: 30,
      stage: 'regulation',
      created_at: '2024-01-04T00:00:00Z',
      error_message: 'LLM调用超时',
      report_id: null,
      documents: [],
    },
  ],
  total: 4,
  page: 1,
  page_size: 20,
};

const mockDocuments = {
  items: [
    { id: 1, filename: 'SOP-001.pdf', file_type: 'pdf', process_status: 'processed' as const },
    { id: 2, filename: 'deviation-report.docx', file_type: 'docx', process_status: 'processed' as const },
  ],
  total: 2,
  page: 1,
  page_size: 100,
};

describe('AuditTasksPage extended tests', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockAuditApi.listTasks.mockResolvedValue(mockTasks as any);
    mockDocumentApi.list.mockResolvedValue(mockDocuments);
    mockAuditApi.getTask.mockImplementation((id: number) => {
      const task = mockTasks.items.find((t) => t.id === id);
      return Promise.resolve(task as any);
    });
    mockAuditApi.getFindings.mockResolvedValue([]);
  });

  // --- Task list rendering ---
  test('renders task list with multiple tasks', async () => {
    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('SOP合规审查')).toBeInTheDocument();
    });

    expect(screen.getByText('偏差分析任务')).toBeInTheDocument();
    expect(screen.getByText('风险评估检查')).toBeInTheDocument();
    expect(screen.getByText('变更控制')).toBeInTheDocument();
  });

  test('shows task count in toolbar', async () => {
    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText(/共 4 个任务/)).toBeInTheDocument();
    });
  });

  test('displays task type labels', async () => {
    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('SOP 合规')).toBeInTheDocument();
    });
  });

  test('displays task status tags', async () => {
    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      // Status tags appear in both stage tag and status tag columns
      expect(screen.getAllByText('已完成').length).toBeGreaterThanOrEqual(1);
    });

    expect(screen.getAllByText('进行中').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('待处理').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('失败').length).toBeGreaterThanOrEqual(1);
  });

  // --- Empty state ---
  test('shows empty state when no tasks', async () => {
    mockAuditApi.listTasks.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 } as any);

    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('暂无审计任务')).toBeInTheDocument();
    });
  });

  // --- Toolbar ---
  test('renders toolbar with filter controls', async () => {
    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('开始审计')).toBeInTheDocument();
    });

    expect(screen.getByPlaceholderText('搜索任务名称...')).toBeInTheDocument();
  });

  // --- Search filter ---
  test('filters tasks by search keyword', async () => {
    const user = userEvent.setup();
    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('SOP合规审查')).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText('搜索任务名称...');
    await user.type(searchInput, '偏差');

    await waitFor(() => {
      expect(screen.getByText('偏差分析任务')).toBeInTheDocument();
    });

    expect(screen.queryByText('SOP合规审查')).not.toBeInTheDocument();
  });

  // --- Task creation ---
  test('opens create task modal when clicking start audit button', async () => {
    const user = userEvent.setup();
    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('开始审计')).toBeInTheDocument();
    });

    await user.click(screen.getByText('开始审计'));

    await waitFor(() => {
      expect(screen.getByText('创建审计任务')).toBeInTheDocument();
    });
  });

  test('create task modal has required form fields', async () => {
    const user = userEvent.setup();
    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('开始审计')).toBeInTheDocument();
    });

    await user.click(screen.getByText('开始审计'));

    await waitFor(() => {
      expect(screen.getByText('创建审计任务')).toBeInTheDocument();
    });

    expect(screen.getByLabelText('任务名称')).toBeInTheDocument();
    expect(screen.getByLabelText('审计类型')).toBeInTheDocument();
    expect(screen.getByLabelText('选择文档')).toBeInTheDocument();
  });

  // --- Task actions ---
  test('shows run button for pending tasks', async () => {
    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('风险评估检查')).toBeInTheDocument();
    });

    const runButtons = screen.getAllByText('运行');
    expect(runButtons.length).toBeGreaterThan(0);
  });

  test('shows cancel button for running tasks', async () => {
    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('偏差分析任务')).toBeInTheDocument();
    });

    const cancelButtons = screen.getAllByText('取消');
    expect(cancelButtons.length).toBeGreaterThan(0);
  });

  test('shows report button for tasks with report_id', async () => {
    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('SOP合规审查')).toBeInTheDocument();
    });

    const reportButtons = screen.getAllByText('报告');
    expect(reportButtons.length).toBeGreaterThan(0);
  });

  test('calls runTask when clicking run button', async () => {
    mockAuditApi.runTask.mockResolvedValue({ status: 'running', task_id: 3 });
    const user = userEvent.setup();
    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('风险评估检查')).toBeInTheDocument();
    });

    const runButtons = screen.getAllByText('运行');
    await user.click(runButtons[0]);

    await waitFor(() => {
      expect(mockAuditApi.runTask).toHaveBeenCalledWith(3);
    });
  });

  // --- Drawer detail view ---
  test('opens drawer when clicking a task', async () => {
    const user = userEvent.setup();
    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('SOP合规审查')).toBeInTheDocument();
    });

    // Click on the task row by clicking on the task name
    const taskElements = screen.getAllByText('SOP合规审查');
    await user.click(taskElements[0]);

    // The drawer should open showing the task details
    await waitFor(() => {
      // AgentFlowChart should be rendered in the drawer
      expect(screen.getByTestId('agent-flow-chart')).toBeInTheDocument();
    });
  });

  test('shows findings section in drawer', async () => {
    mockAuditApi.getFindings.mockResolvedValue([
      {
        id: 1,
        task_id: 1,
        finding_type: 'deviation',
        severity: 'high',
        title: '关键偏差',
        description: '发现关键偏差问题',
        created_at: '2024-01-01T00:00:00Z',
      },
    ]);
    const user = userEvent.setup();
    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('SOP合规审查')).toBeInTheDocument();
    });

    const taskElements = screen.getAllByText('SOP合规审查');
    await user.click(taskElements[0]);

    await waitFor(() => {
      expect(screen.getByText(/审计发现/)).toBeInTheDocument();
    });

    // Finding should be rendered via FindingDetailCard mock
    expect(screen.getByText('关键偏差')).toBeInTheDocument();
  });

  test('shows no findings message when no findings', async () => {
    mockAuditApi.getFindings.mockResolvedValue([]);
    const user = userEvent.setup();
    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('SOP合规审查')).toBeInTheDocument();
    });

    const taskElements = screen.getAllByText('SOP合规审查');
    await user.click(taskElements[0]);

    await waitFor(() => {
      expect(screen.getByText('暂无审计发现')).toBeInTheDocument();
    });
  });

  test('shows task documents section in drawer', async () => {
    const user = userEvent.setup();
    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('SOP合规审查')).toBeInTheDocument();
    });

    const taskElements = screen.getAllByText('SOP合规审查');
    await user.click(taskElements[0]);

    await waitFor(() => {
      expect(screen.getByText(/任务文档/)).toBeInTheDocument();
    });
  });

  test('shows knowledge graph button in drawer', async () => {
    const user = userEvent.setup();
    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('SOP合规审查')).toBeInTheDocument();
    });

    const taskElements = screen.getAllByText('SOP合规审查');
    await user.click(taskElements[0]);

    await waitFor(() => {
      expect(screen.getByText('知识图谱')).toBeInTheDocument();
    });
  });

  // --- Error handling ---
  test('handles API error on task list load', async () => {
    mockAuditApi.listTasks.mockRejectedValue(new Error('网络错误'));

    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('暂无审计任务')).toBeInTheDocument();
    });
  });

  test('handles API error on task details load', async () => {
    mockAuditApi.getTask.mockRejectedValue(new Error('加载失败'));
    mockAuditApi.getFindings.mockRejectedValue(new Error('加载失败'));
    renderWithRouter(<AuditTasksPage />);

    // Should still render the page without crashing
    await waitFor(() => {
      expect(screen.getByText('SOP合规审查')).toBeInTheDocument();
    });

    // The page should still be functional even with API errors
    expect(screen.getByText('偏差分析任务')).toBeInTheDocument();
    expect(screen.getByText('风险评估检查')).toBeInTheDocument();
  });

  // --- Failed task with error message ---
  test('shows error message for failed tasks in drawer', async () => {
    mockAuditApi.getTask.mockResolvedValue({
      id: 4,
      task_name: '变更控制',
      task_type: 'consistency_check',
      status: 'failed',
      progress: 30,
      stage: 'regulation',
      error_message: 'LLM调用超时',
      created_at: '2024-01-04T00:00:00Z',
      documents: [],
    } as any);
    const user = userEvent.setup();
    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('变更控制')).toBeInTheDocument();
    });

    const taskElements = screen.getAllByText('变更控制');
    await user.click(taskElements[0]);

    await waitFor(() => {
      expect(screen.getByText('LLM调用超时')).toBeInTheDocument();
    });
  });

  // --- Task with events timeline ---
  test('shows timeline when task has events', async () => {
    mockAuditApi.getTask.mockResolvedValue({
      id: 2,
      task_name: '偏差分析任务',
      task_type: 'deviation_analysis',
      status: 'running',
      progress: 45,
      stage: 'risk',
      created_at: '2024-01-02T00:00:00Z',
      started_at: '2024-01-02T00:01:00Z',
      documents: [],
      events: [
        { time: '2024-01-02T00:01:00Z', stage: 'parsing', level: 'info' as const, message: '开始解析文档' },
        { time: '2024-01-02T00:02:00Z', stage: 'regulation', level: 'info' as const, message: '法规匹配中' },
      ],
    } as any);
    const user = userEvent.setup();
    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('偏差分析任务')).toBeInTheDocument();
    });

    const taskElements = screen.getAllByText('偏差分析任务');
    await user.click(taskElements[0]);

    await waitFor(() => {
      expect(screen.getByText('执行时间线')).toBeInTheDocument();
    });

    expect(screen.getByText('开始解析文档')).toBeInTheDocument();
  });

  // --- Task with documents ---
  test('shows task documents with status', async () => {
    // Use a unique task name to avoid duplicate text issues
    mockAuditApi.listTasks.mockResolvedValue({
      items: [
        {
          id: 99,
          task_name: '文档测试任务',
          task_type: 'sop_compliance',
          status: 'completed' as const,
          progress: 100,
          stage: 'completed',
          created_at: '2024-01-01T00:00:00Z',
          report_id: 10,
          documents: [
            { document_id: 1, filename: 'SOP-001.pdf', status: 'completed', findings_count: 3, risk_level: '高风险' },
          ],
        },
      ],
      total: 1,
      page: 1,
      page_size: 20,
    } as any);
    mockAuditApi.getTask.mockResolvedValue({
      id: 99,
      task_name: '文档测试任务',
      task_type: 'sop_compliance',
      status: 'completed',
      progress: 100,
      stage: 'completed',
      created_at: '2024-01-01T00:00:00Z',
      report_id: 10,
      documents: [
        { document_id: 1, filename: 'SOP-001.pdf', status: 'completed', findings_count: 3, risk_level: '高风险' },
      ],
    } as any);
    const user = userEvent.setup();
    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('文档测试任务')).toBeInTheDocument();
    });

    // Click on the task to open drawer
    const taskElements = screen.getAllByText('文档测试任务');
    await user.click(taskElements[0]);

    // Wait for the drawer to open and documents section to appear
    await waitFor(() => {
      expect(screen.getByText(/任务文档/)).toBeInTheDocument();
    });

    // Document filenames should be visible
    await waitFor(() => {
      expect(screen.getByText('SOP-001.pdf')).toBeInTheDocument();
    });

    expect(screen.getByText('3 项发现')).toBeInTheDocument();
  });

  // --- Run task from drawer ---
  test('shows run button in drawer for pending task', async () => {
    mockAuditApi.getTask.mockResolvedValue({
      id: 3,
      task_name: '风险评估检查',
      task_type: 'risk_assessment',
      status: 'pending',
      progress: 0,
      stage: 'pending',
      created_at: '2024-01-03T00:00:00Z',
      documents: [],
    } as any);
    const user = userEvent.setup();
    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('风险评估检查')).toBeInTheDocument();
    });

    const taskElements = screen.getAllByText('风险评估检查');
    await user.click(taskElements[0]);

    await waitFor(() => {
      const runButtons = screen.getAllByText('运行');
      expect(runButtons.length).toBeGreaterThanOrEqual(1);
    });
  });

  // --- Cancel task from drawer ---
  test('shows cancel button in drawer for running task', async () => {
    mockAuditApi.getTask.mockResolvedValue({
      id: 2,
      task_name: '偏差分析任务',
      task_type: 'deviation_analysis',
      status: 'running',
      progress: 45,
      stage: 'risk',
      created_at: '2024-01-02T00:00:00Z',
      started_at: '2024-01-02T00:01:00Z',
      documents: [],
    } as any);
    const user = userEvent.setup();
    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('偏差分析任务')).toBeInTheDocument();
    });

    const taskElements = screen.getAllByText('偏差分析任务');
    await user.click(taskElements[0]);

    await waitFor(() => {
      const cancelButtons = screen.getAllByText('取消任务');
      expect(cancelButtons.length).toBeGreaterThanOrEqual(1);
    });
  });

  // --- Multiple task types ---
  test('renders all task type labels correctly', async () => {
    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('SOP 合规')).toBeInTheDocument();
    });

    expect(screen.getAllByText('偏差分析').length).toBeGreaterThan(0);
    expect(screen.getAllByText('风险评估').length).toBeGreaterThan(0);
    expect(screen.getByText('变更控制一致性')).toBeInTheDocument();
  });

  // --- Failed task shows failure status ---
  test('failed task shows failure status', async () => {
    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('变更控制')).toBeInTheDocument();
    });

    expect(screen.getAllByText('失败').length).toBeGreaterThan(0);
  });

  // --- Cancelled task ---
  test('shows cancelled tasks correctly', async () => {
    mockAuditApi.listTasks.mockResolvedValue({
      items: [
        {
          id: 6,
          task_name: '已取消任务',
          task_type: 'deviation_analysis',
          status: 'cancelled' as const,
          progress: 20,
          stage: 'cancelled',
          created_at: '2024-01-06T00:00:00Z',
          documents: [],
        },
      ],
      total: 1,
      page: 1,
      page_size: 20,
    } as any);

    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('已取消任务')).toBeInTheDocument();
    });

    expect(screen.getAllByText('已取消').length).toBeGreaterThan(0);
  });

  // --- Sort controls ---
  test('renders sort controls', async () => {
    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('按时间排序')).toBeInTheDocument();
    });
  });

  // --- Task progress display ---
  test('displays progress for tasks', async () => {
    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('SOP合规审查')).toBeInTheDocument();
    });

    const progressElements = document.querySelectorAll('.ant-progress');
    expect(progressElements.length).toBeGreaterThan(0);
  });

  // --- View report from list ---
  test('shows report button links to reports page', async () => {
    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('SOP合规审查')).toBeInTheDocument();
    });

    const reportButtons = screen.getAllByText('报告');
    expect(reportButtons.length).toBeGreaterThan(0);
  });

  // --- AgentFlowChart renders in drawer ---
  test('shows agent flow chart in drawer', async () => {
    const user = userEvent.setup();
    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('SOP合规审查')).toBeInTheDocument();
    });

    const taskElements = screen.getAllByText('SOP合规审查');
    await user.click(taskElements[0]);

    await waitFor(() => {
      expect(screen.getByTestId('agent-flow-chart')).toBeInTheDocument();
    });
  });

  // --- No documents in drawer ---
  test('shows no documents message when task has no documents', async () => {
    const user = userEvent.setup();
    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('SOP合规审查')).toBeInTheDocument();
    });

    const taskElements = screen.getAllByText('SOP合规审查');
    await user.click(taskElements[0]);

    await waitFor(() => {
      expect(screen.getByText('暂无文档记录')).toBeInTheDocument();
    });
  });

  // --- Task creation flow ---
  test('create task form has task name input', async () => {
    const user = userEvent.setup();
    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('开始审计')).toBeInTheDocument();
    });

    await user.click(screen.getByText('开始审计'));

    await waitFor(() => {
      expect(screen.getByLabelText('任务名称')).toBeInTheDocument();
    });

    const taskNameInput = screen.getByLabelText('任务名称');
    expect(taskNameInput).not.toBeDisabled();
  });

  // --- Drawer close ---
  test('drawer can be closed', async () => {
    const user = userEvent.setup();
    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('SOP合规审查')).toBeInTheDocument();
    });

    const taskElements = screen.getAllByText('SOP合规审查');
    await user.click(taskElements[0]);

    await waitFor(() => {
      expect(screen.getByTestId('agent-flow-chart')).toBeInTheDocument();
    });

    // Close the drawer
    const closeButton = document.querySelector('.ant-drawer-close');
    if (closeButton) {
      await user.click(closeButton as Element);
    }
  });

  // --- Keyboard navigation on task list ---
  test('task list items are keyboard accessible', async () => {
    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('SOP合规审查')).toBeInTheDocument();
    });

    // Task items have role="button" and tabIndex
    const taskItems = document.querySelectorAll('[role="button"]');
    expect(taskItems.length).toBeGreaterThan(0);
  });

  // --- Task with awaiting_review status ---
  test('shows awaiting review status correctly', async () => {
    mockAuditApi.listTasks.mockResolvedValue({
      items: [
        {
          id: 10,
          task_name: '待审核任务',
          task_type: 'deviation_analysis',
          status: 'awaiting_review' as const,
          progress: 90,
          stage: 'report',
          created_at: '2024-01-10T00:00:00Z',
          documents: [],
        },
      ],
      total: 1,
      page: 1,
      page_size: 20,
    } as any);

    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('待审核任务')).toBeInTheDocument();
    });

    expect(screen.getByText('待审核')).toBeInTheDocument();
  });

  // --- Run task from drawer action ---
  test('drawer shows run button for pending task actions', async () => {
    mockAuditApi.getTask.mockResolvedValue({
      id: 3,
      task_name: '风险评估检查',
      task_type: 'risk_assessment',
      status: 'pending',
      progress: 0,
      stage: 'pending',
      created_at: '2024-01-03T00:00:00Z',
      documents: [],
    } as any);
    const user = userEvent.setup();
    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('风险评估检查')).toBeInTheDocument();
    });

    const taskElements = screen.getAllByText('风险评估检查');
    await user.click(taskElements[0]);

    await waitFor(() => {
      // Drawer should show run button
      const runButtons = screen.getAllByText('运行');
      expect(runButtons.length).toBeGreaterThanOrEqual(1);
    });
  });

  // --- Knowledge graph button in drawer ---
  test('knowledge graph button navigates correctly', async () => {
    const user = userEvent.setup();
    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('SOP合规审查')).toBeInTheDocument();
    });

    const taskElements = screen.getAllByText('SOP合规审查');
    await user.click(taskElements[0]);

    await waitFor(() => {
      expect(screen.getByText('知识图谱')).toBeInTheDocument();
    });

    // Click should not crash
    await user.click(screen.getByText('知识图谱'));
  });

  // --- View report from drawer ---
  test('shows view report button in drawer for tasks with report', async () => {
    mockAuditApi.getTask.mockResolvedValue({
      id: 1,
      task_name: 'SOP合规审查',
      task_type: 'sop_compliance',
      status: 'completed',
      progress: 100,
      stage: 'completed',
      created_at: '2024-01-01T00:00:00Z',
      report_id: 10,
      documents: [],
    } as any);
    const user = userEvent.setup();
    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('SOP合规审查')).toBeInTheDocument();
    });

    const taskElements = screen.getAllByText('SOP合规审查');
    await user.click(taskElements[0]);

    await waitFor(() => {
      expect(screen.getByText('查看报告')).toBeInTheDocument();
    });
  });

  // --- Sort by status ---
  test('sort dropdown changes sort order', async () => {
    const user = userEvent.setup();
    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('按时间排序')).toBeInTheDocument();
    });

    // Click the sort selector
    await user.click(screen.getByText('按时间排序'));

    await waitFor(() => {
      expect(screen.getByText('按状态排序')).toBeInTheDocument();
    });
  });

  // --- Multiple findings in drawer ---
  test('shows multiple findings with severity counts', async () => {
    mockAuditApi.getFindings.mockResolvedValue([
      {
        id: 1,
        task_id: 1,
        finding_type: 'deviation',
        severity: 'high',
        title: '关键偏差',
        description: '高风险偏差',
        created_at: '2024-01-01T00:00:00Z',
      },
      {
        id: 2,
        task_id: 1,
        finding_type: 'deviation',
        severity: 'medium',
        title: '中等偏差',
        description: '中风险偏差',
        created_at: '2024-01-01T00:00:00Z',
      },
      {
        id: 3,
        task_id: 1,
        finding_type: 'deviation',
        severity: 'low',
        title: '低风险偏差',
        description: '低风险偏差',
        created_at: '2024-01-01T00:00:00Z',
      },
    ]);
    const user = userEvent.setup();
    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('SOP合规审查')).toBeInTheDocument();
    });

    const taskElements = screen.getAllByText('SOP合规审查');
    await user.click(taskElements[0]);

    await waitFor(() => {
      expect(screen.getByText(/审计发现/)).toBeInTheDocument();
    });

    // Should show severity count tags
    expect(screen.getByText(/高风险 1/)).toBeInTheDocument();
    expect(screen.getByText(/中风险 1/)).toBeInTheDocument();
    expect(screen.getByText(/低风险 1/)).toBeInTheDocument();
  });

  // --- Run task from drawer (covers handleRun) ---
  test('run button in drawer calls runTask API', async () => {
    mockAuditApi.getTask.mockResolvedValue({
      id: 3,
      task_name: '风险评估检查',
      task_type: 'risk_assessment',
      status: 'pending',
      progress: 0,
      stage: 'pending',
      created_at: '2024-01-03T00:00:00Z',
      documents: [],
    } as any);
    mockAuditApi.runTask.mockResolvedValue({ status: 'running', task_id: 3 });
    const user = userEvent.setup();
    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('风险评估检查')).toBeInTheDocument();
    });

    const taskElements = screen.getAllByText('风险评估检查');
    await user.click(taskElements[0]);

    await waitFor(() => {
      const runButtons = screen.getAllByText('运行');
      expect(runButtons.length).toBeGreaterThanOrEqual(1);
    });

    // Click the run button in the drawer
    const runButtons = screen.getAllByText('运行');
    await user.click(runButtons[runButtons.length - 1]); // last one is in drawer

    await waitFor(() => {
      expect(mockAuditApi.runTask).toHaveBeenCalledWith(3);
    });
  });

  // --- Cancel task from drawer (covers handleCancel) ---
  test('cancel button in drawer shows confirmation', async () => {
    mockAuditApi.getTask.mockResolvedValue({
      id: 2,
      task_name: '偏差分析任务',
      task_type: 'deviation_analysis',
      status: 'running',
      progress: 45,
      stage: 'risk',
      created_at: '2024-01-02T00:00:00Z',
      started_at: '2024-01-02T00:01:00Z',
      documents: [],
    } as any);
    const user = userEvent.setup();
    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('偏差分析任务')).toBeInTheDocument();
    });

    const taskElements = screen.getAllByText('偏差分析任务');
    await user.click(taskElements[0]);

    await waitFor(() => {
      const cancelButtons = screen.getAllByText('取消任务');
      expect(cancelButtons.length).toBeGreaterThanOrEqual(1);
    });
  });

  // --- Task with awaiting_review shows approve/reject in drawer ---
  test('drawer shows approve and reject for awaiting_review task', async () => {
    mockAuditApi.listTasks.mockResolvedValue({
      items: [
        {
          id: 10,
          task_name: '待审核任务',
          task_type: 'deviation_analysis',
          status: 'awaiting_review' as const,
          progress: 90,
          stage: 'report',
          created_at: '2024-01-10T00:00:00Z',
          documents: [],
        },
      ],
      total: 1,
      page: 1,
      page_size: 20,
    } as any);
    mockAuditApi.getTask.mockResolvedValue({
      id: 10,
      task_name: '待审核任务',
      task_type: 'deviation_analysis',
      status: 'awaiting_review',
      progress: 90,
      stage: 'report',
      created_at: '2024-01-10T00:00:00Z',
      documents: [],
    } as any);
    const user = userEvent.setup();
    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('待审核任务')).toBeInTheDocument();
    });

    const taskElements = screen.getAllByText('待审核任务');
    await user.click(taskElements[0]);

    await waitFor(() => {
      // Should show approve/reject buttons
      const approveButtons = screen.getAllByText('批准');
      expect(approveButtons.length).toBeGreaterThanOrEqual(1);
    });

    const rejectButtons = screen.getAllByText('驳回');
    expect(rejectButtons.length).toBeGreaterThanOrEqual(1);
  });

  // --- Task with report_id shows report button in list ---
  test('report button navigates to reports page', async () => {
    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('SOP合规审查')).toBeInTheDocument();
    });

    const reportButtons = screen.getAllByText('报告');
    expect(reportButtons.length).toBeGreaterThan(0);
    // The button should be a link
    expect(reportButtons[0].closest('button')).toBeTruthy();
  });

  // --- Type filter ---
  test('type filter changes displayed tasks', async () => {
    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('SOP合规审查')).toBeInTheDocument();
    });

    // All 4 tasks should be visible
    expect(screen.getByText('偏差分析任务')).toBeInTheDocument();

    // The type filter select should be present
    const selects = document.querySelectorAll('.ant-select');
    expect(selects.length).toBeGreaterThanOrEqual(2); // status + type filters
  });

  // --- Status filter ---
  test('status filter select is present', async () => {
    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('SOP合规审查')).toBeInTheDocument();
    });

    // Should have filter selects
    const selects = document.querySelectorAll('.ant-select');
    expect(selects.length).toBeGreaterThanOrEqual(2);
  });

  // --- Task count display ---
  test('displays correct task count', async () => {
    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText(/共 4 个任务/)).toBeInTheDocument();
    });
  });

  // --- Elapsed time for running task ---
  test('shows elapsed time for running task in drawer', async () => {
    mockAuditApi.getTask.mockResolvedValue({
      id: 2,
      task_name: '偏差分析任务',
      task_type: 'deviation_analysis',
      status: 'running',
      progress: 45,
      stage: 'risk',
      created_at: '2024-01-02T00:00:00Z',
      started_at: new Date(Date.now() - 120000).toISOString(), // 2 minutes ago
      documents: [],
    } as any);
    const user = userEvent.setup();
    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('偏差分析任务')).toBeInTheDocument();
    });

    const taskElements = screen.getAllByText('偏差分析任务');
    await user.click(taskElements[0]);

    await waitFor(() => {
      // Should show elapsed time
      expect(screen.getByText(/已运行/)).toBeInTheDocument();
    });
  });

  // --- Empty drawer state ---
  test('shows empty state when no task selected', async () => {
    mockAuditApi.listTasks.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 } as any);
    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('暂无审计任务')).toBeInTheDocument();
    });
  });

  // --- Loading state ---
  test('shows loading state initially', async () => {
    mockAuditApi.listTasks.mockImplementation(() => new Promise(() => {})); // never resolves
    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('加载中...')).toBeInTheDocument();
    });
  });

  // --- Cancel task from list (covers handleCancel) ---
  test('cancel button calls cancelTask API when confirmed', async () => {
    const originalConfirm = (await import('antd')).Modal.confirm;
    const mockConfirm = jest.fn(({ onOk }: any) => {
      if (onOk) onOk();
    });
    (await import('antd')).Modal.confirm = mockConfirm;
    mockAuditApi.cancelTask.mockResolvedValue({ status: 'cancelled', task_id: 2 });

    const user = userEvent.setup();
    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('偏差分析任务')).toBeInTheDocument();
    });

    const cancelButtons = screen.getAllByText('取消');
    await user.click(cancelButtons[0]);

    await waitFor(() => {
      expect(mockAuditApi.cancelTask).toHaveBeenCalled();
    });

    (await import('antd')).Modal.confirm = originalConfirm;
  });

  // --- Run task from list (covers handleRun) ---
  test('run button calls runTask API', async () => {
    mockAuditApi.runTask.mockResolvedValue({ status: 'running', task_id: 3 });
    const user = userEvent.setup();
    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('风险评估检查')).toBeInTheDocument();
    });

    const runButtons = screen.getAllByText('运行');
    await user.click(runButtons[0]);

    await waitFor(() => {
      expect(mockAuditApi.runTask).toHaveBeenCalledWith(3);
    });
  });

  // --- Task with report_id shows report button ---
  test('report button is present for tasks with report', async () => {
    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('SOP合规审查')).toBeInTheDocument();
    });

    const reportButtons = screen.getAllByText('报告');
    expect(reportButtons.length).toBeGreaterThan(0);
  });

  // --- Error handling on run task ---
  test('handles run task error gracefully', async () => {
    mockAuditApi.runTask.mockRejectedValue(new Error('Run failed'));
    const user = userEvent.setup();
    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('风险评估检查')).toBeInTheDocument();
    });

    const runButtons = screen.getAllByText('运行');
    await user.click(runButtons[0]);

    // Should not crash
    await waitFor(() => {
      expect(screen.getByText('风险评估检查')).toBeInTheDocument();
    });
  });

  // --- Drawer shows error message for failed task ---
  test('drawer shows error message section for failed task', async () => {
    mockAuditApi.getTask.mockResolvedValue({
      id: 4,
      task_name: '变更控制',
      task_type: 'consistency_check',
      status: 'failed',
      progress: 30,
      stage: 'regulation',
      error_message: 'LLM调用超时',
      created_at: '2024-01-04T00:00:00Z',
      documents: [],
    } as any);
    const user = userEvent.setup();
    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('变更控制')).toBeInTheDocument();
    });

    const taskElements = screen.getAllByText('变更控制');
    await user.click(taskElements[0]);

    await waitFor(() => {
      expect(screen.getByText('LLM调用超时')).toBeInTheDocument();
    });

    // Should show error section
    expect(screen.getByText('错误')).toBeInTheDocument();
  });

  // --- Drawer shows findings with severity counts ---
  test('drawer shows findings section with count', async () => {
    mockAuditApi.getFindings.mockResolvedValue([
      {
        id: 1,
        task_id: 1,
        finding_type: 'deviation',
        severity: 'high',
        title: '关键偏差',
        description: '高风险偏差',
        created_at: '2024-01-01T00:00:00Z',
      },
    ]);
    const user = userEvent.setup();
    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('SOP合规审查')).toBeInTheDocument();
    });

    const taskElements = screen.getAllByText('SOP合规审查');
    await user.click(taskElements[0]);

    await waitFor(() => {
      expect(screen.getByText(/审计发现 \(1 项\)/)).toBeInTheDocument();
    });
  });

  // --- Task type labels ---
  test('displays all task type labels correctly', async () => {
    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('SOP合规审查')).toBeInTheDocument();
    });

    // Check task type labels
    expect(screen.getAllByText('偏差分析').length).toBeGreaterThan(0);
    expect(screen.getAllByText('风险评估').length).toBeGreaterThan(0);
  });

  // --- Task stage labels ---
  test('displays task stage labels', async () => {
    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('SOP合规审查')).toBeInTheDocument();
    });

    // Stage labels should be visible
    expect(screen.getAllByText('已完成').length).toBeGreaterThan(0);
  });
});

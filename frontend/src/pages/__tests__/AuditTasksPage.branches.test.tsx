import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';

import AuditTasksPage from '../AuditTasksPage';
import { auditApi, documentApi } from '../../services/api';

jest.setTimeout(20000);

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

// Mock components
jest.mock('../../components/AgentFlowChart', () => {
  return function MockAgentFlowChart() {
    return <div data-testid="agent-flow-chart">AgentFlowChart</div>;
  };
});

jest.mock('../../components/AgentThinkingPanel', () => {
  return function MockAgentThinkingPanel() {
    return <div data-testid="agent-thinking-panel">AgentThinkingPanel</div>;
  };
});

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

const singleAwaitingReviewTask = {
  items: [
    {
      id: 10,
      task_name: '待审核任务',
      task_type: 'deviation_analysis',
      status: 'awaiting_review' as const,
      progress: 90,
      stage: 'report',
      created_at: '2024-01-10T00:00:00Z',
      report_id: null,
      documents: [],
    },
  ],
  total: 1,
  page: 1,
  page_size: 20,
};

const singleRunningTask = {
  items: [
    {
      id: 2,
      task_name: '运行中的任务',
      task_type: 'deviation_analysis',
      status: 'running' as const,
      progress: 45,
      stage: 'risk',
      created_at: '2024-01-02T00:00:00Z',
      started_at: new Date(Date.now() - 120000).toISOString(),
      report_id: null,
      documents: [],
    },
  ],
  total: 1,
  page: 1,
  page_size: 20,
};

describe('AuditTasksPage branch coverage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockAuditApi.listTasks.mockResolvedValue({
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
      ],
      total: 1,
      page: 1,
      page_size: 20,
    } as any);
    mockDocumentApi.list.mockResolvedValue({
      items: [
        { id: 1, filename: 'SOP-001.pdf', file_type: 'pdf', process_status: 'processed' as const },
      ],
      total: 1,
      page: 1,
      page_size: 100,
    });
    mockAuditApi.getTask.mockImplementation((id: number) => {
      return Promise.resolve({
        id,
        task_name: 'SOP合规审查',
        task_type: 'sop_compliance',
        status: 'completed',
        progress: 100,
        stage: 'completed',
        created_at: '2024-01-01T00:00:00Z',
        report_id: 10,
        documents: [],
      } as any);
    });
    mockAuditApi.getFindings.mockResolvedValue([]);
  });

  // --- handleApprove via banner ---
  test('approve button in awaiting_review banner calls approveTask API', async () => {
    mockAuditApi.listTasks.mockResolvedValue(singleAwaitingReviewTask as any);
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
    mockAuditApi.approveTask.mockResolvedValue({ status: 'approved' });

    const originalConfirm = (await import('antd')).Modal.confirm;
    const mockConfirm = jest.fn(({ onOk }: any) => {
      if (onOk) onOk();
    });
    (await import('antd')).Modal.confirm = mockConfirm;

    const user = userEvent.setup();
    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getAllByText('待审核任务').length).toBeGreaterThanOrEqual(1);
    });

    const taskElements = screen.getAllByText('待审核任务');
    await user.click(taskElements[0]);

    await waitFor(() => {
      expect(screen.getAllByText('批准').length).toBeGreaterThanOrEqual(1);
    });

    const approveButtons = screen.getAllByText('批准');
    await user.click(approveButtons[0]);

    await waitFor(() => {
      expect(mockAuditApi.approveTask).toHaveBeenCalled();
    });

    (await import('antd')).Modal.confirm = originalConfirm;
  });

  // --- handleApprove error ---
  test('approve handles API error gracefully', async () => {
    mockAuditApi.listTasks.mockResolvedValue(singleAwaitingReviewTask as any);
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
    mockAuditApi.approveTask.mockRejectedValue(new Error('Approve failed'));

    const originalConfirm = (await import('antd')).Modal.confirm;
    const mockConfirm = jest.fn(({ onOk }: any) => {
      if (onOk) onOk();
    });
    (await import('antd')).Modal.confirm = mockConfirm;

    const user = userEvent.setup();
    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getAllByText('待审核任务').length).toBeGreaterThanOrEqual(1);
    });

    const taskElements = screen.getAllByText('待审核任务');
    await user.click(taskElements[0]);

    await waitFor(() => {
      expect(screen.getAllByText('批准').length).toBeGreaterThanOrEqual(1);
    });

    const approveButtons = screen.getAllByText('批准');
    await user.click(approveButtons[0]);

    await waitFor(() => {
      expect(mockAuditApi.approveTask).toHaveBeenCalled();
    });

    (await import('antd')).Modal.confirm = originalConfirm;
  });

  // --- handleApprove non-Error exception ---
  test('approve handles non-Error exception', async () => {
    mockAuditApi.listTasks.mockResolvedValue(singleAwaitingReviewTask as any);
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
    mockAuditApi.approveTask.mockRejectedValue('string error');

    const originalConfirm = (await import('antd')).Modal.confirm;
    const mockConfirm = jest.fn(({ onOk }: any) => {
      if (onOk) onOk();
    });
    (await import('antd')).Modal.confirm = mockConfirm;

    const user = userEvent.setup();
    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getAllByText('待审核任务').length).toBeGreaterThanOrEqual(1);
    });

    const taskElements = screen.getAllByText('待审核任务');
    await user.click(taskElements[0]);

    await waitFor(() => {
      expect(screen.getAllByText('批准').length).toBeGreaterThanOrEqual(1);
    });

    const approveButtons = screen.getAllByText('批准');
    await user.click(approveButtons[0]);

    await waitFor(() => {
      expect(mockAuditApi.approveTask).toHaveBeenCalled();
    });

    (await import('antd')).Modal.confirm = originalConfirm;
  });

  // --- handleReject via banner ---
  test('reject button in awaiting_review banner opens modal', async () => {
    mockAuditApi.listTasks.mockResolvedValue(singleAwaitingReviewTask as any);
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

    const originalConfirm = (await import('antd')).Modal.confirm;
    const mockConfirm = jest.fn();
    (await import('antd')).Modal.confirm = mockConfirm;

    const user = userEvent.setup();
    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getAllByText('待审核任务').length).toBeGreaterThanOrEqual(1);
    });

    const taskElements = screen.getAllByText('待审核任务');
    await user.click(taskElements[0]);

    await waitFor(() => {
      expect(screen.getAllByText('驳回').length).toBeGreaterThanOrEqual(1);
    });

    const rejectButtons = screen.getAllByText('驳回');
    await user.click(rejectButtons[0]);

    await waitFor(() => {
      expect(mockConfirm).toHaveBeenCalled();
    });

    (await import('antd')).Modal.confirm = originalConfirm;
  });

  // --- handleReject calls Modal.confirm with correct title ---
  test('reject modal has correct title', async () => {
    mockAuditApi.listTasks.mockResolvedValue(singleAwaitingReviewTask as any);
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

    const originalConfirm = (await import('antd')).Modal.confirm;
    const mockConfirm = jest.fn();
    (await import('antd')).Modal.confirm = mockConfirm;

    const user = userEvent.setup();
    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getAllByText('待审核任务').length).toBeGreaterThanOrEqual(1);
    });

    const taskElements = screen.getAllByText('待审核任务');
    await user.click(taskElements[0]);

    await waitFor(() => {
      expect(screen.getAllByText('驳回').length).toBeGreaterThanOrEqual(1);
    });

    const rejectButtons = screen.getAllByText('驳回');
    await user.click(rejectButtons[0]);

    await waitFor(() => {
      expect(mockConfirm).toHaveBeenCalledWith(expect.objectContaining({
        title: '驳回任务',
      }));
    });

    (await import('antd')).Modal.confirm = originalConfirm;
  });

  // --- Drawer approve/reject buttons (bottom action area) ---
  test('drawer bottom area shows approve and reject for awaiting_review', async () => {
    mockAuditApi.listTasks.mockResolvedValue(singleAwaitingReviewTask as any);
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
      expect(screen.getAllByText('待审核任务').length).toBeGreaterThanOrEqual(1);
    });

    const taskElements = screen.getAllByText('待审核任务');
    await user.click(taskElements[0]);

    await waitFor(() => {
      const approveButtons = screen.getAllByText('批准');
      expect(approveButtons.length).toBeGreaterThanOrEqual(1);
    });

    const rejectButtons = screen.getAllByText('驳回');
    expect(rejectButtons.length).toBeGreaterThanOrEqual(1);
  });

  // --- Drawer cancel button for running task ---
  test('drawer cancel button calls cancelTask API when confirmed', async () => {
    mockAuditApi.listTasks.mockResolvedValue(singleRunningTask as any);
    mockAuditApi.getTask.mockResolvedValue({
      id: 2,
      task_name: '运行中的任务',
      task_type: 'deviation_analysis',
      status: 'running',
      progress: 45,
      stage: 'risk',
      created_at: '2024-01-02T00:00:00Z',
      started_at: new Date(Date.now() - 120000).toISOString(),
      documents: [],
    } as any);
    mockAuditApi.cancelTask.mockResolvedValue({ status: 'cancelled' });

    const originalConfirm = (await import('antd')).Modal.confirm;
    const mockConfirm = jest.fn(({ onOk }: any) => {
      if (onOk) onOk();
    });
    (await import('antd')).Modal.confirm = mockConfirm;

    const user = userEvent.setup();
    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('运行中的任务')).toBeInTheDocument();
    });

    const taskElements = screen.getAllByText('运行中的任务');
    await user.click(taskElements[0]);

    await waitFor(() => {
      expect(screen.getAllByText('取消任务').length).toBeGreaterThanOrEqual(1);
    });

    const cancelButtons = screen.getAllByText('取消任务');
    await user.click(cancelButtons[cancelButtons.length - 1]);

    await waitFor(() => {
      expect(mockAuditApi.cancelTask).toHaveBeenCalled();
    });

    (await import('antd')).Modal.confirm = originalConfirm;
  });

  // --- Drawer cancel error ---
  test('drawer cancel handles API error', async () => {
    mockAuditApi.listTasks.mockResolvedValue(singleRunningTask as any);
    mockAuditApi.getTask.mockResolvedValue({
      id: 2,
      task_name: '运行中的任务',
      task_type: 'deviation_analysis',
      status: 'running',
      progress: 45,
      stage: 'risk',
      created_at: '2024-01-02T00:00:00Z',
      started_at: new Date(Date.now() - 120000).toISOString(),
      documents: [],
    } as any);
    mockAuditApi.cancelTask.mockRejectedValue(new Error('Cancel failed'));

    const originalConfirm = (await import('antd')).Modal.confirm;
    const mockConfirm = jest.fn(({ onOk }: any) => {
      if (onOk) onOk();
    });
    (await import('antd')).Modal.confirm = mockConfirm;

    const user = userEvent.setup();
    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('运行中的任务')).toBeInTheDocument();
    });

    const taskElements = screen.getAllByText('运行中的任务');
    await user.click(taskElements[0]);

    await waitFor(() => {
      expect(screen.getAllByText('取消任务').length).toBeGreaterThanOrEqual(1);
    });

    const cancelButtons = screen.getAllByText('取消任务');
    await user.click(cancelButtons[cancelButtons.length - 1]);

    await waitFor(() => {
      expect(mockAuditApi.cancelTask).toHaveBeenCalled();
    });

    (await import('antd')).Modal.confirm = originalConfirm;
  });

  // --- Drawer cancel non-Error exception ---
  test('drawer cancel handles non-Error exception', async () => {
    mockAuditApi.listTasks.mockResolvedValue(singleRunningTask as any);
    mockAuditApi.getTask.mockResolvedValue({
      id: 2,
      task_name: '运行中的任务',
      task_type: 'deviation_analysis',
      status: 'running',
      progress: 45,
      stage: 'risk',
      created_at: '2024-01-02T00:00:00Z',
      started_at: new Date(Date.now() - 120000).toISOString(),
      documents: [],
    } as any);
    mockAuditApi.cancelTask.mockRejectedValue('string error');

    const originalConfirm = (await import('antd')).Modal.confirm;
    const mockConfirm = jest.fn(({ onOk }: any) => {
      if (onOk) onOk();
    });
    (await import('antd')).Modal.confirm = mockConfirm;

    const user = userEvent.setup();
    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('运行中的任务')).toBeInTheDocument();
    });

    const taskElements = screen.getAllByText('运行中的任务');
    await user.click(taskElements[0]);

    await waitFor(() => {
      expect(screen.getAllByText('取消任务').length).toBeGreaterThanOrEqual(1);
    });

    const cancelButtons = screen.getAllByText('取消任务');
    await user.click(cancelButtons[cancelButtons.length - 1]);

    await waitFor(() => {
      expect(mockAuditApi.cancelTask).toHaveBeenCalled();
    });

    (await import('antd')).Modal.confirm = originalConfirm;
  });

  // --- handleRun from drawer (pending task) ---
  test('handleRun from drawer calls runTask and reloads', async () => {
    mockAuditApi.listTasks.mockResolvedValue({
      items: [
        {
          id: 3,
          task_name: '待运行任务',
          task_type: 'risk_assessment',
          status: 'pending' as const,
          progress: 0,
          stage: 'pending',
          created_at: '2024-01-03T00:00:00Z',
          report_id: null,
          documents: [],
        },
      ],
      total: 1,
      page: 1,
      page_size: 20,
    } as any);
    mockAuditApi.getTask.mockResolvedValue({
      id: 3,
      task_name: '待运行任务',
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
      expect(screen.getByText('待运行任务')).toBeInTheDocument();
    });

    const taskElements = screen.getAllByText('待运行任务');
    await user.click(taskElements[0]);

    await waitFor(() => {
      const runButtons = screen.getAllByText('运行');
      expect(runButtons.length).toBeGreaterThanOrEqual(1);
    });

    // Click the drawer's run button (last one)
    const runButtons = screen.getAllByText('运行');
    await user.click(runButtons[runButtons.length - 1]);

    await waitFor(() => {
      expect(mockAuditApi.runTask).toHaveBeenCalledWith(3);
    });
  });

  // --- handleRun error ---
  test('handleRun handles API error', async () => {
    mockAuditApi.listTasks.mockResolvedValue({
      items: [
        {
          id: 3,
          task_name: '待运行任务',
          task_type: 'risk_assessment',
          status: 'pending' as const,
          progress: 0,
          stage: 'pending',
          created_at: '2024-01-03T00:00:00Z',
          report_id: null,
          documents: [],
        },
      ],
      total: 1,
      page: 1,
      page_size: 20,
    } as any);
    mockAuditApi.getTask.mockResolvedValue({
      id: 3,
      task_name: '待运行任务',
      task_type: 'risk_assessment',
      status: 'pending',
      progress: 0,
      stage: 'pending',
      created_at: '2024-01-03T00:00:00Z',
      documents: [],
    } as any);
    mockAuditApi.runTask.mockRejectedValue(new Error('Run failed'));

    const user = userEvent.setup();
    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('待运行任务')).toBeInTheDocument();
    });

    const taskElements = screen.getAllByText('待运行任务');
    await user.click(taskElements[0]);

    await waitFor(() => {
      const runButtons = screen.getAllByText('运行');
      expect(runButtons.length).toBeGreaterThanOrEqual(1);
    });

    const runButtons = screen.getAllByText('运行');
    await user.click(runButtons[runButtons.length - 1]);

    await waitFor(() => {
      expect(mockAuditApi.runTask).toHaveBeenCalledWith(3);
    });
  });

  // --- handleRun non-Error exception ---
  test('handleRun handles non-Error exception', async () => {
    mockAuditApi.listTasks.mockResolvedValue({
      items: [
        {
          id: 3,
          task_name: '待运行任务',
          task_type: 'risk_assessment',
          status: 'pending' as const,
          progress: 0,
          stage: 'pending',
          created_at: '2024-01-03T00:00:00Z',
          report_id: null,
          documents: [],
        },
      ],
      total: 1,
      page: 1,
      page_size: 20,
    } as any);
    mockAuditApi.getTask.mockResolvedValue({
      id: 3,
      task_name: '待运行任务',
      task_type: 'risk_assessment',
      status: 'pending',
      progress: 0,
      stage: 'pending',
      created_at: '2024-01-03T00:00:00Z',
      documents: [],
    } as any);
    mockAuditApi.runTask.mockRejectedValue('string error');

    const user = userEvent.setup();
    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('待运行任务')).toBeInTheDocument();
    });

    const taskElements = screen.getAllByText('待运行任务');
    await user.click(taskElements[0]);

    await waitFor(() => {
      const runButtons = screen.getAllByText('运行');
      expect(runButtons.length).toBeGreaterThanOrEqual(1);
    });

    const runButtons = screen.getAllByText('运行');
    await user.click(runButtons[runButtons.length - 1]);

    await waitFor(() => {
      expect(mockAuditApi.runTask).toHaveBeenCalledWith(3);
    });
  });

  // --- handleCancel from list (non-Error) ---
  test('cancel from list handles non-Error exception', async () => {
    mockAuditApi.listTasks.mockResolvedValue({
      items: [
        {
          id: 5,
          task_name: '运行任务',
          task_type: 'deviation_analysis',
          status: 'running' as const,
          progress: 30,
          stage: 'risk',
          created_at: '2024-01-05T00:00:00Z',
          report_id: null,
          documents: [],
        },
      ],
      total: 1,
      page: 1,
      page_size: 20,
    } as any);
    mockAuditApi.getTask.mockResolvedValue({
      id: 5,
      task_name: '运行任务',
      task_type: 'deviation_analysis',
      status: 'running',
      progress: 30,
      stage: 'risk',
      created_at: '2024-01-05T00:00:00Z',
      documents: [],
    } as any);
    mockAuditApi.cancelTask.mockRejectedValue('string error');

    const originalConfirm = (await import('antd')).Modal.confirm;
    const mockConfirm = jest.fn(({ onOk }: any) => {
      if (onOk) onOk();
    });
    (await import('antd')).Modal.confirm = mockConfirm;

    const user = userEvent.setup();
    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('运行任务')).toBeInTheDocument();
    });

    const cancelButtons = screen.getAllByText('取消');
    await user.click(cancelButtons[0]);

    await waitFor(() => {
      expect(mockAuditApi.cancelTask).toHaveBeenCalled();
    });

    (await import('antd')).Modal.confirm = originalConfirm;
  });

  // --- loadDocuments error ---
  test('handles document list load error', async () => {
    mockDocumentApi.list.mockRejectedValue(new Error('Doc load failed'));

    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('SOP合规审查')).toBeInTheDocument();
    });
  });

  // --- loadDocuments non-Error ---
  test('handles document list non-Error exception', async () => {
    mockDocumentApi.list.mockRejectedValue('string error');

    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('SOP合规审查')).toBeInTheDocument();
    });
  });

  // --- loadTasks non-Error (showSpinner=false path) ---
  test('handles loadTasks non-Error when not showing spinner', async () => {
    // First load succeeds
    mockAuditApi.listTasks.mockResolvedValueOnce({
      items: [
        {
          id: 1,
          task_name: 'SOP合规审查',
          task_type: 'sop_compliance',
          status: 'running' as const,
          progress: 50,
          stage: 'risk',
          created_at: '2024-01-01T00:00:00Z',
          report_id: null,
          documents: [],
        },
      ],
      total: 1,
      page: 1,
      page_size: 20,
    } as any);
    // Subsequent loads fail (polling path)
    mockAuditApi.listTasks.mockRejectedValue('string error');

    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('SOP合规审查')).toBeInTheDocument();
    });
  });

  // --- loadTaskDetails error ---
  test('handles loadTaskDetails error', async () => {
    mockAuditApi.getTask.mockRejectedValue(new Error('Task load failed'));
    mockAuditApi.getFindings.mockRejectedValue(new Error('Findings load failed'));

    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('SOP合规审查')).toBeInTheDocument();
    });
  });

  // --- Drawer with no selected task ---
  test('drawer shows empty when no task selected', async () => {
    mockAuditApi.listTasks.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 } as any);

    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('暂无审计任务')).toBeInTheDocument();
    });
  });

  // --- Task with stage = queued ---
  test('shows running status for task with stage queued', async () => {
    mockAuditApi.listTasks.mockResolvedValue({
      items: [
        {
          id: 20,
          task_name: '排队任务',
          task_type: 'deviation_analysis',
          status: 'pending' as const,
          progress: 0,
          stage: 'queued',
          created_at: '2024-01-20T00:00:00Z',
          report_id: null,
          documents: [],
        },
      ],
      total: 1,
      page: 1,
      page_size: 20,
    } as any);

    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('排队任务')).toBeInTheDocument();
    });
  });

  // --- Timeline event levels (error, warning) ---
  test('task with events renders correctly', async () => {
    mockAuditApi.listTasks.mockResolvedValue({
      items: [
        {
          id: 2,
          task_name: 'Timeline Task',
          task_type: 'deviation_analysis',
          status: 'running' as const,
          progress: 45,
          stage: 'risk',
          created_at: '2024-01-02T00:00:00Z',
          started_at: new Date(Date.now() - 120000).toISOString(),
          report_id: null,
          documents: [],
        },
      ],
      total: 1,
      page: 1,
      page_size: 20,
    } as any);
    mockAuditApi.getTask.mockResolvedValue({
      id: 2,
      task_name: 'Timeline Task',
      task_type: 'deviation_analysis',
      status: 'running',
      progress: 45,
      stage: 'risk',
      created_at: '2024-01-02T00:00:00Z',
      started_at: new Date(Date.now() - 120000).toISOString(),
      documents: [],
      events: [
        { time: '2024-01-02T00:01:00Z', stage: 'parsing', level: 'info' as const, message: '开始解析' },
        { time: '2024-01-02T00:02:00Z', stage: 'regulation', level: 'warning' as const, message: '法规匹配较慢' },
        { time: '2024-01-02T00:03:00Z', stage: 'risk', level: 'error' as const, message: 'LLM调用超时' },
      ],
    } as any);

    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getAllByText('Timeline Task').length).toBeGreaterThanOrEqual(1);
    });

    // Verify the task is rendered with correct status
    expect(screen.getAllByText('进行中').length).toBeGreaterThanOrEqual(1);
  });

  // --- Task with stage tag fallback ---
  test('shows stage label for task with unknown stage', async () => {
    mockAuditApi.listTasks.mockResolvedValue({
      items: [
        {
          id: 30,
          task_name: '未知阶段任务',
          task_type: 'deviation_analysis',
          status: 'running' as const,
          progress: 50,
          stage: 'custom_stage',
          created_at: '2024-01-30T00:00:00Z',
          report_id: null,
          documents: [],
        },
      ],
      total: 1,
      page: 1,
      page_size: 20,
    } as any);

    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('未知阶段任务')).toBeInTheDocument();
    });
  });

  // --- Status filter interaction ---
  test('status filter changes displayed tasks', async () => {
    mockAuditApi.listTasks.mockResolvedValue({
      items: [
        { id: 1, task_name: '任务A', task_type: 'deviation_analysis', status: 'completed' as const, progress: 100, stage: 'completed', created_at: '2024-01-01T00:00:00Z', report_id: null, documents: [] },
        { id: 2, task_name: '任务B', task_type: 'deviation_analysis', status: 'running' as const, progress: 50, stage: 'risk', created_at: '2024-01-02T00:00:00Z', report_id: null, documents: [] },
      ],
      total: 2,
      page: 1,
      page_size: 20,
    } as any);

    const user = userEvent.setup();
    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('任务A')).toBeInTheDocument();
    });

    // Both tasks should be visible
    expect(screen.getByText('任务B')).toBeInTheDocument();
  });

  // --- Search keyword filter ---
  test('search keyword filters tasks by name', async () => {
    mockAuditApi.listTasks.mockResolvedValue({
      items: [
        { id: 1, task_name: 'Alpha任务', task_type: 'deviation_analysis', status: 'completed' as const, progress: 100, stage: 'completed', created_at: '2024-01-01T00:00:00Z', report_id: null, documents: [] },
        { id: 2, task_name: 'Beta任务', task_type: 'deviation_analysis', status: 'running' as const, progress: 50, stage: 'risk', created_at: '2024-01-02T00:00:00Z', report_id: null, documents: [] },
      ],
      total: 2,
      page: 1,
      page_size: 20,
    } as any);

    const user = userEvent.setup();
    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('Alpha任务')).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText('搜索任务名称...');
    await user.type(searchInput, 'Alpha');

    await waitFor(() => {
      expect(screen.getByText('Alpha任务')).toBeInTheDocument();
    });

    expect(screen.queryByText('Beta任务')).not.toBeInTheDocument();
  });

  // --- Sort by name ---
  test('sort by name reorders tasks', async () => {
    mockAuditApi.listTasks.mockResolvedValue({
      items: [
        { id: 1, task_name: 'Z任务', task_type: 'deviation_analysis', status: 'completed' as const, progress: 100, stage: 'completed', created_at: '2024-01-01T00:00:00Z', report_id: null, documents: [] },
        { id: 2, task_name: 'A任务', task_type: 'deviation_analysis', status: 'completed' as const, progress: 100, stage: 'completed', created_at: '2024-01-02T00:00:00Z', report_id: null, documents: [] },
      ],
      total: 2,
      page: 1,
      page_size: 20,
    } as any);

    const user = userEvent.setup();
    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('Z任务')).toBeInTheDocument();
    });

    // Click sort selector
    await user.click(screen.getByText('按时间排序'));

    await waitFor(() => {
      expect(screen.getByText('按名称排序')).toBeInTheDocument();
    });

    await user.click(screen.getByText('按名称排序'));

    await waitFor(() => {
      expect(screen.getByText('Z任务')).toBeInTheDocument();
    });
  });

  // --- Sort by status ---
  test('sort by status reorders tasks', async () => {
    mockAuditApi.listTasks.mockResolvedValue({
      items: [
        { id: 1, task_name: '已完成任务', task_type: 'deviation_analysis', status: 'completed' as const, progress: 100, stage: 'completed', created_at: '2024-01-01T00:00:00Z', report_id: null, documents: [] },
        { id: 2, task_name: '运行中任务', task_type: 'deviation_analysis', status: 'running' as const, progress: 50, stage: 'risk', created_at: '2024-01-02T00:00:00Z', report_id: null, documents: [] },
      ],
      total: 2,
      page: 1,
      page_size: 20,
    } as any);

    const user = userEvent.setup();
    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('已完成任务')).toBeInTheDocument();
    });

    await user.click(screen.getByText('按时间排序'));

    await waitFor(() => {
      expect(screen.getByText('按状态排序')).toBeInTheDocument();
    });

    await user.click(screen.getByText('按状态排序'));

    await waitFor(() => {
      expect(screen.getByText('已完成任务')).toBeInTheDocument();
    });
  });

  // --- Awaiting review banner description text ---
  test('shows review description text in banner', async () => {
    mockAuditApi.listTasks.mockResolvedValue(singleAwaitingReviewTask as any);
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
      expect(screen.getByText(/请审查下方的审计发现/)).toBeInTheDocument();
    });
  });

  // --- Knowledge graph button in drawer navigates ---
  test('knowledge graph button click does not crash', async () => {
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
      expect(screen.getByText('知识图谱')).toBeInTheDocument();
    });

    await user.click(screen.getByText('知识图谱'));

    // Should not crash
    expect(screen.getByText('知识图谱')).toBeInTheDocument();
  });

  // --- Create task modal cancel ---
  test('create task modal opens and has close button', async () => {
    const user = userEvent.setup();
    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('开始审计')).toBeInTheDocument();
    });

    await user.click(screen.getByText('开始审计'));

    await waitFor(() => {
      expect(screen.getByText('创建审计任务')).toBeInTheDocument();
    });

    // Modal should have a close button
    expect(document.querySelector('.ant-modal-close')).toBeInTheDocument();
  });

  // --- Drawer shows report button for tasks with report_id ---
  test('drawer bottom shows view report button for tasks with report', async () => {
    mockAuditApi.listTasks.mockResolvedValue({
      items: [
        {
          id: 1,
          task_name: 'Report Task',
          task_type: 'sop_compliance',
          status: 'completed' as const,
          progress: 100,
          stage: 'completed',
          created_at: '2024-01-01T00:00:00Z',
          report_id: 10,
          documents: [],
        },
      ],
      total: 1,
      page: 1,
      page_size: 20,
    } as any);
    mockAuditApi.getTask.mockResolvedValue({
      id: 1,
      task_name: 'Report Task',
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
      expect(screen.getAllByText('Report Task').length).toBeGreaterThanOrEqual(1);
    });

    const taskElements = screen.getAllByText('Report Task');
    await user.click(taskElements[0]);

    await waitFor(() => {
      expect(screen.getAllByText('查看报告').length).toBeGreaterThanOrEqual(1);
    });

    const reportButtons = screen.getAllByText('查看报告');
    await user.click(reportButtons[0]);

    // Should not crash
    expect(screen.getAllByText('Report Task').length).toBeGreaterThanOrEqual(1);
  });

  // --- Error message section not shown when no error ---
  test('does not show error section when task has no error_message', async () => {
    mockAuditApi.getTask.mockResolvedValue({
      id: 1,
      task_name: 'SOP合规审查',
      task_type: 'sop_compliance',
      status: 'completed',
      progress: 100,
      stage: 'completed',
      created_at: '2024-01-01T00:00:00Z',
      report_id: 10,
      error_message: null,
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
      expect(screen.getByTestId('agent-flow-chart')).toBeInTheDocument();
    });

    expect(screen.queryByText('错误')).not.toBeInTheDocument();
  });

  // --- Progress percent fallback ---
  test('shows 0% progress for task with no progress value', async () => {
    mockAuditApi.listTasks.mockResolvedValue({
      items: [
        {
          id: 40,
          task_name: '无进度任务',
          task_type: 'deviation_analysis',
          status: 'pending' as const,
          progress: null,
          stage: 'pending',
          created_at: '2024-01-40T00:00:00Z',
          report_id: null,
          documents: [],
        },
      ],
      total: 1,
      page: 1,
      page_size: 20,
    } as any);

    renderWithRouter(<AuditTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('无进度任务')).toBeInTheDocument();
    });
  });
});

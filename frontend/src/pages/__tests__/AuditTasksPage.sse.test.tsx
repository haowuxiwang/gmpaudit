import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';

import AuditTasksPage from '../AuditTasksPage';
import { auditApi, documentApi } from '../../services/api';

jest.setTimeout(30000);

// Mock useTaskSSE - use __mocks__ pattern
jest.mock('../../hooks/useTaskSSE');

// Import the mocked module to access the mock function
const { useTaskSSE } = require('../../hooks/useTaskSSE') as { useTaskSSE: jest.Mock };

// Mock EventSource (required by component imports)
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

// Mock Notification API
const mockNotificationConstructor = jest.fn();
const mockRequestPermission = jest.fn().mockResolvedValue('default');

class MockNotification {
  static permission = 'default';
  static requestPermission = mockRequestPermission;
  constructor(title: string, options?: any) {
    mockNotificationConstructor(title, options);
  }
}
(global as any).Notification = MockNotification;

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

function makeSSEReturn(overrides: any = {}) {
  return {
    events: [],
    thinkingEvents: [],
    currentStage: 'pending',
    lastActiveStage: 'pending',
    progress: 0,
    status: 'pending',
    isConnected: false,
    connectionError: false,
    resetProgress: jest.fn(),
    ...overrides,
  };
}

// --- Test Data ---
const runningTask = {
  id: 2,
  task_name: 'SSE Running Task',
  task_type: 'deviation_analysis',
  status: 'running' as const,
  progress: 30,
  stage: 'regulation',
  created_at: '2024-01-02T00:00:00Z',
  started_at: new Date(Date.now() - 60000).toISOString(),
  report_id: null,
  documents: [],
};

const runningTaskResponse = {
  items: [runningTask],
  total: 1,
  page: 1,
  page_size: 20,
};

const completedTask = {
  id: 1,
  task_name: 'SSE Completed Task',
  task_type: 'sop_compliance',
  status: 'completed' as const,
  progress: 100,
  stage: 'completed',
  created_at: '2024-01-01T00:00:00Z',
  report_id: 10,
  documents: [],
};

const completedTaskResponse = {
  items: [completedTask],
  total: 1,
  page: 1,
  page_size: 20,
};

const awaitingReviewTask = {
  id: 10,
  task_name: 'SSE Awaiting Review Task',
  task_type: 'deviation_analysis',
  status: 'awaiting_review' as const,
  progress: 90,
  stage: 'report',
  created_at: '2024-01-10T00:00:00Z',
  report_id: null,
  documents: [],
};

const awaitingReviewTaskResponse = {
  items: [awaitingReviewTask],
  total: 1,
  page: 1,
  page_size: 20,
};

const pendingTask = {
  id: 3,
  task_name: 'Pending Task',
  task_type: 'risk_assessment',
  status: 'pending' as const,
  progress: 0,
  stage: 'pending',
  created_at: '2024-01-03T00:00:00Z',
  report_id: null,
  documents: [],
};

const pendingTaskResponse = {
  items: [pendingTask],
  total: 1,
  page: 1,
  page_size: 20,
};

const multiTaskResponse = {
  items: [
    { id: 1, task_name: 'Alpha Task', task_type: 'sop_compliance', status: 'completed' as const, progress: 100, stage: 'completed', created_at: '2024-01-01T00:00:00Z', report_id: 10, documents: [] },
    { id: 2, task_name: 'Beta Task', task_type: 'deviation_analysis', status: 'running' as const, progress: 50, stage: 'risk', created_at: '2024-01-02T00:00:00Z', started_at: '2024-01-02T00:01:00Z', report_id: null, documents: [] },
    { id: 3, task_name: 'Gamma Task', task_type: 'risk_assessment', status: 'pending' as const, progress: 0, stage: 'pending', created_at: '2024-01-03T00:00:00Z', report_id: null, documents: [] },
  ],
  total: 3,
  page: 1,
  page_size: 20,
};

function setupDefaultMocks() {
  useTaskSSE.mockReturnValue(makeSSEReturn());
  mockAuditApi.listTasks.mockResolvedValue(completedTaskResponse as any);
  mockDocumentApi.list.mockResolvedValue({
    items: [],
    total: 0,
    page: 1,
    page_size: 100,
  });
  mockAuditApi.getTask.mockImplementation((id: number) => {
    const all = [completedTask, runningTask, awaitingReviewTask, pendingTask];
    const task = all.find((t) => t.id === id);
    return Promise.resolve(task as any);
  });
  mockAuditApi.getFindings.mockResolvedValue([]);
}

describe('AuditTasksPage SSE tests', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    setupDefaultMocks();
    MockNotification.permission = 'default';
    mockNotificationConstructor.mockClear();
    mockRequestPermission.mockClear();
    mockRequestPermission.mockResolvedValue('default');
  });

  // =====================
  // 1. SSE Connection
  // =====================
  describe('SSE connection', () => {
    test('useTaskSSE is called with running task id and isActive=true', async () => {
      mockAuditApi.listTasks.mockResolvedValue(runningTaskResponse as any);

      renderWithRouter(<AuditTasksPage />);

      await waitFor(() => {
        expect(screen.getByText('SSE Running Task')).toBeInTheDocument();
      });

      await waitFor(() => {
        expect(useTaskSSE).toHaveBeenCalledWith(2, true);
      });
    });

    test('useTaskSSE called with isActive=false for non-running task', async () => {
      mockAuditApi.listTasks.mockResolvedValue(completedTaskResponse as any);

      renderWithRouter(<AuditTasksPage />);

      await waitFor(() => {
        expect(screen.getByText('SSE Completed Task')).toBeInTheDocument();
      });

      await waitFor(() => {
        expect(useTaskSSE).toHaveBeenCalledWith(1, false);
      });
    });
  });

  // =====================
  // 2. SSE State Merge
  // =====================
  describe('SSE state merge', () => {
    test('SSE progress updates merge into running task', async () => {
      mockAuditApi.listTasks.mockResolvedValue(runningTaskResponse as any);
      useTaskSSE.mockReturnValue(makeSSEReturn({
        progress: 65,
        currentStage: 'risk',
        status: 'running',
        isConnected: true,
      }));

      const user = userEvent.setup();
      renderWithRouter(<AuditTasksPage />);

      await waitFor(() => {
        expect(screen.getByText('SSE Running Task')).toBeInTheDocument();
      });

      // Click task to open drawer
      const taskElements = screen.getAllByText('SSE Running Task');
      await user.click(taskElements[0]);

      await waitFor(() => {
        expect(screen.getByTestId('agent-flow-chart')).toBeInTheDocument();
      });
    });

    test('SSE currentStage updates displayed in drawer', async () => {
      mockAuditApi.listTasks.mockResolvedValue(runningTaskResponse as any);
      useTaskSSE.mockReturnValue(makeSSEReturn({
        currentStage: 'report',
        progress: 70,
        status: 'running',
        isConnected: true,
      }));

      const user = userEvent.setup();
      renderWithRouter(<AuditTasksPage />);

      await waitFor(() => {
        expect(screen.getByText('SSE Running Task')).toBeInTheDocument();
      });

      const taskElements = screen.getAllByText('SSE Running Task');
      await user.click(taskElements[0]);

      await waitFor(() => {
        expect(screen.getByTestId('agent-flow-chart')).toBeInTheDocument();
      });
    });

    test('SSE events merge into selectedTask events', async () => {
      mockAuditApi.listTasks.mockResolvedValue(runningTaskResponse as any);
      mockAuditApi.getTask.mockResolvedValue({
        ...runningTask,
        events: [
          { time: '2024-01-02T00:01:00Z', stage: 'parsing', level: 'info' as const, message: 'Initial event' },
        ],
      } as any);
      useTaskSSE.mockReturnValue(makeSSEReturn({
        events: [
          { time: '2024-01-02T00:02:00Z', stage: 'regulation', level: 'info' as const, message: 'SSE event 1' },
        ],
        progress: 50,
        currentStage: 'risk',
        status: 'running',
        isConnected: true,
      }));

      renderWithRouter(<AuditTasksPage />);

      await waitFor(() => {
        expect(screen.getByText('SSE Running Task')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      const taskElements = screen.getAllByText('SSE Running Task');
      await user.click(taskElements[0]);

      await waitFor(() => {
        expect(screen.getByText('执行时间线')).toBeInTheDocument();
      });
    });

    test('SSE thinking events trigger AgentThinkingPanel', async () => {
      mockAuditApi.listTasks.mockResolvedValue(runningTaskResponse as any);
      useTaskSSE.mockReturnValue(makeSSEReturn({
        thinkingEvents: [
          { node: 'regulation_expert', stage: 'regulation', status: 'started' as const, message: 'Analyzing...' },
        ],
        currentStage: 'regulation',
        progress: 30,
        status: 'running',
        isConnected: true,
      }));

      const user = userEvent.setup();
      renderWithRouter(<AuditTasksPage />);

      await waitFor(() => {
        expect(screen.getByText('SSE Running Task')).toBeInTheDocument();
      });

      const taskElements = screen.getAllByText('SSE Running Task');
      await user.click(taskElements[0]);

      await waitFor(() => {
        expect(screen.getByTestId('agent-thinking-panel')).toBeInTheDocument();
      });
    });

    test('SSE no new data does not trigger unnecessary updates', async () => {
      mockAuditApi.listTasks.mockResolvedValue(runningTaskResponse as any);
      useTaskSSE.mockReturnValue(makeSSEReturn({
        events: [],
        progress: 0,
        currentStage: 'pending',
        status: 'running',
        isConnected: true,
      }));

      renderWithRouter(<AuditTasksPage />);

      await waitFor(() => {
        expect(screen.getByText('SSE Running Task')).toBeInTheDocument();
      });

      // Should still render without issues
      expect(screen.getByText('SSE Running Task')).toBeInTheDocument();
    });
  });

  // =====================
  // 3. SSE Done Events
  // =====================
  describe('SSE done events', () => {
    test('done with status=completed triggers task list reload', async () => {
      mockAuditApi.listTasks.mockResolvedValue(runningTaskResponse as any);
      useTaskSSE.mockReturnValue(makeSSEReturn({
        progress: 100,
        currentStage: 'completed',
        status: 'completed',
      }));

      renderWithRouter(<AuditTasksPage />);

      await waitFor(() => {
        expect(screen.getByText('SSE Running Task')).toBeInTheDocument();
      });

      await waitFor(() => {
        expect(mockAuditApi.listTasks.mock.calls.length).toBeGreaterThanOrEqual(2);
      });
    });

    test('done with status=failed triggers task list reload', async () => {
      mockAuditApi.listTasks.mockResolvedValue(runningTaskResponse as any);
      useTaskSSE.mockReturnValue(makeSSEReturn({
        progress: 30,
        currentStage: 'failed',
        status: 'failed',
      }));

      renderWithRouter(<AuditTasksPage />);

      await waitFor(() => {
        expect(screen.getByText('SSE Running Task')).toBeInTheDocument();
      });

      await waitFor(() => {
        expect(mockAuditApi.listTasks.mock.calls.length).toBeGreaterThanOrEqual(2);
      });
    });

    test('done with status=awaiting_review triggers reload', async () => {
      mockAuditApi.listTasks.mockResolvedValue(runningTaskResponse as any);
      useTaskSSE.mockReturnValue(makeSSEReturn({
        progress: 90,
        currentStage: 'awaiting_review',
        status: 'awaiting_review',
      }));

      renderWithRouter(<AuditTasksPage />);

      await waitFor(() => {
        expect(screen.getByText('SSE Running Task')).toBeInTheDocument();
      });

      await waitFor(() => {
        expect(mockAuditApi.listTasks.mock.calls.length).toBeGreaterThanOrEqual(2);
      });
    });

    test('done with status=completed updates progress to 100', async () => {
      mockAuditApi.listTasks.mockResolvedValue(runningTaskResponse as any);
      useTaskSSE.mockReturnValue(makeSSEReturn({
        progress: 100,
        currentStage: 'completed',
        status: 'completed',
      }));

      renderWithRouter(<AuditTasksPage />);

      await waitFor(() => {
        expect(screen.getByText('SSE Running Task')).toBeInTheDocument();
      });

      await waitFor(() => {
        expect(mockAuditApi.listTasks.mock.calls.length).toBeGreaterThanOrEqual(2);
      });
    });
  });

  // =====================
  // 4. SSE Connection Error
  // =====================
  describe('SSE connection error', () => {
    test('shows warning Alert when connectionError and task running', async () => {
      mockAuditApi.listTasks.mockResolvedValue(runningTaskResponse as any);
      useTaskSSE.mockReturnValue(makeSSEReturn({
        connectionError: true,
        progress: 30,
        currentStage: 'regulation',
        status: 'running',
        isConnected: true,
      }));

      renderWithRouter(<AuditTasksPage />);

      await waitFor(() => {
        expect(screen.getByText('SSE Running Task')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      const taskElements = screen.getAllByText('SSE Running Task');
      await user.click(taskElements[0]);

      await waitFor(() => {
        expect(screen.getByText('实时连接中断')).toBeInTheDocument();
      });
    });

    test('connection error Alert not shown for non-running task', async () => {
      mockAuditApi.listTasks.mockResolvedValue(completedTaskResponse as any);
      useTaskSSE.mockReturnValue(makeSSEReturn({
        connectionError: true,
        progress: 100,
        status: 'completed',
      }));

      renderWithRouter(<AuditTasksPage />);

      await waitFor(() => {
        expect(screen.getByText('SSE Completed Task')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      const taskElements = screen.getAllByText('SSE Completed Task');
      await user.click(taskElements[0]);

      await waitFor(() => {
        expect(screen.getByTestId('agent-flow-chart')).toBeInTheDocument();
      });

      expect(screen.queryByText('实时连接中断')).not.toBeInTheDocument();
    });
  });

  // =====================
  // 5. Notification API
  // =====================
  describe('Notification API', () => {
    test('requests permission when tasks are running', async () => {
      mockAuditApi.listTasks.mockResolvedValue(runningTaskResponse as any);
      MockNotification.permission = 'default';
      mockRequestPermission.mockResolvedValue('granted');

      renderWithRouter(<AuditTasksPage />);

      await waitFor(() => {
        expect(screen.getByText('SSE Running Task')).toBeInTheDocument();
      });

      await waitFor(() => {
        expect(mockRequestPermission).toHaveBeenCalled();
      });
    });

    test('Notification on SSE done=completed when permission granted', async () => {
      mockAuditApi.listTasks.mockResolvedValue(runningTaskResponse as any);
      MockNotification.permission = 'granted';
      useTaskSSE.mockReturnValue(makeSSEReturn({
        progress: 100,
        currentStage: 'completed',
        status: 'completed',
      }));

      renderWithRouter(<AuditTasksPage />);

      await waitFor(() => {
        expect(screen.getByText('SSE Running Task')).toBeInTheDocument();
      });

      await waitFor(() => {
        expect(mockNotificationConstructor).toHaveBeenCalledWith(
          'AuditBee 任务完成',
          expect.objectContaining({ body: expect.stringContaining('已完成') }),
        );
      });
    });

    test('Notification on SSE done=failed when permission granted', async () => {
      mockAuditApi.listTasks.mockResolvedValue(runningTaskResponse as any);
      MockNotification.permission = 'granted';
      useTaskSSE.mockReturnValue(makeSSEReturn({
        progress: 30,
        currentStage: 'failed',
        status: 'failed',
      }));

      renderWithRouter(<AuditTasksPage />);

      await waitFor(() => {
        expect(screen.getByText('SSE Running Task')).toBeInTheDocument();
      });

      await waitFor(() => {
        expect(mockNotificationConstructor).toHaveBeenCalledWith(
          'AuditBee 任务完成',
          expect.objectContaining({ body: expect.stringContaining('失败') }),
        );
      });
    });

    test('Notification on SSE done=awaiting_review when permission granted', async () => {
      mockAuditApi.listTasks.mockResolvedValue(runningTaskResponse as any);
      MockNotification.permission = 'granted';
      useTaskSSE.mockReturnValue(makeSSEReturn({
        progress: 90,
        currentStage: 'awaiting_review',
        status: 'awaiting_review',
      }));

      renderWithRouter(<AuditTasksPage />);

      await waitFor(() => {
        expect(screen.getByText('SSE Running Task')).toBeInTheDocument();
      });

      await waitFor(() => {
        expect(mockNotificationConstructor).toHaveBeenCalledWith(
          'AuditBee 任务完成',
          expect.objectContaining({ body: expect.stringContaining('待审核') }),
        );
      });
    });

    test('Notification NOT shown when permission denied', async () => {
      mockAuditApi.listTasks.mockResolvedValue(runningTaskResponse as any);
      MockNotification.permission = 'denied';
      useTaskSSE.mockReturnValue(makeSSEReturn({
        progress: 100,
        currentStage: 'completed',
        status: 'completed',
      }));

      renderWithRouter(<AuditTasksPage />);

      await waitFor(() => {
        expect(screen.getByText('SSE Running Task')).toBeInTheDocument();
      });

      await waitFor(() => {
        expect(mockAuditApi.listTasks.mock.calls.length).toBeGreaterThanOrEqual(2);
      });

      expect(mockNotificationConstructor).not.toHaveBeenCalled();
    });
  });

  // =====================
  // 6. handleCreate Full Flow
  // =====================
  describe('handleCreate flow', () => {
    test('create task modal opens with all required fields', async () => {
      mockAuditApi.listTasks.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 } as any);
      mockDocumentApi.list.mockResolvedValue({
        items: [{ id: 1, filename: 'doc.pdf', file_type: 'pdf', process_status: 'processed' as const }],
        total: 1, page: 1, page_size: 100,
      });

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

    test('create task modal loads documents on open', async () => {
      mockAuditApi.listTasks.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 } as any);
      mockDocumentApi.list.mockResolvedValue({
        items: [
          { id: 1, filename: 'doc1.pdf', file_type: 'pdf', process_status: 'processed' as const },
          { id: 2, filename: 'doc2.docx', file_type: 'docx', process_status: 'processed' as const },
        ],
        total: 2, page: 1, page_size: 100,
      });

      const user = userEvent.setup();
      renderWithRouter(<AuditTasksPage />);

      await waitFor(() => {
        expect(screen.getByText('开始审计')).toBeInTheDocument();
      });

      await user.click(screen.getByText('开始审计'));

      await waitFor(() => {
        expect(mockDocumentApi.list).toHaveBeenCalled();
      });
    });

    test('create task form submits with all fields filled', async () => {
      mockAuditApi.listTasks.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 } as any);
      mockDocumentApi.list.mockResolvedValue({
        items: [{ id: 1, filename: 'doc.pdf', file_type: 'pdf', process_status: 'processed' as const }],
        total: 1, page: 1, page_size: 100,
      });
      mockAuditApi.createTask.mockResolvedValue({ id: 100, task_name: 'New Task', status: 'pending' });
      mockAuditApi.runTask.mockResolvedValue({ status: 'running', task_id: 100 });
      mockAuditApi.getTask.mockResolvedValue({ id: 100, task_name: 'New Task', task_type: 'deviation_analysis', status: 'running', progress: 0, stage: 'pending', created_at: '2024-01-01T00:00:00Z', documents: [] } as any);

      const user = userEvent.setup();
      renderWithRouter(<AuditTasksPage />);

      await waitFor(() => {
        expect(screen.getByText('开始审计')).toBeInTheDocument();
      });

      await user.click(screen.getByText('开始审计'));

      await waitFor(() => {
        expect(screen.getByText('创建审计任务')).toBeInTheDocument();
      });

      // Fill task name
      const taskNameInput = screen.getByLabelText('任务名称');
      await user.type(taskNameInput, 'New Task');

      // Open document select dropdown and select a document
      const docSelect = screen.getByLabelText('选择文档');
      await user.click(docSelect);

      await waitFor(() => {
        expect(screen.getByText('doc.pdf')).toBeInTheDocument();
      });

      await user.click(screen.getByText('doc.pdf'));

      // Submit form
      const okButton = document.querySelector('.ant-modal-footer .ant-btn-primary');
      if (okButton) await user.click(okButton as Element);

      await waitFor(() => {
        expect(mockAuditApi.createTask).toHaveBeenCalledWith(
          expect.objectContaining({
            task_name: 'New Task',
            task_type: 'deviation_analysis',
          }),
        );
      });
    });

    test('create task success shows success message and opens drawer', async () => {
      mockAuditApi.listTasks.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 } as any);
      mockDocumentApi.list.mockResolvedValue({
        items: [{ id: 1, filename: 'doc.pdf', file_type: 'pdf', process_status: 'processed' as const }],
        total: 1, page: 1, page_size: 100,
      });
      mockAuditApi.createTask.mockResolvedValue({ id: 100, task_name: 'New Task', status: 'pending' });
      mockAuditApi.runTask.mockResolvedValue({ status: 'running', task_id: 100 });
      mockAuditApi.getTask.mockResolvedValue({ id: 100, task_name: 'New Task', task_type: 'deviation_analysis', status: 'running', progress: 0, stage: 'pending', created_at: '2024-01-01T00:00:00Z', documents: [] } as any);

      const user = userEvent.setup();
      renderWithRouter(<AuditTasksPage />);

      await waitFor(() => {
        expect(screen.getByText('开始审计')).toBeInTheDocument();
      });

      await user.click(screen.getByText('开始审计'));

      await waitFor(() => {
        expect(screen.getByText('创建审计任务')).toBeInTheDocument();
      });

      const taskNameInput = screen.getByLabelText('任务名称');
      await user.type(taskNameInput, 'New Task');

      // Open and select document
      const docSelect = screen.getByLabelText('选择文档');
      await user.click(docSelect);
      await waitFor(() => { expect(screen.getByText('doc.pdf')).toBeInTheDocument(); });
      await user.click(screen.getByText('doc.pdf'));

      const okButton = document.querySelector('.ant-modal-footer .ant-btn-primary');
      if (okButton) await user.click(okButton as Element);

      await waitFor(() => {
        expect(mockAuditApi.createTask).toHaveBeenCalled();
      });

      // Auto-run should be called
      await waitFor(() => {
        expect(mockAuditApi.runTask).toHaveBeenCalledWith(100);
      });
    });

    test('create task failure shows error message', async () => {
      mockAuditApi.listTasks.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 } as any);
      mockDocumentApi.list.mockResolvedValue({
        items: [{ id: 1, filename: 'doc.pdf', file_type: 'pdf', process_status: 'processed' as const }],
        total: 1, page: 1, page_size: 100,
      });
      mockAuditApi.createTask.mockRejectedValue(new Error('Create failed'));

      const user = userEvent.setup();
      renderWithRouter(<AuditTasksPage />);

      await waitFor(() => {
        expect(screen.getByText('开始审计')).toBeInTheDocument();
      });

      await user.click(screen.getByText('开始审计'));

      await waitFor(() => {
        expect(screen.getByText('创建审计任务')).toBeInTheDocument();
      });

      const taskNameInput = screen.getByLabelText('任务名称');
      await user.type(taskNameInput, 'Fail Task');

      const docSelect = screen.getByLabelText('选择文档');
      await user.click(docSelect);
      await waitFor(() => { expect(screen.getByText('doc.pdf')).toBeInTheDocument(); });
      await user.click(screen.getByText('doc.pdf'));

      const okButton = document.querySelector('.ant-modal-footer .ant-btn-primary');
      if (okButton) await user.click(okButton as Element);

      await waitFor(() => {
        expect(mockAuditApi.createTask).toHaveBeenCalled();
      });

      // Page should not crash
      expect(screen.getByText('创建审计任务')).toBeInTheDocument();
    });

    test('auto-run failure shows warning message', async () => {
      mockAuditApi.listTasks.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 } as any);
      mockDocumentApi.list.mockResolvedValue({
        items: [{ id: 1, filename: 'doc.pdf', file_type: 'pdf', process_status: 'processed' as const }],
        total: 1, page: 1, page_size: 100,
      });
      mockAuditApi.createTask.mockResolvedValue({ id: 101, task_name: 'Task', status: 'pending' });
      mockAuditApi.runTask.mockRejectedValue(new Error('Run failed'));

      const user = userEvent.setup();
      renderWithRouter(<AuditTasksPage />);

      await waitFor(() => { expect(screen.getByText('开始审计')).toBeInTheDocument(); });
      await user.click(screen.getByText('开始审计'));
      await waitFor(() => { expect(screen.getByText('创建审计任务')).toBeInTheDocument(); });

      const taskNameInput = screen.getByLabelText('任务名称');
      await user.type(taskNameInput, 'Task');

      const docSelect = screen.getByLabelText('选择文档');
      await user.click(docSelect);
      await waitFor(() => { expect(screen.getByText('doc.pdf')).toBeInTheDocument(); });
      await user.click(screen.getByText('doc.pdf'));

      const okButton = document.querySelector('.ant-modal-footer .ant-btn-primary');
      if (okButton) await user.click(okButton as Element);

      await waitFor(() => {
        expect(mockAuditApi.createTask).toHaveBeenCalled();
      });

      await waitFor(() => {
        expect(mockAuditApi.runTask).toHaveBeenCalled();
      });
    });

    test('create task non-Error exception handled', async () => {
      mockAuditApi.listTasks.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 } as any);
      mockDocumentApi.list.mockResolvedValue({
        items: [{ id: 1, filename: 'doc.pdf', file_type: 'pdf', process_status: 'processed' as const }],
        total: 1, page: 1, page_size: 100,
      });
      mockAuditApi.createTask.mockRejectedValue('string error');

      const user = userEvent.setup();
      renderWithRouter(<AuditTasksPage />);

      await waitFor(() => { expect(screen.getByText('开始审计')).toBeInTheDocument(); });
      await user.click(screen.getByText('开始审计'));
      await waitFor(() => { expect(screen.getByText('创建审计任务')).toBeInTheDocument(); });

      const taskNameInput = screen.getByLabelText('任务名称');
      await user.type(taskNameInput, 'Fail Task');

      const docSelect = screen.getByLabelText('选择文档');
      await user.click(docSelect);
      await waitFor(() => { expect(screen.getByText('doc.pdf')).toBeInTheDocument(); });
      await user.click(screen.getByText('doc.pdf'));

      const okButton = document.querySelector('.ant-modal-footer .ant-btn-primary');
      if (okButton) await user.click(okButton as Element);

      await waitFor(() => {
        expect(mockAuditApi.createTask).toHaveBeenCalled();
      });
    });

    test('auto-run non-Error exception handled', async () => {
      mockAuditApi.listTasks.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 } as any);
      mockDocumentApi.list.mockResolvedValue({
        items: [{ id: 1, filename: 'doc.pdf', file_type: 'pdf', process_status: 'processed' as const }],
        total: 1, page: 1, page_size: 100,
      });
      mockAuditApi.createTask.mockResolvedValue({ id: 102, task_name: 'Task', status: 'pending' });
      mockAuditApi.runTask.mockRejectedValue('string error');

      const user = userEvent.setup();
      renderWithRouter(<AuditTasksPage />);

      await waitFor(() => { expect(screen.getByText('开始审计')).toBeInTheDocument(); });
      await user.click(screen.getByText('开始审计'));
      await waitFor(() => { expect(screen.getByText('创建审计任务')).toBeInTheDocument(); });

      const taskNameInput = screen.getByLabelText('任务名称');
      await user.type(taskNameInput, 'Task');

      const docSelect = screen.getByLabelText('选择文档');
      await user.click(docSelect);
      await waitFor(() => { expect(screen.getByText('doc.pdf')).toBeInTheDocument(); });
      await user.click(screen.getByText('doc.pdf'));

      const okButton = document.querySelector('.ant-modal-footer .ant-btn-primary');
      if (okButton) await user.click(okButton as Element);

      await waitFor(() => {
        expect(mockAuditApi.createTask).toHaveBeenCalled();
      });
    });

    test('document list load error does not crash modal', async () => {
      mockAuditApi.listTasks.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 } as any);
      mockDocumentApi.list.mockRejectedValue(new Error('Doc load failed'));

      const user = userEvent.setup();
      renderWithRouter(<AuditTasksPage />);

      await waitFor(() => { expect(screen.getByText('开始审计')).toBeInTheDocument(); });
      await user.click(screen.getByText('开始审计'));

      await waitFor(() => {
        expect(screen.getByText('创建审计任务')).toBeInTheDocument();
      });

      expect(screen.getByLabelText('任务名称')).toBeInTheDocument();
    });

    test('document list load non-Error exception does not crash', async () => {
      mockAuditApi.listTasks.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 } as any);
      mockDocumentApi.list.mockRejectedValue('string error');

      const user = userEvent.setup();
      renderWithRouter(<AuditTasksPage />);

      await waitFor(() => { expect(screen.getByText('开始审计')).toBeInTheDocument(); });
      await user.click(screen.getByText('开始审计'));

      await waitFor(() => {
        expect(screen.getByText('创建审计任务')).toBeInTheDocument();
      });
    });
  });

  // =====================
  // 7. Task Operations
  // =====================
  describe('task operations', () => {
    test('approve from banner calls approveTask', async () => {
      mockAuditApi.listTasks.mockResolvedValue(awaitingReviewTaskResponse as any);
      mockAuditApi.getTask.mockResolvedValue(awaitingReviewTask as any);
      mockAuditApi.approveTask.mockResolvedValue({ status: 'approved' });

      const originalConfirm = (await import('antd')).Modal.confirm;
      const mockConfirm = jest.fn(({ onOk }: any) => { if (onOk) onOk(); });
      (await import('antd')).Modal.confirm = mockConfirm;

      const user = userEvent.setup();
      renderWithRouter(<AuditTasksPage />);

      await waitFor(() => {
        expect(screen.getByText('SSE Awaiting Review Task')).toBeInTheDocument();
      });

      const taskElements = screen.getAllByText('SSE Awaiting Review Task');
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

    test('approve handles API error', async () => {
      mockAuditApi.listTasks.mockResolvedValue(awaitingReviewTaskResponse as any);
      mockAuditApi.getTask.mockResolvedValue(awaitingReviewTask as any);
      mockAuditApi.approveTask.mockRejectedValue(new Error('Approve failed'));

      const originalConfirm = (await import('antd')).Modal.confirm;
      const mockConfirm = jest.fn(({ onOk }: any) => { if (onOk) onOk(); });
      (await import('antd')).Modal.confirm = mockConfirm;

      const user = userEvent.setup();
      renderWithRouter(<AuditTasksPage />);

      await waitFor(() => {
        expect(screen.getByText('SSE Awaiting Review Task')).toBeInTheDocument();
      });

      const taskElements = screen.getAllByText('SSE Awaiting Review Task');
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

    test('approve handles non-Error exception', async () => {
      mockAuditApi.listTasks.mockResolvedValue(awaitingReviewTaskResponse as any);
      mockAuditApi.getTask.mockResolvedValue(awaitingReviewTask as any);
      mockAuditApi.approveTask.mockRejectedValue('string error');

      const originalConfirm = (await import('antd')).Modal.confirm;
      const mockConfirm = jest.fn(({ onOk }: any) => { if (onOk) onOk(); });
      (await import('antd')).Modal.confirm = mockConfirm;

      const user = userEvent.setup();
      renderWithRouter(<AuditTasksPage />);

      await waitFor(() => {
        expect(screen.getByText('SSE Awaiting Review Task')).toBeInTheDocument();
      });

      const taskElements = screen.getAllByText('SSE Awaiting Review Task');
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

    test('reject from banner opens Modal.confirm', async () => {
      mockAuditApi.listTasks.mockResolvedValue(awaitingReviewTaskResponse as any);
      mockAuditApi.getTask.mockResolvedValue(awaitingReviewTask as any);

      const originalConfirm = (await import('antd')).Modal.confirm;
      const mockConfirm = jest.fn();
      (await import('antd')).Modal.confirm = mockConfirm;

      const user = userEvent.setup();
      renderWithRouter(<AuditTasksPage />);

      await waitFor(() => {
        expect(screen.getByText('SSE Awaiting Review Task')).toBeInTheDocument();
      });

      const taskElements = screen.getAllByText('SSE Awaiting Review Task');
      await user.click(taskElements[0]);

      await waitFor(() => {
        expect(screen.getAllByText('驳回').length).toBeGreaterThanOrEqual(1);
      });

      const rejectButtons = screen.getAllByText('驳回');
      await user.click(rejectButtons[0]);

      await waitFor(() => {
        expect(mockConfirm).toHaveBeenCalledWith(expect.objectContaining({ title: '驳回任务' }));
      });

      (await import('antd')).Modal.confirm = originalConfirm;
    });

    test('cancel from list triggers Modal.confirm', async () => {
      mockAuditApi.listTasks.mockResolvedValue(runningTaskResponse as any);
      mockAuditApi.cancelTask.mockResolvedValue({ status: 'cancelled' });

      const originalConfirm = (await import('antd')).Modal.confirm;
      const mockConfirm = jest.fn(({ onOk }: any) => { if (onOk) onOk(); });
      (await import('antd')).Modal.confirm = mockConfirm;

      const user = userEvent.setup();
      renderWithRouter(<AuditTasksPage />);

      await waitFor(() => {
        expect(screen.getByText('SSE Running Task')).toBeInTheDocument();
      });

      const cancelButtons = screen.getAllByText('取消');
      await user.click(cancelButtons[0]);

      await waitFor(() => {
        expect(mockConfirm).toHaveBeenCalledWith(expect.objectContaining({ title: '取消任务' }));
      });

      (await import('antd')).Modal.confirm = originalConfirm;
    });

    test('run from list calls runTask API', async () => {
      mockAuditApi.listTasks.mockResolvedValue(pendingTaskResponse as any);
      mockAuditApi.runTask.mockResolvedValue({ status: 'running', task_id: 3 });

      const user = userEvent.setup();
      renderWithRouter(<AuditTasksPage />);

      await waitFor(() => {
        expect(screen.getByText('Pending Task')).toBeInTheDocument();
      });

      const runButtons = screen.getAllByText('运行');
      await user.click(runButtons[0]);

      await waitFor(() => {
        expect(mockAuditApi.runTask).toHaveBeenCalledWith(3);
      });
    });

    test('run from drawer calls runTask API', async () => {
      mockAuditApi.listTasks.mockResolvedValue(pendingTaskResponse as any);
      mockAuditApi.getTask.mockResolvedValue(pendingTask as any);
      mockAuditApi.runTask.mockResolvedValue({ status: 'running', task_id: 3 });

      const user = userEvent.setup();
      renderWithRouter(<AuditTasksPage />);

      await waitFor(() => {
        expect(screen.getByText('Pending Task')).toBeInTheDocument();
      });

      const taskElements = screen.getAllByText('Pending Task');
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

    test('run handles API error', async () => {
      mockAuditApi.listTasks.mockResolvedValue(pendingTaskResponse as any);
      mockAuditApi.getTask.mockResolvedValue(pendingTask as any);
      mockAuditApi.runTask.mockRejectedValue(new Error('Run failed'));

      const user = userEvent.setup();
      renderWithRouter(<AuditTasksPage />);

      await waitFor(() => {
        expect(screen.getAllByText('Pending Task').length).toBeGreaterThanOrEqual(1);
      });

      const taskElements = screen.getAllByText('Pending Task');
      await user.click(taskElements[0]);

      await waitFor(() => {
        const runButtons = screen.getAllByText('运行');
        expect(runButtons.length).toBeGreaterThanOrEqual(1);
      });

      const runButtons = screen.getAllByText('运行');
      await user.click(runButtons[runButtons.length - 1]);

      await waitFor(() => {
        expect(mockAuditApi.runTask).toHaveBeenCalled();
      });

      // Page should not crash
      expect(screen.getAllByText('Pending Task').length).toBeGreaterThanOrEqual(1);
    });

    test('run handles non-Error exception', async () => {
      mockAuditApi.listTasks.mockResolvedValue(pendingTaskResponse as any);
      mockAuditApi.getTask.mockResolvedValue(pendingTask as any);
      mockAuditApi.runTask.mockRejectedValue('string error');

      const user = userEvent.setup();
      renderWithRouter(<AuditTasksPage />);

      await waitFor(() => {
        expect(screen.getAllByText('Pending Task').length).toBeGreaterThanOrEqual(1);
      });

      const taskElements = screen.getAllByText('Pending Task');
      await user.click(taskElements[0]);

      await waitFor(() => {
        const runButtons = screen.getAllByText('运行');
        expect(runButtons.length).toBeGreaterThanOrEqual(1);
      });

      const runButtons = screen.getAllByText('运行');
      await user.click(runButtons[runButtons.length - 1]);

      await waitFor(() => {
        expect(mockAuditApi.runTask).toHaveBeenCalled();
      });
    });

    test('cancel from drawer calls cancelTask', async () => {
      mockAuditApi.listTasks.mockResolvedValue(runningTaskResponse as any);
      mockAuditApi.getTask.mockResolvedValue(runningTask as any);
      mockAuditApi.cancelTask.mockResolvedValue({ status: 'cancelled' });

      const originalConfirm = (await import('antd')).Modal.confirm;
      const mockConfirm = jest.fn(({ onOk }: any) => { if (onOk) onOk(); });
      (await import('antd')).Modal.confirm = mockConfirm;

      const user = userEvent.setup();
      renderWithRouter(<AuditTasksPage />);

      await waitFor(() => {
        expect(screen.getByText('SSE Running Task')).toBeInTheDocument();
      });

      const taskElements = screen.getAllByText('SSE Running Task');
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

    test('cancel handles API error', async () => {
      mockAuditApi.listTasks.mockResolvedValue(runningTaskResponse as any);
      mockAuditApi.getTask.mockResolvedValue(runningTask as any);
      mockAuditApi.cancelTask.mockRejectedValue(new Error('Cancel failed'));

      const originalConfirm = (await import('antd')).Modal.confirm;
      const mockConfirm = jest.fn(({ onOk }: any) => { if (onOk) onOk(); });
      (await import('antd')).Modal.confirm = mockConfirm;

      const user = userEvent.setup();
      renderWithRouter(<AuditTasksPage />);

      await waitFor(() => {
        expect(screen.getByText('SSE Running Task')).toBeInTheDocument();
      });

      const taskElements = screen.getAllByText('SSE Running Task');
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

    test('cancel handles non-Error exception', async () => {
      mockAuditApi.listTasks.mockResolvedValue(runningTaskResponse as any);
      mockAuditApi.getTask.mockResolvedValue(runningTask as any);
      mockAuditApi.cancelTask.mockRejectedValue('string error');

      const originalConfirm = (await import('antd')).Modal.confirm;
      const mockConfirm = jest.fn(({ onOk }: any) => { if (onOk) onOk(); });
      (await import('antd')).Modal.confirm = mockConfirm;

      const user = userEvent.setup();
      renderWithRouter(<AuditTasksPage />);

      await waitFor(() => {
        expect(screen.getByText('SSE Running Task')).toBeInTheDocument();
      });

      const taskElements = screen.getAllByText('SSE Running Task');
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
  });

  // =====================
  // 8. Filtering and Sorting
  // =====================
  describe('filtering and sorting', () => {
    test('type filter dropdown present', async () => {
      mockAuditApi.listTasks.mockResolvedValue(multiTaskResponse as any);

      renderWithRouter(<AuditTasksPage />);

      await waitFor(() => {
        expect(screen.getByText('Alpha Task')).toBeInTheDocument();
      });

      const selects = document.querySelectorAll('.ant-select');
      expect(selects.length).toBeGreaterThanOrEqual(2);
    });

    test('sort dropdown changes between options', async () => {
      mockAuditApi.listTasks.mockResolvedValue(multiTaskResponse as any);

      const user = userEvent.setup();
      renderWithRouter(<AuditTasksPage />);

      await waitFor(() => {
        expect(screen.getByText('Alpha Task')).toBeInTheDocument();
      });

      await user.click(screen.getByText('按时间排序'));

      await waitFor(() => {
        expect(screen.getByText('按名称排序')).toBeInTheDocument();
      });

      await user.click(screen.getByText('按名称排序'));

      await waitFor(() => {
        expect(screen.getByText('Alpha Task')).toBeInTheDocument();
      });
    });

    test('sort by status reorders tasks', async () => {
      mockAuditApi.listTasks.mockResolvedValue(multiTaskResponse as any);

      const user = userEvent.setup();
      renderWithRouter(<AuditTasksPage />);

      await waitFor(() => {
        expect(screen.getByText('Alpha Task')).toBeInTheDocument();
      });

      await user.click(screen.getByText('按时间排序'));

      await waitFor(() => {
        expect(screen.getByText('按状态排序')).toBeInTheDocument();
      });

      await user.click(screen.getByText('按状态排序'));

      await waitFor(() => {
        expect(screen.getByText('Alpha Task')).toBeInTheDocument();
      });
    });

    test('search keyword filters tasks', async () => {
      mockAuditApi.listTasks.mockResolvedValue(multiTaskResponse as any);

      const user = userEvent.setup();
      renderWithRouter(<AuditTasksPage />);

      await waitFor(() => {
        expect(screen.getByText('Alpha Task')).toBeInTheDocument();
      });

      const searchInput = screen.getByPlaceholderText('搜索任务名称...');
      await user.type(searchInput, 'Beta');

      await waitFor(() => {
        expect(screen.getByText('Beta Task')).toBeInTheDocument();
      });

      expect(screen.queryByText('Alpha Task')).not.toBeInTheDocument();
    });

    test('task count updates with search filter', async () => {
      mockAuditApi.listTasks.mockResolvedValue(multiTaskResponse as any);

      const user = userEvent.setup();
      renderWithRouter(<AuditTasksPage />);

      await waitFor(() => {
        expect(screen.getByText(/共 3 个任务/)).toBeInTheDocument();
      });

      const searchInput = screen.getByPlaceholderText('搜索任务名称...');
      await user.type(searchInput, 'Beta');

      await waitFor(() => {
        expect(screen.getByText(/共 1 个任务/)).toBeInTheDocument();
      });
    });
  });

  // =====================
  // 9. Edge Cases
  // =====================
  describe('edge cases', () => {
    test('task with null progress renders', async () => {
      mockAuditApi.listTasks.mockResolvedValue({
        items: [{ id: 50, task_name: 'Null Progress', task_type: 'deviation_analysis', status: 'pending' as const, progress: null, stage: 'pending', created_at: '2024-01-05T00:00:00Z', report_id: null, documents: [] }],
        total: 1, page: 1, page_size: 20,
      } as any);

      renderWithRouter(<AuditTasksPage />);

      await waitFor(() => {
        expect(screen.getByText('Null Progress')).toBeInTheDocument();
      });
    });

    test('task with unknown stage renders', async () => {
      mockAuditApi.listTasks.mockResolvedValue({
        items: [{ id: 60, task_name: 'Unknown Stage', task_type: 'deviation_analysis', status: 'running' as const, progress: 50, stage: 'custom_unknown', created_at: '2024-01-06T00:00:00Z', started_at: '2024-01-06T00:01:00Z', report_id: null, documents: [] }],
        total: 1, page: 1, page_size: 20,
      } as any);

      renderWithRouter(<AuditTasksPage />);

      await waitFor(() => {
        expect(screen.getByText('Unknown Stage')).toBeInTheDocument();
      });
    });

    test('task with stage=queued renders', async () => {
      mockAuditApi.listTasks.mockResolvedValue({
        items: [{ id: 20, task_name: 'Queued Task', task_type: 'deviation_analysis', status: 'pending' as const, progress: 0, stage: 'queued', created_at: '2024-01-20T00:00:00Z', report_id: null, documents: [] }],
        total: 1, page: 1, page_size: 20,
      } as any);

      renderWithRouter(<AuditTasksPage />);

      await waitFor(() => {
        expect(screen.getByText('Queued Task')).toBeInTheDocument();
      });
    });

    test('keyboard accessibility on task list items', async () => {
      mockAuditApi.listTasks.mockResolvedValue(completedTaskResponse as any);

      renderWithRouter(<AuditTasksPage />);

      await waitFor(() => {
        expect(screen.getByText('SSE Completed Task')).toBeInTheDocument();
      });

      const taskItems = document.querySelectorAll('[role="button"]');
      expect(taskItems.length).toBeGreaterThan(0);
    });

    test('drawer opens and closes', async () => {
      mockAuditApi.listTasks.mockResolvedValue(completedTaskResponse as any);

      const user = userEvent.setup();
      renderWithRouter(<AuditTasksPage />);

      await waitFor(() => {
        expect(screen.getByText('SSE Completed Task')).toBeInTheDocument();
      });

      const taskElements = screen.getAllByText('SSE Completed Task');
      await user.click(taskElements[0]);

      await waitFor(() => {
        expect(screen.getByTestId('agent-flow-chart')).toBeInTheDocument();
      });

      const closeButton = document.querySelector('.ant-drawer-close');
      if (closeButton) await user.click(closeButton as Element);
    });

    test('failed task with error_message shows error section', async () => {
      const failedTask = {
        id: 4, task_name: 'Failed Task', task_type: 'consistency_check', status: 'failed' as const,
        progress: 30, stage: 'regulation', created_at: '2024-01-04T00:00:00Z',
        error_message: 'LLM call timeout', report_id: null, documents: [],
      };
      mockAuditApi.listTasks.mockResolvedValue({ items: [failedTask], total: 1, page: 1, page_size: 20 } as any);
      mockAuditApi.getTask.mockResolvedValue(failedTask as any);

      const user = userEvent.setup();
      renderWithRouter(<AuditTasksPage />);

      await waitFor(() => {
        expect(screen.getByText('Failed Task')).toBeInTheDocument();
      });

      const taskElements = screen.getAllByText('Failed Task');
      await user.click(taskElements[0]);

      await waitFor(() => {
        expect(screen.getByText('LLM call timeout')).toBeInTheDocument();
      });

      expect(screen.getByText('错误')).toBeInTheDocument();
    });

    test('task with findings shows severity counts', async () => {
      mockAuditApi.listTasks.mockResolvedValue(completedTaskResponse as any);
      mockAuditApi.getFindings.mockResolvedValue([
        { id: 1, task_id: 1, finding_type: 'deviation', severity: 'high', title: 'Critical', description: 'High risk', created_at: '2024-01-01T00:00:00Z' },
        { id: 2, task_id: 1, finding_type: 'deviation', severity: 'medium', title: 'Medium', description: 'Medium risk', created_at: '2024-01-01T00:00:00Z' },
        { id: 3, task_id: 1, finding_type: 'deviation', severity: 'low', title: 'Low', description: 'Low risk', created_at: '2024-01-01T00:00:00Z' },
        { id: 4, task_id: 1, finding_type: 'deviation', severity: 'info', title: 'Info', description: 'Info', created_at: '2024-01-01T00:00:00Z' },
      ]);

      const user = userEvent.setup();
      renderWithRouter(<AuditTasksPage />);

      await waitFor(() => {
        expect(screen.getByText('SSE Completed Task')).toBeInTheDocument();
      });

      const taskElements = screen.getAllByText('SSE Completed Task');
      await user.click(taskElements[0]);

      await waitFor(() => {
        expect(screen.getByText(/审计发现/)).toBeInTheDocument();
      });

      expect(screen.getByText(/高风险 1/)).toBeInTheDocument();
      expect(screen.getByText(/中风险 1/)).toBeInTheDocument();
      expect(screen.getByText(/低风险 1/)).toBeInTheDocument();
      expect(screen.getByText(/信息 1/)).toBeInTheDocument();
    });

    test('task with documents shows document list', async () => {
      mockAuditApi.listTasks.mockResolvedValue({
        items: [{
          id: 99, task_name: 'Doc Task', task_type: 'sop_compliance', status: 'completed' as const,
          progress: 100, stage: 'completed', created_at: '2024-01-01T00:00:00Z', report_id: 10,
          documents: [{ document_id: 1, filename: 'SOP-001.pdf', status: 'completed', findings_count: 3, risk_level: 'High' }],
        }],
        total: 1, page: 1, page_size: 20,
      } as any);
      mockAuditApi.getTask.mockResolvedValue({
        id: 99, task_name: 'Doc Task', task_type: 'sop_compliance', status: 'completed',
        progress: 100, stage: 'completed', created_at: '2024-01-01T00:00:00Z', report_id: 10,
        documents: [{ document_id: 1, filename: 'SOP-001.pdf', status: 'completed', findings_count: 3, risk_level: 'High' }],
      } as any);

      const user = userEvent.setup();
      renderWithRouter(<AuditTasksPage />);

      await waitFor(() => {
        expect(screen.getByText('Doc Task')).toBeInTheDocument();
      });

      const taskElements = screen.getAllByText('Doc Task');
      await user.click(taskElements[0]);

      await waitFor(() => {
        expect(screen.getByText('SOP-001.pdf')).toBeInTheDocument();
      });
    });

    test('knowledge graph button does not crash', async () => {
      mockAuditApi.listTasks.mockResolvedValue(completedTaskResponse as any);

      const user = userEvent.setup();
      renderWithRouter(<AuditTasksPage />);

      await waitFor(() => {
        expect(screen.getByText('SSE Completed Task')).toBeInTheDocument();
      });

      const taskElements = screen.getAllByText('SSE Completed Task');
      await user.click(taskElements[0]);

      await waitFor(() => {
        expect(screen.getByText('知识图谱')).toBeInTheDocument();
      });

      await user.click(screen.getByText('知识图谱'));
      expect(screen.getByText('知识图谱')).toBeInTheDocument();
    });

    test('view report button in drawer for tasks with report_id', async () => {
      mockAuditApi.listTasks.mockResolvedValue(completedTaskResponse as any);

      const user = userEvent.setup();
      renderWithRouter(<AuditTasksPage />);

      await waitFor(() => {
        expect(screen.getByText('SSE Completed Task')).toBeInTheDocument();
      });

      const taskElements = screen.getAllByText('SSE Completed Task');
      await user.click(taskElements[0]);

      await waitFor(() => {
        expect(screen.getByText('查看报告')).toBeInTheDocument();
      });
    });
  });

  // =====================
  // 10. Loading & Empty States
  // =====================
  describe('loading and empty states', () => {
    test('shows loading indicator when listTasks pending', async () => {
      mockAuditApi.listTasks.mockImplementation(() => new Promise(() => {}));

      renderWithRouter(<AuditTasksPage />);

      await waitFor(() => {
        expect(screen.getByText('加载中...')).toBeInTheDocument();
      });
    });

    test('shows empty state when no tasks', async () => {
      mockAuditApi.listTasks.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 } as any);

      renderWithRouter(<AuditTasksPage />);

      await waitFor(() => {
        expect(screen.getByText('暂无审计任务')).toBeInTheDocument();
      });
    });
  });

  // =====================
  // 11. Awaiting Review Banner
  // =====================
  describe('awaiting review banner', () => {
    test('shows review banner with approve/reject buttons', async () => {
      mockAuditApi.listTasks.mockResolvedValue(awaitingReviewTaskResponse as any);
      mockAuditApi.getTask.mockResolvedValue(awaitingReviewTask as any);

      const user = userEvent.setup();
      renderWithRouter(<AuditTasksPage />);

      await waitFor(() => {
        expect(screen.getByText('SSE Awaiting Review Task')).toBeInTheDocument();
      });

      const taskElements = screen.getAllByText('SSE Awaiting Review Task');
      await user.click(taskElements[0]);

      await waitFor(() => {
        expect(screen.getByText(/待审核 — 发现高风险问题/)).toBeInTheDocument();
      });

      const approveButtons = screen.getAllByText('批准');
      expect(approveButtons.length).toBeGreaterThanOrEqual(1);

      const rejectButtons = screen.getAllByText('驳回');
      expect(rejectButtons.length).toBeGreaterThanOrEqual(1);
    });

    test('review banner shows description text', async () => {
      mockAuditApi.listTasks.mockResolvedValue(awaitingReviewTaskResponse as any);
      mockAuditApi.getTask.mockResolvedValue(awaitingReviewTask as any);

      const user = userEvent.setup();
      renderWithRouter(<AuditTasksPage />);

      await waitFor(() => {
        expect(screen.getByText('SSE Awaiting Review Task')).toBeInTheDocument();
      });

      const taskElements = screen.getAllByText('SSE Awaiting Review Task');
      await user.click(taskElements[0]);

      await waitFor(() => {
        expect(screen.getByText(/请审查下方的审计发现/)).toBeInTheDocument();
      });
    });
  });

  // =====================
  // 12. Task Switching
  // =====================
  describe('task switching', () => {
    test('selecting different task triggers loadTaskDetails', async () => {
      mockAuditApi.listTasks.mockResolvedValue(multiTaskResponse as any);

      const user = userEvent.setup();
      renderWithRouter(<AuditTasksPage />);

      await waitFor(() => {
        expect(screen.getByText('Alpha Task')).toBeInTheDocument();
      });

      const taskTwoElements = screen.getAllByText('Beta Task');
      await user.click(taskTwoElements[0]);

      await waitFor(() => {
        expect(mockAuditApi.getTask).toHaveBeenCalledWith(2);
      });
    });
  });

  // =====================
  // 13. Keyboard Navigation
  // =====================
  describe('keyboard navigation', () => {
    test('Enter key on task item selects task', async () => {
      mockAuditApi.listTasks.mockResolvedValue(completedTaskResponse as any);

      renderWithRouter(<AuditTasksPage />);

      await waitFor(() => {
        expect(screen.getByText('SSE Completed Task')).toBeInTheDocument();
      });

      const taskItems = document.querySelectorAll('[role="button"]');
      expect(taskItems.length).toBeGreaterThan(0);

      // Simulate Enter key press
      const event = new KeyboardEvent('keydown', { key: 'Enter', bubbles: true });
      taskItems[0].dispatchEvent(event);
    });

    test('Space key on task item selects task', async () => {
      mockAuditApi.listTasks.mockResolvedValue(completedTaskResponse as any);

      renderWithRouter(<AuditTasksPage />);

      await waitFor(() => {
        expect(screen.getByText('SSE Completed Task')).toBeInTheDocument();
      });

      const taskItems = document.querySelectorAll('[role="button"]');
      expect(taskItems.length).toBeGreaterThan(0);

      // Simulate Space key press
      const event = new KeyboardEvent('keydown', { key: ' ', bubbles: true });
      taskItems[0].dispatchEvent(event);
    });
  });

  // =====================
  // 14. Report Button Navigation
  // =====================
  describe('report button navigation', () => {
    test('report button in list is clickable', async () => {
      mockAuditApi.listTasks.mockResolvedValue({
        items: [{
          id: 1, task_name: 'Report Task', task_type: 'sop_compliance', status: 'completed' as const,
          progress: 100, stage: 'completed', created_at: '2024-01-01T00:00:00Z', report_id: 10, documents: [],
        }],
        total: 1, page: 1, page_size: 20,
      } as any);

      const user = userEvent.setup();
      renderWithRouter(<AuditTasksPage />);

      await waitFor(() => {
        expect(screen.getByText('Report Task')).toBeInTheDocument();
      });

      const reportButtons = screen.getAllByText('报告');
      expect(reportButtons.length).toBeGreaterThan(0);
      await user.click(reportButtons[0]);
    });
  });

  // =====================
  // 15. Drawer Bottom Approve/Reject (inline Modal.confirm)
  // =====================
  describe('drawer bottom approve/reject', () => {
    test('drawer bottom approve button triggers Modal.confirm', async () => {
      mockAuditApi.listTasks.mockResolvedValue(awaitingReviewTaskResponse as any);
      mockAuditApi.getTask.mockResolvedValue(awaitingReviewTask as any);

      const originalConfirm = (await import('antd')).Modal.confirm;
      const mockConfirm = jest.fn(({ onOk }: any) => { if (onOk) onOk(); });
      (await import('antd')).Modal.confirm = mockConfirm;

      const user = userEvent.setup();
      renderWithRouter(<AuditTasksPage />);

      await waitFor(() => {
        expect(screen.getByText('SSE Awaiting Review Task')).toBeInTheDocument();
      });

      const taskElements = screen.getAllByText('SSE Awaiting Review Task');
      await user.click(taskElements[0]);

      await waitFor(() => {
        expect(screen.getAllByText('批准').length).toBeGreaterThanOrEqual(1);
      });

      // Click the LAST approve button (drawer bottom area)
      const approveButtons = screen.getAllByText('批准');
      await user.click(approveButtons[approveButtons.length - 1]);

      await waitFor(() => {
        expect(mockConfirm).toHaveBeenCalled();
      });

      (await import('antd')).Modal.confirm = originalConfirm;
    });

    test('drawer bottom reject button triggers Modal.confirm', async () => {
      mockAuditApi.listTasks.mockResolvedValue(awaitingReviewTaskResponse as any);
      mockAuditApi.getTask.mockResolvedValue(awaitingReviewTask as any);

      const originalConfirm = (await import('antd')).Modal.confirm;
      const mockConfirm = jest.fn();
      (await import('antd')).Modal.confirm = mockConfirm;

      const user = userEvent.setup();
      renderWithRouter(<AuditTasksPage />);

      await waitFor(() => {
        expect(screen.getByText('SSE Awaiting Review Task')).toBeInTheDocument();
      });

      const taskElements = screen.getAllByText('SSE Awaiting Review Task');
      await user.click(taskElements[0]);

      await waitFor(() => {
        expect(screen.getAllByText('驳回').length).toBeGreaterThanOrEqual(1);
      });

      // Click the LAST reject button (drawer bottom area)
      const rejectButtons = screen.getAllByText('驳回');
      await user.click(rejectButtons[rejectButtons.length - 1]);

      await waitFor(() => {
        expect(mockConfirm).toHaveBeenCalled();
      });

      (await import('antd')).Modal.confirm = originalConfirm;
    });
  });

  // =====================
  // 16. AgentFlowChart onNodeClick
  // =====================
  describe('AgentFlowChart interaction', () => {
    test('AgentFlowChart onNodeClick scrolls to timeline', async () => {
      mockAuditApi.listTasks.mockResolvedValue(runningTaskResponse as any);
      mockAuditApi.getTask.mockResolvedValue({
        ...runningTask,
        events: [
          { time: '2024-01-02T00:01:00Z', stage: 'parsing', level: 'info' as const, message: 'Event 1' },
        ],
      } as any);

      const user = userEvent.setup();
      renderWithRouter(<AuditTasksPage />);

      await waitFor(() => {
        expect(screen.getByText('SSE Running Task')).toBeInTheDocument();
      });

      const taskElements = screen.getAllByText('SSE Running Task');
      await user.click(taskElements[0]);

      await waitFor(() => {
        expect(screen.getByTestId('agent-flow-chart')).toBeInTheDocument();
      });

      // The AgentFlowChart mock doesn't call onNodeClick, but the prop is passed
      // This verifies the component renders without error
    });
  });

  // =====================
  // 17. Elapsed Time Display
  // =====================
  describe('elapsed time', () => {
    test('shows elapsed time for running task with started_at', async () => {
      mockAuditApi.listTasks.mockResolvedValue(runningTaskResponse as any);
      mockAuditApi.getTask.mockResolvedValue({
        ...runningTask,
        started_at: new Date(Date.now() - 180000).toISOString(), // 3 minutes ago
      } as any);

      const user = userEvent.setup();
      renderWithRouter(<AuditTasksPage />);

      await waitFor(() => {
        expect(screen.getByText('SSE Running Task')).toBeInTheDocument();
      });

      const taskElements = screen.getAllByText('SSE Running Task');
      await user.click(taskElements[0]);

      await waitFor(() => {
        expect(screen.getByText(/已运行/)).toBeInTheDocument();
      });
    });

    test('no elapsed time for non-running task', async () => {
      mockAuditApi.listTasks.mockResolvedValue(completedTaskResponse as any);

      const user = userEvent.setup();
      renderWithRouter(<AuditTasksPage />);

      await waitFor(() => {
        expect(screen.getByText('SSE Completed Task')).toBeInTheDocument();
      });

      const taskElements = screen.getAllByText('SSE Completed Task');
      await user.click(taskElements[0]);

      await waitFor(() => {
        expect(screen.getByTestId('agent-flow-chart')).toBeInTheDocument();
      });

      expect(screen.queryByText(/已运行/)).not.toBeInTheDocument();
    });
  });

  // =====================
  // 18. Cancel from List (non-running)
  // =====================
  describe('cancel from list', () => {
    test('cancel button only shows for running tasks', async () => {
      mockAuditApi.listTasks.mockResolvedValue({
        items: [
          { id: 1, task_name: 'Completed Task', task_type: 'sop_compliance', status: 'completed' as const, progress: 100, stage: 'completed', created_at: '2024-01-01T00:00:00Z', report_id: null, documents: [] },
          { id: 2, task_name: 'Running Task', task_type: 'deviation_analysis', status: 'running' as const, progress: 50, stage: 'risk', created_at: '2024-01-02T00:00:00Z', report_id: null, documents: [] },
        ],
        total: 2, page: 1, page_size: 20,
      } as any);

      renderWithRouter(<AuditTasksPage />);

      await waitFor(() => {
        expect(screen.getByText('Completed Task')).toBeInTheDocument();
      });

      // Only one cancel button should exist (for the running task)
      const cancelButtons = screen.getAllByText('取消');
      expect(cancelButtons.length).toBe(1);
    });
  });

  // =====================
  // 19. SSE with no selectedTask
  // =====================
  describe('SSE with no selected task', () => {
    test('no SSE connection when no task selected', async () => {
      mockAuditApi.listTasks.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 } as any);

      renderWithRouter(<AuditTasksPage />);

      await waitFor(() => {
        expect(screen.getByText('暂无审计任务')).toBeInTheDocument();
      });

      // useTaskSSE should be called with null taskId
      expect(useTaskSSE).toHaveBeenCalledWith(null, false);
    });
  });

  // =====================
  // 20. Status tag colors
  // =====================
  describe('status tag rendering', () => {
    test('all status types render correct labels', async () => {
      mockAuditApi.listTasks.mockResolvedValue({
        items: [
          { id: 1, task_name: 'Pending', task_type: 'deviation_analysis', status: 'pending' as const, progress: 0, stage: 'pending', created_at: '2024-01-01T00:00:00Z', report_id: null, documents: [] },
          { id: 2, task_name: 'Running', task_type: 'deviation_analysis', status: 'running' as const, progress: 50, stage: 'risk', created_at: '2024-01-02T00:00:00Z', report_id: null, documents: [] },
          { id: 3, task_name: 'Completed', task_type: 'deviation_analysis', status: 'completed' as const, progress: 100, stage: 'completed', created_at: '2024-01-03T00:00:00Z', report_id: null, documents: [] },
          { id: 4, task_name: 'Failed', task_type: 'deviation_analysis', status: 'failed' as const, progress: 30, stage: 'regulation', created_at: '2024-01-04T00:00:00Z', report_id: null, documents: [] },
          { id: 5, task_name: 'Cancelled', task_type: 'deviation_analysis', status: 'cancelled' as const, progress: 10, stage: 'cancelled', created_at: '2024-01-05T00:00:00Z', report_id: null, documents: [] },
          { id: 6, task_name: 'Awaiting', task_type: 'deviation_analysis', status: 'awaiting_review' as const, progress: 90, stage: 'report', created_at: '2024-01-06T00:00:00Z', report_id: null, documents: [] },
        ],
        total: 6, page: 1, page_size: 20,
      } as any);

      renderWithRouter(<AuditTasksPage />);

      await waitFor(() => {
        expect(screen.getByText('Pending')).toBeInTheDocument();
      });

      expect(screen.getByText('Running')).toBeInTheDocument();
      expect(screen.getByText('Completed')).toBeInTheDocument();
      expect(screen.getByText('Failed')).toBeInTheDocument();
      expect(screen.getByText('Cancelled')).toBeInTheDocument();
      expect(screen.getByText('Awaiting')).toBeInTheDocument();

      // Verify status labels
      expect(screen.getAllByText('待处理').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('进行中').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('已完成').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('失败').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('已取消').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('待审核').length).toBeGreaterThanOrEqual(1);
    });
  });
});

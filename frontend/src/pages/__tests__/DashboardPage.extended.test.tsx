import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';

import DashboardPage from '../DashboardPage';
import { auditApi, documentApi } from '../../services/api';

jest.setTimeout(15000);

jest.mock('../../services/api', () => ({
  documentApi: {
    list: jest.fn(),
  },
  auditApi: {
    getDashboard: jest.fn(),
    listTasks: jest.fn(),
  },
}));

const mockDocumentApi = documentApi as jest.Mocked<typeof documentApi>;
const mockAuditApi = auditApi as jest.Mocked<typeof auditApi>;

const renderWithRouter = (component: React.ReactElement) => {
  return render(<BrowserRouter>{component}</BrowserRouter>);
};

const defaultDocResult = {
  items: [],
  total: 5,
  page: 1,
  page_size: 1,
};

const defaultDashboard = {
  total_tasks: 3,
  task_counts: { pending: 1, running: 1, completed: 1, failed: 0 },
  severity_counts: { high: 2, medium: 1, low: 0 },
};

const defaultTasks = {
  items: [
    {
      id: 1,
      task_name: 'Deviation Review',
      task_type: 'deviation_analysis',
      status: 'completed' as const,
      progress: 100,
      stage: 'completed',
    },
  ],
  total: 1,
  page: 1,
  page_size: 20,
};

describe('DashboardPage extended tests', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockDocumentApi.list.mockResolvedValue(defaultDocResult);
    mockAuditApi.getDashboard.mockResolvedValue(defaultDashboard);
    mockAuditApi.listTasks.mockResolvedValue(defaultTasks);
  });

  test('displays all four statistic cards', async () => {
    renderWithRouter(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText('文档总数')).toBeInTheDocument();
    });

    expect(screen.getByText('审计任务')).toBeInTheDocument();
    expect(screen.getByText('已完成报告')).toBeInTheDocument();
    expect(screen.getByText('高风险发现')).toBeInTheDocument();
  });

  test('displays correct statistics values', async () => {
    renderWithRouter(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText('5')).toBeInTheDocument(); // totalDocuments
    });

    expect(screen.getByText('3')).toBeInTheDocument(); // totalTasks
    expect(screen.getByText('1')).toBeInTheDocument(); // completedTasks
    // highRiskFindings = 2
    expect(screen.getByText('2')).toBeInTheDocument();
  });

  test('shows running task alert when tasks are running', async () => {
    mockAuditApi.getDashboard.mockResolvedValue({
      total_tasks: 3,
      task_counts: { pending: 0, running: 2, completed: 1 },
      severity_counts: { high: 0, medium: 0, low: 0 },
    });

    renderWithRouter(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText(/2 个审计任务正在执行/)).toBeInTheDocument();
    });

    expect(screen.getByText(/可在工作台监控阶段进度/)).toBeInTheDocument();
  });

  test('does not show running task alert when no tasks are running', async () => {
    mockAuditApi.getDashboard.mockResolvedValue({
      total_tasks: 2,
      task_counts: { pending: 1, running: 0, completed: 1 },
      severity_counts: { high: 0, medium: 0, low: 0 },
    });

    renderWithRouter(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText('文档总数')).toBeInTheDocument();
    });

    expect(screen.queryByText(/个审计任务正在执行/)).not.toBeInTheDocument();
  });

  test('shows quick start card when documents exist', async () => {
    renderWithRouter(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getAllByText('开始审计').length).toBeGreaterThanOrEqual(1);
    });

    expect(screen.getByText(/选择文档，一键启动 GMP 合规审计/)).toBeInTheDocument();
  });

  test('hides quick start card when no documents', async () => {
    mockDocumentApi.list.mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 1,
    });

    renderWithRouter(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText('文档总数')).toBeInTheDocument();
    });

    // When no documents, the quick start card with "开始审计" should not appear
    // Note: "进入审计" in hero is always present, that's different
    expect(screen.queryByText(/选择文档，一键启动/)).not.toBeInTheDocument();
  });

  test('shows active task focus panel with running task', async () => {
    mockAuditApi.listTasks.mockResolvedValue({
      items: [
        {
          id: 10,
          task_name: 'Running Task',
          task_type: 'deviation_analysis',
          status: 'running' as const,
          progress: 60,
          stage: 'risk',
        },
        {
          id: 11,
          task_name: 'Pending Task',
          task_type: 'sop_compliance',
          status: 'pending' as const,
          progress: 0,
          stage: 'pending',
        },
      ],
      total: 2,
      page: 1,
      page_size: 20,
    });

    renderWithRouter(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getAllByText('Running Task').length).toBeGreaterThanOrEqual(1);
    });

    expect(screen.getByText('继续此任务')).toBeInTheDocument();
  });

  test('shows first task in focus when no running task', async () => {
    mockAuditApi.listTasks.mockResolvedValue({
      items: [
        {
          id: 5,
          task_name: 'Pending Task',
          task_type: 'sop_compliance',
          status: 'pending' as const,
          progress: 0,
          stage: 'pending',
        },
      ],
      total: 1,
      page: 1,
      page_size: 20,
    });

    renderWithRouter(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getAllByText('Pending Task').length).toBeGreaterThanOrEqual(1);
    });

    expect(screen.getByText('继续此任务')).toBeInTheDocument();
  });

  test('shows empty state when no tasks', async () => {
    mockAuditApi.listTasks.mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 20,
    });

    renderWithRouter(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText('暂无任务记录')).toBeInTheDocument();
    });
  });

  test('renders recent tasks table', async () => {
    mockAuditApi.listTasks.mockResolvedValue({
      items: [
        {
          id: 1,
          task_name: 'Task Alpha',
          task_type: 'deviation_analysis',
          status: 'completed' as const,
          progress: 100,
          stage: 'completed',
        },
        {
          id: 2,
          task_name: 'Task Beta',
          task_type: 'sop_compliance',
          status: 'running' as const,
          progress: 50,
          stage: 'risk',
        },
      ],
      total: 2,
      page: 1,
      page_size: 20,
    });

    renderWithRouter(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText('最近任务')).toBeInTheDocument();
    });

    expect(screen.getAllByText('Task Alpha').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Task Beta').length).toBeGreaterThan(0);
  });

  test('renders system overview section', async () => {
    renderWithRouter(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText('系统概览')).toBeInTheDocument();
    });

    expect(screen.getByText('审计流程')).toBeInTheDocument();
    expect(screen.getByText('数据链路')).toBeInTheDocument();
  });

  test('renders navigation buttons in hero', async () => {
    renderWithRouter(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText('进入审计')).toBeInTheDocument();
    });

    expect(screen.getByText('上传文档')).toBeInTheDocument();
    expect(screen.getByText('知识图谱')).toBeInTheDocument();
  });

  test('gracefully handles API errors', async () => {
    mockDocumentApi.list.mockRejectedValue(new Error('Network error'));
    mockAuditApi.getDashboard.mockRejectedValue(new Error('Server error'));
    mockAuditApi.listTasks.mockRejectedValue(new Error('Timeout'));

    renderWithRouter(<DashboardPage />);

    // Should still render the hero section
    await waitFor(() => {
      expect(screen.getByText('审计工作台')).toBeInTheDocument();
    });

    // Stats should be 0
    expect(screen.getByText('文档总数')).toBeInTheDocument();
  });

  test('gracefully handles partial API failures', async () => {
    mockDocumentApi.list.mockResolvedValue({
      items: [],
      total: 10,
      page: 1,
      page_size: 1,
    });
    mockAuditApi.getDashboard.mockRejectedValue(new Error('Dashboard error'));
    mockAuditApi.listTasks.mockResolvedValue(defaultTasks);

    renderWithRouter(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText('审计工作台')).toBeInTheDocument();
    });

    // Documents loaded successfully
    expect(screen.getByText('10')).toBeInTheDocument();
  });

  test('shows "查看全部" link in recent tasks', async () => {
    renderWithRouter(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText('查看全部')).toBeInTheDocument();
    });
  });

  test('shows "查看知识图谱" button in system overview', async () => {
    renderWithRouter(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText('查看知识图谱')).toBeInTheDocument();
    });
  });

  test('continue task button is clickable', async () => {
    const user = userEvent.setup();
    renderWithRouter(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText('继续此任务')).toBeInTheDocument();
    });

    await user.click(screen.getByText('继续此任务'));

    expect(screen.getByText('AuditBee')).toBeInTheDocument();
  });

  test('view all button is clickable', async () => {
    const user = userEvent.setup();
    renderWithRouter(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText('查看全部')).toBeInTheDocument();
    });

    await user.click(screen.getByText('查看全部'));

    expect(screen.getByText('AuditBee')).toBeInTheDocument();
  });

  test('view knowledge graph button is clickable', async () => {
    const user = userEvent.setup();
    renderWithRouter(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText('查看知识图谱')).toBeInTheDocument();
    });

    await user.click(screen.getByText('查看知识图谱'));

    expect(screen.getByText('AuditBee')).toBeInTheDocument();
  });

  test('renders AuditBee title', async () => {
    renderWithRouter(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText('AuditBee')).toBeInTheDocument();
    });
  });

  test('shows hero description', async () => {
    renderWithRouter(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText(/多智能体协作完成 GMP 合规审计/)).toBeInTheDocument();
    });
  });

  test('hero buttons are clickable', async () => {
    const user = userEvent.setup();
    renderWithRouter(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText('进入审计')).toBeInTheDocument();
    });

    // Click the audit button
    await user.click(screen.getByText('进入审计'));

    // Should not crash
    expect(screen.getByText('AuditBee')).toBeInTheDocument();
  });

  test('upload document button is clickable', async () => {
    const user = userEvent.setup();
    renderWithRouter(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText('上传文档')).toBeInTheDocument();
    });

    await user.click(screen.getByText('上传文档'));

    expect(screen.getByText('AuditBee')).toBeInTheDocument();
  });

  test('knowledge graph button is clickable', async () => {
    const user = userEvent.setup();
    renderWithRouter(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText('知识图谱')).toBeInTheDocument();
    });

    await user.click(screen.getByText('知识图谱'));

    expect(screen.getByText('AuditBee')).toBeInTheDocument();
  });

  test('limits recent tasks to 5', async () => {
    const manyTasks = Array.from({ length: 10 }, (_, i) => ({
      id: i + 1,
      task_name: `Task ${i + 1}`,
      task_type: 'deviation_analysis',
      status: 'completed' as const,
      progress: 100,
      stage: 'completed',
    }));

    mockAuditApi.listTasks.mockResolvedValue({
      items: manyTasks,
      total: 10,
      page: 1,
      page_size: 20,
    });

    renderWithRouter(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getAllByText('Task 1').length).toBeGreaterThanOrEqual(1);
    });

    // Task 5 should appear (in both focus panel and table potentially)
    expect(screen.getAllByText('Task 5').length).toBeGreaterThanOrEqual(1);
    // Task 6 should NOT appear at all (not in focus panel since Task 1 is active, not in table since limited to 5)
    expect(screen.queryByText('Task 6')).not.toBeInTheDocument();
  });

  test('renders with zero dashboard counts', async () => {
    mockAuditApi.getDashboard.mockResolvedValue({
      total_tasks: 0,
      task_counts: {},
      severity_counts: {},
    });
    mockDocumentApi.list.mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 1,
    });
    mockAuditApi.listTasks.mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 20,
    });

    renderWithRouter(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText('审计工作台')).toBeInTheDocument();
    });

    expect(screen.getByText('文档总数')).toBeInTheDocument();
    expect(screen.getAllByText('暂无任务记录').length).toBeGreaterThanOrEqual(1);
  });
});

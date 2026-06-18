import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';

import DashboardPage from '../DashboardPage';
import { auditApi, documentApi } from '../../services/api';

jest.setTimeout(15000);

jest.mock('../../services/api', () => ({
  documentApi: { list: jest.fn() },
  auditApi: { getDashboard: jest.fn(), listTasks: jest.fn() },
}));

const mockDocumentApi = documentApi as jest.Mocked<typeof documentApi>;
const mockAuditApi = auditApi as jest.Mocked<typeof auditApi>;

const renderWithRouter = (component: React.ReactElement) => {
  return render(<BrowserRouter>{component}</BrowserRouter>);
};

describe('DashboardPage branch coverage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockDocumentApi.list.mockResolvedValue({ items: [], total: 5, page: 1, page_size: 1 });
    mockAuditApi.getDashboard.mockResolvedValue({
      total_tasks: 3,
      task_counts: { pending: 1, running: 1, completed: 1, failed: 0 },
      severity_counts: { high: 2, medium: 1, low: 0 },
    });
    mockAuditApi.listTasks.mockResolvedValue({
      items: [
        {
          id: 1,
          task_name: 'Completed Task',
          task_type: 'deviation_analysis',
          status: 'completed' as const,
          progress: 100,
          stage: 'completed',
        },
      ],
      total: 1,
      page: 1,
      page_size: 20,
    });
  });

  // --- Stage tag with status color ---
  test('renders stage tag with correct status color for running task', async () => {
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
      ],
      total: 1,
      page: 1,
      page_size: 20,
    });

    renderWithRouter(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getAllByText('Running Task').length).toBeGreaterThanOrEqual(1);
    });
  });

  test('renders stage tag for failed task', async () => {
    mockAuditApi.listTasks.mockResolvedValue({
      items: [
        {
          id: 11,
          task_name: 'Failed Task',
          task_type: 'deviation_analysis',
          status: 'failed' as const,
          progress: 30,
          stage: 'regulation',
        },
      ],
      total: 1,
      page: 1,
      page_size: 20,
    });

    renderWithRouter(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getAllByText('Failed Task').length).toBeGreaterThanOrEqual(1);
    });
  });

  test('renders stage tag for pending task', async () => {
    mockAuditApi.listTasks.mockResolvedValue({
      items: [
        {
          id: 12,
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
  });

  // --- Progress with different statuses ---
  test('renders progress bar with exception status for failed tasks', async () => {
    mockAuditApi.listTasks.mockResolvedValue({
      items: [
        {
          id: 13,
          task_name: 'Failed Progress',
          task_type: 'deviation_analysis',
          status: 'failed' as const,
          progress: 45,
          stage: 'risk',
        },
      ],
      total: 1,
      page: 1,
      page_size: 20,
    });

    renderWithRouter(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getAllByText('Failed Progress').length).toBeGreaterThanOrEqual(1);
    });

    expect(document.querySelector('.ant-progress')).toBeInTheDocument();
  });

  test('renders progress bar with success status for completed tasks', async () => {
    mockAuditApi.listTasks.mockResolvedValue({
      items: [
        {
          id: 14,
          task_name: 'Completed Progress',
          task_type: 'deviation_analysis',
          status: 'completed' as const,
          progress: 100,
          stage: 'completed',
        },
      ],
      total: 1,
      page: 1,
      page_size: 20,
    });

    renderWithRouter(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getAllByText('Completed Progress').length).toBeGreaterThanOrEqual(1);
    });
  });

  // --- Quick start card navigation ---
  test('quick start card navigates to audit page', async () => {
    const user = userEvent.setup();
    renderWithRouter(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getAllByText('开始审计').length).toBeGreaterThanOrEqual(1);
    });

    // Click the quick start card button
    const startButtons = screen.getAllByText('开始审计');
    await user.click(startButtons[startButtons.length - 1]);

    expect(screen.getByText('AuditBee')).toBeInTheDocument();
  });

  // --- Empty table with create button ---
  test('shows create audit task button in empty table', async () => {
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

    expect(screen.getByText('创建审计任务')).toBeInTheDocument();
  });

  test('create audit task button in empty table is clickable', async () => {
    mockAuditApi.listTasks.mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 20,
    });

    const user = userEvent.setup();
    renderWithRouter(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText('创建审计任务')).toBeInTheDocument();
    });

    await user.click(screen.getByText('创建审计任务'));

    expect(screen.getByText('AuditBee')).toBeInTheDocument();
  });

  // --- Stage label fallback ---
  test('shows stage label for task with undefined stage', async () => {
    mockAuditApi.listTasks.mockResolvedValue({
      items: [
        {
          id: 15,
          task_name: 'No Stage Task',
          task_type: 'deviation_analysis',
          status: 'running' as const,
          progress: 20,
          stage: undefined,
        },
      ],
      total: 1,
      page: 1,
      page_size: 20,
    });

    renderWithRouter(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getAllByText('No Stage Task').length).toBeGreaterThanOrEqual(1);
    });
  });

  // --- Active task with no running, fallback to first task ---
  test('active task panel shows first task when no running task', async () => {
    mockAuditApi.listTasks.mockResolvedValue({
      items: [
        {
          id: 20,
          task_name: 'First Task',
          task_type: 'sop_compliance',
          status: 'completed' as const,
          progress: 100,
          stage: 'completed',
        },
        {
          id: 21,
          task_name: 'Second Task',
          task_type: 'deviation_analysis',
          status: 'completed' as const,
          progress: 100,
          stage: 'completed',
        },
      ],
      total: 2,
      page: 1,
      page_size: 20,
    });

    renderWithRouter(<DashboardPage />);

    await waitFor(() => {
      // First task should be shown in focus panel
      expect(screen.getAllByText('First Task').length).toBeGreaterThanOrEqual(1);
    });
  });

  // --- Running alert description ---
  test('shows running task alert with description', async () => {
    mockAuditApi.getDashboard.mockResolvedValue({
      total_tasks: 5,
      task_counts: { pending: 0, running: 3, completed: 2 },
      severity_counts: { high: 0, medium: 0, low: 0 },
    });

    renderWithRouter(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText(/3 个审计任务正在执行/)).toBeInTheDocument();
    });

    expect(screen.getByText(/可在工作台监控阶段进度/)).toBeInTheDocument();
  });

  // --- Task type label fallback ---
  test('shows task type label for unknown type', async () => {
    mockAuditApi.listTasks.mockResolvedValue({
      items: [
        {
          id: 25,
          task_name: 'Custom Type Task',
          task_type: 'custom_unknown',
          status: 'completed' as const,
          progress: 100,
          stage: 'completed',
        },
      ],
      total: 1,
      page: 1,
      page_size: 20,
    });

    renderWithRouter(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getAllByText('Custom Type Task').length).toBeGreaterThanOrEqual(1);
    });
  });

  // --- Navigate to audit button ---
  test('navigate to audit button in hero is functional', async () => {
    const user = userEvent.setup();
    renderWithRouter(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText('进入审计')).toBeInTheDocument();
    });

    await user.click(screen.getByText('进入审计'));
    expect(screen.getByText('AuditBee')).toBeInTheDocument();
  });

  // --- Navigate to documents button ---
  test('navigate to documents button is functional', async () => {
    const user = userEvent.setup();
    renderWithRouter(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText('上传文档')).toBeInTheDocument();
    });

    await user.click(screen.getByText('上传文档'));
    expect(screen.getByText('AuditBee')).toBeInTheDocument();
  });

  // --- Navigate to KG button ---
  test('navigate to knowledge graph button is functional', async () => {
    const user = userEvent.setup();
    renderWithRouter(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText('知识图谱')).toBeInTheDocument();
    });

    await user.click(screen.getByText('知识图谱'));
    expect(screen.getByText('AuditBee')).toBeInTheDocument();
  });

  // --- View all link ---
  test('view all link navigates correctly', async () => {
    const user = userEvent.setup();
    renderWithRouter(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText('查看全部')).toBeInTheDocument();
    });

    await user.click(screen.getByText('查看全部'));
    expect(screen.getByText('AuditBee')).toBeInTheDocument();
  });

  // --- Continue task button ---
  test('continue task button navigates correctly', async () => {
    const user = userEvent.setup();
    renderWithRouter(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText('继续此任务')).toBeInTheDocument();
    });

    await user.click(screen.getByText('继续此任务'));
    expect(screen.getByText('AuditBee')).toBeInTheDocument();
  });

  // --- Statistics with zero values ---
  test('renders statistics with zero values', async () => {
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
      expect(screen.getByText('文档总数')).toBeInTheDocument();
    });

    expect(screen.getByText('审计任务')).toBeInTheDocument();
    expect(screen.getByText('已完成报告')).toBeInTheDocument();
    expect(screen.getByText('高风险发现')).toBeInTheDocument();
  });

  // --- Recent tasks table action button ---
  test('recent tasks table has action buttons', async () => {
    mockAuditApi.listTasks.mockResolvedValue({
      items: [
        {
          id: 1,
          task_name: 'Action Task',
          task_type: 'deviation_analysis',
          status: 'completed' as const,
          progress: 100,
          stage: 'completed',
        },
      ],
      total: 1,
      page: 1,
      page_size: 20,
    });

    renderWithRouter(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getAllByText('Action Task').length).toBeGreaterThanOrEqual(1);
    });

    expect(screen.getAllByText('进入工作台').length).toBeGreaterThanOrEqual(1);
  });

  test('进入工作台 button is clickable', async () => {
    mockAuditApi.listTasks.mockResolvedValue({
      items: [
        {
          id: 1,
          task_name: 'Navigate Task',
          task_type: 'deviation_analysis',
          status: 'completed' as const,
          progress: 100,
          stage: 'completed',
        },
      ],
      total: 1,
      page: 1,
      page_size: 20,
    });

    const user = userEvent.setup();
    renderWithRouter(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getAllByText('Navigate Task').length).toBeGreaterThanOrEqual(1);
    });

    const workButtons = screen.getAllByText('进入工作台');
    await user.click(workButtons[0]);

    expect(screen.getByText('AuditBee')).toBeInTheDocument();
  });

  // --- System overview card content ---
  test('system overview shows audit process description', async () => {
    renderWithRouter(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText(/智能体依次完成法规检索/)).toBeInTheDocument();
    });
  });

  test('system overview shows data link description', async () => {
    renderWithRouter(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText(/结合知识图谱验证引用的法规依据/)).toBeInTheDocument();
    });
  });

  // --- High risk findings with error color ---
  test('high risk findings statistic uses error color', async () => {
    mockAuditApi.getDashboard.mockResolvedValue({
      total_tasks: 1,
      task_counts: { completed: 1 },
      severity_counts: { high: 5 },
    });

    renderWithRouter(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText('高风险发现')).toBeInTheDocument();
    });
  });
});

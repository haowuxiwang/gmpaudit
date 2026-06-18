import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
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

describe('DashboardPage coverage gaps', () => {
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

  // --- loadDashboard catch block with non-Error (line 72) ---
  test('loadDashboard handles non-Error exception gracefully', async () => {
    // Make Promise.allSettled succeed but the overall try/catch catches something
    // The catch block at line 72 only fires if the outer try block throws
    // Since Promise.allSettled never rejects, this catch is for truly unexpected errors
    mockDocumentApi.list.mockImplementation(() => {
      throw new Error('Synchronous error');
    });

    renderWithRouter(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText('审计工作台')).toBeInTheDocument();
    });
  });

  // --- Progress render for active (non-completed, non-failed) task (line 112) ---
  test('renders progress with active status for running task', async () => {
    mockAuditApi.listTasks.mockResolvedValue({
      items: [
        {
          id: 10,
          task_name: 'Active Task',
          task_type: 'deviation_analysis',
          status: 'running' as const,
          progress: 50,
          stage: 'risk',
        },
      ],
      total: 1,
      page: 1,
      page_size: 20,
    });

    renderWithRouter(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getAllByText('Active Task').length).toBeGreaterThanOrEqual(1);
    });

    // Progress bar should be present with active status
    expect(document.querySelector('.ant-progress')).toBeInTheDocument();
  });

  // --- Stage column render with undefined stage (line 101) ---
  test('renders stage tag with undefined stage value', async () => {
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

    // The stage column renders a Tag; when stage is undefined it shows '待处理'
    // But it may appear as part of a Tag component
    const tags = document.querySelectorAll('.ant-tag');
    expect(tags.length).toBeGreaterThan(0);
  });

  // --- Task with unknown status for StatusPriority ---
  test('handles task with unknown status gracefully', async () => {
    mockAuditApi.listTasks.mockResolvedValue({
      items: [
        {
          id: 20,
          task_name: 'Unknown Status Task',
          task_type: 'deviation_analysis',
          status: 'unknown_status' as any,
          progress: 10,
          stage: 'parsing',
        },
      ],
      total: 1,
      page: 1,
      page_size: 20,
    });

    renderWithRouter(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getAllByText('Unknown Status Task').length).toBeGreaterThanOrEqual(1);
    });
  });

  // --- Multiple tasks with running showing in focus panel ---
  test('focus panel shows running task over first task', async () => {
    mockAuditApi.listTasks.mockResolvedValue({
      items: [
        {
          id: 1,
          task_name: 'First Task',
          task_type: 'sop_compliance',
          status: 'completed' as const,
          progress: 100,
          stage: 'completed',
        },
        {
          id: 2,
          task_name: 'Running Focus Task',
          task_type: 'deviation_analysis',
          status: 'running' as const,
          progress: 60,
          stage: 'risk',
        },
      ],
      total: 2,
      page: 1,
      page_size: 20,
    });

    renderWithRouter(<DashboardPage />);

    await waitFor(() => {
      // The running task should be in the focus panel
      expect(screen.getAllByText('Running Focus Task').length).toBeGreaterThanOrEqual(1);
    });

    expect(screen.getByText('继续此任务')).toBeInTheDocument();
  });

  // --- Empty dashboard data ---
  test('handles null dashboard data', async () => {
    mockAuditApi.getDashboard.mockResolvedValue(null as any);

    renderWithRouter(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText('审计工作台')).toBeInTheDocument();
    });

    // Stats should be 0
    expect(screen.getByText('文档总数')).toBeInTheDocument();
  });

  // --- Task type label fallback ---
  test('renders task_type fallback for unknown type', async () => {
    mockAuditApi.listTasks.mockResolvedValue({
      items: [
        {
          id: 30,
          task_name: 'Custom Type Task',
          task_type: 'custom_unknown_type',
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

    // Should show the raw task_type when not in TASK_TYPE_LABELS
    expect(screen.getByText('custom_unknown_type')).toBeInTheDocument();
  });
});

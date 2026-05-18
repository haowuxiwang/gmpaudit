import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';

import DashboardPage from '../DashboardPage';
import { auditApi, documentApi } from '../../services/api';

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

describe('DashboardPage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('shows the control room hero', async () => {
    mockDocumentApi.list.mockResolvedValue({
      items: [],
      total: 3,
      page: 1,
      page_size: 1,
    });
    mockAuditApi.getDashboard.mockResolvedValue({
      total_tasks: 1,
      task_counts: { pending: 0, running: 1, completed: 0, failed: 0 },
      severity_counts: { high: 0, medium: 0, low: 0 },
    });
    mockAuditApi.listTasks.mockResolvedValue({
      items: [
        {
          id: 7,
          task_name: 'Deviation review',
          task_type: 'deviation_analysis',
          status: 'running',
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
      expect(screen.getByText('审计工作台')).toBeInTheDocument();
    });

    expect(
      screen.getByText(/多智能体协作完成/i),
    ).toBeInTheDocument();
    expect(screen.getByText('继续此任务')).toBeInTheDocument();
  });

  test('renders recent sessions table', async () => {
    mockDocumentApi.list.mockResolvedValue({
      items: [],
      total: 42,
      page: 1,
      page_size: 1,
    });
    mockAuditApi.getDashboard.mockResolvedValue({
      total_tasks: 2,
      task_counts: { pending: 1, running: 0, completed: 1, failed: 0 },
      severity_counts: { high: 2, medium: 3, low: 1 },
    });
    mockAuditApi.listTasks.mockResolvedValue({
      items: [
        {
          id: 1,
          task_name: 'SOP review',
          task_type: 'sop_compliance',
          status: 'completed',
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
      expect(screen.getByText('文档总数')).toBeInTheDocument();
    });

    expect(screen.getByText('最近任务')).toBeInTheDocument();
    expect(screen.getAllByText('SOP review').length).toBeGreaterThan(0);
    expect(screen.getByText('进入工作台')).toBeInTheDocument();
  });
});

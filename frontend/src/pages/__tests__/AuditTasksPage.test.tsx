import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import AuditTasksPage from '../AuditTasksPage';
import { auditApi } from '../../services/api';

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

jest.mock('../../services/api', () => ({
  auditApi: {
    listTasks: jest.fn().mockResolvedValue([]),
    createTask: jest.fn(),
    runTask: jest.fn(),
    cancelTask: jest.fn(),
    getTask: jest.fn(),
  },
}));

const mockAuditApi = auditApi as jest.Mocked<typeof auditApi>;

const renderWithRouter = (component: React.ReactElement) => {
  return render(<BrowserRouter>{component}</BrowserRouter>);
};

describe('AuditTasksPage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockAuditApi.listTasks.mockResolvedValue([]);
  });

  test('renders page title', async () => {
    renderWithRouter(<AuditTasksPage />);
    await waitFor(() => {
      expect(screen.getByText(/审计任务/)).toBeInTheDocument();
    });
  });

  test('renders empty state', async () => {
    renderWithRouter(<AuditTasksPage />);
    await waitFor(() => {
      expect(screen.getByText(/审计任务/)).toBeInTheDocument();
    });
  });

  test('loads tasks on mount', async () => {
    renderWithRouter(<AuditTasksPage />);
    await waitFor(() => {
      expect(mockAuditApi.listTasks).toHaveBeenCalled();
    });
  });
});

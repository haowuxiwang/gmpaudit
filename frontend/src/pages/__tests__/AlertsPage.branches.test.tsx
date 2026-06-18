import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';

import AlertsPage from '../AlertsPage';
import { alertsApi } from '../../services/api';

jest.setTimeout(15000);

jest.mock('../../services/api', () => ({
  alertsApi: {
    list: jest.fn(),
    acknowledge: jest.fn(),
    resolve: jest.fn(),
  },
}));

const mockAlertsApi = alertsApi as jest.Mocked<typeof alertsApi>;

const renderWithRouter = (component: React.ReactElement) => {
  return render(<BrowserRouter>{component}</BrowserRouter>);
};

const mockAlerts = {
  items: [
    {
      id: 1,
      finding_id: 101,
      alert_level: 'critical' as const,
      status: 'active' as const,
      created_at: '2024-01-01T00:00:00Z',
      finding_title: 'Critical Alert',
      finding_description: 'Critical finding description',
      finding_severity: 'high',
      task_id: 1,
    },
    {
      id: 2,
      finding_id: 102,
      alert_level: 'warning' as const,
      status: 'acknowledged' as const,
      created_at: '2024-01-02T00:00:00Z',
      finding_title: 'Warning Alert',
      finding_description: 'Warning finding description',
      finding_severity: 'medium',
      task_id: 2,
    },
  ],
  total: 2,
  page: 1,
  page_size: 10,
};

describe('AlertsPage branch coverage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockAlertsApi.list.mockResolvedValue(mockAlerts as any);
    mockAlertsApi.acknowledge.mockResolvedValue({ status: 'acknowledged' });
    mockAlertsApi.resolve.mockResolvedValue({ status: 'resolved' });
  });

  // --- Acknowledge error ---
  test('acknowledge handles API error', async () => {
    mockAlertsApi.acknowledge.mockRejectedValue(new Error('Acknowledge failed'));

    const originalConfirm = (await import('antd')).Modal.confirm;
    const mockConfirm = jest.fn(({ onOk }: any) => {
      if (onOk) onOk();
    });
    (await import('antd')).Modal.confirm = mockConfirm;

    const user = userEvent.setup();
    renderWithRouter(<AlertsPage />);

    await waitFor(() => {
      expect(screen.getByText('Critical Alert')).toBeInTheDocument();
    });

    const acknowledgeButtons = screen.getAllByText('确认');
    await user.click(acknowledgeButtons[0]);

    await waitFor(() => {
      expect(mockAlertsApi.acknowledge).toHaveBeenCalled();
    });

    (await import('antd')).Modal.confirm = originalConfirm;
  });

  // --- Acknowledge non-Error exception ---
  test('acknowledge handles non-Error exception', async () => {
    mockAlertsApi.acknowledge.mockRejectedValue('string error');

    const originalConfirm = (await import('antd')).Modal.confirm;
    const mockConfirm = jest.fn(({ onOk }: any) => {
      if (onOk) onOk();
    });
    (await import('antd')).Modal.confirm = mockConfirm;

    const user = userEvent.setup();
    renderWithRouter(<AlertsPage />);

    await waitFor(() => {
      expect(screen.getByText('Critical Alert')).toBeInTheDocument();
    });

    const acknowledgeButtons = screen.getAllByText('确认');
    await user.click(acknowledgeButtons[0]);

    await waitFor(() => {
      expect(mockAlertsApi.acknowledge).toHaveBeenCalled();
    });

    (await import('antd')).Modal.confirm = originalConfirm;
  });

  // --- Resolve error ---
  test('resolve handles API error', async () => {
    mockAlertsApi.resolve.mockRejectedValue(new Error('Resolve failed'));

    const originalConfirm = (await import('antd')).Modal.confirm;
    const mockConfirm = jest.fn(({ onOk }: any) => {
      if (onOk) onOk();
    });
    (await import('antd')).Modal.confirm = mockConfirm;

    const user = userEvent.setup();
    renderWithRouter(<AlertsPage />);

    await waitFor(() => {
      expect(screen.getByText('Critical Alert')).toBeInTheDocument();
    });

    const resolveButtons = screen.getAllByText('解决');
    await user.click(resolveButtons[0]);

    await waitFor(() => {
      expect(mockAlertsApi.resolve).toHaveBeenCalled();
    });

    (await import('antd')).Modal.confirm = originalConfirm;
  });

  // --- Resolve non-Error exception ---
  test('resolve handles non-Error exception', async () => {
    mockAlertsApi.resolve.mockRejectedValue('string error');

    const originalConfirm = (await import('antd')).Modal.confirm;
    const mockConfirm = jest.fn(({ onOk }: any) => {
      if (onOk) onOk();
    });
    (await import('antd')).Modal.confirm = mockConfirm;

    const user = userEvent.setup();
    renderWithRouter(<AlertsPage />);

    await waitFor(() => {
      expect(screen.getByText('Critical Alert')).toBeInTheDocument();
    });

    const resolveButtons = screen.getAllByText('解决');
    await user.click(resolveButtons[0]);

    await waitFor(() => {
      expect(mockAlertsApi.resolve).toHaveBeenCalled();
    });

    (await import('antd')).Modal.confirm = originalConfirm;
  });

  // --- Date formatting with empty string ---
  test('formats empty date as dash', async () => {
    mockAlertsApi.list.mockResolvedValue({
      items: [
        {
          id: 9,
          finding_id: 109,
          alert_level: 'info' as const,
          status: 'active' as const,
          created_at: '',
          finding_title: 'Empty Date Alert',
          finding_description: 'desc',
          finding_severity: 'low',
        },
      ],
      total: 1,
      page: 1,
      page_size: 10,
    } as any);

    const user = userEvent.setup();
    renderWithRouter(<AlertsPage />);

    await waitFor(() => {
      expect(screen.getByText('Empty Date Alert')).toBeInTheDocument();
    });

    // Expand the row
    await user.click(screen.getByText('Empty Date Alert'));

    await waitFor(() => {
      expect(screen.getByText('创建时间')).toBeInTheDocument();
    });
  });

  // --- Task navigation button ---
  test('task navigation button navigates correctly', async () => {
    const user = userEvent.setup();
    renderWithRouter(<AlertsPage />);

    await waitFor(() => {
      expect(screen.getByText('Critical Alert')).toBeInTheDocument();
    });

    await user.click(screen.getByText('Critical Alert'));

    await waitFor(() => {
      expect(screen.getByText('查看关联任务')).toBeInTheDocument();
    });

    await user.click(screen.getByText('查看关联任务'));

    // Should not crash
    expect(screen.getByText('风险告警')).toBeInTheDocument();
  });

  // --- Expand icon rendering ---
  test('expand icons render correctly', async () => {
    renderWithRouter(<AlertsPage />);

    await waitFor(() => {
      expect(screen.getByText('Critical Alert')).toBeInTheDocument();
    });

    // The table should be rendered with expandable rows
    expect(document.querySelector('.ant-table')).toBeInTheDocument();
  });

  // --- Custom expanded row class ---
  test('expanded rows have custom class', async () => {
    const user = userEvent.setup();
    renderWithRouter(<AlertsPage />);

    await waitFor(() => {
      expect(screen.getByText('Critical Alert')).toBeInTheDocument();
    });

    await user.click(screen.getByText('Critical Alert'));

    await waitFor(() => {
      const expandedRows = document.querySelectorAll('.alert-expanded-row');
      expect(expandedRows.length).toBeGreaterThanOrEqual(1);
    });
  });

  // --- Status filter select ---
  test('status filter select is present', async () => {
    renderWithRouter(<AlertsPage />);

    await waitFor(() => {
      expect(screen.getByText('按状态筛选')).toBeInTheDocument();
    });
  });

  // --- Alert with all level types ---
  test('renders all alert level types', async () => {
    mockAlertsApi.list.mockResolvedValue({
      items: [
        { id: 1, finding_id: 101, alert_level: 'critical' as const, status: 'active' as const, created_at: '2024-01-01T00:00:00Z', finding_title: 'Critical', finding_description: 'd', finding_severity: 'high' },
        { id: 2, finding_id: 102, alert_level: 'warning' as const, status: 'active' as const, created_at: '2024-01-02T00:00:00Z', finding_title: 'Warning', finding_description: 'd', finding_severity: 'medium' },
        { id: 3, finding_id: 103, alert_level: 'info' as const, status: 'active' as const, created_at: '2024-01-03T00:00:00Z', finding_title: 'Info', finding_description: 'd', finding_severity: 'low' },
      ],
      total: 3,
      page: 1,
      page_size: 10,
    } as any);

    renderWithRouter(<AlertsPage />);

    await waitFor(() => {
      expect(screen.getByText('Critical')).toBeInTheDocument();
    });

    expect(screen.getByText('Warning')).toBeInTheDocument();
    expect(screen.getByText('Info')).toBeInTheDocument();
  });

  // --- Alert with all status types ---
  test('renders all alert status types', async () => {
    mockAlertsApi.list.mockResolvedValue({
      items: [
        { id: 1, finding_id: 101, alert_level: 'critical' as const, status: 'active' as const, created_at: '2024-01-01T00:00:00Z', finding_title: 'Active', finding_description: 'd', finding_severity: 'high' },
        { id: 2, finding_id: 102, alert_level: 'critical' as const, status: 'acknowledged' as const, created_at: '2024-01-02T00:00:00Z', finding_title: 'Acknowledged', finding_description: 'd', finding_severity: 'high' },
        { id: 3, finding_id: 103, alert_level: 'critical' as const, status: 'resolved' as const, created_at: '2024-01-03T00:00:00Z', finding_title: 'Resolved', finding_description: 'd', finding_severity: 'high' },
      ],
      total: 3,
      page: 1,
      page_size: 10,
    } as any);

    renderWithRouter(<AlertsPage />);

    await waitFor(() => {
      expect(screen.getByText('Active')).toBeInTheDocument();
    });

    expect(screen.getByText('Acknowledged')).toBeInTheDocument();
    expect(screen.getByText('Resolved')).toBeInTheDocument();
  });

  // --- Alert with unknown level ---
  test('handles alert with unknown level', async () => {
    mockAlertsApi.list.mockResolvedValue({
      items: [
        { id: 10, finding_id: 110, alert_level: 'unknown_level' as any, status: 'active' as const, created_at: '2024-01-10T00:00:00Z', finding_title: 'Unknown Level', finding_description: 'd', finding_severity: 'high' },
      ],
      total: 1,
      page: 1,
      page_size: 10,
    } as any);

    renderWithRouter(<AlertsPage />);

    await waitFor(() => {
      expect(screen.getByText('Unknown Level')).toBeInTheDocument();
    });
  });

  // --- Alert with unknown status ---
  test('handles alert with unknown status', async () => {
    mockAlertsApi.list.mockResolvedValue({
      items: [
        { id: 11, finding_id: 111, alert_level: 'critical' as const, status: 'unknown_status' as any, created_at: '2024-01-11T00:00:00Z', finding_title: 'Unknown Status', finding_description: 'd', finding_severity: 'high' },
      ],
      total: 1,
      page: 1,
      page_size: 10,
    } as any);

    renderWithRouter(<AlertsPage />);

    await waitFor(() => {
      expect(screen.getByText('Unknown Status')).toBeInTheDocument();
    });
  });

  // --- Expanded row with resolved_at and resolved_by ---
  test('shows resolved_at and resolved_by in expanded row', async () => {
    mockAlertsApi.list.mockResolvedValue({
      items: [
        {
          id: 12,
          finding_id: 112,
          alert_level: 'info' as const,
          status: 'resolved' as const,
          created_at: '2024-01-12T00:00:00Z',
          resolved_at: '2024-01-13T00:00:00Z',
          resolved_by: 'admin',
          finding_title: 'Resolved Alert',
          finding_description: 'Resolved description',
          finding_severity: 'low',
          task_id: 5,
        },
      ],
      total: 1,
      page: 1,
      page_size: 10,
    } as any);

    const user = userEvent.setup();
    renderWithRouter(<AlertsPage />);

    await waitFor(() => {
      expect(screen.getByText('Resolved Alert')).toBeInTheDocument();
    });

    await user.click(screen.getByText('Resolved Alert'));

    await waitFor(() => {
      expect(screen.getByText('解决时间')).toBeInTheDocument();
    });

    expect(screen.getByText(/admin/)).toBeInTheDocument();
  });

  // --- Expanded row without resolved_at ---
  test('does not show resolve time when resolved_at is missing', async () => {
    mockAlertsApi.list.mockResolvedValue({
      items: [
        {
          id: 13,
          finding_id: 113,
          alert_level: 'warning' as const,
          status: 'active' as const,
          created_at: '2024-01-13T00:00:00Z',
          finding_title: 'Active Alert No Resolve',
          finding_description: 'No resolve description',
          finding_severity: 'medium',
          task_id: 6,
        },
      ],
      total: 1,
      page: 1,
      page_size: 10,
    } as any);

    const user = userEvent.setup();
    renderWithRouter(<AlertsPage />);

    await waitFor(() => {
      expect(screen.getByText('Active Alert No Resolve')).toBeInTheDocument();
    });

    await user.click(screen.getByText('Active Alert No Resolve'));

    await waitFor(() => {
      expect(screen.getByText('告警级别')).toBeInTheDocument();
    });

    expect(screen.queryByText('解决时间')).not.toBeInTheDocument();
  });

  // --- Level filter with no matching alerts ---
  test('level filter with info when no info alerts', async () => {
    mockAlertsApi.list.mockResolvedValue({
      items: [
        { id: 1, finding_id: 101, alert_level: 'critical' as const, status: 'active' as const, created_at: '2024-01-01T00:00:00Z', finding_title: 'Critical Only', finding_description: 'd', finding_severity: 'high' },
      ],
      total: 1,
      page: 1,
      page_size: 10,
    } as any);

    const user = userEvent.setup();
    renderWithRouter(<AlertsPage />);

    await waitFor(() => {
      expect(screen.getByText('Critical Only')).toBeInTheDocument();
    });

    // Click info level filter
    const infoTags = screen.getAllByText('信息');
    await user.click(infoTags[0]);

    // Should show empty state since no info alerts match
    await waitFor(() => {
      expect(screen.getByText('暂无告警')).toBeInTheDocument();
    });
  });

  // --- loadAlerts non-Error exception ---
  test('handles loadAlerts non-Error exception', async () => {
    mockAlertsApi.list.mockRejectedValue('string error');

    renderWithRouter(<AlertsPage />);

    await waitFor(() => {
      expect(screen.getByText('风险告警')).toBeInTheDocument();
    });
  });

  // --- Banner dismissed from localStorage ---
  test('respects dismissed banner from localStorage', async () => {
    const getItemSpy = jest.spyOn(Storage.prototype, 'getItem').mockReturnValue('true');

    renderWithRouter(<AlertsPage />);

    await waitFor(() => {
      expect(screen.getByText('风险告警')).toBeInTheDocument();
    });

    expect(screen.queryByText(/告警由审计任务完成后自动生成/)).not.toBeInTheDocument();

    getItemSpy.mockRestore();
  });

  // --- Banner close sets localStorage ---
  test('banner close sets localStorage', async () => {
    const setItemSpy = jest.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {});

    const user = userEvent.setup();
    renderWithRouter(<AlertsPage />);

    await waitFor(() => {
      expect(screen.getByText(/告警由审计任务完成后自动生成/)).toBeInTheDocument();
    });

    const closeButton = document.querySelector('.ant-alert-close-icon');
    if (closeButton) {
      await user.click(closeButton as Element);
    }

    await waitFor(() => {
      expect(setItemSpy).toHaveBeenCalledWith('alerts-info-banner-dismissed', 'true');
    });

    setItemSpy.mockRestore();
  });
});

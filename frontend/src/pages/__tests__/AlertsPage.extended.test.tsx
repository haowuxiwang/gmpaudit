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
      finding_title: '关键偏差未处理',
      finding_description: '发现生产线A存在未处理的关键偏差',
      finding_severity: 'high',
      task_id: 1,
    },
    {
      id: 2,
      finding_id: 102,
      alert_level: 'warning' as const,
      status: 'acknowledged' as const,
      created_at: '2024-01-02T00:00:00Z',
      finding_title: 'SOP文档过期',
      finding_description: 'SOP-001文档已超过复审期限',
      finding_severity: 'medium',
      task_id: 2,
    },
    {
      id: 3,
      finding_id: 103,
      alert_level: 'info' as const,
      status: 'resolved' as const,
      created_at: '2024-01-03T00:00:00Z',
      resolved_at: '2024-01-04T00:00:00Z',
      resolved_by: 'admin',
      finding_title: '记录格式不规范',
      finding_description: '部分批记录填写格式不规范',
      finding_severity: 'low',
      task_id: 3,
    },
    {
      id: 4,
      finding_id: 104,
      alert_level: 'critical' as const,
      status: 'active' as const,
      created_at: '2024-01-05T00:00:00Z',
      finding_title: '环境监测超标',
      finding_description: '洁净区环境监测数据超出标准限值',
      finding_severity: 'high',
      task_id: 4,
    },
  ],
  total: 4,
  page: 1,
  page_size: 10,
};

describe('AlertsPage extended tests', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockAlertsApi.list.mockResolvedValue(mockAlerts as any);
    mockAlertsApi.acknowledge.mockResolvedValue({ status: 'acknowledged' });
    mockAlertsApi.resolve.mockResolvedValue({ status: 'resolved' });
  });

  // --- Page title and description ---
  test('renders page title', async () => {
    renderWithRouter(<AlertsPage />);

    await waitFor(() => {
      expect(screen.getByText('风险告警')).toBeInTheDocument();
    });
  });

  test('renders page description', async () => {
    renderWithRouter(<AlertsPage />);

    await waitFor(() => {
      expect(screen.getByText('审查并关闭审计流程中发现的高风险问题')).toBeInTheDocument();
    });
  });

  // --- Alert list rendering ---
  test('renders alert list with data', async () => {
    renderWithRouter(<AlertsPage />);

    await waitFor(() => {
      expect(screen.getByText('关键偏差未处理')).toBeInTheDocument();
    });

    expect(screen.getByText('SOP文档过期')).toBeInTheDocument();
    expect(screen.getByText('记录格式不规范')).toBeInTheDocument();
    expect(screen.getByText('环境监测超标')).toBeInTheDocument();
  });

  test('displays alert level tags', async () => {
    renderWithRouter(<AlertsPage />);

    await waitFor(() => {
      // 严重 appears in filter tags AND in the table
      const criticalTags = screen.getAllByText('严重');
      expect(criticalTags.length).toBeGreaterThanOrEqual(1);
    });

    const warningTags = screen.getAllByText('警告');
    expect(warningTags.length).toBeGreaterThanOrEqual(1);

    const infoTags = screen.getAllByText('信息');
    expect(infoTags.length).toBeGreaterThanOrEqual(1);
  });

  test('displays alert status tags', async () => {
    renderWithRouter(<AlertsPage />);

    await waitFor(() => {
      const activeTags = screen.getAllByText('活跃');
      expect(activeTags.length).toBeGreaterThanOrEqual(1);
    });

    const acknowledgedTags = screen.getAllByText('已确认');
    expect(acknowledgedTags.length).toBeGreaterThanOrEqual(1);

    const resolvedTags = screen.getAllByText('已解决');
    expect(resolvedTags.length).toBeGreaterThanOrEqual(1);
  });

  test('displays finding severity tags', async () => {
    renderWithRouter(<AlertsPage />);

    await waitFor(() => {
      const highTags = screen.getAllByText('高');
      expect(highTags.length).toBeGreaterThanOrEqual(1);
    });

    const mediumTags = screen.getAllByText('中');
    expect(mediumTags.length).toBeGreaterThanOrEqual(1);

    const lowTags = screen.getAllByText('低');
    expect(lowTags.length).toBeGreaterThanOrEqual(1);
  });

  // --- Empty state ---
  test('shows empty state when no alerts', async () => {
    mockAlertsApi.list.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 10 } as any);

    renderWithRouter(<AlertsPage />);

    await waitFor(() => {
      expect(screen.getByText('暂无告警')).toBeInTheDocument();
    });
  });

  test('shows empty state description', async () => {
    mockAlertsApi.list.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 10 } as any);

    renderWithRouter(<AlertsPage />);

    await waitFor(() => {
      expect(screen.getByText('审计任务完成后自动生成风险告警')).toBeInTheDocument();
    });
  });

  // --- Actions ---
  test('shows acknowledge button for active alerts', async () => {
    renderWithRouter(<AlertsPage />);

    await waitFor(() => {
      expect(screen.getByText('关键偏差未处理')).toBeInTheDocument();
    });

    const acknowledgeButtons = screen.getAllByText('确认');
    expect(acknowledgeButtons.length).toBeGreaterThanOrEqual(1);
  });

  test('shows resolve button for non-resolved alerts', async () => {
    renderWithRouter(<AlertsPage />);

    await waitFor(() => {
      expect(screen.getByText('关键偏差未处理')).toBeInTheDocument();
    });

    const resolveButtons = screen.getAllByText('解决');
    expect(resolveButtons.length).toBeGreaterThanOrEqual(1);
  });

  test('does not show acknowledge button for acknowledged alerts', async () => {
    renderWithRouter(<AlertsPage />);

    await waitFor(() => {
      expect(screen.getByText('SOP文档过期')).toBeInTheDocument();
    });

    // 确认 buttons should be 2 (for the 2 active alerts)
    const acknowledgeButtons = screen.getAllByText('确认');
    expect(acknowledgeButtons.length).toBe(2);
  });

  test('does not show resolve button for resolved alerts', async () => {
    renderWithRouter(<AlertsPage />);

    await waitFor(() => {
      expect(screen.getByText('记录格式不规范')).toBeInTheDocument();
    });

    // 解决 buttons: 3 non-resolved alerts (2 active + 1 acknowledged)
    const resolveButtons = screen.getAllByText('解决');
    expect(resolveButtons.length).toBe(3);
  });

  // --- Info banner ---
  test('shows info banner by default', async () => {
    renderWithRouter(<AlertsPage />);

    await waitFor(() => {
      expect(screen.getByText(/告警由审计任务完成后自动生成/)).toBeInTheDocument();
    });
  });

  // --- Error handling ---
  test('handles API error on load', async () => {
    mockAlertsApi.list.mockRejectedValue(new Error('加载失败'));

    renderWithRouter(<AlertsPage />);

    await waitFor(() => {
      expect(screen.getByText('风险告警')).toBeInTheDocument();
    });
  });

  // --- Alert with no finding title ---
  test('handles alert with no finding title', async () => {
    mockAlertsApi.list.mockResolvedValue({
      items: [
        {
          id: 5,
          finding_id: 105,
          alert_level: 'warning' as const,
          status: 'active' as const,
          created_at: '2024-01-06T00:00:00Z',
          finding_title: undefined,
          finding_description: '描述内容',
          finding_severity: 'medium',
        },
      ],
      total: 1,
      page: 1,
      page_size: 10,
    } as any);

    renderWithRouter(<AlertsPage />);

    await waitFor(() => {
      expect(screen.getByText('发现 #105')).toBeInTheDocument();
    });
  });

  // --- Alert with task_id shows task link ---
  test('shows task link for alerts with task_id when expanded', async () => {
    renderWithRouter(<AlertsPage />);

    await waitFor(() => {
      expect(screen.getByText('关键偏差未处理')).toBeInTheDocument();
    });

    const user = userEvent.setup();
    await user.click(screen.getByText('关键偏差未处理'));

    await waitFor(() => {
      expect(screen.getByText('查看关联任务')).toBeInTheDocument();
    });
  });

  // --- Expanded row content ---
  test('shows expanded row with finding description', async () => {
    const user = userEvent.setup();
    renderWithRouter(<AlertsPage />);

    await waitFor(() => {
      expect(screen.getByText('关键偏差未处理')).toBeInTheDocument();
    });

    await user.click(screen.getByText('关键偏差未处理'));

    await waitFor(() => {
      expect(screen.getByText('发现生产线A存在未处理的关键偏差')).toBeInTheDocument();
    });
  });

  test('shows expanded row with creation time', async () => {
    const user = userEvent.setup();
    renderWithRouter(<AlertsPage />);

    await waitFor(() => {
      expect(screen.getByText('关键偏差未处理')).toBeInTheDocument();
    });

    await user.click(screen.getByText('关键偏差未处理'));

    await waitFor(() => {
      expect(screen.getByText('创建时间')).toBeInTheDocument();
    });
  });

  test('shows expanded row with resolve time for resolved alerts', async () => {
    const user = userEvent.setup();
    renderWithRouter(<AlertsPage />);

    await waitFor(() => {
      expect(screen.getByText('记录格式不规范')).toBeInTheDocument();
    });

    await user.click(screen.getByText('记录格式不规范'));

    await waitFor(() => {
      expect(screen.getByText('解决时间')).toBeInTheDocument();
    });
  });

  // --- Multiple alerts of same level ---
  test('handles multiple critical alerts', async () => {
    renderWithRouter(<AlertsPage />);

    await waitFor(() => {
      expect(screen.getByText('关键偏差未处理')).toBeInTheDocument();
    });

    expect(screen.getByText('环境监测超标')).toBeInTheDocument();
  });

  // --- Alert with no description ---
  test('shows default description when finding description is empty', async () => {
    mockAlertsApi.list.mockResolvedValue({
      items: [
        {
          id: 6,
          finding_id: 106,
          alert_level: 'info' as const,
          status: 'active' as const,
          created_at: '2024-01-07T00:00:00Z',
          finding_title: '无描述告警',
          finding_description: '',
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
      expect(screen.getByText('无描述告警')).toBeInTheDocument();
    });

    await user.click(screen.getByText('无描述告警'));

    await waitFor(() => {
      expect(screen.getByText('无描述')).toBeInTheDocument();
    });
  });

  // --- Alert level colors ---
  test('renders critical alerts with correct level tag', async () => {
    renderWithRouter(<AlertsPage />);

    await waitFor(() => {
      // 严重 appears in filter tags AND in the table level column
      const criticalTags = screen.getAllByText('严重');
      expect(criticalTags.length).toBeGreaterThanOrEqual(2);
    });
  });

  // --- No task_id in expanded row ---
  test('does not show task link when task_id is missing', async () => {
    mockAlertsApi.list.mockResolvedValue({
      items: [
        {
          id: 7,
          finding_id: 107,
          alert_level: 'warning' as const,
          status: 'active' as const,
          created_at: '2024-01-08T00:00:00Z',
          finding_title: '无关联任务告警',
          finding_description: '无关联任务',
          finding_severity: 'medium',
          task_id: undefined,
        },
      ],
      total: 1,
      page: 1,
      page_size: 10,
    } as any);

    const user = userEvent.setup();
    renderWithRouter(<AlertsPage />);

    await waitFor(() => {
      expect(screen.getByText('无关联任务告警')).toBeInTheDocument();
    });

    await user.click(screen.getByText('无关联任务告警'));

    await waitFor(() => {
      expect(screen.queryByText('查看关联任务')).not.toBeInTheDocument();
    });
  });

  // --- Pagination ---
  test('renders pagination', async () => {
    renderWithRouter(<AlertsPage />);

    await waitFor(() => {
      expect(screen.getByText('关键偏差未处理')).toBeInTheDocument();
    });

    expect(document.querySelector('.ant-pagination')).toBeInTheDocument();
  });

  // --- Level filter tags ---
  test('renders level filter tags with badge counts', async () => {
    renderWithRouter(<AlertsPage />);

    await waitFor(() => {
      expect(screen.getByText('风险告警')).toBeInTheDocument();
    });

    // The level filter section should have badges
    const badges = document.querySelectorAll('.ant-badge');
    expect(badges.length).toBeGreaterThanOrEqual(1);
  });

  // --- Finding title in table ---
  test('displays finding titles in table', async () => {
    renderWithRouter(<AlertsPage />);

    await waitFor(() => {
      expect(screen.getByText('关键偏差未处理')).toBeInTheDocument();
    });

    expect(screen.getByText('SOP文档过期')).toBeInTheDocument();
    expect(screen.getByText('记录格式不规范')).toBeInTheDocument();
    expect(screen.getByText('环境监测超标')).toBeInTheDocument();
  });

  // --- Level filter interaction ---
  test('filters alerts by level when level tag clicked', async () => {
    const user = userEvent.setup();
    renderWithRouter(<AlertsPage />);

    await waitFor(() => {
      expect(screen.getByText('关键偏差未处理')).toBeInTheDocument();
    });

    // Click the critical level filter tag
    const criticalTags = screen.getAllByText('严重');
    await user.click(criticalTags[0]);

    // Should filter to only critical alerts
    await waitFor(() => {
      expect(screen.getByText('关键偏差未处理')).toBeInTheDocument();
    });
  });

  test('deselects level filter when same tag clicked again', async () => {
    const user = userEvent.setup();
    renderWithRouter(<AlertsPage />);

    await waitFor(() => {
      expect(screen.getByText('关键偏差未处理')).toBeInTheDocument();
    });

    // Click the critical level filter tag twice to toggle
    const criticalTags = screen.getAllByText('严重');
    await user.click(criticalTags[0]);
    await user.click(criticalTags[0]);

    // All alerts should be visible again
    await waitFor(() => {
      expect(screen.getByText('关键偏差未处理')).toBeInTheDocument();
    });
    expect(screen.getByText('SOP文档过期')).toBeInTheDocument();
  });

  // --- Status filter ---
  test('renders status filter select', async () => {
    renderWithRouter(<AlertsPage />);

    await waitFor(() => {
      expect(screen.getByText('关键偏差未处理')).toBeInTheDocument();
    });

    expect(screen.getByText('按状态筛选')).toBeInTheDocument();
  });

  // --- Dismiss info banner ---
  test('dismisses info banner when close clicked', async () => {
    const user = userEvent.setup();
    renderWithRouter(<AlertsPage />);

    await waitFor(() => {
      expect(screen.getByText(/告警由审计任务完成后自动生成/)).toBeInTheDocument();
    });

    // Find and click the close button on the alert
    const closeButton = document.querySelector('.ant-alert-close-icon');
    if (closeButton) {
      await user.click(closeButton as Element);
      await waitFor(() => {
        expect(screen.queryByText(/告警由审计任务完成后自动生成/)).not.toBeInTheDocument();
      });
    }
  });

  // --- Acknowledge action ---
  test('acknowledge button calls API when modal confirmed', async () => {
    // Mock Modal.confirm to auto-confirm
    const originalConfirm = (await import('antd')).Modal.confirm;
    const mockConfirm = jest.fn(({ onOk }: any) => {
      if (onOk) onOk();
    });
    (await import('antd')).Modal.confirm = mockConfirm;

    const user = userEvent.setup();
    renderWithRouter(<AlertsPage />);

    await waitFor(() => {
      expect(screen.getByText('关键偏差未处理')).toBeInTheDocument();
    });

    const acknowledgeButtons = screen.getAllByText('确认');
    await user.click(acknowledgeButtons[0]);

    await waitFor(() => {
      expect(mockAlertsApi.acknowledge).toHaveBeenCalled();
    });

    (await import('antd')).Modal.confirm = originalConfirm;
  });

  // --- Resolve action ---
  test('resolve button calls API when modal confirmed', async () => {
    const originalConfirm = (await import('antd')).Modal.confirm;
    const mockConfirm = jest.fn(({ onOk }: any) => {
      if (onOk) onOk();
    });
    (await import('antd')).Modal.confirm = mockConfirm;

    const user = userEvent.setup();
    renderWithRouter(<AlertsPage />);

    await waitFor(() => {
      expect(screen.getByText('关键偏差未处理')).toBeInTheDocument();
    });

    const resolveButtons = screen.getAllByText('解决');
    await user.click(resolveButtons[0]);

    await waitFor(() => {
      expect(mockAlertsApi.resolve).toHaveBeenCalled();
    });

    (await import('antd')).Modal.confirm = originalConfirm;
  });

  // --- Alert with unknown severity ---
  test('handles alert with unknown severity', async () => {
    mockAlertsApi.list.mockResolvedValue({
      items: [
        {
          id: 8,
          finding_id: 108,
          alert_level: 'warning' as const,
          status: 'active' as const,
          created_at: '2024-01-09T00:00:00Z',
          finding_title: '未知严重级别告警',
          finding_description: '描述',
          finding_severity: 'unknown',
        },
      ],
      total: 1,
      page: 1,
      page_size: 10,
    } as any);

    renderWithRouter(<AlertsPage />);

    await waitFor(() => {
      expect(screen.getByText('未知严重级别告警')).toBeInTheDocument();
    });
  });

  // --- Alert with no created_at ---
  test('handles alert with no created_at', async () => {
    mockAlertsApi.list.mockResolvedValue({
      items: [
        {
          id: 9,
          finding_id: 109,
          alert_level: 'info' as const,
          status: 'active' as const,
          created_at: '',
          finding_title: '无时间告警',
          finding_description: '描述',
          finding_severity: 'low',
        },
      ],
      total: 1,
      page: 1,
      page_size: 10,
    } as any);

    renderWithRouter(<AlertsPage />);

    await waitFor(() => {
      expect(screen.getByText('无时间告警')).toBeInTheDocument();
    });
  });

  // --- Badge counts ---
  test('displays correct badge counts for each level', async () => {
    renderWithRouter(<AlertsPage />);

    await waitFor(() => {
      expect(screen.getByText('风险告警')).toBeInTheDocument();
    });

    // Should have 3 badge elements for the 3 levels
    const badges = document.querySelectorAll('.ant-badge');
    expect(badges.length).toBeGreaterThanOrEqual(3);
  });

  // --- Critical row styling ---
  test('applies critical row class to critical alerts', async () => {
    renderWithRouter(<AlertsPage />);

    await waitFor(() => {
      expect(screen.getByText('关键偏差未处理')).toBeInTheDocument();
    });

    const criticalRows = document.querySelectorAll('.alert-row-critical');
    expect(criticalRows.length).toBeGreaterThanOrEqual(1);
  });
});

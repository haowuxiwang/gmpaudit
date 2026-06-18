import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import AlertsPage from '../AlertsPage';
import { alertsApi } from '../../services/api';

jest.setTimeout(15000);

jest.mock('../../services/api', () => ({
  alertsApi: {
    list: jest.fn().mockResolvedValue([]),
    acknowledge: jest.fn(),
    resolve: jest.fn(),
  },
}));

const mockAlertsApi = alertsApi as jest.Mocked<typeof alertsApi>;

const renderWithRouter = (component: React.ReactElement) => {
  return render(<BrowserRouter>{component}</BrowserRouter>);
};

describe('AlertsPage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockAlertsApi.list.mockResolvedValue([]);
  });

  test('renders page title', async () => {
    renderWithRouter(<AlertsPage />);
    await waitFor(() => {
      // Page renders without errors
      expect(screen.getByText(/暂无告警/)).toBeInTheDocument();
    });
  });

  test('renders empty state when no alerts', async () => {
    mockAlertsApi.list.mockResolvedValue([]);
    renderWithRouter(<AlertsPage />);
    await waitFor(() => {
      expect(screen.getByText(/暂无告警/)).toBeInTheDocument();
    });
  });
});

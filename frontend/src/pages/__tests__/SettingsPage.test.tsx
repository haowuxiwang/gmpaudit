import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import SettingsPage from '../SettingsPage';
import { configApi } from '../../services/api';

jest.mock('../../services/api', () => ({
  configApi: {
    getAll: jest.fn().mockResolvedValue({}),
    getModels: jest.fn().mockResolvedValue([]),
    batchUpdate: jest.fn(),
    testLLM: jest.fn(),
    testWebhook: jest.fn(),
  },
}));

const renderWithRouter = (component: React.ReactElement) => {
  return render(<BrowserRouter>{component}</BrowserRouter>);
};

describe('SettingsPage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (configApi.getAll as jest.Mock).mockResolvedValue({});
    (configApi.getModels as jest.Mock).mockResolvedValue([]);
  });

  test('renders page title', async () => {
    renderWithRouter(<SettingsPage />);
    await waitFor(() => {
      expect(screen.getByText(/系统设置/)).toBeInTheDocument();
    });
  });

  test('renders without crashing', async () => {
    const { container } = renderWithRouter(<SettingsPage />);
    expect(container).toBeTruthy();
  });
});

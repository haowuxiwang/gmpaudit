import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import ReportsPage from '../ReportsPage';
import { reportApi } from '../../services/api';

jest.setTimeout(15000);

// Mock react-markdown (ESM module)
jest.mock('react-markdown', () => {
  return function MockReactMarkdown({ children }: { children: string }) {
    return <div>{children}</div>;
  };
});

jest.mock('../../services/api', () => ({
  reportApi: {
    list: jest.fn().mockResolvedValue([]),
    get: jest.fn(),
    generate: jest.fn(),
    exportHtml: jest.fn(),
    exportPdf: jest.fn(),
  },
}));

const mockReportApi = reportApi as jest.Mocked<typeof reportApi>;

const renderWithRouter = (component: React.ReactElement) => {
  return render(<BrowserRouter>{component}</BrowserRouter>);
};

describe('ReportsPage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockReportApi.list.mockResolvedValue([]);
  });

  test('renders page title', async () => {
    renderWithRouter(<ReportsPage />);
    await waitFor(() => {
      expect(screen.getByText(/暂无报告/)).toBeInTheDocument();
    });
  });

  test('renders empty state', async () => {
    renderWithRouter(<ReportsPage />);
    await waitFor(() => {
      expect(screen.getByText(/暂无报告/)).toBeInTheDocument();
    });
  });

  test('loads reports on mount', async () => {
    renderWithRouter(<ReportsPage />);
    await waitFor(() => {
      expect(mockReportApi.list).toHaveBeenCalled();
    });
  });
});

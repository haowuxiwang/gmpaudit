import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import App from '../App';

jest.setTimeout(15000);

// Mock lazy-loaded pages to avoid complex rendering
jest.mock('../pages/DashboardPage', () => {
  return function MockDashboard() {
    return <div data-testid="dashboard-page">Dashboard</div>;
  };
});
jest.mock('../pages/DocumentsPage', () => {
  return function MockDocuments() {
    return <div data-testid="documents-page">Documents</div>;
  };
});
jest.mock('../pages/AuditTasksPage', () => {
  return function MockAuditTasks() {
    return <div data-testid="audit-tasks-page">AuditTasks</div>;
  };
});
jest.mock('../pages/ReportsPage', () => {
  return function MockReports() {
    return <div data-testid="reports-page">Reports</div>;
  };
});
jest.mock('../pages/SettingsPage', () => {
  return function MockSettings() {
    return <div data-testid="settings-page">Settings</div>;
  };
});
jest.mock('../pages/AlertsPage', () => {
  return function MockAlerts() {
    return <div data-testid="alerts-page">Alerts</div>;
  };
});
jest.mock('../pages/KnowledgeGraphPage', () => {
  return function MockKG() {
    return <div data-testid="kg-page">KnowledgeGraph</div>;
  };
});
jest.mock('../pages/NotFoundPage', () => {
  return function MockNotFound() {
    return <div data-testid="not-found-page">NotFound</div>;
  };
});

// Mock Sidebar and Header to avoid antd layout issues
jest.mock('../components/common/Sidebar', () => {
  return function MockSidebar() {
    return <div data-testid="sidebar">Sidebar</div>;
  };
});
jest.mock('../components/common/Header', () => {
  return function MockHeader() {
    return <div data-testid="header">Header</div>;
  };
});
jest.mock('../components/common/ErrorBoundary', () => {
  return function MockErrorBoundary({ children }: { children: React.ReactNode }) {
    return <div data-testid="error-boundary">{children}</div>;
  };
});

describe('App', () => {
  beforeEach(() => {
    window.history.pushState({}, '', '/');
  });

  test('renders without crashing', async () => {
    const { container } = render(<App />);
    expect(container).toBeTruthy();
  });

  test('renders sidebar and header', async () => {
    render(<App />);
    await waitFor(() => {
      expect(screen.getByTestId('sidebar')).toBeInTheDocument();
    });
    expect(screen.getByTestId('header')).toBeInTheDocument();
  });

  test('renders dashboard page at root route', async () => {
    window.history.pushState({}, '', '/');
    render(<App />);
    await waitFor(() => {
      expect(screen.getByTestId('dashboard-page')).toBeInTheDocument();
    });
  });

  test('renders error boundary around content', async () => {
    render(<App />);
    await waitFor(() => {
      expect(screen.getByTestId('error-boundary')).toBeInTheDocument();
    });
  });

  test('renders documents page at /documents', async () => {
    window.history.pushState({}, '', '/documents');
    render(<App />);
    await waitFor(() => {
      expect(screen.getByTestId('documents-page')).toBeInTheDocument();
    });
  });

  test('renders audit tasks page at /audit', async () => {
    window.history.pushState({}, '', '/audit');
    render(<App />);
    await waitFor(() => {
      expect(screen.getByTestId('audit-tasks-page')).toBeInTheDocument();
    });
  });

  test('renders reports page at /reports', async () => {
    window.history.pushState({}, '', '/reports');
    render(<App />);
    await waitFor(() => {
      expect(screen.getByTestId('reports-page')).toBeInTheDocument();
    });
  });

  test('renders knowledge graph page at /kg', async () => {
    window.history.pushState({}, '', '/kg');
    render(<App />);
    await waitFor(() => {
      expect(screen.getByTestId('kg-page')).toBeInTheDocument();
    });
  });

  test('renders alerts page at /alerts', async () => {
    window.history.pushState({}, '', '/alerts');
    render(<App />);
    await waitFor(() => {
      expect(screen.getByTestId('alerts-page')).toBeInTheDocument();
    });
  });

  test('renders settings page at /settings', async () => {
    window.history.pushState({}, '', '/settings');
    render(<App />);
    await waitFor(() => {
      expect(screen.getByTestId('settings-page')).toBeInTheDocument();
    });
  });

  test('renders not found page for unknown route', async () => {
    window.history.pushState({}, '', '/nonexistent');
    render(<App />);
    await waitFor(() => {
      expect(screen.getByTestId('not-found-page')).toBeInTheDocument();
    });
  });

  test('renders app layout structure with sidebar and header', async () => {
    render(<App />);
    await waitFor(() => {
      expect(screen.getByTestId('sidebar')).toBeInTheDocument();
      expect(screen.getByTestId('header')).toBeInTheDocument();
      expect(screen.getByTestId('error-boundary')).toBeInTheDocument();
    });
  });
});

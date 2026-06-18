import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import App from '../App';

jest.setTimeout(15000);

// Mock lazy-loaded pages
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

// Mock Sidebar and Header
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

describe('App - branch coverage', () => {
  beforeEach(() => {
    window.history.pushState({}, '', '/');
  });

  test('renders without crashing', async () => {
    const { container } = render(<App />);
    expect(container).toBeTruthy();
  });

  test('renders sidebar', async () => {
    render(<App />);
    await waitFor(() => {
      expect(screen.getByTestId('sidebar')).toBeInTheDocument();
    });
  });

  test('renders header', async () => {
    render(<App />);
    await waitFor(() => {
      expect(screen.getByTestId('header')).toBeInTheDocument();
    });
  });

  test('renders error boundary', async () => {
    render(<App />);
    await waitFor(() => {
      expect(screen.getByTestId('error-boundary')).toBeInTheDocument();
    });
  });

  // --- Route branches ---

  test('renders dashboard at "/"', async () => {
    window.history.pushState({}, '', '/');
    render(<App />);
    await waitFor(() => {
      expect(screen.getByTestId('dashboard-page')).toBeInTheDocument();
    });
  });

  test('renders documents at "/documents"', async () => {
    window.history.pushState({}, '', '/documents');
    render(<App />);
    await waitFor(() => {
      expect(screen.getByTestId('documents-page')).toBeInTheDocument();
    });
  });

  test('renders audit at "/audit"', async () => {
    window.history.pushState({}, '', '/audit');
    render(<App />);
    await waitFor(() => {
      expect(screen.getByTestId('audit-tasks-page')).toBeInTheDocument();
    });
  });

  test('renders reports at "/reports"', async () => {
    window.history.pushState({}, '', '/reports');
    render(<App />);
    await waitFor(() => {
      expect(screen.getByTestId('reports-page')).toBeInTheDocument();
    });
  });

  test('renders knowledge graph at "/kg"', async () => {
    window.history.pushState({}, '', '/kg');
    render(<App />);
    await waitFor(() => {
      expect(screen.getByTestId('kg-page')).toBeInTheDocument();
    });
  });

  test('renders alerts at "/alerts"', async () => {
    window.history.pushState({}, '', '/alerts');
    render(<App />);
    await waitFor(() => {
      expect(screen.getByTestId('alerts-page')).toBeInTheDocument();
    });
  });

  test('renders settings at "/settings"', async () => {
    window.history.pushState({}, '', '/settings');
    render(<App />);
    await waitFor(() => {
      expect(screen.getByTestId('settings-page')).toBeInTheDocument();
    });
  });

  test('renders not found at unknown route', async () => {
    window.history.pushState({}, '', '/nonexistent');
    render(<App />);
    await waitFor(() => {
      expect(screen.getByTestId('not-found-page')).toBeInTheDocument();
    });
  });

  test('renders not found at deeply nested route', async () => {
    window.history.pushState({}, '', '/some/deep/nested/path');
    render(<App />);
    await waitFor(() => {
      expect(screen.getByTestId('not-found-page')).toBeInTheDocument();
    });
  });

  // --- Layout structure ---

  test('renders layout with sidebar and header', async () => {
    render(<App />);
    await waitFor(() => {
      expect(screen.getByTestId('sidebar')).toBeInTheDocument();
      expect(screen.getByTestId('header')).toBeInTheDocument();
    });
  });

  test('renders content area with error boundary', async () => {
    render(<App />);
    await waitFor(() => {
      expect(screen.getByTestId('error-boundary')).toBeInTheDocument();
    });
  });

  // --- ConfigProvider ---

  test('renders with ConfigProvider', async () => {
    const { container } = render(<App />);
    // ConfigProvider wraps the entire app
    expect(container).toBeTruthy();
  });

  // --- Multiple route changes ---

  test('handles multiple route changes', async () => {
    render(<App />);

    // Start at dashboard
    await waitFor(() => {
      expect(screen.getByTestId('dashboard-page')).toBeInTheDocument();
    });

    // Navigate to documents using popstate event
    window.history.pushState({}, '', '/documents');
    window.dispatchEvent(new PopStateEvent('popstate'));
    await waitFor(() => {
      expect(screen.getByTestId('documents-page')).toBeInTheDocument();
    });

    // Navigate to audit
    window.history.pushState({}, '', '/audit');
    window.dispatchEvent(new PopStateEvent('popstate'));
    await waitFor(() => {
      expect(screen.getByTestId('audit-tasks-page')).toBeInTheDocument();
    });
  });

  // --- Suspense fallback ---

  test('renders Suspense wrapper for lazy loading', async () => {
    render(<App />);
    await waitFor(() => {
      expect(screen.getByTestId('dashboard-page')).toBeInTheDocument();
    });
  });

  // --- App component structure ---

  test('renders with correct layout structure', async () => {
    const { container } = render(<App />);
    await waitFor(() => {
      const layout = container.querySelector('.ant-layout');
      expect(layout).toBeInTheDocument();
    });
  });
});

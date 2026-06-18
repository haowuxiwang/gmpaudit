import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Header from '../Header';

const renderWithRouter = (component: React.ReactElement, initialEntries = ['/']) => {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      {component}
    </MemoryRouter>
  );
};

describe('Header - branch coverage', () => {
  test('renders "审计工作台" for root route "/"', () => {
    renderWithRouter(<Header />, ['/']);
    expect(screen.getByText('审计工作台')).toBeInTheDocument();
  });

  test('renders "文档管理" for /documents route', () => {
    renderWithRouter(<Header />, ['/documents']);
    expect(screen.getByText('文档管理')).toBeInTheDocument();
  });

  test('renders "审计任务" for /audit route', () => {
    renderWithRouter(<Header />, ['/audit']);
    expect(screen.getByText('审计任务')).toBeInTheDocument();
  });

  test('renders "审计报告" for /reports route', () => {
    renderWithRouter(<Header />, ['/reports']);
    expect(screen.getByText('审计报告')).toBeInTheDocument();
  });

  test('renders "知识图谱" for /kg route', () => {
    renderWithRouter(<Header />, ['/kg']);
    expect(screen.getByText('知识图谱')).toBeInTheDocument();
  });

  test('renders "风险告警" for /alerts route', () => {
    renderWithRouter(<Header />, ['/alerts']);
    expect(screen.getByText('风险告警')).toBeInTheDocument();
  });

  test('renders "系统设置" for /settings route', () => {
    renderWithRouter(<Header />, ['/settings']);
    expect(screen.getByText('系统设置')).toBeInTheDocument();
  });

  test('renders "审计工作台" as fallback for unknown route', () => {
    renderWithRouter(<Header />, ['/unknown-route']);
    expect(screen.getByText('审计工作台')).toBeInTheDocument();
  });

  test('renders "审计工作台" for deeply nested unknown route', () => {
    renderWithRouter(<Header />, ['/some/very/deep/path']);
    expect(screen.getByText('审计工作台')).toBeInTheDocument();
  });

  test('renders header element with correct structure', () => {
    const { container } = renderWithRouter(<Header />, ['/']);
    const header = container.querySelector('.ant-layout-header');
    expect(header).toBeInTheDocument();
  });

  test('renders title as h4 element', () => {
    renderWithRouter(<Header />, ['/']);
    const title = screen.getByRole('heading', { level: 4 });
    expect(title).toBeInTheDocument();
    expect(title).toHaveTextContent('审计工作台');
  });

  test('updates title when route changes', () => {
    const { unmount } = renderWithRouter(<Header />, ['/']);
    expect(screen.getByText('审计工作台')).toBeInTheDocument();
    unmount();

    renderWithRouter(<Header />, ['/documents']);
    expect(screen.getByText('文档管理')).toBeInTheDocument();
  });

  test('renders with empty path segments', () => {
    renderWithRouter(<Header />, ['///']);
    expect(screen.getByText('审计工作台')).toBeInTheDocument();
  });
});

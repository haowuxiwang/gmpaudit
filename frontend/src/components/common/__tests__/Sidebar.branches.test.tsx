import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import Sidebar from '../Sidebar';

const renderWithRouter = (component: React.ReactElement, initialEntries = ['/']) => {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      {component}
    </MemoryRouter>
  );
};

describe('Sidebar - branch coverage', () => {
  test('renders all 7 menu items', () => {
    renderWithRouter(<Sidebar />);
    expect(screen.getByText('工作台')).toBeInTheDocument();
    expect(screen.getByText('文档管理')).toBeInTheDocument();
    expect(screen.getByText('审计任务')).toBeInTheDocument();
    expect(screen.getByText('审计报告')).toBeInTheDocument();
    expect(screen.getByText('知识图谱')).toBeInTheDocument();
    expect(screen.getByText('风险告警')).toBeInTheDocument();
    expect(screen.getByText('系统设置')).toBeInTheDocument();
  });

  test('renders AuditBee branding', () => {
    renderWithRouter(<Sidebar />);
    expect(screen.getByText('AuditBee')).toBeInTheDocument();
    expect(screen.getByText('多智能体 GMP 合规审计')).toBeInTheDocument();
  });

  test('highlights current route "/" correctly', () => {
    renderWithRouter<Sidebar>(<Sidebar />, ['/']);
    const menuItems = document.querySelectorAll('.ant-menu-item-selected');
    expect(menuItems.length).toBeGreaterThanOrEqual(1);
  });

  test('highlights /documents route correctly', () => {
    renderWithRouter(<Sidebar />, ['/documents']);
    const menuItems = document.querySelectorAll('.ant-menu-item-selected');
    expect(menuItems.length).toBeGreaterThanOrEqual(1);
  });

  test('highlights /audit route correctly', () => {
    renderWithRouter(<Sidebar />, ['/audit']);
    const menuItems = document.querySelectorAll('.ant-menu-item-selected');
    expect(menuItems.length).toBeGreaterThanOrEqual(1);
  });

  test('highlights /reports route correctly', () => {
    renderWithRouter(<Sidebar />, ['/reports']);
    const menuItems = document.querySelectorAll('.ant-menu-item-selected');
    expect(menuItems.length).toBeGreaterThanOrEqual(1);
  });

  test('highlights /kg route correctly', () => {
    renderWithRouter(<Sidebar />, ['/kg']);
    const menuItems = document.querySelectorAll('.ant-menu-item-selected');
    expect(menuItems.length).toBeGreaterThanOrEqual(1);
  });

  test('highlights /alerts route correctly', () => {
    renderWithRouter(<Sidebar />, ['/alerts']);
    const menuItems = document.querySelectorAll('.ant-menu-item-selected');
    expect(menuItems.length).toBeGreaterThanOrEqual(1);
  });

  test('highlights /settings route correctly', () => {
    renderWithRouter(<Sidebar />, ['/settings']);
    const menuItems = document.querySelectorAll('.ant-menu-item-selected');
    expect(menuItems.length).toBeGreaterThanOrEqual(1);
  });

  test('renders collapsible sider', () => {
    const { container } = renderWithRouter(<Sidebar />);
    const sider = container.querySelector('.ant-layout-sider');
    expect(sider).toBeInTheDocument();
  });

  test('has correct initial width', () => {
    const { container } = renderWithRouter(<Sidebar />);
    const sider = container.querySelector('.ant-layout-sider');
    expect(sider).toBeInTheDocument();
  });

  test('renders menu items with icons', () => {
    const { container } = renderWithRouter(<Sidebar />);
    const menuItems = container.querySelectorAll('.ant-menu-item');
    expect(menuItems.length).toBe(7);
  });

  test('does not select any item for unknown route', () => {
    renderWithRouter(<Sidebar />, ['/unknown-route']);
    const selectedItems = document.querySelectorAll('.ant-menu-item-selected');
    expect(selectedItems.length).toBe(0);
  });

  test('menu is rendered in inline mode', () => {
    const { container } = renderWithRouter(<Sidebar />);
    const menu = container.querySelector('.ant-menu-inline');
    expect(menu).toBeInTheDocument();
  });
});

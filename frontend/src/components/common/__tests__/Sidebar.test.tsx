import React from 'react';
import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import Sidebar from '../Sidebar';

const renderWithRouter = (component: React.ReactElement) => {
  return render(<BrowserRouter>{component}</BrowserRouter>);
};

describe('Sidebar', () => {
  test('renders navigation menu items', () => {
    renderWithRouter(<Sidebar />);
    // Check for key menu items
    expect(screen.getByText(/工作台/)).toBeInTheDocument();
    expect(screen.getByText(/文档管理/)).toBeInTheDocument();
    expect(screen.getByText(/审计任务/)).toBeInTheDocument();
  });

  test('renders all menu items', () => {
    renderWithRouter(<Sidebar />);
    expect(screen.getByText(/审计报告/)).toBeInTheDocument();
    expect(screen.getByText(/知识图谱/)).toBeInTheDocument();
    expect(screen.getByText(/风险告警/)).toBeInTheDocument();
    expect(screen.getByText(/系统设置/)).toBeInTheDocument();
  });
});

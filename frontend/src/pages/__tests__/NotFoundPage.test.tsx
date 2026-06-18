import React from 'react';
import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import NotFoundPage from '../NotFoundPage';

const renderWithRouter = (component: React.ReactElement) => {
  return render(<BrowserRouter>{component}</BrowserRouter>);
};

describe('NotFoundPage', () => {
  test('renders 404 title', () => {
    renderWithRouter(<NotFoundPage />);
    expect(screen.getByText('404')).toBeInTheDocument();
  });

  test('renders not found message', () => {
    renderWithRouter(<NotFoundPage />);
    expect(screen.getByText('页面不存在')).toBeInTheDocument();
  });

  test('renders back to home button', () => {
    renderWithRouter(<NotFoundPage />);
    expect(screen.getByText('返回首页')).toBeInTheDocument();
  });
});

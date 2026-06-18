import React from 'react';
import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import Header from '../Header';

const renderWithRouter = (component: React.ReactElement) => {
  return render(<BrowserRouter>{component}</BrowserRouter>);
};

describe('Header', () => {
  test('renders default page title', () => {
    renderWithRouter(<Header />);
    // Default route "/" shows "审计工作台"
    expect(screen.getByText(/审计工作台/)).toBeInTheDocument();
  });
});

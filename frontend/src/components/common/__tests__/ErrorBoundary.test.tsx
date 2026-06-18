import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ErrorBoundary from '../ErrorBoundary';

// Suppress console.error from React error boundary warnings
const originalError = console.error;
beforeAll(() => {
  console.error = jest.fn();
});
afterAll(() => {
  console.error = originalError;
});

const ThrowingChild = () => {
  throw new Error('test error');
};

describe('ErrorBoundary', () => {
  test('renders children when no error', () => {
    render(
      <ErrorBoundary>
        <div>child content</div>
      </ErrorBoundary>,
    );
    expect(screen.getByText('child content')).toBeInTheDocument();
  });

  test('renders error UI when child throws', () => {
    render(
      <ErrorBoundary>
        <ThrowingChild />
      </ErrorBoundary>,
    );
    expect(screen.getByText('页面出错了')).toBeInTheDocument();
    // Ant Design renders button text with letter-spacing, so use flexible matcher
    expect(screen.getByRole('button', { name: /重\s*试/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /返回首页/ })).toBeInTheDocument();
  });

  test('retry button resets error state and shows children again', async () => {
    const user = userEvent.setup();

    // Use a component that throws on first render but not on retry
    let shouldThrow = true;
    const ConditionalThrow = () => {
      if (shouldThrow) {
        throw new Error('test error');
      }
      return <div>recovered content</div>;
    };

    render(
      <ErrorBoundary>
        <ConditionalThrow />
      </ErrorBoundary>,
    );
    expect(screen.getByText('页面出错了')).toBeInTheDocument();

    // After retry, the child should not throw
    shouldThrow = false;
    await user.click(screen.getByRole('button', { name: /重\s*试/ }));
    expect(screen.getByText('recovered content')).toBeInTheDocument();
  });
});

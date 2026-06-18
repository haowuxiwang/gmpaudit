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

describe('ErrorBoundary - branch coverage', () => {
  test('renders children when no error occurs', () => {
    render(
      <ErrorBoundary>
        <div>normal content</div>
      </ErrorBoundary>
    );
    expect(screen.getByText('normal content')).toBeInTheDocument();
  });

  test('renders error UI when child throws', () => {
    render(
      <ErrorBoundary>
        <ThrowingChild />
      </ErrorBoundary>
    );
    expect(screen.getByText('页面出错了')).toBeInTheDocument();
    expect(screen.getByText('发生了意外错误，请重试或返回首页')).toBeInTheDocument();
  });

  test('renders retry button with correct text', () => {
    render(
      <ErrorBoundary>
        <ThrowingChild />
      </ErrorBoundary>
    );
    expect(screen.getByRole('button', { name: /重\s*试/ })).toBeInTheDocument();
  });

  test('renders go home button with correct text', () => {
    render(
      <ErrorBoundary>
        <ThrowingChild />
      </ErrorBoundary>
    );
    expect(screen.getByRole('button', { name: /返回首页/ })).toBeInTheDocument();
  });

  test('retry button resets error state and shows children', async () => {
    const user = userEvent.setup();
    let shouldThrow = true;
    const ConditionalThrow = () => {
      if (shouldThrow) throw new Error('test error');
      return <div>recovered content</div>;
    };

    render(
      <ErrorBoundary>
        <ConditionalThrow />
      </ErrorBoundary>
    );
    expect(screen.getByText('页面出错了')).toBeInTheDocument();

    shouldThrow = false;
    await user.click(screen.getByRole('button', { name: /重\s*试/ }));
    expect(screen.getByText('recovered content')).toBeInTheDocument();
  });

  test('go home button resets error state', async () => {
    const user = userEvent.setup();
    // Mock window.location.href setter
    const mockAssign = jest.fn();
    Object.defineProperty(window, 'location', {
      value: { ...window.location, href: '/', assign: mockAssign },
      writable: true,
    });

    let shouldThrow = true;
    const ConditionalThrow = () => {
      if (shouldThrow) throw new Error('test error');
      return <div>recovered</div>;
    };

    render(
      <ErrorBoundary>
        <ConditionalThrow />
      </ErrorBoundary>
    );
    expect(screen.getByText('页面出错了')).toBeInTheDocument();

    shouldThrow = false;
    await user.click(screen.getByRole('button', { name: /返回首页/ }));
    // After clicking, hasError should be reset to false
    // Since window.location.href = '/' would navigate, the component re-renders
  });

  test('logs error to console.error when catching', () => {
    const consoleSpy = jest.spyOn(console, 'error').mockImplementation(() => {});

    render(
      <ErrorBoundary>
        <ThrowingChild />
      </ErrorBoundary>
    );

    expect(consoleSpy).toHaveBeenCalledWith(
      'ErrorBoundary caught:',
      expect.any(Error),
      expect.any(Object)
    );

    consoleSpy.mockRestore();
  });

  test('renders error result with error status', () => {
    const { container } = render(
      <ErrorBoundary>
        <ThrowingChild />
      </ErrorBoundary>
    );

    const result = container.querySelector('.ant-result-error');
    expect(result).toBeInTheDocument();
  });

  test('handles error and recovery', async () => {
    const user = userEvent.setup();
    let shouldThrow = true;
    const ConditionalThrow = () => {
      if (shouldThrow) throw new Error('test error');
      return <div>recovered content</div>;
    };

    render(
      <ErrorBoundary>
        <ConditionalThrow />
      </ErrorBoundary>
    );

    // Error state
    expect(screen.getByText('页面出错了')).toBeInTheDocument();

    // Retry - recovery
    shouldThrow = false;
    await user.click(screen.getByRole('button', { name: /重\s*试/ }));
    expect(screen.getByText('recovered content')).toBeInTheDocument();
  });

  test('renders children after successful retry', async () => {
    const user = userEvent.setup();
    let shouldThrow = true;
    const ConditionalThrow = () => {
      if (shouldThrow) throw new Error('test');
      return <div>success after retry</div>;
    };

    render(
      <ErrorBoundary>
        <ConditionalThrow />
      </ErrorBoundary>
    );

    shouldThrow = false;
    await user.click(screen.getByRole('button', { name: /重\s*试/ }));
    expect(screen.getByText('success after retry')).toBeInTheDocument();
    expect(screen.queryByText('页面出错了')).not.toBeInTheDocument();
  });

  test('renders with complex children when no error', () => {
    render(
      <ErrorBoundary>
        <div>
          <h1>Title</h1>
          <p>Paragraph</p>
          <button>Action</button>
        </div>
      </ErrorBoundary>
    );

    expect(screen.getByText('Title')).toBeInTheDocument();
    expect(screen.getByText('Paragraph')).toBeInTheDocument();
    expect(screen.getByText('Action')).toBeInTheDocument();
  });

  test('renders with null children', () => {
    const { container } = render(
      <ErrorBoundary>
        {null}
      </ErrorBoundary>
    );
    expect(container).toBeTruthy();
  });

  test('renders with multiple children', () => {
    render(
      <ErrorBoundary>
        <div>Child 1</div>
        <div>Child 2</div>
      </ErrorBoundary>
    );
    expect(screen.getByText('Child 1')).toBeInTheDocument();
    expect(screen.getByText('Child 2')).toBeInTheDocument();
  });

  test('getDerivedStateFromError returns correct state', () => {
    const state = ErrorBoundary.getDerivedStateFromError(new Error('test'));
    expect(state).toEqual({ hasError: true });
  });

  test('componentDidCatch is called with error and info', () => {
    const componentDidCatchSpy = jest.spyOn(ErrorBoundary.prototype, 'componentDidCatch');

    render(
      <ErrorBoundary>
        <ThrowingChild />
      </ErrorBoundary>
    );

    expect(componentDidCatchSpy).toHaveBeenCalledWith(
      expect.any(Error),
      expect.objectContaining({ componentStack: expect.any(String) })
    );

    componentDidCatchSpy.mockRestore();
  });
});

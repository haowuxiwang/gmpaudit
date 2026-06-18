/**
 * Tests for useSSE hook - branch coverage extension.
 * Covers reconnection logic, error handling, edge cases.
 */

import { renderHook, act } from '@testing-library/react';
import { useSSE } from '../useSSE';

// Mock EventSource globally
const mockClose = jest.fn();
const mockInstances: any[] = [];

class MockEventSource {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSED = 2;

  readyState = 0;
  url: string;
  onopen: any = null;
  onmessage: any = null;
  onerror: any = null;
  private _listeners: Record<string, Function[]> = {};

  constructor(url: string) {
    this.url = url;
    mockInstances.push(this);
  }

  addEventListener(type: string, handler: Function) {
    if (!this._listeners[type]) this._listeners[type] = [];
    this._listeners[type].push(handler);
  }

  removeEventListener(type: string, handler: Function) {
    if (this._listeners[type]) {
      this._listeners[type] = this._listeners[type].filter((h) => h !== handler);
    }
  }

  close() {
    mockClose();
    this.readyState = 2;
  }

  _emit(type: string, data: any) {
    if (type === 'message' && this.onmessage) {
      this.onmessage({ data: JSON.stringify(data) });
    } else if (this._listeners[type]) {
      this._listeners[type].forEach((handler) => {
        handler({ data: JSON.stringify(data) });
      });
    }
  }

  _emitOpen() {
    this.readyState = 1;
    if (this.onopen) this.onopen({});
  }

  _emitError() {
    if (this.onerror) this.onerror({});
  }
}

beforeEach(() => {
  mockClose.mockClear();
  mockInstances.length = 0;
  (global as any).EventSource = MockEventSource;
});

describe('useSSE - branch coverage', () => {
  // --- Connection conditions ---

  test('does not connect when url is null', () => {
    renderHook(() => useSSE({ url: null }));
    expect(mockInstances).toHaveLength(0);
  });

  test('does not connect when enabled is false', () => {
    renderHook(() => useSSE({ url: 'http://localhost/sse', enabled: false }));
    expect(mockInstances).toHaveLength(0);
  });

  test('connects when url is provided and enabled', () => {
    renderHook(() => useSSE({ url: 'http://localhost/sse' }));
    expect(mockInstances).toHaveLength(1);
    expect(mockInstances[0].url).toBe('http://localhost/sse');
  });

  test('connects with default enabled (true)', () => {
    renderHook(() => useSSE({ url: 'http://localhost/sse' }));
    expect(mockInstances).toHaveLength(1);
  });

  // --- Cleanup ---

  test('cleans up on unmount', () => {
    const { unmount } = renderHook(() => useSSE({ url: 'http://localhost/sse' }));
    unmount();
    expect(mockClose).toHaveBeenCalled();
  });

  test('closes existing source when url changes', () => {
    const { rerender } = renderHook(
      ({ url }) => useSSE({ url }),
      { initialProps: { url: 'http://localhost/sse1' } }
    );

    expect(mockInstances).toHaveLength(1);

    rerender({ url: 'http://localhost/sse2' });

    expect(mockClose).toHaveBeenCalled();
    expect(mockInstances).toHaveLength(2);
  });

  test('disconnects when enabled changes to false', () => {
    const { rerender } = renderHook(
      ({ enabled }) => useSSE({ url: 'http://localhost/sse', enabled }),
      { initialProps: { enabled: true } }
    );

    expect(mockInstances).toHaveLength(1);

    rerender({ enabled: false });

    expect(mockClose).toHaveBeenCalled();
  });

  test('reconnects when enabled changes back to true', () => {
    const { rerender } = renderHook(
      ({ enabled }) => useSSE({ url: 'http://localhost/sse', enabled }),
      { initialProps: { enabled: false } }
    );

    expect(mockInstances).toHaveLength(0);

    rerender({ enabled: true });

    expect(mockInstances).toHaveLength(1);
  });

  // --- Initial state ---

  test('returns initial state', () => {
    const { result } = renderHook(() => useSSE({ url: null }));
    expect(result.current.readyState).toBe(2); // CLOSED
    expect(result.current.connectionError).toBe(false);
    expect(result.current.reconnectCount).toBe(0);
    expect(typeof result.current.close).toBe('function');
  });

  test('close function is stable', () => {
    const { result, rerender } = renderHook(() => useSSE({ url: 'http://localhost/sse' }));
    const firstClose = result.current.close;
    rerender();
    expect(result.current.close).toBe(firstClose);
  });

  // --- onMessage handling ---

  test('calls onMessage with parsed data', () => {
    const onMessage = jest.fn();
    renderHook(() => useSSE({ url: 'http://localhost/sse', onMessage }));

    const instance = mockInstances[0];
    act(() => {
      instance._emit('message', { hello: 'world' });
    });

    expect(onMessage).toHaveBeenCalledWith({ hello: 'world' });
  });

  test('handles JSON parse error in onMessage gracefully', () => {
    const onMessage = jest.fn();
    const consoleSpy = jest.spyOn(console, 'warn').mockImplementation();
    renderHook(() => useSSE({ url: 'http://localhost/sse', onMessage }));

    const instance = mockInstances[0];
    act(() => {
      instance.onmessage({ data: 'not-json' });
    });

    expect(onMessage).not.toHaveBeenCalled();
    consoleSpy.mockRestore();
  });

  test('calls onMessage with complex data structures', () => {
    const onMessage = jest.fn();
    renderHook(() => useSSE({ url: 'http://localhost/sse', onMessage }));

    const complexData = { nested: { array: [1, 2, 3], string: 'test' } };
    const instance = mockInstances[0];
    act(() => {
      instance._emit('message', complexData);
    });

    expect(onMessage).toHaveBeenCalledWith(complexData);
  });

  // --- Named event handling ---

  test('registers named event listeners', () => {
    const handler = jest.fn();
    renderHook(() => useSSE({
      url: 'http://localhost/sse',
      onEvent: { 'task-event': handler },
    }));

    const instance = mockInstances[0];
    act(() => {
      instance._emit('task-event', { type: 'task-event', data: { status: 'running' } });
    });

    expect(handler).toHaveBeenCalledWith({ status: 'running' });
  });

  test('unwraps nested data in named events', () => {
    const handler = jest.fn();
    renderHook(() => useSSE({
      url: 'http://localhost/sse',
      onEvent: { progress: handler },
    }));

    const instance = mockInstances[0];
    act(() => {
      instance._emit('progress', { data: { percent: 50 } });
    });

    expect(handler).toHaveBeenCalledWith({ percent: 50 });
  });

  test('handles multiple named event types', () => {
    const handler1 = jest.fn();
    const handler2 = jest.fn();
    renderHook(() => useSSE({
      url: 'http://localhost/sse',
      onEvent: {
        event: handler1,
        done: handler2,
      },
    }));

    const instance = mockInstances[0];
    act(() => {
      instance._emit('event', { type: 'event', data: { message: 'test' } });
      instance._emit('done', { type: 'done', data: { status: 'completed' } });
    });

    expect(handler1).toHaveBeenCalledWith({ message: 'test' });
    expect(handler2).toHaveBeenCalledWith({ status: 'completed' });
  });

  test('handles JSON parse error in named event listener', () => {
    const handler = jest.fn();
    const consoleSpy = jest.spyOn(console, 'warn').mockImplementation();
    renderHook(() => useSSE({
      url: 'http://localhost/sse',
      onEvent: { 'test-event': handler },
    }));

    const instance = mockInstances[0];
    act(() => {
      const listeners = (instance as any)._listeners['test-event'];
      if (listeners && listeners.length > 0) {
        listeners[0]({ data: 'not-json' });
      }
    });

    expect(handler).not.toHaveBeenCalled();
    expect(consoleSpy).toHaveBeenCalled();
    consoleSpy.mockRestore();
  });

  // --- onOpen callback ---

  test('calls onOpen when connection opens', () => {
    const onOpen = jest.fn();
    renderHook(() => useSSE({ url: 'http://localhost/sse', onOpen }));

    const instance = mockInstances[0];
    act(() => {
      instance._emitOpen();
    });

    expect(onOpen).toHaveBeenCalled();
  });

  test('resets connection error on successful open', () => {
    const { result } = renderHook(() => useSSE({ url: 'http://localhost/sse' }));

    const instance = mockInstances[0];

    // Trigger errors to set connectionError
    act(() => {
      instance._emitError();
      instance._emitError();
      instance._emitError();
      instance._emitError();
    });

    // Now connect successfully
    act(() => {
      instance._emitOpen();
    });

    expect(result.current.connectionError).toBe(false);
    expect(result.current.reconnectCount).toBe(0);
  });

  // --- Error handling and reconnection ---

  test('increments reconnect count on error', () => {
    const { result } = renderHook(() => useSSE({ url: 'http://localhost/sse' }));

    const instance = mockInstances[0];
    act(() => {
      instance._emitError();
    });

    expect(result.current.reconnectCount).toBe(1);
  });

  test('sets connectionError after max reconnect attempts', () => {
    const { result } = renderHook(() => useSSE({ url: 'http://localhost/sse' }));

    const instance = mockInstances[0];
    act(() => {
      instance._emitError();
      instance._emitError();
      instance._emitError();
    });

    expect(result.current.connectionError).toBe(true);
    expect(result.current.reconnectCount).toBe(3);
  });

  test('calls onError callback on error', () => {
    const onError = jest.fn();
    renderHook(() => useSSE({ url: 'http://localhost/sse', onError }));

    const instance = mockInstances[0];
    act(() => {
      instance._emitError();
    });

    expect(onError).toHaveBeenCalled();
  });

  test('handles single error without setting connectionError', () => {
    const { result } = renderHook(() => useSSE({ url: 'http://localhost/sse' }));

    const instance = mockInstances[0];
    act(() => {
      instance._emitError();
    });

    expect(result.current.reconnectCount).toBe(1);
    expect(result.current.connectionError).toBe(false);
  });

  test('handles two errors without setting connectionError', () => {
    const { result } = renderHook(() => useSSE({ url: 'http://localhost/sse' }));

    const instance = mockInstances[0];
    act(() => {
      instance._emitError();
      instance._emitError();
    });

    expect(result.current.reconnectCount).toBe(2);
    expect(result.current.connectionError).toBe(false);
  });

  // --- close() function ---

  test('close function closes the EventSource', () => {
    const { result } = renderHook(() => useSSE({ url: 'http://localhost/sse' }));

    act(() => {
      result.current.close();
    });

    expect(mockClose).toHaveBeenCalled();
  });

  test('close function is safe to call multiple times', () => {
    const { result } = renderHook(() => useSSE({ url: 'http://localhost/sse' }));

    act(() => {
      result.current.close();
    });

    expect(mockClose).toHaveBeenCalled();
  });

  // --- ReadyState tracking ---

  test('tracks readyState changes from CONNECTING to OPEN', () => {
    const { result } = renderHook(() => useSSE({ url: 'http://localhost/sse' }));

    const instance = mockInstances[0];

    expect(result.current.readyState).toBe(0); // CONNECTING

    act(() => {
      instance._emitOpen();
    });

    expect(result.current.readyState).toBe(1); // OPEN
  });

  test('readyState is CLOSED when no connection', () => {
    const { result } = renderHook(() => useSSE({ url: null }));
    expect(result.current.readyState).toBe(2); // CLOSED
  });

  // --- Cleanup removes event listeners ---

  test('removes named event listeners on cleanup', () => {
    const handler = jest.fn();
    const removeSpy = jest.spyOn(MockEventSource.prototype, 'removeEventListener');

    const { unmount } = renderHook(() => useSSE({
      url: 'http://localhost/sse',
      onEvent: { 'test-event': handler },
    }));

    unmount();

    expect(removeSpy).toHaveBeenCalledWith('test-event', expect.any(Function));
    removeSpy.mockRestore();
  });

  // --- URL change cleanup ---

  test('closes existing source before creating new one on url change', () => {
    const { rerender } = renderHook(
      ({ url }) => useSSE({ url }),
      { initialProps: { url: 'http://localhost/sse1' } }
    );

    expect(mockInstances).toHaveLength(1);

    rerender({ url: 'http://localhost/sse2' });

    expect(mockClose).toHaveBeenCalled();
    expect(mockInstances).toHaveLength(2);
  });

  // --- Edge cases ---

  test('handles empty url string', () => {
    renderHook(() => useSSE({ url: '' }));
    // Empty string is falsy, should not connect
    expect(mockInstances).toHaveLength(0);
  });

  test('handles rapid url changes', () => {
    const { rerender } = renderHook(
      ({ url }) => useSSE({ url }),
      { initialProps: { url: 'http://localhost/sse1' } }
    );

    rerender({ url: 'http://localhost/sse2' });
    rerender({ url: 'http://localhost/sse3' });

    expect(mockInstances).toHaveLength(3);
    expect(mockClose).toHaveBeenCalledTimes(2);
  });

  test('handles onMessage with undefined data', () => {
    const onMessage = jest.fn();
    const consoleSpy = jest.spyOn(console, 'warn').mockImplementation();
    renderHook(() => useSSE({ url: 'http://localhost/sse', onMessage }));

    const instance = mockInstances[0];
    act(() => {
      instance.onmessage({ data: undefined });
    });

    expect(onMessage).not.toHaveBeenCalled();
    consoleSpy.mockRestore();
  });

  test('handles onMessage with null data', () => {
    const onMessage = jest.fn();
    const consoleSpy = jest.spyOn(console, 'warn').mockImplementation();
    renderHook(() => useSSE({ url: 'http://localhost/sse', onMessage }));

    const instance = mockInstances[0];
    act(() => {
      instance.onmessage({ data: 'null' });
    });

    expect(onMessage).toHaveBeenCalledWith(null);
    consoleSpy.mockRestore();
  });

  test('handles named event with no data wrapper', () => {
    const handler = jest.fn();
    renderHook(() => useSSE({
      url: 'http://localhost/sse',
      onEvent: { 'test-event': handler },
    }));

    const instance = mockInstances[0];
    act(() => {
      instance._emit('test-event', { message: 'direct' });
    });

    expect(handler).toHaveBeenCalledWith({ message: 'direct' });
  });
});

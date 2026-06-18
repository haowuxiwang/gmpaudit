/**
 * Tests for useSSE hook.
 * Covers connection lifecycle, message handling, event dispatch, error/reconnect.
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

  // Helper: simulate events for testing
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

describe('useSSE', () => {
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

  test('cleans up on unmount', () => {
    const { unmount } = renderHook(() => useSSE({ url: 'http://localhost/sse' }));
    unmount();
    expect(mockClose).toHaveBeenCalled();
  });

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

  // --- onMessage handling (lines 75-81) ---
  test('calls onMessage with parsed data when message received', () => {
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
      // Simulate malformed data
      instance.onmessage({ data: 'not-json' });
    });

    expect(onMessage).not.toHaveBeenCalled();
    consoleSpy.mockRestore();
  });

  // --- Named event handling (lines 86-101) ---
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

    // The handler should be called with unwrapped data
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

  // --- onOpen callback (lines 66-72) ---
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

    // Trigger some errors first
    act(() => {
      instance._emitError();
      instance._emitError();
      instance._emitError();
      instance._emitError(); // 4th error triggers connectionError
    });

    // Now connect successfully
    act(() => {
      instance._emitOpen();
    });

    expect(result.current.connectionError).toBe(false);
    expect(result.current.reconnectCount).toBe(0);
  });

  // --- Error handling and reconnection (lines 104-116) ---
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

  // --- close() function (lines 39-45) ---
  test('close function closes the EventSource', () => {
    const { result } = renderHook(() => useSSE({ url: 'http://localhost/sse' }));

    act(() => {
      result.current.close();
    });

    expect(mockClose).toHaveBeenCalled();
  });

  // --- URL change cleanup (lines 57-60) ---
  test('closes existing source when url changes', () => {
    const { rerender } = renderHook(
      ({ url }) => useSSE({ url }),
      { initialProps: { url: 'http://localhost/sse1' } }
    );

    expect(mockInstances).toHaveLength(1);

    rerender({ url: 'http://localhost/sse2' });

    // Old source should be closed
    expect(mockClose).toHaveBeenCalled();
    // New source should be created
    expect(mockInstances).toHaveLength(2);
  });

  // --- Enabled toggle ---
  test('disconnects when enabled changes to false', () => {
    const { rerender } = renderHook(
      ({ enabled }) => useSSE({ url: 'http://localhost/sse', enabled }),
      { initialProps: { enabled: true } }
    );

    expect(mockInstances).toHaveLength(1);

    rerender({ enabled: false });

    expect(mockClose).toHaveBeenCalled();
  });

  // --- ReadyState tracking ---
  test('tracks readyState changes', () => {
    const { result } = renderHook(() => useSSE({ url: 'http://localhost/sse' }));

    const instance = mockInstances[0];

    // Initially CONNECTING
    expect(result.current.readyState).toBe(0);

    act(() => {
      instance._emitOpen();
    });

    expect(result.current.readyState).toBe(1); // OPEN
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

  // --- Multiple named events ---
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

  // --- Named event JSON parse error (line 96) ---
  test('handles JSON parse error in named event listener', () => {
    const handler = jest.fn();
    const consoleSpy = jest.spyOn(console, 'warn').mockImplementation();
    renderHook(() => useSSE({
      url: 'http://localhost/sse',
      onEvent: { 'test-event': handler },
    }));

    const instance = mockInstances[0];
    act(() => {
      // Simulate malformed data for a named event
      const listeners = (instance as any)._listeners['test-event'];
      if (listeners && listeners.length > 0) {
        listeners[0]({ data: 'not-json' });
      }
    });

    expect(handler).not.toHaveBeenCalled();
    expect(consoleSpy).toHaveBeenCalled();
    consoleSpy.mockRestore();
  });

  // --- Race condition protection (lines 58-59) ---
  test('closes existing source before creating new one on url change', () => {
    const { rerender } = renderHook(
      ({ url }) => useSSE({ url }),
      { initialProps: { url: 'http://localhost/sse1' } }
    );

    expect(mockInstances).toHaveLength(1);

    // Change URL - should close old source first
    rerender({ url: 'http://localhost/sse2' });

    // Old source should be closed
    expect(mockClose).toHaveBeenCalled();
    // New source should be created
    expect(mockInstances).toHaveLength(2);
  });
});

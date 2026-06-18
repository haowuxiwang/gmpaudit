/**
 * Tests for useTaskSSE hook.
 * Mocks useSSE to control event dispatching.
 */

import { renderHook, act } from '@testing-library/react';
import { useTaskSSE } from '../useTaskSSE';

// Mock useSSE
const mockSSEHook = {
  close: jest.fn(),
  readyState: 1, // OPEN
  connectionError: false,
  reconnectCount: 0,
};

let sseConfig: any = null;

jest.mock('../useSSE', () => ({
  useSSE: (config: any) => {
    sseConfig = config;
    return mockSSEHook;
  },
}));

jest.mock('../../services/api', () => ({
  API_BASE_URL: 'http://localhost:8000/api',
}));

describe('useTaskSSE', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    sseConfig = null;
    mockSSEHook.connectionError = false;
  });

  test('returns initial state', () => {
    const { result } = renderHook(() => useTaskSSE(null, false));
    expect(result.current.events).toEqual([]);
    expect(result.current.progress).toBe(0);
    expect(result.current.status).toBe('pending');
    expect(result.current.currentStage).toBe('pending');
    expect(result.current.isConnected).toBe(false);
  });

  test('does not connect when taskId is null', () => {
    renderHook(() => useTaskSSE(null, true));
    expect(sseConfig?.url).toBeNull();
  });

  test('does not connect when isActive is false', () => {
    renderHook(() => useTaskSSE(1, false));
    expect(sseConfig?.url).toBeNull();
  });

  test('connects when taskId and isActive are set', () => {
    renderHook(() => useTaskSSE(42, true));
    expect(sseConfig?.url).toBe('http://localhost:8000/api/audit/tasks/42/stream');
  });

  test('handles done event with completed status', () => {
    const { result } = renderHook(() => useTaskSSE(1, true));

    act(() => {
      sseConfig.onEvent.done({ status: 'completed' });
    });

    expect(result.current.status).toBe('completed');
    expect(result.current.progress).toBe(100);
    expect(result.current.currentStage).toBe('completed');
  });

  test('handles done event with failed status', () => {
    const { result } = renderHook(() => useTaskSSE(1, true));

    act(() => {
      sseConfig.onEvent.done({ status: 'failed' });
    });

    expect(result.current.status).toBe('failed');
    expect(result.current.currentStage).toBe('failed');
  });

  test('handles progress event', () => {
    const { result } = renderHook(() => useTaskSSE(1, true));

    act(() => {
      sseConfig.onEvent.progress({ percent: 50, stage: 'risk' });
    });

    expect(result.current.progress).toBe(50);
    expect(result.current.currentStage).toBe('risk');
  });

  test('handles agent_thinking event', () => {
    const { result } = renderHook(() => useTaskSSE(1, true));

    act(() => {
      sseConfig.onEvent.agent_thinking({
        stage: 'regulation',
        status: 'started',
        node: 'regulation_expert',
        message: 'Analyzing...',
      });
    });

    expect(result.current.currentStage).toBe('regulation');
    expect(result.current.thinkingEvents).toHaveLength(1);
  });

  test('handles event with stage progress fallback', () => {
    const { result } = renderHook(() => useTaskSSE(1, true));

    act(() => {
      sseConfig.onEvent.event({ stage: 'parsing', message: 'parsing doc' });
    });

    expect(result.current.events).toHaveLength(1);
    expect(result.current.progress).toBe(5); // STAGE_PROGRESS_MAP.parsing = 5
  });

  test('resetProgress clears state', () => {
    const { result } = renderHook(() => useTaskSSE(1, true));

    // Set some state
    act(() => {
      sseConfig.onEvent.progress({ percent: 50, stage: 'risk' });
    });
    expect(result.current.progress).toBe(50);

    // Reset
    act(() => {
      result.current.resetProgress();
    });

    expect(result.current.progress).toBe(0);
    expect(result.current.currentStage).toBe('pending');
    expect(result.current.status).toBe('pending');
    expect(result.current.events).toEqual([]);
  });

  test('progress never decreases', () => {
    const { result } = renderHook(() => useTaskSSE(1, true));

    act(() => {
      sseConfig.onEvent.progress({ percent: 50, stage: 'risk' });
    });
    expect(result.current.progress).toBe(50);

    act(() => {
      sseConfig.onEvent.progress({ percent: 30, stage: 'parsing' });
    });
    expect(result.current.progress).toBe(50); // stays at 50
  });
});

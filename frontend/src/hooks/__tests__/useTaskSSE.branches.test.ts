/**
 * Tests for useTaskSSE hook - branch coverage extension.
 * Covers cancelled status, multiple thinking events, stage progress map.
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

describe('useTaskSSE - branch coverage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    sseConfig = null;
    mockSSEHook.connectionError = false;
    mockSSEHook.readyState = 1;
  });

  // --- Initial state ---

  test('returns initial state with correct defaults', () => {
    const { result } = renderHook(() => useTaskSSE(null, false));
    expect(result.current.events).toEqual([]);
    expect(result.current.progress).toBe(0);
    expect(result.current.status).toBe('pending');
    expect(result.current.currentStage).toBe('pending');
    expect(result.current.isConnected).toBe(false);
    expect(result.current.thinkingEvents).toEqual([]);
  });

  // --- Connection conditions ---

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

  test('connects with different task IDs', () => {
    renderHook(() => useTaskSSE(100, true));
    expect(sseConfig?.url).toBe('http://localhost:8000/api/audit/tasks/100/stream');
  });

  // --- Done event branches ---

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

  test('handles done event with cancelled status', () => {
    const { result } = renderHook(() => useTaskSSE(1, true));

    act(() => {
      sseConfig.onEvent.done({ status: 'cancelled' });
    });

    expect(result.current.status).toBe('cancelled');
    // cancelled maps to 'failed' stage in the implementation
    expect(result.current.currentStage).toBe('failed');
  });

  test('handles done event with unknown status', () => {
    const { result } = renderHook(() => useTaskSSE(1, true));

    act(() => {
      sseConfig.onEvent.done({ status: 'unknown' });
    });

    expect(result.current.status).toBe('unknown');
  });

  // --- Progress event branches ---

  test('handles progress event with percent', () => {
    const { result } = renderHook(() => useTaskSSE(1, true));

    act(() => {
      sseConfig.onEvent.progress({ percent: 50, stage: 'risk' });
    });

    expect(result.current.progress).toBe(50);
    expect(result.current.currentStage).toBe('risk');
  });

  test('handles progress event with 0 percent', () => {
    const { result } = renderHook(() => useTaskSSE(1, true));

    act(() => {
      sseConfig.onEvent.progress({ percent: 0, stage: 'parsing' });
    });

    expect(result.current.progress).toBe(0);
    expect(result.current.currentStage).toBe('parsing');
  });

  test('handles progress event with 100 percent', () => {
    const { result } = renderHook(() => useTaskSSE(1, true));

    act(() => {
      sseConfig.onEvent.progress({ percent: 100, stage: 'completed' });
    });

    expect(result.current.progress).toBe(100);
    expect(result.current.currentStage).toBe('completed');
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
    expect(result.current.progress).toBe(50);
  });

  test('progress increases when new value is higher', () => {
    const { result } = renderHook(() => useTaskSSE(1, true));

    act(() => {
      sseConfig.onEvent.progress({ percent: 30, stage: 'parsing' });
    });
    expect(result.current.progress).toBe(30);

    act(() => {
      sseConfig.onEvent.progress({ percent: 60, stage: 'risk' });
    });
    expect(result.current.progress).toBe(60);
  });

  // --- Agent thinking event branches ---

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
    expect(result.current.thinkingEvents[0].stage).toBe('regulation');
  });

  test('handles multiple agent_thinking events', () => {
    const { result } = renderHook(() => useTaskSSE(1, true));

    act(() => {
      sseConfig.onEvent.agent_thinking({
        stage: 'parsing',
        status: 'started',
        node: 'parse_doc',
        message: 'Parsing...',
      });
    });

    act(() => {
      sseConfig.onEvent.agent_thinking({
        stage: 'parsing',
        status: 'completed',
        node: 'parse_doc',
        message: 'Done',
      });
    });

    act(() => {
      sseConfig.onEvent.agent_thinking({
        stage: 'regulation',
        status: 'started',
        node: 'regulation_expert',
        message: 'Searching...',
      });
    });

    expect(result.current.thinkingEvents).toHaveLength(3);
    expect(result.current.currentStage).toBe('regulation');
  });

  test('handles agent_thinking with different stages', () => {
    const { result } = renderHook(() => useTaskSSE(1, true));

    const stages = ['parsing', 'regulation', 'risk', 'report'];
    stages.forEach((stage) => {
      act(() => {
        sseConfig.onEvent.agent_thinking({
          stage,
          status: 'started',
          node: `${stage}_node`,
          message: `${stage} started`,
        });
      });
    });

    expect(result.current.thinkingEvents).toHaveLength(4);
    expect(result.current.currentStage).toBe('report');
  });

  // --- Event with stage progress fallback ---

  test('handles event with stage in STAGE_PROGRESS_MAP', () => {
    const { result } = renderHook(() => useTaskSSE(1, true));

    act(() => {
      sseConfig.onEvent.event({ stage: 'parsing', message: 'parsing doc' });
    });

    expect(result.current.events).toHaveLength(1);
    expect(result.current.progress).toBe(5); // STAGE_PROGRESS_MAP.parsing = 5
  });

  test('handles event with regulation stage', () => {
    const { result } = renderHook(() => useTaskSSE(1, true));

    act(() => {
      sseConfig.onEvent.event({ stage: 'regulation', message: 'searching regulations' });
    });

    expect(result.current.events).toHaveLength(1);
    expect(result.current.progress).toBe(25); // STAGE_PROGRESS_MAP.regulation = 25
  });

  test('handles event with risk stage', () => {
    const { result } = renderHook(() => useTaskSSE(1, true));

    act(() => {
      sseConfig.onEvent.event({ stage: 'risk', message: 'assessing risk' });
    });

    expect(result.current.events).toHaveLength(1);
    expect(result.current.progress).toBe(50); // STAGE_PROGRESS_MAP.risk = 50
  });

  test('handles event with report stage', () => {
    const { result } = renderHook(() => useTaskSSE(1, true));

    act(() => {
      sseConfig.onEvent.event({ stage: 'report', message: 'generating report' });
    });

    expect(result.current.events).toHaveLength(1);
    expect(result.current.progress).toBe(70); // STAGE_PROGRESS_MAP.report = 70
  });

  test('handles event with unknown stage', () => {
    const { result } = renderHook(() => useTaskSSE(1, true));

    act(() => {
      sseConfig.onEvent.event({ stage: 'unknown', message: 'unknown stage' });
    });

    expect(result.current.events).toHaveLength(1);
    // Unknown stage should not change progress
    expect(result.current.progress).toBe(0);
  });

  test('handles event without stage', () => {
    const { result } = renderHook(() => useTaskSSE(1, true));

    act(() => {
      sseConfig.onEvent.event({ message: 'no stage event' });
    });

    expect(result.current.events).toHaveLength(1);
  });

  // --- Multiple events accumulation ---

  test('accumulates multiple events', () => {
    const { result } = renderHook(() => useTaskSSE(1, true));

    act(() => {
      sseConfig.onEvent.event({ stage: 'parsing', message: 'event 1' });
    });
    act(() => {
      sseConfig.onEvent.event({ stage: 'regulation', message: 'event 2' });
    });
    act(() => {
      sseConfig.onEvent.event({ stage: 'risk', message: 'event 3' });
    });

    expect(result.current.events).toHaveLength(3);
  });

  // --- resetProgress ---

  test('resetProgress clears all state', () => {
    const { result } = renderHook(() => useTaskSSE(1, true));

    act(() => {
      sseConfig.onEvent.progress({ percent: 50, stage: 'risk' });
    });
    act(() => {
      sseConfig.onEvent.agent_thinking({
        stage: 'risk',
        status: 'started',
        node: 'risk_assessor',
        message: 'Assessing...',
      });
    });
    act(() => {
      sseConfig.onEvent.event({ stage: 'risk', message: 'risk event' });
    });

    expect(result.current.progress).toBe(50);
    expect(result.current.thinkingEvents).toHaveLength(1);
    expect(result.current.events).toHaveLength(1);

    act(() => {
      result.current.resetProgress();
    });

    expect(result.current.progress).toBe(0);
    expect(result.current.currentStage).toBe('pending');
    expect(result.current.status).toBe('pending');
    expect(result.current.events).toEqual([]);
    expect(result.current.thinkingEvents).toEqual([]);
  });

  // --- isConnected ---

  test('isConnected is true when url is set (taskId and isActive)', () => {
    const { result } = renderHook(() => useTaskSSE(1, true));
    expect(result.current.isConnected).toBe(true);
  });

  test('isConnected is false when taskId is null', () => {
    const { result } = renderHook(() => useTaskSSE(null, true));
    expect(result.current.isConnected).toBe(false);
  });

  test('isConnected is false when isActive is false', () => {
    const { result } = renderHook(() => useTaskSSE(1, false));
    expect(result.current.isConnected).toBe(false);
  });

  // --- Edge cases ---

  test('handles progress event without percent', () => {
    const { result } = renderHook(() => useTaskSSE(1, true));

    act(() => {
      sseConfig.onEvent.progress({ stage: 'parsing' });
    });

    expect(result.current.currentStage).toBe('parsing');
  });

  test('handles done event without status', () => {
    const { result } = renderHook(() => useTaskSSE(1, true));

    act(() => {
      sseConfig.onEvent.done({});
    });

    expect(result.current.status).toBeUndefined();
  });

  test('handles agent_thinking without message', () => {
    const { result } = renderHook(() => useTaskSSE(1, true));

    act(() => {
      sseConfig.onEvent.agent_thinking({
        stage: 'parsing',
        status: 'started',
        node: 'parse_doc',
      });
    });

    expect(result.current.thinkingEvents).toHaveLength(1);
  });

  test('handles rapid successive events', () => {
    const { result } = renderHook(() => useTaskSSE(1, true));

    act(() => {
      for (let i = 0; i < 10; i++) {
        sseConfig.onEvent.progress({ percent: i * 10, stage: 'parsing' });
      }
    });

    expect(result.current.progress).toBe(90);
  });

  test('handles mixed event types in sequence', () => {
    const { result } = renderHook(() => useTaskSSE(1, true));

    act(() => {
      sseConfig.onEvent.event({ stage: 'parsing', message: 'start' });
      sseConfig.onEvent.progress({ percent: 25, stage: 'parsing' });
      sseConfig.onEvent.agent_thinking({
        stage: 'parsing',
        status: 'completed',
        node: 'parse_doc',
        message: 'Done',
      });
      sseConfig.onEvent.progress({ percent: 50, stage: 'regulation' });
      sseConfig.onEvent.done({ status: 'completed' });
    });

    expect(result.current.status).toBe('completed');
    expect(result.current.progress).toBe(100);
    expect(result.current.events).toHaveLength(1);
    expect(result.current.thinkingEvents).toHaveLength(1);
  });
});

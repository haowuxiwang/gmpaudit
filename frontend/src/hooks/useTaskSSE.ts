import { useState, useEffect, useRef } from 'react';
import { useSSE } from './useSSE';
import { API_BASE_URL } from '../services/api';
import type { TaskEvent, AgentThinkingEvent } from '../types/api';

// Must match backend task_runner.py NODE_PROGRESS_MAP
const STAGE_PROGRESS_MAP: Record<string, number> = {
  parsing: 5,
  regulation: 25,
  risk: 50,
  report: 70,
  completed: 100,
};

const MAX_EVENTS = 200;

interface UseTaskSSEReturn {
  events: TaskEvent[];
  thinkingEvents: AgentThinkingEvent[];
  currentStage: string;
  lastActiveStage: string;
  progress: number;
  status: string;
  isConnected: boolean;
  connectionError: boolean;
  resetProgress: () => void;
}

export function useTaskSSE(taskId: number | null, isActive: boolean): UseTaskSSEReturn {
  const [events, setEvents] = useState<TaskEvent[]>([]);
  const [thinkingEvents, setThinkingEvents] = useState<AgentThinkingEvent[]>([]);
  const [currentStage, setCurrentStage] = useState('pending');
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState('pending');
  const eventsRef = useRef<TaskEvent[]>([]);
  const lastActiveStageRef = useRef('pending');

  // Debug logging helper — uses refs to avoid stale closures in useEffect
  const stateRef = useRef({ taskId, isActive, currentStage, progress, status });
  stateRef.current = { taskId, isActive, currentStage, progress, status };
  const logSSE = (action: string, data?: unknown) => {
    const s = stateRef.current;
    console.log(`[useTaskSSE] ${action}`, data ?? '', { taskId: s.taskId, isActive: s.isActive, stage: s.currentStage, progress: s.progress, status: s.status });
  };

  // Reset state when task changes (but keep progress for same task)
  const prevTaskIdRef = useRef<number | null>(null);
  const prevIsActiveRef = useRef(false);
  useEffect(() => {
    if (taskId !== prevTaskIdRef.current) {
      logSSE('task changed, resetting', { from: prevTaskIdRef.current, to: taskId });
      setEvents([]);
      setThinkingEvents([]);
      setCurrentStage('pending');
      setProgress(0);
      setStatus('pending');
      eventsRef.current = [];
      prevTaskIdRef.current = taskId;
    }
  }, [taskId]);

  // When isActive transitions from false to true, only reset events (keep progress)
  useEffect(() => {
    if (isActive && !prevIsActiveRef.current) {
      logSSE('isActive: false -> true (SSE connecting)');
    } else if (!isActive && prevIsActiveRef.current) {
      logSSE('isActive: true -> false (SSE disconnecting)');
    }
    prevIsActiveRef.current = isActive;
  }, [isActive]);

  const url = taskId && isActive
    ? `${API_BASE_URL}/audit/tasks/${taskId}/stream`
    : null;

  // Log SSE connection state changes
  const prevUrlRef = useRef<string | null>(null);
  useEffect(() => {
    if (url !== prevUrlRef.current) {
      logSSE('SSE url changed', { from: prevUrlRef.current, to: url });
      prevUrlRef.current = url;
    }
  }, [url]);

  const { connectionError } = useSSE({
    url,
    onEvent: {
      event: (raw: unknown) => {
        const data = raw as TaskEvent;
        const next = [...eventsRef.current, data];
        eventsRef.current = next.length > MAX_EVENTS ? next.slice(-MAX_EVENTS) : next;
        setEvents([...eventsRef.current]);
        // Fallback progress from stage events
        const stageProgress = STAGE_PROGRESS_MAP[data.stage];
        if (stageProgress !== undefined) {
          setProgress(prev => Math.max(prev, stageProgress));
        }
      },
      agent_thinking: (raw: unknown) => {
        const data = raw as AgentThinkingEvent;
        const MAX_THINKING_EVENTS = 500;
        setThinkingEvents(prev => {
          const next = [...prev, data];
          return next.length > MAX_THINKING_EVENTS ? next.slice(-MAX_THINKING_EVENTS) : next;
        });
        if (data.stage && data.status === 'started') {
          logSSE('stage <- agent_thinking', { to: data.stage });
          setCurrentStage(data.stage);
          lastActiveStageRef.current = data.stage;
        }
      },
      progress: (raw: unknown) => {
        const data = raw as { percent: number; stage: string };
        setProgress(prev => Math.max(prev, data.percent));
        if (data.stage) {
          logSSE('stage <- progress', { to: data.stage });
          setCurrentStage(data.stage);
          lastActiveStageRef.current = data.stage;
        }
      },
      done: (raw: unknown) => {
        const data = raw as { status: string };
        logSSE('done', { status: data.status });
        setStatus(data.status);
        if (data.status === 'completed') {
          setProgress(100);
          setCurrentStage('completed');
        } else if (data.status === 'failed' || data.status === 'cancelled') {
          setProgress(prev => prev); // keep current progress
          setCurrentStage('failed');
        } else if (data.status === 'awaiting_review') {
          setProgress(90);
          setCurrentStage('awaiting_review');
        } else {
          setProgress(90);
        }
      },
    },
    onError: () => {
      // Browser handles reconnection automatically
    },
    enabled: isActive,
  });

  // Reset progress — call when task restarts (e.g. after approve)
  const resetProgress = () => {
    setProgress(0);
    setCurrentStage('pending');
    setStatus('pending');
    lastActiveStageRef.current = 'pending';
    setEvents([]);
    setThinkingEvents([]);
    eventsRef.current = [];
  };

  return {
    events,
    thinkingEvents,
    currentStage,
    lastActiveStage: lastActiveStageRef.current,
    progress,
    status,
    isConnected: !!url,
    connectionError,
    resetProgress,
  };
}

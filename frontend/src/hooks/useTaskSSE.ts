import { useState, useEffect, useRef } from 'react';
import { useSSE } from './useSSE';
import { API_BASE_URL } from '../services/api';
import type { TaskEvent, AgentThinkingEvent } from '../types/api';

const STAGE_PROGRESS_MAP: Record<string, number> = {
  parsing: 10,
  regulation: 35,
  risk: 60,
  report: 80,
  completed: 100,
};

interface UseTaskSSEReturn {
  events: TaskEvent[];
  thinkingEvents: AgentThinkingEvent[];
  currentStage: string;
  progress: number;
  status: string;
  isConnected: boolean;
}

export function useTaskSSE(taskId: number | null, isActive: boolean): UseTaskSSEReturn {
  const [events, setEvents] = useState<TaskEvent[]>([]);
  const [thinkingEvents, setThinkingEvents] = useState<AgentThinkingEvent[]>([]);
  const [currentStage, setCurrentStage] = useState('pending');
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState('pending');
  const eventsRef = useRef<TaskEvent[]>([]);

  // Reset state when task changes
  useEffect(() => {
    setEvents([]);
    setThinkingEvents([]);
    setCurrentStage('pending');
    setProgress(0);
    setStatus('pending');
    eventsRef.current = [];
  }, [taskId]);

  const url = taskId && isActive
    ? `${API_BASE_URL}/audit/tasks/${taskId}/stream`
    : null;

  useSSE({
    url,
    onEvent: {
      event: (data: TaskEvent) => {
        eventsRef.current = [...eventsRef.current, data];
        setEvents([...eventsRef.current]);
        // Fallback progress from stage events
        const stageProgress = STAGE_PROGRESS_MAP[data.stage];
        if (stageProgress !== undefined) {
          setProgress(prev => Math.max(prev, stageProgress));
        }
      },
      agent_thinking: (data: AgentThinkingEvent) => {
        setThinkingEvents(prev => [...prev, data]);
        if (data.stage && data.status === 'started') {
          setCurrentStage(data.stage);
        }
      },
      progress: (data: { percent: number; stage: string }) => {
        setProgress(data.percent);
        if (data.stage) {
          setCurrentStage(data.stage);
        }
      },
      done: (data: { status: string }) => {
        setStatus(data.status);
        setProgress(100);
      },
    },
    onError: () => {
      // Browser handles reconnection automatically
    },
    enabled: isActive,
  });

  return {
    events,
    thinkingEvents,
    currentStage,
    progress,
    status,
    isConnected: !!url,
  };
}

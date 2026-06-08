import { useEffect, useRef, useCallback, useState } from 'react';

interface UseSSEOptions {
  url: string | null;
  onMessage?: (data: any) => void;
  onEvent?: Record<string, (data: any) => void>;
  onError?: (error: Event) => void;
  onOpen?: () => void;
  enabled?: boolean;
}

interface UseSSEReturn {
  close: () => void;
  readyState: number;
  connectionError: boolean;
  reconnectCount: number;
}

const MAX_RECONNECT_ATTEMPTS = 3;

export function useSSE({ url, onMessage, onEvent, onError, onOpen, enabled = true }: UseSSEOptions): UseSSEReturn {
  const sourceRef = useRef<EventSource | null>(null);
  const onMessageRef = useRef(onMessage);
  const onErrorRef = useRef(onError);
  const onOpenRef = useRef(onOpen);
  const onEventRef = useRef(onEvent);
  const [readyState, setReadyState] = useState<number>(EventSource.CLOSED);
  const [connectionError, setConnectionError] = useState(false);
  const [reconnectCount, setReconnectCount] = useState(0);
  const errorCountRef = useRef(0);

  useEffect(() => {
    onMessageRef.current = onMessage;
    onErrorRef.current = onError;
    onOpenRef.current = onOpen;
    onEventRef.current = onEvent;
  }, [onMessage, onError, onOpen, onEvent]);

  const close = useCallback(() => {
    if (sourceRef.current) {
      sourceRef.current.close();
      sourceRef.current = null;
      setReadyState(EventSource.CLOSED);
    }
  }, []);

  useEffect(() => {
    if (!url || !enabled) {
      close();
      setConnectionError(false);
      errorCountRef.current = 0;
      setReconnectCount(0);
      return;
    }

    // Close any existing source before creating a new one (prevents race condition)
    if (sourceRef.current) {
      sourceRef.current.close();
      sourceRef.current = null;
    }

    const source = new EventSource(url);
    sourceRef.current = source;
    setReadyState(EventSource.CONNECTING);

    source.onopen = () => {
      setReadyState(EventSource.OPEN);
      setConnectionError(false);
      errorCountRef.current = 0;
      setReconnectCount(0);
      onOpenRef.current?.();
    };

    source.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        onMessageRef.current?.(data);
      } catch (err) {
        console.warn('SSE JSON parse error:', err);
      }
    };

    // Named event listeners — track for cleanup
    const listeners: Array<[string, EventListener]> = [];
    if (onEventRef.current) {
      for (const [eventType, handler] of Object.entries(onEventRef.current)) {
        const listener = ((event: MessageEvent) => {
          try {
            const raw = JSON.parse(event.data);
            // Backend wraps events in {"type": "...", "data": {...}} envelope.
            // Unwrap the inner data so handlers receive the payload directly.
            const data = raw?.data ?? raw;
            handler(data);
          } catch (err) {
            console.warn(`SSE parse error for event "${eventType}":`, err);
          }
        }) as EventListener;
        source.addEventListener(eventType, listener);
        listeners.push([eventType, listener]);
      }
    }

    source.onerror = (event) => {
      setReadyState(source.readyState);
      errorCountRef.current += 1;
      setReconnectCount(errorCountRef.current);

      // After MAX_RECONNECT_ATTEMPTS, mark as connection error
      if (errorCountRef.current >= MAX_RECONNECT_ATTEMPTS) {
        setConnectionError(true);
      }

      onErrorRef.current?.(event);
    };

    return () => {
      for (const [eventType, listener] of listeners) {
        source.removeEventListener(eventType, listener);
      }
      close();
    };
  }, [url, enabled, close]);

  return { close, readyState, connectionError, reconnectCount };
}

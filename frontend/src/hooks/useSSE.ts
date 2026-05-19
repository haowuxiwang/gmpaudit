import { useEffect, useRef, useCallback, useState } from 'react';

interface UseSSEOptions {
  url: string | null;
  onMessage?: (data: any) => void;
  onEvent?: Record<string, (data: any) => void>;
  onError?: (error: Event) => void;
  onOpen?: () => void;
  enabled?: boolean;
}

export function useSSE({ url, onMessage, onEvent, onError, onOpen, enabled = true }: UseSSEOptions) {
  const sourceRef = useRef<EventSource | null>(null);
  const onMessageRef = useRef(onMessage);
  const onErrorRef = useRef(onError);
  const onOpenRef = useRef(onOpen);
  const [readyState, setReadyState] = useState<number>(EventSource.CLOSED);

  useEffect(() => {
    onMessageRef.current = onMessage;
    onErrorRef.current = onError;
    onOpenRef.current = onOpen;
  }, [onMessage, onError, onOpen]);

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
      return;
    }

    const source = new EventSource(url);
    sourceRef.current = source;
    setReadyState(EventSource.CONNECTING);

    source.onopen = () => {
      setReadyState(EventSource.OPEN);
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

    // Named event listeners
    if (onEvent) {
      for (const [eventType, handler] of Object.entries(onEvent)) {
        source.addEventListener(eventType, ((event: MessageEvent) => {
          try {
            const data = JSON.parse(event.data);
            handler(data);
          } catch (err) {
            console.warn(`SSE parse error for event "${eventType}":`, err);
          }
        }) as EventListener);
      }
    }

    source.onerror = (event) => {
      setReadyState(source.readyState);
      onErrorRef.current?.(event);
    };

    return close;
  }, [url, enabled, close]); // eslint-disable-line react-hooks/exhaustive-deps

  return { close, readyState };
}

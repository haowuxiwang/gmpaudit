import { useEffect, useRef, useCallback } from 'react';

interface UseSSEOptions {
  url: string | null;
  onMessage: (data: any) => void;
  onError?: (error: Event) => void;
  enabled?: boolean;
}

export function useSSE({ url, onMessage, onError, enabled = true }: UseSSEOptions) {
  const sourceRef = useRef<EventSource | null>(null);
  const onMessageRef = useRef(onMessage);
  const onErrorRef = useRef(onError);

  useEffect(() => {
    onMessageRef.current = onMessage;
    onErrorRef.current = onError;
  }, [onMessage, onError]);

  const close = useCallback(() => {
    if (sourceRef.current) {
      sourceRef.current.close();
      sourceRef.current = null;
    }
  }, []);

  useEffect(() => {
    if (!url || !enabled) {
      close();
      return;
    }

    const source = new EventSource(url);
    sourceRef.current = source;

    source.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        onMessageRef.current(data);
      } catch (err) {
        console.warn('SSE JSON parse error:', err);
      }
    };

    source.onerror = (event) => {
      onErrorRef.current?.(event);
      // Let browser handle reconnection automatically
    };

    return close;
  }, [url, enabled, close]);

  return { close };
}

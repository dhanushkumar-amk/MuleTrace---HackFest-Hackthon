import { useState, useEffect, useRef, useCallback } from 'react';
import { AgentEvent } from './types';

interface UseInvestigationStreamOptions {
  sessionId: string | null;
  enabled?: boolean;
  onEvent?: (event: AgentEvent) => void;
  onDone?: () => void;
  onError?: (err: any) => void;
}

interface UseInvestigationStreamResult {
  events: AgentEvent[];
  activeEvent: AgentEvent | null;
  activeTool: string | null;
  activeThought: string | null;
  isStreaming: boolean;
  isDone: boolean;
  error: string | null;
  disconnect: () => void;
  reconnect: () => void;
}

export function useInvestigationStream({
  sessionId,
  enabled = true,
  onEvent,
  onDone,
  onError,
}: UseInvestigationStreamOptions): UseInvestigationStreamResult {
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isDone, setIsDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const eventSourceRef = useRef<EventSource | null>(null);
  const lastEventIdRef = useRef<string | null>(null);
  const seenEventKeysRef = useRef<Set<string>>(new Set());
  const isDoneRef = useRef<boolean>(false);

  const onEventRef = useRef(onEvent);
  const onDoneRef = useRef(onDone);
  const onErrorRef = useRef(onError);
  onEventRef.current = onEvent;
  onDoneRef.current = onDone;
  onErrorRef.current = onError;

  const disconnect = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    setIsStreaming(false);
  }, []);

  const connect = useCallback(() => {
    if (!sessionId || !enabled) return;

    disconnect();
    setIsStreaming(true);
    setError(null);

    const apiBase = import.meta.env.VITE_API_URL || '';
    let url = `${apiBase}/api/investigations/${encodeURIComponent(sessionId)}/events`;
    if (lastEventIdRef.current) {
      url += `?last_event_id=${encodeURIComponent(lastEventIdRef.current)}`;
    }

    const es = new EventSource(url);
    eventSourceRef.current = es;

    const handleIncoming = (type: AgentEvent['type'], e: MessageEvent) => {
      if (e.lastEventId) {
        lastEventIdRef.current = e.lastEventId;
      }

      if (!e.data || e.data === 'undefined' || e.data === 'null' || typeof e.data !== 'string') {
        return;
      }

      try {
        const parsed = JSON.parse(e.data);
        const eventData: AgentEvent = {
          ...parsed,
          type: type || parsed.type,
        };

        // Create a unique key for deduplication
        const eventKey = `${e.lastEventId || ''}-${eventData.type}-${eventData.call_id || ''}-${eventData.duration_ms || ''}-${(eventData.content || '').slice(0, 20)}`;

        if (seenEventKeysRef.current.has(eventKey)) {
          return;
        }
        seenEventKeysRef.current.add(eventKey);

        setEvents((prev) => [...prev, eventData]);
        onEventRef.current?.(eventData);

        if (eventData.type === 'done') {
          isDoneRef.current = true;
          setIsDone(true);
          setIsStreaming(false);
          disconnect();
          onDoneRef.current?.();
        } else if (eventData.type === 'error') {
          setError(eventData.message || 'Stream reported an error');
          onErrorRef.current?.(eventData);
        }
      } catch (err) {
        console.warn('Failed to parse SSE event data (ignoring non-JSON frame):', e.data);
      }
    };

    // Register handlers for distinct event names
    const eventTypes: AgentEvent['type'][] = ['thought', 'tool_call', 'tool_result', 'final', 'error', 'done'];
    eventTypes.forEach((type) => {
      es.addEventListener(type, (e: MessageEvent) => handleIncoming(type, e));
    });

    // Default message handler fallback
    es.onmessage = (e: MessageEvent) => {
      handleIncoming('thought', e);
    };

    es.onerror = (err) => {
      if (isDoneRef.current) {
        disconnect();
        return;
      }
      if (es.readyState === EventSource.CLOSED) {
        setIsStreaming(false);
      }
    };
  }, [sessionId, enabled, disconnect]);

  useEffect(() => {
    if (sessionId && enabled) {
      setEvents([]);
      seenEventKeysRef.current.clear();
      lastEventIdRef.current = null;
      isDoneRef.current = false;
      setIsDone(false);
      connect();
    } else {
      disconnect();
    }

    return () => {
      disconnect();
    };
  }, [sessionId, enabled, connect, disconnect]);

  // Derive active indicators
  const activeEvent = events.length > 0 ? events[events.length - 1] : null;

  let activeTool: string | null = null;
  let activeThought: string | null = null;

  for (let i = events.length - 1; i >= 0; i--) {
    const ev = events[i];
    if (!activeTool && (ev.type === 'tool_call' || ev.type === 'tool_result')) {
      activeTool = ev.tool || null;
    }
    if (!activeThought && ev.type === 'thought') {
      activeThought = ev.content || null;
    }
    if (activeTool && activeThought) break;
  }

  return {
    events,
    activeEvent,
    activeTool,
    activeThought,
    isStreaming,
    isDone,
    error,
    disconnect,
    reconnect: connect,
  };
}

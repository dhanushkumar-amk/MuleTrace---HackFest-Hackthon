import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useInvestigationStream } from '../sse';

// Mock EventSource
class MockEventSource {
  static instances: MockEventSource[] = [];
  url: string;
  listeners: Record<string, ((e: any) => void)[]> = {};
  readyState = 1;

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }

  addEventListener(type: string, listener: (e: any) => void) {
    if (!this.listeners[type]) this.listeners[type] = [];
    this.listeners[type].push(listener);
  }

  emit(type: string, data: any, lastEventId?: string) {
    const event = {
      type,
      data: JSON.stringify(data),
      lastEventId,
    };
    if (this.listeners[type]) {
      this.listeners[type].forEach((l) => l(event));
    }
    if (this.onmessage && type === 'message') {
      this.onmessage(event as any);
    }
  }

  onmessage: ((e: MessageEvent) => void) | null = null;
  onerror: ((e: any) => void) | null = null;

  close() {
    this.readyState = 2;
  }
}

describe('useInvestigationStream Hook', () => {
  beforeEach(() => {
    MockEventSource.instances = [];
    (global as any).EventSource = MockEventSource;
  });

  it('connects to event stream URL and parses events', () => {
    const { result } = renderHook(() =>
      useInvestigationStream({ sessionId: 'test_session_1' })
    );

    expect(MockEventSource.instances.length).toBe(1);
    const es = MockEventSource.instances[0];
    expect(es.url).toContain('/api/investigations/test_session_1/events');

    // Emit a thought event
    act(() => {
      es.emit('thought', { type: 'thought', content: 'Tracing money forward...' }, 'ev_1');
    });

    expect(result.current.events.length).toBe(1);
    expect(result.current.events[0].content).toBe('Tracing money forward...');
    expect(result.current.activeThought).toBe('Tracing money forward...');
  });

  it('deduplicates events when reconnecting with Last-Event-ID', () => {
    const { result } = renderHook(() =>
      useInvestigationStream({ sessionId: 'test_session_2' })
    );

    const es = MockEventSource.instances[0];

    // Emit two events
    act(() => {
      es.emit('tool_call', { type: 'tool_call', call_id: 'c1', tool: 'get_fraud_report' }, 'ev_1');
      es.emit('tool_result', { type: 'tool_result', call_id: 'c1', summary: 'Done' }, 'ev_2');
    });

    expect(result.current.events.length).toBe(2);

    // Duplicate event emission (same lastEventId & callId)
    act(() => {
      es.emit('tool_call', { type: 'tool_call', call_id: 'c1', tool: 'get_fraud_report' }, 'ev_1');
    });

    // Should NOT duplicate
    expect(result.current.events.length).toBe(2);
  });

  it('marks stream done on terminal done event', () => {
    const { result } = renderHook(() =>
      useInvestigationStream({ sessionId: 'test_session_3' })
    );

    const es = MockEventSource.instances[0];

    act(() => {
      es.emit('done', { type: 'done', session_id: 'test_session_3' }, 'ev_done');
    });

    expect(result.current.isDone).toBe(true);
    expect(result.current.isStreaming).toBe(false);
  });
});

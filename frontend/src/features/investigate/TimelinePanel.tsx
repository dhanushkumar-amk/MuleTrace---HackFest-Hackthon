import React, { useRef, useEffect, useState } from 'react';
import { AgentEvent, ToolInfo } from '@/api/types';
import {
  Sparkles,
  CheckCircle2,
  AlertCircle,
  ChevronDown,
  ChevronRight,
  Terminal,
  Clock,
  ArrowDownCircle,
  Cpu,
  Search,
} from 'lucide-react';
import { Badge } from '@/components/ui/Badge';
import { formatDuration } from '@/lib/formatters';

interface TimelinePanelProps {
  events: AgentEvent[];
  activeTool: string | null;
  activeThought: string | null;
  isStreaming: boolean;
  isDone: boolean;
  availableTools?: ToolInfo[];
  onSelectStep?: (callId: string) => void;
  className?: string;
}

export const TimelinePanel: React.FC<TimelinePanelProps> = ({
  events,
  activeTool,
  activeThought,
  isStreaming,
  isDone,
  availableTools = [],
  onSelectStep,
  className,
}) => {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [expandedSteps, setExpandedSteps] = useState<Record<string, boolean>>({});
  const [showJumpToBottom, setShowJumpToBottom] = useState(false);

  // Group events into step units (pair tool_call with tool_result)
  const steps = React.useMemo(() => {
    const list: Array<{
      stepNumber: number;
      callId: string;
      tool: string;
      arguments: Record<string, any>;
      thought?: string;
      summary?: string;
      duration_ms?: number;
      status: 'pending' | 'success' | 'error';
    }> = [];

    const callMap = new Map<string, any>();
    let stepCount = 0;

    let pendingThought = '';

    for (const ev of events) {
      if (ev.type === 'thought') {
        pendingThought = ev.content || '';
      } else if (ev.type === 'tool_call') {
        stepCount += 1;
        const callId = ev.call_id || `call_${stepCount}`;
        const item = {
          stepNumber: stepCount,
          callId,
          tool: ev.tool || 'tool',
          arguments: ev.arguments || {},
          thought: pendingThought,
          status: 'pending' as const,
        };
        callMap.set(callId, item);
        list.push(item);
        pendingThought = '';
      } else if (ev.type === 'tool_result') {
        const item = callMap.get(ev.call_id || '');
        if (item) {
          item.summary = ev.summary;
          item.duration_ms = ev.duration_ms;
          item.status = 'success';
        }
      } else if (ev.type === 'error') {
        const last = list[list.length - 1];
        if (last) {
          last.status = 'error';
          last.summary = ev.message;
        }
      }
    }

    return list;
  }, [events]);

  // Handle auto-scroll
  const scrollToBottom = () => {
    if (scrollRef.current) {
      scrollRef.current.scrollTo({
        top: scrollRef.current.scrollHeight,
        behavior: 'smooth',
      });
      setShowJumpToBottom(false);
    }
  };

  useEffect(() => {
    if (!showJumpToBottom) {
      scrollToBottom();
    }
  }, [events.length, activeThought, showJumpToBottom]);

  const handleScroll = () => {
    if (!scrollRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
    const isAtBottom = scrollHeight - scrollTop - clientHeight < 60;
    setShowJumpToBottom(!isAtBottom);
  };

  const toggleExpand = (callId: string) => {
    setExpandedSteps((prev) => ({
      ...prev,
      [callId]: !prev[callId],
    }));
  };

  // Tools the agent can choose from row
  const popularTools = availableTools.slice(0, 10);

  return (
    <div
      className={`h-full flex flex-col bg-[#090d16] border-r border-white/10 select-none overflow-hidden relative ${className || ''}`}
    >
      {/* Panel Header */}
      <div className="p-3.5 border-b border-white/10 bg-[#0e1526]/90 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          <Terminal className="w-4 h-4 text-indigo-400" />
          <span className="text-xs font-semibold text-slate-100 uppercase tracking-wider">
            Agent Activity
          </span>
          {isStreaming && (
            <span className="inline-flex items-center gap-1 text-[10px] text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/25">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              Thinking
            </span>
          )}
          {isDone && (
            <span className="inline-flex items-center gap-1 text-[10px] text-slate-300 bg-white/5 px-2 py-0.5 rounded-full border border-white/10">
              Completed ({steps.length} steps)
            </span>
          )}
        </div>
      </div>

      {/* Tool Selection Strip: "Tools the agent can choose from" */}
      <div className="px-3.5 py-2.5 border-b border-white/10 bg-[#0e1526]/50 overflow-x-auto">
        <div className="flex items-center justify-between text-[11px] text-slate-400 mb-1.5">
          <span>MCP Tool Belt ({availableTools.length || 20} tools)</span>
          {activeTool && (
            <span className="text-indigo-400 font-mono text-[10px] animate-pulse">
              Active: {activeTool}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 scrollbar-none">
          {popularTools.map((t) => {
            const isSelected = activeTool === t.name;
            return (
              <span
                key={t.name}
                className={`text-[10px] font-mono px-2 py-0.5 rounded-md border shrink-0 transition-all duration-200 ${
                  isSelected
                    ? 'bg-indigo-600 text-white border-indigo-400 shadow-md shadow-indigo-500/30 scale-105'
                    : 'bg-white/5 text-slate-400 border-white/10'
                }`}
              >
                {t.name}
              </span>
            );
          })}
        </div>
      </div>

      {/* Vertical Timeline Stream */}
      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto p-3.5 space-y-3"
      >
        {steps.map((st, idx) => {
          const isExpanded = !!expandedSteps[st.callId];
          const isLast = idx === steps.length - 1;

          return (
            <div
              key={st.callId}
              onClick={() => toggleExpand(st.callId)}
              className={`p-3 rounded-xl border transition-all duration-200 cursor-pointer ${
                isLast && isStreaming
                  ? 'bg-indigo-500/10 border-indigo-500/35 shadow-md shadow-indigo-500/10'
                  : 'bg-[#0e1526]/75 border-white/10 hover:border-white/20'
              }`}
            >
              {/* Header: Step Number, Tool Name, Duration */}
              <div className="flex items-center justify-between text-xs mb-1">
                <div className="flex items-center gap-2">
                  <span className="w-5 h-5 rounded-md bg-white/10 flex items-center justify-center font-mono text-[11px] font-bold text-slate-300 shrink-0">
                    {st.stepNumber}
                  </span>
                  <span className="font-semibold text-slate-100 font-mono">
                    {st.tool}
                  </span>
                </div>

                <div className="flex items-center gap-1.5 text-[11px] text-slate-400">
                  {st.duration_ms && (
                    <span className="tabular-nums font-mono">
                      {formatDuration(st.duration_ms)}
                    </span>
                  )}
                  {st.status === 'success' ? (
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                  ) : st.status === 'pending' ? (
                    <span className="w-2 h-2 rounded-full bg-indigo-400 animate-pulse" />
                  ) : (
                    <AlertCircle className="w-3.5 h-3.5 text-rose-400" />
                  )}
                  {isExpanded ? (
                    <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
                  ) : (
                    <ChevronRight className="w-3.5 h-3.5 text-slate-400" />
                  )}
                </div>
              </div>

              {/* Thought narrative if present */}
              {st.thought && (
                <p className="text-[11px] text-slate-400 italic mb-2 line-clamp-2 leading-relaxed">
                  "{st.thought}"
                </p>
              )}

              {/* Compact Result Summary */}
              {st.summary && (
                <div className="text-xs text-slate-300 font-medium bg-white/5 p-2 rounded-lg border border-white/5">
                  {st.summary}
                </div>
              )}

              {/* Expanded details (Arguments & Payload) */}
              {isExpanded && (
                <div className="mt-2.5 pt-2 border-t border-white/5 space-y-2">
                  <div className="text-[10px] uppercase font-semibold text-slate-400 tracking-wider">
                    Arguments
                  </div>
                  <pre className="text-[11px] font-mono text-slate-300 bg-black/40 p-2 rounded-md overflow-x-auto border border-white/5">
                    {JSON.stringify(st.arguments, null, 2)}
                  </pre>
                  <div className="text-[10px] font-mono text-slate-400">
                    Call ID: {st.callId}
                  </div>
                </div>
              )}
            </div>
          );
        })}

        {/* Shimmering Active Thought (Agent Reasoning) */}
        {isStreaming && activeThought && (
          <div className="p-3.5 rounded-xl border border-indigo-500/30 bg-indigo-950/20 animate-shimmer">
            <div className="flex items-center gap-2 text-xs font-semibold text-indigo-400 mb-1.5">
              <Sparkles className="w-3.5 h-3.5 animate-spin" />
              <span>Synthesizing next action...</span>
            </div>
            <p className="text-xs text-slate-300 leading-relaxed font-sans">
              {activeThought}
            </p>
          </div>
        )}
      </div>

      {/* "Jump to Latest" Floating Pill */}
      {showJumpToBottom && (
        <button
          onClick={scrollToBottom}
          className="absolute bottom-3 right-4 z-20 flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-indigo-600 text-white text-xs font-medium shadow-lg hover:bg-indigo-500 transition-all cursor-pointer active:scale-95"
        >
          <ArrowDownCircle className="w-3.5 h-3.5" />
          <span>Jump to latest</span>
        </button>
      )}
    </div>
  );
};

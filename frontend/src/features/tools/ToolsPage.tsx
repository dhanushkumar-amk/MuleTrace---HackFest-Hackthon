import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/api/client';
import { ToolInfo } from '@/api/types';
import {
  Wrench,
  Cpu,
  Search,
  Database,
  ShieldAlert,
  Brain,
  Layers,
  ArrowRight,
  CheckCircle2,
  Sparkles,
} from 'lucide-react';
import { Badge } from '@/components/ui/Badge';
import { Skeleton } from '@/components/ui/Skeleton';

export const ToolsPage: React.FC = () => {
  const [selectedKind, setSelectedKind] = useState<string>('all');
  const [search, setSearch] = useState('');

  const { data: tools = [], isLoading } = useQuery<ToolInfo[]>({
    queryKey: ['mcpTools'],
    queryFn: () => api.getTools(),
  });

  const toolKinds = ['all', 'query', 'algorithm', 'trace', 'freeze', 'memory'];

  // Popular tools used in the Ravi investigation run
  const demoRunTools = new Set([
    'get_fraud_report',
    'trace_money_forward',
    'get_account_profile',
    'find_shared_devices',
    'find_shared_phones',
    'find_cash_out_points',
    'build_freeze_list',
    'recall_past_cases',
    'save_case_to_memory',
  ]);

  const filteredTools = tools.filter((t) => {
    if (selectedKind !== 'all' && t.kind !== selectedKind) return false;
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      t.name.toLowerCase().includes(q) ||
      t.short_description?.toLowerCase().includes(q) ||
      t.kind?.toLowerCase().includes(q)
    );
  });

  return (
    <div className="h-full flex flex-col p-4 sm:p-8 max-w-6xl mx-auto space-y-6 overflow-y-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-white/10">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2.5">
            <Wrench className="w-6 h-6 text-amber-400" />
            <span>Model Context Protocol (MCP) Tool Belt</span>
          </h1>
          <p className="text-xs sm:text-sm text-slate-400 mt-1">
            20 high-performance tools exposed over MCP to the autonomous Groq investigation agent.
          </p>
        </div>

        <Badge variant="purple" size="md">
          MCP Server: In-Process & Stdio
        </Badge>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-[#0e1526]/80 p-3 rounded-2xl border border-white/10">
        <div className="relative w-full sm:w-80">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search tools by name, description, kind..."
            className="w-full pl-9 pr-4 py-2 bg-white/5 border border-white/10 rounded-xl text-xs text-slate-100 placeholder:text-slate-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          />
        </div>

        {/* Kind Filters */}
        <div className="flex items-center gap-1.5 overflow-x-auto w-full sm:w-auto pb-1 sm:pb-0">
          {toolKinds.map((k) => (
            <button
              key={k}
              onClick={() => setSelectedKind(k)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium uppercase tracking-wider transition-colors cursor-pointer select-none ${
                selectedKind === k
                  ? 'bg-indigo-600 text-white shadow-xs'
                  : 'bg-white/5 text-slate-400 hover:text-slate-200 border border-white/10'
              }`}
            >
              {k}
            </button>
          ))}
        </div>
      </div>

      {/* Tools Cards Grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-32 w-full" />
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filteredTools.map((tool) => {
            const wasUsed = demoRunTools.has(tool.name);

            return (
              <div
                key={tool.name}
                className="p-4 rounded-xl border border-white/10 bg-[#0e1526]/85 hover:border-amber-500/35 transition-all flex flex-col justify-between gap-3 shadow-sm group"
              >
                <div>
                  <div className="flex items-center justify-between gap-2 mb-2">
                    <span className="font-mono font-bold text-sm text-slate-100 flex items-center gap-2">
                      <Cpu className="w-4 h-4 text-amber-400 shrink-0" />
                      <span>{tool.name}</span>
                    </span>

                    <div className="flex items-center gap-1.5">
                      {wasUsed && (
                        <span className="text-[10px] font-semibold text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-md border border-emerald-500/20">
                          Active in Demo
                        </span>
                      )}
                      <span className="text-[10px] uppercase font-mono font-semibold px-2 py-0.5 rounded-md bg-white/5 text-slate-300 border border-white/10">
                        {tool.kind}
                      </span>
                    </div>
                  </div>

                  <p className="text-xs text-slate-300 leading-relaxed font-sans">
                    {tool.short_description || tool.description}
                  </p>
                </div>

                <div className="pt-2.5 border-t border-white/5 flex items-center justify-between text-[11px] text-slate-400 font-mono">
                  <span>Served over MCP Bridge</span>
                  <span className="text-indigo-400 group-hover:translate-x-1 transition-transform">
                    read-only query →
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

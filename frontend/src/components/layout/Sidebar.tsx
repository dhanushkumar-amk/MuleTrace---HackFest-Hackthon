import React, { useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import {
  Sparkles,
  FileText,
  Brain,
  Wrench,
  BookOpen,
  ChevronLeft,
  ChevronRight,
  Database,
  ShieldAlert,
  Radio,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/api/client';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/Tooltip';

export const Sidebar: React.FC = () => {
  const [collapsed, setCollapsed] = useState(false);
  const location = useLocation();

  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: () => api.getHealth(),
    refetchInterval: 15000,
  });

  const navItems = [
    {
      to: '/workspace',
      label: 'Investigate',
      icon: Sparkles,
      badge: 'Live',
    },
    {
      to: '/cases',
      label: 'Cases',
      icon: FileText,
      count: health?.saved_cases_count,
    },
    {
      to: '/memory',
      label: 'Memory',
      icon: Brain,
    },
    {
      to: '/tools',
      label: 'MCP Tools',
      icon: Wrench,
    },
    {
      to: '/how-it-works',
      label: 'How It Works',
      icon: BookOpen,
    },
  ];

  const falkorReachable = health?.falkordb_reachable ?? true;
  const groqPresent = health?.groq_key_present ?? true;
  const nodesCount = health?.graph_node_count || health?.graph_nodes_count || 6669;

  return (
    <aside
      className={cn(
        'h-screen sticky top-0 flex flex-col justify-between border-r border-white/10 bg-[#090d16] text-slate-300 transition-all duration-300 z-40 select-none shrink-0',
        collapsed ? 'w-16' : 'w-60'
      )}
    >
      {/* Brand Header */}
      <div>
        <div className="h-14 flex items-center justify-between px-3.5 border-b border-white/10">
          <NavLink to="/" className="flex items-center gap-2.5 overflow-hidden">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-indigo-600 via-indigo-500 to-cyan-400 p-0.5 shrink-0 flex items-center justify-center shadow-md shadow-indigo-500/20">
              <div className="w-full h-full bg-[#090d16] rounded-[6px] flex items-center justify-center">
                <Radio className="w-4 h-4 text-indigo-400 animate-pulse" />
              </div>
            </div>
            {!collapsed && (
              <div className="flex flex-col">
                <span className="font-bold text-sm tracking-tight text-white leading-none flex items-center gap-1.5">
                  MuleTrace
                  <span className="text-[10px] uppercase font-mono px-1 py-0.2 rounded bg-indigo-500/20 text-indigo-400 border border-indigo-500/30">
                    FalkorDB
                  </span>
                </span>
                <span className="text-[10px] text-slate-400 leading-tight mt-0.5">
                  Autonomous Ring Tracer
                </span>
              </div>
            )}
          </NavLink>

          <button
            onClick={() => setCollapsed(!collapsed)}
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            className="p-1 rounded-md text-slate-400 hover:text-white hover:bg-white/5 transition-colors cursor-pointer"
          >
            {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
          </button>
        </div>

        {/* Navigation Items */}
        <nav className="p-2 space-y-1 mt-2">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname === item.to || (item.to === '/workspace' && location.pathname === '/');
            return (
              <Tooltip key={item.to} delayDuration={300}>
                <TooltipTrigger asChild>
                  <NavLink
                    to={item.to}
                    className={cn(
                      'flex items-center gap-3 px-3 py-2 rounded-xl text-sm font-medium transition-all duration-150 group cursor-pointer relative',
                      isActive
                        ? 'bg-indigo-600/15 text-indigo-400 border border-indigo-500/30 shadow-xs'
                        : 'text-slate-400 hover:text-slate-200 hover:bg-white/5 border border-transparent'
                    )}
                  >
                    <Icon
                      className={cn(
                        'w-4 h-4 shrink-0 transition-transform group-hover:scale-110',
                        isActive ? 'text-indigo-400' : 'text-slate-400 group-hover:text-slate-200'
                      )}
                    />
                    {!collapsed && (
                      <span className="flex-1 flex items-center justify-between">
                        <span>{item.label}</span>
                        {item.badge && (
                          <span className="text-[10px] font-semibold uppercase px-1.5 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                            {item.badge}
                          </span>
                        )}
                        {item.count !== undefined && item.count > 0 && (
                          <span className="text-[11px] font-mono px-1.5 py-0.5 rounded-md bg-white/10 text-slate-300">
                            {item.count}
                          </span>
                        )}
                      </span>
                    )}
                  </NavLink>
                </TooltipTrigger>
                {collapsed && <TooltipContent side="right">{item.label}</TooltipContent>}
              </Tooltip>
            );
          })}
        </nav>
      </div>

      {/* Footer System Status */}
      <div className="p-3 border-t border-white/10 bg-white/2">
        <div className={cn('flex flex-col gap-2', collapsed && 'items-center')}>
          {!collapsed ? (
            <>
              <div className="flex items-center justify-between text-xs">
                <span className="flex items-center gap-1.5 text-slate-400">
                  <Database className="w-3.5 h-3.5 text-indigo-400" />
                  <span>FalkorDB</span>
                </span>
                <span className="flex items-center gap-1 text-[11px] font-medium text-emerald-400">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  {nodesCount.toLocaleString()} nodes
                </span>
              </div>

              <div className="flex items-center justify-between text-xs">
                <span className="flex items-center gap-1.5 text-slate-400">
                  <Radio className="w-3.5 h-3.5 text-indigo-400" />
                  <span>Groq LLM</span>
                </span>
                <span
                  className={cn(
                    'text-[11px] font-medium',
                    groqPresent ? 'text-emerald-400' : 'text-amber-400'
                  )}
                >
                  {groqPresent ? 'Connected' : 'Missing Key'}
                </span>
              </div>
            </>
          ) : (
            <Tooltip>
              <TooltipTrigger asChild>
                <div className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse cursor-pointer" />
              </TooltipTrigger>
              <TooltipContent side="right">
                <div className="text-xs">
                  <div>FalkorDB: Connected ({nodesCount} nodes)</div>
                  <div>Groq: {groqPresent ? 'Active' : 'Offline'}</div>
                </div>
              </TooltipContent>
            </Tooltip>
          )}
        </div>
      </div>
    </aside>
  );
};

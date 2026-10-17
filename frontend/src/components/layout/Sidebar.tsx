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

  const groqPresent = health?.groq_key_present ?? true;
  const nodesCount = health?.graph_node_count || health?.graph_nodes_count || 6669;

  return (
    <aside
      className={cn(
        'h-screen sticky top-0 flex flex-col justify-between border-r border-slate-200 bg-white text-slate-700 transition-all duration-300 z-40 select-none shrink-0 shadow-xs',
        collapsed ? 'w-16' : 'w-60'
      )}
    >
      {/* Brand Header */}
      <div>
        <div className="h-14 flex items-center justify-between px-3.5 border-b border-slate-100">
          <NavLink to="/" className="flex items-center gap-2.5 overflow-hidden">
            <div className="w-8 h-8 rounded-lg bg-indigo-600 p-0.5 shrink-0 flex items-center justify-center shadow-xs">
              <Radio className="w-4 h-4 text-white" />
            </div>
            {!collapsed && (
              <div className="flex flex-col">
                <span className="font-bold text-sm tracking-tight text-slate-900 leading-none flex items-center gap-1.5">
                  MuleTrace
                  <span className="text-[10px] uppercase font-mono px-1 py-0.2 rounded bg-indigo-50 text-indigo-700 border border-indigo-200">
                    FalkorDB
                  </span>
                </span>
                <span className="text-[10px] text-slate-500 leading-tight mt-0.5">
                  Autonomous Ring Tracer
                </span>
              </div>
            )}
          </NavLink>

          <button
            onClick={() => setCollapsed(!collapsed)}
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            className="p-1 rounded-md text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors cursor-pointer"
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
                        ? 'bg-indigo-50 text-indigo-700 font-semibold border border-indigo-100 shadow-2xs'
                        : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50 border border-transparent'
                    )}
                  >
                    <Icon
                      className={cn(
                        'w-4 h-4 shrink-0 transition-transform group-hover:scale-105',
                        isActive ? 'text-indigo-600' : 'text-slate-400 group-hover:text-slate-700'
                      )}
                    />
                    {!collapsed && (
                      <span className="flex-1 flex items-center justify-between">
                        <span>{item.label}</span>
                        {item.badge && (
                          <span className="text-[10px] font-semibold uppercase px-1.5 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
                            {item.badge}
                          </span>
                        )}
                        {item.count !== undefined && item.count > 0 && (
                          <span className="text-[11px] font-mono px-1.5 py-0.5 rounded-md bg-slate-100 text-slate-600 border border-slate-200">
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
      <div className="p-3 border-t border-slate-100 bg-slate-50/50">
        <div className={cn('flex flex-col gap-2', collapsed && 'items-center')}>
          {!collapsed ? (
            <>
              <div className="flex items-center justify-between text-xs">
                <span className="flex items-center gap-1.5 text-slate-500">
                  <Database className="w-3.5 h-3.5 text-indigo-600" />
                  <span>FalkorDB</span>
                </span>
                <span className="flex items-center gap-1 text-[11px] font-medium text-emerald-700">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                  {nodesCount.toLocaleString()} nodes
                </span>
              </div>

              <div className="flex items-center justify-between text-xs">
                <span className="flex items-center gap-1.5 text-slate-500">
                  <Radio className="w-3.5 h-3.5 text-indigo-600" />
                  <span>Groq LLM</span>
                </span>
                <span
                  className={cn(
                    'text-[11px] font-medium',
                    groqPresent ? 'text-emerald-700' : 'text-amber-700'
                  )}
                >
                  {groqPresent ? 'Active' : 'Missing Key'}
                </span>
              </div>
            </>
          ) : (
            <Tooltip>
              <TooltipTrigger asChild>
                <div className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse cursor-pointer" />
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

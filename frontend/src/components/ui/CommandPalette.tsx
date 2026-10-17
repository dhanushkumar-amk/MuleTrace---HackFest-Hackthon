import React, { useEffect, useState } from 'react';
import { Command } from 'cmdk';
import { useNavigate } from 'react-router-dom';
import {
  Search,
  Play,
  FileText,
  Brain,
  Wrench,
  BookOpen,
  Copy,
  RotateCcw,
  Sparkles,
} from 'lucide-react';
import { toast } from 'sonner';
import { api } from '@/api/client';

export const CommandPalette: React.FC = () => {
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if ((e.key === 'k' || e.key === 'K') && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((open) => !open);
      }
    };
    document.addEventListener('keydown', down);
    return () => document.removeEventListener('keydown', down);
  }, []);

  const runAction = (fn: () => void) => {
    setOpen(false);
    fn();
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/30 backdrop-blur-2xs flex items-start justify-center pt-[15vh] px-4">
      <div
        className="w-full max-w-lg rounded-2xl border border-slate-200 bg-white shadow-2xl overflow-hidden text-slate-900 animate-in fade-in-0 zoom-in-95"
        onClick={(e) => e.stopPropagation()}
      >
        <Command className="w-full">
          <div className="flex items-center px-4 border-b border-slate-100 gap-2.5">
            <Search className="w-4 h-4 text-slate-400 shrink-0" />
            <Command.Input
              autoFocus
              placeholder="Type a command or jump to page..."
              className="w-full py-3.5 bg-transparent text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none font-sans"
            />
            <kbd className="text-[10px] bg-slate-100 text-slate-500 px-1.5 py-0.5 rounded font-mono border border-slate-200">
              ESC
            </kbd>
          </div>

          <Command.List className="max-h-72 overflow-y-auto p-2">
            <Command.Empty className="py-6 text-center text-xs text-slate-400">
              No results found.
            </Command.Empty>

            <Command.Group heading="Navigation" className="px-2 py-1 text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
              <Command.Item
                onSelect={() => runAction(() => navigate('/workspace'))}
                className="flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-slate-700 hover:bg-slate-100 hover:text-slate-900 cursor-pointer"
              >
                <Sparkles className="w-4 h-4 text-indigo-600" />
                <span>Investigation Workspace</span>
              </Command.Item>
              <Command.Item
                onSelect={() => runAction(() => navigate('/cases'))}
                className="flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-slate-700 hover:bg-slate-100 hover:text-slate-900 cursor-pointer"
              >
                <FileText className="w-4 h-4 text-blue-600" />
                <span>Cases Directory</span>
              </Command.Item>
              <Command.Item
                onSelect={() => runAction(() => navigate('/memory'))}
                className="flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-slate-700 hover:bg-slate-100 hover:text-slate-900 cursor-pointer"
              >
                <Brain className="w-4 h-4 text-violet-600" />
                <span>Graph Memory & Rings</span>
              </Command.Item>
              <Command.Item
                onSelect={() => runAction(() => navigate('/tools'))}
                className="flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-slate-700 hover:bg-slate-100 hover:text-slate-900 cursor-pointer"
              >
                <Wrench className="w-4 h-4 text-amber-600" />
                <span>MCP Tool Belt</span>
              </Command.Item>
              <Command.Item
                onSelect={() => runAction(() => navigate('/how-it-works'))}
                className="flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-slate-700 hover:bg-slate-100 hover:text-slate-900 cursor-pointer"
              >
                <BookOpen className="w-4 h-4 text-emerald-600" />
                <span>Architecture & How It Works</span>
              </Command.Item>
            </Command.Group>

            <Command.Group heading="Quick Actions" className="px-2 py-1 text-[11px] font-semibold text-slate-400 uppercase tracking-wider mt-2 border-t border-slate-100 pt-2">
              <Command.Item
                onSelect={() =>
                  runAction(() => {
                    navigate('/workspace?session_id=demo_ravi_run&mode=replay');
                    toast.success('Loaded Ravi Kumar recorded run');
                  })
                }
                className="flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-slate-700 hover:bg-slate-100 hover:text-slate-900 cursor-pointer"
              >
                <Play className="w-4 h-4 text-emerald-600" />
                <span>Load Ravi Demo (Recorded Mode)</span>
              </Command.Item>
              <Command.Item
                onSelect={() =>
                  runAction(() => {
                    navigate('/workspace?autorun=true&mode=replay');
                    toast.info('Auto-running Ravi investigation demo');
                  })
                }
                className="flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-slate-700 hover:bg-slate-100 hover:text-slate-900 cursor-pointer"
              >
                <RotateCcw className="w-4 h-4 text-indigo-600" />
                <span>Run Live Investigation</span>
              </Command.Item>
              <Command.Item
                onSelect={() =>
                  runAction(() => {
                    navigator.clipboard.writeText(window.location.origin + '/workspace');
                    toast.success('Workspace link copied');
                  })
                }
                className="flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-slate-700 hover:bg-slate-100 hover:text-slate-900 cursor-pointer"
              >
                <Copy className="w-4 h-4 text-slate-500" />
                <span>Copy Current Case Link</span>
              </Command.Item>
            </Command.Group>
          </Command.List>
        </Command>
      </div>
    </div>
  );
};

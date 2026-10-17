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
  Moon,
  Sun,
  Copy,
  RotateCcw,
  Sparkles,
} from 'lucide-react';
import { useThemeStore } from '@/lib/theme';
import { toast } from 'sonner';
import { api } from '@/api/client';

export const CommandPalette: React.FC = () => {
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  const { theme, toggleTheme } = useThemeStore();

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
    <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-start justify-center pt-[15vh] px-4">
      <div
        className="w-full max-w-lg rounded-2xl border border-white/15 bg-[#141c30] shadow-2xl overflow-hidden text-slate-100 animate-in fade-in-0 zoom-in-95"
        onClick={(e) => e.stopPropagation()}
      >
        <Command className="w-full">
          <div className="flex items-center px-4 border-b border-white/10 gap-2.5">
            <Search className="w-4 h-4 text-slate-400 shrink-0" />
            <Command.Input
              autoFocus
              placeholder="Type a command or jump to page..."
              className="w-full py-3.5 bg-transparent text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none font-sans"
            />
            <kbd className="text-[10px] bg-white/10 text-slate-400 px-1.5 py-0.5 rounded font-mono">
              ESC
            </kbd>
          </div>

          <Command.List className="max-h-72 overflow-y-auto p-2 space-y-1">
            <Command.Empty className="py-6 text-center text-xs text-slate-400">
              No results found.
            </Command.Empty>

            <Command.Group heading="Actions" className="text-[11px] font-semibold text-slate-500 uppercase px-2 py-1">
              <Command.Item
                onSelect={() =>
                  runAction(() => {
                    navigate('/workspace?autorun=true&mode=replay');
                    toast.success('Starting recorded demo run...');
                  })
                }
                className="flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-slate-200 hover:bg-indigo-600 hover:text-white cursor-pointer select-none transition-colors"
              >
                <Play className="w-4 h-4 text-emerald-400" />
                <span>Run Demo Investigation (Ravi FR_0001)</span>
              </Command.Item>

              <Command.Item
                onSelect={() =>
                  runAction(() => {
                    toggleTheme();
                    toast.success(`Theme switched to ${theme === 'dark' ? 'light' : 'dark'}`);
                  })
                }
                className="flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-slate-200 hover:bg-indigo-600 hover:text-white cursor-pointer select-none transition-colors"
              >
                {theme === 'dark' ? <Sun className="w-4 h-4 text-amber-400" /> : <Moon className="w-4 h-4 text-indigo-400" />}
                <span>Toggle Theme ({theme === 'dark' ? 'Light' : 'Dark'})</span>
              </Command.Item>
            </Command.Group>

            <Command.Group heading="Navigation" className="text-[11px] font-semibold text-slate-500 uppercase px-2 py-1 mt-2">
              <Command.Item
                onSelect={() => runAction(() => navigate('/workspace'))}
                className="flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-slate-200 hover:bg-indigo-600 hover:text-white cursor-pointer select-none transition-colors"
              >
                <Sparkles className="w-4 h-4 text-indigo-400" />
                <span>Investigation Workspace</span>
              </Command.Item>

              <Command.Item
                onSelect={() => runAction(() => navigate('/cases'))}
                className="flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-slate-200 hover:bg-indigo-600 hover:text-white cursor-pointer select-none transition-colors"
              >
                <FileText className="w-4 h-4 text-blue-400" />
                <span>Cases Directory</span>
              </Command.Item>

              <Command.Item
                onSelect={() => runAction(() => navigate('/memory'))}
                className="flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-slate-200 hover:bg-indigo-600 hover:text-white cursor-pointer select-none transition-colors"
              >
                <Brain className="w-4 h-4 text-violet-400" />
                <span>Case Memory</span>
              </Command.Item>

              <Command.Item
                onSelect={() => runAction(() => navigate('/tools'))}
                className="flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-slate-200 hover:bg-indigo-600 hover:text-white cursor-pointer select-none transition-colors"
              >
                <Wrench className="w-4 h-4 text-amber-400" />
                <span>MCP Tools Catalog</span>
              </Command.Item>

              <Command.Item
                onSelect={() => runAction(() => navigate('/how-it-works'))}
                className="flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-slate-200 hover:bg-indigo-600 hover:text-white cursor-pointer select-none transition-colors"
              >
                <BookOpen className="w-4 h-4 text-emerald-400" />
                <span>How It Works & Architecture</span>
              </Command.Item>
            </Command.Group>
          </Command.List>

          <div className="p-2 border-t border-white/10 bg-white/2 flex items-center justify-between text-[11px] text-slate-400 px-4">
            <span className="flex items-center gap-1.5">
              <span>Use</span>
              <kbd className="bg-white/10 px-1 py-0.5 rounded text-[10px]">↑</kbd>
              <kbd className="bg-white/10 px-1 py-0.5 rounded text-[10px]">↓</kbd>
              <span>to navigate</span>
            </span>
            <span className="flex items-center gap-1.5">
              <span>Press</span>
              <kbd className="bg-white/10 px-1 py-0.5 rounded text-[10px]">↵</kbd>
              <span>to select</span>
            </span>
          </div>
        </Command>
      </div>
      <div className="fixed inset-0 -z-10" onClick={() => setOpen(false)} />
    </div>
  );
};

import React from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  Search,
  Moon,
  Sun,
  Maximize2,
  Minimize2,
  Play,
  Film,
  Zap,
} from 'lucide-react';
import { useThemeStore } from '@/lib/theme';
import { Button } from '@/components/ui/Button';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/Tooltip';
import { Kbd } from '@/components/ui/Kbd';

interface TopBarProps {
  presenterMode: boolean;
  onTogglePresenter: () => void;
  investigationMode?: 'live' | 'replay';
}

export const TopBar: React.FC<TopBarProps> = ({
  presenterMode,
  onTogglePresenter,
  investigationMode = 'replay',
}) => {
  const location = useLocation();
  const navigate = useNavigate();
  const { theme, toggleTheme } = useThemeStore();

  const getBreadcrumb = () => {
    switch (location.pathname) {
      case '/':
        return 'Overview';
      case '/workspace':
        return 'Investigation Workspace';
      case '/cases':
        return 'Cases Directory';
      case '/memory':
        return 'Graph Case Memory';
      case '/tools':
        return 'MCP Tool Belt';
      case '/how-it-works':
        return 'Architecture & Logic';
      default:
        return 'Workspace';
    }
  };

  return (
    <header className="h-14 border-b border-white/10 bg-[#090d16]/80 backdrop-blur-md px-4 sm:px-6 flex items-center justify-between sticky top-0 z-30 select-none">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-xs sm:text-sm font-medium">
        <span className="text-slate-400">MuleTrace</span>
        <span className="text-slate-400">/</span>
        <span className="text-slate-100 font-semibold">{getBreadcrumb()}</span>
      </div>

      {/* Right Controls */}
      <div className="flex items-center gap-2 sm:gap-3">
        {/* Command palette trigger */}
        <button
          onClick={() => {
            const event = new KeyboardEvent('keydown', {
              key: 'k',
              ctrlKey: true,
              bubbles: true,
            });
            document.dispatchEvent(event);
          }}
          className="hidden md:flex items-center gap-2 px-2.5 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-xs text-slate-300 transition-colors cursor-pointer"
        >
          <Search className="w-3.5 h-3.5 text-slate-400" />
          <span>Quick actions</span>
          <div className="flex items-center gap-0.5 ml-2">
            <Kbd>⌘</Kbd>
            <Kbd>K</Kbd>
          </div>
        </button>

        {/* Mode Pill (Always Honest: Live vs Recorded) */}
        <Tooltip>
          <TooltipTrigger asChild>
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold border select-none cursor-help bg-indigo-500/10 text-indigo-300 border-indigo-500/25">
              {investigationMode === 'replay' ? (
                <>
                  <Film className="w-3 h-3 text-cyan-400" />
                  <span>Recorded Run</span>
                </>
              ) : (
                <>
                  <Zap className="w-3 h-3 text-emerald-400" />
                  <span>Live Agent</span>
                </>
              )}
            </div>
          </TooltipTrigger>
          <TooltipContent side="bottom">
            {investigationMode === 'replay'
              ? 'Demo replay mode: plays real verified run events deterministically'
              : 'Live agent mode: connects dynamically to Groq LLM and tool layer'}
          </TooltipContent>
        </Tooltip>

        {/* Presenter Mode Toggle */}
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="outline"
              size="icon"
              onClick={onTogglePresenter}
              aria-label={presenterMode ? 'Exit presenter mode' : 'Enter presenter mode'}
              className="hidden sm:inline-flex"
            >
              {presenterMode ? <Minimize2 className="w-4 h-4 text-amber-400" /> : <Maximize2 className="w-4 h-4" />}
            </Button>
          </TooltipTrigger>
          <TooltipContent side="bottom">
            Presenter Mode <Kbd className="ml-1">P</Kbd>
          </TooltipContent>
        </Tooltip>

        {/* Theme Toggle */}
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="outline"
              size="icon"
              onClick={toggleTheme}
              aria-label="Toggle dark/light theme"
            >
              {theme === 'dark' ? <Sun className="w-4 h-4 text-amber-400" /> : <Moon className="w-4 h-4 text-indigo-400" />}
            </Button>
          </TooltipTrigger>
          <TooltipContent side="bottom">
            Toggle {theme === 'dark' ? 'Light' : 'Dark'} Theme
          </TooltipContent>
        </Tooltip>

        {/* Quick Demo Button (if not on workspace) */}
        {location.pathname !== '/workspace' && (
          <Button
            variant="primary"
            size="sm"
            leftIcon={<Play className="w-3.5 h-3.5 fill-current" />}
            onClick={() => navigate('/workspace?autorun=true')}
          >
            Run Demo
          </Button>
        )}
      </div>
    </header>
  );
};

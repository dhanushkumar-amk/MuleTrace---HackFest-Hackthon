import React from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  Search,
  Maximize2,
  Minimize2,
  Play,
  Film,
  Zap,
} from 'lucide-react';
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
    <header className="h-14 border-b border-slate-200 bg-white/95 backdrop-blur-md px-4 sm:px-6 flex items-center justify-between sticky top-0 z-30 select-none">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-xs sm:text-sm font-medium">
        <span className="text-slate-500">MuleTrace</span>
        <span className="text-slate-300">/</span>
        <span className="text-slate-900 font-semibold">{getBreadcrumb()}</span>
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
          className="hidden md:flex items-center gap-2 px-2.5 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 border border-slate-200 text-xs text-slate-700 transition-colors cursor-pointer"
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
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold border select-none cursor-help bg-indigo-50 text-indigo-700 border-indigo-200 shadow-2xs">
              {investigationMode === 'replay' ? (
                <>
                  <Film className="w-3 h-3 text-indigo-600" />
                  <span>Recorded Run</span>
                </>
              ) : (
                <>
                  <Zap className="w-3 h-3 text-emerald-600" />
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
              variant="secondary"
              size="icon"
              onClick={onTogglePresenter}
              aria-label={presenterMode ? 'Exit presenter mode' : 'Enter presenter mode'}
              className="hidden sm:inline-flex"
            >
              {presenterMode ? <Minimize2 className="w-4 h-4 text-amber-600" /> : <Maximize2 className="w-4 h-4 text-slate-600" />}
            </Button>
          </TooltipTrigger>
          <TooltipContent side="bottom">
            Presenter Mode <Kbd className="ml-1">P</Kbd>
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

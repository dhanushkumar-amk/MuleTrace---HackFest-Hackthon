import React, { useState, useEffect } from 'react';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';
import { CommandPalette } from '@/components/ui/CommandPalette';
import { Toaster } from 'sonner';
import { TooltipProvider } from '@/components/ui/Tooltip';
import { Minimize2 } from 'lucide-react';

interface AppShellProps {
  children: React.ReactNode;
}

export const AppShell: React.FC<AppShellProps> = ({ children }) => {
  const [presenterMode, setPresenterMode] = useState(false);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't trigger if user is typing in an input, textarea or search
      const tag = (e.target as HTMLElement)?.tagName?.toLowerCase();
      if (tag === 'input' || tag === 'textarea' || (e.target as HTMLElement)?.isContentEditable) {
        return;
      }

      if (e.key === 'p' || e.key === 'P') {
        e.preventDefault();
        setPresenterMode((prev) => !prev);
      } else if (e.key === 'Escape' && presenterMode) {
        setPresenterMode(false);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [presenterMode]);

  return (
    <TooltipProvider delayDuration={200}>
      <div className="min-h-screen bg-slate-50 text-slate-900 flex flex-row">
        {/* Sidebar (hidden in presenter mode) */}
        {!presenterMode && <Sidebar />}

        {/* Main Content Area */}
        <div className="flex-1 flex flex-col min-w-0 h-screen overflow-hidden">
          {!presenterMode && (
            <TopBar
              presenterMode={presenterMode}
              onTogglePresenter={() => setPresenterMode(!presenterMode)}
            />
          )}

          <main className="flex-1 overflow-y-auto min-w-0 relative bg-slate-50">
            {children}
          </main>
        </div>

        {/* Presenter Mode Floating Exit Button */}
        {presenterMode && (
          <button
            onClick={() => setPresenterMode(false)}
            aria-label="Exit Presenter Mode"
            className="fixed bottom-4 right-4 z-50 flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-white text-slate-800 border border-slate-200 text-xs font-semibold shadow-xl hover:bg-slate-50 transition-all cursor-pointer active:scale-95"
          >
            <Minimize2 className="w-3.5 h-3.5 text-amber-600" />
            <span>Exit Presenter Mode (P)</span>
          </button>
        )}

        <CommandPalette />
        <Toaster
          position="bottom-right"
          theme="light"
          toastOptions={{
            style: {
              background: '#ffffff',
              border: '1px solid #e2e8f0',
              color: '#0f172a',
              boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.08)',
            },
          }}
        />
      </div>
    </TooltipProvider>
  );
};

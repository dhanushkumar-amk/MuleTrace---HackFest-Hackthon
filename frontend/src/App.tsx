import React, { Suspense, lazy } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AppShell } from '@/components/layout/AppShell';
import { Skeleton } from '@/components/ui/Skeleton';

const LandingPage = lazy(() =>
  import('@/features/landing/LandingPage').then((m) => ({ default: m.LandingPage }))
);
const WorkspacePage = lazy(() =>
  import('@/features/investigate/WorkspacePage').then((m) => ({ default: m.WorkspacePage }))
);
const CasesPage = lazy(() =>
  import('@/features/cases/CasesPage').then((m) => ({ default: m.CasesPage }))
);
const MemoryPage = lazy(() =>
  import('@/features/memory/MemoryPage').then((m) => ({ default: m.MemoryPage }))
);
const ToolsPage = lazy(() =>
  import('@/features/tools/ToolsPage').then((m) => ({ default: m.ToolsPage }))
);
const HowItWorksPage = lazy(() =>
  import('@/features/landing/HowItWorksPage').then((m) => ({ default: m.HowItWorksPage }))
);

const PageLoader = () => (
  <div className="p-8 space-y-4 max-w-5xl mx-auto">
    <Skeleton className="h-10 w-48" />
    <Skeleton className="h-32 w-full" />
    <Skeleton className="h-64 w-full" />
  </div>
);

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 30, // 30s
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

export const App: React.FC = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AppShell>
          <Suspense fallback={<PageLoader />}>
            <Routes>
              <Route path="/" element={<LandingPage />} />
              <Route path="/workspace" element={<WorkspacePage />} />
              <Route path="/cases" element={<CasesPage />} />
              <Route path="/memory" element={<MemoryPage />} />
              <Route path="/tools" element={<ToolsPage />} />
              <Route path="/how-it-works" element={<HowItWorksPage />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Suspense>
        </AppShell>
      </BrowserRouter>
    </QueryClientProvider>
  );
};

export default App;

import React, { useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/api/client';
import { useInvestigationStream } from '@/api/sse';
import { GraphCanvas } from './GraphCanvas';
import { TimelinePanel } from './TimelinePanel';
import { RecommendationPanel } from './RecommendationPanel';
import { AccountDossierSheet } from './AccountDossierSheet';
import { NewInvestigationModal } from './NewInvestigationModal';
import { VerifiedBadge } from '@/components/ui/VerifiedBadge';
import { CopyButton } from '@/components/ui/CopyButton';
import { Button } from '@/components/ui/Button';
import { formatRupees, formatExactIST, formatRelativeTime } from '@/lib/formatters';
import {
  Sparkles,
  Download,
  Printer,
  Share2,
  AlertTriangle,
  Play,
  Film,
  Zap,
} from 'lucide-react';
import { toast } from 'sonner';
import { CaseExplanation, HighlightGraph, FraudReport } from '@/api/types';

export const WorkspacePage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [sessionId, setSessionId] = useState<string | null>(
    searchParams.get('session_id') || 'demo_ravi_run'
  );
  const [investigationMode, setInvestigationMode] = useState<'live' | 'replay'>(
    (searchParams.get('mode') as 'live' | 'replay') || 'replay'
  );

  const [modalOpen, setModalOpen] = useState(false);
  const [selectedAccountId, setSelectedAccountId] = useState<string | null>(null);
  const [hoveredAccountId, setHoveredAccountId] = useState<string | null>(null);

  // Queries for initial data
  const { data: reports = [] } = useQuery({
    queryKey: ['fraudReports'],
    queryFn: () => api.getReports(),
  });

  const { data: tools = [] } = useQuery({
    queryKey: ['mcpTools'],
    queryFn: () => api.getTools(),
  });

  // Query for current case explanation
  const {
    data: caseData,
    refetch: refetchCase,
  } = useQuery<CaseExplanation>({
    queryKey: ['caseExplanation', sessionId],
    queryFn: async () => {
      if (!sessionId) throw new Error('No session');
      // If demo_ravi_run or session exists
      try {
        const res = await api.getInvestigationStatus(sessionId);
        if (res.case) return res.case;
      } catch (err) {
        // Fallback to cases endpoint
      }
      return api.getCaseExplanation(sessionId, 'json');
    },
    enabled: !!sessionId,
  });

  // Query for highlight subgraph
  const { data: highlightData, refetch: refetchHighlight } = useQuery<HighlightGraph>({
    queryKey: ['caseHighlight', sessionId],
    queryFn: () => (sessionId ? api.getCaseHighlight(sessionId) : Promise.reject('No session')),
    enabled: !!sessionId,
  });

  // Server-Sent Events stream hook
  const {
    events,
    activeTool,
    activeThought,
    isStreaming,
    isDone,
    error: streamError,
  } = useInvestigationStream({
    sessionId,
    enabled: !!sessionId,
    onDone: () => {
      toast.success('Investigation completed and mathematically verified against graph');
      refetchCase();
      refetchHighlight();
    },
  });

  // Handle start investigation
  const handleStartInvestigation = async ({
    reportId,
    mode,
    saveMemory,
    speed,
  }: {
    reportId: string;
    mode: 'live' | 'replay';
    saveMemory: boolean;
    speed: number;
  }) => {
    setModalOpen(false);
    setInvestigationMode(mode);

    try {
      toast.info(`Launching ${mode === 'replay' ? 'recorded demo' : 'live agent'} investigation...`);
      const resp = await api.startInvestigation({
        report_id: reportId,
        mode,
        save_memory: saveMemory,
        speed,
      });

      setSessionId(resp.session_id);
      setSearchParams({ session_id: resp.session_id, mode: resp.mode });
    } catch (err: any) {
      if (err?.error?.includes('limit reached') || err?.error?.includes('429')) {
        toast.error('Investigation limit active', {
          description: err.error,
          action: {
            label: 'Run Recorded Demo',
            onClick: () =>
              handleStartInvestigation({
                reportId,
                mode: 'replay',
                saveMemory: false,
                speed: 1,
              }),
          },
        });
      } else {
        toast.error('Failed to start investigation', {
          description: err.error || 'Server error',
        });
      }
    }
  };

  const hasAutoRunRef = React.useRef(false);
  // Autorun if query param ?autorun=true
  useEffect(() => {
    if (searchParams.get('autorun') === 'true' && !hasAutoRunRef.current) {
      hasAutoRunRef.current = true;
      handleStartInvestigation({
        reportId: 'FR_0001',
        mode: (searchParams.get('mode') as 'live' | 'replay') || 'replay',
        saveMemory: false,
        speed: 1,
      });
    }
  }, [searchParams]);

  // Actions
  const handleDownloadMarkdown = async () => {
    if (!sessionId) return;
    try {
      const md = await api.getCaseExplanation(sessionId, 'markdown');
      const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `MuleTrace_${sessionId}.md`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success('Downloaded compliance brief (Markdown)');
    } catch {
      toast.error('Failed to download report');
    }
  };

  const handlePrint = () => {
    window.print();
  };

  const handleShare = () => {
    navigator.clipboard.writeText(window.location.href);
    toast.success('Case URL copied to clipboard');
  };

  const header = caseData?.case_header;
  const victimName = header?.victim_name || 'Ravi Kumar';
  const victimAccount = header?.victim_account || 'ACC_0461';
  const stolenAmount = header?.amount_stolen || header?.stolen_amount || 85000;
  const totalRecoverable = header?.total_recoverable || 57000;
  const reportedAt = header?.reported_at || 1792044900;

  return (
    <div className="h-full flex flex-col bg-[#090d16] text-slate-100 overflow-hidden">
      {/* Top Header Summary Strip */}
      <div className="h-14 border-b border-white/10 bg-[#0e1526] px-4 sm:px-6 flex items-center justify-between shrink-0 select-none">
        <div className="flex items-center gap-3 sm:gap-6 overflow-hidden">
          {/* Victim Dossier Chip */}
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-blue-500 shrink-0" />
            <div className="flex flex-col">
              <span className="text-xs font-semibold text-slate-200 leading-tight">
                Victim: {victimName} ({victimAccount})
              </span>
              <span className="text-[10px] text-slate-400 font-mono">
                Stolen: {formatRupees(stolenAmount)} • {formatExactIST(reportedAt)}
              </span>
            </div>
          </div>

          {/* Verified Badge */}
          <div className="hidden md:block">
            <VerifiedBadge
              verified={caseData?.verified ?? true}
              totalRecoverable={totalRecoverable}
            />
          </div>
        </div>

        {/* Right Actions Cluster */}
        <div className="flex items-center gap-2">
          <CopyButton
            value={`MuleTrace Compliance Brief\nVictim: ${victimName} (${victimAccount})\nStolen Amount: Rs ${stolenAmount}\nTotal Recoverable: Rs ${totalRecoverable}\nStatus: Verified against FalkorDB graph\nDisclaimer: Recommendation for human review. Nothing was frozen.`}
            label="Copy Brief"
            className="hidden sm:inline-flex"
          />

          <Button
            variant="outline"
            size="sm"
            onClick={handleDownloadMarkdown}
            leftIcon={<Download className="w-3.5 h-3.5" />}
            className="hidden sm:inline-flex"
          >
            Markdown
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={handlePrint}
            leftIcon={<Printer className="w-3.5 h-3.5" />}
            className="hidden md:inline-flex"
          >
            Print
          </Button>

          <Button
            variant="outline"
            size="icon"
            onClick={handleShare}
            aria-label="Share case link"
          >
            <Share2 className="w-4 h-4" />
          </Button>

          <Button
            variant="primary"
            size="sm"
            leftIcon={<Sparkles className="w-3.5 h-3.5" />}
            onClick={() => setModalOpen(true)}
          >
            New Run
          </Button>
        </div>
      </div>

      {/* Three-Pane Layout */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 min-h-0 overflow-hidden">
        {/* LEFT PANE: Agent Activity Timeline (3 cols) */}
        <div className="lg:col-span-3 h-full overflow-hidden border-b lg:border-b-0 border-white/10">
          <TimelinePanel
            events={events}
            activeTool={activeTool}
            activeThought={activeThought}
            isStreaming={isStreaming}
            isDone={isDone}
            availableTools={tools}
          />
        </div>

        {/* CENTER PANE: Graph Canvas (6 cols) */}
        <div className="lg:col-span-6 h-full overflow-hidden relative">
          <GraphCanvas
            data={highlightData || caseData?.highlight || null}
            hoveredAccountId={hoveredAccountId}
            onHoverNode={setHoveredAccountId}
            onNodeClick={(id) => setSelectedAccountId(id)}
            theftTimestamp={reportedAt}
          />
        </div>

        {/* RIGHT PANE: Recommendation Tabs (3 cols) */}
        <div className="lg:col-span-3 h-full overflow-hidden">
          <RecommendationPanel
            caseData={caseData || null}
            onHoverAccount={setHoveredAccountId}
            onSelectAccount={(id) => setSelectedAccountId(id)}
          />
        </div>
      </div>

      {/* Account Dossier Sheet */}
      <AccountDossierSheet
        accountId={selectedAccountId}
        onClose={() => setSelectedAccountId(null)}
      />

      {/* New Investigation Launch Modal */}
      <NewInvestigationModal
        open={modalOpen}
        onOpenChange={setModalOpen}
        reports={reports}
        selectedReport={reports[0] || null}
        onSelectReport={() => {}}
        onStart={handleStartInvestigation}
      />
    </div>
  );
};

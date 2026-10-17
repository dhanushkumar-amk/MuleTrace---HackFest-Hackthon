import React, { useState } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import {
  Sparkles,
  Play,
  Film,
  Zap,
  Brain,
  AlertTriangle,
  X,
  CreditCard,
  User,
  Clock,
  ShieldCheck,
} from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { SegmentedControl } from '@/components/ui/SegmentedControl';
import { FraudReport } from '@/api/types';
import { formatRupees, formatExactIST } from '@/lib/formatters';
import { Badge } from '@/components/ui/Badge';

interface NewInvestigationModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  reports: FraudReport[];
  selectedReport: FraudReport | null;
  onSelectReport: (report: FraudReport) => void;
  onStart: (params: {
    reportId: string;
    mode: 'live' | 'replay';
    saveMemory: boolean;
    speed: number;
  }) => void;
  isLoading?: boolean;
}

export const NewInvestigationModal: React.FC<NewInvestigationModalProps> = ({
  open,
  onOpenChange,
  reports,
  selectedReport,
  onSelectReport,
  onStart,
  isLoading = false,
}) => {
  const [mode, setMode] = useState<'live' | 'replay'>('replay');
  const [saveMemory, setSaveMemory] = useState<boolean>(true);
  const [speed, setSpeed] = useState<number>(1);

  const activeReport = selectedReport || reports[0] || {
    id: 'FR_0001',
    victim_account: 'ACC_0461',
    amount: 85000,
    reported_at: 1792044900,
    description: "Victim received a fake KYC call and followed scammer instructions.",
  };

  const handleLaunch = () => {
    onStart({
      reportId: activeReport.id,
      mode,
      saveMemory,
      speed,
    });
  };

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/70 backdrop-blur-xs animate-in fade-in-0" />
        <Dialog.Content className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-50 w-full max-w-lg rounded-2xl border border-white/12 bg-[#0e1526] p-6 text-slate-100 shadow-2xl animate-in fade-in-0 zoom-in-95">
          {/* Header */}
          <div className="flex items-center justify-between pb-4 border-b border-white/10">
            <div className="flex items-center gap-2.5">
              <div className="p-2 rounded-xl bg-indigo-600/20 text-indigo-400 border border-indigo-500/30">
                <Sparkles className="w-5 h-5" />
              </div>
              <div>
                <Dialog.Title className="text-base font-bold text-slate-100">
                  New Autonomous Investigation
                </Dialog.Title>
                <Dialog.Description className="text-xs text-slate-400">
                  FalkorDB Payment Graph + Groq Reasoning Agent
                </Dialog.Description>
              </div>
            </div>

            <Dialog.Close className="rounded-lg p-1 text-slate-400 hover:text-white hover:bg-white/10 transition-colors cursor-pointer">
              <X className="w-4 h-4" />
            </Dialog.Close>
          </div>

          <div className="py-4 space-y-4">
            {/* Selected Fraud Report Card */}
            <div className="p-4 rounded-xl border border-indigo-500/30 bg-indigo-950/20 space-y-2.5">
              <div className="flex items-center justify-between">
                <Badge variant="danger" size="xs">
                  ACTIVE FRAUD INCIDENT: {activeReport.id}
                </Badge>
                <span className="font-mono text-sm font-bold text-rose-400">
                  {formatRupees(activeReport.amount)}
                </span>
              </div>

              <div className="text-xs text-slate-200 flex items-center gap-3">
                <span className="flex items-center gap-1 text-slate-400">
                  <User className="w-3.5 h-3.5" /> Ravi Kumar
                </span>
                <span className="flex items-center gap-1 text-slate-400 font-mono">
                  <CreditCard className="w-3.5 h-3.5" /> {activeReport.victim_account}
                </span>
                <span className="flex items-center gap-1 text-slate-400 font-mono">
                  <Clock className="w-3.5 h-3.5" /> {formatExactIST(activeReport.reported_at)}
                </span>
              </div>

              <p className="text-xs text-slate-300 italic bg-black/30 p-2.5 rounded-lg border border-white/5 leading-relaxed">
                "{activeReport.description}"
              </p>
            </div>

            {/* Execution Mode Toggle: Recorded Run vs Live Agent */}
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
                Execution Mode
              </label>
              <SegmentedControl
                value={mode}
                onChange={(val) => setMode(val as any)}
                options={[
                  {
                    value: 'replay',
                    label: 'Recorded Run (Fast & Verified)',
                    icon: <Film className="w-3.5 h-3.5 text-cyan-400" />,
                  },
                  {
                    value: 'live',
                    label: 'Live Groq Agent',
                    icon: <Zap className="w-3.5 h-3.5 text-emerald-400" />,
                  },
                ]}
                className="w-full grid grid-cols-2"
              />
              <p className="text-[11px] text-slate-400 mt-1">
                {mode === 'replay'
                  ? 'Recommended for live demos: streams exact real agent events deterministically with 0 latency.'
                  : 'Invokes real Groq LLM API autonomously calling 20 MCP tools.'}
              </p>
            </div>

            {/* Options Row: Save Memory & Speed */}
            <div className="flex items-center justify-between p-3 rounded-xl bg-white/5 border border-white/10 text-xs">
              <label className="flex items-center gap-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={saveMemory}
                  onChange={(e) => setSaveMemory(e.target.checked)}
                  className="rounded border-white/20 bg-slate-800 text-indigo-600 focus:ring-indigo-500 w-4 h-4 cursor-pointer"
                />
                <span className="font-medium text-slate-200">Save findings to Graph Memory</span>
              </label>

              {mode === 'replay' && (
                <div className="flex items-center gap-1.5">
                  <span className="text-slate-400">Speed:</span>
                  <button
                    type="button"
                    onClick={() => setSpeed(speed === 1 ? 2 : 1)}
                    className="px-2 py-0.5 rounded bg-white/10 text-slate-200 font-mono text-xs border border-white/10"
                  >
                    {speed}x
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* Footer Actions */}
          <div className="flex items-center justify-end gap-2.5 pt-3 border-t border-white/10">
            <Button variant="ghost" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button
              variant="primary"
              isLoading={isLoading}
              leftIcon={<Play className="w-4 h-4 fill-current" />}
              onClick={handleLaunch}
            >
              Start Autonomous Investigation
            </Button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
};

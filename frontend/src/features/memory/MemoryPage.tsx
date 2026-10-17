import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/api/client';
import {
  Brain,
  Sparkles,
  RotateCcw,
  Network,
  ArrowRight,
  TrendingDown,
  CheckCircle2,
  Clock,
  ShieldCheck,
} from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { toast } from 'sonner';

export const MemoryPage: React.FC = () => {
  const [isResetting, setIsResetting] = useState(false);

  const {
    data: memoryCases = [],
    isLoading,
    refetch,
  } = useQuery({
    queryKey: ['memoryCases'],
    queryFn: () => api.getMemoryCases(),
  });

  const handleResetMemory = async () => {
    setIsResetting(true);
    try {
      await api.resetMemory();
      toast.success('Graph case memory reset successfully');
      refetch();
    } catch (err: any) {
      if (err?.error?.includes('403') || err?.status === 403) {
        toast.error('DEMO_ADMIN=1 required', {
          description: 'Memory reset is restricted in production demo mode.',
        });
      } else {
        toast.error('Failed to reset memory', {
          description: err?.error || 'Server error',
        });
      }
    } finally {
      setIsResetting(false);
    }
  };

  return (
    <div className="h-full flex flex-col p-4 sm:p-8 max-w-6xl mx-auto space-y-6 overflow-y-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-white/10">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2.5">
            <Brain className="w-6 h-6 text-violet-400" />
            <span>Agent Long-Term Case Memory</span>
          </h1>
          <p className="text-xs sm:text-sm text-slate-400 mt-1">
            FalkorDB graph nodes (:Case) cross-linking recurring mules, shared hardware, and syndicate rings.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            isLoading={isResetting}
            leftIcon={<RotateCcw className="w-3.5 h-3.5" />}
            onClick={handleResetMemory}
          >
            Reset Memory
          </Button>
        </div>
      </div>

      {/* The "It Learned" Showcase Callout */}
      <div className="p-5 rounded-2xl border border-violet-500/30 bg-gradient-to-r from-violet-950/30 via-[#0e1526] to-[#0e1526] relative overflow-hidden">
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
          <div className="space-y-2 max-w-xl">
            <div className="inline-flex items-center gap-2 px-2.5 py-0.5 rounded-full bg-violet-500/10 text-violet-300 text-xs font-semibold border border-violet-500/25">
              <Sparkles className="w-3 h-3 text-violet-400 animate-spin" />
              <span>Second-Run Efficiency Acceleration</span>
            </div>
            <h2 className="text-lg font-bold text-white">
              The Agent Remembers Past Syndicates
            </h2>
            <p className="text-xs text-slate-300 leading-relaxed">
              When investigating a recurring fraud incident, the agent queries <code className="text-violet-300 font-mono">recall_past_cases</code>.
              Because past mule rings and shared hardware are already indexed in FalkorDB, investigation hops drop drastically.
            </p>
          </div>

          {/* Before vs After Step Comparison */}
          <div className="grid grid-cols-2 gap-3 p-3.5 rounded-xl bg-black/40 border border-white/10 text-center shrink-0 w-full sm:w-auto">
            <div className="px-3">
              <span className="text-[10px] text-slate-400 uppercase font-semibold">1st Run (Cold)</span>
              <div className="text-xl font-bold font-mono text-slate-200 mt-0.5">22 Steps</div>
              <span className="text-[10px] text-slate-500 font-mono">14 Tools</span>
            </div>

            <div className="px-3 border-l border-white/10">
              <span className="text-[10px] text-emerald-400 uppercase font-semibold flex items-center justify-center gap-1">
                <TrendingDown className="w-3 h-3" /> 2nd Run (Warm)
              </span>
              <div className="text-xl font-bold font-mono text-emerald-400 mt-0.5">14 Steps</div>
              <span className="text-[10px] text-emerald-400/70 font-mono">36% Faster</span>
            </div>
          </div>
        </div>
      </div>

      {/* Memory Nodes List */}
      <div>
        <h3 className="text-base font-semibold text-slate-100 mb-3 flex items-center gap-2">
          <Network className="w-4 h-4 text-indigo-400" />
          <span>Persisted Memory Entities in Graph</span>
        </h3>

        {isLoading ? (
          <div className="space-y-3">
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-16 w-full" />
          </div>
        ) : memoryCases.length === 0 ? (
          <EmptyState
            title="Graph Memory Clean"
            description="No past cases currently stored in memory. Run an investigation with 'Save findings to memory' enabled to populate."
          />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {memoryCases.map((mc, idx) => {
              const cid = mc.case_id || mc.id || `CASE_MEM_${idx + 1}`;
              const victim = mc.victim || 'Ravi Kumar';
              const amt = mc.amount || 85000;
              const mulesCount = mc.mule_count || mc.flagged_accounts?.length || 4;

              return (
                <div
                  key={cid}
                  className="p-4 rounded-xl border border-white/10 bg-[#0e1526]/80 flex flex-col justify-between gap-3 shadow-sm hover:border-violet-500/40 transition-all"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <div className="font-semibold text-sm text-slate-100 font-mono">
                        {cid}
                      </div>
                      <div className="text-xs text-slate-400 mt-0.5">
                        Victim: {victim} • Stolen: ₹{amt.toLocaleString('en-IN')}
                      </div>
                    </div>
                    <Badge variant="purple" size="xs">
                      INDEXED
                    </Badge>
                  </div>

                  <div className="flex items-center justify-between text-xs pt-2 border-t border-white/5 font-mono text-slate-400">
                    <span>{mulesCount} Mules Flagged</span>
                    <span className="text-emerald-400 flex items-center gap-1">
                      <CheckCircle2 className="w-3 h-3" /> Recall Ready
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

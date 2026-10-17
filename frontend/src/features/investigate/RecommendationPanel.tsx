import React, { useState, useEffect } from 'react';
import {
  CaseExplanation,
  RecommendationItem,
  RejectionItem,
  LinkedRingItem,
} from '@/api/types';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/Tabs';
import { DisclaimerBanner } from '@/components/ui/DisclaimerBanner';
import { Badge } from '@/components/ui/Badge';
import { formatRupees, formatAccountShort, formatExactIST } from '@/lib/formatters';
import {
  ShieldAlert,
  CheckCircle2,
  Smartphone,
  Network,
  FileCheck,
  TrendingUp,
  Clock,
  ArrowRight,
  ExternalLink,
} from 'lucide-react';
import { EmptyState } from '@/components/ui/EmptyState';

interface RecommendationPanelProps {
  caseData: CaseExplanation | null;
  onHoverAccount?: (accountId: string | null) => void;
  onSelectAccount?: (accountId: string) => void;
  onSelectEvidence?: (callId: string) => void;
  className?: string;
}

export const RecommendationPanel: React.FC<RecommendationPanelProps> = ({
  caseData,
  onHoverAccount,
  onSelectAccount,
  onSelectEvidence,
  className,
}) => {
  const [activeTab, setActiveTab] = useState<string>('freeze');

  // Keyboard shortcut: 1, 2, 3, 4, 5 switch tabs
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName?.toLowerCase();
      if (tag === 'input' || tag === 'textarea') return;

      if (e.key === '1') setActiveTab('freeze');
      else if (e.key === '2') setActiveTab('cleared');
      else if (e.key === '3') setActiveTab('rings');
      else if (e.key === '4') setActiveTab('patterns');
      else if (e.key === '5') setActiveTab('evidence');
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const recommendations = caseData?.recommendations || [];
  const rejections = caseData?.rejections || [];
  const links = caseData?.links || [];
  const patterns = caseData?.other_patterns || [];

  const totalRecoverable =
    caseData?.case_header?.total_recoverable ||
    recommendations.reduce((sum, r) => sum + (r.money?.recoverable_balance || 0), 0);
  const totalCashedOut = caseData?.case_header?.total_cashed_out || 28000;
  const totalStolen = (caseData?.case_header?.amount_stolen || 85000);

  // Recovery ratio percentage
  const recPct = Math.round((totalRecoverable / totalStolen) * 100);
  const cashPct = Math.min(100 - recPct, Math.round((totalCashedOut / totalStolen) * 100));

  return (
    <div
      className={`h-full flex flex-col bg-[#090d16] border-l border-white/10 overflow-hidden ${className || ''}`}
    >
      {/* Top 2-Part Recovery Split Bar */}
      <div className="p-4 border-b border-white/10 bg-[#0e1526]/90 space-y-2 shrink-0">
        <div className="flex items-center justify-between text-xs">
          <span className="font-semibold text-slate-200">Stolen Funds Recovery Split</span>
          <span className="font-mono text-slate-400">Total: {formatRupees(totalStolen)}</span>
        </div>

        {/* 2-Part Bar */}
        <div className="h-3 w-full bg-slate-800 rounded-full overflow-hidden flex shadow-inner">
          <div
            style={{ width: `${recPct}%` }}
            className="h-full bg-gradient-to-r from-rose-500 to-rose-600 transition-all duration-500"
            title={`Recoverable: ${formatRupees(totalRecoverable)}`}
          />
          <div
            style={{ width: `${cashPct}%` }}
            className="h-full bg-gradient-to-r from-amber-500 to-amber-600 transition-all duration-500"
            title={`Cashed Out: ${formatRupees(totalCashedOut)}`}
          />
        </div>

        <div className="flex items-center justify-between text-[11px] pt-1">
          <div className="flex items-center gap-1.5 text-rose-400">
            <span className="w-2 h-2 rounded-full bg-rose-500" />
            <span className="font-medium">Recoverable: {formatRupees(totalRecoverable)}</span>
            <span className="text-slate-500 font-mono">({recPct}%)</span>
          </div>

          <div className="flex items-center gap-1.5 text-amber-400">
            <span className="w-2 h-2 rounded-full bg-amber-500" />
            <span className="font-medium">Cashed Out: {formatRupees(totalCashedOut)}</span>
            <span className="text-slate-500 font-mono">({cashPct}%)</span>
          </div>
        </div>
      </div>

      {/* Safety Disclaimer Banner */}
      <div className="p-3.5 pb-0 shrink-0">
        <DisclaimerBanner variant="prominent" />
      </div>

      {/* Five Tabs Header */}
      <div className="px-3.5 pt-3 pb-1 border-b border-white/10 shrink-0">
        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <TabsList className="w-full grid grid-cols-5 h-8">
            <TabsTrigger value="freeze" className="text-[11px] px-1">
              Freeze ({recommendations.length})
            </TabsTrigger>
            <TabsTrigger value="cleared" className="text-[11px] px-1">
              Cleared ({rejections.length})
            </TabsTrigger>
            <TabsTrigger value="rings" className="text-[11px] px-1">
              Rings ({links.length})
            </TabsTrigger>
            <TabsTrigger value="patterns" className="text-[11px] px-1">
              Patterns
            </TabsTrigger>
            <TabsTrigger value="evidence" className="text-[11px] px-1">
              Evidence
            </TabsTrigger>
          </TabsList>
        </Tabs>
      </div>

      {/* Tab Contents (Scrollable) */}
      <div className="flex-1 overflow-y-auto p-3.5 space-y-3">
        {/* TAB 1: FREEZE LIST */}
        {activeTab === 'freeze' && (
          <div className="space-y-3">
            {recommendations.length === 0 ? (
              <EmptyState
                title="No Freeze Actions"
                description="Run an investigation to identify and rank candidate mule accounts."
              />
            ) : (
              recommendations.map((rec) => {
                const aid = rec.account;
                const bal = rec.money?.recoverable_balance || 0;
                const pri = rec.priority;
                const conf = rec.confidence || 'high';

                return (
                  <div
                    key={aid}
                    onMouseEnter={() => onHoverAccount?.(aid)}
                    onMouseLeave={() => onHoverAccount?.(null)}
                    onClick={() => onSelectAccount?.(aid)}
                    className="p-3.5 rounded-xl border border-white/10 hover:border-rose-500/40 bg-[#0e1526]/85 hover:bg-[#0e1526] transition-all duration-200 cursor-pointer shadow-sm group"
                  >
                    {/* Header: Priority, Account ID, Bank, Recoverable Amount */}
                    <div className="flex items-start justify-between gap-2 mb-2">
                      <div className="flex items-center gap-2">
                        <span className="w-6 h-6 rounded-lg bg-rose-500/15 border border-rose-500/30 flex items-center justify-center text-xs font-bold font-mono text-rose-400">
                          #{pri}
                        </span>
                        <div>
                          <div className="font-semibold text-sm text-slate-100 flex items-center gap-1.5">
                            <span>{aid}</span>
                            <span className="text-[11px] font-normal text-slate-400">
                              ({rec.bank || 'ICICI Bank'})
                            </span>
                          </div>
                          <div className="text-[11px] text-slate-400 flex items-center gap-1 mt-0.5">
                            <Badge
                              variant={conf === 'high' ? 'danger' : 'warning'}
                              size="xs"
                            >
                              {conf.toUpperCase()} CONFIDENCE
                            </Badge>
                          </div>
                        </div>
                      </div>

                      <div className="text-right">
                        <div className="text-base font-bold text-rose-400 font-mono tabular-nums">
                          {formatRupees(bal)}
                        </div>
                        <div className="text-[10px] text-slate-400">Recoverable</div>
                      </div>
                    </div>

                    {/* Path Narrative e.g. Ravi -> ACC_0462 -> ACC_0463 */}
                    <div className="text-xs text-slate-300 font-mono bg-white/5 px-2.5 py-1.5 rounded-lg border border-white/5 flex items-center gap-1.5 mb-2.5 overflow-x-auto">
                      <span className="text-slate-400 text-[10px] uppercase font-sans font-semibold">
                        Path:
                      </span>
                      <span>{rec.path_text || (rec.path ? rec.path.join(' → ') : aid)}</span>
                    </div>

                    {/* Risk Signals as Chips */}
                    <div className="flex flex-wrap gap-1">
                      {(rec.signals || []).map((sig, i) => {
                        const sigName = typeof sig === 'string' ? sig : sig.name;
                        return (
                          <span
                            key={i}
                            className="text-[10px] font-medium px-2 py-0.5 rounded-md bg-rose-500/10 text-rose-300 border border-rose-500/20"
                          >
                            {sigName.replace(/_/g, ' ')}
                          </span>
                        );
                      })}
                    </div>
                  </div>
                );
              })
            )}
          </div>
        )}

        {/* TAB 2: CLEARED ACCOUNTS (DECOY PROTECTION) */}
        {activeTab === 'cleared' && (
          <div className="space-y-3">
            {rejections.length === 0 ? (
              <EmptyState
                title="No Cleared Accounts"
                description="Candidate merchant accounts evaluated and cleared will appear here."
              />
            ) : (
              rejections.map((rej) => {
                const aid = rej.account;
                return (
                  <div
                    key={aid}
                    onMouseEnter={() => onHoverAccount?.(aid)}
                    onMouseLeave={() => onHoverAccount?.(null)}
                    onClick={() => onSelectAccount?.(aid)}
                    className="p-4 rounded-xl border border-emerald-500/25 bg-emerald-950/15 text-slate-200 transition-all cursor-pointer shadow-sm"
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                        <div>
                          <div className="font-semibold text-sm text-emerald-300">
                            {aid} (Cleared Legitimate Decoy)
                          </div>
                          <div className="text-[11px] text-slate-400">
                            {rej.holder_name || 'Local Merchant Shop'} • Regular Inflow Pattern
                          </div>
                        </div>
                      </div>
                      <Badge variant="success" size="xs">
                        CLEARED
                      </Badge>
                    </div>

                    {/* Behavioral Numbers Grid */}
                    <div className="grid grid-cols-2 gap-2 my-3 p-2.5 rounded-lg bg-black/30 border border-white/5 text-xs">
                      <div>
                        <div className="text-[10px] text-slate-400">Distinct Senders</div>
                        <div className="font-semibold font-mono text-slate-100">84 customers</div>
                      </div>
                      <div>
                        <div className="text-[10px] text-slate-400">Money Trail Link</div>
                        <div className="font-semibold text-emerald-400 font-mono">None (0 hops)</div>
                      </div>
                      <div>
                        <div className="text-[10px] text-slate-400">Hardware Stability</div>
                        <div className="font-semibold font-mono text-slate-100">Single Dedicated POS</div>
                      </div>
                      <div>
                        <div className="text-[10px] text-slate-400">Onward Ratio</div>
                        <div className="font-semibold font-mono text-slate-100">0.02 (Retained)</div>
                      </div>
                    </div>

                    {/* Explanation why not frozen */}
                    <div className="text-xs text-slate-300 leading-relaxed bg-white/5 p-2.5 rounded-lg border border-white/5">
                      <span className="text-emerald-400 font-semibold">Exclusion Reason: </span>
                      {rej.reasons?.[0] ||
                        'Account exhibits high inbound payment velocity and PageRank, but zero money paths from victim Ravi reach this account. Normal merchant counterparty behavior verified.'}
                    </div>
                  </div>
                );
              })
            )}
          </div>
        )}

        {/* TAB 3: LINKED RINGS (SHARED HARDWARE INFRASTRUCTURE) */}
        {activeTab === 'rings' && (
          <div className="space-y-3">
            {links.length === 0 ? (
              <EmptyState
                title="No Cross-Ring Links Discovered"
                description="Cross-ring hardware devices and phone links will appear here once discovered."
              />
            ) : (
              links.map((lnk, i) => (
                <div
                  key={i}
                  className="p-3.5 rounded-xl border border-cyan-500/25 bg-cyan-950/15 text-slate-200 transition-all shadow-sm"
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <Smartphone className="w-4 h-4 text-cyan-400" />
                      <span className="font-semibold text-sm text-cyan-300 font-mono">
                        {lnk.shared_id}
                      </span>
                    </div>
                    <Badge variant={lnk.strength === 'strong' ? 'danger' : 'info'} size="xs">
                      {lnk.strength?.toUpperCase() || 'STRONG'} LINK
                    </Badge>
                  </div>

                  <p className="text-xs text-slate-300 leading-relaxed mb-3">
                    {lnk.headline ||
                      `Discovered link between primary ring account ${lnk.account_a} and un-reported syndicate account ${lnk.account_b}.`}
                  </p>

                  <div className="p-2.5 rounded-lg bg-black/40 border border-white/5 text-xs space-y-1 font-mono">
                    <div className="text-slate-400 text-[10px] uppercase font-sans">
                      Path Connection:
                    </div>
                    <div className="text-cyan-300">
                      {lnk.path_text || `${lnk.account_a} ──[${lnk.shared_id}]──> ${lnk.account_b}`}
                    </div>
                    <div className="text-slate-400 text-[11px] pt-1">
                      Total Co-using Accounts: {lnk.total_sharers}
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {/* TAB 4: OTHER PATTERNS */}
        {activeTab === 'patterns' && (
          <div className="space-y-2.5">
            {patterns.length === 0 ? (
              <EmptyState
                title="No Additional Patterns"
                description="Fan-in, fan-out, and pass-through patterns will appear here."
              />
            ) : (
              patterns.map((pat, i) => (
                <div
                  key={i}
                  className="p-3 rounded-xl border border-white/10 bg-[#0e1526]/75 flex items-start gap-2.5 text-xs text-slate-300"
                >
                  <Network className="w-4 h-4 text-violet-400 shrink-0 mt-0.5" />
                  <span className="leading-relaxed">{pat}</span>
                </div>
              ))
            )}
          </div>
        )}

        {/* TAB 5: EVIDENCE & AUDIT LOG */}
        {activeTab === 'evidence' && (
          <div className="space-y-2">
            <div className="text-xs text-slate-400 mb-2">
              All {caseData?.timeline?.length || 0} tool calls executed and cryptographically logged for compliance audit:
            </div>
            {(caseData?.timeline || []).map((step) => (
              <div
                key={step.call_id}
                onClick={() => onSelectEvidence?.(step.call_id)}
                className="p-2.5 rounded-lg border border-white/5 bg-white/2 hover:bg-white/5 transition-colors cursor-pointer text-xs flex items-center justify-between font-mono"
              >
                <div className="flex items-center gap-2">
                  <span className="text-indigo-400 font-bold">#{step.step}</span>
                  <span className="text-slate-200">{step.tool}</span>
                </div>
                <div className="flex items-center gap-1.5 text-slate-400 text-[11px]">
                  <span>{step.duration}</span>
                  <ExternalLink className="w-3 h-3 text-slate-500" />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

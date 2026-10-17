import React, { useState } from 'react';
import {
  BookOpen,
  Database,
  Wrench,
  Bot,
  ShieldCheck,
  UserCheck,
  ArrowRight,
  Lock,
  Sparkles,
  CheckCircle2,
  AlertCircle,
} from 'lucide-react';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { useNavigate } from 'react-router-dom';

export const HowItWorksPage: React.FC = () => {
  const navigate = useNavigate();
  const [activeStage, setActiveStage] = useState<number>(0);

  const stages = [
    {
      id: 'falkordb',
      title: '1. FalkorDB Payment Graph',
      role: 'Graph Database & Cypher Engine',
      icon: Database,
      color: '#3b82f6',
      summary: '6,669 nodes representing accounts, hardware devices, phone numbers, and timed payment transactions.',
      invariants: [
        'Multi-hop path traversals execute in sub-10ms in memory.',
        'Zero schema migration bottlenecks; relationships are native graph edges.',
        'Temporal transaction filtering preserves chronological validity.',
      ],
    },
    {
      id: 'mcp',
      title: '2. Model Context Protocol Tools',
      role: 'Tool Layer & Sandboxed Interface',
      icon: Wrench,
      color: '#f59e0b',
      summary: '20 purpose-built analytical tools exposed to the agent over standard MCP schemas with compact output tokens.',
      invariants: [
        'Strictly parameterized read-only queries.',
        'Output compaction guarantees bounded token consumption.',
        'Never accepts raw Cypher strings from the LLM.',
      ],
    },
    {
      id: 'groq',
      title: '3. Groq Autonomous Agent',
      role: 'Tool-Calling Reasoning Loop',
      icon: Bot,
      color: '#6366f1',
      summary: 'Groq LLM operates in an autonomous loop, formulating hypotheses and invoking graph tools dynamically.',
      invariants: [
        'Agent selects tools dynamically based on graph evidence.',
        'Chain-of-thought hypothesis streaming via Server-Sent Events.',
        'Cannot directly invent balances or account numbers.',
      ],
    },
    {
      id: 'explain',
      title: '4. Grounded Explainability',
      role: 'Pure Python Verification Engine',
      icon: ShieldCheck,
      color: '#10b981',
      summary: 'Deterministic Python engine checks 100% of claims against live graph trace facts before assembling reports.',
      invariants: [
        'Recoverable sums must match live graph balances exactly.',
        'Decoys without money trails are automatically exempted.',
        'Every cited path and transaction ID is re-verified in graph.',
      ],
    },
    {
      id: 'human',
      title: '5. Human Decision & Action',
      role: 'Compliance & Fraud Team',
      icon: UserCheck,
      color: '#e11d48',
      summary: 'Outputs clear ranked freeze actions for human fraud officers with full forensic audit proof.',
      invariants: [
        'The system NEVER freezes accounts automatically.',
        'Disclaimer on every view: "Recommendation for human review".',
        'Analyst sees the exact money path and evidence for every item.',
      ],
    },
  ];

  return (
    <div className="h-full flex flex-col p-4 sm:p-8 max-w-5xl mx-auto space-y-8 overflow-y-auto">
      {/* Page Title */}
      <div className="text-center max-w-2xl mx-auto space-y-2">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/10 text-indigo-300 text-xs font-semibold border border-indigo-500/20">
          <BookOpen className="w-3.5 h-3.5" />
          <span>System Architecture & Safety Invariants</span>
        </div>
        <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-white">
          How MuleTrace Operates
        </h1>
        <p className="text-xs sm:text-sm text-slate-400">
          A high-integrity architecture separating LLM reasoning from mathematical graph facts.
        </p>
      </div>

      {/* Interactive Horizontal Pipeline */}
      <div className="grid grid-cols-1 sm:grid-cols-5 gap-2 select-none">
        {stages.map((stg, i) => {
          const Icon = stg.icon;
          const isActive = activeStage === i;
          return (
            <button
              key={stg.id}
              onClick={() => setActiveStage(i)}
              className={`p-3 rounded-xl border text-left transition-all duration-200 cursor-pointer flex flex-col justify-between gap-3 ${
                isActive
                  ? 'bg-indigo-600/15 border-indigo-500 shadow-lg shadow-indigo-500/10'
                  : 'bg-[#0e1526]/80 border-white/10 hover:border-white/20'
              }`}
            >
              <div className="flex items-center justify-between">
                <span
                  className="p-1.5 rounded-lg"
                  style={{
                    backgroundColor: `${stg.color}20`,
                    color: stg.color,
                  }}
                >
                  <Icon className="w-4 h-4" />
                </span>
                <span className="text-[10px] font-mono text-slate-500 font-bold">
                  0{i + 1}
                </span>
              </div>
              <div>
                <div
                  className={`text-xs font-bold leading-tight ${
                    isActive ? 'text-indigo-400' : 'text-slate-200'
                  }`}
                >
                  {stg.title.split('. ')[1]}
                </div>
                <div className="text-[10px] text-slate-400 mt-0.5 line-clamp-1">{stg.role}</div>
              </div>
            </button>
          );
        })}
      </div>

      {/* Selected Stage Detail Dossier */}
      {(() => {
        const current = stages[activeStage];
        const Icon = current.icon;
        return (
          <div className="p-6 rounded-2xl border border-white/10 bg-[#0e1526] space-y-4 shadow-xl">
            <div className="flex items-center gap-3 pb-3 border-b border-white/10">
              <span
                className="p-2.5 rounded-xl shrink-0"
                style={{
                  backgroundColor: `${current.color}20`,
                  color: current.color,
                }}
              >
                <Icon className="w-6 h-6" />
              </span>
              <div>
                <h3 className="text-lg font-bold text-white">{current.title}</h3>
                <span className="text-xs text-slate-400 font-medium">{current.role}</span>
              </div>
            </div>

            <p className="text-sm text-slate-300 leading-relaxed font-sans">{current.summary}</p>

            <div className="pt-2">
              <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2.5">
                Guaranteed Architectural Invariants:
              </h4>
              <div className="space-y-2">
                {current.invariants.map((inv, idx) => (
                  <div
                    key={idx}
                    className="flex items-start gap-2.5 text-xs text-slate-300 bg-white/5 p-2.5 rounded-lg border border-white/5"
                  >
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                    <span>{inv}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        );
      })()}

      {/* The Three Golden Rules */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-4">
        <div className="p-4 rounded-xl border border-white/10 bg-[#0e1526]/80 space-y-2">
          <div className="text-xs font-bold text-indigo-400 uppercase tracking-wider flex items-center gap-1.5">
            <Lock className="w-3.5 h-3.5" /> Rule 1: No Invented Facts
          </div>
          <p className="text-xs text-slate-300 leading-relaxed">
            The LLM never writes amounts, paths, or account IDs. Every fact in the final brief originates strictly from tool outputs.
          </p>
        </div>

        <div className="p-4 rounded-xl border border-white/10 bg-[#0e1526]/80 space-y-2">
          <div className="text-xs font-bold text-amber-400 uppercase tracking-wider flex items-center gap-1.5">
            <Wrench className="w-3.5 h-3.5" /> Rule 2: Agent Decides Tools
          </div>
          <p className="text-xs text-slate-300 leading-relaxed">
            There is no hardcoded investigation script. The agent evaluates graph findings and dynamically decides what tool to invoke next.
          </p>
        </div>

        <div className="p-4 rounded-xl border border-white/10 bg-[#0e1526]/80 space-y-2">
          <div className="text-xs font-bold text-rose-400 uppercase tracking-wider flex items-center gap-1.5">
            <ShieldCheck className="w-3.5 h-3.5" /> Rule 3: Recommendation Only
          </div>
          <p className="text-xs text-slate-300 leading-relaxed">
            MuleTrace cannot freeze bank accounts. It delivers ranked, verified evidence for human compliance officers to review and execute.
          </p>
        </div>
      </div>

      <div className="text-center pt-4 pb-8">
        <Button
          variant="primary"
          size="lg"
          rightIcon={<ArrowRight className="w-4 h-4" />}
          onClick={() => navigate('/workspace?autorun=true')}
        >
          Launch Interactive Workspace Demo
        </Button>
      </div>
    </div>
  );
};

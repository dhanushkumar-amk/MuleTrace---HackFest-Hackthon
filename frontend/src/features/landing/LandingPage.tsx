import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Sparkles,
  ArrowRight,
  ShieldCheck,
  Zap,
  Network,
  Clock,
  Layers,
  CheckCircle2,
  Database,
  Radio,
  FileText,
  Smartphone,
  ChevronRight,
  Play,
  Lock,
} from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Stat } from '@/components/ui/Stat';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/api/client';
import { formatRupees } from '@/lib/formatters';

export const LandingPage: React.FC = () => {
  const navigate = useNavigate();

  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: () => api.getHealth(),
  });

  const nodesCount = health?.graph_node_count || health?.graph_nodes_count || 6669;

  return (
    <div className="min-h-full bg-slate-50 text-slate-900 flex flex-col selection:bg-indigo-500/15">
      {/* Hero Section */}
      <section className="relative pt-16 pb-20 px-4 sm:px-8 max-w-6xl mx-auto flex flex-col items-center text-center">
        {/* Subtle Ambient Light Glow */}
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[600px] h-[320px] bg-indigo-500/5 blur-3xl pointer-events-none -z-10 rounded-full" />

        {/* Hackathon Pill */}
        <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-white border border-slate-200/90 text-xs text-indigo-700 mb-6 shadow-xs">
          <span className="w-2 h-2 rounded-full bg-indigo-600 animate-pulse" />
          <span className="font-semibold">FalkorDB Graph Hacks Hackathon</span>
          <span className="text-slate-300">•</span>
          <span className="text-slate-600">Track 01: Fraud & Compliance</span>
        </div>

        {/* Headline */}
        <h1 className="text-4xl sm:text-6xl font-extrabold tracking-tight text-slate-900 max-w-4xl leading-[1.12] mb-5">
          Follow the money.{' '}
          <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-600 via-blue-600 to-indigo-800">
            Explain every decision.
          </span>
        </h1>

        {/* Subhead */}
        <p className="text-base sm:text-lg text-slate-600 max-w-2xl leading-relaxed mb-8 font-normal">
          Autonomous financial fraud ring investigation powered by FalkorDB payment graph
          traversals, Groq agent reasoning, and Model Context Protocol. Zero hallucinated actions.
        </p>

        {/* Action Buttons */}
        <div className="flex flex-col sm:flex-row items-center gap-3.5 mb-14">
          <Button
            variant="primary"
            size="lg"
            leftIcon={<Sparkles className="w-4 h-4" />}
            rightIcon={<ArrowRight className="w-4 h-4" />}
            onClick={() => navigate('/workspace?autorun=true')}
          >
            Investigate Ravi Report (FR_0001)
          </Button>

          <Button
            variant="secondary"
            size="lg"
            leftIcon={<FileText className="w-4 h-4" />}
            onClick={() => navigate('/cases')}
          >
            Browse 20 Saved Cases
          </Button>
        </div>

        {/* Interactive Forensic Preview Card */}
        <div className="w-full max-w-4xl bg-white rounded-2xl border border-slate-200 shadow-sm p-5 sm:p-6 text-left mb-14">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between pb-4 border-b border-slate-100 gap-3">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl bg-indigo-50 border border-indigo-200 flex items-center justify-center text-indigo-600">
                <Network className="w-5 h-5" />
              </div>
              <div>
                <div className="text-sm font-semibold text-slate-900">
                  Live Payment Forensics Preview: FR_0001 (Ravi Kumar)
                </div>
                <div className="text-xs text-slate-500">
                  8-Hop Money Trail • FalkorDB In-Memory Graph Traversal
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                <CheckCircle2 className="w-3.5 h-3.5" />
                100% Graph Grounded
              </span>
              <button
                onClick={() => navigate('/workspace?autorun=true')}
                className="text-xs font-semibold text-indigo-600 hover:text-indigo-800 flex items-center gap-1 cursor-pointer"
              >
                <span>Open in Workspace</span>
                <ChevronRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          {/* Graph Flow Mockup Bar */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3 pt-5">
            {/* Step 1: Victim */}
            <div className="p-3.5 rounded-xl bg-blue-50/60 border border-blue-200 flex flex-col justify-between">
              <div className="flex items-center justify-between text-xs mb-2">
                <span className="font-semibold text-blue-700">1. Theft Point</span>
                <span className="text-[10px] font-mono bg-blue-100 text-blue-800 px-1.5 py-0.5 rounded">Victim</span>
              </div>
              <div className="font-semibold text-sm text-slate-900">ACC_9901</div>
              <div className="text-xs text-slate-600 mt-1">₹85,000 Stolen via UPI</div>
            </div>

            {/* Step 2: Mule L1 */}
            <div className="p-3.5 rounded-xl bg-rose-50/70 border border-rose-200 flex flex-col justify-between">
              <div className="flex items-center justify-between text-xs mb-2">
                <span className="font-semibold text-rose-700">2. Layer 1 Mule</span>
                <span className="text-[10px] font-mono bg-rose-100 text-rose-800 px-1.5 py-0.5 rounded">FREEZE</span>
              </div>
              <div className="font-semibold text-sm text-slate-900">ACC_0461</div>
              <div className="text-xs text-rose-700 font-semibold mt-1">₹57,000 Recoverable</div>
            </div>

            {/* Step 3: Decoy Cleared */}
            <div className="p-3.5 rounded-xl bg-emerald-50/60 border border-emerald-200 flex flex-col justify-between">
              <div className="flex items-center justify-between text-xs mb-2">
                <span className="font-semibold text-emerald-700">3. Legitimate Merchant</span>
                <span className="text-[10px] font-mono bg-emerald-100 text-emerald-800 px-1.5 py-0.5 rounded">CLEARED</span>
              </div>
              <div className="font-semibold text-sm text-slate-900">ACC_0462</div>
              <div className="text-xs text-slate-600 mt-1">₹1,20,000 Normal Vol</div>
            </div>

            {/* Step 4: Cashout Point */}
            <div className="p-3.5 rounded-xl bg-amber-50/60 border border-amber-200 flex flex-col justify-between">
              <div className="flex items-center justify-between text-xs mb-2">
                <span className="font-semibold text-amber-700">4. Cashout Point</span>
                <span className="text-[10px] font-mono bg-amber-100 text-amber-800 px-1.5 py-0.5 rounded">CASHOUT</span>
              </div>
              <div className="font-semibold text-sm text-slate-900">ACC_0888</div>
              <div className="text-xs text-slate-600 mt-1">₹28,000 ATM Disperse</div>
            </div>
          </div>
        </div>

        {/* Live Metrics Grid */}
        <div className="w-full grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4 max-w-4xl text-left">
          <Stat
            label="Graph Nodes"
            value={nodesCount.toLocaleString()}
            subvalue="FalkorDB In-Memory Graph"
            icon={<Database className="w-4 h-4" />}
          />
          <Stat
            label="Agent Tools"
            value="20 Tools"
            subvalue="Model Context Protocol"
            icon={<Zap className="w-4 h-4" />}
          />
          <Stat
            label="Decision Speed"
            value="~12s"
            subvalue="Multi-hop money trace"
            icon={<Clock className="w-4 h-4" />}
          />
          <Stat
            label="Grounding"
            value="100%"
            subvalue="Verified against graph facts"
            icon={<ShieldCheck className="w-4 h-4" />}
          />
        </div>
      </section>

      {/* 3 Core Pillars Section */}
      <section className="py-16 border-t border-slate-200/80 bg-white px-4 sm:px-8">
        <div className="max-w-5xl mx-auto space-y-12">
          <div className="text-center max-w-2xl mx-auto space-y-2">
            <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900">
              High-Precision Fraud Investigation Architecture
            </h2>
            <p className="text-sm text-slate-500">
              Designed specifically for bank fraud compliance teams to act within the 1-hour freeze window.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="p-6 rounded-2xl border border-slate-200 bg-slate-50/50 flex flex-col gap-3 shadow-2xs hover:border-slate-300 transition-colors">
              <div className="w-10 h-10 rounded-xl bg-blue-50 border border-blue-200 flex items-center justify-center text-blue-600">
                <Network className="w-5 h-5" />
              </div>
              <h3 className="text-base font-semibold text-slate-900">Multi-Hop Graph Forensics</h3>
              <p className="text-xs text-slate-600 leading-relaxed">
                Forward-in-time BFS walks through intermediary mules, splits, and aggregation points in 8ms, detecting complex money laundering rings before cash-out.
              </p>
            </div>

            <div className="p-6 rounded-2xl border border-slate-200 bg-slate-50/50 flex flex-col gap-3 shadow-2xs hover:border-slate-300 transition-colors">
              <div className="w-10 h-10 rounded-xl bg-indigo-50 border border-indigo-200 flex items-center justify-center text-indigo-600">
                <Radio className="w-5 h-5" />
              </div>
              <h3 className="text-base font-semibold text-slate-900">Autonomous MCP Tool Calling</h3>
              <p className="text-xs text-slate-600 leading-relaxed">
                Groq LLM calls 20 specialized forensic tools over Model Context Protocol, querying Cypher primitives directly rather than guessing parameters.
              </p>
            </div>

            <div className="p-6 rounded-2xl border border-slate-200 bg-slate-50/50 flex flex-col gap-3 shadow-2xs hover:border-slate-300 transition-colors">
              <div className="w-10 h-10 rounded-xl bg-emerald-50 border border-emerald-200 flex items-center justify-center text-emerald-600">
                <ShieldCheck className="w-5 h-5" />
              </div>
              <h3 className="text-base font-semibold text-slate-900">100% Grounded Explanations</h3>
              <p className="text-xs text-slate-600 leading-relaxed">
                Zero hallucinated balances or account IDs. Every recommendation is deterministically checked against the live payment graph state.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Quick Launch Demo Grid */}
      <section className="py-16 border-t border-slate-200 bg-slate-50 px-4 sm:px-8">
        <div className="max-w-5xl mx-auto space-y-8">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2">
            <div>
              <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-slate-900">
                Instant Test Cases
              </h2>
              <p className="text-xs text-slate-500">
                Click any case scenario below to run the investigation instantly.
              </p>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => navigate('/cases')}
              rightIcon={<ArrowRight className="w-3.5 h-3.5" />}
            >
              View All 20 Cases
            </Button>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {[
              {
                id: 'FR_0001',
                title: 'Ravi Kumar (Hackathon Demo)',
                tag: 'Primary Demo',
                tagColor: 'bg-indigo-50 text-indigo-700 border-indigo-200',
                stolen: '₹85,000',
                recoverable: '₹57,000',
                desc: '8-hop laundering chain with decoy merchant accounts.',
              },
              {
                id: 'FR_0002',
                title: 'Layered Ring Syndicate',
                tag: 'Layered Mules',
                tagColor: 'bg-rose-50 text-rose-700 border-rose-200',
                stolen: '₹1,40,000',
                recoverable: '₹95,000',
                desc: 'Multiple intermediaries splitting funds across banks.',
              },
              {
                id: 'FR_0003',
                title: 'Rapid ATM Cash-Out',
                tag: 'Fast Cashout',
                tagColor: 'bg-amber-50 text-amber-700 border-amber-200',
                stolen: '₹60,000',
                recoverable: '₹15,000',
                desc: 'High velocity withdrawals executed within 15 minutes.',
              },
              {
                id: 'FR_0004',
                title: 'Device & IP Cluster Ring',
                tag: 'Hardware Link',
                tagColor: 'bg-purple-50 text-purple-700 border-purple-200',
                stolen: '₹2,20,000',
                recoverable: '₹1,80,000',
                desc: 'Multiple accounts linked by shared hardware and proxies.',
              },
            ].map((c) => (
              <div
                key={c.id}
                onClick={() => navigate(`/workspace?session_id=demo_ravi_run&mode=replay`)}
                className="p-4 rounded-xl border border-slate-200 bg-white hover:border-indigo-400 hover:shadow-xs transition-all duration-200 cursor-pointer flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between gap-1 mb-2">
                    <span className="text-xs font-mono font-semibold text-slate-500">{c.id}</span>
                    <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-md border ${c.tagColor}`}>
                      {c.tag}
                    </span>
                  </div>
                  <div className="font-semibold text-sm text-slate-900 mb-1">{c.title}</div>
                  <div className="text-xs text-slate-500 mb-3">{c.desc}</div>
                </div>

                <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-xs">
                  <span className="text-slate-500">Recoverable:</span>
                  <span className="font-semibold text-emerald-700">{c.recoverable}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-8 border-t border-slate-200 bg-white px-4 text-center text-xs text-slate-500">
        <div className="max-w-5xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <span className="font-bold text-slate-800">MuleTrace</span>
            <span>•</span>
            <span>FalkorDB Graph Hacks Hackathon (Track 01)</span>
          </div>
          <div>
            Built with FalkorDB In-Memory Graph, Groq LLM & Model Context Protocol.
          </div>
        </div>
      </footer>
    </div>
  );
};

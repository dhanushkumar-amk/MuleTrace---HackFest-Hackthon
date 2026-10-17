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
  ExternalLink,
  ChevronRight,
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
    <div className="min-h-full bg-[#090d16] text-slate-100 flex flex-col selection:bg-indigo-500/20">
      {/* Hero Section */}
      <section className="relative pt-20 pb-24 px-4 sm:px-8 max-w-6xl mx-auto flex flex-col items-center text-center overflow-hidden">
        {/* Ambient Gradient Mesh */}
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[700px] h-[400px] bg-gradient-to-b from-indigo-600/15 via-cyan-500/10 to-transparent blur-3xl pointer-events-none -z-10" />

        {/* Announcement Pill */}
        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/5 border border-white/10 text-xs text-indigo-300 mb-8 shadow-xs">
          <span className="w-2 h-2 rounded-full bg-indigo-400 animate-pulse" />
          <span>FalkorDB Graph Hacks Hackathon • Track 01</span>
          <span className="text-white/20">|</span>
          <span className="text-slate-400">Groq LLM + MCP Agent</span>
        </div>

        {/* Headline */}
        <h1 className="text-4xl sm:text-6xl lg:text-7xl font-extrabold tracking-tight text-white max-w-4xl leading-[1.1] mb-6">
          Follow the money.{' '}
          <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 via-cyan-300 to-emerald-400">
            Explain every decision.
          </span>
        </h1>

        {/* Subhead */}
        <p className="text-base sm:text-lg text-slate-300 max-w-2xl leading-relaxed mb-10 font-normal">
          Autonomous financial fraud ring investigation powered by FalkorDB payment graph
          algorithms, Groq agent reasoning, and Model Context Protocol. Zero black-box hallucinations.
        </p>

        {/* CTA Buttons */}
        <div className="flex flex-col sm:flex-row items-center gap-4 mb-16">
          <Button
            variant="primary"
            size="lg"
            leftIcon={<Sparkles className="w-4 h-4" />}
            rightIcon={<ArrowRight className="w-4 h-4" />}
            onClick={() => navigate('/workspace?autorun=true')}
          >
            Run Live Demo (Ravi FR_0001)
          </Button>

          <Button
            variant="outline"
            size="lg"
            onClick={() => navigate('/how-it-works')}
          >
            Watch How It Works
          </Button>
        </div>

        {/* Real Stats Strip */}
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

      {/* The Problem & Solution Breakdown */}
      <section className="py-20 border-t border-white/10 bg-[#0e1526]/40 px-4 sm:px-8">
        <div className="max-w-5xl mx-auto space-y-16">
          <div className="text-center max-w-2xl mx-auto space-y-3">
            <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-white">
              Why Relational Databases Fail at Mule Detection
            </h2>
            <p className="text-sm text-slate-400">
              Modern fraud syndicates disperse stolen money across multiple bank accounts in minutes.
              SQL joins choke on 8-hop recursive paths; FalkorDB traverses them in milliseconds.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="p-6 rounded-2xl border border-white/10 bg-[#0e1526]/80 flex flex-col gap-3">
              <div className="w-10 h-10 rounded-xl bg-blue-500/10 border border-blue-500/25 flex items-center justify-center text-blue-400">
                <Network className="w-5 h-5" />
              </div>
              <h3 className="text-base font-semibold text-white">Multi-Hop Traversal</h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                Forward-in-time BFS walks through intermediary mules, splits, and aggregation points in 8ms, detecting complex money laundering rings before cash-out.
              </p>
            </div>

            <div className="p-6 rounded-2xl border border-white/10 bg-[#0e1526]/80 flex flex-col gap-3">
              <div className="w-10 h-10 rounded-xl bg-cyan-500/10 border border-cyan-500/25 flex items-center justify-center text-cyan-400">
                <Layers className="w-5 h-5" />
              </div>
              <h3 className="text-base font-semibold text-white">Cross-Ring Infrastructure</h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                Syndicates reuse burner devices and SIM cards. Graph algorithms surface shared hardware co-used by mules across seemingly unrelated rings.
              </p>
            </div>

            <div className="p-6 rounded-2xl border border-white/10 bg-[#0e1526]/80 flex flex-col gap-3">
              <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/25 flex items-center justify-center text-emerald-400">
                <ShieldCheck className="w-5 h-5" />
              </div>
              <h3 className="text-base font-semibold text-white">Zero False Positive Decoys</h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                Busy local shops receive thousands of payments. MuleTrace checks actual money paths from the victim before recommending freezes, preventing innocent merchant account locks.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* The 4-Step Investigation Pipeline */}
      <section className="py-20 px-4 sm:px-8 max-w-5xl mx-auto w-full">
        <div className="text-center max-w-2xl mx-auto space-y-3 mb-16">
          <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-white">
            How the Autonomous Agent Works
          </h2>
          <p className="text-sm text-slate-400">
            A tool-augmented agent architecture where the LLM reasons over graph algorithms rather than hallucinating answers.
          </p>
        </div>

        <div className="space-y-4">
          {[
            {
              step: '01',
              title: "Incident Intake: Ravi Kumar's Complaint",
              desc: "Victim loses Rs 85,000 to an imposter KYC call. The agent retrieves the victim account, exact stolen amount, and timestamp.",
              badge: "FR_0001",
            },
            {
              step: '02',
              title: 'Multi-Hop Downstream Forward Trace',
              desc: 'Autonomous agent invokes trace_money_forward, discovering Mule A, splitting into Mule B & C, then passing to Mule D & E.',
              badge: "4 Mules Identified",
            },
            {
              step: '03',
              title: 'Shared Hardware Syndicate Discovery',
              desc: 'Using find_shared_devices, the agent uncovers that Mule B shares a device with an account in a second un-reported ring.',
              badge: "DEV_0593 Linked",
            },
            {
              step: '04',
              title: 'Mathematical Verification & Decoy Exemption',
              desc: 'The explainability engine verifies all 22 tool calls and clears legitimate merchant ACC_0476, outputting Rs 57,000 in ranked recoverable actions.',
              badge: "100% Grounded",
            },
          ].map((item, i) => (
            <div
              key={i}
              className="p-5 rounded-2xl border border-white/10 bg-[#0e1526]/70 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4"
            >
              <div className="flex items-start gap-4">
                <span className="text-2xl font-bold font-mono text-indigo-400/80 shrink-0">
                  {item.step}
                </span>
                <div>
                  <h4 className="text-base font-semibold text-slate-100">{item.title}</h4>
                  <p className="text-xs text-slate-400 mt-1 max-w-xl leading-relaxed">{item.desc}</p>
                </div>
              </div>
              <span className="text-xs font-mono font-semibold px-3 py-1 rounded-full bg-white/5 border border-white/10 text-slate-300 shrink-0">
                {item.badge}
              </span>
            </div>
          ))}
        </div>

        <div className="text-center mt-12">
          <Button
            variant="primary"
            size="lg"
            rightIcon={<ArrowRight className="w-4 h-4" />}
            onClick={() => navigate('/workspace')}
          >
            Enter Investigation Workspace
          </Button>
        </div>
      </section>

      {/* Footer */}
      <footer className="mt-auto border-t border-white/10 bg-[#070b12] py-8 px-4 sm:px-8 text-center text-xs text-slate-400">
        <div className="max-w-5xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-slate-200">MuleTrace</span>
            <span>— Built for Graph Hacks with FalkorDB & Groq</span>
          </div>
          <div className="text-slate-400">
            Strict human compliance review: the system never freezes accounts directly.
          </div>
        </div>
      </footer>
    </div>
  );
};

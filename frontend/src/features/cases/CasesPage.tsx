import React, { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/api/client';
import { SavedCaseSummary } from '@/api/types';
import { formatRupees, formatExactIST, formatRelativeTime } from '@/lib/formatters';
import {
  FileText,
  Search,
  ArrowUpDown,
  ExternalLink,
  ShieldCheck,
  CheckCircle2,
  Calendar,
  Sparkles,
} from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { Card } from '@/components/ui/Card';

export const CasesPage: React.FC = () => {
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [filterVerified, setFilterVerified] = useState<'all' | 'verified'>('all');
  const [sortField, setSortField] = useState<'timestamp' | 'amount'>('timestamp');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');

  const { data: cases = [], isLoading } = useQuery<SavedCaseSummary[]>({
    queryKey: ['savedCases'],
    queryFn: () => api.getCases(),
  });

  const filteredCases = useMemo(() => {
    return cases
      .filter((c) => {
        if (filterVerified === 'verified' && !c.verified) return false;
        if (!search) return true;
        const q = search.toLowerCase();
        return (
          c.session_id.toLowerCase().includes(q) ||
          c.case_id.toLowerCase().includes(q) ||
          (c.victim_name && c.victim_name.toLowerCase().includes(q)) ||
          c.report_id.toLowerCase().includes(q)
        );
      })
      .sort((a, b) => {
        if (sortField === 'amount') {
          const amtA = a.total_recoverable || a.recoverable_total || 0;
          const amtB = b.total_recoverable || b.recoverable_total || 0;
          return sortOrder === 'desc' ? amtB - amtA : amtA - amtB;
        }
        const tsA = a.timestamp || a.created_at || 0;
        const tsB = b.timestamp || b.created_at || 0;
        return sortOrder === 'desc' ? tsB - tsA : tsA - tsB;
      });
  }, [cases, search, filterVerified, sortField, sortOrder]);

  const toggleSort = (field: 'timestamp' | 'amount') => {
    if (sortField === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortOrder('desc');
    }
  };

  return (
    <div className="h-full flex flex-col p-4 sm:p-8 max-w-6xl mx-auto space-y-6 overflow-y-auto">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-white/10">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2.5">
            <FileText className="w-6 h-6 text-indigo-400" />
            <span>Persisted Cases Directory</span>
          </h1>
          <p className="text-xs sm:text-sm text-slate-400 mt-1">
            Historical investigation briefs verified against live FalkorDB payment graph facts.
          </p>
        </div>

        <Button
          variant="primary"
          leftIcon={<Sparkles className="w-4 h-4" />}
          onClick={() => navigate('/workspace?autorun=true')}
        >
          Run Investigation Demo
        </Button>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-[#0e1526]/80 p-3 rounded-2xl border border-white/10">
        <div className="relative w-full sm:w-80">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by case ID, session, victim..."
            className="w-full pl-9 pr-4 py-2 bg-white/5 border border-white/10 rounded-xl text-xs text-slate-100 placeholder:text-slate-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          />
        </div>

        <div className="flex items-center gap-2 w-full sm:w-auto justify-end text-xs">
          <span className="text-slate-400 hidden sm:inline">Filter:</span>
          <button
            onClick={() => setFilterVerified(filterVerified === 'all' ? 'verified' : 'all')}
            className={`px-3 py-1.5 rounded-lg border transition-colors cursor-pointer select-none ${
              filterVerified === 'verified'
                ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
                : 'bg-white/5 text-slate-400 border-white/10 hover:text-slate-200'
            }`}
          >
            {filterVerified === 'verified' ? 'Verified Only' : 'All Cases'}
          </button>
        </div>
      </div>

      {/* Cases Table */}
      {isLoading ? (
        <div className="space-y-3">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-full" />
        </div>
      ) : filteredCases.length === 0 ? (
        <EmptyState
          title="No Cases Found"
          description={
            search
              ? "No investigation records match your search criteria."
              : "No cases saved yet. Run the Ravi investigation demo to persist a case."
          }
          actionLabel="Run Ravi Demo Run"
          onAction={() => navigate('/workspace?autorun=true')}
        />
      ) : (
        <div className="rounded-2xl border border-white/10 bg-[#0e1526]/90 overflow-hidden shadow-lg">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-white/10 bg-white/5 text-slate-400 uppercase font-semibold tracking-wider select-none">
                  <th className="py-3 px-4">Case / Session</th>
                  <th className="py-3 px-4">Victim</th>
                  <th
                    className="py-3 px-4 cursor-pointer hover:text-slate-200"
                    onClick={() => toggleSort('amount')}
                  >
                    <div className="flex items-center gap-1.5">
                      <span>Total Recoverable</span>
                      <ArrowUpDown className="w-3 h-3" />
                    </div>
                  </th>
                  <th className="py-3 px-4">Verification</th>
                  <th
                    className="py-3 px-4 cursor-pointer hover:text-slate-200"
                    onClick={() => toggleSort('timestamp')}
                  >
                    <div className="flex items-center gap-1.5">
                      <span>Date / Elapsed</span>
                      <ArrowUpDown className="w-3 h-3" />
                    </div>
                  </th>
                  <th className="py-3 px-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {filteredCases.map((c) => {
                  const amt = c.total_recoverable || c.recoverable_total || 0;
                  const ts = c.timestamp || c.created_at || 1792044900;

                  return (
                    <tr
                      key={c.session_id}
                      onClick={() => navigate(`/workspace?session_id=${encodeURIComponent(c.session_id)}`)}
                      className="hover:bg-white/5 transition-colors cursor-pointer group"
                    >
                      <td className="py-3.5 px-4 font-mono font-medium text-slate-200">
                        <div className="font-semibold text-slate-100 flex items-center gap-1.5">
                          <span>{c.case_id || 'CASE_FR_0001'}</span>
                          <span className="text-[10px] text-slate-400 font-normal">
                            ({c.report_id || 'FR_0001'})
                          </span>
                        </div>
                        <div className="text-[10px] text-slate-400 truncate max-w-[200px]">
                          {c.session_id}
                        </div>
                      </td>

                      <td className="py-3.5 px-4 text-slate-200 font-medium">
                        {c.victim_name || 'Ravi Kumar'}
                      </td>

                      <td className="py-3.5 px-4 font-mono font-bold text-rose-400 text-sm tabular-nums">
                        {formatRupees(amt)}
                      </td>

                      <td className="py-3.5 px-4">
                        {c.verified ? (
                          <Badge variant="success" size="xs">
                            VERIFIED
                          </Badge>
                        ) : (
                          <Badge variant="warning" size="xs">
                            UNVERIFIED
                          </Badge>
                        )}
                      </td>

                      <td className="py-3.5 px-4 text-slate-400 font-mono text-[11px]">
                        <div>{formatExactIST(ts)}</div>
                        <div className="text-[10px] text-slate-400">{formatRelativeTime(ts)}</div>
                      </td>

                      <td className="py-3.5 px-4 text-right">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            navigate(`/workspace?session_id=${encodeURIComponent(c.session_id)}`);
                          }}
                          className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium text-indigo-400 hover:text-indigo-300 hover:bg-indigo-600/10 transition-colors"
                        >
                          <span>Open</span>
                          <ExternalLink className="w-3 h-3" />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};

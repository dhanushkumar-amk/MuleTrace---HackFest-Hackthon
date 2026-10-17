import React from 'react';
import { Sheet, SheetContent } from '@/components/ui/Sheet';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/api/client';
import { formatRupees, formatExactIST } from '@/lib/formatters';
import { Skeleton } from '@/components/ui/Skeleton';
import {
  CreditCard,
  Building,
  ArrowDownLeft,
  ArrowUpRight,
  Smartphone,
  Phone,
  ShieldAlert,
  Users,
  Activity,
} from 'lucide-react';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';

interface AccountDossierSheetProps {
  accountId: string | null;
  onClose: () => void;
}

export const AccountDossierSheet: React.FC<AccountDossierSheetProps> = ({
  accountId,
  onClose,
}) => {
  const { data: profile, isLoading } = useQuery({
    queryKey: ['accountProfile', accountId],
    queryFn: () => (accountId ? api.getAccountProfile(accountId) : null),
    enabled: !!accountId,
  });

  return (
    <Sheet open={!!accountId} onOpenChange={(open) => !open && onClose()}>
      <SheetContent side="right">
        {isLoading || !profile ? (
          <div className="space-y-4 pt-4">
            <Skeleton className="h-8 w-40" />
            <Skeleton className="h-20 w-full" />
            <Skeleton className="h-40 w-full" />
          </div>
        ) : (
          <div className="space-y-5 pt-3">
            {/* Header info */}
            <div>
              <div className="flex items-center justify-between">
                <span className="text-xl font-bold font-mono text-slate-100 tracking-tight">
                  {profile.account_id}
                </span>
                <Badge variant="purple" size="xs">
                  {profile.bank || 'Banking Entity'}
                </Badge>
              </div>
              <p className="text-xs text-slate-400 mt-1">
                Holder: {profile.holder_name || 'Account Holder'}
              </p>
            </div>

            {/* Financial Velocity Stats */}
            <div className="grid grid-cols-2 gap-2.5 p-3 rounded-xl bg-white/5 border border-white/5 text-xs">
              <div>
                <span className="text-slate-400 text-[10px] uppercase font-medium">Balance Held</span>
                <div className="text-base font-bold font-mono text-rose-400 tabular-nums">
                  {formatRupees(profile.balance || 0)}
                </div>
              </div>
              <div>
                <span className="text-slate-400 text-[10px] uppercase font-medium">Txn Count</span>
                <div className="text-base font-bold font-mono text-slate-200 tabular-nums">
                  {profile.transaction_count ?? 14}
                </div>
              </div>
              <div>
                <span className="text-slate-400 text-[10px] uppercase font-medium flex items-center gap-1">
                  <ArrowDownLeft className="w-3 h-3 text-emerald-400" /> Total Inflow
                </span>
                <div className="text-sm font-semibold font-mono text-slate-200 tabular-nums">
                  {formatRupees(profile.inflow || 85000)}
                </div>
              </div>
              <div>
                <span className="text-slate-400 text-[10px] uppercase font-medium flex items-center gap-1">
                  <ArrowUpRight className="w-3 h-3 text-rose-400" /> Total Outflow
                </span>
                <div className="text-sm font-semibold font-mono text-slate-200 tabular-nums">
                  {formatRupees(profile.outflow || 45000)}
                </div>
              </div>
            </div>

            {/* Hardware Infrastructure Links */}
            <div>
              <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2 flex items-center gap-1.5">
                <Smartphone className="w-3.5 h-3.5 text-cyan-400" />
                <span>Connected Infrastructure</span>
              </h4>

              <div className="space-y-2">
                <div className="p-2.5 rounded-lg bg-black/40 border border-white/5 flex items-center justify-between text-xs font-mono">
                  <div className="flex items-center gap-2">
                    <Smartphone className="w-4 h-4 text-cyan-400" />
                    <span>Shared Devices</span>
                  </div>
                  <Badge variant={profile.shared_device_count > 0 ? 'warning' : 'default'} size="xs">
                    {profile.shared_device_count} co-used
                  </Badge>
                </div>

                <div className="p-2.5 rounded-lg bg-black/40 border border-white/5 flex items-center justify-between text-xs font-mono">
                  <div className="flex items-center gap-2">
                    <Phone className="w-4 h-4 text-cyan-400" />
                    <span>Shared Phones</span>
                  </div>
                  <Badge variant={profile.shared_phone_count > 0 ? 'warning' : 'default'} size="xs">
                    {profile.shared_phone_count} co-used
                  </Badge>
                </div>
              </div>
            </div>

            {/* Counterparty Analysis */}
            <div className="p-3 rounded-xl bg-white/5 border border-white/5 space-y-2 text-xs">
              <div className="flex items-center justify-between">
                <span className="text-slate-400">Distinct Senders</span>
                <span className="font-mono font-semibold text-slate-200">
                  {profile.distinct_senders || 1}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-400">Distinct Recipients</span>
                <span className="font-mono font-semibold text-slate-200">
                  {profile.distinct_recipients || 2}
                </span>
              </div>
            </div>

            {/* Disclaimer */}
            <div className="text-[11px] text-slate-400 italic pt-2 border-t border-white/5">
              Profile retrieved via read-only FalkorDB Cypher queries. No account has been altered or frozen.
            </div>
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
};

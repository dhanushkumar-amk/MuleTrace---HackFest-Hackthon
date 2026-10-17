import React from 'react';
import { AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';

interface DisclaimerBannerProps {
  className?: string;
  variant?: 'subtle' | 'prominent';
}

export const DisclaimerBanner: React.FC<DisclaimerBannerProps> = ({
  className,
  variant = 'prominent',
}) => {
  if (variant === 'subtle') {
    return (
      <div
        className={cn(
          'flex items-center gap-2 py-1.5 px-3 rounded-lg text-xs text-amber-300/90 bg-amber-500/10 border border-amber-500/20 select-none',
          className
        )}
      >
        <AlertCircle className="w-3.5 h-3.5 shrink-0 text-amber-400" />
        <span>Recommendation for human compliance review. Nothing was frozen automatically.</span>
      </div>
    );
  }

  return (
    <div
      className={cn(
        'p-3.5 rounded-xl border border-amber-500/25 bg-amber-500/10 text-amber-200 flex items-start gap-3 shadow-xs select-none',
        className
      )}
    >
      <div className="p-1 rounded-md bg-amber-500/20 text-amber-400 shrink-0 mt-0.5">
        <AlertCircle className="w-4 h-4" />
      </div>
      <div className="text-xs">
        <div className="font-semibold text-amber-300">
          Recommendation for human review. Nothing was frozen.
        </div>
        <div className="text-amber-200/80 mt-0.5 leading-relaxed">
          MuleTrace outputs evidence-backed actions for compliance and fraud operations teams. All account freezing requires human authorization.
        </div>
      </div>
    </div>
  );
};

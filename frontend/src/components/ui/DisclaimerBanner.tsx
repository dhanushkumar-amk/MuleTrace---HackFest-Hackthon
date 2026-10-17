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
          'flex items-center gap-2 py-1.5 px-3 rounded-lg text-xs text-amber-800 bg-amber-50 border border-amber-200 select-none shadow-2xs',
          className
        )}
      >
        <AlertCircle className="w-3.5 h-3.5 shrink-0 text-amber-600" />
        <span>Recommendation for human compliance review. Nothing was frozen automatically.</span>
      </div>
    );
  }

  return (
    <div
      className={cn(
        'p-3.5 rounded-xl border border-amber-200 bg-amber-50/90 text-amber-900 flex items-start gap-3 shadow-2xs select-none',
        className
      )}
    >
      <div className="p-1 rounded-md bg-amber-100 text-amber-700 shrink-0 mt-0.5">
        <AlertCircle className="w-4 h-4" />
      </div>
      <div className="text-xs">
        <div className="font-semibold text-amber-900">
          Recommendation for human review. Nothing was frozen.
        </div>
        <div className="text-amber-800/80 mt-0.5 leading-relaxed">
          MuleTrace outputs evidence-backed actions for compliance and fraud operations teams. All account freezing requires human authorization.
        </div>
      </div>
    </div>
  );
};

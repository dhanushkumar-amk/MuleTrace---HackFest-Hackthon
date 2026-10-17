import React from 'react';
import { cn } from '@/lib/utils';
import { SemanticRole, SEMANTIC_COLORS } from '@/design/tokens';

export interface StatProps extends React.HTMLAttributes<HTMLDivElement> {
  label: string;
  value: React.ReactNode;
  subvalue?: React.ReactNode;
  icon?: React.ReactNode;
  roleVariant?: SemanticRole;
}

export const Stat: React.FC<StatProps> = ({
  className,
  label,
  value,
  subvalue,
  icon,
  roleVariant,
  ...props
}) => {
  const semantic = roleVariant ? SEMANTIC_COLORS[roleVariant] : null;

  return (
    <div
      className={cn(
        'p-3.5 sm:p-4 rounded-xl border border-white/10 bg-[#0e1526]/80 flex flex-col justify-between transition-all duration-200',
        className
      )}
      style={
        semantic
          ? {
              borderColor: semantic.border,
              background: `linear-gradient(135deg, ${semantic.bg} 0%, rgba(14, 21, 38, 0.8) 100%)`,
            }
          : undefined
      }
      {...props}
    >
      <div className="flex items-center justify-between gap-2 mb-1.5">
        <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">
          {label}
        </span>
        {icon && (
          <span
            className="p-1.5 rounded-lg shrink-0"
            style={{
              backgroundColor: semantic ? semantic.bg : 'rgba(255, 255, 255, 0.05)',
              color: semantic ? semantic.color : '#94a3b8',
            }}
          >
            {icon}
          </span>
        )}
      </div>
      <div>
        <div
          className="text-xl sm:text-2xl font-bold tracking-tight tabular-nums text-slate-100"
          style={semantic ? { color: semantic.color } : undefined}
        >
          {value}
        </div>
        {subvalue && (
          <div className="text-xs text-slate-400 mt-1 flex items-center gap-1 font-normal">
            {subvalue}
          </div>
        )}
      </div>
    </div>
  );
};

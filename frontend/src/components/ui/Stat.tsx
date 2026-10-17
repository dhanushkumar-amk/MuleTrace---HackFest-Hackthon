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
        'p-3.5 sm:p-4 rounded-xl border border-slate-200/80 bg-white shadow-xs flex flex-col justify-between transition-all duration-200 hover:border-slate-300',
        className
      )}
      style={
        semantic
          ? {
              borderColor: semantic.border,
              background: `linear-gradient(135deg, ${semantic.bg} 0%, #ffffff 100%)`,
            }
          : undefined
      }
      {...props}
    >
      <div className="flex items-center justify-between gap-2 mb-1.5">
        <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
          {label}
        </span>
        {icon && (
          <span
            className="p-1.5 rounded-lg shrink-0"
            style={{
              backgroundColor: semantic ? semantic.bg : '#f1f5f9',
              color: semantic ? semantic.color : '#475569',
            }}
          >
            {icon}
          </span>
        )}
      </div>
      <div>
        <div
          className="text-xl sm:text-2xl font-bold tracking-tight tabular-nums text-slate-900"
          style={semantic ? { color: semantic.text } : undefined}
        >
          {value}
        </div>
        {subvalue && (
          <div className="text-xs text-slate-500 mt-0.5 font-normal">
            {subvalue}
          </div>
        )}
      </div>
    </div>
  );
};

import React from 'react';
import { cn } from '@/lib/utils';
import { SEMANTIC_COLORS, SemanticRole } from '@/design/tokens';

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  roleVariant?: SemanticRole;
  variant?: 'default' | 'success' | 'warning' | 'danger' | 'info' | 'purple' | 'outline';
  size?: 'xs' | 'sm' | 'md';
  dot?: boolean;
}

export const Badge: React.FC<BadgeProps> = ({
  className,
  roleVariant,
  variant = 'default',
  size = 'sm',
  dot = false,
  children,
  ...props
}) => {
  let colorStyles = 'bg-slate-800/80 text-slate-300 border-slate-700/60';
  let dotColor = '#94a3b8';

  if (roleVariant && SEMANTIC_COLORS[roleVariant]) {
    const sc = SEMANTIC_COLORS[roleVariant];
    return (
      <span
        className={cn(
          'inline-flex items-center font-medium rounded-md border select-none transition-colors',
          size === 'xs' && 'text-[10px] px-1.5 py-0.5 gap-1',
          size === 'sm' && 'text-xs px-2 py-0.5 gap-1.5',
          size === 'md' && 'text-sm px-2.5 py-1 gap-2',
          className
        )}
        style={{
          backgroundColor: sc.bg,
          borderColor: sc.border,
          color: sc.text,
        }}
        {...props}
      >
        {dot && (
          <span
            className="w-1.5 h-1.5 rounded-full shrink-0"
            style={{ backgroundColor: sc.color }}
          />
        )}
        {children || sc.label}
      </span>
    );
  }

  const variants = {
    default: 'bg-white/5 text-slate-300 border-white/10',
    success: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/25',
    warning: 'bg-amber-500/10 text-amber-400 border-amber-500/25',
    danger: 'bg-rose-500/10 text-rose-400 border-rose-500/25',
    info: 'bg-blue-500/10 text-blue-400 border-blue-500/25',
    purple: 'bg-violet-500/10 text-violet-400 border-violet-500/25',
    outline: 'bg-transparent text-slate-400 border-white/15',
  };

  const dotColors = {
    default: 'bg-slate-400',
    success: 'bg-emerald-400',
    warning: 'bg-amber-400',
    danger: 'bg-rose-400',
    info: 'bg-blue-400',
    purple: 'bg-violet-400',
    outline: 'bg-slate-400',
  };

  return (
    <span
      className={cn(
        'inline-flex items-center font-medium rounded-md border select-none',
        variants[variant],
        size === 'xs' && 'text-[10px] px-1.5 py-0.5 gap-1',
        size === 'sm' && 'text-xs px-2 py-0.5 gap-1.5',
        size === 'md' && 'text-sm px-2.5 py-1 gap-2',
        className
      )}
      {...props}
    >
      {dot && <span className={cn('w-1.5 h-1.5 rounded-full shrink-0', dotColors[variant])} />}
      {children}
    </span>
  );
};

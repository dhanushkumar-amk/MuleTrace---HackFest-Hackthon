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
  if (roleVariant && SEMANTIC_COLORS[roleVariant]) {
    const sc = SEMANTIC_COLORS[roleVariant];
    return (
      <span
        className={cn(
          'inline-flex items-center font-medium rounded-md border select-none transition-colors shadow-2xs',
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
    default: 'bg-slate-100 text-slate-700 border-slate-200',
    success: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    warning: 'bg-amber-50 text-amber-700 border-amber-200',
    danger: 'bg-rose-50 text-rose-700 border-rose-200',
    info: 'bg-blue-50 text-blue-700 border-blue-200',
    purple: 'bg-purple-50 text-purple-700 border-purple-200',
    outline: 'bg-transparent text-slate-600 border-slate-300',
  };

  const dotColors = {
    default: '#64748b',
    success: '#059669',
    warning: '#d97706',
    danger: '#dc2626',
    info: '#2563eb',
    purple: '#7c3aed',
    outline: '#64748b',
  };

  return (
    <span
      className={cn(
        'inline-flex items-center font-medium rounded-md border select-none transition-colors shadow-2xs',
        variants[variant],
        size === 'xs' && 'text-[10px] px-1.5 py-0.5 gap-1',
        size === 'sm' && 'text-xs px-2 py-0.5 gap-1.5',
        size === 'md' && 'text-sm px-2.5 py-1 gap-2',
        className
      )}
      {...props}
    >
      {dot && (
        <span
          className="w-1.5 h-1.5 rounded-full shrink-0"
          style={{ backgroundColor: dotColors[variant] }}
        />
      )}
      {children}
    </span>
  );
};

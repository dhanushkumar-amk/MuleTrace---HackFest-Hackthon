import React from 'react';
import { cn } from '@/lib/utils';

export const Kbd: React.FC<React.HTMLAttributes<HTMLElement>> = ({
  className,
  children,
  ...props
}) => {
  return (
    <kbd
      className={cn(
        'inline-flex items-center justify-center px-1.5 py-0.5 text-[10px] font-mono font-medium text-slate-400 bg-white/5 border border-white/10 rounded shadow-xs select-none',
        className
      )}
      {...props}
    >
      {children}
    </kbd>
  );
};

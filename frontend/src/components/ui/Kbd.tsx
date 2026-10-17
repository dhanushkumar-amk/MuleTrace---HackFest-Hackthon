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
        'inline-flex items-center justify-center px-1.5 py-0.5 text-[10px] font-mono font-medium text-slate-500 bg-slate-100 border border-slate-200 rounded shadow-2xs select-none',
        className
      )}
      {...props}
    >
      {children}
    </kbd>
  );
};

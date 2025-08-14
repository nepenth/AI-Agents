import { cn } from '@/utils/cn';
import { ReactNode } from 'react';

interface GlassPanelProps {
  className?: string;
  children: ReactNode;
}

export function GlassPanel({ className, children }: GlassPanelProps) {
  return (
    <div
      className={cn(
        'rounded-xl border border-white/10 bg-white/10 backdrop-blur-md shadow-lg',
        'ring-1 ring-black/5',
        className
      )}
    >
      {children}
    </div>
  );
}



import { cn } from '@/utils/cn';
import { ReactNode } from 'react';

interface GlassCardProps {
  className?: string;
  children: ReactNode;
}

export function GlassCard({ className, children }: GlassCardProps) {
  return (
    <div
      className={cn(
        'rounded-lg border bg-glass-bg border-glass-border shadow-glass backdrop-blur-glass transition-colors duration-300',
        className
      )}
    >
      <div className="p-6">{children}</div>
    </div>
  );
}



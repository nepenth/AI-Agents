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
        // Glass morphism effect
        'rounded-lg border border-glass-border bg-glass-bg shadow-glass backdrop-blur-glass',
        // Transitions and interactions
        'transition-all duration-300 hover:shadow-lg',
        // Ensure proper text contrast
        'text-foreground',
        className
      )}
    >
      <div className="p-6">{children}</div>
    </div>
  );
}



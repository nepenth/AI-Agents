import React from 'react';
import { cn } from '@/utils/cn';

export interface GlassCardProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  variant?: 'default' | 'subtle' | 'strong';
}

export const GlassCard = React.forwardRef<HTMLDivElement, GlassCardProps>(
  ({ className, children, variant = 'default', ...props }, ref) => {
    const variantClasses = {
      default: 'bg-glass-bg backdrop-blur-glass border-glass-border shadow-glass',
      subtle: 'bg-background/80 backdrop-blur-sm border-border/50 shadow-sm',
      strong: 'bg-background/95 backdrop-blur-md border-border shadow-lg'
    };

    return (
      <div
        ref={ref}
        className={cn(
          'rounded-lg border transition-colors duration-300',
          variantClasses[variant],
          className
        )}
        {...props}
      >
        {children}
      </div>
    );
  }
);

GlassCard.displayName = 'GlassCard';

import React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/utils/cn';

const glassCardVariants = cva(
  'rounded-xl border transition-all duration-300 ease-out relative overflow-hidden backdrop-blur-md',
  {
    variants: {
      variant: {
        primary: [
          'bg-glass-primary border-glass-border-primary shadow-glass-primary',
          'hover:shadow-glass-secondary hover:scale-[1.02]',
          'before:absolute before:inset-0 before:bg-gradient-to-br before:from-white/10 before:to-transparent before:pointer-events-none'
        ],
        secondary: [
          'bg-glass-secondary border-glass-border-secondary shadow-glass-secondary',
          'hover:shadow-glass-primary hover:scale-[1.01]',
          'before:absolute before:inset-0 before:bg-gradient-to-br before:from-white/5 before:to-transparent before:pointer-events-none'
        ],
        tertiary: [
          'bg-glass-tertiary border-glass-border-tertiary shadow-glass-tertiary',
          'hover:shadow-glass-secondary',
          'before:absolute before:inset-0 before:bg-gradient-to-br before:from-white/3 before:to-transparent before:pointer-events-none'
        ],
        interactive: [
          'bg-glass-interactive border-glass-border-interactive shadow-glass-interactive',
          'hover:shadow-glass-interactive-hover hover:scale-105 cursor-pointer',
          'active:scale-[1.02] transition-transform',
          'before:absolute before:inset-0 before:bg-gradient-to-br before:from-white/8 before:to-transparent before:pointer-events-none'
        ],
        // Legacy variants for backward compatibility
        default: [
          'bg-glass-primary border-glass-border-primary shadow-glass-primary',
          'hover:shadow-glass-secondary hover:scale-[1.02]'
        ],
        subtle: [
          'bg-glass-tertiary border-glass-border-tertiary shadow-glass-tertiary',
          'hover:shadow-glass-secondary'
        ],
        strong: [
          'bg-glass-secondary border-glass-border-secondary shadow-glass-secondary',
          'hover:shadow-glass-primary'
        ]
      },
      elevated: {
        true: 'hover:-translate-y-1',
        false: ''
      }
    },
    defaultVariants: {
      variant: 'primary',
      elevated: false
    }
  }
);

export interface GlassCardProps 
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof glassCardVariants> {
  children: React.ReactNode;
}

export const GlassCard = React.forwardRef<HTMLDivElement, GlassCardProps>(
  ({ className, children, variant, elevated, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn(glassCardVariants({ variant, elevated }), className)}
        {...props}
      >
        {children}
      </div>
    );
  }
);

GlassCard.displayName = 'GlassCard';

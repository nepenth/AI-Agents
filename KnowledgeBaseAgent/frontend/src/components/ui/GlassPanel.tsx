import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/utils/cn';

const glassPanelVariants = cva(
  'rounded-xl border transition-all duration-500 ease-out relative overflow-hidden',
  {
    variants: {
      variant: {
        primary: [
          'bg-glass-primary border-glass-border-primary shadow-glass-primary backdrop-blur-glass-primary',
          'hover:shadow-glass-secondary hover:backdrop-blur-glass-secondary hover:border-glass-border-secondary',
          'before:absolute before:inset-0 before:bg-gradient-to-br before:from-white/8 before:to-transparent before:pointer-events-none'
        ],
        secondary: [
          'bg-glass-secondary border-glass-border-secondary shadow-glass-secondary backdrop-blur-glass-secondary',
          'hover:shadow-glass-primary hover:backdrop-blur-glass-primary hover:border-glass-border-primary',
          'before:absolute before:inset-0 before:bg-gradient-to-br before:from-white/5 before:to-transparent before:pointer-events-none'
        ],
        tertiary: [
          'bg-glass-tertiary border-glass-border-tertiary shadow-glass-tertiary backdrop-blur-glass-tertiary',
          'hover:shadow-glass-secondary hover:backdrop-blur-glass-secondary hover:border-glass-border-secondary',
          'before:absolute before:inset-0 before:bg-gradient-to-br before:from-white/3 before:to-transparent before:pointer-events-none'
        ],
        navbar: [
          'bg-glass-navbar border-glass-border-navbar shadow-glass-navbar backdrop-blur-glass-navbar',
          'sticky top-0 z-40',
          'before:absolute before:inset-0 before:bg-gradient-to-b before:from-white/10 before:to-transparent before:pointer-events-none'
        ],
        interactive: [
          'bg-glass-interactive border-glass-border-interactive shadow-glass-interactive backdrop-blur-glass-interactive',
          'hover:shadow-glass-interactive-hover hover:scale-[1.02] hover:backdrop-blur-glass-overlay cursor-pointer',
          'active:scale-[0.98] transition-transform',
          'before:absolute before:inset-0 before:bg-gradient-to-br before:from-white/8 before:to-transparent before:pointer-events-none'
        ],
        overlay: [
          'bg-glass-overlay border-glass-border-overlay shadow-glass-overlay backdrop-blur-glass-overlay',
          'fixed inset-0 z-50 flex items-center justify-center',
          'before:absolute before:inset-0 before:bg-gradient-to-br before:from-white/15 before:to-transparent before:pointer-events-none'
        ]
      },
      size: {
        sm: 'p-3',
        md: 'p-4',
        lg: 'p-6',
        xl: 'p-8'
      },
      elevated: {
        true: 'hover:-translate-y-1',
        false: ''
      }
    },
    defaultVariants: {
      variant: 'primary',
      size: 'md',
      elevated: false
    }
  }
);

export interface GlassPanelProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof glassPanelVariants> {}

const GlassPanel = React.forwardRef<HTMLDivElement, GlassPanelProps>(
  ({ className, variant, size, elevated, ...props }, ref) => {
    return (
      <div
        className={cn(glassPanelVariants({ variant, size, elevated }), className)}
        ref={ref}
        {...props}
      />
    );
  }
);
GlassPanel.displayName = 'GlassPanel';

export { GlassPanel, glassPanelVariants };

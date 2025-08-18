import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/utils/cn';

const glassPanelVariants = cva(
  'rounded-xl border transition-colors duration-300',
  {
    variants: {
      variant: {
        primary:
          'bg-glass-bg-primary backdrop-blur-glass-medium shadow-glass-md border-glass-border-primary',
        secondary:
          'bg-glass-bg-secondary backdrop-blur-glass-light shadow-glass-sm border-glass-border-secondary',
        tertiary:
          'bg-glass-bg-tertiary backdrop-blur-glass-subtle border-glass-border-tertiary',
      },
    },
    defaultVariants: {
      variant: 'primary',
    },
  }
);

export interface GlassPanelProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof glassPanelVariants> {}

const GlassPanel = React.forwardRef<HTMLDivElement, GlassPanelProps>(
  ({ className, variant, ...props }, ref) => {
    return (
      <div
        className={cn(glassPanelVariants({ variant }), className)}
        ref={ref}
        {...props}
      />
    );
  }
);
GlassPanel.displayName = 'GlassPanel';

export { GlassPanel, glassPanelVariants };

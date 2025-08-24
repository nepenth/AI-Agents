import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/utils/cn';

const glassInputVariants = cva(
  'flex w-full rounded-lg transition-all duration-300 ease-out relative overflow-hidden',
  {
    variants: {
      variant: {
        primary: [
          'bg-glass-primary border-glass-border-primary shadow-glass-primary backdrop-blur-glass-primary',
          'focus-within:shadow-glass-secondary focus-within:backdrop-blur-glass-secondary focus-within:border-glass-border-secondary',
          'focus-within:ring-2 focus-within:ring-primary/20 focus-within:ring-offset-0',
          'before:absolute before:inset-0 before:bg-gradient-to-br before:from-white/5 before:to-transparent before:pointer-events-none'
        ],
        secondary: [
          'bg-glass-secondary border-glass-border-secondary shadow-glass-secondary backdrop-blur-glass-secondary',
          'focus-within:shadow-glass-primary focus-within:backdrop-blur-glass-primary focus-within:border-glass-border-primary',
          'focus-within:ring-2 focus-within:ring-primary/15 focus-within:ring-offset-0',
          'before:absolute before:inset-0 before:bg-gradient-to-br before:from-white/3 before:to-transparent before:pointer-events-none'
        ],
        tertiary: [
          'bg-glass-tertiary border-glass-border-tertiary shadow-glass-tertiary backdrop-blur-glass-tertiary',
          'focus-within:shadow-glass-secondary focus-within:backdrop-blur-glass-secondary focus-within:border-glass-border-secondary',
          'focus-within:ring-2 focus-within:ring-primary/10 focus-within:ring-offset-0',
          'before:absolute before:inset-0 before:bg-gradient-to-br before:from-white/2 before:to-transparent before:pointer-events-none'
        ]
      },
      size: {
        sm: 'h-8 px-3 text-sm',
        md: 'h-10 px-4 text-sm',
        lg: 'h-12 px-4 text-base'
      }
    },
    defaultVariants: {
      variant: 'primary',
      size: 'md'
    }
  }
);

export interface GlassInputProps 
  extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'size'>,
    VariantProps<typeof glassInputVariants> {}

const GlassInput = React.forwardRef<HTMLInputElement, GlassInputProps>(
  ({ className, variant, size, type = 'text', ...props }, ref) => {
    return (
      <div className={cn(glassInputVariants({ variant, size }), 'border', className)}>
        <input
          type={type}
          className={cn(
            'w-full bg-transparent border-0 outline-none ring-0 focus:ring-0 relative z-10',
            'text-foreground placeholder:text-muted-foreground',
            'disabled:cursor-not-allowed disabled:opacity-50'
          )}
          ref={ref}
          {...props}
        />
      </div>
    );
  }
);
GlassInput.displayName = 'GlassInput';

export { GlassInput, glassInputVariants };

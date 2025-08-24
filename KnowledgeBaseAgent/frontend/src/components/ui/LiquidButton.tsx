import * as React from 'react';
import { Slot } from '@radix-ui/react-slot';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/utils/cn';

const liquidButtonVariants = cva(
  'inline-flex items-center justify-center whitespace-nowrap text-sm font-semibold ring-offset-background transition-all duration-500 ease-out focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 relative overflow-hidden',
  {
    variants: {
      variant: {
        primary: [
          'bg-glass-primary border border-glass-border-primary shadow-glass-primary backdrop-blur-glass-primary text-foreground',
          'hover:shadow-glass-secondary hover:scale-105 hover:backdrop-blur-glass-secondary hover:border-glass-border-secondary',
          'active:scale-[1.02] active:shadow-glass-tertiary',
          'before:absolute before:inset-0 before:bg-gradient-to-br before:from-white/10 before:to-transparent before:pointer-events-none',
          'rounded-2xl'
        ],
        secondary: [
          'bg-glass-secondary border border-glass-border-secondary shadow-glass-secondary backdrop-blur-glass-secondary text-foreground',
          'hover:shadow-glass-primary hover:scale-[1.03] hover:backdrop-blur-glass-primary hover:border-glass-border-primary',
          'active:scale-[1.01] active:shadow-glass-tertiary',
          'before:absolute before:inset-0 before:bg-gradient-to-br before:from-white/8 before:to-transparent before:pointer-events-none',
          'rounded-2xl'
        ],
        interactive: [
          'bg-glass-interactive border border-glass-border-interactive shadow-glass-interactive backdrop-blur-glass-interactive text-white',
          'hover:shadow-glass-interactive-hover hover:scale-110 hover:backdrop-blur-glass-overlay',
          'active:scale-105 active:shadow-glass-secondary transition-transform',
          'before:absolute before:inset-0 before:bg-gradient-to-br before:from-white/15 before:to-transparent before:pointer-events-none',
          'rounded-3xl'
        ],
        glass: [
          'bg-glass-interactive border border-glass-border-interactive shadow-glass-interactive backdrop-blur-glass-interactive text-white',
          'hover:scale-105 hover:shadow-glass-interactive-hover hover:backdrop-blur-glass-overlay',
          'active:scale-[1.02] transition-transform',
          'before:absolute before:inset-0 before:bg-gradient-to-br before:from-white/12 before:to-transparent before:pointer-events-none',
          'rounded-3xl'
        ],
        ghost: [
          'text-foreground hover:bg-glass-tertiary hover:backdrop-blur-glass-tertiary',
          'hover:scale-[1.02] active:scale-[0.98]',
          'rounded-xl'
        ],
        outline: [
          'border-2 border-glass-border-secondary bg-transparent backdrop-blur-glass-tertiary text-foreground',
          'hover:bg-glass-tertiary hover:border-glass-border-primary hover:scale-[1.02]',
          'active:scale-[0.98] active:bg-glass-secondary',
          'rounded-xl'
        ]
      },
      size: {
        sm: 'h-8 px-4 py-2 text-xs rounded-xl',
        default: 'h-10 px-6 py-3 text-sm',
        lg: 'h-12 px-8 py-4 text-base',
        icon: 'h-10 w-10 p-0',
        'icon-sm': 'h-8 w-8 p-0',
        'icon-lg': 'h-12 w-12 p-0'
      },
      elevated: {
        true: 'hover:-translate-y-1',
        false: ''
      }
    },
    defaultVariants: {
      variant: 'primary',
      size: 'default',
      elevated: false
    }
  }
);

export interface LiquidButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof liquidButtonVariants> {
  asChild?: boolean;
  loading?: boolean;
}

const LiquidButton = React.forwardRef<HTMLButtonElement, LiquidButtonProps>(
  ({ className, variant, size, elevated, asChild = false, loading = false, children, ...props }, ref) => {
    const Comp = asChild ? Slot : 'button';
    return (
      <Comp
        className={cn(liquidButtonVariants({ variant, size, elevated }), className)}
        ref={ref}
        disabled={loading || props.disabled}
        {...props}
      >
        {loading && (
          <svg
            className="animate-spin -ml-1 mr-2 h-4 w-4 relative z-10"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            />
          </svg>
        )}
        <span className="relative z-10">{children}</span>
      </Comp>
    );
  }
);
LiquidButton.displayName = 'LiquidButton';

export { LiquidButton, liquidButtonVariants };

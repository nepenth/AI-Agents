import * as React from 'react';
import { Slot } from '@radix-ui/react-slot';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/utils/cn';

const liquidButtonVariants = cva(
  'inline-flex items-center justify-center whitespace-nowrap rounded-lg text-sm font-semibold ring-offset-background transition-all duration-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 animate-lift-hover backdrop-blur-glass-subtle',
  {
    variants: {
      variant: {
        primary: 'bg-glass-bg-primary text-[var(--liquid-button-text-color)] hover:bg-glass-bg-secondary border border-glass-border-primary shadow-glass-md',
        secondary: 'bg-glass-bg-secondary text-[var(--liquid-button-text-color)] hover:bg-glass-bg-tertiary border border-glass-border-secondary shadow-glass-sm',
        ghost: 'text-[var(--liquid-button-text-color)] hover:bg-white/10',
        glass: 'bg-glass-button-bg border border-glass-button-border shadow-glass-button backdrop-blur-glass-button text-white hover:scale-105 hover:shadow-glass-button-hover hover:backdrop-blur-glass-button-hover rounded-[20px]',
      },
      size: {
        default: 'h-10 px-6 py-3',
        sm: 'h-9 px-4 py-2',
        lg: 'h-11 px-8 py-4',
        icon: 'h-12 w-12',
      },
    },
    defaultVariants: {
      variant: 'primary',
      size: 'default',
    },
  }
);

export interface LiquidButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof liquidButtonVariants> {
  asChild?: boolean;
  loading?: boolean;
}

const LiquidButton = React.forwardRef<HTMLButtonElement, LiquidButtonProps>(
  ({ className, variant, size, asChild = false, loading = false, children, ...props }, ref) => {
    const Comp = asChild ? Slot : 'button';
    return (
      <Comp
        className={cn(liquidButtonVariants({ variant, size, className }))}
        ref={ref}
        disabled={loading || props.disabled}
        {...props}
      >
        {loading && (
          <svg
            className="animate-spin -ml-1 mr-2 h-4 w-4"
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
        {children}
      </Comp>
    );
  }
);
LiquidButton.displayName = 'LiquidButton';

export { LiquidButton, liquidButtonVariants };

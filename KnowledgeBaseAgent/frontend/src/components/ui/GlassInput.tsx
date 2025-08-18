import * as React from 'react';
import { cn } from '@/utils/cn';
import { Input, type InputProps } from './Input';

const GlassInput = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, ...props }, ref) => {
    return (
      <Input
        className={cn(
          'border-glass-border-secondary bg-glass-bg-tertiary text-white placeholder:text-gray-400 focus:ring-offset-0 focus:border-glass-border-primary focus:bg-glass-bg-secondary',
          'transition-all duration-300 ease-in-out',
          className
        )}
        ref={ref}
        {...props}
      />
    );
  }
);
GlassInput.displayName = 'GlassInput';

export { GlassInput };

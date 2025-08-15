import React from 'react';
import { cn } from '../../utils/cn';

export interface ProgressBarProps {
  value: number; // 0-100
  max?: number;
  className?: string;
  showLabel?: boolean;
  label?: string;
  variant?: 'default' | 'success' | 'warning' | 'error';
  size?: 'sm' | 'md' | 'lg';
  animated?: boolean;
  striped?: boolean;
}

export const ProgressBar: React.FC<ProgressBarProps> = ({
  value,
  max = 100,
  className,
  showLabel = false,
  label,
  variant = 'default',
  size = 'md',
  animated = false,
  striped = false
}) => {
  const percentage = Math.min(Math.max((value / max) * 100, 0), 100);
  
  const sizeClasses = {
    sm: 'h-2',
    md: 'h-3',
    lg: 'h-4'
  };
  
  const variantClasses = {
    default: 'bg-blue-600',
    success: 'bg-green-600',
    warning: 'bg-yellow-600',
    error: 'bg-red-600'
  };
  
  const backgroundClasses = {
    default: 'bg-blue-100',
    success: 'bg-green-100',
    warning: 'bg-yellow-100',
    error: 'bg-red-100'
  };
  
  return (
    <div className={cn('w-full', className)}>
      {(showLabel || label) && (
        <div className="flex justify-between items-center mb-1">
          <span className="text-sm font-medium text-gray-700">
            {label || 'Progress'}
          </span>
          <span className="text-sm text-gray-500">
            {percentage.toFixed(0)}%
          </span>
        </div>
      )}
      <div
        className={cn(
          'w-full rounded-full overflow-hidden',
          sizeClasses[size],
          backgroundClasses[variant]
        )}
      >
        <div
          className={cn(
            'h-full rounded-full transition-all duration-300 ease-out',
            variantClasses[variant],
            {
              'animate-pulse': animated,
              'bg-gradient-to-r from-transparent via-white to-transparent bg-[length:200%_100%] animate-[shimmer_2s_infinite]': striped
            }
          )}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
};

// Add shimmer animation to global CSS
export const progressBarStyles = `
@keyframes shimmer {
  0% { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}
`;
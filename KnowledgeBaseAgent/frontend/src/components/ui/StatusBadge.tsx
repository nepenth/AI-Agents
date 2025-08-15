import React from 'react';
import { cn } from '../../utils/cn';

export type StatusType = 
  | 'pending' 
  | 'running' 
  | 'completed' 
  | 'failed' 
  | 'warning'
  | 'info'
  | 'success'
  | 'error';

export interface StatusBadgeProps {
  status: StatusType;
  label?: string;
  className?: string;
  size?: 'sm' | 'md' | 'lg';
  showIcon?: boolean;
  animated?: boolean;
}

const statusConfig = {
  pending: {
    icon: '⏳',
    label: 'Pending',
    classes: 'bg-gray-100 text-gray-800 border-gray-200'
  },
  running: {
    icon: '🔄',
    label: 'Running',
    classes: 'bg-blue-100 text-blue-800 border-blue-200'
  },
  completed: {
    icon: '✅',
    label: 'Completed',
    classes: 'bg-green-100 text-green-800 border-green-200'
  },
  failed: {
    icon: '❌',
    label: 'Failed',
    classes: 'bg-red-100 text-red-800 border-red-200'
  },
  warning: {
    icon: '⚠️',
    label: 'Warning',
    classes: 'bg-yellow-100 text-yellow-800 border-yellow-200'
  },
  info: {
    icon: 'ℹ️',
    label: 'Info',
    classes: 'bg-blue-100 text-blue-800 border-blue-200'
  },
  success: {
    icon: '✅',
    label: 'Success',
    classes: 'bg-green-100 text-green-800 border-green-200'
  },
  error: {
    icon: '❌',
    label: 'Error',
    classes: 'bg-red-100 text-red-800 border-red-200'
  }
};

export const StatusBadge: React.FC<StatusBadgeProps> = ({
  status,
  label,
  className,
  size = 'md',
  showIcon = true,
  animated = false
}) => {
  const config = statusConfig[status];
  const displayLabel = label || config.label;
  
  const sizeClasses = {
    sm: 'px-2 py-1 text-xs',
    md: 'px-3 py-1 text-sm',
    lg: 'px-4 py-2 text-base'
  };
  
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 font-medium rounded-full border',
        config.classes,
        sizeClasses[size],
        {
          'animate-pulse': animated && status === 'running'
        },
        className
      )}
    >
      {showIcon && (
        <span 
          className={cn(
            'inline-block',
            {
              'animate-spin': animated && status === 'running' && config.icon === '🔄'
            }
          )}
        >
          {config.icon}
        </span>
      )}
      {displayLabel}
    </span>
  );
};

// Utility function to get status from string
export const getStatusType = (status: string): StatusType => {
  const normalizedStatus = status.toLowerCase();
  
  if (normalizedStatus.includes('pending') || normalizedStatus.includes('waiting')) {
    return 'pending';
  }
  if (normalizedStatus.includes('running') || normalizedStatus.includes('processing')) {
    return 'running';
  }
  if (normalizedStatus.includes('completed') || normalizedStatus.includes('done')) {
    return 'completed';
  }
  if (normalizedStatus.includes('failed') || normalizedStatus.includes('error')) {
    return 'failed';
  }
  if (normalizedStatus.includes('warning')) {
    return 'warning';
  }
  
  return 'info';
};
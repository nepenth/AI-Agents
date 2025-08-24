import * as React from 'react';
import { cn } from '@/utils/cn';
import { GlassCard } from './GlassCard';

interface ChartProps {
  title?: string;
  description?: string;
  children: React.ReactNode;
  className?: string;
}

export function Chart({ title, description, children, className }: ChartProps) {
  return (
    <GlassCard variant="secondary" className={cn('p-6', className)}>
      {(title || description) && (
        <div className="mb-4 relative z-10">
          {title && (
            <h3 className="text-lg font-semibold text-foreground mb-1">{title}</h3>
          )}
          {description && (
            <p className="text-sm text-muted-foreground">{description}</p>
          )}
        </div>
      )}
      <div className="relative z-10">
        {children}
      </div>
    </GlassCard>
  );
}

interface ProgressChartProps {
  value: number;
  max?: number;
  label?: string;
  color?: 'primary' | 'secondary' | 'success' | 'warning' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  showValue?: boolean;
  className?: string;
}

export function ProgressChart({ 
  value, 
  max = 100, 
  label, 
  color = 'primary',
  size = 'md',
  showValue = true,
  className 
}: ProgressChartProps) {
  const percentage = Math.min((value / max) * 100, 100);
  
  const colorClasses = {
    primary: 'bg-primary',
    secondary: 'bg-secondary',
    success: 'bg-green-500',
    warning: 'bg-yellow-500',
    danger: 'bg-red-500',
  };

  const sizeClasses = {
    sm: 'h-2',
    md: 'h-3',
    lg: 'h-4',
  };

  return (
    <div className={cn('space-y-2', className)}>
      {(label || showValue) && (
        <div className="flex items-center justify-between text-sm">
          {label && <span className="text-foreground font-medium">{label}</span>}
          {showValue && (
            <span className="text-muted-foreground">
              {Math.round(percentage)}%
            </span>
          )}
        </div>
      )}
      <div className={cn(
        'w-full bg-glass-tertiary rounded-full overflow-hidden backdrop-blur-sm border border-glass-border-tertiary',
        sizeClasses[size]
      )}>
        <div
          className={cn(
            'h-full transition-all duration-500 ease-out rounded-full shadow-glass-tertiary',
            colorClasses[color]
          )}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}

interface MetricCardProps {
  title: string;
  value: string | number;
  change?: {
    value: number;
    type: 'increase' | 'decrease';
  };
  icon?: React.ReactNode;
  className?: string;
}

export function MetricCard({ title, value, change, icon, className }: MetricCardProps) {
  return (
    <GlassCard variant="tertiary" className={cn('p-4', className)}>
      <div className="flex items-center justify-between relative z-10">
        <div className="flex-1">
          <p className="text-sm text-muted-foreground mb-1">{title}</p>
          <p className="text-2xl font-bold text-foreground">{value}</p>
          {change && (
            <div className={cn(
              'flex items-center text-xs mt-1',
              change.type === 'increase' ? 'text-green-500' : 'text-red-500'
            )}>
              <span className="mr-1">
                {change.type === 'increase' ? '↗' : '↘'}
              </span>
              {Math.abs(change.value)}%
            </div>
          )}
        </div>
        {icon && (
          <div className="p-2 bg-glass-secondary rounded-lg border border-glass-border-secondary backdrop-blur-sm">
            {icon}
          </div>
        )}
      </div>
    </GlassCard>
  );
}

interface SimpleBarChartProps {
  data: Array<{ label: string; value: number; color?: string }>;
  maxValue?: number;
  className?: string;
}

export function SimpleBarChart({ data, maxValue, className }: SimpleBarChartProps) {
  const max = maxValue || Math.max(...data.map(d => d.value));
  
  return (
    <div className={cn('space-y-3', className)}>
      {data.map((item, index) => (
        <div key={index} className="space-y-1">
          <div className="flex items-center justify-between text-sm">
            <span className="text-foreground font-medium">{item.label}</span>
            <span className="text-muted-foreground">{item.value}</span>
          </div>
          <div className="w-full bg-glass-tertiary rounded-full h-2 overflow-hidden backdrop-blur-sm border border-glass-border-tertiary">
            <div
              className={cn(
                'h-full transition-all duration-500 ease-out rounded-full',
                item.color || 'bg-primary'
              )}
              style={{ width: `${(item.value / max) * 100}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
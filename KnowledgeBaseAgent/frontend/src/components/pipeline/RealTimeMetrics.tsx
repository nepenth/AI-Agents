import React, { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/Card';
import { ProgressBar } from '../ui/ProgressBar';
import { cn } from '../../utils/cn';

export interface MetricData {
  label: string;
  value: number;
  unit: string;
  trend?: 'up' | 'down' | 'stable';
  color?: 'blue' | 'green' | 'yellow' | 'red' | 'purple';
  target?: number;
  history?: number[];
}

export interface RealTimeMetricsProps {
  metrics: MetricData[];
  updateInterval?: number;
  showTrends?: boolean;
  showSparklines?: boolean;
  className?: string;
}

export const RealTimeMetrics: React.FC<RealTimeMetricsProps> = ({
  metrics,
  updateInterval = 1000,
  showTrends = true,
  showSparklines = true,
  className
}) => {
  const [animatedValues, setAnimatedValues] = useState<{ [key: string]: number }>({});
  const [isUpdating, setIsUpdating] = useState(false);

  // Animate value changes
  useEffect(() => {
    metrics.forEach(metric => {
      const currentValue = animatedValues[metric.label] || 0;
      if (currentValue !== metric.value) {
        setIsUpdating(true);
        
        const startValue = currentValue;
        const targetValue = metric.value;
        const duration = 500;
        const startTime = Date.now();

        const animate = () => {
          const elapsed = Date.now() - startTime;
          const progress = Math.min(elapsed / duration, 1);
          
          // Easing function
          const easeOutCubic = (t: number) => 1 - Math.pow(1 - t, 3);
          const easedProgress = easeOutCubic(progress);
          
          const currentAnimatedValue = startValue + (targetValue - startValue) * easedProgress;
          
          setAnimatedValues(prev => ({
            ...prev,
            [metric.label]: currentAnimatedValue
          }));

          if (progress < 1) {
            requestAnimationFrame(animate);
          } else {
            setIsUpdating(false);
          }
        };

        requestAnimationFrame(animate);
      }
    });
  }, [metrics, animatedValues]);

  const getTrendIcon = (trend?: 'up' | 'down' | 'stable') => {
    switch (trend) {
      case 'up': return '📈';
      case 'down': return '📉';
      case 'stable': return '➡️';
      default: return '';
    }
  };

  const getTrendColor = (trend?: 'up' | 'down' | 'stable') => {
    switch (trend) {
      case 'up': return 'text-green-600';
      case 'down': return 'text-red-600';
      case 'stable': return 'text-gray-600';
      default: return 'text-gray-600';
    }
  };

  const getColorClasses = (color?: string) => {
    switch (color) {
      case 'blue': return 'text-blue-600 bg-blue-50 border-blue-200';
      case 'green': return 'text-green-600 bg-green-50 border-green-200';
      case 'yellow': return 'text-yellow-600 bg-yellow-50 border-yellow-200';
      case 'red': return 'text-red-600 bg-red-50 border-red-200';
      case 'purple': return 'text-purple-600 bg-purple-50 border-purple-200';
      default: return 'text-gray-600 bg-gray-50 border-gray-200';
    }
  };

  const formatValue = (value: number, unit: string) => {
    if (unit === '%') return `${value.toFixed(1)}%`;
    if (unit === 'ms') return `${Math.round(value)}ms`;
    if (unit === 's') return `${value.toFixed(1)}s`;
    if (unit === 'MB') return `${value.toFixed(1)}MB`;
    if (unit === 'req/s') return `${value.toFixed(1)} req/s`;
    return `${value.toFixed(1)} ${unit}`;
  };

  const renderSparkline = (history: number[], color: string = 'blue') => {
    if (!history || history.length < 2) return null;

    const max = Math.max(...history);
    const min = Math.min(...history);
    const range = max - min || 1;

    const points = history.map((value, index) => {
      const x = (index / (history.length - 1)) * 60;
      const y = 20 - ((value - min) / range) * 20;
      return `${x},${y}`;
    }).join(' ');

    return (
      <svg width="60" height="20" className="inline-block">
        <polyline
          points={points}
          fill="none"
          stroke={color === 'blue' ? '#3B82F6' : 
                 color === 'green' ? '#10B981' :
                 color === 'red' ? '#EF4444' :
                 color === 'yellow' ? '#F59E0B' : '#6B7280'}
          strokeWidth="2"
          className="transition-all duration-300"
        />
      </svg>
    );
  };

  return (
    <div className={cn('grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4', className)}>
      {metrics.map((metric, index) => {
        const animatedValue = animatedValues[metric.label] || metric.value;
        const colorClasses = getColorClasses(metric.color);
        
        return (
          <Card key={metric.label} className={cn(
            'border-2 transition-all duration-300',
            isUpdating && 'scale-[1.02] shadow-md',
            colorClasses.includes('border-') ? colorClasses : 'border-gray-200'
          )}>
            <CardContent className="p-4">
              <div className="flex items-center justify-between mb-2">
                <div className="text-sm font-medium text-gray-700">
                  {metric.label}
                </div>
                {showTrends && metric.trend && (
                  <div className={cn('text-xs flex items-center gap-1', getTrendColor(metric.trend))}>
                    <span>{getTrendIcon(metric.trend)}</span>
                  </div>
                )}
              </div>
              
              <div className="flex items-end justify-between">
                <div>
                  <div className={cn(
                    'text-2xl font-bold transition-all duration-300',
                    colorClasses.split(' ')[0],
                    isUpdating && 'scale-110'
                  )}>
                    {formatValue(animatedValue, metric.unit)}
                  </div>
                  
                  {metric.target && (
                    <div className="text-xs text-gray-500 mt-1">
                      Target: {formatValue(metric.target, metric.unit)}
                    </div>
                  )}
                </div>
                
                {showSparklines && metric.history && (
                  <div className="ml-2">
                    {renderSparkline(metric.history, metric.color)}
                  </div>
                )}
              </div>
              
              {/* Progress bar for metrics with targets */}
              {metric.target && (
                <div className="mt-3">
                  <ProgressBar
                    value={(animatedValue / metric.target) * 100}
                    variant={metric.color === 'red' ? 'error' : 
                           metric.color === 'green' ? 'success' : 'default'}
                    size="sm"
                    showLabel={false}
                  />
                </div>
              )}
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
};

// Specialized component for pipeline metrics
export interface PipelineMetricsProps {
  processingSpeed: number; // items per second
  successRate: number; // percentage
  averageResponseTime: number; // milliseconds
  activeConnections: number;
  memoryUsage: number; // MB
  cpuUsage: number; // percentage
  queueSize: number;
  errorRate: number; // percentage
  className?: string;
}

export const PipelineMetrics: React.FC<PipelineMetricsProps> = ({
  processingSpeed,
  successRate,
  averageResponseTime,
  activeConnections,
  memoryUsage,
  cpuUsage,
  queueSize,
  errorRate,
  className
}) => {
  const [metricsHistory, setMetricsHistory] = useState<{ [key: string]: number[] }>({
    processingSpeed: [],
    successRate: [],
    averageResponseTime: [],
    activeConnections: [],
    memoryUsage: [],
    cpuUsage: [],
    queueSize: [],
    errorRate: []
  });

  // Update metrics history
  useEffect(() => {
    setMetricsHistory(prev => ({
      processingSpeed: [...prev.processingSpeed.slice(-19), processingSpeed],
      successRate: [...prev.successRate.slice(-19), successRate],
      averageResponseTime: [...prev.averageResponseTime.slice(-19), averageResponseTime],
      activeConnections: [...prev.activeConnections.slice(-19), activeConnections],
      memoryUsage: [...prev.memoryUsage.slice(-19), memoryUsage],
      cpuUsage: [...prev.cpuUsage.slice(-19), cpuUsage],
      queueSize: [...prev.queueSize.slice(-19), queueSize],
      errorRate: [...prev.errorRate.slice(-19), errorRate]
    }));
  }, [processingSpeed, successRate, averageResponseTime, activeConnections, memoryUsage, cpuUsage, queueSize, errorRate]);

  const metrics: MetricData[] = [
    {
      label: 'Processing Speed',
      value: processingSpeed,
      unit: 'items/s',
      color: 'blue',
      history: metricsHistory.processingSpeed,
      trend: processingSpeed > 5 ? 'up' : processingSpeed < 2 ? 'down' : 'stable'
    },
    {
      label: 'Success Rate',
      value: successRate,
      unit: '%',
      color: successRate > 95 ? 'green' : successRate > 80 ? 'yellow' : 'red',
      target: 100,
      history: metricsHistory.successRate,
      trend: successRate > 90 ? 'up' : successRate < 80 ? 'down' : 'stable'
    },
    {
      label: 'Response Time',
      value: averageResponseTime,
      unit: 'ms',
      color: averageResponseTime < 1000 ? 'green' : averageResponseTime < 3000 ? 'yellow' : 'red',
      history: metricsHistory.averageResponseTime,
      trend: averageResponseTime < 1000 ? 'up' : averageResponseTime > 3000 ? 'down' : 'stable'
    },
    {
      label: 'Active Connections',
      value: activeConnections,
      unit: 'conn',
      color: 'purple',
      history: metricsHistory.activeConnections
    },
    {
      label: 'Memory Usage',
      value: memoryUsage,
      unit: 'MB',
      color: memoryUsage < 500 ? 'green' : memoryUsage < 1000 ? 'yellow' : 'red',
      target: 1024,
      history: metricsHistory.memoryUsage
    },
    {
      label: 'CPU Usage',
      value: cpuUsage,
      unit: '%',
      color: cpuUsage < 50 ? 'green' : cpuUsage < 80 ? 'yellow' : 'red',
      target: 100,
      history: metricsHistory.cpuUsage
    },
    {
      label: 'Queue Size',
      value: queueSize,
      unit: 'items',
      color: queueSize < 10 ? 'green' : queueSize < 50 ? 'yellow' : 'red',
      history: metricsHistory.queueSize
    },
    {
      label: 'Error Rate',
      value: errorRate,
      unit: '%',
      color: errorRate < 1 ? 'green' : errorRate < 5 ? 'yellow' : 'red',
      target: 0,
      history: metricsHistory.errorRate,
      trend: errorRate < 1 ? 'down' : errorRate > 5 ? 'up' : 'stable'
    }
  ];

  return (
    <div className={className}>
      <div className="mb-4">
        <h3 className="text-lg font-semibold text-gray-900">Real-Time Pipeline Metrics</h3>
        <p className="text-sm text-gray-600">Live performance monitoring and system health</p>
      </div>
      <RealTimeMetrics 
        metrics={metrics}
        showTrends={true}
        showSparklines={true}
      />
    </div>
  );
};
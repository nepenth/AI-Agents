import React, { useEffect, useState } from 'react';
import { ProgressBar } from '../ui/ProgressBar';
import { cn } from '../../utils/cn';

export interface ProgressIndicatorProps {
  value: number;
  max?: number;
  label?: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  showPercentage?: boolean;
  showETA?: boolean;
  estimatedDuration?: number;
  startTime?: Date;
  className?: string;
  size?: 'sm' | 'md' | 'lg';
  variant?: 'default' | 'success' | 'warning' | 'error';
  animated?: boolean;
  pulseOnUpdate?: boolean;
  showSpeedometer?: boolean;
}

export const ProgressIndicator: React.FC<ProgressIndicatorProps> = ({
  value,
  max = 100,
  label,
  status,
  showPercentage = true,
  showETA = false,
  estimatedDuration,
  startTime,
  className,
  size = 'md',
  variant,
  animated = true,
  pulseOnUpdate = true,
  showSpeedometer = false
}) => {
  const [displayValue, setDisplayValue] = useState(0);
  const [isUpdating, setIsUpdating] = useState(false);
  const [speed, setSpeed] = useState(0); // Progress per second
  const [eta, setETA] = useState<number | null>(null);

  const percentage = Math.min(Math.max((value / max) * 100, 0), 100);

  // Smooth animation to new value
  useEffect(() => {
    if (status === 'running' && animated) {
      const startValue = displayValue;
      const targetValue = percentage;
      const duration = 500; // Animation duration in ms
      const startTime = Date.now();

      const animate = () => {
        const elapsed = Date.now() - startTime;
        const progress = Math.min(elapsed / duration, 1);
        
        // Easing function for smooth animation
        const easeOutCubic = (t: number) => 1 - Math.pow(1 - t, 3);
        const easedProgress = easeOutCubic(progress);
        
        const currentValue = startValue + (targetValue - startValue) * easedProgress;
        setDisplayValue(currentValue);

        if (progress < 1) {
          requestAnimationFrame(animate);
        }
      };

      requestAnimationFrame(animate);
    } else {
      setDisplayValue(percentage);
    }
  }, [percentage, status, animated, displayValue]);

  // Calculate speed and ETA
  useEffect(() => {
    if (status === 'running' && startTime && showETA) {
      const elapsed = Date.now() - startTime.getTime();
      const currentSpeed = (percentage / elapsed) * 1000; // Progress per second
      setSpeed(currentSpeed);

      if (currentSpeed > 0 && percentage < 100) {
        const remainingProgress = 100 - percentage;
        const estimatedTimeRemaining = remainingProgress / currentSpeed;
        setETA(estimatedTimeRemaining);
      } else {
        setETA(null);
      }
    } else {
      setSpeed(0);
      setETA(null);
    }
  }, [percentage, startTime, status, showETA]);

  // Pulse effect on updates
  useEffect(() => {
    if (pulseOnUpdate && status === 'running') {
      setIsUpdating(true);
      const timer = setTimeout(() => setIsUpdating(false), 300);
      return () => clearTimeout(timer);
    }
  }, [value, pulseOnUpdate, status]);

  const getVariant = () => {
    if (variant) return variant;
    
    switch (status) {
      case 'completed': return 'success';
      case 'failed': return 'error';
      case 'running': return 'default';
      default: return 'default';
    }
  };

  const formatETA = (seconds: number) => {
    if (seconds < 60) return `${Math.round(seconds)}s`;
    if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
    return `${Math.round(seconds / 3600)}h`;
  };

  const getSpeedColor = () => {
    if (speed > 10) return 'text-green-600';
    if (speed > 5) return 'text-yellow-600';
    return 'text-red-600';
  };

  return (
    <div className={cn('space-y-2', className)}>
      {/* Header with label and stats */}
      {(label || showPercentage || showETA || showSpeedometer) && (
        <div className="flex justify-between items-center text-sm">
          <div className="flex items-center gap-2">
            {label && (
              <span className={cn(
                'font-medium transition-colors',
                isUpdating && 'text-blue-600'
              )}>
                {label}
              </span>
            )}
            {status === 'running' && (
              <div className="flex items-center gap-1">
                <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse"></div>
                <span className="text-blue-600 text-xs">Processing</span>
              </div>
            )}
          </div>
          
          <div className="flex items-center gap-3 text-xs text-gray-600">
            {showPercentage && (
              <span className={cn(
                'font-medium',
                isUpdating && 'text-blue-600 scale-110 transition-transform'
              )}>
                {displayValue.toFixed(1)}%
              </span>
            )}
            
            {showSpeedometer && speed > 0 && (
              <span className={cn('font-medium', getSpeedColor())}>
                {speed.toFixed(1)}/s
              </span>
            )}
            
            {showETA && eta && (
              <span className="text-gray-500">
                ETA: {formatETA(eta)}
              </span>
            )}
          </div>
        </div>
      )}

      {/* Progress Bar */}
      <div className={cn(
        'transition-all duration-300',
        isUpdating && 'scale-[1.02] shadow-md'
      )}>
        <ProgressBar
          value={displayValue}
          variant={getVariant()}
          size={size}
          animated={status === 'running' && animated}
          striped={status === 'running'}
        />
      </div>

      {/* Status indicators */}
      {status === 'running' && (
        <div className="flex items-center gap-2 text-xs text-gray-500">
          <div className="flex items-center gap-1">
            <div className="w-1 h-1 bg-blue-500 rounded-full animate-ping"></div>
            <div className="w-1 h-1 bg-blue-500 rounded-full animate-ping animation-delay-100"></div>
            <div className="w-1 h-1 bg-blue-500 rounded-full animate-ping animation-delay-200"></div>
          </div>
          <span>Processing in real-time</span>
        </div>
      )}

      {status === 'completed' && (
        <div className="flex items-center gap-2 text-xs text-green-600">
          <span>✅</span>
          <span>Completed successfully</span>
        </div>
      )}

      {status === 'failed' && (
        <div className="flex items-center gap-2 text-xs text-red-600">
          <span>❌</span>
          <span>Processing failed</span>
        </div>
      )}
    </div>
  );
};

// Specialized progress indicator for phases
export interface PhaseProgressIndicatorProps {
  phaseName: string;
  phaseNumber: number;
  status: 'pending' | 'running' | 'completed' | 'failed';
  progress?: number;
  subPhases?: Array<{
    name: string;
    status: 'pending' | 'running' | 'completed' | 'failed';
    progress?: number;
  }>;
  startTime?: Date;
  duration?: number;
  aiModelUsed?: string;
  isRealAI?: boolean;
  className?: string;
}

export const PhaseProgressIndicator: React.FC<PhaseProgressIndicatorProps> = ({
  phaseName,
  phaseNumber,
  status,
  progress = 0,
  subPhases,
  startTime,
  duration,
  aiModelUsed,
  isRealAI,
  className
}) => {
  const getPhaseIcon = () => {
    switch (status) {
      case 'completed': return isRealAI ? '🤖✅' : '✅';
      case 'running': return '🔄';
      case 'failed': return '❌';
      default: return '⏳';
    }
  };

  const formatDuration = (ms: number) => {
    if (ms < 1000) return `${ms}ms`;
    if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
    return `${(ms / 60000).toFixed(1)}m`;
  };

  return (
    <div className={cn('space-y-3', className)}>
      {/* Phase Header */}
      <div className="flex items-center gap-3">
        <span className={cn(
          'text-2xl transition-transform duration-300',
          status === 'running' && 'animate-pulse scale-110'
        )}>
          {getPhaseIcon()}
        </span>
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-lg">
              Phase {phaseNumber}: {phaseName}
            </h3>
            {aiModelUsed && (
              <div className={cn(
                'text-xs px-2 py-1 rounded-full border',
                isRealAI 
                  ? 'bg-green-100 text-green-700 border-green-200'
                  : 'bg-yellow-100 text-yellow-700 border-yellow-200'
              )}>
                {aiModelUsed} {isRealAI ? '(Real AI)' : '(Simulated)'}
              </div>
            )}
          </div>
          {duration && (
            <div className="text-sm text-gray-600 mt-1">
              Duration: {formatDuration(duration)}
            </div>
          )}
        </div>
      </div>

      {/* Main Progress */}
      {status === 'running' && (
        <ProgressIndicator
          value={progress}
          label={`Processing ${phaseName}`}
          status={status}
          showETA={true}
          showSpeedometer={true}
          startTime={startTime}
          size="md"
          animated={true}
          pulseOnUpdate={true}
        />
      )}

      {/* Sub-phases */}
      {subPhases && subPhases.length > 0 && (
        <div className="space-y-2 pl-6 border-l-2 border-gray-200">
          <div className="text-sm font-medium text-gray-700">Sub-phases:</div>
          {subPhases.map((subPhase, index) => (
            <div key={index} className="space-y-1">
              <div className="flex items-center gap-2 text-sm">
                <span className={cn(
                  'w-2 h-2 rounded-full',
                  {
                    'bg-gray-300': subPhase.status === 'pending',
                    'bg-blue-500 animate-pulse': subPhase.status === 'running',
                    'bg-green-500': subPhase.status === 'completed',
                    'bg-red-500': subPhase.status === 'failed'
                  }
                )}></span>
                <span className="font-medium">{subPhase.name}</span>
              </div>
              {subPhase.status === 'running' && subPhase.progress !== undefined && (
                <div className="ml-4">
                  <ProgressIndicator
                    value={subPhase.progress}
                    status={subPhase.status}
                    size="sm"
                    showPercentage={true}
                    animated={true}
                  />
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
import React from 'react';
import { GlassCard } from '../ui/GlassCard';
import { ProgressBar } from '../ui/ProgressBar';
import { StatusBadge } from '../ui/StatusBadge';
import { LiquidButton } from '../ui/LiquidButton';
import { RotateCcw, Eye, Clock, Zap } from 'lucide-react';
import { cn } from '../../utils/cn';

export interface PhaseCardProps {
  phase: {
    id: string;
    name: string;
    description: string;
    status: 'pending' | 'running' | 'completed' | 'failed';
    progress?: number;
    duration?: number;
    error?: string;
    aiModelUsed?: string;
    isRealAI?: boolean;
    subPhases?: Array<{
      id: string;
      name: string;
      description: string;
      status: 'pending' | 'running' | 'completed' | 'failed';
      progress?: number;
      duration?: number;
      error?: string;
    }>;
  };
  index: number;
  onRetry?: (phaseId: string) => void;
  onViewDetails?: (phaseId: string) => void;
}

export const PhaseCard: React.FC<PhaseCardProps> = ({
  phase,
  index,
  onRetry,
  onViewDetails
}) => {
  const getPhaseIcon = (status: string, isRealAI?: boolean) => {
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

  const getCardBorderClass = () => {
    switch (phase.status) {
      case 'running': return 'border-blue-200 bg-blue-50';
      case 'completed': return 'border-green-200 bg-green-50';
      case 'failed': return 'border-red-200 bg-red-50';
      default: return 'border-gray-200 bg-white';
    }
  };

  return (
    <GlassCard 
      variant={
        phase.status === 'running' ? 'interactive' : 
        phase.status === 'completed' ? 'primary' : 
        phase.status === 'failed' ? 'secondary' : 'tertiary'
      }
      elevated={phase.status === 'running'}
      className={cn(
        'transition-all duration-300',
        phase.status === 'running' && 'scale-[1.02] shadow-glass-interactive-hover'
      )}
    >
      <div className="p-6 relative z-10">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <span className={cn(
              'text-3xl transition-transform duration-300',
              phase.status === 'running' && 'animate-pulse scale-110'
            )}>
              {getPhaseIcon(phase.status, phase.isRealAI)}
            </span>
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-2">
                <h3 className="text-lg font-semibold text-foreground">
                  Phase {index + 1}: {phase.name}
                </h3>
                <StatusBadge 
                  status={phase.status} 
                  size="sm"
                  animated={phase.status === 'running'}
                />
              </div>
              <p className="text-sm text-muted-foreground mb-3">{phase.description}</p>
              
              {/* AI Model Information */}
              {phase.aiModelUsed && (
                <div className="flex items-center gap-2">
                  <div className="text-xs text-muted-foreground">
                    Model: <span className="font-medium text-foreground">{phase.aiModelUsed}</span>
                  </div>
                  <div className={cn(
                    'text-xs px-2 py-1 rounded-full backdrop-blur-sm border',
                    phase.isRealAI 
                      ? 'bg-green-500/20 text-green-600 border-green-500/30'
                      : 'bg-yellow-500/20 text-yellow-600 border-yellow-500/30'
                  )}>
                    {phase.isRealAI ? 'Real AI' : 'Simulated'}
                  </div>
                </div>
              )}
            </div>
          </div>
          
          {/* Duration and Actions */}
          <div className="flex items-center gap-3">
            {phase.duration && (
              <div className="text-right">
                <div className="flex items-center gap-1 text-sm font-medium text-foreground">
                  <Clock className="h-3 w-3" />
                  {formatDuration(phase.duration)}
                </div>
                <div className="text-xs text-muted-foreground">duration</div>
              </div>
            )}
            
            {/* Action Buttons */}
            <div className="flex gap-2">
              {phase.status === 'failed' && onRetry && (
                <LiquidButton
                  variant="outline"
                  size="sm"
                  onClick={() => onRetry(phase.id)}
                >
                  <RotateCcw className="h-3 w-3 mr-1" />
                  Retry
                </LiquidButton>
              )}
              {onViewDetails && (
                <LiquidButton
                  variant="ghost"
                  size="sm"
                  onClick={() => onViewDetails(phase.id)}
                >
                  <Eye className="h-3 w-3 mr-1" />
                  Details
                </LiquidButton>
              )}
            </div>
          </div>
        </div>
      
        {/* Progress Bar for Running Phase */}
        {phase.status === 'running' && phase.progress !== undefined && (
          <div className="mb-4">
            <ProgressBar
              value={phase.progress}
              variant="default"
              size="md"
              showLabel
              animated
              label={`Processing ${phase.name}`}
              className="mb-2"
            />
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Zap className="h-3 w-3" />
              <span>Processing in real-time</span>
            </div>
          </div>
        )}
        
        {/* Error Display */}
        {phase.error && (
          <div className="mb-4 p-4 bg-red-500/10 border border-red-500/20 rounded-xl backdrop-blur-sm">
            <div className="flex items-start gap-2">
              <span className="text-red-500 mt-0.5">⚠️</span>
              <div>
                <div className="text-red-600 text-sm font-medium">Error:</div>
                <div className="text-red-600 text-sm">{phase.error}</div>
                {phase.status === 'failed' && (
                  <div className="text-xs text-red-500 mt-2">
                    This phase failed and may need to be retried or investigated.
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
        
        {/* Success Message */}
        {phase.status === 'completed' && (
          <div className="mb-4 p-4 bg-green-500/10 border border-green-500/20 rounded-xl backdrop-blur-sm">
            <div className="flex items-center gap-2">
              <span className="text-green-500">✅</span>
              <div className="text-green-600 text-sm">
                Phase completed successfully
                {phase.isRealAI && ' with real AI processing'}
                {!phase.isRealAI && ' with simulated processing'}
              </div>
            </div>
          </div>
        )}

        {/* Sub-phases */}
        {phase.subPhases && phase.subPhases.length > 0 && (
          <div className="space-y-3">
            <div className="text-sm font-medium text-foreground border-b border-glass-border-tertiary pb-2">
              Sub-phases:
            </div>
            <div className="space-y-3">
              {phase.subPhases.map((subPhase) => (
                <div 
                  key={subPhase.id} 
                  className={cn(
                    'flex items-center gap-3 p-3 rounded-xl border backdrop-blur-sm transition-all duration-200',
                    {
                      'bg-glass-tertiary border-glass-border-tertiary': subPhase.status === 'pending',
                      'bg-blue-500/10 border-blue-500/20 shadow-glass-tertiary': subPhase.status === 'running',
                      'bg-green-500/10 border-green-500/20 shadow-glass-tertiary': subPhase.status === 'completed',
                      'bg-red-500/10 border-red-500/20 shadow-glass-tertiary': subPhase.status === 'failed'
                    }
                  )}
                >
                  <StatusBadge 
                    status={subPhase.status} 
                    size="sm"
                    animated={subPhase.status === 'running'}
                  />
                  <div className="flex-1">
                    <div className="text-sm font-medium text-foreground">{subPhase.name}</div>
                    <div className="text-xs text-muted-foreground">{subPhase.description}</div>
                    {subPhase.error && (
                      <div className="text-xs text-red-600 mt-1">
                        Error: {subPhase.error}
                      </div>
                    )}
                  </div>
                  {subPhase.duration && (
                    <div className="text-xs text-muted-foreground text-right flex items-center gap-1">
                      <Clock className="h-3 w-3" />
                      {formatDuration(subPhase.duration)}
                    </div>
                  )}
                  {subPhase.status === 'running' && subPhase.progress !== undefined && (
                    <div className="w-20">
                      <ProgressBar
                        value={subPhase.progress}
                        size="sm"
                        variant="default"
                        animated
                      />
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Phase Insights */}
        {phase.status === 'completed' && (
          <div className="mt-4 pt-4 border-t border-glass-border-tertiary">
            <div className="text-xs text-muted-foreground space-y-2">
              <div className="flex justify-between items-center">
                <span>Processing Quality:</span>
                <span className={cn(
                  'font-medium px-2 py-1 rounded-full text-xs',
                  phase.isRealAI 
                    ? 'text-green-600 bg-green-500/20' 
                    : 'text-yellow-600 bg-yellow-500/20'
                )}>
                  {phase.isRealAI ? 'Real AI Analysis' : 'Rule-based Fallback'}
                </span>
              </div>
              {phase.duration && (
                <div className="flex justify-between items-center">
                  <span>Performance:</span>
                  <span className={cn(
                    'font-medium px-2 py-1 rounded-full text-xs',
                    phase.duration < 5000 ? 'text-green-600 bg-green-500/20' : 
                    phase.duration < 15000 ? 'text-yellow-600 bg-yellow-500/20' : 'text-red-600 bg-red-500/20'
                  )}>
                    {phase.duration < 5000 ? 'Fast' : 
                     phase.duration < 15000 ? 'Normal' : 'Slow'}
                  </span>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </GlassCard>
  );
};
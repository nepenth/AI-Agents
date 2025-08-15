import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/Card';
import { ProgressBar } from '../ui/ProgressBar';
import { StatusBadge } from '../ui/StatusBadge';
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
    <Card className={cn(
      'border-2 transition-all duration-300',
      getCardBorderClass()
    )}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className={cn(
              'text-2xl transition-transform duration-300',
              phase.status === 'running' && 'animate-pulse'
            )}>
              {getPhaseIcon(phase.status, phase.isRealAI)}
            </span>
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1">
                <CardTitle className="text-lg">
                  Phase {index + 1}: {phase.name}
                </CardTitle>
                <StatusBadge 
                  status={phase.status} 
                  size="sm"
                  animated={phase.status === 'running'}
                />
              </div>
              <p className="text-sm text-gray-600">{phase.description}</p>
              
              {/* AI Model Information */}
              {phase.aiModelUsed && (
                <div className="flex items-center gap-2 mt-2">
                  <div className="text-xs text-gray-500">
                    Model: <span className="font-medium">{phase.aiModelUsed}</span>
                  </div>
                  <div className={cn(
                    'text-xs px-2 py-1 rounded-full',
                    phase.isRealAI 
                      ? 'bg-green-100 text-green-700 border border-green-200'
                      : 'bg-yellow-100 text-yellow-700 border border-yellow-200'
                  )}>
                    {phase.isRealAI ? 'Real AI' : 'Simulated'}
                  </div>
                </div>
              )}
            </div>
          </div>
          
          {/* Duration and Actions */}
          <div className="flex items-center gap-2">
            {phase.duration && (
              <div className="text-right">
                <div className="text-sm font-medium">{formatDuration(phase.duration)}</div>
                <div className="text-xs text-gray-500">duration</div>
              </div>
            )}
            
            {/* Action Buttons */}
            <div className="flex flex-col gap-1">
              {phase.status === 'failed' && onRetry && (
                <button
                  onClick={() => onRetry(phase.id)}
                  className="text-xs text-blue-600 hover:text-blue-800 underline"
                >
                  Retry
                </button>
              )}
              {onViewDetails && (
                <button
                  onClick={() => onViewDetails(phase.id)}
                  className="text-xs text-gray-600 hover:text-gray-800 underline"
                >
                  Details
                </button>
              )}
            </div>
          </div>
        </div>
      </CardHeader>
      
      <CardContent className="pt-0">
        {/* Progress Bar for Running Phase */}
        {phase.status === 'running' && phase.progress !== undefined && (
          <div className="mb-3">
            <ProgressBar
              value={phase.progress}
              variant="default"
              size="md"
              showLabel
              animated
              label={`Processing ${phase.name}`}
            />
          </div>
        )}
        
        {/* Error Display */}
        {phase.error && (
          <div className="text-red-600 text-sm bg-red-50 p-3 rounded border border-red-200 mb-3">
            <div className="flex items-start gap-2">
              <span className="text-red-500 mt-0.5">⚠️</span>
              <div>
                <strong>Error:</strong> {phase.error}
                {phase.status === 'failed' && (
                  <div className="text-xs text-red-500 mt-1">
                    This phase failed and may need to be retried or investigated.
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
        
        {/* Success Message */}
        {phase.status === 'completed' && (
          <div className="text-green-600 text-sm bg-green-50 p-2 rounded border border-green-200 mb-3">
            <div className="flex items-center gap-2">
              <span>✅</span>
              <span>
                Phase completed successfully
                {phase.isRealAI && ' with real AI processing'}
                {!phase.isRealAI && ' with simulated processing'}
              </span>
            </div>
          </div>
        )}

        {/* Sub-phases */}
        {phase.subPhases && phase.subPhases.length > 0 && (
          <div className="space-y-3">
            <div className="text-sm font-medium text-gray-700 border-b border-gray-200 pb-1">
              Sub-phases:
            </div>
            <div className="space-y-2">
              {phase.subPhases.map((subPhase) => (
                <div 
                  key={subPhase.id} 
                  className={cn(
                    'flex items-center gap-3 p-2 rounded border transition-colors',
                    {
                      'bg-gray-50 border-gray-200': subPhase.status === 'pending',
                      'bg-blue-50 border-blue-200': subPhase.status === 'running',
                      'bg-green-50 border-green-200': subPhase.status === 'completed',
                      'bg-red-50 border-red-200': subPhase.status === 'failed'
                    }
                  )}
                >
                  <StatusBadge 
                    status={subPhase.status} 
                    size="sm"
                    animated={subPhase.status === 'running'}
                  />
                  <div className="flex-1">
                    <div className="text-sm font-medium">{subPhase.name}</div>
                    <div className="text-xs text-gray-600">{subPhase.description}</div>
                    {subPhase.error && (
                      <div className="text-xs text-red-600 mt-1">
                        Error: {subPhase.error}
                      </div>
                    )}
                  </div>
                  {subPhase.duration && (
                    <div className="text-xs text-gray-500 text-right">
                      {formatDuration(subPhase.duration)}
                    </div>
                  )}
                  {subPhase.status === 'running' && subPhase.progress !== undefined && (
                    <div className="w-16">
                      <ProgressBar
                        value={subPhase.progress}
                        size="sm"
                        variant="default"
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
          <div className="mt-3 pt-3 border-t border-gray-200">
            <div className="text-xs text-gray-600">
              <div className="flex justify-between">
                <span>Processing Quality:</span>
                <span className={cn(
                  'font-medium',
                  phase.isRealAI ? 'text-green-600' : 'text-yellow-600'
                )}>
                  {phase.isRealAI ? 'Real AI Analysis' : 'Rule-based Fallback'}
                </span>
              </div>
              {phase.duration && (
                <div className="flex justify-between mt-1">
                  <span>Performance:</span>
                  <span className={cn(
                    'font-medium',
                    phase.duration < 5000 ? 'text-green-600' : 
                    phase.duration < 15000 ? 'text-yellow-600' : 'text-red-600'
                  )}>
                    {phase.duration < 5000 ? 'Fast' : 
                     phase.duration < 15000 ? 'Normal' : 'Slow'}
                  </span>
                </div>
              )}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
};
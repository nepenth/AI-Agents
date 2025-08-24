import React, { useState } from 'react';
import { 
  SparklesIcon, 
  CpuChipIcon, 
  ArrowsRightLeftIcon,
  CheckCircleIcon,
  ChartBarIcon,
  EyeIcon,
  DocumentTextIcon,
  TagIcon
} from '@heroicons/react/24/outline';
import { GlassCard } from '../ui/GlassCard';
import { LiquidButton } from '../ui/LiquidButton';
import { StatusBadge } from '../ui/StatusBadge';
import { cn } from '../../utils/cn';

export interface ProcessingResult {
  phase: string;
  phaseName: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  duration?: number;
  aiModelUsed?: string;
  isRealAI?: boolean;
  results?: {
    mediaAnalysis?: any;
    contentUnderstanding?: any;
    categorization?: any;
  };
  error?: string;
}

export interface ComparisonData {
  realAI: ProcessingResult[];
  simulated: ProcessingResult[];
  metrics: {
    realAI: {
      totalTime: number;
      averageTime: number;
      successRate: number;
      accuracy?: number;
    };
    simulated: {
      totalTime: number;
      averageTime: number;
      successRate: number;
      accuracy?: number;
    };
  };
}

export interface ComparisonViewProps {
  comparison: ComparisonData;
  onCopy?: (text: string, label: string) => void;
  copiedText?: string | null;
  className?: string;
}

const formatDuration = (ms: number): string => {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${(ms / 60000).toFixed(1)}m`;
};

const getPhaseIcon = (phase: string) => {
  switch (phase) {
    case 'phase_3_1': return EyeIcon;
    case 'phase_3_2': return SparklesIcon;
    case 'phase_3_3': return TagIcon;
    case 'phase_4': return DocumentTextIcon;
    case 'phase_5': return ChartBarIcon;
    default: return DocumentTextIcon;
  }
};

export const ComparisonView: React.FC<ComparisonViewProps> = ({
  comparison,
  onCopy: _onCopy,
  copiedText: _copiedText,
  className
}) => {
  const [selectedPhase, setSelectedPhase] = useState<string | null>(null);

  // Get phases that exist in both real and simulated results
  const commonPhases = comparison.realAI
    .filter(realPhase => 
      comparison.simulated.some(simPhase => simPhase.phase === realPhase.phase)
    )
    .map(phase => phase.phase);

  return (
    <div className={cn('space-y-6', className)}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-foreground">AI vs Simulated Comparison</h2>
          <p className="text-muted-foreground">
            Compare real AI processing results with simulated outputs
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-2 px-3 py-1 bg-green-100 text-green-800 rounded-full text-sm">
            <SparklesIcon className="h-4 w-4" />
            <span>Real AI</span>
          </div>
          <ArrowsRightLeftIcon className="h-4 w-4 text-muted-foreground" />
          <div className="flex items-center gap-2 px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm">
            <CpuChipIcon className="h-4 w-4" />
            <span>Simulated</span>
          </div>
        </div>
      </div>

      {/* Metrics Overview */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Real AI Metrics */}
        <GlassCard variant="secondary">
          <div className="p-6">
            <div className="flex items-center gap-2 mb-4">
              <SparklesIcon className="h-5 w-5 text-green-600" />
              <h3 className="text-lg font-semibold text-foreground">Real AI Performance</h3>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="text-center">
                <div className="text-2xl font-bold text-green-600">
                  {formatDuration(comparison.metrics.realAI.totalTime)}
                </div>
                <div className="text-sm text-muted-foreground">Total Time</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-green-600">
                  {formatDuration(comparison.metrics.realAI.averageTime)}
                </div>
                <div className="text-sm text-muted-foreground">Avg Time</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-green-600">
                  {(comparison.metrics.realAI.successRate * 100).toFixed(0)}%
                </div>
                <div className="text-sm text-muted-foreground">Success Rate</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-green-600">
                  {comparison.metrics.realAI.accuracy ? 
                    `${(comparison.metrics.realAI.accuracy * 100).toFixed(0)}%` : 'N/A'
                  }
                </div>
                <div className="text-sm text-muted-foreground">Accuracy</div>
              </div>
            </div>
          </div>
        </GlassCard>

        {/* Simulated Metrics */}
        <GlassCard variant="secondary">
          <div className="p-6">
            <div className="flex items-center gap-2 mb-4">
              <CpuChipIcon className="h-5 w-5 text-blue-600" />
              <h3 className="text-lg font-semibold text-foreground">Simulated Performance</h3>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="text-center">
                <div className="text-2xl font-bold text-blue-600">
                  {formatDuration(comparison.metrics.simulated.totalTime)}
                </div>
                <div className="text-sm text-muted-foreground">Total Time</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-blue-600">
                  {formatDuration(comparison.metrics.simulated.averageTime)}
                </div>
                <div className="text-sm text-muted-foreground">Avg Time</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-blue-600">
                  {(comparison.metrics.simulated.successRate * 100).toFixed(0)}%
                </div>
                <div className="text-sm text-muted-foreground">Success Rate</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-blue-600">
                  {comparison.metrics.simulated.accuracy ? 
                    `${(comparison.metrics.simulated.accuracy * 100).toFixed(0)}%` : 'N/A'
                  }
                </div>
                <div className="text-sm text-muted-foreground">Accuracy</div>
              </div>
            </div>
          </div>
        </GlassCard>
      </div>

      {/* Phase-by-Phase Comparison */}
      <GlassCard variant="primary">
        <div className="p-6">
          <div className="flex items-center gap-2 mb-4">
            <ArrowsRightLeftIcon className="h-5 w-5 text-primary" />
            <h3 className="text-lg font-semibold text-foreground">Phase-by-Phase Comparison</h3>
          </div>
          
          <div className="space-y-4">
            {commonPhases.map(phase => {
              const realPhase = comparison.realAI.find(p => p.phase === phase);
              const simulatedPhase = comparison.simulated.find(p => p.phase === phase);
              const PhaseIcon = getPhaseIcon(phase);
              
              if (!realPhase || !simulatedPhase) return null;
              
              return (
                <div key={phase} className="border border-white/10 rounded-lg p-4">
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-3">
                      <PhaseIcon className="h-5 w-5 text-primary" />
                      <div>
                        <div className="font-medium text-foreground">{realPhase.phaseName}</div>
                        <div className="text-sm text-muted-foreground">{phase}</div>
                      </div>
                    </div>
                    <LiquidButton
                      variant="ghost"
                      size="sm"
                      onClick={() => setSelectedPhase(selectedPhase === phase ? null : phase)}
                    >
                      {selectedPhase === phase ? 'Hide Details' : 'Show Details'}
                    </LiquidButton>
                  </div>
                  
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {/* Real AI Results */}
                    <div className="space-y-2">
                      <div className="flex items-center gap-2">
                        <SparklesIcon className="h-4 w-4 text-green-600" />
                        <span className="text-sm font-medium text-green-600">Real AI</span>
                        <StatusBadge status={realPhase.status} size="sm" />
                      </div>
                      <div className="text-xs text-muted-foreground space-y-1">
                        <div>Duration: {realPhase.duration ? formatDuration(realPhase.duration) : 'N/A'}</div>
                        <div>Model: {realPhase.aiModelUsed || 'N/A'}</div>
                      </div>
                    </div>
                    
                    {/* Simulated Results */}
                    <div className="space-y-2">
                      <div className="flex items-center gap-2">
                        <CpuChipIcon className="h-4 w-4 text-blue-600" />
                        <span className="text-sm font-medium text-blue-600">Simulated</span>
                        <StatusBadge status={simulatedPhase.status} size="sm" />
                      </div>
                      <div className="text-xs text-muted-foreground space-y-1">
                        <div>Duration: {simulatedPhase.duration ? formatDuration(simulatedPhase.duration) : 'N/A'}</div>
                        <div>Model: {simulatedPhase.aiModelUsed || 'Simulated'}</div>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </GlassCard>

      {/* Summary and Recommendations */}
      <GlassCard variant="tertiary">
        <div className="p-6">
          <div className="flex items-center gap-2 mb-4">
            <CheckCircleIcon className="h-5 w-5 text-primary" />
            <h3 className="text-lg font-semibold text-foreground">Summary & Recommendations</h3>
          </div>
          
          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Advantages */}
              <div className="space-y-3">
                <h4 className="font-medium text-green-600">Real AI Advantages</h4>
                <ul className="space-y-1 text-sm text-muted-foreground">
                  <li className="flex items-start gap-2">
                    <CheckCircleIcon className="h-4 w-4 text-green-500 mt-0.5 flex-shrink-0" />
                    <span>Higher accuracy and nuanced understanding</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <CheckCircleIcon className="h-4 w-4 text-green-500 mt-0.5 flex-shrink-0" />
                    <span>Better context awareness and reasoning</span>
                  </li>
                </ul>
              </div>
              
              <div className="space-y-3">
                <h4 className="font-medium text-blue-600">Simulated Advantages</h4>
                <ul className="space-y-1 text-sm text-muted-foreground">
                  <li className="flex items-start gap-2">
                    <CheckCircleIcon className="h-4 w-4 text-blue-500 mt-0.5 flex-shrink-0" />
                    <span>Faster processing times</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <CheckCircleIcon className="h-4 w-4 text-blue-500 mt-0.5 flex-shrink-0" />
                    <span>More predictable results</span>
                  </li>
                </ul>
              </div>
            </div>
            
            <div className="pt-4 border-t border-white/10">
              <h4 className="font-medium text-foreground mb-2">Recommendation</h4>
              <p className="text-sm text-muted-foreground">
                {comparison.metrics.realAI.successRate > comparison.metrics.simulated.successRate
                  ? "Real AI processing shows superior results and is recommended for production use when accuracy is critical."
                  : "Simulated processing offers good performance with faster execution times, suitable for high-volume scenarios."
                }
              </p>
            </div>
          </div>
        </div>
      </GlassCard>
    </div>
  );
};
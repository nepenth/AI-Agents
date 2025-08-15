import React, { useEffect, useState } from 'react';
import { Card, CardContent } from '../ui/Card';
import { ProgressIndicator } from './ProgressIndicator';
import { cn } from '../../utils/cn';

export interface PipelineVisualizerProps {
  phases: Array<{
    id: string;
    name: string;
    status: 'pending' | 'running' | 'completed' | 'failed';
    progress?: number;
    duration?: number;
    startTime?: Date;
    aiModelUsed?: string;
    isRealAI?: boolean;
  }>;
  currentPhase?: string;
  isProcessing: boolean;
  className?: string;
}

export const PipelineVisualizer: React.FC<PipelineVisualizerProps> = ({
  phases,
  currentPhase,
  isProcessing,
  className
}) => {
  const [animationPhase, setAnimationPhase] = useState(0);

  // Animate the pipeline flow
  useEffect(() => {
    if (isProcessing) {
      const interval = setInterval(() => {
        setAnimationPhase(prev => (prev + 1) % 4);
      }, 500);
      return () => clearInterval(interval);
    }
  }, [isProcessing]);

  const getPhasePosition = (index: number) => {
    const totalPhases = phases.length;
    const angle = (index / totalPhases) * 2 * Math.PI - Math.PI / 2; // Start from top
    const radius = 120;
    const centerX = 150;
    const centerY = 150;
    
    return {
      x: centerX + radius * Math.cos(angle),
      y: centerY + radius * Math.sin(angle)
    };
  };

  const getConnectionPath = (fromIndex: number, toIndex: number) => {
    const from = getPhasePosition(fromIndex);
    const to = getPhasePosition(toIndex);
    
    return `M ${from.x} ${from.y} L ${to.x} ${to.y}`;
  };

  const getPhaseColor = (status: string, isActive: boolean) => {
    if (isActive) return '#3B82F6'; // Blue for active
    
    switch (status) {
      case 'completed': return '#10B981'; // Green
      case 'failed': return '#EF4444'; // Red
      case 'running': return '#F59E0B'; // Yellow
      default: return '#9CA3AF'; // Gray
    }
  };

  const getPhaseIcon = (status: string, isRealAI?: boolean) => {
    switch (status) {
      case 'completed': return isRealAI ? '🤖' : '✅';
      case 'running': return '🔄';
      case 'failed': return '❌';
      default: return '⏳';
    }
  };

  return (
    <Card className={cn('p-6', className)}>
      <CardContent className="p-0">
        <div className="relative">
          {/* SVG Pipeline Visualization */}
          <svg width="300" height="300" className="mx-auto">
            {/* Background circle */}
            <circle
              cx="150"
              cy="150"
              r="120"
              fill="none"
              stroke="#E5E7EB"
              strokeWidth="2"
              strokeDasharray="5,5"
            />
            
            {/* Progress arc */}
            {isProcessing && (
              <circle
                cx="150"
                cy="150"
                r="120"
                fill="none"
                stroke="#3B82F6"
                strokeWidth="3"
                strokeDasharray={`${(phases.filter(p => p.status === 'completed').length / phases.length) * 754} 754`}
                strokeDashoffset="0"
                transform="rotate(-90 150 150)"
                className="transition-all duration-1000 ease-out"
              />
            )}

            {/* Connection lines */}
            {phases.map((_, index) => {
              const nextIndex = (index + 1) % phases.length;
              const isActive = phases[index].status === 'running' || phases[nextIndex].status === 'running';
              
              return (
                <path
                  key={`connection-${index}`}
                  d={getConnectionPath(index, nextIndex)}
                  stroke={isActive ? '#3B82F6' : '#E5E7EB'}
                  strokeWidth={isActive ? '3' : '1'}
                  strokeDasharray={isActive ? '5,5' : 'none'}
                  className={cn(
                    'transition-all duration-500',
                    isActive && 'animate-pulse'
                  )}
                />
              );
            })}

            {/* Phase nodes */}
            {phases.map((phase, index) => {
              const position = getPhasePosition(index);
              const isActive = phase.id === currentPhase;
              const color = getPhaseColor(phase.status, isActive);
              
              return (
                <g key={phase.id}>
                  {/* Outer ring for active phase */}
                  {isActive && (
                    <circle
                      cx={position.x}
                      cy={position.y}
                      r="25"
                      fill="none"
                      stroke={color}
                      strokeWidth="2"
                      opacity="0.5"
                      className="animate-ping"
                    />
                  )}
                  
                  {/* Main phase circle */}
                  <circle
                    cx={position.x}
                    cy={position.y}
                    r="20"
                    fill={color}
                    stroke="white"
                    strokeWidth="3"
                    className={cn(
                      'transition-all duration-300',
                      phase.status === 'running' && 'animate-pulse'
                    )}
                  />
                  
                  {/* Phase number */}
                  <text
                    x={position.x}
                    y={position.y + 5}
                    textAnchor="middle"
                    className="text-white text-sm font-bold"
                    fill="white"
                  >
                    {index + 1}
                  </text>
                  
                  {/* Phase label */}
                  <text
                    x={position.x}
                    y={position.y + 40}
                    textAnchor="middle"
                    className="text-xs font-medium fill-gray-700"
                    fill="#374151"
                  >
                    {phase.name.split(' ')[0]}
                  </text>
                </g>
              );
            })}

            {/* Center status */}
            <g>
              <circle
                cx="150"
                cy="150"
                r="40"
                fill={isProcessing ? '#3B82F6' : '#9CA3AF'}
                fillOpacity="0.1"
                stroke={isProcessing ? '#3B82F6' : '#9CA3AF'}
                strokeWidth="2"
                className={cn(
                  'transition-all duration-500',
                  isProcessing && 'animate-pulse'
                )}
              />
              <text
                x="150"
                y="145"
                textAnchor="middle"
                className="text-sm font-bold fill-gray-700"
                fill="#374151"
              >
                Pipeline
              </text>
              <text
                x="150"
                y="160"
                textAnchor="middle"
                className="text-xs fill-gray-500"
                fill="#6B7280"
              >
                {isProcessing ? 'Running' : 'Ready'}
              </text>
            </g>
          </svg>

          {/* Phase Details */}
          <div className="mt-6 space-y-3">
            {phases.map((phase, index) => (
              <div
                key={phase.id}
                className={cn(
                  'flex items-center gap-3 p-3 rounded-lg border transition-all duration-300',
                  {
                    'bg-blue-50 border-blue-200': phase.status === 'running',
                    'bg-green-50 border-green-200': phase.status === 'completed',
                    'bg-red-50 border-red-200': phase.status === 'failed',
                    'bg-gray-50 border-gray-200': phase.status === 'pending'
                  }
                )}
              >
                <div className={cn(
                  'w-8 h-8 rounded-full flex items-center justify-center text-white font-bold text-sm',
                  {
                    'bg-blue-500': phase.status === 'running',
                    'bg-green-500': phase.status === 'completed',
                    'bg-red-500': phase.status === 'failed',
                    'bg-gray-400': phase.status === 'pending'
                  }
                )}>
                  {index + 1}
                </div>
                
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{phase.name}</span>
                    <span className="text-lg">{getPhaseIcon(phase.status, phase.isRealAI)}</span>
                    {phase.aiModelUsed && (
                      <span className={cn(
                        'text-xs px-2 py-1 rounded-full',
                        phase.isRealAI 
                          ? 'bg-green-100 text-green-700'
                          : 'bg-yellow-100 text-yellow-700'
                      )}>
                        {phase.aiModelUsed}
                      </span>
                    )}
                  </div>
                  
                  {phase.status === 'running' && phase.progress !== undefined && (
                    <div className="mt-2">
                      <ProgressIndicator
                        value={phase.progress}
                        status={phase.status}
                        size="sm"
                        showPercentage={true}
                        showSpeedometer={true}
                        startTime={phase.startTime}
                        animated={true}
                      />
                    </div>
                  )}
                  
                  {phase.duration && (
                    <div className="text-xs text-gray-500 mt-1">
                      Duration: {phase.duration < 1000 ? `${phase.duration}ms` : `${(phase.duration / 1000).toFixed(1)}s`}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Processing Animation */}
          {isProcessing && (
            <div className="absolute top-4 right-4">
              <div className="flex items-center gap-2 text-blue-600">
                <div className="flex gap-1">
                  {[0, 1, 2].map((i) => (
                    <div
                      key={i}
                      className={cn(
                        'w-2 h-2 bg-blue-500 rounded-full animate-bounce',
                        i === 1 && 'animation-delay-100',
                        i === 2 && 'animation-delay-200'
                      )}
                    />
                  ))}
                </div>
                <span className="text-sm font-medium">Processing...</span>
              </div>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
};
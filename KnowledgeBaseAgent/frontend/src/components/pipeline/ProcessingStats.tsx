import React from 'react';
import { Card, CardContent } from '../ui/Card';
import { ProgressBar } from '../ui/ProgressBar';
import { cn } from '../../utils/cn';

export interface ProcessingStatsProps {
  stats: {
    totalPhases: number;
    completedPhases: number;
    failedPhases: number;
    totalDuration: number;
    startTime: Date | null;
    endTime: Date | null;
  };
  isProcessing: boolean;
  currentTaskId?: string | null;
}

export const ProcessingStats: React.FC<ProcessingStatsProps> = ({
  stats,
  isProcessing,
  currentTaskId
}) => {
  const formatDuration = (ms: number) => {
    if (ms < 1000) return `${ms}ms`;
    if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
    return `${(ms / 60000).toFixed(1)}m`;
  };

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString([], { 
      hour: '2-digit', 
      minute: '2-digit', 
      second: '2-digit' 
    });
  };

  const completionPercentage = (stats.completedPhases / stats.totalPhases) * 100;
  const failureRate = (stats.failedPhases / stats.totalPhases) * 100;
  const successRate = (stats.completedPhases / (stats.completedPhases + stats.failedPhases)) * 100;

  const getStatusColor = () => {
    if (stats.failedPhases > 0) return 'text-red-600';
    if (isProcessing) return 'text-blue-600';
    if (stats.completedPhases === stats.totalPhases) return 'text-green-600';
    return 'text-gray-600';
  };

  const getStatusText = () => {
    if (stats.failedPhases > 0 && !isProcessing) return 'Failed';
    if (isProcessing) return 'Processing';
    if (stats.completedPhases === stats.totalPhases) return 'Completed';
    return 'Pending';
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      {/* Total Phases */}
      <Card>
        <CardContent className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-2xl font-bold text-blue-600">{stats.totalPhases}</div>
              <div className="text-sm text-gray-600">Total Phases</div>
            </div>
            <div className="text-blue-500 opacity-60">
              📋
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Completed Phases */}
      <Card>
        <CardContent className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-2xl font-bold text-green-600">{stats.completedPhases}</div>
              <div className="text-sm text-gray-600">Completed</div>
              {stats.completedPhases > 0 && (
                <div className="text-xs text-green-500">
                  {completionPercentage.toFixed(0)}% done
                </div>
              )}
            </div>
            <div className="text-green-500 opacity-60">
              ✅
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Failed Phases */}
      <Card>
        <CardContent className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-2xl font-bold text-red-600">{stats.failedPhases}</div>
              <div className="text-sm text-gray-600">Failed</div>
              {stats.failedPhases > 0 && (
                <div className="text-xs text-red-500">
                  {failureRate.toFixed(0)}% failed
                </div>
              )}
            </div>
            <div className="text-red-500 opacity-60">
              ❌
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Duration */}
      <Card>
        <CardContent className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-2xl font-bold text-purple-600">
                {formatDuration(stats.totalDuration)}
              </div>
              <div className="text-sm text-gray-600">Duration</div>
              {stats.startTime && (
                <div className="text-xs text-gray-500">
                  {isProcessing ? 'Running' : 'Total time'}
                </div>
              )}
            </div>
            <div className="text-purple-500 opacity-60">
              ⏱️
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Overall Status Card */}
      <Card className="md:col-span-2 lg:col-span-4">
        <CardContent className="p-4">
          <div className="space-y-4">
            {/* Status Header */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className={cn('text-lg font-semibold', getStatusColor())}>
                  Pipeline Status: {getStatusText()}
                </div>
                {isProcessing && (
                  <div className="flex items-center gap-2 text-sm text-blue-600">
                    <div className="animate-spin w-4 h-4 border-2 border-blue-600 border-t-transparent rounded-full"></div>
                    Processing...
                  </div>
                )}
                {currentTaskId && (
                  <div className="text-xs text-gray-500 font-mono">
                    Task: {currentTaskId.substring(0, 8)}...
                  </div>
                )}
              </div>
              
              {/* Success Rate */}
              {(stats.completedPhases > 0 || stats.failedPhases > 0) && (
                <div className="text-right">
                  <div className={cn(
                    'text-lg font-semibold',
                    successRate >= 90 ? 'text-green-600' :
                    successRate >= 70 ? 'text-yellow-600' : 'text-red-600'
                  )}>
                    {isNaN(successRate) ? '0' : successRate.toFixed(0)}%
                  </div>
                  <div className="text-sm text-gray-600">Success Rate</div>
                </div>
              )}
            </div>

            {/* Progress Bar */}
            <div>
              <div className="flex justify-between text-sm mb-2">
                <span className="font-medium">Overall Progress</span>
                <span>{completionPercentage.toFixed(1)}%</span>
              </div>
              <ProgressBar
                value={completionPercentage}
                variant={stats.failedPhases > 0 ? 'error' : 'default'}
                size="lg"
                animated={isProcessing}
                striped={isProcessing}
              />
            </div>

            {/* Timing Information */}
            {stats.startTime && (
              <div className="flex justify-between text-sm text-gray-600 pt-2 border-t border-gray-200">
                <div className="flex items-center gap-4">
                  <span>Started: {formatTime(stats.startTime)}</span>
                  {stats.endTime && (
                    <span>Ended: {formatTime(stats.endTime)}</span>
                  )}
                </div>
                
                {/* Performance Indicator */}
                {stats.totalDuration > 0 && (
                  <div className="flex items-center gap-2">
                    <span>Performance:</span>
                    <span className={cn(
                      'font-medium',
                      stats.totalDuration < 30000 ? 'text-green-600' :
                      stats.totalDuration < 120000 ? 'text-yellow-600' : 'text-red-600'
                    )}>
                      {stats.totalDuration < 30000 ? 'Excellent' :
                       stats.totalDuration < 120000 ? 'Good' : 'Slow'}
                    </span>
                  </div>
                )}
              </div>
            )}

            {/* Processing Insights */}
            {!isProcessing && (stats.completedPhases > 0 || stats.failedPhases > 0) && (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2 border-t border-gray-200">
                <div className="text-center">
                  <div className="text-lg font-semibold text-blue-600">
                    {stats.totalDuration > 0 ? (stats.totalDuration / (stats.completedPhases + stats.failedPhases)).toFixed(0) : '0'}ms
                  </div>
                  <div className="text-xs text-gray-600">Avg per Phase</div>
                </div>
                <div className="text-center">
                  <div className="text-lg font-semibold text-green-600">
                    {stats.completedPhases > 0 ? (stats.totalDuration / stats.completedPhases).toFixed(0) : '0'}ms
                  </div>
                  <div className="text-xs text-gray-600">Avg Success Time</div>
                </div>
                <div className="text-center">
                  <div className={cn(
                    'text-lg font-semibold',
                    stats.failedPhases === 0 ? 'text-green-600' : 'text-red-600'
                  )}>
                    {stats.failedPhases === 0 ? '100%' : `${(100 - failureRate).toFixed(0)}%`}
                  </div>
                  <div className="text-xs text-gray-600">Reliability</div>
                </div>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
};
import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/Card';
import { Button } from '../ui/Button';
import { ProgressBar } from '../ui/ProgressBar';
import { WebSocketIndicator } from '../ui/WebSocketIndicator';
import { PhaseCard } from './PhaseCard';
import { ProcessingStats } from './ProcessingStats';
import { usePipeline } from '../../hooks/usePipeline';
import { cn } from '../../utils/cn';

export const PipelineDashboard: React.FC = () => {
  const [tweetId, setTweetId] = useState('');

  const {
    phases,
    currentTaskId,
    isProcessing,
    tweetData,
    error,
    processingStats,
    isConnected,
    connectionState,
    startProcessing,
    cancelProcessing,
    retryPhase,
    resetPipeline,
    completionPercentage
  } = usePipeline({
    onPhaseComplete: (phase) => {
      console.log(`Phase ${phase.name} completed`);
    },
    onPipelineComplete: (phases) => {
      console.log('Pipeline completed successfully');
    },
    onError: (error) => {
      console.error('Pipeline error:', error);
    }
  });

  const handleStartProcessing = async () => {
    if (!tweetId.trim()) {
      return;
    }
    await startProcessing(tweetId);
  };

  const handleRetryPhase = async (phaseId: string) => {
    await retryPhase(phaseId);
  };

  const handleViewPhaseDetails = (phaseId: string) => {
    // TODO: Implement phase details modal
    console.log('View details for phase:', phaseId);
  };

  return (
    <div className="space-y-6">
      {/* Header with Connection Status */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Seven-Phase Pipeline</h1>
          <p className="text-gray-600 mt-1">AI-powered tweet processing and knowledge base generation</p>
        </div>
        <div className="flex items-center gap-4">
          <WebSocketIndicator 
            status={connectionState as any}
            size="md"
          />
          <div className="text-right">
            <div className="text-2xl font-bold text-blue-600">{completionPercentage.toFixed(0)}%</div>
            <div className="text-sm text-gray-500">Complete</div>
          </div>
        </div>
      </div>

      {/* Processing Stats */}
      <ProcessingStats 
        stats={processingStats}
        isProcessing={isProcessing}
        currentTaskId={currentTaskId}
      />

      {/* Tweet Input */}
      <Card>
        <CardHeader>
          <CardTitle>Process Tweet</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="flex gap-4">
              <input
                type="text"
                value={tweetId}
                onChange={(e) => setTweetId(e.target.value)}
                placeholder="Enter tweet ID or URL (e.g., 1955505151680319929 or https://twitter.com/user/status/123...)"
                className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                disabled={isProcessing}
              />
              <Button 
                onClick={handleStartProcessing} 
                disabled={isProcessing || !tweetId.trim()}
                loading={isProcessing && !currentTaskId}
                className="px-6"
              >
                {isProcessing ? 'Processing...' : 'Start Pipeline'}
              </Button>
              {isProcessing && currentTaskId && (
                <Button 
                  onClick={cancelProcessing}
                  variant="outline"
                  className="px-6"
                >
                  Cancel
                </Button>
              )}
              <Button 
                onClick={resetPipeline} 
                variant="outline"
                disabled={isProcessing}
              >
                Reset
              </Button>
            </div>
            
            {error && (
              <div className="text-red-600 text-sm bg-red-50 p-3 rounded border border-red-200">
                <strong>Error:</strong> {error}
              </div>
            )}

            {tweetData && (
              <div className="bg-blue-50 p-4 rounded border border-blue-200">
                <div className="text-sm font-medium text-blue-800 mb-2">Tweet Data Loaded:</div>
                <div className="text-sm text-blue-700">
                  <strong>@{tweetData.author.username}:</strong> {tweetData.text.substring(0, 150)}
                  {tweetData.text.length > 150 && '...'}
                </div>
                <div className="text-xs text-blue-600 mt-1">
                  Engagement: {Object.values(tweetData.publicMetrics).reduce((a: number, b: number) => a + b, 0)} total
                  {tweetData.media && ` • ${tweetData.media.length} media items`}
                </div>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Pipeline Phases */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {phases.map((phase, index) => (
          <PhaseCard
            key={phase.id}
            phase={phase}
            index={index}
            onRetry={handleRetryPhase}
            onViewDetails={handleViewPhaseDetails}
          />
        ))}
      </div>

      {/* Overall Progress Bar */}
      <Card>
        <CardContent className="p-4">
          <div className="flex justify-between text-sm mb-2">
            <span className="font-medium">Overall Pipeline Progress</span>
            <span>{completionPercentage.toFixed(1)}%</span>
          </div>
          <ProgressBar
            value={completionPercentage}
            variant={processingStats.failedPhases > 0 ? 'error' : 'default'}
            size="lg"
            animated={isProcessing}
            striped={isProcessing}
          />
          {processingStats.startTime && (
            <div className="flex justify-between text-xs text-gray-500 mt-2">
              <span>Started: {processingStats.startTime.toLocaleTimeString()}</span>
              {processingStats.endTime && (
                <span>Ended: {processingStats.endTime.toLocaleTimeString()}</span>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};
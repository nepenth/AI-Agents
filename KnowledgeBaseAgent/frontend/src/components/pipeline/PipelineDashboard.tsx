import React, { useState } from 'react';
import { GlassCard } from '../ui/GlassCard';
import { LiquidButton } from '../ui/LiquidButton';
import { ProgressBar } from '../ui/ProgressBar';
import { WebSocketIndicator } from '../ui/WebSocketIndicator';
import { PhaseCard } from './PhaseCard';
import { ProcessingStats } from './ProcessingStats';
import { usePipeline } from '../../hooks/usePipeline';
import { useAgentStore } from '@/stores/agentStore';
import { Play, Square, Pause, RotateCcw, Settings, History, Download } from 'lucide-react';
import { cn } from '../../utils/cn';

export const PipelineDashboard: React.FC = () => {
  const [config, setConfig] = useState({
    sources: {
      twitter_enabled: true,
      web_scraping_enabled: true,
      file_upload_enabled: true,
    },
    processing: {
      ai_backend: 'openai',
      model: 'gpt-4',
      batch_size: 10,
    },
    categories: ['general', 'technology', 'science'],
  });
  const [showHistory, setShowHistory] = useState(false);
  const [showSettings, setShowSettings] = useState(false);

  const {
    startAgent,
    stopAgent,
    pauseAgent,
    resumeAgent,
    isRunning,
    currentPhase,
    progress,
    executionHistory
  } = useAgentStore();

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

  const handleStartPipeline = async () => {
    await startAgent(config);
  };

  const handleStopPipeline = async () => {
    await stopAgent();
  };

  const handlePausePipeline = async () => {
    await pauseAgent();
  };

  const handleResumePipeline = async () => {
    await resumeAgent();
  };

  const handleRetryPhase = async (phaseId: string) => {
    await retryPhase(phaseId);
  };

  const handleViewPhaseDetails = (phaseId: string) => {
    // TODO: Implement phase details modal
    console.log('View details for phase:', phaseId);
  };

  const handleExportResults = () => {
    // TODO: Implement results export
    console.log('Export results');
  };

  return (
    <div className="space-y-6 p-6">
      {/* Header with Connection Status */}
      <GlassCard variant="primary" className="p-6">
        <div className="flex justify-between items-center relative z-10">
          <div>
            <h1 className="text-3xl font-bold text-foreground mb-2">Seven-Phase Pipeline</h1>
            <p className="text-muted-foreground">AI-powered Twitter/X bookmark processing and knowledge base generation</p>
          </div>
          <div className="flex items-center gap-6">
            <WebSocketIndicator
              status={connectionState as any}
              size="md"
            />
            <div className="text-right">
              <div className="text-3xl font-bold text-primary">{Math.round(progress)}%</div>
              <div className="text-sm text-muted-foreground">Complete</div>
            </div>
          </div>
        </div>
      </GlassCard>

      {/* Pipeline Controls */}
      <GlassCard variant="secondary" className="p-6">
        <div className="relative z-10">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-xl font-semibold text-foreground">Pipeline Controls</h3>
            <div className="flex items-center gap-2">
              <LiquidButton
                variant="ghost"
                size="sm"
                onClick={() => setShowHistory(!showHistory)}
              >
                <History className="h-4 w-4 mr-2" />
                History
              </LiquidButton>
              <LiquidButton
                variant="ghost"
                size="sm"
                onClick={() => setShowSettings(!showSettings)}
              >
                <Settings className="h-4 w-4 mr-2" />
                Settings
              </LiquidButton>
              <LiquidButton
                variant="ghost"
                size="sm"
                onClick={handleExportResults}
                disabled={!isRunning && progress === 0}
              >
                <Download className="h-4 w-4 mr-2" />
                Export
              </LiquidButton>
            </div>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <LiquidButton
              variant="primary"
              onClick={handleStartPipeline}
              disabled={isRunning}
              className="flex flex-col items-center gap-2 h-auto py-4"
              elevated
            >
              <Play className="h-6 w-6" />
              <span>Start Pipeline</span>
            </LiquidButton>

            <LiquidButton
              variant="secondary"
              onClick={handleStopPipeline}
              disabled={!isRunning}
              className="flex flex-col items-center gap-2 h-auto py-4"
              elevated
            >
              <Square className="h-6 w-6" />
              <span>Stop</span>
            </LiquidButton>

            <LiquidButton
              variant="outline"
              onClick={handlePausePipeline}
              disabled={!isRunning || currentPhase === 'Paused'}
              className="flex flex-col items-center gap-2 h-auto py-4"
              elevated
            >
              <Pause className="h-6 w-6" />
              <span>Pause</span>
            </LiquidButton>

            <LiquidButton
              variant="outline"
              onClick={handleResumePipeline}
              disabled={!isRunning || currentPhase !== 'Paused'}
              className="flex flex-col items-center gap-2 h-auto py-4"
              elevated
            >
              <RotateCcw className="h-6 w-6" />
              <span>Resume</span>
            </LiquidButton>
          </div>

          {error && (
            <div className="mt-4 p-4 bg-red-500/10 border border-red-500/20 rounded-xl backdrop-blur-sm">
              <div className="text-red-600 text-sm">
                <strong>Error:</strong> {error}
              </div>
            </div>
          )}

          {currentPhase && (
            <div className="mt-4 p-4 bg-primary/10 border border-primary/20 rounded-xl backdrop-blur-sm">
              <div className="text-primary text-sm">
                <strong>Current Phase:</strong> {currentPhase}
              </div>
            </div>
          )}
        </div>
      </GlassCard>

      {/* Processing Stats */}
      <ProcessingStats
        stats={processingStats}
        isProcessing={isRunning}
        currentTaskId={currentTaskId}
      />

      {/* Pipeline Phases */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
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
      <GlassCard variant="primary" className="p-6">
        <div className="relative z-10">
          <div className="flex justify-between items-center mb-4">
            <h3 className="text-lg font-semibold text-foreground">Overall Pipeline Progress</h3>
            <span className="text-2xl font-bold text-primary">{Math.round(progress)}%</span>
          </div>
          <ProgressBar
            value={progress}
            variant={processingStats?.failedPhases > 0 ? 'error' : 'default'}
            size="lg"
            animated={isRunning}
            striped={isRunning}
            className="mb-4"
          />
          {processingStats?.startTime && (
            <div className="flex justify-between text-sm text-muted-foreground">
              <span>Started: {processingStats.startTime.toLocaleTimeString()}</span>
              {processingStats.endTime && (
                <span>Ended: {processingStats.endTime.toLocaleTimeString()}</span>
              )}
            </div>
          )}
        </div>
      </GlassCard>

      {/* Execution History */}
      {showHistory && executionHistory.length > 0 && (
        <GlassCard variant="tertiary" className="p-6">
          <div className="relative z-10">
            <h3 className="text-lg font-semibold text-foreground mb-4">Execution History</h3>
            <div className="space-y-3">
              {executionHistory.slice(0, 5).map((execution, index) => (
                <div key={index} className="flex items-center justify-between p-3 bg-glass-secondary rounded-lg border border-glass-border-secondary backdrop-blur-sm">
                  <div>
                    <div className="text-sm font-medium text-foreground">
                      {execution.startTime?.toLocaleDateString()} {execution.startTime?.toLocaleTimeString()}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      Duration: {execution.duration ? `${Math.round(execution.duration / 1000)}s` : 'In progress'}
                    </div>
                  </div>
                  <div className={cn(
                    'px-2 py-1 rounded-full text-xs font-medium',
                    execution.status === 'completed' ? 'bg-green-500/20 text-green-600' :
                      execution.status === 'failed' ? 'bg-red-500/20 text-red-600' :
                        'bg-blue-500/20 text-blue-600'
                  )}>
                    {execution.status}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </GlassCard>
      )}
    </div>
  );
};
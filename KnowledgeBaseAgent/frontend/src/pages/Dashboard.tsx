import * as React from 'react';
import { PlayIcon, StopIcon, PauseIcon, ArrowPathIcon } from '@heroicons/react/24/solid';
import { CheckCircleIcon, XCircleIcon, ArrowPathIcon as OutlineArrowPathIcon } from '@heroicons/react/24/outline';
import { useAgentStore } from '@/stores';
import { GlassCard } from '@/components/ui/GlassCard';
import { Button } from '@/components/ui/Button';
import { ProgressBar } from '@/components/ui/ProgressBar';
import { cn } from '@/utils/cn';

const SEVEN_PHASES = [
  'Initialization',
  'Fetch Bookmarks',
  'Content Processing',
  'Synthesis Generation',
  'Embedding Generation',
  'README Generation',
  'Git Sync',
];

type PhaseStatus = 'pending' | 'running' | 'completed' | 'failed';

function getPhaseStatus(phaseName: string, currentPhase: string, isRunning: boolean, progress: number): PhaseStatus {
  const currentIndex = SEVEN_PHASES.indexOf(currentPhase);
  const phaseIndex = SEVEN_PHASES.indexOf(phaseName);

  if (currentIndex === -1 && !isRunning && progress === 100) return 'completed';
  if (currentIndex === -1 && !isRunning && progress === 0) return 'pending';

  if (phaseIndex < currentIndex) return 'completed';
  if (phaseIndex === currentIndex && isRunning) return 'running';
  if (phaseIndex === currentIndex && !isRunning) return 'failed'; // Assuming if it's not running on the current phase, it failed or was stopped.
  return 'pending';
}

function PhaseDisplay({ phaseName, status }: { phaseName: string; status: PhaseStatus }) {
  const statusConfig = {
    pending: { Icon: null, color: 'text-muted-foreground', label: 'Pending' },
    running: { Icon: OutlineArrowPathIcon, color: 'text-primary animate-spin', label: 'Running' },
    completed: { Icon: CheckCircleIcon, color: 'text-green-500', label: 'Completed' },
    failed: { Icon: XCircleIcon, color: 'text-destructive', label: 'Failed' },
  };

  const { Icon, color, label } = statusConfig[status];

  return (
    <div className="flex items-center gap-4 p-3 rounded-lg transition-all bg-white/5 hover:bg-white/10">
      <div className={cn("flex-shrink-0 h-8 w-8 flex items-center justify-center rounded-full",
        status === 'running' && 'bg-primary/10',
        status === 'completed' && 'bg-green-500/10',
        status === 'failed' && 'bg-destructive/10',
        status === 'pending' && 'bg-gray-500/10'
      )}>
        {Icon ? <Icon className={cn('h-5 w-5', color)} /> : <div className="h-5 w-5" />}
      </div>
      <div className="flex-1">
        <p className="font-medium text-foreground">{phaseName}</p>
        <p className={cn("text-sm", color)}>{label}</p>
      </div>
    </div>
  );
}

function PipelineControls() {
  const { startAgent, stopAgent, pauseAgent, resumeAgent, isRunning, currentPhase } = useAgentStore();

  const handleStart = () => {
    // TODO: Open modal to get config
    startAgent({ config: {} });
  };

  return (
    <div className="flex items-center gap-2">
      <Button onClick={handleStart} disabled={isRunning}>
        <PlayIcon className="h-5 w-5 mr-2" />
        Start New Run
      </Button>
      <Button onClick={() => stopAgent()} variant="destructive" disabled={!isRunning}>
        <StopIcon className="h-5 w-5 mr-2" />
        Stop
      </Button>
      <Button onClick={() => pauseAgent()} variant="secondary" disabled={!isRunning || currentPhase === 'Paused'}>
        <PauseIcon className="h-5 w-5 mr-2" />
        Pause
      </Button>
      <Button onClick={() => resumeAgent()} variant="secondary" disabled={!isRunning || currentPhase !== 'Paused'}>
        <ArrowPathIcon className="h-5 w-5 mr-2" />
        Resume
      </Button>
    </div>
  );
}

function PipelineStatus() {
  const { isRunning, currentPhase, progress } = useAgentStore();

  return (
    <GlassCard>
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-lg font-semibold text-foreground">Pipeline Status</h3>
        <span className={cn(
          "text-sm font-medium px-2 py-1 rounded-full",
          isRunning ? "bg-green-500/20 text-green-500" : "bg-gray-500/20 text-muted-foreground"
        )}>
          {isRunning ? 'RUNNING' : 'IDLE'}
        </span>
      </div>
      <div className="space-y-2">
        {SEVEN_PHASES.map((phase) => (
          <PhaseDisplay
            key={phase}
            phaseName={phase}
            status={getPhaseStatus(phase, currentPhase, isRunning, progress)}
          />
        ))}
      </div>
      <div className="mt-6">
        <div className="flex justify-between text-sm text-muted-foreground mb-1">
          <span>Overall Progress</span>
          <span>{Math.round(progress)}%</span>
        </div>
        <ProgressBar value={progress} />
      </div>
    </GlassCard>
  );
}

export function Dashboard() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-foreground">Dashboard</h2>
        <p className="text-muted-foreground">
          Control the AI agent and monitor its progress.
        </p>
      </div>

      <GlassCard>
        <h3 className="text-lg font-semibold text-foreground mb-4">Agent Controls</h3>
        <PipelineControls />
      </GlassCard>

      <PipelineStatus />
    </div>
  );
}

import * as React from 'react';
import { Play, Square, Pause, RotateCcw, CheckCircle, XCircle, Loader2 } from 'lucide-react';
import { useAgentStore } from '@/stores';
import { GlassPanel } from '@/components/ui/GlassPanel';
import { LiquidButton } from '@/components/ui/LiquidButton';
import { ProgressBar } from '@/components/ui/ProgressBar';
import { ResponsiveGrid, ResponsiveStack } from '@/components/ui/ResponsiveGrid';
import { PageLayout, PageHeader, PageSection } from '@/components/layout/PageLayout';
import { useResponsive } from '@/hooks/useResponsive';
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
  const { isMobile } = useResponsive();
  
  const statusConfig = {
    pending: { Icon: null, color: 'text-muted-foreground', label: 'Pending' },
    running: { Icon: Loader2, color: 'text-primary animate-spin', label: 'Running' },
    completed: { Icon: CheckCircle, color: 'text-green-500', label: 'Completed' },
    failed: { Icon: XCircle, color: 'text-destructive', label: 'Failed' },
  };

  const { Icon, color, label } = statusConfig[status];

  return (
    <GlassPanel 
      variant={status === 'running' ? 'interactive' : 'tertiary'}
      size={isMobile ? 'lg' : 'md'}
      elevated={status === 'running'}
      className={cn(
        "flex items-center gap-3",
        "touch-manipulation cursor-pointer", // Better touch targets on mobile
        status === 'running' && 'hover:scale-105'
      )}
    >
      <div className={cn(
        "flex-shrink-0 flex items-center justify-center rounded-full relative z-10",
        isMobile ? "h-10 w-10" : "h-8 w-8",
        status === 'running' && 'bg-primary/15 shadow-glass-tertiary',
        status === 'completed' && 'bg-green-500/15 shadow-glass-tertiary',
        status === 'failed' && 'bg-destructive/15 shadow-glass-tertiary',
        status === 'pending' && 'bg-muted/10'
      )}>
        {Icon ? (
          <Icon className={cn(
            color,
            isMobile ? 'h-6 w-6' : 'h-5 w-5'
          )} />
        ) : (
          <div className={isMobile ? "h-6 w-6" : "h-5 w-5"} />
        )}
      </div>
      <div className="flex-1 min-w-0 relative z-10">
        <p className={cn(
          "font-medium text-foreground truncate",
          isMobile ? "text-base" : "text-sm"
        )}>
          {phaseName}
        </p>
        <p className={cn(
          color,
          isMobile ? "text-sm" : "text-xs"
        )}>
          {label}
        </p>
      </div>
    </GlassPanel>
  );
}

function PipelineControls() {
  const { startAgent, stopAgent, pauseAgent, resumeAgent, isRunning, currentPhase } = useAgentStore();
  const { isMobile } = useResponsive();

  const handleStart = () => {
    // TODO: Open modal to get config
    const defaultConfig = {
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
    };
    startAgent(defaultConfig);
  };

  const controls = [
    {
      label: isMobile ? 'Start' : 'Start New Run',
      icon: Play,
      onClick: handleStart,
      disabled: isRunning,
      variant: 'interactive' as const
    },
    {
      label: 'Stop',
      icon: Square,
      onClick: () => stopAgent(),
      disabled: !isRunning,
      variant: 'secondary' as const
    },
    {
      label: 'Pause',
      icon: Pause,
      onClick: () => pauseAgent(),
      disabled: !isRunning || currentPhase === 'Paused',
      variant: 'outline' as const
    },
    {
      label: 'Resume',
      icon: RotateCcw,
      onClick: () => resumeAgent(),
      disabled: !isRunning || currentPhase !== 'Paused',
      variant: 'outline' as const
    }
  ];

  if (isMobile) {
    return (
      <ResponsiveGrid cols={{ xs: 2, sm: 4 }} gap={{ xs: 2, sm: 3 }}>
        {controls.map((control) => (
          <LiquidButton
            key={control.label}
            onClick={control.onClick}
            disabled={control.disabled}
            variant={control.variant}
            size="sm"
            elevated
            className="flex flex-col items-center gap-1 h-auto py-3"
          >
            <control.icon className="h-4 w-4" />
            <span className="text-xs">{control.label}</span>
          </LiquidButton>
        ))}
      </ResponsiveGrid>
    );
  }

  return (
    <ResponsiveStack 
      direction={{ xs: 'col', sm: 'row' }} 
      gap={{ xs: 2, sm: 3 }}
      className="flex-wrap"
    >
      {controls.map((control) => (
        <LiquidButton
          key={control.label}
          onClick={control.onClick}
          disabled={control.disabled}
          variant={control.variant}
          size={isMobile ? 'sm' : 'default'}
          elevated
        >
          <control.icon className="h-4 w-4 mr-2" />
          {control.label}
        </LiquidButton>
      ))}
    </ResponsiveStack>
  );
}

function PipelineStatus() {
  const { isRunning, currentPhase, progress } = useAgentStore();
  const { isMobile } = useResponsive();

  return (
    <GlassPanel variant="primary" className={cn("p-6", isMobile && "p-4")}>
      <div className="flex justify-between items-center mb-4">
        <h3 className={cn(
          "font-semibold text-foreground",
          isMobile ? "text-base" : "text-lg"
        )}>
          Pipeline Status
        </h3>
        <span className={cn(
          "font-medium px-3 py-1 rounded-full text-xs",
          isRunning ? "bg-green-500/20 text-green-500" : "bg-muted text-muted-foreground"
        )}>
          {isRunning ? 'RUNNING' : 'IDLE'}
        </span>
      </div>
      
      <div className={cn(
        "space-y-2",
        isMobile && "space-y-3"
      )}>
        {SEVEN_PHASES.map((phase) => (
          <PhaseDisplay
            key={phase}
            phaseName={phase}
            status={getPhaseStatus(phase, currentPhase, isRunning, progress)}
          />
        ))}
      </div>
      
      <div className={cn(
        "mt-6 pt-4 border-t border-border",
        isMobile && "mt-8"
      )}>
        <div className="flex justify-between text-sm text-muted-foreground mb-2">
          <span>Overall Progress</span>
          <span className="font-medium">{Math.round(progress)}%</span>
        </div>
        <ProgressBar 
          value={progress} 
          className={cn(isMobile && "h-3")}
        />
      </div>
    </GlassPanel>
  );
}

export function Dashboard() {
  return (
    <PageLayout>
      <PageHeader
        title="Dashboard"
        description="Control the AI agent and monitor its progress."
      />
      
      <PageSection>
        <GlassPanel variant="secondary" className="p-6">
          <h3 className="font-semibold text-foreground mb-4 text-lg">
            Agent Controls
          </h3>
          <PipelineControls />
        </GlassPanel>
      </PageSection>

      <PageSection>
        <PipelineStatus />
      </PageSection>
    </PageLayout>
  );
}

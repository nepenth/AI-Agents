import * as React from 'react';
import { useAgentStore } from '@/stores';
import { GlassPanel } from '@/components/ui/GlassPanel';
import { ProgressBar } from '@/components/ui/ProgressBar';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { cn } from '@/utils/cn';

function ResourceMonitor() {
  const { systemMetrics, loadSystemMetrics } = useAgentStore();

  React.useEffect(() => {
    const interval = setInterval(() => {
      loadSystemMetrics();
    }, 5000); // Refresh every 5 seconds

    loadSystemMetrics(); // Initial load

    return () => clearInterval(interval);
  }, [loadSystemMetrics]);

  if (!systemMetrics) {
    return <LoadingSpinner />;
  }

  const resources = [
    { name: 'CPU Usage', value: systemMetrics.cpu_usage, color: 'bg-blue-500' },
    { name: 'Memory Usage', value: systemMetrics.memory_usage, color: 'bg-green-500' },
    { name: 'Disk Usage', value: systemMetrics.disk_usage, color: 'bg-yellow-500' },
  ];

  return (
    <GlassPanel variant="primary" className="p-6">
      <h3 className="text-lg font-semibold text-foreground mb-4">System Resources</h3>
      <div className="space-y-4">
        {resources.map((res) => (
          <div key={res.name}>
            <div className="flex justify-between text-sm text-muted-foreground mb-1">
              <span>{res.name}</span>
              <span>{Math.round(res.value * 100)}%</span>
            </div>
            <ProgressBar value={res.value * 100} className={res.color} />
          </div>
        ))}
      </div>
    </GlassPanel>
  );
}

function LogViewer() {
  const { systemLogs, systemLogsLoading, loadSystemLogs } = useAgentStore();

  React.useEffect(() => {
    loadSystemLogs();
  }, [loadSystemLogs]);

  const getLevelColor = (level: string) => {
    switch (level.toUpperCase()) {
      case 'INFO': return 'text-blue-400';
      case 'WARNING': return 'text-yellow-400';
      case 'ERROR': return 'text-destructive';
      default: return 'text-muted-foreground';
    }
  }

  return (
    <GlassPanel variant="secondary" className="p-6">
      <h3 className="text-lg font-semibold text-foreground mb-4">System Logs</h3>
      <div className="h-96 overflow-y-auto bg-black/20 rounded-md p-4 font-mono text-xs">
        {systemLogsLoading && <LoadingSpinner />}
        {systemLogs.map((log, i) => (
          <div key={i} className="flex gap-3">
            <span className="text-muted-foreground/80">{new Date(log.timestamp).toLocaleTimeString()}</span>
            <span className={cn("font-bold", getLevelColor(log.level))}>{log.level.toUpperCase()}</span>
            <span className="text-foreground/90 flex-1">{log.message}</span>
          </div>
        ))}
      </div>
    </GlassPanel>
  );
}

import { GPUStats } from '@/components/monitoring/GPUStats';

export function Monitoring() {
  return (
    <div className="container mx-auto px-4 py-4 sm:px-6 sm:py-6 lg:px-8 lg:py-8">
      <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-foreground">System Monitoring</h2>
        <p className="text-muted-foreground">
          Live metrics and logs for the AI agent system.
        </p>
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        <ResourceMonitor />
        <GPUStats />
      </div>
      <LogViewer />
      </div>
    </div>
  );
}

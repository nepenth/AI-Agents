import { GlassCard } from '@/components/ui/GlassCard';

export function Monitoring() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-medium text-gray-900">Monitoring</h2>
        <p className="text-sm text-gray-600">Monitor system performance and task execution</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <GlassCard title="Logs">
          <div className="text-sm text-gray-700">Live logs stream.</div>
        </GlassCard>
        <GlassCard title="Metrics">
          <div className="text-sm text-gray-700">Charts and resource usage.</div>
        </GlassCard>
      </div>
    </div>
  );
}
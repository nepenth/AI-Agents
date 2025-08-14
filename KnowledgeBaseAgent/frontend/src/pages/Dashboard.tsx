import { useEffect } from 'react';
import { ChartBarIcon, CpuChipIcon } from '@heroicons/react/24/outline';
import { useAgentStore } from '@/stores';

interface StatCardProps {
  title: string;
  value: string | number;
  icon: React.ComponentType<{ className?: string }>;
  change?: string;
  changeType?: 'positive' | 'negative' | 'neutral';
}

function StatCard({ title, value, icon: Icon, change, changeType = 'neutral' }: StatCardProps) {
  const changeColors = {
    positive: 'text-green-600',
    negative: 'text-red-600',
    neutral: 'text-gray-600',
  };

  return (
    <div className="card p-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-gray-600">{title}</p>
          <p className="text-2xl font-semibold text-gray-900">{value}</p>
          {change && (
            <p className={`text-sm ${changeColors[changeType]}`}>
              {change}
            </p>
          )}
        </div>
        <div className="p-3 bg-primary-50 rounded-full">
          <Icon className="w-6 h-6 text-primary-600" />
        </div>
      </div>
    </div>
  );
}

export function Dashboard() {
  const { systemMetrics: metrics, loadSystemMetrics } = useAgentStore();

  useEffect(() => {
    loadSystemMetrics();
  }, []);

  if (!metrics) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-medium text-gray-900">System Overview</h2>
        <p className="text-sm text-gray-600">
          Monitor your AI agent's performance and activity
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <StatCard
          title="Active Tasks"
          value={metrics?.active_tasks || 0}
          icon={CpuChipIcon}
        />
        <StatCard
          title="Queue Size"
          value={metrics?.queue_size || 0}
          icon={ChartBarIcon}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="card p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-4">System Resources</h3>
          <div className="space-y-4">
            <div>
              <div className="flex justify-between text-sm">
                <span>CPU Usage</span>
                <span>{Math.round((metrics?.cpu_usage || 0) * 100)}%</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2 mt-1">
                <div 
                  className="bg-primary-600 h-2 rounded-full transition-all duration-300"
                  style={{ width: `${(metrics?.cpu_usage || 0) * 100}%` }}
                ></div>
              </div>
            </div>
            <div>
              <div className="flex justify-between text-sm">
                <span>Memory Usage</span>
                <span>{Math.round((metrics?.memory_usage || 0) * 100)}%</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2 mt-1">
                <div 
                  className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                  style={{ width: `${(metrics?.memory_usage || 0) * 100}%` }}
                ></div>
              </div>
            </div>
            <div>
              <div className="flex justify-between text-sm">
                <span>Disk Usage</span>
                <span>{Math.round((metrics?.disk_usage || 0) * 100)}%</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2 mt-1">
                <div 
                  className="bg-green-600 h-2 rounded-full transition-all duration-300"
                  style={{ width: `${(metrics?.disk_usage || 0) * 100}%` }}
                ></div>
              </div>
            </div>
          </div>
        </div>

        <div className="card p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Recent Activity</h3>
          <div className="text-sm text-gray-600">No recent activity yet.</div>
        </div>
      </div>
    </div>
  );
}
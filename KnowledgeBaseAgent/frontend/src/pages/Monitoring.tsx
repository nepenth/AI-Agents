import * as React from 'react';
import { useAgentStore } from '@/stores';
import { GlassPanel } from '@/components/ui/GlassPanel';
import { ProgressBar } from '@/components/ui/ProgressBar';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { cn } from '@/utils/cn';
import { 
  Gauge, 
  Zap, 
  MemoryStick, 
  Thermometer, 
  Activity, 
  HardDrive, 
  Wifi, 
  RefreshCw,
  TrendingUp,
  AlertTriangle,
  CheckCircle,
  Cpu
} from 'lucide-react';

function ResourceMonitor() {
  const { systemMetrics, loadSystemMetrics } = useAgentStore();
  const [isRefreshing, setIsRefreshing] = React.useState(false);

  const refreshMetrics = async () => {
    setIsRefreshing(true);
    await loadSystemMetrics();
    setTimeout(() => setIsRefreshing(false), 500);
  };

  React.useEffect(() => {
    const interval = setInterval(() => {
      loadSystemMetrics();
    }, 3000); // Refresh every 3 seconds for more responsive monitoring

    loadSystemMetrics(); // Initial load

    return () => clearInterval(interval);
  }, [loadSystemMetrics]);

  if (!systemMetrics) {
    return (
      <GlassPanel variant="primary" className="p-6 h-64">
        <div className="flex items-center justify-center h-full">
          <LoadingSpinner />
        </div>
      </GlassPanel>
    );
  }

  const getUsageColor = (value: number) => {
    if (value > 80) return 'text-red-500';
    if (value > 60) return 'text-yellow-500';
    return 'text-green-500';
  };

  const getUsageBarColor = (value: number) => {
    if (value > 80) return 'bg-gradient-to-r from-red-500 to-red-600';
    if (value > 60) return 'bg-gradient-to-r from-yellow-500 to-orange-500';
    return 'bg-gradient-to-r from-green-500 to-blue-500';
  };

  // Extract values from either new or legacy format
  const getCpuUsage = () => {
    if (systemMetrics.cpu?.usage_percent !== undefined) {
      return systemMetrics.cpu.usage_percent;
    }
    if (systemMetrics.cpu_usage !== undefined) {
      return systemMetrics.cpu_usage;
    }
    return 0;
  };

  const getMemoryUsage = () => {
    if (systemMetrics.memory?.usage_percent !== undefined) {
      return systemMetrics.memory.usage_percent;
    }
    if (systemMetrics.memory_usage !== undefined) {
      return systemMetrics.memory_usage * 100;
    }
    return 0;
  };

  const getDiskUsage = () => {
    if (systemMetrics.disk?.usage_percent !== undefined) {
      return systemMetrics.disk.usage_percent;
    }
    if (systemMetrics.disk_usage !== undefined) {
      return systemMetrics.disk_usage * 100;
    }
    return 0;
  };

  const resources = [
    { 
      name: 'CPU Usage', 
      value: getCpuUsage(), 
      icon: Cpu,
      unit: '%'
    },
    { 
      name: 'Memory Usage', 
      value: getMemoryUsage(), 
      icon: MemoryStick,
      unit: '%'
    },
    { 
      name: 'Disk Usage', 
      value: getDiskUsage(), 
      icon: HardDrive,
      unit: '%'
    },
  ];

  return (
    <GlassPanel variant="primary" className="p-6 backdrop-blur-glass-strong">
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-lg font-semibold text-foreground flex items-center gap-2">
          <Activity className="h-5 w-5 text-primary" />
          System Resources
        </h3>
        <button
          onClick={refreshMetrics}
          className={cn(
            'p-2 rounded-full bg-glass-bg-secondary hover:bg-glass-bg-tertiary transition-all duration-200',
            isRefreshing && 'animate-spin'
          )}
          disabled={isRefreshing}
        >
          <RefreshCw className="h-4 w-4 text-muted-foreground" />
        </button>
      </div>
      
      <div className="grid gap-6">
        {resources.map((res) => {
          const Icon = res.icon;
          const value = Math.round(res.value);
          
          return (
            <div key={res.name} className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-primary/10">
                    <Icon className="h-5 w-5 text-primary" />
                  </div>
                  <div>
                    <div className="font-medium text-foreground">{res.name}</div>
                    <div className="text-xs text-muted-foreground">Real-time monitoring</div>
                  </div>
                </div>
                <div className="text-right">
                  <div className={cn("text-2xl font-bold", getUsageColor(value))}>
                    {isNaN(value) ? 'N/A' : Math.round(value)}{res.unit}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {isNaN(value) ? 'Loading...' : value > 80 ? 'High' : value > 60 ? 'Moderate' : 'Normal'}
                  </div>
                </div>
              </div>
              <div className="space-y-2">
                <ProgressBar 
                  value={isNaN(value) ? 0 : value} 
                  className={cn("h-2 rounded-full", getUsageBarColor(value))}
                />
                <div className="flex justify-between text-xs text-muted-foreground">
                  <span>0%</span>
                  <span>50%</span>
                  <span>100%</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </GlassPanel>
  );
}

function LogViewer() {
  const { systemLogs, systemLogsLoading, loadSystemLogs } = useAgentStore();
  const [isAutoScroll, setIsAutoScroll] = React.useState(true);
  const [selectedChannel, setSelectedChannel] = React.useState<string>('all');
  const [selectedLevel, setSelectedLevel] = React.useState<string>('all');
  const [filteredLogs, setFilteredLogs] = React.useState(systemLogs);
  const logEndRef = React.useRef<HTMLDivElement>(null);

  // Available channels and levels
  const logChannels = [
    { value: 'all', label: 'All Logs', color: 'text-gray-400' },
    { value: 'job_logs', label: 'Job Logs', color: 'text-blue-400' },
    { value: 'system_logs', label: 'System Logs', color: 'text-green-400' },
    { value: 'error_logs', label: 'Error Logs', color: 'text-red-400' },
    { value: 'debug_logs', label: 'Debug Logs', color: 'text-purple-400' },
    { value: 'audit_logs', label: 'Audit Logs', color: 'text-orange-400' },
  ];

  const logLevels = [
    { value: 'all', label: 'All Levels' },
    { value: 'DEBUG', label: 'Debug' },
    { value: 'INFO', label: 'Info' },
    { value: 'WARNING', label: 'Warning' },
    { value: 'ERROR', label: 'Error' },
    { value: 'CRITICAL', label: 'Critical' },
  ];

  React.useEffect(() => {
    const loadLogsWithFilters = () => {
      const params: any = {};
      if (selectedChannel !== 'all') {
        params.channel = selectedChannel;
      }
      if (selectedLevel !== 'all') {
        params.level = selectedLevel;
      }
      loadSystemLogs(params);
    };
    
    loadLogsWithFilters();
    const interval = setInterval(loadLogsWithFilters, 10000); // Refresh logs every 10 seconds
    return () => clearInterval(interval);
  }, [loadSystemLogs, selectedChannel, selectedLevel]);

  // Filter logs based on selected filters
  React.useEffect(() => {
    let filtered = systemLogs;
    
    if (selectedChannel !== 'all') {
      filtered = filtered.filter(log => log.channel === selectedChannel);
    }
    
    if (selectedLevel !== 'all') {
      filtered = filtered.filter(log => log.level === selectedLevel);
    }
    
    setFilteredLogs(filtered);
  }, [systemLogs, selectedChannel, selectedLevel]);

  React.useEffect(() => {
    if (isAutoScroll && logEndRef.current) {
      logEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [filteredLogs, isAutoScroll]);

  const getLevelColor = (level: string) => {
    switch (level.toUpperCase()) {
      case 'INFO': return 'text-blue-400';
      case 'WARNING': return 'text-yellow-400';
      case 'ERROR': return 'text-red-400';
      case 'DEBUG': return 'text-gray-400';
      case 'SUCCESS': return 'text-green-400';
      default: return 'text-muted-foreground';
    }
  }

  const getLevelBadgeColor = (level: string) => {
    switch (level.toUpperCase()) {
      case 'INFO': return 'bg-blue-500/20 text-blue-400 border-blue-500/30';
      case 'WARNING': return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30';
      case 'ERROR': return 'bg-red-500/20 text-red-400 border-red-500/30';
      case 'DEBUG': return 'bg-gray-500/20 text-gray-400 border-gray-500/30';
      case 'SUCCESS': return 'bg-green-500/20 text-green-400 border-green-500/30';
      default: return 'bg-muted/20 text-muted-foreground border-muted/30';
    }
  }

  const getChannelColor = (channel: string) => {
    const channelInfo = logChannels.find(ch => ch.value === channel);
    return channelInfo?.color || 'text-gray-400';
  };

  const logCounts = React.useMemo(() => {
    const counts = { INFO: 0, WARNING: 0, ERROR: 0, DEBUG: 0, SUCCESS: 0, CRITICAL: 0, OTHER: 0 };
    filteredLogs.forEach(log => {
      const level = log.level.toUpperCase();
      if (counts.hasOwnProperty(level)) {
        counts[level as keyof typeof counts]++;
      } else {
        counts.OTHER++;
      }
    });
    return counts;
  }, [filteredLogs]);

  return (
    <GlassPanel variant="secondary" className="p-6 backdrop-blur-glass-medium">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-foreground flex items-center gap-2">
          <Activity className="h-5 w-5 text-primary" />
          System Logs
        </h3>
        <div className="flex items-center gap-2">
          {/* Channel Selector */}
          <select
            value={selectedChannel}
            onChange={(e) => setSelectedChannel(e.target.value)}
            className="px-3 py-1 rounded-lg text-xs bg-glass-bg-tertiary text-foreground border border-glass-border-tertiary hover:bg-glass-bg-secondary focus:outline-none focus:ring-2 focus:ring-primary/50"
          >
            {logChannels.map((channel) => (
              <option key={channel.value} value={channel.value}>
                {channel.label}
              </option>
            ))}
          </select>
          
          {/* Level Selector */}
          <select
            value={selectedLevel}
            onChange={(e) => setSelectedLevel(e.target.value)}
            className="px-3 py-1 rounded-lg text-xs bg-glass-bg-tertiary text-foreground border border-glass-border-tertiary hover:bg-glass-bg-secondary focus:outline-none focus:ring-2 focus:ring-primary/50"
          >
            {logLevels.map((level) => (
              <option key={level.value} value={level.value}>
                {level.label}
              </option>
            ))}
          </select>
          
          <button
            onClick={() => setIsAutoScroll(!isAutoScroll)}
            className={cn(
              'px-3 py-1 rounded-full text-xs transition-all duration-200',
              isAutoScroll 
                ? 'bg-primary/20 text-primary border border-primary/30' 
                : 'bg-glass-bg-tertiary text-muted-foreground border border-glass-border-tertiary hover:bg-glass-bg-secondary'
            )}
          >
            Auto-scroll {isAutoScroll ? 'ON' : 'OFF'}
          </button>
          <button
            onClick={() => loadSystemLogs({ channel: selectedChannel !== 'all' ? selectedChannel : undefined, level: selectedLevel !== 'all' ? selectedLevel : undefined })}
            className="p-2 rounded-full bg-glass-bg-tertiary hover:bg-glass-bg-secondary transition-all duration-200"
          >
            <RefreshCw className="h-4 w-4 text-muted-foreground" />
          </button>
        </div>
      </div>

      {/* Log Level Summary */}
      <div className="flex flex-wrap gap-2 mb-4 p-3 rounded-xl bg-glass-bg-tertiary/50">
        {Object.entries(logCounts).map(([level, count]) => (
          <div key={level} className={cn(
            'px-2 py-1 rounded-full text-xs border',
            getLevelBadgeColor(level)
          )}>
            {level}: {count}
          </div>
        ))}
      </div>

      {/* Logs Container */}
      <div className="h-96 overflow-y-auto bg-black/30 backdrop-blur-sm rounded-xl p-4 font-mono text-xs border border-glass-border-tertiary">
        {systemLogsLoading && (
          <div className="flex justify-center py-4">
            <LoadingSpinner />
          </div>
        )}
        
        {filteredLogs.length === 0 && !systemLogsLoading && (
          <div className="text-center py-8 text-muted-foreground">
            <Activity className="h-8 w-8 mx-auto mb-2 opacity-50" />
            <p>No logs available{selectedChannel !== 'all' ? ` for ${logChannels.find(ch => ch.value === selectedChannel)?.label}` : ''}</p>
          </div>
        )}

        {filteredLogs.map((log, i) => (
          <div key={i} className="py-2 hover:bg-white/5 rounded px-3 transition-colors border-l-2 border-transparent hover:border-primary/30">
            <div className="flex gap-3 items-start">
              <span className="text-muted-foreground/60 text-[10px] mt-0.5 min-w-[70px] font-mono">
                {new Date(log.timestamp).toLocaleTimeString()}
              </span>
              <span className={cn(
                "font-bold min-w-[60px] text-[10px] mt-0.5 px-2 py-0.5 rounded-full",
                getLevelBadgeColor(log.level)
              )}>
                {log.level}
              </span>
              {/* Channel Indicator */}
              {log.channel && (
                <span className={cn(
                  "text-[9px] mt-0.5 px-2 py-0.5 rounded-full font-medium",
                  "bg-glass-bg-secondary border border-glass-border-secondary",
                  getChannelColor(log.channel)
                )}>
                  {logChannels.find(ch => ch.value === log.channel)?.label || log.channel}
                </span>
              )}
              <div className="flex-1 space-y-1">
                <div className="text-foreground/90 text-[11px] leading-relaxed">
                  {log.message}
                </div>
                <div className="flex gap-4 text-[9px] text-muted-foreground/70">
                  <span>📦 {log.module}</span>
                  {log.task_id && <span>🔧 Task: {log.task_id.substring(0, 8)}...</span>}
                  {log.pipeline_phase && <span>⚡ Phase: {log.pipeline_phase}</span>}
                </div>
                {log.details && Object.keys(log.details).length > 0 && (
                  <details className="text-[9px] text-muted-foreground/60 mt-1">
                    <summary className="cursor-pointer hover:text-muted-foreground">Details</summary>
                    <pre className="mt-1 ml-2 p-2 bg-black/20 rounded text-[8px] overflow-x-auto">
                      {JSON.stringify(log.details, null, 2)}
                    </pre>
                  </details>
                )}
              </div>
            </div>
          </div>
        ))}
        <div ref={logEndRef} />
      </div>
    </GlassPanel>
  );
}

// Enhanced GPU monitoring with multi-GPU support
interface GPUData {
  id: number;
  name: string;
  usage: number;
  frequency: number;
  memoryUsage: number;
  memoryTotal: number;
  memoryFrequency: number;
  temperature: number;
  powerUsage: number;
  powerLimit: number;
  fanSpeed: number;
}

// Initial GPU data - will be replaced with real data if available
const getInitialGpuData = (): GPUData[] => {
  // This would normally come from nvidia-ml-py or nvidia-smi
  // For now, return realistic idle state data
  return [
    {
      id: 0,
      name: 'NVIDIA RTX 4090',
      usage: 0,
      frequency: 210,  // Base clock when idle
      memoryUsage: 512, // Small amount used by system
      memoryTotal: 24576,
      memoryFrequency: 5001, // Half speed when idle
      temperature: 35, // Cool when idle
      powerUsage: 25,  // Very low when idle
      powerLimit: 450,
      fanSpeed: 0,     // Fans off when cool
    },
    {
      id: 1,
      name: 'NVIDIA RTX 4090',
      usage: 0,
      frequency: 210,
      memoryUsage: 512,
      memoryTotal: 24576,
      memoryFrequency: 5001,
      temperature: 33,
      powerUsage: 23,
      powerLimit: 450,
      fanSpeed: 0,
    },
  ];
};

// Convert Celsius to Fahrenheit
function celsiusToFahrenheit(celsius: number): number {
  return Math.round((celsius * 9/5) + 32);
}

function getTemperatureColor(tempF: number) {
  if (tempF > 185) return 'text-red-500';     // 85°C
  if (tempF > 167) return 'text-orange-500';  // 75°C
  if (tempF > 149) return 'text-yellow-500';  // 65°C
  return 'text-green-500';
}

function getTemperatureBarColor(tempF: number) {
  if (tempF > 185) return 'bg-gradient-to-r from-red-500 to-red-600';
  if (tempF > 167) return 'bg-gradient-to-r from-orange-500 to-red-500';
  if (tempF > 149) return 'bg-gradient-to-r from-yellow-500 to-orange-500';
  return 'bg-gradient-to-r from-green-500 to-blue-500';
}

function SingleGPUCard({ gpu }: { gpu: GPUData }) {
  const memoryUsagePercent = Math.round((gpu.memoryUsage / gpu.memoryTotal) * 100);
  const tempInFahrenheit = celsiusToFahrenheit(gpu.temperature);

  return (
    <GlassPanel variant="secondary" className="p-6 backdrop-blur-glass-medium">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-gradient-to-br from-green-500/20 to-blue-500/20">
            <Gauge className="h-5 w-5 text-green-500" />
          </div>
          <div>
            <h4 className="font-semibold text-foreground">GPU {gpu.id}</h4>
            <p className="text-xs text-muted-foreground">{gpu.name}</p>
          </div>
        </div>
        <div className="text-right">
          <div className="text-sm font-medium text-foreground">{Math.round(gpu.usage)}%</div>
          <div className="text-xs text-muted-foreground">Usage</div>
        </div>
      </div>

      {/* GPU Usage */}
      <div className="space-y-4">
        <div>
          <div className="flex justify-between text-sm mb-2">
            <span className="text-muted-foreground">GPU Usage</span>
            <span className="font-medium text-foreground">{Math.round(gpu.usage)}%</span>
          </div>
          <ProgressBar 
            value={gpu.usage} 
            className="bg-gradient-to-r from-blue-500 to-purple-500 h-2"
          />
        </div>

        {/* Memory Usage */}
        <div>
          <div className="flex justify-between text-sm mb-2">
            <span className="text-muted-foreground">Memory</span>
            <span className="font-medium text-foreground">
              {Math.round(gpu.memoryUsage / 1024)}GB / {Math.round(gpu.memoryTotal / 1024)}GB
            </span>
          </div>
          <ProgressBar 
            value={memoryUsagePercent} 
            className="bg-gradient-to-r from-cyan-500 to-blue-500 h-2"
          />
        </div>

        {/* Temperature */}
        <div>
          <div className="flex justify-between text-sm mb-2">
            <span className="text-muted-foreground flex items-center gap-1">
              <Thermometer className="h-3 w-3" />
              Temperature
            </span>
            <span className={cn("font-medium", getTemperatureColor(tempInFahrenheit))}>
              {tempInFahrenheit}°F
            </span>
          </div>
          <ProgressBar 
            value={(tempInFahrenheit / 200) * 100} 
            className={cn("h-2", getTemperatureBarColor(tempInFahrenheit))}
          />
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-2 gap-4 pt-2 border-t border-glass-border-tertiary">
          <div className="text-center p-2 rounded-lg bg-glass-bg-tertiary">
            <div className="text-xs text-muted-foreground">Core Clock</div>
            <div className="text-sm font-semibold text-foreground">{gpu.frequency} MHz</div>
          </div>
          <div className="text-center p-2 rounded-lg bg-glass-bg-tertiary">
            <div className="text-xs text-muted-foreground">Memory Clock</div>
            <div className="text-sm font-semibold text-foreground">{gpu.memoryFrequency} MHz</div>
          </div>
          <div className="text-center p-2 rounded-lg bg-glass-bg-tertiary">
            <div className="text-xs text-muted-foreground">Power</div>
            <div className="text-sm font-semibold text-foreground">{gpu.powerUsage}W</div>
          </div>
          <div className="text-center p-2 rounded-lg bg-glass-bg-tertiary">
            <div className="text-xs text-muted-foreground">Fan Speed</div>
            <div className="text-sm font-semibold text-foreground">{gpu.fanSpeed}%</div>
          </div>
        </div>
      </div>
    </GlassPanel>
  );
}

function GPUStats() {
  const [isRefreshing, setIsRefreshing] = React.useState(false);
  const [gpuData, setGpuData] = React.useState<GPUData[]>(getInitialGpuData());
  const [gpuDetected, setGpuDetected] = React.useState(true); // Set to false if no GPU detected

  const fetchGPUStats = async () => {
    setIsRefreshing(true);
    try {
      // TODO: Replace with real GPU monitoring API call
      // 1. Add GPU monitoring endpoint to backend: GET /system/gpu-stats
      // 2. Install nvidia-ml-py in backend requirements
      // 3. Add nvidia-smi integration to system.py
      // Example API response format:
      // {
      //   "gpus": [
      //     {
      //       "id": 0,
      //       "name": "NVIDIA RTX 4090",
      //       "usage": 0,
      //       "frequency": 210,
      //       "memoryUsage": 512,
      //       "memoryTotal": 24576,
      //       "memoryFrequency": 5001,
      //       "temperature": 35,
      //       "powerUsage": 25,
      //       "powerLimit": 450,
      //       "fanSpeed": 0
      //     }
      //   ]
      // }
      
      // const response = await apiService.get('/system/gpu-stats');
      // if (response.gpus && response.gpus.length > 0) {
      //   setGpuData(response.gpus);
      //   setGpuDetected(true);
      // } else {
      //   setGpuDetected(false);
      // }
      
      // For now, maintain realistic idle state
      setGpuData(getInitialGpuData());
    } catch (error) {
      console.error('Failed to fetch GPU stats:', error);
      setGpuDetected(false);
    } finally {
      setIsRefreshing(false);
    }
  };

  React.useEffect(() => {
    fetchGPUStats(); // Initial load
    const interval = setInterval(fetchGPUStats, 5000); // Refresh every 5 seconds
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="space-y-4">
      <GlassPanel variant="primary" className="p-4 backdrop-blur-glass-strong">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-foreground flex items-center gap-2">
            <Gauge className="h-5 w-5 text-primary" />
            NVIDIA GPU Statistics
          </h3>
          <div className="flex items-center gap-2">
            <div className="text-sm text-muted-foreground">
              {gpuData.length} GPU{gpuData.length > 1 ? 's' : ''} detected
            </div>
            <button
              onClick={fetchGPUStats}
              className={cn(
                'p-2 rounded-full bg-glass-bg-secondary hover:bg-glass-bg-tertiary transition-all duration-200',
                isRefreshing && 'animate-spin'
              )}
              disabled={isRefreshing}
            >
              <RefreshCw className="h-4 w-4 text-muted-foreground" />
            </button>
          </div>
        </div>
        
        {/* GPU Overview */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
          <div className="text-center p-3 rounded-xl bg-glass-bg-secondary">
            <div className="text-xs text-muted-foreground">Avg Usage</div>
            <div className="text-lg font-bold text-foreground">
              {Math.round(gpuData.reduce((acc, gpu) => acc + gpu.usage, 0) / gpuData.length)}%
            </div>
          </div>
          <div className="text-center p-3 rounded-xl bg-glass-bg-secondary">
            <div className="text-xs text-muted-foreground">Avg Temp</div>
            <div className="text-lg font-bold text-foreground">
              {Math.round(gpuData.reduce((acc, gpu) => acc + celsiusToFahrenheit(gpu.temperature), 0) / gpuData.length)}°F
            </div>
          </div>
          <div className="text-center p-3 rounded-xl bg-glass-bg-secondary">
            <div className="text-xs text-muted-foreground">Total Power</div>
            <div className="text-lg font-bold text-foreground">
              {gpuData.reduce((acc, gpu) => acc + gpu.powerUsage, 0)}W
            </div>
          </div>
          <div className="text-center p-3 rounded-xl bg-glass-bg-secondary">
            <div className="text-xs text-muted-foreground">Memory Used</div>
            <div className="text-lg font-bold text-foreground">
              {Math.round(gpuData.reduce((acc, gpu) => acc + gpu.memoryUsage, 0) / 1024)}GB
            </div>
          </div>
        </div>
      </GlassPanel>
      
      {/* Individual GPU Cards */}
      <div className="grid gap-4 md:grid-cols-2">
        {gpuData.map((gpu) => (
          <SingleGPUCard key={gpu.id} gpu={gpu} />
        ))}
      </div>
    </div>
  );
}

function SystemOverview() {
  const [systemHealth, setSystemHealth] = React.useState('excellent');
  const [lastUpdate, setLastUpdate] = React.useState(new Date());

  React.useEffect(() => {
    const interval = setInterval(() => {
      setLastUpdate(new Date());
      // Simulate health status changes for demo
      const statuses = ['excellent', 'good', 'warning', 'critical'];
      setSystemHealth(statuses[Math.floor(Math.random() * statuses.length)]);
    }, 30000);
    return () => clearInterval(interval);
  }, []);

  const getHealthColor = (health: string) => {
    switch (health) {
      case 'excellent': return 'text-green-500';
      case 'good': return 'text-blue-500';
      case 'warning': return 'text-yellow-500';
      case 'critical': return 'text-red-500';
      default: return 'text-gray-500';
    }
  };

  const getHealthIcon = (health: string) => {
    switch (health) {
      case 'excellent': return CheckCircle;
      case 'good': return CheckCircle;
      case 'warning': return AlertTriangle;
      case 'critical': return AlertTriangle;
      default: return Activity;
    }
  };

  const HealthIcon = getHealthIcon(systemHealth);

  return (
    <GlassPanel variant="primary" className="p-6 backdrop-blur-glass-strong">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="p-3 rounded-full bg-gradient-to-br from-primary/20 to-primary/10">
            <Activity className="h-8 w-8 text-primary" />
          </div>
          <div>
            <h3 className="text-xl font-bold text-foreground">System Overview</h3>
            <p className="text-muted-foreground">Real-time monitoring dashboard</p>
          </div>
        </div>
        <div className="text-right">
          <div className="flex items-center gap-2 mb-1">
            <HealthIcon className={cn("h-5 w-5", getHealthColor(systemHealth))} />
            <span className={cn("font-semibold capitalize", getHealthColor(systemHealth))}>
              {systemHealth}
            </span>
          </div>
          <div className="text-xs text-muted-foreground">
            Last updated: {lastUpdate.toLocaleTimeString()}
          </div>
        </div>
      </div>
    </GlassPanel>
  );
}

export function Monitoring() {
  return (
    <div className="container mx-auto px-4 py-4 sm:px-6 sm:py-6 lg:px-8 lg:py-8 space-y-6">
      {/* Header */}
      <div className="text-center lg:text-left">
        <h2 className="text-3xl font-bold tracking-tight text-foreground mb-2">
          System Monitoring
        </h2>
        <p className="text-muted-foreground text-lg">
          Real-time metrics, GPU statistics, and system logs for comprehensive monitoring.
        </p>
      </div>

      {/* System Overview */}
      <SystemOverview />

      {/* Main Grid */}
      <div className="grid gap-6 xl:grid-cols-3">
        {/* System Resources - Takes 1 column */}
        <div className="xl:col-span-1">
          <ResourceMonitor />
        </div>
        
        {/* GPU Stats - Takes 2 columns */}
        <div className="xl:col-span-2">
          <GPUStats />
        </div>
      </div>

      {/* Logs - Full width */}
      <LogViewer />
    </div>
  );
}

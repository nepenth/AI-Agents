import { useState, useEffect, useCallback } from 'react';
import { websocketService } from '@/services/websocket';
import { useAgentStore } from '@/stores';

export interface LogEntry {
  timestamp: string;
  level: string;
  message: string;
  module: string;
  channel?: string;
  task_id?: string;
  pipeline_phase?: string;
  details?: Record<string, any>;
}

export interface LogFilters {
  channel?: string;
  level?: string;
  module?: string;
  task_id?: string;
  limit?: number;
}

export interface UseRealTimeLogsOptions {
  autoConnect?: boolean;
  maxLogs?: number;
  filters?: LogFilters;
}

export function useRealTimeLogs(options: UseRealTimeLogsOptions = {}) {
  const {
    autoConnect = true,
    maxLogs = 1000,
    filters = {}
  } = options;

  const { systemLogs, loadSystemLogs } = useAgentStore();
  const [isConnected, setIsConnected] = useState(false);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [subscriptions, setSubscriptions] = useState<Set<string>>(new Set());

  // Filter logs based on current filters
  const filteredLogs = systemLogs.filter(log => {
    if (filters.channel && filters.channel !== 'all' && log.channel !== filters.channel) {
      return false;
    }
    if (filters.level && filters.level !== 'all' && log.level !== filters.level) {
      return false;
    }
    if (filters.module && !log.module.toLowerCase().includes(filters.module.toLowerCase())) {
      return false;
    }
    if (filters.task_id && log.task_id !== filters.task_id) {
      return false;
    }
    return true;
  });

  // Connect to WebSocket and set up log streaming
  const connect = useCallback(async () => {
    try {
      if (!websocketService.isConnected) {
        await websocketService.connect();
      }
      setIsConnected(true);
      setConnectionError(null);
    } catch (error) {
      setConnectionError(error instanceof Error ? error.message : 'Connection failed');
      setIsConnected(false);
    }
  }, []);

  // Disconnect from WebSocket
  const disconnect = useCallback(() => {
    // Unsubscribe from all channels
    subscriptions.forEach(channel => {
      websocketService.unsubscribeFromChannel(channel);
    });
    setSubscriptions(new Set());
    
    websocketService.disconnect();
    setIsConnected(false);
  }, [subscriptions]);

  // Subscribe to a specific log channel
  const subscribeToChannel = useCallback((channel: string) => {
    if (!subscriptions.has(channel)) {
      websocketService.subscribeToChannel(channel);
      setSubscriptions(prev => new Set([...prev, channel]));
    }
  }, [subscriptions]);

  // Unsubscribe from a specific log channel
  const unsubscribeFromChannel = useCallback((channel: string) => {
    if (subscriptions.has(channel)) {
      websocketService.unsubscribeFromChannel(channel);
      setSubscriptions(prev => {
        const newSet = new Set(prev);
        newSet.delete(channel);
        return newSet;
      });
    }
  }, [subscriptions]);

  // Load historical logs
  const loadHistoricalLogs = useCallback(async (customFilters?: LogFilters) => {
    const params = { ...filters, ...customFilters };
    await loadSystemLogs(params);
  }, [filters, loadSystemLogs]);

  // Clear all logs
  const clearLogs = useCallback(() => {
    useAgentStore.setState({ systemLogs: [] });
  }, []);

  // Set up WebSocket connection and subscriptions
  useEffect(() => {
    if (autoConnect) {
      connect();
    }

    // Set up connection status listener
    const unsubscribeConnection = websocketService.subscribe('connection', (data: any) => {
      setIsConnected(data.status === 'connected');
      if (data.status === 'error' || data.status === 'failed') {
        setConnectionError(data.error || data.reason || 'Connection failed');
      } else {
        setConnectionError(null);
      }
    });

    return () => {
      unsubscribeConnection();
      if (autoConnect) {
        disconnect();
      }
    };
  }, [autoConnect, connect, disconnect]);

  // Set up channel subscriptions based on filters
  useEffect(() => {
    if (!isConnected) return;

    // Subscribe to appropriate channels based on filters
    if (filters.channel && filters.channel !== 'all') {
      subscribeToChannel(filters.channel);
    } else {
      // Subscribe to all log channels
      const logChannels = ['job_logs', 'system_logs', 'error_logs', 'debug_logs', 'audit_logs'];
      logChannels.forEach(channel => subscribeToChannel(channel));
    }

    // Load initial historical logs
    loadHistoricalLogs();
  }, [isConnected, filters.channel, subscribeToChannel, loadHistoricalLogs]);

  // Get log statistics
  const getLogStats = useCallback(() => {
    const stats = {
      total: filteredLogs.length,
      byLevel: {} as Record<string, number>,
      byChannel: {} as Record<string, number>,
      byModule: {} as Record<string, number>
    };

    filteredLogs.forEach(log => {
      // Count by level
      stats.byLevel[log.level] = (stats.byLevel[log.level] || 0) + 1;
      
      // Count by channel
      if (log.channel) {
        stats.byChannel[log.channel] = (stats.byChannel[log.channel] || 0) + 1;
      }
      
      // Count by module
      const moduleBase = log.module.split('.')[0];
      stats.byModule[moduleBase] = (stats.byModule[moduleBase] || 0) + 1;
    });

    return stats;
  }, [filteredLogs]);

  // Get recent logs (last N logs)
  const getRecentLogs = useCallback((count: number = 50) => {
    return filteredLogs.slice(-count);
  }, [filteredLogs]);

  // Search logs by message content
  const searchLogs = useCallback((query: string) => {
    if (!query.trim()) return filteredLogs;
    
    const searchTerm = query.toLowerCase();
    return filteredLogs.filter(log => 
      log.message.toLowerCase().includes(searchTerm) ||
      log.module.toLowerCase().includes(searchTerm) ||
      (log.pipeline_phase && log.pipeline_phase.toLowerCase().includes(searchTerm))
    );
  }, [filteredLogs]);

  return {
    // Log data
    logs: filteredLogs,
    allLogs: systemLogs,
    
    // Connection state
    isConnected,
    connectionError,
    subscriptions: Array.from(subscriptions),
    
    // Actions
    connect,
    disconnect,
    subscribeToChannel,
    unsubscribeFromChannel,
    loadHistoricalLogs,
    clearLogs,
    
    // Utilities
    getLogStats,
    getRecentLogs,
    searchLogs,
    
    // Computed values
    logCount: filteredLogs.length,
    hasLogs: filteredLogs.length > 0
  };
}

// Hook for monitoring specific task logs
export function useTaskLogs(taskId: string) {
  return useRealTimeLogs({
    filters: { task_id: taskId },
    maxLogs: 500
  });
}

// Hook for monitoring specific channel logs
export function useChannelLogs(channel: string) {
  return useRealTimeLogs({
    filters: { channel: channel !== 'all' ? channel : undefined },
    maxLogs: 1000
  });
}

// Hook for monitoring error logs only
export function useErrorLogs() {
  return useRealTimeLogs({
    filters: { level: 'ERROR' },
    maxLogs: 200
  });
}
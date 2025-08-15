import { useEffect, useCallback, useState } from 'react';
import { useWebSocket } from './useWebSocket';

export interface PipelineUpdate {
  phase: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  progress?: number;
  duration?: number;
  error?: string;
  timestamp: string;
}

export interface SystemUpdate {
  type: 'pipeline' | 'ai_model' | 'system_health' | 'error';
  data: any;
  timestamp: string;
}

export interface UseRealTimeUpdatesOptions {
  onPipelineUpdate?: (update: PipelineUpdate) => void;
  onSystemUpdate?: (update: SystemUpdate) => void;
  onError?: (error: any) => void;
}

export const useRealTimeUpdates = (options: UseRealTimeUpdatesOptions = {}) => {
  const { onPipelineUpdate, onSystemUpdate, onError } = options;
  const { subscribe, send, isConnected, connectionState } = useWebSocket();
  
  const [lastUpdate, setLastUpdate] = useState<SystemUpdate | null>(null);
  const [updateCount, setUpdateCount] = useState(0);

  // Handle pipeline updates
  useEffect(() => {
    const unsubscribe = subscribe('pipeline_update', (data: PipelineUpdate) => {
      setLastUpdate({
        type: 'pipeline',
        data,
        timestamp: new Date().toISOString()
      });
      setUpdateCount(prev => prev + 1);
      onPipelineUpdate?.(data);
    });

    return unsubscribe;
  }, [subscribe, onPipelineUpdate]);

  // Handle AI model updates
  useEffect(() => {
    const unsubscribe = subscribe('ai_model_update', (data: any) => {
      const update: SystemUpdate = {
        type: 'ai_model',
        data,
        timestamp: new Date().toISOString()
      };
      setLastUpdate(update);
      setUpdateCount(prev => prev + 1);
      onSystemUpdate?.(update);
    });

    return unsubscribe;
  }, [subscribe, onSystemUpdate]);

  // Handle system health updates
  useEffect(() => {
    const unsubscribe = subscribe('system_health', (data: any) => {
      const update: SystemUpdate = {
        type: 'system_health',
        data,
        timestamp: new Date().toISOString()
      };
      setLastUpdate(update);
      setUpdateCount(prev => prev + 1);
      onSystemUpdate?.(update);
    });

    return unsubscribe;
  }, [subscribe, onSystemUpdate]);

  // Handle error updates
  useEffect(() => {
    const unsubscribe = subscribe('error', (data: any) => {
      const update: SystemUpdate = {
        type: 'error',
        data,
        timestamp: new Date().toISOString()
      };
      setLastUpdate(update);
      setUpdateCount(prev => prev + 1);
      onError?.(data);
    });

    return unsubscribe;
  }, [subscribe, onError]);

  // Subscribe to pipeline progress for a specific task
  const subscribeToPipeline = useCallback((taskId: string) => {
    send('subscribe_pipeline', { taskId });
  }, [send]);

  // Unsubscribe from pipeline progress
  const unsubscribeFromPipeline = useCallback((taskId: string) => {
    send('unsubscribe_pipeline', { taskId });
  }, [send]);

  // Request system status update
  const requestSystemStatus = useCallback(() => {
    send('request_system_status', {});
  }, [send]);

  // Request pipeline status update
  const requestPipelineStatus = useCallback((taskId?: string) => {
    send('request_pipeline_status', { taskId });
  }, [send]);

  return {
    // Connection status
    isConnected,
    connectionState,
    
    // Update information
    lastUpdate,
    updateCount,
    
    // Control methods
    subscribeToPipeline,
    unsubscribeFromPipeline,
    requestSystemStatus,
    requestPipelineStatus
  };
};

// Hook for pipeline-specific updates
export const usePipelineUpdates = (taskId?: string) => {
  const [pipelineStatus, setPipelineStatus] = useState<{
    [phase: string]: PipelineUpdate;
  }>({});
  
  const [overallProgress, setOverallProgress] = useState(0);
  const [isProcessing, setIsProcessing] = useState(false);

  const handlePipelineUpdate = useCallback((update: PipelineUpdate) => {
    setPipelineStatus(prev => ({
      ...prev,
      [update.phase]: update
    }));

    // Calculate overall progress
    const phases = Object.values(pipelineStatus);
    if (phases.length > 0) {
      const completedPhases = phases.filter(p => p.status === 'completed').length;
      const totalPhases = phases.length;
      setOverallProgress((completedPhases / totalPhases) * 100);
    }

    // Update processing status
    const hasRunningPhases = Object.values(pipelineStatus).some(p => p.status === 'running');
    setIsProcessing(hasRunningPhases);
  }, [pipelineStatus]);

  const { subscribeToPipeline, unsubscribeFromPipeline, ...rest } = useRealTimeUpdates({
    onPipelineUpdate: handlePipelineUpdate
  });

  useEffect(() => {
    if (taskId) {
      subscribeToPipeline(taskId);
      return () => unsubscribeFromPipeline(taskId);
    }
  }, [taskId, subscribeToPipeline, unsubscribeFromPipeline]);

  return {
    pipelineStatus,
    overallProgress,
    isProcessing,
    subscribeToPipeline,
    unsubscribeFromPipeline,
    ...rest
  };
};
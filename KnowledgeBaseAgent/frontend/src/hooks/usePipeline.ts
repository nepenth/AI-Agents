import { useState, useCallback, useEffect } from 'react';
import { pipelineService } from '../services/pipelineService';
import { tweetService } from '../services/tweetService';
import { usePipelineUpdates } from './useRealTimeUpdates';

export interface PipelinePhase {
  id: string;
  name: string;
  description: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  progress?: number;
  duration?: number;
  error?: string;
  aiModelUsed?: string;
  isRealAI?: boolean;
  subPhases?: PipelineSubPhase[];
}

export interface PipelineSubPhase {
  id: string;
  name: string;
  description: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  progress?: number;
  duration?: number;
  error?: string;
}

export interface ProcessingStats {
  totalPhases: number;
  completedPhases: number;
  failedPhases: number;
  totalDuration: number;
  startTime: Date | null;
  endTime: Date | null;
}

export interface UsePipelineOptions {
  onPhaseComplete?: (phase: PipelinePhase) => void;
  onPipelineComplete?: (phases: PipelinePhase[]) => void;
  onError?: (error: string) => void;
}

const INITIAL_PHASES: Omit<PipelinePhase, 'status' | 'progress' | 'duration' | 'error'>[] = [
  {
    id: 'phase_1',
    name: 'System Initialization',
    description: 'Initialize AI services, database connections, and system components'
  },
  {
    id: 'phase_2',
    name: 'Fetch Bookmarks',
    description: 'Retrieve tweet data from Twitter API with full metadata',
    subPhases: [
      {
        id: 'phase_2_1',
        name: 'Bookmark Caching',
        description: 'Cache tweet content, detect threads, and process media'
      }
    ]
  },
  {
    id: 'phase_3',
    name: 'Content Processing',
    description: 'Multi-stage AI analysis with three specialized sub-phases',
    subPhases: [
      {
        id: 'phase_3_1',
        name: 'Media Analysis',
        description: 'AI-powered analysis of images, videos, and other media content'
      },
      {
        id: 'phase_3_2',
        name: 'Content Understanding',
        description: 'AI comprehension of tweet content, sentiment, and key insights'
      },
      {
        id: 'phase_3_3',
        name: 'AI Categorization',
        description: 'Intelligent categorization and tagging of content'
      }
    ]
  },
  {
    id: 'phase_4',
    name: 'Synthesis Generation',
    description: 'Generate synthesis documents linking related content'
  },
  {
    id: 'phase_5',
    name: 'Embedding Generation',
    description: 'Create vector embeddings for semantic search and similarity'
  },
  {
    id: 'phase_6',
    name: 'README Generation',
    description: 'Generate documentation and navigation for the knowledge base'
  },
  {
    id: 'phase_7',
    name: 'Git Sync',
    description: 'Synchronize processed content with git repository'
  }
];

export const usePipeline = (options: UsePipelineOptions = {}) => {
  const { onPhaseComplete, onPipelineComplete, onError } = options;

  const [phases, setPhases] = useState<PipelinePhase[]>(
    INITIAL_PHASES.map(phase => ({ 
      ...phase, 
      status: 'pending' as const,
      subPhases: phase.subPhases?.map(sub => ({ ...sub, status: 'pending' as const }))
    }))
  );

  const [currentTaskId, setCurrentTaskId] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [tweetData, setTweetData] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const [processingStats, setProcessingStats] = useState<ProcessingStats>({
    totalPhases: INITIAL_PHASES.length,
    completedPhases: 0,
    failedPhases: 0,
    totalDuration: 0,
    startTime: null,
    endTime: null
  });

  // Real-time updates
  const { pipelineStatus, isConnected, connectionState } = usePipelineUpdates(currentTaskId || undefined);

  // Update phases based on real-time pipeline status
  useEffect(() => {
    if (Object.keys(pipelineStatus).length > 0) {
      setPhases(prevPhases => {
        const updatedPhases = prevPhases.map(phase => {
          const statusUpdate = pipelineStatus[phase.id];
          if (statusUpdate) {
            const updatedPhase = {
              ...phase,
              status: statusUpdate.status,
              progress: statusUpdate.progress,
              duration: statusUpdate.duration,
              error: statusUpdate.error,
              aiModelUsed: statusUpdate.aiModelUsed,
              isRealAI: statusUpdate.isRealAI
            };

            // Check if phase just completed
            if (phase.status !== 'completed' && statusUpdate.status === 'completed') {
              onPhaseComplete?.(updatedPhase);
            }

            return updatedPhase;
          }
          return phase;
        });

        // Check if pipeline is complete
        const allCompleted = updatedPhases.every(p => p.status === 'completed');
        const wasProcessing = prevPhases.some(p => p.status === 'running');
        
        if (allCompleted && wasProcessing) {
          setIsProcessing(false);
          setProcessingStats(prev => ({ ...prev, endTime: new Date() }));
          onPipelineComplete?.(updatedPhases);
        }

        return updatedPhases;
      });
    }
  }, [pipelineStatus, onPhaseComplete, onPipelineComplete]);

  // Update processing stats
  useEffect(() => {
    const completed = phases.filter(p => p.status === 'completed').length;
    const failed = phases.filter(p => p.status === 'failed').length;
    const totalDuration = phases.reduce((sum, p) => sum + (p.duration || 0), 0);
    
    setProcessingStats(prev => ({
      ...prev,
      completedPhases: completed,
      failedPhases: failed,
      totalDuration
    }));
  }, [phases]);

  const validateTweetId = useCallback((id: string): boolean => {
    return tweetService.validateTweetId(id) || tweetService.extractTweetIdFromUrl(id) !== null;
  }, []);

  const extractTweetId = useCallback((input: string): string => {
    const extracted = tweetService.extractTweetIdFromUrl(input);
    return extracted || input.trim();
  }, []);

  const startProcessing = useCallback(async (tweetId: string, options?: {
    forceReprocess?: boolean;
    phases?: string[];
    aiModelOverrides?: { [phase: string]: string };
  }) => {
    const processedTweetId = extractTweetId(tweetId);
    
    if (!validateTweetId(processedTweetId)) {
      const errorMsg = 'Please enter a valid tweet ID or Twitter URL';
      setError(errorMsg);
      onError?.(errorMsg);
      return false;
    }

    setError(null);
    setIsProcessing(true);
    setProcessingStats({
      totalPhases: INITIAL_PHASES.length,
      completedPhases: 0,
      failedPhases: 0,
      totalDuration: 0,
      startTime: new Date(),
      endTime: null
    });

    // Reset phases
    setPhases(INITIAL_PHASES.map(phase => ({ 
      ...phase, 
      status: 'pending' as const,
      progress: undefined,
      duration: undefined,
      error: undefined,
      subPhases: phase.subPhases?.map(sub => ({ ...sub, status: 'pending' as const }))
    })));

    try {
      // Validate tweet exists
      const tweet = await tweetService.getTweetById(processedTweetId);
      setTweetData(tweet);

      // Start pipeline processing
      const response = await pipelineService.executePipeline({
        tweetId: processedTweetId,
        forceReprocess: options?.forceReprocess || false,
        phases: options?.phases,
        aiModelOverrides: options?.aiModelOverrides
      });

      setCurrentTaskId(response.taskId);
      return true;

    } catch (error: any) {
      console.error('Pipeline processing failed:', error);
      const errorMsg = error.message || 'Failed to start pipeline processing';
      setError(errorMsg);
      setIsProcessing(false);
      setProcessingStats(prev => ({ ...prev, endTime: new Date() }));
      onError?.(errorMsg);
      return false;
    }
  }, [extractTweetId, validateTweetId, onError]);

  const cancelProcessing = useCallback(async () => {
    if (currentTaskId) {
      try {
        await pipelineService.cancelTask(currentTaskId);
        setIsProcessing(false);
        setCurrentTaskId(null);
        setProcessingStats(prev => ({ ...prev, endTime: new Date() }));
        return true;
      } catch (error: any) {
        console.error('Failed to cancel task:', error);
        const errorMsg = 'Failed to cancel processing';
        setError(errorMsg);
        onError?.(errorMsg);
        return false;
      }
    }
    return false;
  }, [currentTaskId, onError]);

  const retryPhase = useCallback(async (phaseId: string) => {
    try {
      const phaseNumber = parseInt(phaseId.replace('phase_', ''));
      const response = await pipelineService.executePhase(phaseNumber, {}, true);
      
      // Update phase status to running
      setPhases(prev => prev.map(phase => 
        phase.id === phaseId 
          ? { ...phase, status: 'running' as const, error: undefined }
          : phase
      ));

      return true;
    } catch (error: any) {
      console.error(`Failed to retry phase ${phaseId}:`, error);
      const errorMsg = `Failed to retry ${phaseId}`;
      setError(errorMsg);
      onError?.(errorMsg);
      return false;
    }
  }, [onError]);

  const resetPipeline = useCallback(() => {
    setPhases(INITIAL_PHASES.map(phase => ({ 
      ...phase, 
      status: 'pending' as const,
      progress: undefined,
      duration: undefined,
      error: undefined,
      subPhases: phase.subPhases?.map(sub => ({ ...sub, status: 'pending' as const }))
    })));
    setProcessingStats({
      totalPhases: INITIAL_PHASES.length,
      completedPhases: 0,
      failedPhases: 0,
      totalDuration: 0,
      startTime: null,
      endTime: null
    });
    setIsProcessing(false);
    setCurrentTaskId(null);
    setTweetData(null);
    setError(null);
  }, []);

  const getPhaseById = useCallback((phaseId: string) => {
    return phases.find(phase => phase.id === phaseId);
  }, [phases]);

  const getCompletionPercentage = useCallback(() => {
    return (processingStats.completedPhases / processingStats.totalPhases) * 100;
  }, [processingStats]);

  return {
    // State
    phases,
    currentTaskId,
    isProcessing,
    tweetData,
    error,
    processingStats,
    
    // Connection status
    isConnected,
    connectionState,
    
    // Actions
    startProcessing,
    cancelProcessing,
    retryPhase,
    resetPipeline,
    
    // Utilities
    validateTweetId,
    extractTweetId,
    getPhaseById,
    getCompletionPercentage,
    
    // Computed values
    completionPercentage: getCompletionPercentage(),
    hasErrors: processingStats.failedPhases > 0,
    isComplete: processingStats.completedPhases === processingStats.totalPhases && !isProcessing
  };
};
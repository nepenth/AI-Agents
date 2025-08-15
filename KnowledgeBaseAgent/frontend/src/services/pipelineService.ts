import { apiService } from './api';

export interface PipelinePhaseStatus {
  phase: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  progress?: number;
  duration?: number;
  error?: string;
  startTime?: string;
  endTime?: string;
  aiModelUsed?: string;
  isRealAI?: boolean;
}

export interface PipelineStatus {
  taskId: string;
  overallStatus: 'pending' | 'running' | 'completed' | 'failed' | 'partial';
  phases: { [phaseId: string]: PipelinePhaseStatus };
  totalDuration?: number;
  startTime?: string;
  endTime?: string;
  tweetId?: string;
  tweetData?: any;
}

export interface PipelineExecutionRequest {
  tweetId: string;
  phases?: string[];
  forceReprocess?: boolean;
  aiModelOverrides?: { [phase: string]: string };
}

export interface PipelineExecutionResponse {
  taskId: string;
  status: string;
  message: string;
  estimatedDuration?: number;
}

export interface SubPhaseStatus {
  contentId: string;
  bookmarkCached: boolean;
  mediaAnalyzed: boolean;
  contentUnderstood: boolean;
  categorized: boolean;
  completionPercentage: number;
  isFullyProcessed: boolean;
  lastUpdated: string;
  processingErrors: string[];
}

class PipelineService {
  /**
   * Execute the complete seven-phase pipeline for a tweet
   */
  async executePipeline(request: PipelineExecutionRequest): Promise<PipelineExecutionResponse> {
    try {
      const response = await apiService.post('/pipeline/execute', request);
      return response.data;
    } catch (error) {
      console.error('Failed to execute pipeline:', error);
      throw error;
    }
  }

  /**
   * Execute a specific phase of the pipeline
   */
  async executePhase(
    phase: number, 
    config?: any, 
    forceReprocess: boolean = false
  ): Promise<PipelineExecutionResponse> {
    try {
      const response = await apiService.post(`/pipeline/phases/${phase}/execute`, {
        config,
        forceReprocess
      });
      return response.data;
    } catch (error) {
      console.error(`Failed to execute phase ${phase}:`, error);
      throw error;
    }
  }

  /**
   * Get overall pipeline status
   */
  async getPipelineStatus(): Promise<{
    overallStatus: string;
    phases: { [key: string]: any };
    activeTasks: string[];
    lastUpdated: string;
  }> {
    try {
      const response = await apiService.get('/pipeline/status');
      return response.data;
    } catch (error) {
      console.error('Failed to get pipeline status:', error);
      throw error;
    }
  }

  /**
   * Get status for a specific pipeline task
   */
  async getTaskStatus(taskId: string): Promise<PipelineStatus> {
    try {
      const response = await apiService.get(`/pipeline/tasks/${taskId}/status`);
      return response.data;
    } catch (error) {
      console.error(`Failed to get task status for ${taskId}:`, error);
      throw error;
    }
  }

  /**
   * Get status for a specific phase
   */
  async getPhaseStatus(phase: number): Promise<{
    phase: number;
    status: string;
    progress: number;
    lastRun?: string;
    subPhases?: { [key: string]: any };
  }> {
    try {
      const response = await apiService.get(`/pipeline/phases/${phase}/status`);
      return response.data;
    } catch (error) {
      console.error(`Failed to get phase ${phase} status:`, error);
      throw error;
    }
  }

  /**
   * Get sub-phase processing status for content items
   */
  async getSubPhaseStatus(
    processingState?: string,
    incompleteOnly: boolean = false,
    limit: number = 100
  ): Promise<SubPhaseStatus[]> {
    try {
      const params = new URLSearchParams();
      if (processingState) params.append('processing_state', processingState);
      if (incompleteOnly) params.append('incomplete_only', 'true');
      params.append('limit', limit.toString());

      const response = await apiService.get(`/content/sub-phases/status?${params}`);
      return response.data;
    } catch (error) {
      console.error('Failed to get sub-phase status:', error);
      throw error;
    }
  }

  /**
   * Reset sub-phase status for a content item
   */
  async resetSubPhaseStatus(contentId: string, phases: string[]): Promise<{
    message: string;
    contentId: string;
    resetPhases: string[];
  }> {
    try {
      const params = new URLSearchParams();
      phases.forEach(phase => params.append('phases', phase));

      const response = await apiService.post(
        `/content/sub-phases/${contentId}/reset?${params}`
      );
      return response.data;
    } catch (error) {
      console.error(`Failed to reset sub-phase status for ${contentId}:`, error);
      throw error;
    }
  }

  /**
   * Cancel a running pipeline task
   */
  async cancelTask(taskId: string): Promise<{ message: string; taskId: string }> {
    try {
      const response = await apiService.post(`/pipeline/tasks/${taskId}/cancel`);
      return response.data;
    } catch (error) {
      console.error(`Failed to cancel task ${taskId}:`, error);
      throw error;
    }
  }

  /**
   * Get pipeline execution history
   */
  async getPipelineHistory(
    limit: number = 50,
    offset: number = 0,
    status?: string
  ): Promise<{
    items: PipelineStatus[];
    total: number;
    hasNext: boolean;
  }> {
    try {
      const params = new URLSearchParams();
      params.append('limit', limit.toString());
      params.append('offset', offset.toString());
      if (status) params.append('status', status);

      const response = await apiService.get(`/pipeline/history?${params}`);
      return response.data;
    } catch (error) {
      console.error('Failed to get pipeline history:', error);
      throw error;
    }
  }

  /**
   * Get pipeline performance metrics
   */
  async getPipelineMetrics(timeRange: string = '24h'): Promise<{
    totalExecutions: number;
    successRate: number;
    averageDuration: number;
    phaseMetrics: { [phase: string]: any };
    aiModelUsage: { [model: string]: any };
  }> {
    try {
      const response = await apiService.get(`/pipeline/metrics?timeRange=${timeRange}`);
      return response.data;
    } catch (error) {
      console.error('Failed to get pipeline metrics:', error);
      throw error;
    }
  }

  /**
   * Get CLI-testable endpoints information
   */
  async getCliEndpoints(): Promise<{
    message: string;
    pipelineEndpoints: { [key: string]: any };
    contentEndpoints: { [key: string]: any };
    authentication: { [key: string]: any };
  }> {
    try {
      const response = await apiService.get('/cli/test-endpoints');
      return response.data;
    } catch (error) {
      console.error('Failed to get CLI endpoints:', error);
      throw error;
    }
  }

  /**
   * Validate pipeline configuration
   */
  async validateConfiguration(): Promise<{
    isValid: boolean;
    errors: string[];
    warnings: string[];
    aiModelsStatus: { [model: string]: any };
  }> {
    try {
      const response = await apiService.get('/pipeline/validate');
      return response.data;
    } catch (error) {
      console.error('Failed to validate pipeline configuration:', error);
      throw error;
    }
  }

  /**
   * Get pipeline phase definitions and descriptions
   */
  async getPhaseDefinitions(): Promise<{
    phases: Array<{
      id: string;
      name: string;
      description: string;
      subPhases?: Array<{
        id: string;
        name: string;
        description: string;
      }>;
      requiredModels: string[];
      estimatedDuration: number;
    }>;
  }> {
    try {
      const response = await apiService.get('/pipeline/phases/definitions');
      return response.data;
    } catch (error) {
      console.error('Failed to get phase definitions:', error);
      throw error;
    }
  }
}

export const pipelineService = new PipelineService();
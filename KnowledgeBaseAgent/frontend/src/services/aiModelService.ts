import { apiService } from './api';

export type ModelPhase = 'vision' | 'kb_generation' | 'synthesis' | 'chat' | 'embeddings';
export type ModelBackend = 'ollama' | 'localai' | 'openai';

export interface PhaseModelSelector {
  backend: ModelBackend;
  model: string;
  params?: { [key: string]: any };
}

export interface ModelConfiguration {
  perPhase: { [phase in ModelPhase]?: PhaseModelSelector };
}

export interface AvailableModel {
  name: string;
  backend: ModelBackend;
  capabilities: string[];
  size?: string;
  description?: string;
  isAvailable: boolean;
  lastTested?: string;
  responseTime?: number;
}

export interface BackendInfo {
  name: ModelBackend;
  isAvailable: boolean;
  url?: string;
  models: AvailableModel[];
  capabilities: { [model: string]: string[] };
  lastChecked?: string;
  error?: string;
}

export interface ModelTestResult {
  model: string;
  backend: ModelBackend;
  phase: ModelPhase;
  isAvailable: boolean;
  responseTime?: number;
  testPrompt: string;
  testResponse?: string;
  error?: string;
  timestamp: string;
}

export interface ModelUsageStats {
  model: string;
  backend: ModelBackend;
  phase: ModelPhase;
  totalCalls: number;
  successfulCalls: number;
  failedCalls: number;
  averageResponseTime: number;
  lastUsed?: string;
}

class AIModelService {
  /**
   * Get available models from all backends
   */
  async getAvailableModels(): Promise<{
    backends: { [backend: string]: BackendInfo };
  }> {
    try {
      const response = await apiService.get('/system/models/available');
      return response.data;
    } catch (error) {
      console.error('Failed to get available models:', error);
      throw error;
    }
  }

  /**
   * Get current model configuration
   */
  async getModelConfiguration(): Promise<ModelConfiguration> {
    try {
      const response = await apiService.get('/system/models/config');
      return response.data;
    } catch (error) {
      console.error('Failed to get model configuration:', error);
      throw error;
    }
  }

  /**
   * Update model configuration
   */
  async updateModelConfiguration(config: ModelConfiguration): Promise<ModelConfiguration> {
    try {
      const response = await apiService.put('/system/models/config', config);
      return response.data;
    } catch (error) {
      console.error('Failed to update model configuration:', error);
      throw error;
    }
  }

  /**
   * Test connectivity and capability of a specific model
   */
  async testModel(
    backend: ModelBackend,
    model: string,
    phase: ModelPhase,
    testPrompt?: string
  ): Promise<ModelTestResult> {
    try {
      const response = await apiService.post('/system/models/test', {
        backend,
        model,
        phase,
        testPrompt: testPrompt || this.getDefaultTestPrompt(phase)
      });
      return response.data;
    } catch (error) {
      console.error(`Failed to test model ${model}:`, error);
      throw error;
    }
  }

  /**
   * Test all configured models
   */
  async testAllModels(): Promise<{
    results: ModelTestResult[];
    summary: {
      total: number;
      passed: number;
      failed: number;
      duration: number;
    };
  }> {
    try {
      const response = await apiService.post('/system/models/test-all');
      return response.data;
    } catch (error) {
      console.error('Failed to test all models:', error);
      throw error;
    }
  }

  /**
   * Get model usage statistics
   */
  async getModelUsageStats(timeRange: string = '24h'): Promise<{
    stats: ModelUsageStats[];
    summary: {
      totalCalls: number;
      successRate: number;
      averageResponseTime: number;
      mostUsedModel: string;
      fastestModel: string;
    };
  }> {
    try {
      const response = await apiService.get(`/system/models/usage?timeRange=${timeRange}`);
      return response.data;
    } catch (error) {
      console.error('Failed to get model usage stats:', error);
      throw error;
    }
  }

  /**
   * Get model performance metrics for a specific phase
   */
  async getPhaseModelMetrics(phase: ModelPhase, timeRange: string = '24h'): Promise<{
    phase: ModelPhase;
    currentModel?: string;
    metrics: {
      totalCalls: number;
      successRate: number;
      averageResponseTime: number;
      errorRate: number;
    };
    alternatives: Array<{
      model: string;
      backend: ModelBackend;
      isAvailable: boolean;
      estimatedPerformance?: number;
    }>;
  }> {
    try {
      const response = await apiService.get(`/system/models/phases/${phase}/metrics?timeRange=${timeRange}`);
      return response.data;
    } catch (error) {
      console.error(`Failed to get metrics for phase ${phase}:`, error);
      throw error;
    }
  }

  /**
   * Validate model configuration for all phases
   */
  async validateConfiguration(): Promise<{
    isValid: boolean;
    errors: Array<{
      phase: ModelPhase;
      error: string;
      suggestion?: string;
    }>;
    warnings: Array<{
      phase: ModelPhase;
      warning: string;
      impact?: string;
    }>;
    recommendations: Array<{
      phase: ModelPhase;
      currentModel?: string;
      recommendedModel: string;
      reason: string;
    }>;
  }> {
    try {
      const response = await apiService.post('/system/models/validate');
      return response.data;
    } catch (error) {
      console.error('Failed to validate model configuration:', error);
      throw error;
    }
  }

  /**
   * Get model recommendations for a specific phase
   */
  async getModelRecommendations(phase: ModelPhase): Promise<{
    phase: ModelPhase;
    currentModel?: string;
    recommendations: Array<{
      model: string;
      backend: ModelBackend;
      score: number;
      reasons: string[];
      pros: string[];
      cons: string[];
      estimatedPerformance: {
        responseTime: number;
        accuracy: number;
        reliability: number;
      };
    }>;
  }> {
    try {
      const response = await apiService.get(`/system/models/phases/${phase}/recommendations`);
      return response.data;
    } catch (error) {
      console.error(`Failed to get recommendations for phase ${phase}:`, error);
      throw error;
    }
  }

  /**
   * Refresh model availability from all backends
   */
  async refreshModelAvailability(): Promise<{
    message: string;
    backends: { [backend: string]: BackendInfo };
    newModels: string[];
    unavailableModels: string[];
  }> {
    try {
      const response = await apiService.post('/system/models/refresh');
      return response.data;
    } catch (error) {
      console.error('Failed to refresh model availability:', error);
      throw error;
    }
  }

  /**
   * Get model capability matrix
   */
  async getModelCapabilities(): Promise<{
    phases: ModelPhase[];
    models: Array<{
      name: string;
      backend: ModelBackend;
      capabilities: { [phase in ModelPhase]?: boolean };
      performance: { [phase in ModelPhase]?: number };
      isRecommended: { [phase in ModelPhase]?: boolean };
    }>;
  }> {
    try {
      const response = await apiService.get('/system/models/capabilities');
      return response.data;
    } catch (error) {
      console.error('Failed to get model capabilities:', error);
      throw error;
    }
  }

  /**
   * Set fallback model for a phase
   */
  async setFallbackModel(
    phase: ModelPhase,
    fallbackModel: PhaseModelSelector
  ): Promise<{ message: string; phase: ModelPhase; fallbackModel: PhaseModelSelector }> {
    try {
      const response = await apiService.post(`/system/models/phases/${phase}/fallback`, {
        fallbackModel
      });
      return response.data;
    } catch (error) {
      console.error(`Failed to set fallback model for phase ${phase}:`, error);
      throw error;
    }
  }

  /**
   * Get model health status
   */
  async getModelHealthStatus(): Promise<{
    overall: 'healthy' | 'degraded' | 'critical';
    backends: { [backend: string]: 'healthy' | 'degraded' | 'down' };
    models: { [model: string]: 'healthy' | 'degraded' | 'unavailable' };
    issues: Array<{
      type: 'error' | 'warning';
      message: string;
      affectedPhases: ModelPhase[];
      recommendation?: string;
    }>;
  }> {
    try {
      const response = await apiService.get('/system/models/health');
      return response.data;
    } catch (error) {
      console.error('Failed to get model health status:', error);
      throw error;
    }
  }

  /**
   * Get default test prompt for a phase
   */
  private getDefaultTestPrompt(phase: ModelPhase): string {
    const prompts = {
      vision: 'Describe what you see in this image: [test image]',
      kb_generation: 'Generate a brief summary of this text: "This is a test for knowledge base generation."',
      synthesis: 'Create a synthesis of these topics: AI, machine learning, and data science.',
      chat: 'Hello, how are you today?',
      embeddings: 'Generate embeddings for: "test embedding generation"'
    };

    return prompts[phase] || 'Test prompt for model validation.';
  }

  /**
   * Export model configuration
   */
  async exportConfiguration(): Promise<{
    configuration: ModelConfiguration;
    metadata: {
      exportedAt: string;
      version: string;
      totalModels: number;
    };
  }> {
    try {
      const response = await apiService.get('/system/models/export');
      return response.data;
    } catch (error) {
      console.error('Failed to export model configuration:', error);
      throw error;
    }
  }

  /**
   * Import model configuration
   */
  async importConfiguration(configuration: ModelConfiguration): Promise<{
    message: string;
    imported: number;
    skipped: number;
    errors: string[];
  }> {
    try {
      const response = await apiService.post('/system/models/import', { configuration });
      return response.data;
    } catch (error) {
      console.error('Failed to import model configuration:', error);
      throw error;
    }
  }
}

export const aiModelService = new AIModelService();
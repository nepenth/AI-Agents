import { aiModelService } from '../aiModelService';
import { apiService } from '../api';

// Mock the API service
jest.mock('../api');
const mockApiService = apiService as jest.Mocked<typeof apiService>;

describe('AIModelService', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('getAvailableModels', () => {
    it('should get available models from all backends', async () => {
      const mockResponse = {
        data: {
          backends: {
            ollama: {
              name: 'ollama',
              isAvailable: true,
              url: 'http://localhost:11434',
              models: [
                {
                  name: 'llama2',
                  backend: 'ollama',
                  capabilities: ['text', 'chat'],
                  isAvailable: true,
                  responseTime: 1500
                }
              ],
              capabilities: {
                'llama2': ['text', 'chat']
              }
            },
            localai: {
              name: 'localai',
              isAvailable: false,
              error: 'Connection refused'
            }
          }
        }
      };

      mockApiService.get.mockResolvedValue(mockResponse);

      const result = await aiModelService.getAvailableModels();

      expect(mockApiService.get).toHaveBeenCalledWith('/system/models/available');
      expect(result).toEqual(mockResponse.data);
    });
  });

  describe('getModelConfiguration', () => {
    it('should get current model configuration', async () => {
      const mockResponse = {
        data: {
          perPhase: {
            vision: {
              backend: 'ollama',
              model: 'llava:13b',
              params: { temperature: 0.7 }
            },
            chat: {
              backend: 'localai',
              model: 'gpt-3.5-turbo',
              params: { max_tokens: 1000 }
            }
          }
        }
      };

      mockApiService.get.mockResolvedValue(mockResponse);

      const result = await aiModelService.getModelConfiguration();

      expect(mockApiService.get).toHaveBeenCalledWith('/system/models/config');
      expect(result).toEqual(mockResponse.data);
    });
  });

  describe('updateModelConfiguration', () => {
    it('should update model configuration successfully', async () => {
      const config = {
        perPhase: {
          vision: {
            backend: 'ollama' as const,
            model: 'llava:13b',
            params: { temperature: 0.8 }
          }
        }
      };

      const mockResponse = { data: config };
      mockApiService.put.mockResolvedValue(mockResponse);

      const result = await aiModelService.updateModelConfiguration(config);

      expect(mockApiService.put).toHaveBeenCalledWith('/system/models/config', config);
      expect(result).toEqual(config);
    });
  });

  describe('testModel', () => {
    it('should test model successfully', async () => {
      const mockResponse = {
        data: {
          model: 'llama2',
          backend: 'ollama',
          phase: 'chat',
          isAvailable: true,
          responseTime: 1200,
          testPrompt: 'Hello, how are you?',
          testResponse: 'I am doing well, thank you!',
          timestamp: '2024-01-01T12:00:00Z'
        }
      };

      mockApiService.post.mockResolvedValue(mockResponse);

      const result = await aiModelService.testModel('ollama', 'llama2', 'chat', 'Custom test prompt');

      expect(mockApiService.post).toHaveBeenCalledWith('/system/models/test', {
        backend: 'ollama',
        model: 'llama2',
        phase: 'chat',
        testPrompt: 'Custom test prompt'
      });
      expect(result).toEqual(mockResponse.data);
    });

    it('should use default test prompt when none provided', async () => {
      const mockResponse = {
        data: {
          model: 'llava',
          backend: 'ollama',
          phase: 'vision',
          isAvailable: true,
          responseTime: 2000,
          testPrompt: 'Describe what you see in this image: [test image]',
          testResponse: 'I can see a test image.',
          timestamp: '2024-01-01T12:00:00Z'
        }
      };

      mockApiService.post.mockResolvedValue(mockResponse);

      await aiModelService.testModel('ollama', 'llava', 'vision');

      expect(mockApiService.post).toHaveBeenCalledWith('/system/models/test', {
        backend: 'ollama',
        model: 'llava',
        phase: 'vision',
        testPrompt: 'Describe what you see in this image: [test image]'
      });
    });
  });

  describe('testAllModels', () => {
    it('should test all configured models', async () => {
      const mockResponse = {
        data: {
          results: [
            {
              model: 'llama2',
              backend: 'ollama',
              phase: 'chat',
              isAvailable: true,
              responseTime: 1200
            },
            {
              model: 'llava',
              backend: 'ollama',
              phase: 'vision',
              isAvailable: false,
              error: 'Model not found'
            }
          ],
          summary: {
            total: 2,
            passed: 1,
            failed: 1,
            duration: 3500
          }
        }
      };

      mockApiService.post.mockResolvedValue(mockResponse);

      const result = await aiModelService.testAllModels();

      expect(mockApiService.post).toHaveBeenCalledWith('/system/models/test-all');
      expect(result).toEqual(mockResponse.data);
    });
  });

  describe('getModelUsageStats', () => {
    it('should get model usage statistics', async () => {
      const mockResponse = {
        data: {
          stats: [
            {
              model: 'llama2',
              backend: 'ollama',
              phase: 'chat',
              totalCalls: 150,
              successfulCalls: 145,
              failedCalls: 5,
              averageResponseTime: 1200,
              lastUsed: '2024-01-01T11:30:00Z'
            }
          ],
          summary: {
            totalCalls: 150,
            successRate: 0.967,
            averageResponseTime: 1200,
            mostUsedModel: 'llama2',
            fastestModel: 'llama2'
          }
        }
      };

      mockApiService.get.mockResolvedValue(mockResponse);

      const result = await aiModelService.getModelUsageStats('7d');

      expect(mockApiService.get).toHaveBeenCalledWith('/system/models/usage?timeRange=7d');
      expect(result).toEqual(mockResponse.data);
    });
  });

  describe('getPhaseModelMetrics', () => {
    it('should get metrics for specific phase', async () => {
      const mockResponse = {
        data: {
          phase: 'vision',
          currentModel: 'llava:13b',
          metrics: {
            totalCalls: 50,
            successRate: 0.94,
            averageResponseTime: 2500,
            errorRate: 0.06
          },
          alternatives: [
            {
              model: 'llava:7b',
              backend: 'ollama',
              isAvailable: true,
              estimatedPerformance: 1800
            }
          ]
        }
      };

      mockApiService.get.mockResolvedValue(mockResponse);

      const result = await aiModelService.getPhaseModelMetrics('vision', '24h');

      expect(mockApiService.get).toHaveBeenCalledWith('/system/models/phases/vision/metrics?timeRange=24h');
      expect(result).toEqual(mockResponse.data);
    });
  });

  describe('validateConfiguration', () => {
    it('should validate model configuration', async () => {
      const mockResponse = {
        data: {
          isValid: false,
          errors: [
            {
              phase: 'vision',
              error: 'Model not available',
              suggestion: 'Try llava:7b instead'
            }
          ],
          warnings: [
            {
              phase: 'chat',
              warning: 'High response time',
              impact: 'May slow down processing'
            }
          ],
          recommendations: [
            {
              phase: 'embeddings',
              currentModel: 'text-embedding-ada-002',
              recommendedModel: 'all-MiniLM-L6-v2',
              reason: 'Better performance for local deployment'
            }
          ]
        }
      };

      mockApiService.post.mockResolvedValue(mockResponse);

      const result = await aiModelService.validateConfiguration();

      expect(mockApiService.post).toHaveBeenCalledWith('/system/models/validate');
      expect(result).toEqual(mockResponse.data);
    });
  });

  describe('getModelRecommendations', () => {
    it('should get recommendations for specific phase', async () => {
      const mockResponse = {
        data: {
          phase: 'kb_generation',
          currentModel: 'llama2',
          recommendations: [
            {
              model: 'mixtral:8x7b',
              backend: 'ollama',
              score: 0.92,
              reasons: ['Better reasoning capabilities', 'Faster response time'],
              pros: ['High accuracy', 'Good performance'],
              cons: ['Larger model size'],
              estimatedPerformance: {
                responseTime: 1800,
                accuracy: 0.95,
                reliability: 0.98
              }
            }
          ]
        }
      };

      mockApiService.get.mockResolvedValue(mockResponse);

      const result = await aiModelService.getModelRecommendations('kb_generation');

      expect(mockApiService.get).toHaveBeenCalledWith('/system/models/phases/kb_generation/recommendations');
      expect(result).toEqual(mockResponse.data);
    });
  });

  describe('refreshModelAvailability', () => {
    it('should refresh model availability from backends', async () => {
      const mockResponse = {
        data: {
          message: 'Model availability refreshed',
          backends: {
            ollama: {
              name: 'ollama',
              isAvailable: true,
              models: ['llama2', 'llava']
            }
          },
          newModels: ['qwen2.5:7b'],
          unavailableModels: ['gpt-4']
        }
      };

      mockApiService.post.mockResolvedValue(mockResponse);

      const result = await aiModelService.refreshModelAvailability();

      expect(mockApiService.post).toHaveBeenCalledWith('/system/models/refresh');
      expect(result).toEqual(mockResponse.data);
    });
  });

  describe('getModelCapabilities', () => {
    it('should get model capability matrix', async () => {
      const mockResponse = {
        data: {
          phases: ['vision', 'kb_generation', 'synthesis', 'chat', 'embeddings'],
          models: [
            {
              name: 'llama2',
              backend: 'ollama',
              capabilities: {
                chat: true,
                kb_generation: true,
                synthesis: true
              },
              performance: {
                chat: 0.85,
                kb_generation: 0.78,
                synthesis: 0.82
              },
              isRecommended: {
                chat: true,
                kb_generation: false,
                synthesis: true
              }
            }
          ]
        }
      };

      mockApiService.get.mockResolvedValue(mockResponse);

      const result = await aiModelService.getModelCapabilities();

      expect(mockApiService.get).toHaveBeenCalledWith('/system/models/capabilities');
      expect(result).toEqual(mockResponse.data);
    });
  });

  describe('setFallbackModel', () => {
    it('should set fallback model for phase', async () => {
      const fallbackModel = {
        backend: 'ollama' as const,
        model: 'llama2:7b',
        params: { temperature: 0.5 }
      };

      const mockResponse = {
        data: {
          message: 'Fallback model set successfully',
          phase: 'chat',
          fallbackModel
        }
      };

      mockApiService.post.mockResolvedValue(mockResponse);

      const result = await aiModelService.setFallbackModel('chat', fallbackModel);

      expect(mockApiService.post).toHaveBeenCalledWith('/system/models/phases/chat/fallback', {
        fallbackModel
      });
      expect(result).toEqual(mockResponse.data);
    });
  });

  describe('getModelHealthStatus', () => {
    it('should get model health status', async () => {
      const mockResponse = {
        data: {
          overall: 'degraded',
          backends: {
            ollama: 'healthy',
            localai: 'down',
            openai: 'degraded'
          },
          models: {
            'llama2': 'healthy',
            'gpt-3.5-turbo': 'unavailable',
            'llava:13b': 'degraded'
          },
          issues: [
            {
              type: 'error',
              message: 'LocalAI backend is not responding',
              affectedPhases: ['embeddings'],
              recommendation: 'Check LocalAI service status'
            },
            {
              type: 'warning',
              message: 'High response times detected',
              affectedPhases: ['vision'],
              recommendation: 'Consider using a smaller model'
            }
          ]
        }
      };

      mockApiService.get.mockResolvedValue(mockResponse);

      const result = await aiModelService.getModelHealthStatus();

      expect(mockApiService.get).toHaveBeenCalledWith('/system/models/health');
      expect(result).toEqual(mockResponse.data);
    });
  });

  describe('exportConfiguration', () => {
    it('should export model configuration', async () => {
      const mockResponse = {
        data: {
          configuration: {
            perPhase: {
              chat: {
                backend: 'ollama',
                model: 'llama2',
                params: {}
              }
            }
          },
          metadata: {
            exportedAt: '2024-01-01T12:00:00Z',
            version: '1.0.0',
            totalModels: 5
          }
        }
      };

      mockApiService.get.mockResolvedValue(mockResponse);

      const result = await aiModelService.exportConfiguration();

      expect(mockApiService.get).toHaveBeenCalledWith('/system/models/export');
      expect(result).toEqual(mockResponse.data);
    });
  });

  describe('importConfiguration', () => {
    it('should import model configuration', async () => {
      const configuration = {
        perPhase: {
          chat: {
            backend: 'ollama' as const,
            model: 'llama2',
            params: {}
          }
        }
      };

      const mockResponse = {
        data: {
          message: 'Configuration imported successfully',
          imported: 1,
          skipped: 0,
          errors: []
        }
      };

      mockApiService.post.mockResolvedValue(mockResponse);

      const result = await aiModelService.importConfiguration(configuration);

      expect(mockApiService.post).toHaveBeenCalledWith('/system/models/import', { configuration });
      expect(result).toEqual(mockResponse.data);
    });
  });
});
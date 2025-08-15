import { pipelineService } from '../pipelineService';
import { apiService } from '../api';

// Mock the API service
jest.mock('../api');
const mockApiService = apiService as jest.Mocked<typeof apiService>;

describe('PipelineService', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('executePipeline', () => {
    it('should execute pipeline successfully', async () => {
      const mockResponse = {
        data: {
          taskId: 'task-123',
          status: 'started',
          message: 'Pipeline execution started',
          estimatedDuration: 300
        }
      };

      mockApiService.post.mockResolvedValue(mockResponse);

      const request = {
        tweetId: '1234567890',
        forceReprocess: false
      };

      const result = await pipelineService.executePipeline(request);

      expect(mockApiService.post).toHaveBeenCalledWith('/pipeline/execute', request);
      expect(result).toEqual(mockResponse.data);
    });

    it('should handle pipeline execution errors', async () => {
      const error = new Error('Pipeline execution failed');
      mockApiService.post.mockRejectedValue(error);

      const request = {
        tweetId: '1234567890'
      };

      await expect(pipelineService.executePipeline(request)).rejects.toThrow('Pipeline execution failed');
    });
  });

  describe('executePhase', () => {
    it('should execute specific phase successfully', async () => {
      const mockResponse = {
        data: {
          taskId: 'phase-task-123',
          status: 'started',
          message: 'Phase 2 execution started'
        }
      };

      mockApiService.post.mockResolvedValue(mockResponse);

      const result = await pipelineService.executePhase(2, { maxResults: 100 }, true);

      expect(mockApiService.post).toHaveBeenCalledWith('/pipeline/phases/2/execute', {
        config: { maxResults: 100 },
        forceReprocess: true
      });
      expect(result).toEqual(mockResponse.data);
    });

    it('should handle phase execution errors', async () => {
      const error = new Error('Phase execution failed');
      mockApiService.post.mockRejectedValue(error);

      await expect(pipelineService.executePhase(3)).rejects.toThrow('Phase execution failed');
    });
  });

  describe('getPipelineStatus', () => {
    it('should get pipeline status successfully', async () => {
      const mockResponse = {
        data: {
          overallStatus: 'running',
          phases: {
            '1': { status: 'completed', progress: 100 },
            '2': { status: 'running', progress: 50 }
          },
          activeTasks: ['task-123'],
          lastUpdated: '2024-01-01T12:00:00Z'
        }
      };

      mockApiService.get.mockResolvedValue(mockResponse);

      const result = await pipelineService.getPipelineStatus();

      expect(mockApiService.get).toHaveBeenCalledWith('/pipeline/status');
      expect(result).toEqual(mockResponse.data);
    });
  });

  describe('getTaskStatus', () => {
    it('should get task status successfully', async () => {
      const mockResponse = {
        data: {
          taskId: 'task-123',
          overallStatus: 'completed',
          phases: {
            'phase_1': { status: 'completed', duration: 1500 },
            'phase_2': { status: 'completed', duration: 2000 }
          },
          totalDuration: 3500,
          tweetId: '1234567890'
        }
      };

      mockApiService.get.mockResolvedValue(mockResponse);

      const result = await pipelineService.getTaskStatus('task-123');

      expect(mockApiService.get).toHaveBeenCalledWith('/pipeline/tasks/task-123/status');
      expect(result).toEqual(mockResponse.data);
    });
  });

  describe('getSubPhaseStatus', () => {
    it('should get sub-phase status with filters', async () => {
      const mockResponse = {
        data: [
          {
            contentId: 'content-1',
            bookmarkCached: true,
            mediaAnalyzed: false,
            contentUnderstood: false,
            categorized: false,
            completionPercentage: 25.0,
            isFullyProcessed: false,
            lastUpdated: '2024-01-01T12:00:00Z',
            processingErrors: []
          }
        ]
      };

      mockApiService.get.mockResolvedValue(mockResponse);

      const result = await pipelineService.getSubPhaseStatus('cached', true, 50);

      expect(mockApiService.get).toHaveBeenCalledWith(
        '/content/sub-phases/status?processing_state=cached&incomplete_only=true&limit=50'
      );
      expect(result).toEqual(mockResponse.data);
    });

    it('should get sub-phase status without filters', async () => {
      const mockResponse = { data: [] };
      mockApiService.get.mockResolvedValue(mockResponse);

      await pipelineService.getSubPhaseStatus();

      expect(mockApiService.get).toHaveBeenCalledWith(
        '/content/sub-phases/status?limit=100'
      );
    });
  });

  describe('resetSubPhaseStatus', () => {
    it('should reset sub-phase status successfully', async () => {
      const mockResponse = {
        data: {
          message: 'Reset phases for content item',
          contentId: 'content-1',
          resetPhases: ['media_analyzed', 'content_understood']
        }
      };

      mockApiService.post.mockResolvedValue(mockResponse);

      const result = await pipelineService.resetSubPhaseStatus('content-1', ['media_analyzed', 'content_understood']);

      expect(mockApiService.post).toHaveBeenCalledWith(
        '/content/sub-phases/content-1/reset?phases=media_analyzed&phases=content_understood'
      );
      expect(result).toEqual(mockResponse.data);
    });
  });

  describe('getPipelineHistory', () => {
    it('should get pipeline history with pagination', async () => {
      const mockResponse = {
        data: {
          items: [
            {
              taskId: 'task-1',
              overallStatus: 'completed',
              startTime: '2024-01-01T10:00:00Z',
              endTime: '2024-01-01T10:05:00Z',
              totalDuration: 300000
            }
          ],
          total: 1,
          hasNext: false
        }
      };

      mockApiService.get.mockResolvedValue(mockResponse);

      const result = await pipelineService.getPipelineHistory(25, 10, 'completed');

      expect(mockApiService.get).toHaveBeenCalledWith(
        '/pipeline/history?limit=25&offset=10&status=completed'
      );
      expect(result).toEqual(mockResponse.data);
    });
  });

  describe('getPipelineMetrics', () => {
    it('should get pipeline metrics for time range', async () => {
      const mockResponse = {
        data: {
          totalExecutions: 150,
          successRate: 0.95,
          averageDuration: 280.5,
          phaseMetrics: {
            'phase_1': { averageDuration: 15.2, successRate: 0.99 },
            'phase_2': { averageDuration: 45.8, successRate: 0.97 }
          },
          aiModelUsage: {
            'llama2': { calls: 75, successRate: 0.94 },
            'gpt-3.5': { calls: 50, successRate: 0.98 }
          }
        }
      };

      mockApiService.get.mockResolvedValue(mockResponse);

      const result = await pipelineService.getPipelineMetrics('7d');

      expect(mockApiService.get).toHaveBeenCalledWith('/pipeline/metrics?timeRange=7d');
      expect(result).toEqual(mockResponse.data);
    });
  });

  describe('validateConfiguration', () => {
    it('should validate pipeline configuration', async () => {
      const mockResponse = {
        data: {
          isValid: true,
          errors: [],
          warnings: ['AI model response time is high'],
          aiModelsStatus: {
            'llama2': { available: true, responseTime: 1500 },
            'gpt-3.5': { available: false, error: 'API key invalid' }
          }
        }
      };

      mockApiService.get.mockResolvedValue(mockResponse);

      const result = await pipelineService.validateConfiguration();

      expect(mockApiService.get).toHaveBeenCalledWith('/pipeline/validate');
      expect(result).toEqual(mockResponse.data);
    });
  });

  describe('getPhaseDefinitions', () => {
    it('should get phase definitions successfully', async () => {
      const mockResponse = {
        data: {
          phases: [
            {
              id: 'phase_1',
              name: 'System Initialization',
              description: 'Initialize system components',
              requiredModels: [],
              estimatedDuration: 15
            },
            {
              id: 'phase_2',
              name: 'Fetch Bookmarks',
              description: 'Retrieve Twitter bookmarks',
              subPhases: [
                {
                  id: 'phase_2_1',
                  name: 'Bookmark Caching',
                  description: 'Cache bookmark content'
                }
              ],
              requiredModels: [],
              estimatedDuration: 45
            }
          ]
        }
      };

      mockApiService.get.mockResolvedValue(mockResponse);

      const result = await pipelineService.getPhaseDefinitions();

      expect(mockApiService.get).toHaveBeenCalledWith('/pipeline/phases/definitions');
      expect(result).toEqual(mockResponse.data);
    });
  });

  describe('cancelTask', () => {
    it('should cancel task successfully', async () => {
      const mockResponse = {
        data: {
          message: 'Task cancelled successfully',
          taskId: 'task-123'
        }
      };

      mockApiService.post.mockResolvedValue(mockResponse);

      const result = await pipelineService.cancelTask('task-123');

      expect(mockApiService.post).toHaveBeenCalledWith('/pipeline/tasks/task-123/cancel');
      expect(result).toEqual(mockResponse.data);
    });
  });

  describe('getCliEndpoints', () => {
    it('should get CLI endpoints information', async () => {
      const mockResponse = {
        data: {
          message: 'CLI-testable endpoints',
          pipelineEndpoints: {
            execute_phase: {
              url: '/api/v1/pipeline/phases/{phase}/execute',
              method: 'POST'
            }
          },
          contentEndpoints: {
            twitter_bookmarks: {
              url: '/api/v1/content/twitter/bookmarks',
              method: 'GET'
            }
          },
          authentication: {
            note: 'All endpoints require authentication'
          }
        }
      };

      mockApiService.get.mockResolvedValue(mockResponse);

      const result = await pipelineService.getCliEndpoints();

      expect(mockApiService.get).toHaveBeenCalledWith('/cli/test-endpoints');
      expect(result).toEqual(mockResponse.data);
    });
  });
});
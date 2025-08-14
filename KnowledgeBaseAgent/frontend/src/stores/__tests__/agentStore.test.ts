import { describe, it, expect, beforeEach, vi } from 'vitest';
import { useAgentStore } from '../agentStore';
import { agentService } from '@/services/agentService';

// Mock the agent service
vi.mock('@/services/agentService', () => ({
  agentService: {
    startAgent: vi.fn(),
    stopAgent: vi.fn(),
    getSystemMetrics: vi.fn(),
    getTaskHistory: vi.fn(),
  },
}));

// Mock WebSocket service
vi.mock('@/services/websocket', () => ({
  websocketService: {
    subscribe: vi.fn(() => () => {}),
  },
}));

describe('agentStore', () => {
  beforeEach(() => {
    useAgentStore.getState().reset();
    vi.clearAllMocks();
  });

  it('should have initial state', () => {
    const state = useAgentStore.getState();
    
    expect(state.currentTask).toBe(null);
    expect(state.isRunning).toBe(false);
    expect(state.progress).toBe(0);
    expect(state.loading).toBe(false);
    expect(state.error).toBe(null);
  });

  it('should start agent successfully', async () => {
    const mockTask = {
      id: 'task-1',
      status: 'running' as const,
      current_phase: 'Processing',
      progress_percentage: 0,
      task_type: 'content_processing',
      config: {},
      created_at: '2024-01-01T00:00:00Z',
    };

    (agentService.startAgent as any).mockResolvedValue(mockTask);

    const config = {
      sources: { twitter_enabled: true, web_scraping_enabled: false, file_upload_enabled: false },
      processing: { ai_backend: 'ollama', model: 'llama2', batch_size: 10 },
      categories: ['tech', 'ai'],
    };

    await useAgentStore.getState().startAgent(config);

    const state = useAgentStore.getState();
    expect(state.currentTask).toEqual(mockTask);
    expect(state.isRunning).toBe(true);
    expect(state.loading).toBe(false);
    expect(state.error).toBe(null);
  });

  it('should handle start agent error', async () => {
    const mockError = new Error('Failed to start agent');
    (agentService.startAgent as any).mockRejectedValue(mockError);

    const config = {
      sources: { twitter_enabled: true, web_scraping_enabled: false, file_upload_enabled: false },
      processing: { ai_backend: 'ollama', model: 'llama2', batch_size: 10 },
      categories: ['tech'],
    };

    await expect(useAgentStore.getState().startAgent(config)).rejects.toThrow(mockError);

    const state = useAgentStore.getState();
    expect(state.error).toBe('Failed to start agent');
    expect(state.loading).toBe(false);
  });

  it('should load system metrics', async () => {
    const mockMetrics = {
      cpu_usage: 0.5,
      memory_usage: 0.7,
      disk_usage: 0.3,
      active_tasks: 2,
      queue_size: 5,
      uptime: 3600,
    };

    (agentService.getSystemMetrics as any).mockResolvedValue(mockMetrics);

    await useAgentStore.getState().loadSystemMetrics();

    const state = useAgentStore.getState();
    expect(state.systemMetrics).toEqual(mockMetrics);
  });

  it('should update progress', () => {
    const progressUpdate = {
      task_id: 'task-1',
      progress: 50,
      phase: 'Processing content',
      message: 'Processing 50 items',
      timestamp: '2024-01-01T00:00:00Z',
    };

    // Set current task first
    useAgentStore.setState({
      currentTask: {
        id: 'task-1',
        status: 'running',
        current_phase: 'Starting',
        progress_percentage: 0,
        task_type: 'content_processing',
        config: {},
        created_at: '2024-01-01T00:00:00Z',
      },
    });

    useAgentStore.getState().updateProgress(progressUpdate);

    const state = useAgentStore.getState();
    expect(state.progress).toBe(50);
    expect(state.currentPhase).toBe('Processing content');
  });
});
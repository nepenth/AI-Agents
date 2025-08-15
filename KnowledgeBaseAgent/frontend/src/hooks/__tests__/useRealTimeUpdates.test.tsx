import { renderHook, act } from '@testing-library/react';
import { useRealTimeUpdates, usePipelineUpdates } from '../useRealTimeUpdates';
import { useWebSocket } from '../useWebSocket';

// Mock the useWebSocket hook
jest.mock('../useWebSocket');
const mockUseWebSocket = useWebSocket as jest.MockedFunction<typeof useWebSocket>;

describe('useRealTimeUpdates', () => {
  const mockSubscribe = jest.fn();
  const mockSend = jest.fn();
  
  beforeEach(() => {
    mockUseWebSocket.mockReturnValue({
      subscribe: mockSubscribe,
      send: mockSend,
      isConnected: true,
      connectionState: 'connected'
    });
    
    mockSubscribe.mockImplementation((event: string, handler: Function) => {
      // Return unsubscribe function
      return () => {};
    });
    
    jest.clearAllMocks();
  });

  it('should initialize with correct default values', () => {
    const { result } = renderHook(() => useRealTimeUpdates());
    
    expect(result.current.isConnected).toBe(true);
    expect(result.current.connectionState).toBe('connected');
    expect(result.current.lastUpdate).toBeNull();
    expect(result.current.updateCount).toBe(0);
  });

  it('should subscribe to pipeline updates', () => {
    const onPipelineUpdate = jest.fn();
    
    renderHook(() => useRealTimeUpdates({ onPipelineUpdate }));
    
    expect(mockSubscribe).toHaveBeenCalledWith('pipeline_update', expect.any(Function));
  });

  it('should handle pipeline updates correctly', () => {
    const onPipelineUpdate = jest.fn();
    let pipelineHandler: Function;
    
    mockSubscribe.mockImplementation((event: string, handler: Function) => {
      if (event === 'pipeline_update') {
        pipelineHandler = handler;
      }
      return () => {};
    });
    
    const { result } = renderHook(() => useRealTimeUpdates({ onPipelineUpdate }));
    
    const pipelineUpdate = {
      phase: 'phase_1',
      status: 'running' as const,
      progress: 50,
      timestamp: '2024-01-01T12:00:00Z'
    };
    
    act(() => {
      pipelineHandler(pipelineUpdate);
    });
    
    expect(onPipelineUpdate).toHaveBeenCalledWith(pipelineUpdate);
    expect(result.current.lastUpdate).toEqual({
      type: 'pipeline',
      data: pipelineUpdate,
      timestamp: expect.any(String)
    });
    expect(result.current.updateCount).toBe(1);
  });

  it('should handle AI model updates', () => {
    const onSystemUpdate = jest.fn();
    let aiModelHandler: Function;
    
    mockSubscribe.mockImplementation((event: string, handler: Function) => {
      if (event === 'ai_model_update') {
        aiModelHandler = handler;
      }
      return () => {};
    });
    
    renderHook(() => useRealTimeUpdates({ onSystemUpdate }));
    
    const aiModelUpdate = {
      model: 'llama2',
      status: 'available',
      responseTime: 1500
    };
    
    act(() => {
      aiModelHandler(aiModelUpdate);
    });
    
    expect(onSystemUpdate).toHaveBeenCalledWith({
      type: 'ai_model',
      data: aiModelUpdate,
      timestamp: expect.any(String)
    });
  });

  it('should handle system health updates', () => {
    const onSystemUpdate = jest.fn();
    let healthHandler: Function;
    
    mockSubscribe.mockImplementation((event: string, handler: Function) => {
      if (event === 'system_health') {
        healthHandler = handler;
      }
      return () => {};
    });
    
    renderHook(() => useRealTimeUpdates({ onSystemUpdate }));
    
    const healthUpdate = {
      database: 'healthy',
      aiServices: 'degraded',
      twitterAPI: 'healthy'
    };
    
    act(() => {
      healthHandler(healthUpdate);
    });
    
    expect(onSystemUpdate).toHaveBeenCalledWith({
      type: 'system_health',
      data: healthUpdate,
      timestamp: expect.any(String)
    });
  });

  it('should handle error updates', () => {
    const onError = jest.fn();
    let errorHandler: Function;
    
    mockSubscribe.mockImplementation((event: string, handler: Function) => {
      if (event === 'error') {
        errorHandler = handler;
      }
      return () => {};
    });
    
    renderHook(() => useRealTimeUpdates({ onError }));
    
    const errorUpdate = {
      type: 'ai_model_error',
      message: 'Model not available',
      phase: 'phase_3_1'
    };
    
    act(() => {
      errorHandler(errorUpdate);
    });
    
    expect(onError).toHaveBeenCalledWith(errorUpdate);
  });

  it('should provide control methods', () => {
    const { result } = renderHook(() => useRealTimeUpdates());
    
    act(() => {
      result.current.subscribeToPipeline('task-123');
    });
    
    expect(mockSend).toHaveBeenCalledWith('subscribe_pipeline', { taskId: 'task-123' });
    
    act(() => {
      result.current.unsubscribeFromPipeline('task-123');
    });
    
    expect(mockSend).toHaveBeenCalledWith('unsubscribe_pipeline', { taskId: 'task-123' });
    
    act(() => {
      result.current.requestSystemStatus();
    });
    
    expect(mockSend).toHaveBeenCalledWith('request_system_status', {});
    
    act(() => {
      result.current.requestPipelineStatus('task-123');
    });
    
    expect(mockSend).toHaveBeenCalledWith('request_pipeline_status', { taskId: 'task-123' });
  });
});

describe('usePipelineUpdates', () => {
  const mockSubscribe = jest.fn();
  const mockSend = jest.fn();
  
  beforeEach(() => {
    mockUseWebSocket.mockReturnValue({
      subscribe: mockSubscribe,
      send: mockSend,
      isConnected: true,
      connectionState: 'connected'
    });
    
    mockSubscribe.mockImplementation((event: string, handler: Function) => {
      return () => {};
    });
    
    jest.clearAllMocks();
  });

  it('should initialize with empty pipeline status', () => {
    const { result } = renderHook(() => usePipelineUpdates());
    
    expect(result.current.pipelineStatus).toEqual({});
    expect(result.current.overallProgress).toBe(0);
    expect(result.current.isProcessing).toBe(false);
  });

  it('should subscribe to pipeline for specific task ID', () => {
    const taskId = 'task-123';
    
    renderHook(() => usePipelineUpdates(taskId));
    
    expect(mockSend).toHaveBeenCalledWith('subscribe_pipeline', { taskId });
  });

  it('should update pipeline status on pipeline updates', () => {
    let pipelineHandler: Function;
    
    mockSubscribe.mockImplementation((event: string, handler: Function) => {
      if (event === 'pipeline_update') {
        pipelineHandler = handler;
      }
      return () => {};
    });
    
    const { result } = renderHook(() => usePipelineUpdates());
    
    const update1 = {
      phase: 'phase_1',
      status: 'completed' as const,
      progress: 100,
      timestamp: '2024-01-01T12:00:00Z'
    };
    
    const update2 = {
      phase: 'phase_2',
      status: 'running' as const,
      progress: 50,
      timestamp: '2024-01-01T12:01:00Z'
    };
    
    act(() => {
      pipelineHandler(update1);
    });
    
    expect(result.current.pipelineStatus).toEqual({
      phase_1: update1
    });
    
    act(() => {
      pipelineHandler(update2);
    });
    
    expect(result.current.pipelineStatus).toEqual({
      phase_1: update1,
      phase_2: update2
    });
    
    expect(result.current.isProcessing).toBe(true);
  });

  it('should calculate overall progress correctly', () => {
    let pipelineHandler: Function;
    
    mockSubscribe.mockImplementation((event: string, handler: Function) => {
      if (event === 'pipeline_update') {
        pipelineHandler = handler;
      }
      return () => {};
    });
    
    const { result } = renderHook(() => usePipelineUpdates());
    
    // Add 3 phases, 2 completed
    act(() => {
      pipelineHandler({ phase: 'phase_1', status: 'completed', timestamp: '2024-01-01T12:00:00Z' });
    });
    
    act(() => {
      pipelineHandler({ phase: 'phase_2', status: 'completed', timestamp: '2024-01-01T12:01:00Z' });
    });
    
    act(() => {
      pipelineHandler({ phase: 'phase_3', status: 'running', timestamp: '2024-01-01T12:02:00Z' });
    });
    
    // Should be 66.67% (2 out of 3 completed)
    expect(result.current.overallProgress).toBeCloseTo(66.67, 1);
  });

  it('should detect when processing is complete', () => {
    let pipelineHandler: Function;
    
    mockSubscribe.mockImplementation((event: string, handler: Function) => {
      if (event === 'pipeline_update') {
        pipelineHandler = handler;
      }
      return () => {};
    });
    
    const { result } = renderHook(() => usePipelineUpdates());
    
    // Add running phase
    act(() => {
      pipelineHandler({ phase: 'phase_1', status: 'running', timestamp: '2024-01-01T12:00:00Z' });
    });
    
    expect(result.current.isProcessing).toBe(true);
    
    // Complete the phase
    act(() => {
      pipelineHandler({ phase: 'phase_1', status: 'completed', timestamp: '2024-01-01T12:01:00Z' });
    });
    
    expect(result.current.isProcessing).toBe(false);
  });

  it('should unsubscribe when task ID changes', () => {
    const unsubscribeMock = jest.fn();
    
    mockSend.mockImplementation((type: string, payload: any) => {
      if (type === 'unsubscribe_pipeline') {
        unsubscribeMock(payload.taskId);
      }
    });
    
    const { rerender } = renderHook(
      ({ taskId }) => usePipelineUpdates(taskId),
      { initialProps: { taskId: 'task-1' } }
    );
    
    expect(mockSend).toHaveBeenCalledWith('subscribe_pipeline', { taskId: 'task-1' });
    
    // Change task ID
    rerender({ taskId: 'task-2' });
    
    expect(unsubscribeMock).toHaveBeenCalledWith('task-1');
    expect(mockSend).toHaveBeenCalledWith('subscribe_pipeline', { taskId: 'task-2' });
  });
});
import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import { Task, SystemMetrics, ProgressUpdate } from '@/types';
import { agentService, AgentConfig } from '@/services/agentService';
import { websocketService } from '@/services/websocket';

interface AgentState {
  // Current task state
  currentTask: Task | null;
  isRunning: boolean;
  progress: number;
  currentPhase: string;

  // System metrics
  systemMetrics: SystemMetrics | null;
  systemHealth: { status: string; checks: Record<string, boolean> } | null;

  // Task history
  taskHistory: Task[];
  taskHistoryLoading: boolean;
  taskHistoryTotal: number;

  // System logs
  systemLogs: Array<{
    timestamp: string;
    level: string;
    message: string;
    module: string;
    channel?: string;
    task_id?: string;
    pipeline_phase?: string;
    details?: Record<string, any>;
  }>;
  systemLogsLoading: boolean;
  logChannelStats?: Record<string, number>;
  availableLogChannels?: string[];

  // Loading states
  loading: boolean;
  error: string | null;

  // Actions
  startAgent: (config: AgentConfig) => Promise<void>;
  stopAgent: () => Promise<void>;
  pauseAgent: () => Promise<void>;
  resumeAgent: () => Promise<void>;
  cancelTask: (taskId: string) => Promise<void>;

  // Data fetching
  loadSystemMetrics: () => Promise<void>;
  loadSystemHealth: () => Promise<void>;
  loadTaskHistory: (params?: any) => Promise<void>;
  loadSystemLogs: (params?: any) => Promise<void>;

  // Real-time updates
  updateProgress: (update: ProgressUpdate) => void;
  updateTaskStatus: (task: Task) => void;

  // Utility
  clearError: () => void;
  reset: () => void;
}

export const useAgentStore = create<AgentState>()(
  devtools(
    (set, get) => ({
      // Initial state
      currentTask: null,
      isRunning: false,
      progress: 0,
      currentPhase: '',
      systemMetrics: null,
      systemHealth: null,
      taskHistory: [],
      taskHistoryLoading: false,
      taskHistoryTotal: 0,
      systemLogs: [],
      systemLogsLoading: false,
      loading: false,
      error: null,

      // Actions
      startAgent: async (config: AgentConfig) => {
        set({ loading: true, error: null });
        try {
          const task = await agentService.startAgent({ config });
          set({
            currentTask: task,
            isRunning: true,
            progress: 0,
            currentPhase: task.current_phase || 'Starting...',
            loading: false,
          });
        } catch (error) {
          set({
            error: error instanceof Error ? error.message : 'Failed to start agent',
            loading: false,
          });
          throw error;
        }
      },

      stopAgent: async () => {
        const { currentTask } = get();
        if (!currentTask) return;

        set({ loading: true, error: null });
        try {
          await agentService.stopAgent(currentTask.id);
          set({
            isRunning: false,
            currentPhase: 'Stopped',
            loading: false,
          });
        } catch (error) {
          set({
            error: error instanceof Error ? error.message : 'Failed to stop agent',
            loading: false,
          });
          throw error;
        }
      },

      pauseAgent: async () => {
        const { currentTask } = get();
        if (!currentTask) return;

        try {
          await agentService.pauseAgent(currentTask.id);
          set({ currentPhase: 'Paused' });
        } catch (error) {
          set({
            error: error instanceof Error ? error.message : 'Failed to pause agent',
          });
          throw error;
        }
      },

      resumeAgent: async () => {
        const { currentTask } = get();
        if (!currentTask) return;

        try {
          await agentService.resumeAgent(currentTask.id);
          set({ currentPhase: 'Resuming...' });
        } catch (error) {
          set({
            error: error instanceof Error ? error.message : 'Failed to resume agent',
          });
          throw error;
        }
      },

      cancelTask: async (taskId: string) => {
        try {
          await agentService.cancelTask(taskId);
          const { taskHistory } = get();
          set({
            taskHistory: taskHistory.map(task =>
              task.id === taskId ? { ...task, status: 'cancelled' } : task
            ),
          });
        } catch (error) {
          set({
            error: error instanceof Error ? error.message : 'Failed to cancel task',
          });
          throw error;
        }
      },

      loadSystemMetrics: async () => {
        try {
          const metrics = await agentService.getSystemMetrics();
          set({ systemMetrics: metrics });
        } catch (error) {
          console.error('Failed to load system metrics:', error);
        }
      },

      loadSystemHealth: async () => {
        try {
          const health = await agentService.getSystemHealth();
          set({ systemHealth: health });
        } catch (error) {
          console.error('Failed to load system health:', error);
        }
      },

      loadTaskHistory: async (params = {}) => {
        set({ taskHistoryLoading: true });
        try {
          const response = await agentService.getTaskHistory(params);
          set({
            taskHistory: response.items,
            taskHistoryTotal: response.total,
            taskHistoryLoading: false,
          });
        } catch (error) {
          set({
            error: error instanceof Error ? error.message : 'Failed to load task history',
            taskHistoryLoading: false,
          });
        }
      },

      loadSystemLogs: async (params = {}) => {
        set({ systemLogsLoading: true });
        try {
          const response = await agentService.getSystemLogs({
            limit: 100,
            offset: 0,
            ...params
          });
          set({
            systemLogs: response.logs || [],
            logChannelStats: response.channel_stats,
            availableLogChannels: response.available_channels,
            systemLogsLoading: false,
          });
        } catch (error) {
          console.error('Failed to load system logs:', error);
          set({
            error: error instanceof Error ? error.message : 'Failed to load system logs',
            systemLogsLoading: false,
            systemLogs: [], // Set empty array on error
          });
        }
      },

      updateProgress: (update: ProgressUpdate) => {
        const { currentTask } = get();
        if (currentTask && currentTask.id === update.task_id) {
          set({
            progress: update.progress,
            currentPhase: update.phase,
          });
        }
      },

      updateTaskStatus: (task: Task) => {
        const { currentTask, taskHistory } = get();

        // Update current task if it matches
        if (currentTask && currentTask.id === task.id) {
          set({
            currentTask: task,
            isRunning: task.status === 'running',
            progress: task.progress_percentage,
            currentPhase: task.current_phase || '',
          });
        }

        // Update task in history
        set({
          taskHistory: taskHistory.map(t => t.id === task.id ? task : t),
        });
      },

      clearError: () => set({ error: null }),

      reset: () => set({
        currentTask: null,
        isRunning: false,
        progress: 0,
        currentPhase: '',
        error: null,
        loading: false,
      }),
    }),
    {
      name: 'agent-store',
    }
  )
);

// Set up WebSocket listeners for real-time updates
websocketService.subscribe('task_progress', (data: ProgressUpdate) => {
  useAgentStore.getState().updateProgress(data);
});

websocketService.subscribe('task_status', (data: Task) => {
  useAgentStore.getState().updateTaskStatus(data);
});

websocketService.subscribe('system_metrics', (data: SystemMetrics) => {
  useAgentStore.setState({ systemMetrics: data });
});
import { apiService } from './api';
import { Task, SystemMetrics, PaginatedResponse } from '@/types';

export interface AgentConfig {
  sources: {
    twitter_enabled: boolean;
    web_scraping_enabled: boolean;
    file_upload_enabled: boolean;
  };
  processing: {
    ai_backend: string;
    model: string;
    batch_size: number;
  };
  categories: string[];
}

export interface StartAgentRequest {
  config: AgentConfig;
  schedule?: string; // Cron expression for scheduling
}

export interface TaskHistoryParams {
  page?: number;
  page_size?: number;
  status?: string;
  task_type?: string;
  date_from?: string;
  date_to?: string;
}

export class AgentService {
  async startAgent(request: StartAgentRequest): Promise<Task> {
    return apiService.post<Task>('/agent/start', request);
  }

  async stopAgent(taskId: string): Promise<void> {
    return apiService.post<void>(`/agent/stop/${taskId}`);
  }

  async getTaskStatus(taskId: string): Promise<Task> {
    return apiService.get<Task>(`/agent/status/${taskId}`);
  }

  async getTaskHistory(params?: TaskHistoryParams): Promise<PaginatedResponse<Task>> {
    return apiService.get<PaginatedResponse<Task>>('/agent/history', params);
  }

  async getSystemMetrics(): Promise<SystemMetrics> {
    return apiService.get<SystemMetrics>('/system/metrics');
  }

  async getSystemHealth(): Promise<{ status: string; checks: Record<string, boolean> }> {
    return apiService.get<{ status: string; checks: Record<string, boolean> }>('/system/health');
  }

  async getSystemLogs(params?: {
    level?: string;
    limit?: number;
    offset?: number;
    since?: string;
  }): Promise<{
    logs: Array<{
      timestamp: string;
      level: string;
      message: string;
      module: string;
      details?: Record<string, any>;
    }>;
    total: number;
  }> {
    return apiService.get('/system/logs', params);
  }

  async pauseAgent(taskId: string): Promise<void> {
    return apiService.post<void>(`/agent/pause/${taskId}`);
  }

  async resumeAgent(taskId: string): Promise<void> {
    return apiService.post<void>(`/agent/resume/${taskId}`);
  }

  async cancelTask(taskId: string): Promise<void> {
    return apiService.delete<void>(`/agent/tasks/${taskId}`);
  }
}

export const agentService = new AgentService();
import { apiService } from './api';
import { ChatSession, ChatMessage, PaginatedResponse } from '@/types';

export interface CreateChatSessionRequest {
  title?: string;
}

export interface SendMessageRequest {
  content: string;
  use_knowledge_base?: boolean;
  model?: string;
  temperature?: number;
  max_tokens?: number;
}

export interface ChatResponse {
  id: string;
  content: string;
  sources: Array<{
    id: string;
    title: string;
    score: number;
    excerpt: string;
  }>;
  model_used: string;
  context_stats: {
    sources_found: number;
    tokens_used: number;
    response_time: number;
  };
  created_at: string;
}

export class ChatService {
  async getChatSessions(params?: {
    page?: number;
    page_size?: number;
    include_archived?: boolean;
  }): Promise<PaginatedResponse<ChatSession>> {
    return apiService.get<PaginatedResponse<ChatSession>>('/chat/sessions', params);
  }

  async createChatSession(request?: CreateChatSessionRequest): Promise<ChatSession> {
    return apiService.post<ChatSession>('/chat/sessions', request);
  }

  async getChatSession(sessionId: string): Promise<ChatSession> {
    return apiService.get<ChatSession>(`/chat/sessions/${sessionId}`);
  }

  async updateChatSession(sessionId: string, updates: {
    title?: string;
    is_archived?: boolean;
  }): Promise<ChatSession> {
    return apiService.put<ChatSession>(`/chat/sessions/${sessionId}`, updates);
  }

  async deleteChatSession(sessionId: string): Promise<void> {
    return apiService.delete<void>(`/chat/sessions/${sessionId}`);
  }

  async getChatMessages(sessionId: string, params?: {
    page?: number;
    page_size?: number;
    before?: string; // Message ID for pagination
  }): Promise<PaginatedResponse<ChatMessage>> {
    return apiService.get<PaginatedResponse<ChatMessage>>(
      `/chat/sessions/${sessionId}/messages`,
      params
    );
  }

  async sendMessage(sessionId: string, request: SendMessageRequest): Promise<ChatResponse> {
    return apiService.post<ChatResponse>(`/chat/sessions/${sessionId}/messages`, request);
  }

  async deleteMessage(sessionId: string, messageId: string): Promise<void> {
    return apiService.delete<void>(`/chat/sessions/${sessionId}/messages/${messageId}`);
  }

  async regenerateResponse(sessionId: string, messageId: string, options?: {
    model?: string;
    temperature?: number;
  }): Promise<ChatResponse> {
    return apiService.post<ChatResponse>(
      `/chat/sessions/${sessionId}/messages/${messageId}/regenerate`,
      options
    );
  }

  async exportChatSession(sessionId: string, format: 'json' | 'markdown' | 'txt' = 'json'): Promise<Blob> {
    const response = await fetch(`/api/v1/chat/sessions/${sessionId}/export?format=${format}`);
    if (!response.ok) {
      throw new Error('Export failed');
    }
    return response.blob();
  }

  async searchMessages(query: string, params?: {
    session_id?: string;
    limit?: number;
    offset?: number;
  }): Promise<{
    results: Array<{
      message: ChatMessage;
      session: ChatSession;
      score: number;
      excerpt: string;
    }>;
    total: number;
  }> {
    return apiService.post('/chat/search', { query, ...params });
  }

  async getAvailableModels(): Promise<Array<{
    id: string;
    name: string;
    provider: string;
    capabilities: string[];
    context_length: number;
    is_available: boolean;
  }>> {
    return apiService.get('/chat/models');
  }
}

export const chatService = new ChatService();
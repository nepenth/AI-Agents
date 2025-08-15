import { apiService } from './api';
import { KnowledgeItem, ContentItem, BasicSearchResult, PaginatedResponse, FilterState } from '@/types';

export interface CreateKnowledgeItemRequest {
  title: string;
  content: string;
  source_type: string;
  source_id?: string;
  category?: string;
  sub_category?: string;
  tags?: string[];
  metadata?: Record<string, any>;
}

export interface UpdateKnowledgeItemRequest {
  title?: string;
  content?: string;
  category?: string;
  sub_category?: string;
  tags?: string[];
  metadata?: Record<string, any>;
}

export interface SearchRequest {
  query: string;
  search_type?: 'text' | 'vector' | 'hybrid';
  filters?: FilterState;
  limit?: number;
  offset?: number;
  similarity_threshold?: number;
}

export interface Category {
  name: string;
  count: number;
  sub_categories: Array<{
    name: string;
    count: number;
  }>;
}

export interface SynthesisDocument {
  id: string;
  main_category: string;
  sub_category: string;
  title: string;
  content: string;
  item_count: number;
  source_item_ids: string[];
  is_stale: boolean;
  created_at: string;
  updated_at: string;
}

export class KnowledgeService {
  async getKnowledgeItems(params?: {
    page?: number;
    page_size?: number;
    category?: string;
    sub_category?: string;
    tags?: string[];
    search?: string;
    sort_by?: string;
    sort_order?: 'asc' | 'desc';
  }): Promise<PaginatedResponse<KnowledgeItem>> {
    return apiService.get<PaginatedResponse<KnowledgeItem>>('/knowledge/items', params);
  }

  async getKnowledgeItem(id: string): Promise<KnowledgeItem> {
    return apiService.get<KnowledgeItem>(`/knowledge/items/${id}`);
  }

  async createKnowledgeItem(request: CreateKnowledgeItemRequest): Promise<KnowledgeItem> {
    return apiService.post<KnowledgeItem>('/knowledge/items', request);
  }

  async updateKnowledgeItem(id: string, request: UpdateKnowledgeItemRequest): Promise<KnowledgeItem> {
    return apiService.put<KnowledgeItem>(`/knowledge/items/${id}`, request);
  }

  async deleteKnowledgeItem(id: string): Promise<void> {
    return apiService.delete<void>(`/knowledge/items/${id}`);
  }

  async searchKnowledge(request: SearchRequest): Promise<{
    results: BasicSearchResult[];
    total: number;
    query_time: number;
  }> {
    return apiService.post('/knowledge/search', request);
  }

  async searchAdvanced(
    filters: import('@/types').SearchFilters,
    page: number = 1,
    pageSize: number = 20
  ): Promise<PaginatedResponse<import('@/types').SearchResult>> {
    const params = {
      query: filters.query,
      search_type: filters.searchType,
      page,
      page_size: pageSize,
      sort_by: filters.sortBy,
      sort_order: filters.sortOrder,
      
      // Date filters
      start_date: filters.dateRange.start,
      end_date: filters.dateRange.end,
      
      // Engagement filters
      min_engagement: filters.engagementRange.min,
      max_engagement: filters.engagementRange.max,
      
      // Array filters
      categories: filters.categories.length > 0 ? filters.categories.join(',') : undefined,
      authors: filters.authors.length > 0 ? filters.authors.join(',') : undefined,
      tags: filters.tags.length > 0 ? filters.tags.join(',') : undefined,
      
      // Boolean filters
      has_media: filters.hasMedia,
      is_thread: filters.isThread,
      min_thread_length: filters.minThreadLength,
    };
    
    // Remove undefined values
    const cleanParams = Object.fromEntries(
      Object.entries(params).filter(([_, value]) => value !== undefined)
    );
    
    return apiService.get<PaginatedResponse<import('@/types').SearchResult>>('/knowledge/search/advanced', cleanParams);
  }

  async getCategories(): Promise<Category[]> {
    return apiService.get<Category[]>('/knowledge/categories');
  }

  async getSynthesisDocuments(params?: {
    category?: string;
    sub_category?: string;
    include_stale?: boolean;
  }): Promise<SynthesisDocument[]> {
    return apiService.get<SynthesisDocument[]>('/knowledge/synthesis', params);
  }

  async generateSynthesis(params: {
    main_category: string;
    sub_category?: string;
    force_regenerate?: boolean;
  }): Promise<{ task_id: string; message: string }> {
    return apiService.post('/knowledge/synthesis/generate', params);
  }

  async getSynthesisDocument(id: string): Promise<SynthesisDocument> {
    return apiService.get<SynthesisDocument>(`/knowledge/synthesis/${id}`);
  }

  async getContentItems(params?: {
    page?: number;
    page_size?: number;
    processing_state?: string;
    source_type?: string;
    category?: string;
  }): Promise<PaginatedResponse<ContentItem>> {
    return apiService.get<PaginatedResponse<ContentItem>>('/content/items', params);
  }

  async getContentItem(id: string): Promise<ContentItem> {
    return apiService.get<ContentItem>(`/content/items/${id}`);
  }

  async deleteContentItem(id: string): Promise<void> {
    return apiService.delete<void>(`/content/items/${id}`);
  }

  async reprocessContentItem(id: string): Promise<{ task_id: string; message: string }> {
    return apiService.post(`/content/items/${id}/reprocess`);
  }

  async exportKnowledge(params?: {
    format?: 'json' | 'markdown' | 'csv';
    category?: string;
    include_media?: boolean;
  }): Promise<Blob> {
    const searchParams = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined) {
          searchParams.append(key, String(value));
        }
      });
    }
    
    const response = await fetch(`/api/v1/knowledge/export?${searchParams}`);
    if (!response.ok) {
      throw new Error('Export failed');
    }
    return response.blob();
  }
}

export const knowledgeService = new KnowledgeService();
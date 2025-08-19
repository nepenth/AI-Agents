// Common types used throughout the application

export interface User {
  id: string;
  username: string;
  email: string;
  roles: string[];
  created_at: string;
}

export interface ContentItem {
  id: string;
  source_type: string;
  source_id: string;
  title: string;
  content: string;
  raw_data: Record<string, any>;
  processing_state: 'pending' | 'processing' | 'completed' | 'failed';
  processed_at?: string;
  main_category?: string;
  sub_category?: string;
  tags: string[];
  media_files: MediaFile[];
  generated_files: string[];
  created_at: string;
  updated_at: string;
}

export interface KnowledgeItem {
  id: string;
  content_item_id: string;
  display_title: string;
  summary?: string;
  enhanced_content: string;
  markdown_path?: string;
  media_paths: string[];
  created_at: string;
  updated_at: string;
}

export interface MediaFile {
  id: string;
  filename: string;
  content_type: string;
  size: number;
  path: string;
  description?: string;
}

export interface Task {
  id: string;
  task_type: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  config: Record<string, any>;
  current_phase?: string;
  progress_percentage: number;
  result_data?: Record<string, any>;
  error_message?: string;
  created_at: string;
  started_at?: string;
  completed_at?: string;
}

export interface ChatSession {
  id: string;
  title?: string;
  message_count: number;
  is_archived: boolean;
  created_at: string;
  last_updated: string;
}

export interface ChatMessage {
  id: string;
  session_id: string;
  role: 'user' | 'assistant';
  content: string;
  model_used?: string;
  sources: string[];
  context_stats?: Record<string, any>;
  created_at: string;
}

export interface BasicSearchResult {
  id: string;
  title: string;
  content: string;
  score: number;
  source_type: string;
  category?: string;
  tags: string[];
  created_at: string;
}

export interface SystemMetrics {
  // Legacy format (deprecated)
  cpu_usage?: number;
  memory_usage?: number;
  disk_usage?: number;
  gpu_usage?: number;
  active_tasks?: number;
  queue_size?: number;
  uptime?: number;
  
  // New format from backend
  cpu?: {
    usage_percent: number;
    count: number;
  };
  memory?: {
    total: number;
    available: number;
    used: number;
    usage_percent: number;
  };
  disk?: {
    total: number;
    used: number;
    free: number;
    usage_percent: number;
  };
  timestamp?: string;
}

export interface ProgressUpdate {
  task_id: string;
  progress: number;
  phase: string;
  message: string;
  timestamp: string;
}

export interface WebSocketMessage {
  type: string;
  payload: any;
  timestamp: string;
}

// Models and settings
export type ModelPhase = 'vision' | 'kb_generation' | 'synthesis' | 'chat' | 'embeddings';

export interface PhaseModelSelector {
  backend: 'ollama' | 'localai' | 'openai' | 'openai_compatible';
  model: string;
  params?: {
    temperature?: number;
    top_p?: number;
    max_tokens?: number;
  };
}

export interface ModelsAvailableResponse {
  backends: Record<string, {
    models: string[];
    capabilities: Record<string, string[]>; // modelName -> ["text", "embed", "vision"]
  }>;
}

export interface ModelsConfigResponse {
  per_phase: Record<ModelPhase, PhaseModelSelector | null>;
}

export interface APIErrorResponse {
  error_code: string;
  message: string;
  details?: Record<string, any>;
  timestamp: string;
  request_id: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  has_next: boolean;
  has_previous: boolean;
}

export interface FilterState {
  search?: string;
  category?: string;
  tags?: string[];
  date_range?: {
    start: string;
    end: string;
  };
  source_type?: string;
  processing_state?: string;
  // Advanced search filters
  searchType?: 'text' | 'vector' | 'hybrid' | 'semantic';
  sortBy?: 'relevance' | 'created_at_desc' | 'created_at_asc' | 'title_asc' | 'title_desc' | 'engagement_desc' | 'engagement_asc';
  dateRange?: string;
  contentType?: string;
  minEngagement?: number;
  author?: string;
  similarityThreshold?: number;
  startDate?: string;
  endDate?: string;
  hasMedia?: boolean;
  isThread?: boolean;
  hasAIAnalysis?: boolean;
  isBookmarked?: boolean;
  highEngagement?: boolean;
  recentlyProcessed?: boolean;
}

export interface SearchFilters {
  query: string;
  searchType: 'text' | 'vector' | 'hybrid';
  dateRange: {
    start?: string;
    end?: string;
  };
  engagementRange: {
    min?: number;
    max?: number;
  };
  categories: string[];
  authors: string[];
  hasMedia: boolean | null;
  isThread: boolean | null;
  minThreadLength?: number;
  tags: string[];
  sortBy: 'relevance' | 'date' | 'engagement' | 'thread_length';
  sortOrder: 'asc' | 'desc';
}

export interface SearchResult {
  item: KnowledgeItem & {
    author_username: string;
    total_engagement: number;
    thread_id?: string;
    thread_length?: number;
    has_media: boolean;
    categories: string[];
  };
  score?: number;
  highlights?: {
    title?: string;
    content?: string;
  };
}
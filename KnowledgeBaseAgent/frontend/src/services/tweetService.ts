import { apiService } from './api';

export interface TweetData {
  id: string;
  text: string;
  author: {
    id: string;
    username: string;
    name: string;
    verified?: boolean;
  };
  createdAt: string;
  publicMetrics: {
    likeCount: number;
    retweetCount: number;
    replyCount: number;
    quoteCount: number;
  };
  media?: Array<{
    id: string;
    type: 'photo' | 'video' | 'gif';
    url: string;
    altText?: string;
    width?: number;
    height?: number;
  }>;
  contextAnnotations?: Array<{
    domain: {
      id: string;
      name: string;
      description?: string;
    };
    entity: {
      id: string;
      name: string;
      description?: string;
    };
  }>;
  threadInfo?: {
    threadId: string;
    isRoot: boolean;
    position: number;
    length: number;
  };
}

export interface ProcessedTweetData extends TweetData {
  // Processing metadata
  processingStatus: 'pending' | 'processing' | 'completed' | 'failed';
  processedAt?: string;
  processingDuration?: number;
  
  // Sub-phase status
  bookmarkCached: boolean;
  mediaAnalyzed: boolean;
  contentUnderstood: boolean;
  categorized: boolean;
  
  // AI analysis results
  mediaAnalysisResults?: Array<{
    mediaId: string;
    analysis: string;
    modelUsed: string;
    isRealAI: boolean;
  }>;
  
  collectiveUnderstanding?: {
    mainTopic: string;
    sentiment: 'positive' | 'negative' | 'neutral';
    keyInsights: string[];
    technicalLevel: 'beginner' | 'intermediate' | 'advanced';
    targetAudience: string;
    relevanceScore: number;
    modelUsed: string;
    isRealAI: boolean;
  };
  
  categorization?: {
    mainCategory: string;
    subCategory: string;
    confidence: 'high' | 'medium' | 'low';
    reasoning: string;
    modelUsed: string;
    isRealAI: boolean;
  };
  
  // Engagement and metrics
  totalEngagement: number;
  engagementLevel: 'low' | 'medium' | 'high';
  
  // Knowledge base integration
  knowledgeBaseId?: string;
  categories: string[];
  tags: string[];
}

export interface TwitterBookmarkResponse {
  id: string;
  tweetId: string;
  authorUsername: string;
  authorId: string;
  tweetUrl: string;
  content: string;
  threadId?: string;
  isThreadRoot: boolean;
  threadLength?: number;
  engagementMetrics: {
    likes: number;
    retweets: number;
    replies: number;
    quotes: number;
    total: number;
  };
  subPhaseStatus: {
    bookmarkCached: boolean;
    mediaAnalyzed: boolean;
    contentUnderstood: boolean;
    categorized: boolean;
    completionPercentage: number;
  };
  createdAt: string;
  originalTweetCreatedAt?: string;
}

export interface TweetProcessingRequest {
  tweetId: string;
  forceReprocess?: boolean;
  phases?: string[];
  aiModelOverrides?: { [phase: string]: string };
}

export interface ThreadVisualization {
  threadId: string;
  rootTweetId: string;
  tweets: Array<{
    id: string;
    position: number;
    content: string;
    author: string;
    createdAt: string;
    metrics: {
      likes: number;
      retweets: number;
      replies: number;
    };
    processingStatus: string;
  }>;
  collectiveUnderstanding?: {
    mainTheme: string;
    keyPoints: string[];
    overallSentiment: string;
    threadSummary: string;
  };
  totalEngagement: number;
  threadLength: number;
  processingStatus: 'pending' | 'processing' | 'completed' | 'failed';
}

class TweetService {
  /**
   * Fetch tweet data by ID
   */
  async getTweetById(tweetId: string): Promise<TweetData> {
    try {
      const response = await apiService.get(`/content/twitter/tweets/${tweetId}`);
      return response.data;
    } catch (error) {
      console.error(`Failed to get tweet ${tweetId}:`, error);
      throw error;
    }
  }

  /**
   * Get processed tweet data with AI analysis
   */
  async getProcessedTweet(tweetId: string): Promise<ProcessedTweetData> {
    try {
      const response = await apiService.get(`/content/twitter/processed/${tweetId}`);
      return response.data;
    } catch (error) {
      console.error(`Failed to get processed tweet ${tweetId}:`, error);
      throw error;
    }
  }

  /**
   * Process a tweet through the seven-phase pipeline
   */
  async processTweet(request: TweetProcessingRequest): Promise<{
    taskId: string;
    status: string;
    message: string;
    estimatedDuration?: number;
  }> {
    try {
      const response = await apiService.post('/content/twitter/process', request);
      return response.data;
    } catch (error) {
      console.error('Failed to process tweet:', error);
      throw error;
    }
  }

  /**
   * Get Twitter bookmarks with filtering
   */
  async getBookmarks(
    author?: string,
    category?: string,
    hasMedia?: boolean,
    isThread?: boolean,
    processingStatus?: string,
    limit: number = 20,
    offset: number = 0
  ): Promise<{
    items: TwitterBookmarkResponse[];
    total: number;
    hasNext: boolean;
  }> {
    try {
      const params = new URLSearchParams();
      if (author) params.append('author', author);
      if (category) params.append('category', category);
      if (hasMedia !== undefined) params.append('has_media', hasMedia.toString());
      if (isThread !== undefined) params.append('is_thread', isThread.toString());
      if (processingStatus) params.append('processing_status', processingStatus);
      params.append('limit', limit.toString());
      params.append('offset', offset.toString());

      const response = await apiService.get(`/content/twitter/bookmarks?${params}`);
      return response.data;
    } catch (error) {
      console.error('Failed to get bookmarks:', error);
      throw error;
    }
  }

  /**
   * Get thread visualization data
   */
  async getThreadVisualization(threadId: string): Promise<ThreadVisualization> {
    try {
      const response = await apiService.get(`/content/twitter/threads/${threadId}`);
      return response.data;
    } catch (error) {
      console.error(`Failed to get thread visualization for ${threadId}:`, error);
      throw error;
    }
  }

  /**
   * Search tweets with various filters
   */
  async searchTweets(
    query: string,
    searchType: 'text' | 'vector' | 'hybrid' = 'hybrid',
    filters?: {
      author?: string;
      dateRange?: [string, string];
      category?: string;
      hasMedia?: boolean;
      engagementLevel?: 'low' | 'medium' | 'high';
      isProcessed?: boolean;
    },
    limit: number = 20,
    offset: number = 0
  ): Promise<{
    items: ProcessedTweetData[];
    total: number;
    hasNext: boolean;
    searchType: string;
    query: string;
  }> {
    try {
      const searchRequest = {
        query,
        searchType,
        filters: filters || {},
        limit,
        offset
      };

      const response = await apiService.post('/content/twitter/search', searchRequest);
      return response.data;
    } catch (error) {
      console.error('Failed to search tweets:', error);
      throw error;
    }
  }

  /**
   * Get tweet processing history
   */
  async getProcessingHistory(
    tweetId?: string,
    status?: string,
    limit: number = 50,
    offset: number = 0
  ): Promise<{
    items: Array<{
      tweetId: string;
      taskId: string;
      status: string;
      startTime: string;
      endTime?: string;
      duration?: number;
      phases: { [phase: string]: any };
      errors?: string[];
    }>;
    total: number;
    hasNext: boolean;
  }> {
    try {
      const params = new URLSearchParams();
      if (tweetId) params.append('tweet_id', tweetId);
      if (status) params.append('status', status);
      params.append('limit', limit.toString());
      params.append('offset', offset.toString());

      const response = await apiService.get(`/content/twitter/processing-history?${params}`);
      return response.data;
    } catch (error) {
      console.error('Failed to get processing history:', error);
      throw error;
    }
  }

  /**
   * Get tweet engagement analytics
   */
  async getEngagementAnalytics(
    tweetId: string,
    timeRange: string = '24h'
  ): Promise<{
    tweetId: string;
    currentMetrics: {
      likes: number;
      retweets: number;
      replies: number;
      quotes: number;
      total: number;
    };
    trends: {
      likeGrowthRate: number;
      retweetGrowthRate: number;
      replyGrowthRate: number;
      trendDirection: 'up' | 'down' | 'stable';
    };
    performanceComparison: {
      percentile: number;
      similarTweets: number;
      averageEngagement: number;
    };
    insights: string[];
  }> {
    try {
      const response = await apiService.get(
        `/content/twitter/tweets/${tweetId}/analytics?timeRange=${timeRange}`
      );
      return response.data;
    } catch (error) {
      console.error(`Failed to get engagement analytics for ${tweetId}:`, error);
      throw error;
    }
  }

  /**
   * Compare AI analysis with Twitter's context annotations
   */
  async compareAnalysis(tweetId: string): Promise<{
    tweetId: string;
    aiAnalysis: {
      category: string;
      sentiment: string;
      keyTopics: string[];
      confidence: number;
      modelUsed: string;
    };
    twitterAnnotations: Array<{
      domain: string;
      entity: string;
      confidence?: number;
    }>;
    comparison: {
      similarity: number;
      differences: string[];
      aiAdvantages: string[];
      twitterAdvantages: string[];
    };
    recommendation: {
      preferredSource: 'ai' | 'twitter' | 'hybrid';
      reasoning: string;
    };
  }> {
    try {
      const response = await apiService.get(`/content/twitter/tweets/${tweetId}/compare-analysis`);
      return response.data;
    } catch (error) {
      console.error(`Failed to compare analysis for ${tweetId}:`, error);
      throw error;
    }
  }

  /**
   * Get tweet media analysis details
   */
  async getMediaAnalysis(tweetId: string): Promise<{
    tweetId: string;
    mediaItems: Array<{
      mediaId: string;
      type: 'photo' | 'video' | 'gif';
      url: string;
      altText?: string;
      analysis: {
        description: string;
        keyElements: string[];
        relevanceToTweet: string;
        technicalDetails?: string;
        emotionalTone?: string;
        modelUsed: string;
        isRealAI: boolean;
        confidence?: number;
      };
    }>;
    overallMediaSummary: string;
    mediaRelevanceScore: number;
  }> {
    try {
      const response = await apiService.get(`/content/twitter/tweets/${tweetId}/media-analysis`);
      return response.data;
    } catch (error) {
      console.error(`Failed to get media analysis for ${tweetId}:`, error);
      throw error;
    }
  }

  /**
   * Export tweet data in various formats
   */
  async exportTweetData(
    tweetIds: string[],
    format: 'json' | 'csv' | 'markdown' = 'json',
    includeAnalysis: boolean = true
  ): Promise<{
    format: string;
    data: any;
    filename: string;
    size: number;
  }> {
    try {
      const response = await apiService.post('/content/twitter/export', {
        tweetIds,
        format,
        includeAnalysis
      });
      return response.data;
    } catch (error) {
      console.error('Failed to export tweet data:', error);
      throw error;
    }
  }

  /**
   * Validate tweet ID format
   */
  validateTweetId(tweetId: string): boolean {
    // Twitter tweet IDs are numeric strings, typically 19 digits
    const tweetIdRegex = /^\d{10,20}$/;
    return tweetIdRegex.test(tweetId);
  }

  /**
   * Extract tweet ID from Twitter URL
   */
  extractTweetIdFromUrl(url: string): string | null {
    const twitterUrlRegex = /twitter\.com\/\w+\/status\/(\d+)/;
    const match = url.match(twitterUrlRegex);
    return match ? match[1] : null;
  }

  /**
   * Get tweet processing recommendations
   */
  async getProcessingRecommendations(tweetId: string): Promise<{
    tweetId: string;
    recommendations: Array<{
      type: 'reprocess' | 'skip' | 'priority';
      reason: string;
      confidence: number;
      estimatedBenefit: string;
    }>;
    suggestedPhases: string[];
    estimatedProcessingTime: number;
    costBenefit: {
      processingCost: number;
      expectedValue: number;
      recommendation: 'process' | 'skip';
    };
  }> {
    try {
      const response = await apiService.get(`/content/twitter/tweets/${tweetId}/recommendations`);
      return response.data;
    } catch (error) {
      console.error(`Failed to get processing recommendations for ${tweetId}:`, error);
      throw error;
    }
  }
}

export const tweetService = new TweetService();
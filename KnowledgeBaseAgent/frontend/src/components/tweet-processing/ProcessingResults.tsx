import React, { useState } from 'react';
import { 
  SparklesIcon, 
  EyeIcon, 
  TagIcon, 
  DocumentTextIcon,
  ChartBarIcon,
  ClipboardDocumentIcon,
  ArrowPathIcon,
  CheckCircleIcon,
  XCircleIcon,
  ClockIcon
} from '@heroicons/react/24/outline';
import { GlassCard } from '../ui/GlassCard';
import { LiquidButton } from '../ui/LiquidButton';
import { StatusBadge } from '../ui/StatusBadge';
import { ProgressBar } from '../ui/ProgressBar';
import { LoadingSpinner } from '../ui/LoadingSpinner';
import { cn } from '../../utils/cn';

export interface ProcessingResult {
  phase: string;
  phaseName: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  progress?: number;
  startTime?: string;
  endTime?: string;
  duration?: number;
  aiModelUsed?: string;
  isRealAI?: boolean;
  results?: {
    mediaAnalysis?: {
      items: Array<{
        mediaId: string;
        mediaType: string;
        analysis: string;
        confidence: number;
        detectedObjects?: string[];
        extractedText?: string;
        visualDescription: string;
        technicalDetails?: string;
        emotionalTone?: string;
      }>;
      model: string;
      processingTime: number;
    };
    contentUnderstanding?: {
      summary: string;
      keyInsights: string[];
      mainTopics: string[];
      technicalConcepts?: string[];
      sentiment: {
        overall: 'positive' | 'negative' | 'neutral';
        confidence: number;
        aspects: Array<{
          aspect: string;
          sentiment: string;
          confidence: number;
        }>;
      };
      complexity: {
        level: 'low' | 'medium' | 'high';
        score: number;
        factors: string[];
      };
      model: string;
      processingTime: number;
    };
    categorization?: {
      mainCategory: string;
      subCategory?: string;
      confidence: number;
      alternativeCategories: Array<{
        category: string;
        confidence: number;
      }>;
      tags: string[];
      model: string;
      processingTime: number;
    };
    synthesis?: {
      document: string;
      relatedContent: Array<{
        id: string;
        title: string;
        relevanceScore: number;
      }>;
      keyConnections: string[];
      model: string;
      processingTime: number;
    };
    embeddings?: {
      vector: number[];
      dimensions: number;
      model: string;
      processingTime: number;
    };
  };
  error?: string;
}

export interface ProcessingResultsProps {
  results: ProcessingResult[];
  overallStatus: 'pending' | 'running' | 'completed' | 'failed';
  overallProgress: number;
  tweetId: string;
  onReprocess?: (phases?: string[]) => void;
  onExportResults?: () => void;
  className?: string;
}

const getPhaseIcon = (phase: string) => {
  switch (phase) {
    case 'phase_3_1': return EyeIcon;
    case 'phase_3_2': return SparklesIcon;
    case 'phase_3_3': return TagIcon;
    case 'phase_4': return DocumentTextIcon;
    case 'phase_5': return ChartBarIcon;
    default: return DocumentTextIcon;
  }
};

const getStatusIcon = (status: string) => {
  switch (status) {
    case 'completed': return CheckCircleIcon;
    case 'failed': return XCircleIcon;
    case 'running': return ArrowPathIcon;
    default: return ClockIcon;
  }
};

const formatDuration = (ms: number): string => {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${(ms / 60000).toFixed(1)}m`;
};

const copyToClipboard = async (text: string) => {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch (err) {
    console.error('Failed to copy text: ', err);
    return false;
  }
};

export const ProcessingResults: React.FC<ProcessingResultsProps> = ({
  results,
  overallStatus,
  overallProgress,
  tweetId,
  onReprocess,
  onExportResults,
  className
}) => {
  const [activeTab, setActiveTab] = useState<string>('overview');
  const [expandedPhases, setExpandedPhases] = useState<Set<string>>(new Set());
  const [copiedText, setCopiedText] = useState<string | null>(null);

  const handleCopy = async (text: string, label: string) => {
    const success = await copyToClipboard(text);
    if (success) {
      setCopiedText(label);
      setTimeout(() => setCopiedText(null), 2000);
    }
  };

  const togglePhaseExpansion = (phase: string) => {
    const newExpanded = new Set(expandedPhases);
    if (newExpanded.has(phase)) {
      newExpanded.delete(phase);
    } else {
      newExpanded.add(phase);
    }
    setExpandedPhases(newExpanded);
  };

  const completedResults = results.filter(r => r.status === 'completed');
  const failedResults = results.filter(r => r.status === 'failed');
  const runningResults = results.filter(r => r.status === 'running');

  const totalProcessingTime = completedResults.reduce((sum, r) => sum + (r.duration || 0), 0);
  const averageProcessingTime = completedResults.length > 0 ? totalProcessingTime / completedResults.length : 0;

  // Get available tabs based on completed results
  const availableTabs = [
    { id: 'overview', label: 'Overview', icon: ChartBarIcon },
    ...(completedResults.filter(r => r.results?.mediaAnalysis).length > 0 
      ? [{ id: 'media', label: 'Media Analysis', icon: EyeIcon }] : []),
    ...(completedResults.filter(r => r.results?.contentUnderstanding).length > 0 
      ? [{ id: 'understanding', label: 'Content Understanding', icon: SparklesIcon }] : []),
    ...(completedResults.filter(r => r.results?.categorization).length > 0 
      ? [{ id: 'categorization', label: 'Categorization', icon: TagIcon }] : []),
    ...(completedResults.filter(r => r.results?.synthesis).length > 0 
      ? [{ id: 'synthesis', label: 'Synthesis', icon: DocumentTextIcon }] : [])
  ];

  return (
    <div className={cn('space-y-6', className)}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-foreground">Processing Results</h2>
          <p className="text-muted-foreground">Tweet ID: {tweetId}</p>
        </div>
        <div className="flex items-center gap-3">
          <StatusBadge 
            status={overallStatus} 
            animated={overallStatus === 'running'}
          />
          {onExportResults && (
            <LiquidButton variant="outline" size="sm" onClick={onExportResults}>
              <ClipboardDocumentIcon className="h-4 w-4 mr-2" />
              Export
            </LiquidButton>
          )}
          {onReprocess && (
            <LiquidButton variant="outline" size="sm" onClick={() => onReprocess()}>
              <ArrowPathIcon className="h-4 w-4 mr-2" />
              Reprocess
            </LiquidButton>
          )}
        </div>
      </div>

      {/* Overall Progress */}
      <GlassCard variant="primary">
        <div className="p-6">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-foreground">Overall Progress</span>
              <span className="text-sm text-muted-foreground">{overallProgress.toFixed(0)}%</span>
            </div>
            <ProgressBar
              value={overallProgress}
              variant={overallStatus === 'failed' ? 'error' : overallStatus === 'completed' ? 'success' : 'default'}
              animated={overallStatus === 'running'}
              striped={overallStatus === 'running'}
            />
            
            {/* Summary Stats */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div className="text-center">
                <div className="text-lg font-bold text-green-600">{completedResults.length}</div>
                <div className="text-muted-foreground">Completed</div>
              </div>
              <div className="text-center">
                <div className="text-lg font-bold text-blue-600">{runningResults.length}</div>
                <div className="text-muted-foreground">Running</div>
              </div>
              <div className="text-center">
                <div className="text-lg font-bold text-red-600">{failedResults.length}</div>
                <div className="text-muted-foreground">Failed</div>
              </div>
              <div className="text-center">
                <div className="text-lg font-bold text-purple-600">
                  {averageProcessingTime > 0 ? formatDuration(averageProcessingTime) : 'N/A'}
                </div>
                <div className="text-muted-foreground">Avg Time</div>
              </div>
            </div>
          </div>
        </div>
      </GlassCard>

      {/* Tab Navigation */}
      <div className="flex items-center gap-1 border-b border-white/10">
        {availableTabs.map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                'flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-t-lg transition-all',
                activeTab === tab.id
                  ? 'bg-primary/20 text-primary border-b-2 border-primary'
                  : 'text-muted-foreground hover:text-foreground hover:bg-white/5'
              )}
            >
              <Icon className="h-4 w-4" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Tab Content */}
      <div className="space-y-4">
        {/* Overview Tab */}
        {activeTab === 'overview' && (
          <div className="space-y-4">
            {results.map((result) => {
              const Icon = getPhaseIcon(result.phase);
              const StatusIcon = getStatusIcon(result.status);
              const isExpanded = expandedPhases.has(result.phase);
              
              return (
                <GlassCard key={result.phase} variant="secondary">
                  <div 
                    className="p-6 cursor-pointer" 
                    onClick={() => togglePhaseExpansion(result.phase)}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <Icon className="h-5 w-5 text-primary" />
                        <div>
                          <div className="flex items-center gap-2">
                            {result.phaseName}
                            <StatusBadge 
                              status={result.status} 
                              size="sm"
                              animated={result.status === 'running'}
                            />
                          </div>
                          {result.aiModelUsed && (
                            <div className="text-sm text-muted-foreground mt-1">
                              Model: {result.aiModelUsed} 
                              {result.isRealAI ? ' (Real AI)' : ' (Simulated)'}
                            </div>
                          )}
                        </div>
                      </div>
                      
                      <div className="flex items-center gap-2">
                        {result.duration && (
                          <span className="text-sm text-muted-foreground">
                            {formatDuration(result.duration)}
                          </span>
                        )}
                        <StatusIcon className={cn(
                          'h-5 w-5',
                          result.status === 'completed' && 'text-green-500',
                          result.status === 'failed' && 'text-red-500',
                          result.status === 'running' && 'text-blue-500 animate-spin',
                          result.status === 'pending' && 'text-gray-500'
                        )} />
                      </div>
                    </div>
                    
                    {isExpanded && (
                      <div className="mt-4 pt-4 border-t border-white/10">
                        {result.status === 'running' && result.progress !== undefined && (
                          <div className="mb-4">
                            <ProgressBar
                              value={result.progress}
                              variant="default"
                              animated
                              striped
                              showLabel
                            />
                          </div>
                        )}
                        
                        {result.error && (
                          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg">
                            <div className="text-red-800 text-sm font-medium">Error:</div>
                            <div className="text-red-700 text-sm mt-1">{result.error}</div>
                          </div>
                        )}
                        
                        {result.results && (
                          <div className="space-y-4">
                            {/* Media Analysis Results */}
                            {result.results.mediaAnalysis && (
                              <div>
                                <h4 className="font-medium text-foreground mb-2">Media Analysis</h4>
                                <div className="text-sm text-muted-foreground">
                                  {result.results.mediaAnalysis.items.length} media items analyzed
                                  using {result.results.mediaAnalysis.model}
                                </div>
                              </div>
                            )}
                            
                            {/* Content Understanding Results */}
                            {result.results.contentUnderstanding && (
                              <div>
                                <h4 className="font-medium text-foreground mb-2">Content Understanding</h4>
                                <div className="text-sm text-muted-foreground mb-2">
                                  Sentiment: {result.results.contentUnderstanding.sentiment.overall} 
                                  ({(result.results.contentUnderstanding.sentiment.confidence * 100).toFixed(0)}% confidence)
                                </div>
                                <div className="text-sm">
                                  {result.results.contentUnderstanding.summary.substring(0, 200)}...
                                </div>
                              </div>
                            )}
                            
                            {/* Categorization Results */}
                            {result.results.categorization && (
                              <div>
                                <h4 className="font-medium text-foreground mb-2">Categorization</h4>
                                <div className="flex items-center gap-2">
                                  <span className="text-sm px-2 py-1 bg-primary/20 text-primary rounded-full">
                                    {result.results.categorization.mainCategory}
                                  </span>
                                  {result.results.categorization.subCategory && (
                                    <span className="text-sm px-2 py-1 bg-gray-500/20 text-gray-500 rounded-full">
                                      {result.results.categorization.subCategory}
                                    </span>
                                  )}
                                  <span className="text-xs text-muted-foreground">
                                    {(result.results.categorization.confidence * 100).toFixed(0)}% confidence
                                  </span>
                                </div>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </GlassCard>
              );
            })}
          </div>
        )}

        {/* Other tabs would be implemented here */}
        {activeTab !== 'overview' && (
          <GlassCard variant="tertiary">
            <div className="p-6 text-center">
              <p className="text-muted-foreground">
                {activeTab.charAt(0).toUpperCase() + activeTab.slice(1)} view implementation in progress...
              </p>
            </div>
          </GlassCard>
        )}
      </div>
    </div>
  );
};
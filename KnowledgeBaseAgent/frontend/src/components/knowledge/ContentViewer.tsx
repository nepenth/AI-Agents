import React, { useState, useEffect } from 'react';
import { 
  XMarkIcon, 
  ArrowTopRightOnSquareIcon,
  DocumentTextIcon,
  CalendarIcon,
  UserIcon,
  ClipboardDocumentIcon,
  SparklesIcon
} from '@heroicons/react/24/outline';
import { GlassCard } from '../ui/GlassCard';
import { LiquidButton } from '../ui/LiquidButton';
import { StatusBadge } from '../ui/StatusBadge';
import { LoadingSpinner } from '../ui/LoadingSpinner';
import { useKnowledgeStore } from '../../stores/knowledgeStore';
import { cn } from '../../utils/cn';

export interface ContentViewerProps {
  itemId: string | null;
  onClose?: () => void;
  className?: string;
}

const formatDate = (dateString: string): string => {
  return new Date(dateString).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
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

export const ContentViewer: React.FC<ContentViewerProps> = ({
  itemId,
  onClose,
  className
}) => {
  const { currentKnowledgeItem, loading, loadKnowledgeItem } = useKnowledgeStore();
  const [activeTab, setActiveTab] = useState<'content' | 'analysis'>('content');
  const [copiedText, setCopiedText] = useState<string | null>(null);
  
  // Load item when itemId changes
  useEffect(() => {
    if (itemId) {
      loadKnowledgeItem(itemId);
    }
  }, [itemId, loadKnowledgeItem]);
  
  // Handle copy with feedback
  const handleCopy = async (text: string, label: string) => {
    const success = await copyToClipboard(text);
    if (success) {
      setCopiedText(label);
      setTimeout(() => setCopiedText(null), 2000);
    }
  };
  
  if (!itemId) {
    return (
      <div className={cn('flex items-center justify-center h-64', className)}>
        <div className="text-center text-muted-foreground">
          <DocumentTextIcon className="h-12 w-12 mx-auto mb-4 opacity-50" />
          <p>Select an item to view its details</p>
        </div>
      </div>
    );
  }
  
  if (loading) {
    return (
      <div className={cn('flex items-center justify-center h-64', className)}>
        <LoadingSpinner size="lg" />
      </div>
    );
  }
  
  if (!currentKnowledgeItem) {
    return (
      <div className={cn('flex items-center justify-center h-64', className)}>
        <div className="text-center text-muted-foreground">
          <XMarkIcon className="h-12 w-12 mx-auto mb-4 opacity-50" />
          <p>Item not found</p>
        </div>
      </div>
    );
  }
  
  const item = currentKnowledgeItem;
  const hasAnalysis = item.ai_summary || item.enhanced_content || item.collective_understanding;
  
  // Determine available tabs
  const availableTabs = [
    { id: 'content', label: 'Content', icon: DocumentTextIcon },
    ...(hasAnalysis ? [{ id: 'analysis', label: 'AI Analysis', icon: SparklesIcon }] : [])
  ];
  
  return (
    <div className={cn('space-y-6', className)}>
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-2">
            <StatusBadge status={item.processing_state as 'pending' | 'running' | 'completed' | 'failed'} size="sm" />
            {item.content_type && (
              <span className="text-xs px-2 py-1 bg-glass-tertiary border border-glass-border-tertiary rounded-full">
                {item.content_type}
              </span>
            )}
          </div>
          <h1 className="text-xl font-bold text-foreground mb-2">{item.title}</h1>
          
          {/* Metadata */}
          <div className="flex items-center gap-4 text-sm text-muted-foreground">
            {item.author_username && (
              <div className="flex items-center gap-1">
                <UserIcon className="h-4 w-4" />
                <span>@{item.author_username}</span>
              </div>
            )}
            <div className="flex items-center gap-1">
              <CalendarIcon className="h-4 w-4" />
              <span>{formatDate(item.created_at)}</span>
            </div>
            {item.tweet_url && (
              <a
                href={item.tweet_url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 hover:text-primary transition-colors"
              >
                <ArrowTopRightOnSquareIcon className="h-4 w-4" />
                <span>View Original</span>
              </a>
            )}
          </div>
        </div>
        
        {onClose && (
          <LiquidButton variant="ghost" size="sm" onClick={onClose}>
            <XMarkIcon className="h-4 w-4" />
          </LiquidButton>
        )}
      </div>
      
      {/* Tab Navigation */}
      <div className="flex items-center gap-1 border-b border-white/10">
        {availableTabs.map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
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
        {/* Content Tab */}
        {activeTab === 'content' && (
          <GlassCard variant="primary">
            <div className="p-6 space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-medium text-foreground">Original Content</h3>
                <LiquidButton
                  variant="ghost"
                  size="sm"
                  onClick={() => handleCopy(item.content, 'Content')}
                >
                  <ClipboardDocumentIcon className="h-4 w-4 mr-2" />
                  {copiedText === 'Content' ? 'Copied!' : 'Copy'}
                </LiquidButton>
              </div>
              <div className="prose prose-sm max-w-none text-foreground">
                <p className="whitespace-pre-wrap">{item.content}</p>
              </div>
            </div>
          </GlassCard>
        )}
        
        {/* Analysis Tab */}
        {activeTab === 'analysis' && hasAnalysis && (
          <div className="space-y-4">
            {item.ai_summary && (
              <GlassCard variant="secondary">
                <div className="p-6">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-lg font-medium text-foreground flex items-center gap-2">
                      <SparklesIcon className="h-5 w-5 text-primary" />
                      AI Summary
                    </h3>
                    <LiquidButton
                      variant="ghost"
                      size="sm"
                      onClick={() => handleCopy(item.ai_summary!, 'Summary')}
                    >
                      <ClipboardDocumentIcon className="h-4 w-4 mr-2" />
                      {copiedText === 'Summary' ? 'Copied!' : 'Copy'}
                    </LiquidButton>
                  </div>
                  <div className="prose prose-sm max-w-none text-foreground">
                    <p className="whitespace-pre-wrap">{item.ai_summary}</p>
                  </div>
                </div>
              </GlassCard>
            )}
            
            {item.enhanced_content && (
              <GlassCard variant="tertiary">
                <div className="p-6">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-lg font-medium text-foreground">Enhanced Content</h3>
                    <LiquidButton
                      variant="ghost"
                      size="sm"
                      onClick={() => handleCopy(item.enhanced_content!, 'Enhanced Content')}
                    >
                      <ClipboardDocumentIcon className="h-4 w-4 mr-2" />
                      {copiedText === 'Enhanced Content' ? 'Copied!' : 'Copy'}
                    </LiquidButton>
                  </div>
                  <div className="prose prose-sm max-w-none text-foreground">
                    <div dangerouslySetInnerHTML={{ __html: item.enhanced_content }} />
                  </div>
                </div>
              </GlassCard>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
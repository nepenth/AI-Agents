import React, { useState } from 'react';
import {
  Heart,
  Repeat2,
  MessageCircle,
  Share,
  Image,
  Play,
  FileText,
  Tag,
  Calendar,
  User,
  Link,
  Check,
  Eye,
  MoreHorizontal
} from 'lucide-react';
import { GlassCard } from '@/components/ui/GlassCard';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { Tooltip } from '@/components/ui/Tooltip';
import { LiquidButton } from '@/components/ui/LiquidButton';
import { cn } from '@/utils/cn';
import type { KnowledgeItem } from '@/types';

export interface KnowledgeItemCardProps {
  item: KnowledgeItem;
  viewMode: 'grid' | 'list';
  isSelected?: boolean;
  isHighlighted?: boolean;
  onSelect?: () => void;
  onToggleSelection?: () => void;
  searchQuery?: string;
  className?: string;
}

const formatNumber = (num: number): string => {
  if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`;
  if (num >= 1000) return `${(num / 1000).toFixed(1)}K`;
  return num.toString();
};

const formatDate = (dateString: string): string => {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays === 0) return 'Today';
  if (diffDays === 1) return 'Yesterday';
  if (diffDays < 7) return `${diffDays} days ago`;
  if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`;
  if (diffDays < 365) return `${Math.floor(diffDays / 30)} months ago`;
  return `${Math.floor(diffDays / 365)} years ago`;
};

const highlightText = (text: string, query: string): React.ReactNode => {
  if (!query.trim()) return text;

  const regex = new RegExp(`(${query.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&')})`, 'gi');
  const parts = text.split(regex);

  return parts.map((part, index) =>
    regex.test(part) ? (
      <mark key={index} className="bg-yellow-200/50 text-yellow-900 px-0.5 rounded">
        {part}
      </mark>
    ) : part
  );
};

const getContentTypeIcon = (contentType: string) => {
  switch (contentType) {
    case 'tweet':
      return <FileText className="h-4 w-4" />;
    case 'thread':
      return <Link className="h-4 w-4" />;
    case 'media':
      return <Image className="h-4 w-4" />;
    case 'video':
      return <Play className="h-4 w-4" />;
    default:
      return <FileText className="h-4 w-4" />;
  }
};

export const KnowledgeItemCard: React.FC<KnowledgeItemCardProps> = ({
  item,
  viewMode,
  isSelected = false,
  isHighlighted = false,
  onSelect,
  onToggleSelection,
  searchQuery = '',
  className
}) => {
  const [imageError, setImageError] = useState(false);

  const engagement = {
    likes: item.like_count || 0,
    retweets: item.retweet_count || 0,
    replies: item.reply_count || 0,
    quotes: item.quote_count || 0
  };

  const totalEngagement = engagement.likes + engagement.retweets + engagement.replies + engagement.quotes;
  const hasMedia = item.media_content && item.media_content.length > 0;
  const mediaCount = hasMedia ? item.media_content.length : 0;
  const previewMedia = hasMedia ? item.media_content[0] : null;
  const isThread = item.thread_id && item.thread_length && item.thread_length > 1;

  const cardVariant = isHighlighted ? 'interactive' : isSelected ? 'primary' : 'secondary';

  if (viewMode === 'list') {
    return (
      <GlassCard 
        variant={cardVariant} 
        elevated={isHighlighted}
        className={cn('cursor-pointer transition-all duration-300 hover:scale-[1.01]', className)} 
        onClick={onSelect}
      >
        <div className="p-5 relative z-10">
          <div className="flex gap-4">
            {onToggleSelection && (
              <div className="flex-shrink-0 pt-1">
                <button
                  onClick={(e) => { e.stopPropagation(); onToggleSelection(); }}
                  className={cn(
                    'w-5 h-5 rounded border-2 flex items-center justify-center transition-all backdrop-blur-sm',
                    isSelected 
                      ? 'bg-primary border-primary text-primary-foreground' 
                      : 'border-glass-border-secondary hover:border-primary/50 hover:bg-glass-tertiary'
                  )}
                >
                  {isSelected && <Check className="h-3 w-3" />}
                </button>
              </div>
            )}
            {hasMedia && previewMedia && !imageError && (
              <div className="flex-shrink-0">
                <div className="w-16 h-16 rounded-xl overflow-hidden bg-glass-tertiary border border-glass-border-tertiary backdrop-blur-sm">
                  {previewMedia.type === 'photo' ? (
                    <img 
                      src={previewMedia.url} 
                      alt="Media preview" 
                      className="w-full h-full object-cover" 
                      onError={() => setImageError(true)} 
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center">
                      {previewMedia.type === 'video' ? 
                        <Play className="h-6 w-6 text-muted-foreground" /> : 
                        <Image className="h-6 w-6 text-muted-foreground" />
                      }
                    </div>
                  )}
                </div>
                {mediaCount > 1 && (
                  <div className="text-xs text-muted-foreground mt-1 text-center">
                    +{mediaCount - 1} more
                  </div>
                )}
              </div>
            )}
            <div className="flex-1 min-w-0">
              <div className="flex items-start justify-between gap-4 mb-3">
                <div className="flex-1">
                  <h3 className="font-semibold text-foreground line-clamp-2 mb-2">
                    {highlightText(item.title, searchQuery)}
                  </h3>
                  <p className="text-sm text-muted-foreground line-clamp-3">
                    {highlightText(item.content.substring(0, 200) + (item.content.length > 200 ? '...' : ''), searchQuery)}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <StatusBadge status={item.processing_state as any} size="sm" />
                  <div className="p-1 bg-glass-tertiary rounded-lg border border-glass-border-tertiary backdrop-blur-sm">
                    {getContentTypeIcon(item.content_type)}
                  </div>
                </div>
              </div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4 text-xs text-muted-foreground">
                  {item.author_username && (
                    <div className="flex items-center gap-1">
                      <User className="h-3 w-3" />
                      <span>@{item.author_username}</span>
                    </div>
                  )}
                  <div className="flex items-center gap-1">
                    <Calendar className="h-3 w-3" />
                    <span>{formatDate(item.created_at)}</span>
                  </div>
                  {isThread && (
                    <div className="flex items-center gap-1 text-primary">
                      <Link className="h-3 w-3" />
                      <span>{item.thread_length} tweets</span>
                    </div>
                  )}
                  {item.main_category && (
                    <div className="flex items-center gap-1">
                      <Tag className="h-3 w-3" />
                      <span>{item.main_category}</span>
                    </div>
                  )}
                </div>
                {totalEngagement > 0 && (
                  <div className="flex items-center gap-3 text-xs text-muted-foreground">
                    {engagement.likes > 0 && (
                      <div className="flex items-center gap-1">
                        <Heart className="h-3 w-3" />
                        <span>{formatNumber(engagement.likes)}</span>
                      </div>
                    )}
                    {engagement.retweets > 0 && (
                      <div className="flex items-center gap-1">
                        <Repeat2 className="h-3 w-3" />
                        <span>{formatNumber(engagement.retweets)}</span>
                      </div>
                    )}
                    {engagement.replies > 0 && (
                      <div className="flex items-center gap-1">
                        <MessageCircle className="h-3 w-3" />
                        <span>{formatNumber(engagement.replies)}</span>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </GlassCard>
    );
  }

  return (
    <GlassCard 
      variant={cardVariant} 
      elevated={isHighlighted}
      className={cn('cursor-pointer transition-all duration-300 hover:scale-[1.02]', className)} 
      onClick={onSelect}
    >
      <div className="p-5 relative z-10">
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center gap-2">
            <div className="p-1.5 bg-glass-tertiary rounded-lg border border-glass-border-tertiary backdrop-blur-sm">
              {getContentTypeIcon(item.content_type)}
            </div>
            <StatusBadge status={item.processing_state as any} size="sm" />
            {isThread && (
              <Tooltip content={`Thread with ${item.thread_length} tweets`}>
                <div className="flex items-center gap-1 text-xs text-primary bg-primary/10 px-2 py-1 rounded-full border border-primary/20">
                  <Link className="h-3 w-3" />
                  <span>{item.thread_length}</span>
                </div>
              </Tooltip>
            )}
          </div>
          <div className="flex items-center gap-2">
            {onToggleSelection && (
              <button 
                onClick={(e) => { e.stopPropagation(); onToggleSelection(); }} 
                className={cn(
                  'w-5 h-5 rounded border-2 flex items-center justify-center transition-all backdrop-blur-sm',
                  isSelected 
                    ? 'bg-primary border-primary text-primary-foreground' 
                    : 'border-glass-border-secondary hover:border-primary/50 hover:bg-glass-tertiary'
                )}
              >
                {isSelected && <Check className="h-3 w-3" />}
              </button>
            )}
            <LiquidButton variant="ghost" size="icon-sm">
              <MoreHorizontal className="h-4 w-4" />
            </LiquidButton>
          </div>
        </div>

        {hasMedia && previewMedia && !imageError && (
          <div className="mb-4">
            <div className="aspect-video rounded-xl overflow-hidden bg-glass-tertiary border border-glass-border-tertiary backdrop-blur-sm relative">
              {previewMedia.type === 'photo' ? (
                <img 
                  src={previewMedia.url} 
                  alt="Media preview" 
                  className="w-full h-full object-cover" 
                  onError={() => setImageError(true)} 
                />
              ) : (
                <div className="w-full h-full flex items-center justify-center">
                  {previewMedia.type === 'video' ? 
                    <Play className="h-8 w-8 text-muted-foreground" /> : 
                    <Image className="h-8 w-8 text-muted-foreground" />
                  }
                </div>
              )}
              {mediaCount > 1 && (
                <div className="absolute top-3 right-3 bg-black/70 text-white text-xs px-2 py-1 rounded-full backdrop-blur-sm">
                  +{mediaCount - 1}
                </div>
              )}
            </div>
          </div>
        )}

        <div className="mb-4">
          <h3 className="font-semibold text-foreground line-clamp-2 mb-2">
            {highlightText(item.title, searchQuery)}
          </h3>
          <p className="text-sm text-muted-foreground line-clamp-4">
            {highlightText(item.content.substring(0, 150) + (item.content.length > 150 ? '...' : ''), searchQuery)}
          </p>
        </div>

        {(item.main_category || item.sub_category) && (
          <div className="flex items-center gap-2 mb-4">
            {item.main_category && (
              <span className="text-xs px-3 py-1 bg-primary/20 text-primary rounded-full border border-primary/30 backdrop-blur-sm">
                {item.main_category}
              </span>
            )}
            {item.sub_category && (
              <span className="text-xs px-3 py-1 bg-glass-tertiary text-muted-foreground rounded-full border border-glass-border-tertiary backdrop-blur-sm">
                {item.sub_category}
              </span>
            )}
          </div>
        )}

        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <div className="flex items-center gap-3">
            {item.author_username && (
              <div className="flex items-center gap-1">
                <User className="h-3 w-3" />
                <span>@{item.author_username}</span>
              </div>
            )}
            <div className="flex items-center gap-1">
              <Calendar className="h-3 w-3" />
              <span>{formatDate(item.created_at)}</span>
            </div>
          </div>
          {totalEngagement > 0 && (
            <div className="flex items-center gap-3">
              {engagement.likes > 0 && (
                <div className="flex items-center gap-1">
                  <Heart className="h-3 w-3" />
                  <span>{formatNumber(engagement.likes)}</span>
                </div>
              )}
              {engagement.retweets > 0 && (
                <div className="flex items-center gap-1">
                  <Repeat2 className="h-3 w-3" />
                  <span>{formatNumber(engagement.retweets)}</span>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </GlassCard>
  );
};

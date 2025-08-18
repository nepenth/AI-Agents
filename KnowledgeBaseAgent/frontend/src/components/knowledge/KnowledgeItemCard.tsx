import React, { useState } from 'react';
import {
  HeartIcon,
  ArrowPathRoundedSquareIcon,
  ChatBubbleLeftIcon,
  ShareIcon,
  PhotoIcon,
  PlayIcon,
  DocumentTextIcon,
  TagIcon,
  CalendarIcon,
  UserIcon,
  LinkIcon,
  CheckIcon
} from '@heroicons/react/24/outline';
import { HeartIcon as HeartSolidIcon } from '@heroicons/react/24/solid';
import { Button } from '@/components/ui/Button';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { Tooltip } from '@/components/ui/Tooltip';
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
      return <DocumentTextIcon className="h-4 w-4" />;
    case 'thread':
      return <LinkIcon className="h-4 w-4" />;
    case 'media':
      return <PhotoIcon className="h-4 w-4" />;
    case 'video':
      return <PlayIcon className="h-4 w-4" />;
    default:
      return <DocumentTextIcon className="h-4 w-4" />;
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

  const cardClasses = cn(
    'p-5 rounded-[15px] cursor-pointer transition-transform duration-300 hover:-translate-y-1',
    'bg-glass-card-bg border border-glass-card-border shadow-glass-card backdrop-blur-glass-card',
    isHighlighted && 'ring-2 ring-primary/50',
    isSelected && 'ring-2 ring-blue-500/50',
    className
  );

  if (viewMode === 'list') {
    return (
      <div className={cardClasses} onClick={onSelect}>
        <div className="flex gap-4">
          {onToggleSelection && (
            <div className="flex-shrink-0 pt-1">
              <button
                onClick={(e) => { e.stopPropagation(); onToggleSelection(); }}
                className={cn('w-5 h-5 rounded border-2 flex items-center justify-center transition-all', isSelected ? 'bg-blue-500 border-blue-500 text-white' : 'border-gray-300 hover:border-blue-400')}
              >
                {isSelected && <CheckIcon className="h-3 w-3" />}
              </button>
            </div>
          )}
          {hasMedia && previewMedia && !imageError && (
            <div className="flex-shrink-0">
              <div className="w-16 h-16 rounded-lg overflow-hidden bg-gray-100">
                {previewMedia.type === 'photo' ? (
                  <img src={previewMedia.url} alt="Media preview" className="w-full h-full object-cover" onError={() => setImageError(true)} />
                ) : (
                  <div className="w-full h-full flex items-center justify-center bg-gray-200">
                    {previewMedia.type === 'video' ? <PlayIcon className="h-6 w-6 text-gray-500" /> : <PhotoIcon className="h-6 w-6 text-gray-500" />}
                  </div>
                )}
              </div>
              {mediaCount > 1 && <div className="text-xs text-muted-foreground mt-1 text-center">+{mediaCount - 1} more</div>}
            </div>
          )}
          <div className="flex-1 min-w-0">
            <div className="flex items-start justify-between gap-4 mb-2">
              <div className="flex-1">
                <h3 className="font-medium text-foreground line-clamp-2 mb-1">{highlightText(item.title, searchQuery)}</h3>
                <p className="text-sm text-muted-foreground line-clamp-3">{highlightText(item.content.substring(0, 200) + (item.content.length > 200 ? '...' : ''), searchQuery)}</p>
              </div>
              <div className="flex items-center gap-2">
                <StatusBadge status={item.processing_state as any} size="sm" />
                {getContentTypeIcon(item.content_type)}
              </div>
            </div>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4 text-xs text-muted-foreground">
                {item.author_username && <div className="flex items-center gap-1"><UserIcon className="h-3 w-3" /><span>@{item.author_username}</span></div>}
                <div className="flex items-center gap-1"><CalendarIcon className="h-3 w-3" /><span>{formatDate(item.created_at)}</span></div>
                {isThread && <div className="flex items-center gap-1"><LinkIcon className="h-3 w-3" /><span>{item.thread_length} tweets</span></div>}
                {item.main_category && <div className="flex items-center gap-1"><TagIcon className="h-3 w-3" /><span>{item.main_category}</span></div>}
              </div>
              {totalEngagement > 0 && (
                <div className="flex items-center gap-3 text-xs text-muted-foreground">
                  {engagement.likes > 0 && <div className="flex items-center gap-1"><HeartIcon className="h-3 w-3" /><span>{formatNumber(engagement.likes)}</span></div>}
                  {engagement.retweets > 0 && <div className="flex items-center gap-1"><ArrowPathRoundedSquareIcon className="h-3 w-3" /><span>{formatNumber(engagement.retweets)}</span></div>}
                  {engagement.replies > 0 && <div className="flex items-center gap-1"><ChatBubbleLeftIcon className="h-3 w-3" /><span>{formatNumber(engagement.replies)}</span></div>}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={cardClasses} onClick={onSelect}>
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          {getContentTypeIcon(item.content_type)}
          <StatusBadge status={item.processing_state as any} size="sm" />
          {isThread && <Tooltip content={`Thread with ${item.thread_length} tweets`}><div className="flex items-center gap-1 text-xs text-blue-500"><LinkIcon className="h-3 w-3" /><span>{item.thread_length}</span></div></Tooltip>}
        </div>
        {onToggleSelection && (
          <button onClick={(e) => { e.stopPropagation(); onToggleSelection(); }} className={cn('w-5 h-5 rounded border-2 flex items-center justify-center transition-all', isSelected ? 'bg-blue-500 border-blue-500 text-white' : 'border-gray-300 hover:border-blue-400')}>
            {isSelected && <CheckIcon className="h-3 w-3" />}
          </button>
        )}
      </div>
      {hasMedia && previewMedia && !imageError && (
        <div className="mb-3">
          <div className="aspect-video rounded-lg overflow-hidden bg-gray-100 relative">
            {previewMedia.type === 'photo' ? (
              <img src={previewMedia.url} alt="Media preview" className="w-full h-full object-cover" onError={() => setImageError(true)} />
            ) : (
              <div className="w-full h-full flex items-center justify-center bg-gray-200">
                {previewMedia.type === 'video' ? <PlayIcon className="h-8 w-8 text-gray-500" /> : <PhotoIcon className="h-8 w-8 text-gray-500" />}
              </div>
            )}
            {mediaCount > 1 && <div className="absolute top-2 right-2 bg-black/70 text-white text-xs px-2 py-1 rounded">+{mediaCount - 1}</div>}
          </div>
        </div>
      )}
      <div className="mb-3">
        <h3 className="font-medium text-foreground line-clamp-2 mb-2">{highlightText(item.title, searchQuery)}</h3>
        <p className="text-sm text-muted-foreground line-clamp-4">{highlightText(item.content.substring(0, 150) + (item.content.length > 150 ? '...' : ''), searchQuery)}</p>
      </div>
      {(item.main_category || item.sub_category) && (
        <div className="flex items-center gap-2 mb-3">
          {item.main_category && <span className="text-xs px-2 py-1 bg-primary/20 text-primary rounded-full">{item.main_category}</span>}
          {item.sub_category && <span className="text-xs px-2 py-1 bg-gray-500/20 text-gray-500 rounded-full">{item.sub_category}</span>}
        </div>
      )}
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <div className="flex items-center gap-2">
          {item.author_username && <div className="flex items-center gap-1"><UserIcon className="h-3 w-3" /><span>@{item.author_username}</span></div>}
          <div className="flex items-center gap-1"><CalendarIcon className="h-3 w-3" /><span>{formatDate(item.created_at)}</span></div>
        </div>
        {totalEngagement > 0 && (
          <div className="flex items-center gap-2">
            {engagement.likes > 0 && <div className="flex items-center gap-1"><HeartIcon className="h-3 w-3" /><span>{formatNumber(engagement.likes)}</span></div>}
            {engagement.retweets > 0 && <div className="flex items-center gap-1"><ArrowPathRoundedSquareIcon className="h-3 w-3" /><span>{formatNumber(engagement.retweets)}</span></div>}
          </div>
        )}
      </div>
    </div>
  );
};

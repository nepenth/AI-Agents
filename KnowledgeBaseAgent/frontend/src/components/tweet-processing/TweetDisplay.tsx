import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/Card';
import { StatusBadge } from '../ui/StatusBadge';
import { cn } from '../../utils/cn';

export interface TweetDisplayProps {
  tweetData: {
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
  };
  className?: string;
}

export const TweetDisplay: React.FC<TweetDisplayProps> = ({
  tweetData,
  className
}) => {
  const formatNumber = (num: number) => {
    if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`;
    if (num >= 1000) return `${(num / 1000).toFixed(1)}K`;
    return num.toString();
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const getTotalEngagement = () => {
    return Object.values(tweetData.publicMetrics).reduce((sum, count) => sum + count, 0);
  };

  const getEngagementLevel = () => {
    const total = getTotalEngagement();
    if (total > 10000) return { level: 'high', color: 'text-green-600' };
    if (total > 1000) return { level: 'medium', color: 'text-yellow-600' };
    return { level: 'low', color: 'text-gray-600' };
  };

  const engagement = getEngagementLevel();

  return (
    <Card className={cn('w-full', className)}>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span>Tweet Data</span>
          <div className="flex items-center gap-2">
            <StatusBadge status="success" label="Loaded" size="sm" />
            <span className="text-sm text-gray-500">ID: {tweetData.id}</span>
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Author Information */}
        <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
          <div className="w-12 h-12 bg-blue-500 rounded-full flex items-center justify-center text-white font-bold">
            {tweetData.author.name.charAt(0).toUpperCase()}
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <span className="font-semibold text-gray-900">{tweetData.author.name}</span>
              {tweetData.author.verified && (
                <span className="text-blue-500" title="Verified account">✓</span>
              )}
            </div>
            <div className="text-sm text-gray-600">@{tweetData.author.username}</div>
          </div>
          <div className="text-right">
            <div className="text-sm text-gray-500">
              {formatDate(tweetData.createdAt)}
            </div>
          </div>
        </div>

        {/* Tweet Content */}
        <div className="space-y-3">
          <div className="text-gray-900 leading-relaxed">
            {tweetData.text}
          </div>

          {/* Thread Information */}
          {tweetData.threadInfo && (
            <div className="bg-blue-50 p-3 rounded-lg border border-blue-200">
              <div className="flex items-center gap-2 text-sm">
                <span className="text-blue-600">🧵</span>
                <span className="font-medium text-blue-800">Thread Information</span>
              </div>
              <div className="text-sm text-blue-700 mt-1">
                {tweetData.threadInfo.isRoot ? (
                  <span>Root tweet of a {tweetData.threadInfo.length}-tweet thread</span>
                ) : (
                  <span>
                    Tweet {tweetData.threadInfo.position} of {tweetData.threadInfo.length} in thread
                  </span>
                )}
              </div>
            </div>
          )}

          {/* Media Content */}
          {tweetData.media && tweetData.media.length > 0 && (
            <div className="space-y-2">
              <div className="text-sm font-medium text-gray-700">
                Media Content ({tweetData.media.length} items):
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {tweetData.media.map((media, index) => (
                  <div key={media.id} className="bg-gray-50 p-3 rounded-lg border">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-lg">
                        {media.type === 'photo' ? '📸' : 
                         media.type === 'video' ? '🎥' : '🎬'}
                      </span>
                      <span className="text-sm font-medium capitalize">{media.type}</span>
                      {media.width && media.height && (
                        <span className="text-xs text-gray-500">
                          {media.width}×{media.height}
                        </span>
                      )}
                    </div>
                    {media.altText && (
                      <div className="text-xs text-gray-600 bg-white p-2 rounded border">
                        <strong>Alt text:</strong> {media.altText}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Engagement Metrics */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 p-4 bg-gray-50 rounded-lg">
          <div className="text-center">
            <div className="text-lg font-bold text-red-500">
              {formatNumber(tweetData.publicMetrics.likeCount)}
            </div>
            <div className="text-xs text-gray-600">Likes</div>
          </div>
          <div className="text-center">
            <div className="text-lg font-bold text-green-500">
              {formatNumber(tweetData.publicMetrics.retweetCount)}
            </div>
            <div className="text-xs text-gray-600">Retweets</div>
          </div>
          <div className="text-center">
            <div className="text-lg font-bold text-blue-500">
              {formatNumber(tweetData.publicMetrics.replyCount)}
            </div>
            <div className="text-xs text-gray-600">Replies</div>
          </div>
          <div className="text-center">
            <div className="text-lg font-bold text-purple-500">
              {formatNumber(tweetData.publicMetrics.quoteCount)}
            </div>
            <div className="text-xs text-gray-600">Quotes</div>
          </div>
        </div>

        {/* Total Engagement Summary */}
        <div className="flex items-center justify-between p-3 bg-gradient-to-r from-blue-50 to-purple-50 rounded-lg border">
          <div>
            <div className="text-sm font-medium text-gray-700">Total Engagement</div>
            <div className="text-2xl font-bold text-blue-600">
              {formatNumber(getTotalEngagement())}
            </div>
          </div>
          <div className="text-right">
            <div className={cn('text-sm font-medium', engagement.color)}>
              {engagement.level.toUpperCase()} ENGAGEMENT
            </div>
            <div className="text-xs text-gray-500">
              {engagement.level === 'high' ? 'Viral potential' :
               engagement.level === 'medium' ? 'Good reach' : 'Standard reach'}
            </div>
          </div>
        </div>

        {/* Context Annotations */}
        {tweetData.contextAnnotations && tweetData.contextAnnotations.length > 0 && (
          <div className="space-y-2">
            <div className="text-sm font-medium text-gray-700">
              Twitter Context Annotations ({tweetData.contextAnnotations.length}):
            </div>
            <div className="flex flex-wrap gap-2">
              {tweetData.contextAnnotations.slice(0, 6).map((annotation, index) => (
                <div
                  key={index}
                  className="text-xs bg-blue-100 text-blue-800 px-2 py-1 rounded-full border border-blue-200"
                  title={annotation.entity.description || annotation.domain.description}
                >
                  {annotation.domain.name}: {annotation.entity.name}
                </div>
              ))}
              {tweetData.contextAnnotations.length > 6 && (
                <div className="text-xs bg-gray-100 text-gray-600 px-2 py-1 rounded-full border">
                  +{tweetData.contextAnnotations.length - 6} more
                </div>
              )}
            </div>
          </div>
        )}

        {/* Processing Readiness Indicator */}
        <div className="flex items-center justify-between p-3 bg-green-50 rounded-lg border border-green-200">
          <div className="flex items-center gap-2">
            <span className="text-green-600">✅</span>
            <span className="text-sm font-medium text-green-800">Ready for Processing</span>
          </div>
          <div className="text-xs text-green-600">
            {tweetData.media?.length ? `${tweetData.media.length} media items` : 'Text only'} • 
            {tweetData.threadInfo ? ' Thread content' : ' Standalone tweet'} • 
            {tweetData.contextAnnotations?.length || 0} annotations
          </div>
        </div>
      </CardContent>
    </Card>
  );
};
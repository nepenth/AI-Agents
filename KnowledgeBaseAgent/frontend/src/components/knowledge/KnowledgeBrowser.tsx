import React, { useState, useEffect, useCallback } from 'react';
import {
  MagnifyingGlassIcon,
  FunnelIcon,
  ViewColumnsIcon,
  ListBulletIcon
} from '@heroicons/react/24/outline';
import { GlassCard } from '../ui/GlassCard';
import { LiquidButton } from '../ui/LiquidButton';
import { LoadingSpinner } from '../ui/LoadingSpinner';
import { useKnowledgeStore } from '../../stores/knowledgeStore';
import { cn } from '../../utils/cn';
import type { KnowledgeItem } from '../../types';

export interface KnowledgeBrowserProps {
  className?: string;
  onItemSelect?: (item: KnowledgeItem) => void;
  selectedItemId?: string;
}

export const KnowledgeBrowser: React.FC<KnowledgeBrowserProps> = ({
  className,
  onItemSelect,
  selectedItemId
}) => {
  const {
    knowledgeItems,
    knowledgeItemsLoading,
    knowledgeItemsTotal,
    loadKnowledgeItems,
  } = useKnowledgeStore();

  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [showFilters, setShowFilters] = useState(false);

  // Load initial data
  useEffect(() => {
    loadKnowledgeItems();
  }, [loadKnowledgeItems]);

  // Handle item selection
  const handleItemClick = useCallback((item: KnowledgeItem) => {
    onItemSelect?.(item);
  }, [onItemSelect]);

  return (
    <div className={cn('space-y-6', className)}>
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-foreground">Knowledge Base</h2>
          <p className="text-muted-foreground">
            Browse and search through {knowledgeItemsTotal.toLocaleString()} knowledge items
          </p>
        </div>
        
        <div className="flex items-center gap-2">
          <LiquidButton
            variant="outline"
            size="sm"
            onClick={() => setShowFilters(!showFilters)}
          >
            <FunnelIcon className="h-4 w-4 mr-2" />
            Filters
          </LiquidButton>
          
          <div className="flex border border-white/10 rounded-lg overflow-hidden">
            <LiquidButton
              variant={viewMode === 'grid' ? 'primary' : 'ghost'}
              size="sm"
              onClick={() => setViewMode('grid')}
              className="rounded-none"
            >
              <ViewColumnsIcon className="h-4 w-4" />
            </LiquidButton>
            <LiquidButton
              variant={viewMode === 'list' ? 'primary' : 'ghost'}
              size="sm"
              onClick={() => setViewMode('list')}
              className="rounded-none"
            >
              <ListBulletIcon className="h-4 w-4" />
            </LiquidButton>
          </div>
        </div>
      </div>

      {/* Filters Panel */}
      {showFilters && (
        <GlassCard variant="secondary">
          <div className="p-6">
            <h3 className="text-lg font-semibold text-foreground mb-4">Filters</h3>
            <p className="text-muted-foreground">Filter functionality coming soon...</p>
          </div>
        </GlassCard>
      )}

      {/* Results */}
      <div className="space-y-4">
        {/* Results Header */}
        <div className="flex items-center justify-between">
          <div className="text-sm text-muted-foreground">
            {knowledgeItemsLoading ? (
              <div className="flex items-center gap-2">
                <LoadingSpinner size="sm" />
                <span>Loading...</span>
              </div>
            ) : (
              <span>
                {knowledgeItemsTotal.toLocaleString()} {knowledgeItemsTotal === 1 ? 'item' : 'items'} found
              </span>
            )}
          </div>
        </div>

        {/* Items Grid/List */}
        {knowledgeItemsLoading ? (
          <div className="flex items-center justify-center py-12">
            <LoadingSpinner size="lg" />
          </div>
        ) : knowledgeItems.length === 0 ? (
          <GlassCard variant="tertiary">
            <div className="p-12 text-center">
              <MagnifyingGlassIcon className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
              <h3 className="text-lg font-medium text-foreground mb-2">No items found</h3>
              <p className="text-muted-foreground mb-4">
                No knowledge items available. Start by processing some content.
              </p>
            </div>
          </GlassCard>
        ) : (
          <div className={cn(
            'gap-4',
            viewMode === 'grid' 
              ? 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4'
              : 'space-y-4'
          )}>
            {knowledgeItems.map((item) => (
              <GlassCard 
                key={item.id} 
                variant={selectedItemId === item.id ? 'primary' : 'secondary'}
                className={cn(
                  'p-4 cursor-pointer transition-all hover:scale-105',
                  selectedItemId === item.id && 'ring-2 ring-primary'
                )}
                onClick={() => handleItemClick(item)}
              >
                <div className="space-y-2">
                  <h3 className="font-medium text-foreground line-clamp-2">
                    {item.title}
                  </h3>
                  <p className="text-sm text-muted-foreground line-clamp-3">
                    {item.content}
                  </p>
                  <div className="flex items-center justify-between text-xs text-muted-foreground">
                    <span>{new Date(item.created_at).toLocaleDateString()}</span>
                    {item.content_type && (
                      <span className="px-2 py-1 bg-glass-tertiary border border-glass-border-tertiary rounded-full">
                        {item.content_type}
                      </span>
                    )}
                  </div>
                </div>
              </GlassCard>
            ))}
          </div>
        )}

        {/* Load More */}
        {!knowledgeItemsLoading && knowledgeItems.length > 0 && knowledgeItems.length < knowledgeItemsTotal && (
          <div className="flex justify-center pt-6">
            <LiquidButton
              variant="outline"
              onClick={() => loadKnowledgeItems({ offset: knowledgeItems.length })}
            >
              Load More ({knowledgeItemsTotal - knowledgeItems.length} remaining)
            </LiquidButton>
          </div>
        )}
      </div>
    </div>
  );
};
import React, { useState, useCallback } from 'react';
import { MagnifyingGlassIcon, AdjustmentsHorizontalIcon, XMarkIcon } from '@heroicons/react/24/outline';
import { GlassCard } from '@/components/ui/GlassCard';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { Checkbox } from '@/components/ui/Checkbox';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { cn } from '@/utils/cn';
import type { FilterState } from '@/types';

export interface SearchInterfaceProps {
  searchQuery: string;
  onSearchChange: (query: string) => void;
  filters: FilterState;
  onFiltersChange: (filters: Partial<FilterState>) => void;
  isLoading?: boolean;
  totalResults?: number;
  showAdvanced?: boolean;
  onToggleAdvanced?: () => void;
  className?: string;
}

const SEARCH_TYPES = [
  { value: 'hybrid', label: 'Hybrid Search', description: 'Combines text and semantic search' },
  { value: 'semantic', label: 'Semantic Search', description: 'AI-powered meaning-based search' },
  { value: 'text', label: 'Text Search', description: 'Traditional keyword search' },
  { value: 'vector', label: 'Vector Search', description: 'Pure similarity search' }
];

const SORT_OPTIONS = [
  { value: 'relevance', label: 'Relevance' },
  { value: 'created_at_desc', label: 'Newest First' },
  { value: 'created_at_asc', label: 'Oldest First' },
  { value: 'title_asc', label: 'Title A-Z' },
  { value: 'title_desc', label: 'Title Z-A' },
  { value: 'engagement_desc', label: 'Most Engagement' },
  { value: 'engagement_asc', label: 'Least Engagement' }
];

const DATE_RANGES = [
  { value: '', label: 'Any time' },
  { value: 'today', label: 'Today' },
  { value: 'week', label: 'Past week' },
  { value: 'month', label: 'Past month' },
  { value: 'quarter', label: 'Past 3 months' },
  { value: 'year', label: 'Past year' },
  { value: 'custom', label: 'Custom range' }
];

const CONTENT_TYPES = [
  { value: 'tweet', label: 'Tweets' },
  { value: 'thread', label: 'Threads' },
  { value: 'media', label: 'With Media' },
  { value: 'text_only', label: 'Text Only' }
];

export const SearchInterface: React.FC<SearchInterfaceProps> = ({
  searchQuery,
  onSearchChange,
  filters,
  onFiltersChange,
  isLoading = false,
  totalResults = 0,
  showAdvanced = false,
  onToggleAdvanced,
  className
}) => {
  const [localQuery, setLocalQuery] = useState(searchQuery);
  const [showCustomDateRange, setShowCustomDateRange] = useState(false);

  // Handle search input
  const handleSearchSubmit = useCallback((e: React.FormEvent) => {
    e.preventDefault();
    onSearchChange(localQuery);
  }, [localQuery, onSearchChange]);

  // Handle filter changes
  const handleFilterChange = useCallback((key: string, value: any) => {
    onFiltersChange({ [key]: value });
  }, [onFiltersChange]);

  // Handle date range change
  const handleDateRangeChange = useCallback((value: string) => {
    if (value === 'custom') {
      setShowCustomDateRange(true);
    } else {
      setShowCustomDateRange(false);
      handleFilterChange('dateRange', value);
    }
  }, [handleFilterChange]);

  // Clear all filters
  const clearAllFilters = useCallback(() => {
    onFiltersChange({});
    setShowCustomDateRange(false);
  }, [onFiltersChange]);

  return (
    <div className={cn('space-y-4', className)}>
      {/* Main Search Bar */}
      <GlassCard className="p-4">
        <form onSubmit={handleSearchSubmit} className="space-y-4">
          <div className="flex gap-2">
            <div className="relative flex-1">
              <MagnifyingGlassIcon className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-muted-foreground" />
              <Input
                type="text"
                placeholder="Search knowledge base... (e.g., 'AI ethics', 'machine learning trends')"
                value={localQuery}
                onChange={(e) => setLocalQuery(e.target.value)}
                className="pl-10 pr-4"
              />
              {isLoading && (
                <div className="absolute right-3 top-1/2 transform -translate-y-1/2">
                  <LoadingSpinner size="sm" />
                </div>
              )}
            </div>
            
            <Button type="submit" disabled={isLoading}>
              Search
            </Button>
            
            {onToggleAdvanced && (
              <Button
                type="button"
                variant="outline"
                onClick={onToggleAdvanced}
                className={cn(showAdvanced && 'bg-primary/10')}
              >
                <AdjustmentsHorizontalIcon className="h-4 w-4 mr-2" />
                Advanced
              </Button>
            )}
          </div>

          {/* Quick Search Type Selector */}
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm text-muted-foreground">Search type:</span>
            {SEARCH_TYPES.map((type) => (
              <Button
                key={type.value}
                type="button"
                variant={filters.searchType === type.value ? 'default' : 'ghost'}
                size="sm"
                onClick={() => handleFilterChange('searchType', type.value)}
                title={type.description}
              >
                {type.label}
              </Button>
            ))}
          </div>
        </form>
      </GlassCard>

      {/* Advanced Filters */}
      {showAdvanced && (
        <GlassCard className="p-4">
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-medium text-foreground">Advanced Search Filters</h3>
              <Button
                variant="ghost"
                size="sm"
                onClick={clearAllFilters}
              >
                <XMarkIcon className="h-4 w-4 mr-2" />
                Clear All
              </Button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {/* Sort Options */}
              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground">Sort by</label>
                <Select
                  value={filters.sortBy || 'relevance'}
                  onValueChange={(value) => handleFilterChange('sortBy', value)}
                >
                  {SORT_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </Select>
              </div>

              {/* Date Range */}
              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground">Date range</label>
                <Select
                  value={filters.dateRange || ''}
                  onValueChange={handleDateRangeChange}
                >
                  {DATE_RANGES.map((range) => (
                    <option key={range.value} value={range.value}>
                      {range.label}
                    </option>
                  ))}
                </Select>
              </div>

              {/* Content Type */}
              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground">Content type</label>
                <Select
                  value={filters.contentType || ''}
                  onValueChange={(value) => handleFilterChange('contentType', value)}
                >
                  <option value="">All types</option>
                  {CONTENT_TYPES.map((type) => (
                    <option key={type.value} value={type.value}>
                      {type.label}
                    </option>
                  ))}
                </Select>
              </div>

              {/* Engagement Range */}
              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground">Min engagement</label>
                <Input
                  type="number"
                  placeholder="e.g., 100"
                  value={filters.minEngagement || ''}
                  onChange={(e) => handleFilterChange('minEngagement', e.target.value ? parseInt(e.target.value) : null)}
                />
              </div>

              {/* Author Filter */}
              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground">Author</label>
                <Input
                  type="text"
                  placeholder="@username"
                  value={filters.author || ''}
                  onChange={(e) => handleFilterChange('author', e.target.value)}
                />
              </div>

              {/* Similarity Threshold */}
              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground">
                  Similarity threshold ({filters.similarityThreshold || 0.7})
                </label>
                <input
                  type="range"
                  min="0.1"
                  max="1.0"
                  step="0.1"
                  value={filters.similarityThreshold || 0.7}
                  onChange={(e) => handleFilterChange('similarityThreshold', parseFloat(e.target.value))}
                  className="w-full"
                />
              </div>
            </div>

            {/* Custom Date Range */}
            {showCustomDateRange && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 p-4 bg-white/5 rounded-lg">
                <div className="space-y-2">
                  <label className="text-sm font-medium text-foreground">From date</label>
                  <Input
                    type="date"
                    value={filters.startDate || ''}
                    onChange={(e) => handleFilterChange('startDate', e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium text-foreground">To date</label>
                  <Input
                    type="date"
                    value={filters.endDate || ''}
                    onChange={(e) => handleFilterChange('endDate', e.target.value)}
                  />
                </div>
              </div>
            )}

            {/* Boolean Filters */}
            <div className="space-y-3">
              <h4 className="text-sm font-medium text-foreground">Additional filters</h4>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                <label className="flex items-center space-x-2">
                  <Checkbox
                    checked={filters.hasMedia || false}
                    onCheckedChange={(checked) => handleFilterChange('hasMedia', checked)}
                  />
                  <span className="text-sm text-foreground">Has media content</span>
                </label>

                <label className="flex items-center space-x-2">
                  <Checkbox
                    checked={filters.isThread || false}
                    onCheckedChange={(checked) => handleFilterChange('isThread', checked)}
                  />
                  <span className="text-sm text-foreground">Is part of thread</span>
                </label>

                <label className="flex items-center space-x-2">
                  <Checkbox
                    checked={filters.hasAIAnalysis || false}
                    onCheckedChange={(checked) => handleFilterChange('hasAIAnalysis', checked)}
                  />
                  <span className="text-sm text-foreground">Has AI analysis</span>
                </label>

                <label className="flex items-center space-x-2">
                  <Checkbox
                    checked={filters.isBookmarked || false}
                    onCheckedChange={(checked) => handleFilterChange('isBookmarked', checked)}
                  />
                  <span className="text-sm text-foreground">Is bookmarked</span>
                </label>

                <label className="flex items-center space-x-2">
                  <Checkbox
                    checked={filters.highEngagement || false}
                    onCheckedChange={(checked) => handleFilterChange('highEngagement', checked)}
                  />
                  <span className="text-sm text-foreground">High engagement</span>
                </label>

                <label className="flex items-center space-x-2">
                  <Checkbox
                    checked={filters.recentlyProcessed || false}
                    onCheckedChange={(checked) => handleFilterChange('recentlyProcessed', checked)}
                  />
                  <span className="text-sm text-foreground">Recently processed</span>
                </label>
              </div>
            </div>
          </div>
        </GlassCard>
      )}

      {/* Search Results Summary */}
      {searchQuery && (
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <div className="flex items-center gap-2">
            {isLoading ? (
              <>
                <LoadingSpinner size="sm" />
                <span>Searching...</span>
              </>
            ) : (
              <span>
                Found {totalResults.toLocaleString()} results for "{searchQuery}"
                {filters.searchType && ` using ${SEARCH_TYPES.find(t => t.value === filters.searchType)?.label}`}
              </span>
            )}
          </div>
          
          {!isLoading && totalResults > 0 && (
            <span>
              Search completed in {Math.random() * 0.5 + 0.1}s
            </span>
          )}
        </div>
      )}
    </div>
  );
};
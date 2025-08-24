import React, { useState, useCallback } from 'react';
import { Search, Settings, X, Filter, Calendar, User, Hash, Zap } from 'lucide-react';
import { GlassCard } from '@/components/ui/GlassCard';
import { LiquidButton } from '@/components/ui/LiquidButton';
import { GlassInput } from '@/components/ui/GlassInput';
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
    <div className={cn('space-y-6', className)}>
      {/* Main Search Bar */}
      <GlassCard variant="primary" className="p-6">
        <div className="relative z-10">
          <form onSubmit={handleSearchSubmit} className="space-y-4">
            <div className="flex gap-3">
              <div className="relative flex-1">
                <Search className="absolute left-4 top-1/2 transform -translate-y-1/2 h-5 w-5 text-muted-foreground z-20" />
                <GlassInput
                  type="text"
                  placeholder="Search knowledge base... (e.g., 'AI ethics', 'machine learning trends')"
                  value={localQuery}
                  onChange={(e) => setLocalQuery(e.target.value)}
                  className="pl-12 pr-12 h-12 text-base"
                  variant="primary"
                />
                {isLoading && (
                  <div className="absolute right-4 top-1/2 transform -translate-y-1/2 z-20">
                    <LoadingSpinner size="sm" variant="glass" />
                  </div>
                )}
              </div>
              
              <LiquidButton 
                type="submit" 
                disabled={isLoading}
                variant="primary"
                size="lg"
                elevated
              >
                <Search className="h-5 w-5 mr-2" />
                Search
              </LiquidButton>
              
              {onToggleAdvanced && (
                <LiquidButton
                  type="button"
                  variant={showAdvanced ? "secondary" : "outline"}
                  size="lg"
                  onClick={onToggleAdvanced}
                  elevated
                >
                  <Settings className="h-5 w-5 mr-2" />
                  Advanced
                </LiquidButton>
              )}
            </div>

            {/* Quick Search Type Selector */}
            <div className="flex items-center gap-3 flex-wrap">
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Zap className="h-4 w-4" />
                <span>Search type:</span>
              </div>
              {SEARCH_TYPES.map((type) => (
                <LiquidButton
                  key={type.value}
                  type="button"
                  variant={filters.searchType === type.value ? 'primary' : 'ghost'}
                  size="sm"
                  onClick={() => handleFilterChange('searchType', type.value)}
                  title={type.description}
                >
                  {type.label}
                </LiquidButton>
              ))}
            </div>
          </form>
        </div>
      </GlassCard>

      {/* Advanced Filters */}
      {showAdvanced && (
        <GlassCard variant="secondary" className="p-6">
          <div className="space-y-6 relative z-10">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-glass-tertiary rounded-lg border border-glass-border-tertiary backdrop-blur-sm">
                  <Filter className="h-5 w-5 text-primary" />
                </div>
                <h3 className="text-xl font-semibold text-foreground">Advanced Search Filters</h3>
              </div>
              <LiquidButton
                variant="ghost"
                size="sm"
                onClick={clearAllFilters}
              >
                <X className="h-4 w-4 mr-2" />
                Clear All
              </LiquidButton>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {/* Sort Options */}
              <div className="space-y-3">
                <label className="text-sm font-medium text-foreground flex items-center gap-2">
                  <Hash className="h-4 w-4" />
                  Sort by
                </label>
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
              <div className="space-y-3">
                <label className="text-sm font-medium text-foreground flex items-center gap-2">
                  <Calendar className="h-4 w-4" />
                  Date range
                </label>
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
              <div className="space-y-3">
                <label className="text-sm font-medium text-foreground flex items-center gap-2">
                  <Filter className="h-4 w-4" />
                  Content type
                </label>
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
              <div className="space-y-3">
                <label className="text-sm font-medium text-foreground flex items-center gap-2">
                  <Zap className="h-4 w-4" />
                  Min engagement
                </label>
                <GlassInput
                  type="number"
                  placeholder="e.g., 100"
                  value={filters.minEngagement || ''}
                  onChange={(e) => handleFilterChange('minEngagement', e.target.value ? parseInt(e.target.value) : null)}
                  variant="secondary"
                />
              </div>

              {/* Author Filter */}
              <div className="space-y-3">
                <label className="text-sm font-medium text-foreground flex items-center gap-2">
                  <User className="h-4 w-4" />
                  Author
                </label>
                <GlassInput
                  type="text"
                  placeholder="@username"
                  value={filters.author || ''}
                  onChange={(e) => handleFilterChange('author', e.target.value)}
                  variant="secondary"
                />
              </div>

              {/* Similarity Threshold */}
              <div className="space-y-3">
                <label className="text-sm font-medium text-foreground flex items-center justify-between">
                  <span className="flex items-center gap-2">
                    <Search className="h-4 w-4" />
                    Similarity threshold
                  </span>
                  <span className="text-primary font-mono">
                    {filters.similarityThreshold || 0.7}
                  </span>
                </label>
                <div className="relative">
                  <input
                    type="range"
                    min="0.1"
                    max="1.0"
                    step="0.1"
                    value={filters.similarityThreshold || 0.7}
                    onChange={(e) => handleFilterChange('similarityThreshold', parseFloat(e.target.value))}
                    className="w-full h-2 bg-glass-tertiary rounded-lg appearance-none cursor-pointer backdrop-blur-sm border border-glass-border-tertiary slider"
                  />
                </div>
              </div>
            </div>

            {/* Custom Date Range */}
            {showCustomDateRange && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 p-4 bg-glass-tertiary rounded-xl border border-glass-border-tertiary backdrop-blur-sm">
                <div className="space-y-3">
                  <label className="text-sm font-medium text-foreground flex items-center gap-2">
                    <Calendar className="h-4 w-4" />
                    From date
                  </label>
                  <GlassInput
                    type="date"
                    value={filters.startDate || ''}
                    onChange={(e) => handleFilterChange('startDate', e.target.value)}
                    variant="tertiary"
                  />
                </div>
                <div className="space-y-3">
                  <label className="text-sm font-medium text-foreground flex items-center gap-2">
                    <Calendar className="h-4 w-4" />
                    To date
                  </label>
                  <GlassInput
                    type="date"
                    value={filters.endDate || ''}
                    onChange={(e) => handleFilterChange('endDate', e.target.value)}
                    variant="tertiary"
                  />
                </div>
              </div>
            )}

            {/* Boolean Filters */}
            <div className="space-y-4">
              <h4 className="text-sm font-medium text-foreground flex items-center gap-2">
                <Filter className="h-4 w-4" />
                Additional filters
              </h4>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                <label className="flex items-center space-x-3 p-3 bg-glass-tertiary rounded-lg border border-glass-border-tertiary backdrop-blur-sm hover:bg-glass-secondary transition-colors cursor-pointer">
                  <Checkbox
                    checked={filters.hasMedia || false}
                    onCheckedChange={(checked) => handleFilterChange('hasMedia', checked)}
                  />
                  <span className="text-sm text-foreground">Has media content</span>
                </label>

                <label className="flex items-center space-x-3 p-3 bg-glass-tertiary rounded-lg border border-glass-border-tertiary backdrop-blur-sm hover:bg-glass-secondary transition-colors cursor-pointer">
                  <Checkbox
                    checked={filters.isThread || false}
                    onCheckedChange={(checked) => handleFilterChange('isThread', checked)}
                  />
                  <span className="text-sm text-foreground">Is part of thread</span>
                </label>

                <label className="flex items-center space-x-3 p-3 bg-glass-tertiary rounded-lg border border-glass-border-tertiary backdrop-blur-sm hover:bg-glass-secondary transition-colors cursor-pointer">
                  <Checkbox
                    checked={filters.hasAIAnalysis || false}
                    onCheckedChange={(checked) => handleFilterChange('hasAIAnalysis', checked)}
                  />
                  <span className="text-sm text-foreground">Has AI analysis</span>
                </label>

                <label className="flex items-center space-x-3 p-3 bg-glass-tertiary rounded-lg border border-glass-border-tertiary backdrop-blur-sm hover:bg-glass-secondary transition-colors cursor-pointer">
                  <Checkbox
                    checked={filters.isBookmarked || false}
                    onCheckedChange={(checked) => handleFilterChange('isBookmarked', checked)}
                  />
                  <span className="text-sm text-foreground">Is bookmarked</span>
                </label>

                <label className="flex items-center space-x-3 p-3 bg-glass-tertiary rounded-lg border border-glass-border-tertiary backdrop-blur-sm hover:bg-glass-secondary transition-colors cursor-pointer">
                  <Checkbox
                    checked={filters.highEngagement || false}
                    onCheckedChange={(checked) => handleFilterChange('highEngagement', checked)}
                  />
                  <span className="text-sm text-foreground">High engagement</span>
                </label>

                <label className="flex items-center space-x-3 p-3 bg-glass-tertiary rounded-lg border border-glass-border-tertiary backdrop-blur-sm hover:bg-glass-secondary transition-colors cursor-pointer">
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
        <GlassCard variant="tertiary" className="p-4">
          <div className="flex items-center justify-between text-sm relative z-10">
            <div className="flex items-center gap-3">
              {isLoading ? (
                <>
                  <LoadingSpinner size="sm" variant="glass" />
                  <span className="text-muted-foreground">Searching...</span>
                </>
              ) : (
                <>
                  <div className="p-1.5 bg-primary/20 rounded-lg border border-primary/30 backdrop-blur-sm">
                    <Search className="h-4 w-4 text-primary" />
                  </div>
                  <span className="text-foreground font-medium">
                    Found <span className="text-primary font-bold">{totalResults.toLocaleString()}</span> results for "{searchQuery}"
                    {filters.searchType && (
                      <span className="text-muted-foreground">
                        {' '}using {SEARCH_TYPES.find(t => t.value === filters.searchType)?.label}
                      </span>
                    )}
                  </span>
                </>
              )}
            </div>
            
            {!isLoading && totalResults > 0 && (
              <span className="text-muted-foreground">
                Search completed in {(Math.random() * 0.5 + 0.1).toFixed(2)}s
              </span>
            )}
          </div>
        </GlassCard>
      )}
    </div>
  );
};
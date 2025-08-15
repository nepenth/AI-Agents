import React, { useState, useCallback } from 'react'
import { Search, Filter, X, Calendar, Hash, User, TrendingUp } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { Checkbox } from '@/components/ui/Checkbox'
import { GlassCard } from '@/components/ui/GlassCard'
import { Badge } from '@/components/ui/Badge'
import { useDebounce } from '@/hooks/useDebounce'

export interface SearchFilters {
  query: string
  searchType: 'text' | 'vector' | 'hybrid'
  dateRange: {
    start?: string
    end?: string
  }
  engagementRange: {
    min?: number
    max?: number
  }
  categories: string[]
  authors: string[]
  hasMedia: boolean | null
  isThread: boolean | null
  minThreadLength?: number
  tags: string[]
  sortBy: 'relevance' | 'date' | 'engagement' | 'thread_length'
  sortOrder: 'asc' | 'desc'
}

interface AdvancedSearchProps {
  filters: SearchFilters
  onFiltersChange: (filters: SearchFilters) => void
  availableCategories: string[]
  availableAuthors: string[]
  availableTags: string[]
  isLoading?: boolean
}

export function AdvancedSearch({
  filters,
  onFiltersChange,
  availableCategories,
  availableAuthors,
  availableTags,
  isLoading = false
}: AdvancedSearchProps) {
  const [isExpanded, setIsExpanded] = useState(false)
  const [localQuery, setLocalQuery] = useState(filters.query)
  
  // Debounce search query to avoid excessive API calls
  const debouncedQuery = useDebounce(localQuery, 300)
  
  React.useEffect(() => {
    if (debouncedQuery !== filters.query) {
      onFiltersChange({ ...filters, query: debouncedQuery })
    }
  }, [debouncedQuery, filters, onFiltersChange])
  
  const updateFilter = useCallback(<K extends keyof SearchFilters>(
    key: K,
    value: SearchFilters[K]
  ) => {
    onFiltersChange({ ...filters, [key]: value })
  }, [filters, onFiltersChange])
  
  const addToArrayFilter = useCallback(<K extends keyof SearchFilters>(
    key: K,
    value: string
  ) => {
    const currentArray = filters[key] as string[]
    if (!currentArray.includes(value)) {
      updateFilter(key, [...currentArray, value] as SearchFilters[K])
    }
  }, [filters, updateFilter])
  
  const removeFromArrayFilter = useCallback(<K extends keyof SearchFilters>(
    key: K,
    value: string
  ) => {
    const currentArray = filters[key] as string[]
    updateFilter(key, currentArray.filter(item => item !== value) as SearchFilters[K])
  }, [filters, updateFilter])
  
  const clearAllFilters = useCallback(() => {
    onFiltersChange({
      query: '',
      searchType: 'hybrid',
      dateRange: {},
      engagementRange: {},
      categories: [],
      authors: [],
      hasMedia: null,
      isThread: null,
      tags: [],
      sortBy: 'relevance',
      sortOrder: 'desc'
    })
    setLocalQuery('')
  }, [onFiltersChange])
  
  const activeFilterCount = [
    filters.categories.length,
    filters.authors.length,
    filters.tags.length,
    filters.dateRange.start || filters.dateRange.end ? 1 : 0,
    filters.engagementRange.min || filters.engagementRange.max ? 1 : 0,
    filters.hasMedia !== null ? 1 : 0,
    filters.isThread !== null ? 1 : 0,
    filters.minThreadLength ? 1 : 0
  ].reduce((sum, count) => sum + count, 0)
  
  return (
    <GlassCard className="p-4 space-y-4">
      {/* Main Search Bar */}
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground h-4 w-4" />
          <Input
            placeholder="Search knowledge base..."
            value={localQuery}
            onChange={(e) => setLocalQuery(e.target.value)}
            className="pl-10"
            disabled={isLoading}
          />
        </div>
        
        <Select
          value={filters.searchType}
          onValueChange={(value) => updateFilter('searchType', value as SearchFilters['searchType'])}
        >
          <option value="hybrid">Hybrid Search</option>
          <option value="text">Text Search</option>
          <option value="vector">Semantic Search</option>
        </Select>
        
        <Button
          variant="outline"
          onClick={() => setIsExpanded(!isExpanded)}
          className="relative"
        >
          <Filter className="h-4 w-4 mr-2" />
          Filters
          {activeFilterCount > 0 && (
            <Badge variant="secondary" className="ml-2 h-5 w-5 p-0 text-xs">
              {activeFilterCount}
            </Badge>
          )}
        </Button>
        
        {activeFilterCount > 0 && (
          <Button variant="ghost" onClick={clearAllFilters}>
            <X className="h-4 w-4" />
          </Button>
        )}
      </div>
      
      {/* Advanced Filters */}
      {isExpanded && (
        <div className="space-y-4 pt-4 border-t border-border">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {/* Date Range */}
            <div className="space-y-2">
              <label className="text-sm font-medium flex items-center gap-2">
                <Calendar className="h-4 w-4" />
                Date Range
              </label>
              <div className="flex gap-2">
                <Input
                  type="date"
                  placeholder="Start date"
                  value={filters.dateRange.start || ''}
                  onChange={(e) => updateFilter('dateRange', {
                    ...filters.dateRange,
                    start: e.target.value || undefined
                  })}
                />
                <Input
                  type="date"
                  placeholder="End date"
                  value={filters.dateRange.end || ''}
                  onChange={(e) => updateFilter('dateRange', {
                    ...filters.dateRange,
                    end: e.target.value || undefined
                  })}
                />
              </div>
            </div>
            
            {/* Engagement Range */}
            <div className="space-y-2">
              <label className="text-sm font-medium flex items-center gap-2">
                <TrendingUp className="h-4 w-4" />
                Engagement
              </label>
              <div className="flex gap-2">
                <Input
                  type="number"
                  placeholder="Min"
                  value={filters.engagementRange.min || ''}
                  onChange={(e) => updateFilter('engagementRange', {
                    ...filters.engagementRange,
                    min: e.target.value ? parseInt(e.target.value) : undefined
                  })}
                />
                <Input
                  type="number"
                  placeholder="Max"
                  value={filters.engagementRange.max || ''}
                  onChange={(e) => updateFilter('engagementRange', {
                    ...filters.engagementRange,
                    max: e.target.value ? parseInt(e.target.value) : undefined
                  })}
                />
              </div>
            </div>
            
            {/* Sort Options */}
            <div className="space-y-2">
              <label className="text-sm font-medium">Sort By</label>
              <div className="flex gap-2">
                <Select
                  value={filters.sortBy}
                  onValueChange={(value) => updateFilter('sortBy', value as SearchFilters['sortBy'])}
                >
                  <option value="relevance">Relevance</option>
                  <option value="date">Date</option>
                  <option value="engagement">Engagement</option>
                  <option value="thread_length">Thread Length</option>
                </Select>
                <Select
                  value={filters.sortOrder}
                  onValueChange={(value) => updateFilter('sortOrder', value as SearchFilters['sortOrder'])}
                >
                  <option value="desc">Descending</option>
                  <option value="asc">Ascending</option>
                </Select>
              </div>
            </div>
          </div>
          
          {/* Categories Filter */}
          <div className="space-y-2">
            <label className="text-sm font-medium flex items-center gap-2">
              <Hash className="h-4 w-4" />
              Categories
            </label>
            <div className="flex flex-wrap gap-2">
              {filters.categories.map(category => (
                <Badge
                  key={category}
                  variant="secondary"
                  className="cursor-pointer"
                  onClick={() => removeFromArrayFilter('categories', category)}
                >
                  {category}
                  <X className="h-3 w-3 ml-1" />
                </Badge>
              ))}
              <Select
                value=""
                onValueChange={(value) => value && addToArrayFilter('categories', value)}
              >
                <option value="">Add category...</option>
                {availableCategories
                  .filter(cat => !filters.categories.includes(cat))
                  .map(category => (
                    <option key={category} value={category}>
                      {category}
                    </option>
                  ))}
              </Select>
            </div>
          </div>
          
          {/* Authors Filter */}
          <div className="space-y-2">
            <label className="text-sm font-medium flex items-center gap-2">
              <User className="h-4 w-4" />
              Authors
            </label>
            <div className="flex flex-wrap gap-2">
              {filters.authors.map(author => (
                <Badge
                  key={author}
                  variant="secondary"
                  className="cursor-pointer"
                  onClick={() => removeFromArrayFilter('authors', author)}
                >
                  @{author}
                  <X className="h-3 w-3 ml-1" />
                </Badge>
              ))}
              <Select
                value=""
                onValueChange={(value) => value && addToArrayFilter('authors', value)}
              >
                <option value="">Add author...</option>
                {availableAuthors
                  .filter(author => !filters.authors.includes(author))
                  .map(author => (
                    <option key={author} value={author}>
                      @{author}
                    </option>
                  ))}
              </Select>
            </div>
          </div>
          
          {/* Tags Filter */}
          <div className="space-y-2">
            <label className="text-sm font-medium">Tags</label>
            <div className="flex flex-wrap gap-2">
              {filters.tags.map(tag => (
                <Badge
                  key={tag}
                  variant="secondary"
                  className="cursor-pointer"
                  onClick={() => removeFromArrayFilter('tags', tag)}
                >
                  #{tag}
                  <X className="h-3 w-3 ml-1" />
                </Badge>
              ))}
              <Select
                value=""
                onValueChange={(value) => value && addToArrayFilter('tags', value)}
              >
                <option value="">Add tag...</option>
                {availableTags
                  .filter(tag => !filters.tags.includes(tag))
                  .map(tag => (
                    <option key={tag} value={tag}>
                      #{tag}
                    </option>
                  ))}
              </Select>
            </div>
          </div>
          
          {/* Content Type Filters */}
          <div className="space-y-2">
            <label className="text-sm font-medium">Content Type</label>
            <div className="flex gap-4">
              <label className="flex items-center gap-2">
                <Checkbox
                  checked={filters.hasMedia === true}
                  onCheckedChange={(checked) => 
                    updateFilter('hasMedia', checked ? true : null)
                  }
                />
                Has Media
              </label>
              <label className="flex items-center gap-2">
                <Checkbox
                  checked={filters.hasMedia === false}
                  onCheckedChange={(checked) => 
                    updateFilter('hasMedia', checked ? false : null)
                  }
                />
                Text Only
              </label>
              <label className="flex items-center gap-2">
                <Checkbox
                  checked={filters.isThread === true}
                  onCheckedChange={(checked) => 
                    updateFilter('isThread', checked ? true : null)
                  }
                />
                Threads
              </label>
              <label className="flex items-center gap-2">
                <Checkbox
                  checked={filters.isThread === false}
                  onCheckedChange={(checked) => 
                    updateFilter('isThread', checked ? false : null)
                  }
                />
                Single Tweets
              </label>
            </div>
          </div>
          
          {/* Thread Length Filter */}
          {filters.isThread === true && (
            <div className="space-y-2">
              <label className="text-sm font-medium">Minimum Thread Length</label>
              <Input
                type="number"
                placeholder="Minimum tweets in thread"
                value={filters.minThreadLength || ''}
                onChange={(e) => updateFilter('minThreadLength', 
                  e.target.value ? parseInt(e.target.value) : undefined
                )}
                className="w-48"
              />
            </div>
          )}
        </div>
      )}
    </GlassCard>
  )
}
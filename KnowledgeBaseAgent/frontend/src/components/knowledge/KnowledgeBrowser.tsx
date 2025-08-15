import React, { useState, useEffect, useCallback } from 'react';
import { MagnifyingGlassIcon, FunnelIcon, ViewColumnsIcon, ListBulletIcon } from '@heroicons/react/24/outline';
import { useKnowledgeStore } from '@/stores/knowledgeStore';
import { useDebounce } from '@/hooks/useDebounce';
import { GlassCard } from '@/components/ui/GlassCard';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { SearchInterface } from './SearchInterface';
import { ContentViewer } from './ContentViewer';
import { CategoryExplorer } from './CategoryExplorer';
import { KnowledgeItemCard } from './KnowledgeItemCard';
import { cn } from '@/utils/cn';
import type { KnowledgeItem, FilterState } from '@/types';

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
    categories,
    filters,
    viewMode,
    searchQuery,
    searchResults,
    searchLoading,
    loadKnowledgeItems,
    loadCategories,
    searchKnowledge,
    clearSearch,
    setFilters,
    clearFilters,
    setViewMode,
    toggleItemSelection,
    selectedItems
  } = useKnowledgeStore();

  const [localSearchQuery, setLocalSearchQuery] = useState(searchQuery);
  const [showFilters, setShowFilters] = useState(false);
  const [showCategoryExplorer, setShowCategoryExplorer] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  
  const debouncedSearchQuery = useDebounce(localSearchQuery, 300);

  // Load initial data
  useEffect(() => {
    loadKnowledgeItems();
    loadCategories();
  }, [loadKnowledgeItems, loadCategories]);

  // Handle search
  useEffect(() => {
    if (debouncedSearchQuery.trim()) {
      searchKnowledge(debouncedSearchQuery, {
        ...filters,
        category: selectedCategory
      });
    } else {
      clearSearch();
    }
  }, [debouncedSearchQuery, filters, selectedCategory, searchKnowledge, clearSearch]);

  // Handle filter changes
  const handleFilterChange = useCallback((newFilters: Partial<FilterState>) => {
    setFilters(newFilters);
    
    // Reload items with new filters
    if (!searchQuery.trim()) {
      loadKnowledgeItems({ ...filters, ...newFilters });
    }
  }, [filters, searchQuery, setFilters, loadKnowledgeItems]);

  // Handle category selection
  const handleCategorySelect = useCallback((categoryId: string | null) => {
    setSelectedCategory(categoryId);
    handleFilterChange({ category: categoryId });
  }, [handleFilterChange]);

  // Clear all filters
  const handleClearFilters = useCallback(() => {
    clearFilters();
    setSelectedCategory(null);
    setLocalSearchQuery('');
    clearSearch();
    loadKnowledgeItems();
  }, [clearFilters, clearSearch, loadKnowledgeItems]);

  // Get items to display (search results or regular items)
  const itemsToDisplay = searchQuery.trim() ? searchResults.map(r => r.item) : knowledgeItems;
  const isLoading = searchQuery.trim() ? searchLoading : knowledgeItemsLoading;
  const totalItems = searchQuery.trim() ? searchResults.length : knowledgeItemsTotal;

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
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowCategoryExplorer(!showCategoryExplorer)}
          >
            <FunnelIcon className="h-4 w-4 mr-2" />
            Categories
          </Button>
          
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowFilters(!showFilters)}
          >
            <FunnelIcon className="h-4 w-4 mr-2" />
            Filters
          </Button>
          
          <div className="flex border rounded-lg overflow-hidden">
            <Button
              variant={viewMode === 'grid' ? 'default' : 'ghost'}
              size="sm"
              onClick={() => setViewMode('grid')}
              className="rounded-none"
            >
              <ViewColumnsIcon className="h-4 w-4" />
            </Button>
            <Button
              variant={viewMode === 'list' ? 'default' : 'ghost'}
              size="sm"
              onClick={() => setViewMode('list')}
              className="rounded-none"
            >
              <ListBulletIcon className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>

      {/* Search Interface */}
      <SearchInterface
        searchQuery={localSearchQuery}
        onSearchChange={setLocalSearchQuery}
        filters={filters}
        onFiltersChange={handleFilterChange}
        isLoading={isLoading}
        totalResults={totalItems}
        showAdvanced={showFilters}
        onToggleAdvanced={() => setShowFilters(!showFilters)}
      />

      {/* Category Explorer */}
      {showCategoryExplorer && (
        <GlassCard>
          <CategoryExplorer
            categories={categories}
            selectedCategory={selectedCategory}
            onCategorySelect={handleCategorySelect}
            onClose={() => setShowCategoryExplorer(false)}
          />
        </GlassCard>
      )}

      {/* Active Filters */}
      {(Object.keys(filters).length > 0 || selectedCategory || searchQuery.trim()) && (
        <GlassCard className="p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-sm font-medium text-foreground">Active filters:</span>
              
              {searchQuery.trim() && (
                <span className="inline-flex items-center px-2 py-1 rounded-full text-xs bg-primary/20 text-primary">
                  Search: "{searchQuery}"
                </span>
              )}
              
              {selectedCategory && (
                <span className="inline-flex items-center px-2 py-1 rounded-full text-xs bg-blue-500/20 text-blue-500">
                  Category: {categories.find(c => c.id === selectedCategory)?.name || selectedCategory}
                </span>
              )}
              
              {Object.entries(filters).map(([key, value]) => {
                if (!value || key === 'category') return null;
                return (
                  <span
                    key={key}
                    className="inline-flex items-center px-2 py-1 rounded-full text-xs bg-gray-500/20 text-gray-500"
                  >
                    {key}: {String(value)}
                  </span>
                );
              })}
            </div>
            
            <Button
              variant="ghost"
              size="sm"
              onClick={handleClearFilters}
            >
              Clear all
            </Button>
          </div>
        </GlassCard>
      )}

      {/* Results */}
      <div className="space-y-4">
        {/* Results Header */}
        <div className="flex items-center justify-between">
          <div className="text-sm text-muted-foreground">
            {isLoading ? (
              <div className="flex items-center gap-2">
                <LoadingSpinner size="sm" />
                <span>Loading...</span>
              </div>
            ) : (
              <span>
                {totalItems.toLocaleString()} {totalItems === 1 ? 'item' : 'items'} found
                {searchQuery.trim() && ` for "${searchQuery}"`}
              </span>
            )}
          </div>
          
          {selectedItems.length > 0 && (
            <div className="text-sm text-muted-foreground">
              {selectedItems.length} selected
            </div>
          )}
        </div>

        {/* Items Grid/List */}
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <LoadingSpinner size="lg" />
          </div>
        ) : itemsToDisplay.length === 0 ? (
          <GlassCard className="p-12 text-center">
            <MagnifyingGlassIcon className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
            <h3 className="text-lg font-medium text-foreground mb-2">No items found</h3>
            <p className="text-muted-foreground mb-4">
              {searchQuery.trim() 
                ? `No results found for "${searchQuery}". Try adjusting your search terms or filters.`
                : 'No knowledge items available. Start by processing some content.'
              }
            </p>
            {(searchQuery.trim() || Object.keys(filters).length > 0) && (
              <Button onClick={handleClearFilters}>
                Clear filters
              </Button>
            )}
          </GlassCard>
        ) : (
          <div className={cn(
            'gap-4',
            viewMode === 'grid' 
              ? 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4'
              : 'space-y-4'
          )}>
            {itemsToDisplay.map((item) => (
              <KnowledgeItemCard
                key={item.id}
                item={item}
                viewMode={viewMode}
                isSelected={selectedItems.includes(item.id)}
                isHighlighted={selectedItemId === item.id}
                onSelect={() => handleItemClick(item)}
                onToggleSelection={() => toggleItemSelection(item.id)}
                searchQuery={searchQuery}
              />
            ))}
          </div>
        )}

        {/* Load More */}
        {!isLoading && itemsToDisplay.length > 0 && itemsToDisplay.length < totalItems && (
          <div className="flex justify-center pt-6">
            <Button
              variant="outline"
              onClick={() => {
                if (searchQuery.trim()) {
                  // Load more search results
                  searchKnowledge(searchQuery, {
                    ...filters,
                    offset: searchResults.length
                  });
                } else {
                  // Load more regular items
                  loadKnowledgeItems({
                    ...filters,
                    offset: knowledgeItems.length
                  });
                }\n              }}
            >\n              Load More ({totalItems - itemsToDisplay.length} remaining)\n            </Button>\n          </div>\n        )}\n      </div>\n    </div>\n  );\n};"
import React, { useState, useMemo } from 'react';
import { ChevronRightIcon, ChevronDownIcon, XMarkIcon, TagIcon } from '@heroicons/react/24/outline';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { cn } from '@/utils/cn';
import type { Category } from '@/services/knowledgeService';

export interface CategoryExplorerProps {
  categories: Category[];
  selectedCategory?: string | null;
  onCategorySelect: (categoryId: string | null) => void;
  onClose?: () => void;
  className?: string;
}

interface CategoryNode extends Category {
  children: CategoryNode[];
  level: number;
}

export const CategoryExplorer: React.FC<CategoryExplorerProps> = ({
  categories,
  selectedCategory,
  onCategorySelect,
  onClose,
  className
}) => {
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set());
  const [searchQuery, setSearchQuery] = useState('');

  // Build category tree
  const categoryTree = useMemo(() => {
    const categoryMap = new Map<string, CategoryNode>();
    const rootCategories: CategoryNode[] = [];

    // First pass: create all nodes
    categories.forEach(category => {
      categoryMap.set(category.id, {
        ...category,
        children: [],
        level: 0
      });
    });

    // Second pass: build tree structure
    categories.forEach(category => {
      const node = categoryMap.get(category.id)!;
      
      if (category.parent_id && categoryMap.has(category.parent_id)) {
        const parent = categoryMap.get(category.parent_id)!;
        parent.children.push(node);
        node.level = parent.level + 1;
      } else {
        rootCategories.push(node);
      }
    });

    // Sort categories by item count (descending) and then by name
    const sortCategories = (cats: CategoryNode[]) => {
      cats.sort((a, b) => {
        if (b.item_count !== a.item_count) {
          return b.item_count - a.item_count;
        }
        return a.name.localeCompare(b.name);
      });
      cats.forEach(cat => sortCategories(cat.children));
    };

    sortCategories(rootCategories);
    return rootCategories;
  }, [categories]);

  // Filter categories based on search
  const filteredCategories = useMemo(() => {
    if (!searchQuery.trim()) return categoryTree;

    const matchesSearch = (category: CategoryNode): boolean => {
      return category.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
             category.description?.toLowerCase().includes(searchQuery.toLowerCase()) ||
             category.children.some(matchesSearch);
    };

    const filterTree = (cats: CategoryNode[]): CategoryNode[] => {
      return cats.filter(matchesSearch).map(cat => ({
        ...cat,
        children: filterTree(cat.children)
      }));
    };

    return filterTree(categoryTree);
  }, [categoryTree, searchQuery]);

  // Toggle category expansion
  const toggleExpanded = (categoryId: string) => {
    const newExpanded = new Set(expandedCategories);
    if (newExpanded.has(categoryId)) {
      newExpanded.delete(categoryId);
    } else {
      newExpanded.add(categoryId);
    }
    setExpandedCategories(newExpanded);
  };

  // Render category node
  const renderCategory = (category: CategoryNode) => {
    const isExpanded = expandedCategories.has(category.id);
    const isSelected = selectedCategory === category.id;
    const hasChildren = category.children.length > 0;

    return (
      <div key={category.id} className="space-y-1">
        <div
          className={cn(
            'flex items-center gap-2 p-2 rounded-lg cursor-pointer transition-all',
            'hover:bg-white/10',
            isSelected && 'bg-primary/20 ring-1 ring-primary/30',
            `ml-${category.level * 4}`
          )}
          onClick={() => onCategorySelect(isSelected ? null : category.id)}
        >
          {/* Expand/Collapse Button */}
          <button
            onClick={(e) => {
              e.stopPropagation();
              if (hasChildren) {
                toggleExpanded(category.id);
              }
            }}
            className={cn(
              'flex-shrink-0 w-5 h-5 flex items-center justify-center rounded',
              hasChildren ? 'hover:bg-white/20' : 'invisible'
            )}
          >
            {hasChildren && (
              isExpanded ? (
                <ChevronDownIcon className="h-3 w-3" />
              ) : (
                <ChevronRightIcon className="h-3 w-3" />
              )
            )}
          </button>

          {/* Category Icon */}
          <div className={cn(
            'flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center text-xs',
            category.color ? `bg-${category.color}-500/20 text-${category.color}-500` : 'bg-gray-500/20 text-gray-500'
          )}>
            {category.icon ? (
              <span>{category.icon}</span>
            ) : (
              <TagIcon className="h-3 w-3" />
            )}
          </div>

          {/* Category Info */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className={cn(
                'font-medium truncate',
                isSelected ? 'text-primary' : 'text-foreground'
              )}>
                {category.name}
              </span>
              <span className={cn(
                'text-xs px-2 py-0.5 rounded-full',
                isSelected 
                  ? 'bg-primary/30 text-primary' 
                  : 'bg-muted text-muted-foreground'
              )}>
                {category.item_count}
              </span>
            </div>
            {category.description && (
              <p className="text-xs text-muted-foreground truncate mt-0.5">
                {category.description}
              </p>
            )}
          </div>

          {/* AI Generated Badge */}
          {category.is_ai_generated && (
            <span className="text-xs px-2 py-0.5 bg-blue-500/20 text-blue-500 rounded-full">
              AI
            </span>
          )}
        </div>

        {/* Children */}
        {hasChildren && isExpanded && (
          <div className="space-y-1">
            {category.children.map(renderCategory)}
          </div>
        )}
      </div>
    );
  };

  // Get category stats
  const totalCategories = categories.length;
  const totalItems = categories.reduce((sum, cat) => sum + cat.item_count, 0);
  const aiGeneratedCount = categories.filter(cat => cat.is_ai_generated).length;

  return (
    <div className={cn('space-y-4', className)}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-medium text-foreground">Category Explorer</h3>
          <p className="text-sm text-muted-foreground">
            {totalCategories} categories • {totalItems.toLocaleString()} items
            {aiGeneratedCount > 0 && ` • ${aiGeneratedCount} AI-generated`}
          </p>
        </div>
        {onClose && (
          <Button variant="ghost" size="sm" onClick={onClose}>
            <XMarkIcon className="h-4 w-4" />
          </Button>
        )}
      </div>

      {/* Search */}
      <div className="relative">
        <Input
          type="text"
          placeholder="Search categories..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="pr-8"
        />
        {searchQuery && (
          <button
            onClick={() => setSearchQuery('')}
            className="absolute right-2 top-1/2 transform -translate-y-1/2 text-muted-foreground hover:text-foreground"
          >
            <XMarkIcon className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* Quick Actions */}
      <div className="flex items-center gap-2 flex-wrap">
        <Button
          variant={selectedCategory === null ? 'default' : 'ghost'}
          size="sm"
          onClick={() => onCategorySelect(null)}
        >
          All Categories
        </Button>
        
        {/* Top categories */}
        {categoryTree.slice(0, 5).map(category => (
          <Button
            key={category.id}
            variant={selectedCategory === category.id ? 'default' : 'ghost'}
            size="sm"
            onClick={() => onCategorySelect(category.id)}
          >
            {category.icon && <span className="mr-1">{category.icon}</span>}
            {category.name}
            <span className="ml-1 text-xs opacity-70">
              {category.item_count}
            </span>
          </Button>
        ))}
      </div>

      {/* Category Tree */}
      <div className="max-h-96 overflow-y-auto space-y-1">
        {filteredCategories.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">
            {searchQuery ? (
              <>
                <TagIcon className="h-8 w-8 mx-auto mb-2 opacity-50" />
                <p>No categories found for "{searchQuery}"</p>
              </>
            ) : (
              <>
                <TagIcon className="h-8 w-8 mx-auto mb-2 opacity-50" />
                <p>No categories available</p>
              </>
            )}
          </div>
        ) : (
          filteredCategories.map(renderCategory)
        )}
      </div>

      {/* Selected Category Info */}
      {selectedCategory && (
        <div className="p-3 bg-primary/10 rounded-lg border border-primary/20">
          {(() => {
            const category = categories.find(c => c.id === selectedCategory);
            if (!category) return null;
            
            return (
              <div className="flex items-start gap-3">
                <div className={cn(
                  'flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center',
                  category.color ? `bg-${category.color}-500/20 text-${category.color}-500` : 'bg-gray-500/20 text-gray-500'
                )}>
                  {category.icon ? (
                    <span className="text-sm">{category.icon}</span>
                  ) : (
                    <TagIcon className="h-4 w-4" />
                  )}
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <h4 className="font-medium text-primary">{category.name}</h4>
                    <span className="text-xs px-2 py-0.5 bg-primary/20 text-primary rounded-full">
                      {category.item_count} items
                    </span>
                    {category.is_ai_generated && (
                      <span className="text-xs px-2 py-0.5 bg-blue-500/20 text-blue-500 rounded-full">
                        AI Generated
                      </span>
                    )}
                  </div>
                  {category.description && (
                    <p className="text-sm text-muted-foreground">{category.description}</p>
                  )}
                  <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
                    <span>Created: {new Date(category.created_at).toLocaleDateString()}</span>
                    {category.updated_at !== category.created_at && (
                      <span>Updated: {new Date(category.updated_at).toLocaleDateString()}</span>
                    )}
                  </div>
                </div>
              </div>
            );
          })()}
        </div>
      )}
    </div>
  );
};
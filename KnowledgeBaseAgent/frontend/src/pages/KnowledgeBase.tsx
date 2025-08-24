import * as React from 'react';
import { Link } from 'react-router-dom';
import { useKnowledgeStore } from '@/stores';
import { useDebounce } from '@/hooks/useDebounce';
import { GlassCard } from '@/components/ui/GlassCard';
import { Input } from '@/components/ui/Input';
import { LiquidButton } from '@/components/ui/LiquidButton';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { PageLayout, PageHeader, PageSection, PageContent } from '@/components/layout/PageLayout';
import { LayoutGridIcon, ListIcon, SearchIcon } from 'lucide-react';
import { cn } from '@/utils/cn';

function SearchControls() {
  const { viewMode, setViewMode, searchQuery, setSearchQuery } = useKnowledgeStore(
    (state) => ({
      viewMode: state.viewMode,
      setViewMode: state.setViewMode,
      searchQuery: state.searchQuery,
      setSearchQuery: state.setFilters, // Simplified for now
    })
  );

  const [localQuery, setLocalQuery] = React.useState(searchQuery);
  const debouncedQuery = useDebounce(localQuery, 300);

  React.useEffect(() => {
    setSearchQuery({ search: debouncedQuery });
  }, [debouncedQuery, setSearchQuery]);

  return (
    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
      <div className="relative flex-1 max-w-md">
        <SearchIcon className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Search knowledge items..."
          className="pl-10"
          value={localQuery}
          onChange={(e) => setLocalQuery(e.target.value)}
        />
      </div>
      <div className="flex items-center gap-2">
        <LiquidButton 
          variant={viewMode === 'grid' ? 'primary' : 'outline'} 
          size="sm" 
          onClick={() => setViewMode('grid')}
        >
          <LayoutGridIcon className="h-4 w-4 mr-2" />
          Grid
        </LiquidButton>
        <LiquidButton 
          variant={viewMode === 'list' ? 'primary' : 'outline'} 
          size="sm" 
          onClick={() => setViewMode('list')}
        >
          <ListIcon className="h-4 w-4 mr-2" />
          List
        </LiquidButton>
      </div>
    </div>
  );
}

function ItemCard({ item }: { item: any }) {
  return (
    <GlassCard variant="secondary" className="h-full p-4 transition-all hover:scale-105 hover:shadow-glass-primary">
      <Link to={`/knowledge/${item.id}`} className="block space-y-3">
        <div>
          <h3 className="font-semibold text-foreground truncate leading-tight">
            {item.display_title || item.title}
          </h3>
          {(item.main_category || item.sub_category) && (
            <div className="flex items-center gap-1 mt-1 text-xs text-muted-foreground">
              {item.main_category && (
                <span className="px-2 py-1 bg-primary/10 text-primary rounded-full">
                  {item.main_category}
                </span>
              )}
              {item.sub_category && (
                <span className="px-2 py-1 bg-muted/20 text-muted-foreground rounded-full">
                  {item.sub_category}
                </span>
              )}
            </div>
          )}
        </div>
        <p className="text-sm text-muted-foreground line-clamp-3 leading-relaxed">
          {item.summary || item.content || 'No summary available.'}
        </p>
        {item.created_at && (
          <div className="text-xs text-muted-foreground/70">
            {new Date(item.created_at).toLocaleDateString()}
          </div>
        )}
      </Link>
    </GlassCard>
  );
}

function KnowledgeGrid() {
  const { items, isLoading, viewMode, knowledgeItemsTotal } = useKnowledgeStore((state) => ({
    items: state.knowledgeItems,
    isLoading: state.knowledgeItemsLoading,
    viewMode: state.viewMode,
    knowledgeItemsTotal: state.knowledgeItemsTotal
  }));

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  if (!items.length) {
    return (
      <GlassCard variant="tertiary" className="p-12 text-center">
        <SearchIcon className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
        <h3 className="text-lg font-medium text-foreground mb-2">No items found</h3>
        <p className="text-muted-foreground">
          No knowledge items match your search criteria. Try adjusting your search terms.
        </p>
      </GlassCard>
    );
  }

  return (
    <div className="space-y-4">
      {/* Results count */}
      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span>
          Showing {items.length} of {knowledgeItemsTotal.toLocaleString()} items
        </span>
      </div>

      {/* Grid/List layout */}
      <div className={cn(
        viewMode === 'grid' 
          ? 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4'
          : 'space-y-3'
      )}>
        {items.map((item) => (
          <ItemCard key={item.id} item={item} />
        ))}
      </div>
    </div>
  );
}

export function KnowledgeBase() {
  const { loadKnowledgeItems, filters, knowledgeItemsTotal } = useKnowledgeStore();

  React.useEffect(() => {
    loadKnowledgeItems(filters);
  }, [filters, loadKnowledgeItems]);

  return (
    <PageLayout maxWidth="2xl" spacing="lg">
      <PageHeader
        title="Knowledge Base"
        description={`Browse and manage your knowledge collection. ${knowledgeItemsTotal.toLocaleString()} items available.`}
      />
      
      <PageSection spacing="md">
        <SearchControls />
      </PageSection>
      
      <PageSection spacing="lg">
        <KnowledgeGrid />
      </PageSection>
    </PageLayout>
  );
}

import * as React from 'react';
import { Link } from 'react-router-dom';
import { useKnowledgeStore } from '@/stores';
import { useDebounce } from '@/hooks/useDebounce';
import { GlassCard } from '@/components/ui/GlassCard';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';
import { Select } from '@/components/ui/Select';
import { LayoutGridIcon, ListIcon } from 'lucide-react';
import { cn } from '@/utils/cn';

function KBBrowserHeader() {
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
    setSearchQuery({ query: debouncedQuery });
  }, [debouncedQuery, setSearchQuery]);

  return (
    <div className="flex justify-between items-center mb-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-foreground">Knowledge Base</h2>
        <p className="text-muted-foreground">Browse and manage your knowledge.</p>
      </div>
      <div className="flex items-center gap-2">
        <Input
          placeholder="Search..."
          className="w-64"
          value={localQuery}
          onChange={(e) => setLocalQuery(e.target.value)}
        />
        <Button variant={viewMode === 'grid' ? 'default' : 'outline'} size="icon" onClick={() => setViewMode('grid')}>
          <LayoutGridIcon className="h-5 w-5" />
        </Button>
        <Button variant={viewMode === 'list' ? 'default' : 'outline'} size="icon" onClick={() => setViewMode('list')}>
          <ListIcon className="h-5 w-5" />
        </Button>
      </div>
    </div>
  );
}

function ItemCard({ item }: { item: any }) {
  return (
    <GlassCard className="h-full">
      <Link to={`/knowledge/${item.id}`} className="block">
        <h3 className="font-semibold text-foreground truncate">{item.display_title || item.title}</h3>
        <p className="text-sm text-muted-foreground line-clamp-3 mt-2">
          {item.summary || 'No summary available.'}
        </p>
        <div className="text-xs text-muted-foreground/80 mt-4">
          {item.main_category} &gt; {item.sub_category}
        </div>
      </Link>
    </GlassCard>
  );
}

function KBGrid() {
  const { items, isLoading } = useKnowledgeStore((state) => ({
    items: state.knowledgeItems,
    isLoading: state.knowledgeItemsLoading,
  }));

  if (isLoading) return <div>Loading...</div>;
  if (!items.length) return <div>No items found.</div>;

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {items.map((item) => (
        <ItemCard key={item.id} item={item} />
      ))}
    </div>
  );
}

export function KnowledgeBase() {
  const { loadKnowledgeItems, filters } = useKnowledgeStore();

  React.useEffect(() => {
    loadKnowledgeItems(filters);
  }, [filters, loadKnowledgeItems]);

  return (
    <div>
      <KBBrowserHeader />
      <KBGrid />
      {/* TODO: Add pagination controls */}
    </div>
  );
}

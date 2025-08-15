import React, { useState } from 'react'
import { Grid, List, ArrowUpDown, Sparkles, Search, Hash } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { GlassCard } from '@/components/ui/GlassCard'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { KnowledgeItemCard } from './KnowledgeItemCard'
import { ContentViewer } from './ContentViewer'
import type { KnowledgeItem, SearchResult } from '@/types'

interface SearchResultsProps {
  results: SearchResult[]
  isLoading: boolean
  totalResults: number
  searchQuery: string
  searchType: 'text' | 'vector' | 'hybrid'
  onLoadMore?: () => void
  hasMore?: boolean
}

export function SearchResults({
  results,
  isLoading,
  totalResults,
  searchQuery,
  searchType,
  onLoadMore,
  hasMore = false
}: SearchResultsProps) {
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid')
  const [selectedItem, setSelectedItem] = useState<KnowledgeItem | null>(null)
  
  if (isLoading && results.length === 0) {
    return (
      <GlassCard className="p-8 text-center">
        <LoadingSpinner size="lg" />
        <p className="mt-4 text-muted-foreground">Searching knowledge base...</p>
      </GlassCard>
    )
  }
  
  if (!isLoading && results.length === 0 && searchQuery) {
    return (
      <GlassCard className="p-8 text-center">
        <Search className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
        <h3 className="text-lg font-semibold mb-2">No results found</h3>
        <p className="text-muted-foreground mb-4">
          No content matches your search criteria. Try adjusting your filters or search terms.
        </p>
        <div className="space-y-2 text-sm text-muted-foreground">
          <p>• Try using different keywords</p>
          <p>• Remove some filters to broaden your search</p>
          <p>• Check for typos in your search query</p>
          {searchType === 'vector' && (
            <p>• Try switching to hybrid or text search</p>
          )}
        </div>
      </GlassCard>
    )
  }
  
  return (
    <div className="space-y-4">
      {/* Results Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">
              {totalResults.toLocaleString()} results
            </span>
            {searchQuery && (
              <span className="text-sm text-muted-foreground">
                for "{searchQuery}"
              </span>
            )}
          </div>
          
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="text-xs">
              {searchType === 'hybrid' && <Sparkles className="h-3 w-3 mr-1" />}
              {searchType === 'vector' && <Hash className="h-3 w-3 mr-1" />}
              {searchType === 'text' && <Search className="h-3 w-3 mr-1" />}
              {searchType === 'hybrid' ? 'Hybrid Search' : 
               searchType === 'vector' ? 'Semantic Search' : 'Text Search'}
            </Badge>
          </div>
        </div>
        
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setViewMode('grid')}
            className={viewMode === 'grid' ? 'bg-accent' : ''}
          >
            <Grid className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setViewMode('list')}
            className={viewMode === 'list' ? 'bg-accent' : ''}
          >
            <List className="h-4 w-4" />
          </Button>
        </div>
      </div>
      
      {/* Search Results */}
      <div className={
        viewMode === 'grid' 
          ? 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4'
          : 'space-y-4'
      }>
        {results.map((result, index) => (
          <SearchResultItem
            key={result.item.id}
            result={result}
            viewMode={viewMode}
            onClick={() => setSelectedItem(result.item)}
            rank={index + 1}
          />
        ))}
      </div>
      
      {/* Load More */}
      {hasMore && (
        <div className="text-center pt-4">
          <Button
            variant="outline"
            onClick={onLoadMore}
            disabled={isLoading}
          >
            {isLoading ? (
              <>
                <LoadingSpinner size="sm" className="mr-2" />
                Loading more...
              </>
            ) : (
              'Load More Results'
            )}
          </Button>
        </div>
      )}
      
      {/* Content Viewer Modal */}
      {selectedItem && (
        <ContentViewer
          item={selectedItem}
          isOpen={true}
          onClose={() => setSelectedItem(null)}
        />
      )}
    </div>
  )
}

interface SearchResultItemProps {
  result: SearchResult
  viewMode: 'grid' | 'list'
  onClick: () => void
  rank: number
}

function SearchResultItem({ result, viewMode, onClick, rank }: SearchResultItemProps) {
  const { item, score, highlights } = result
  
  if (viewMode === 'list') {
    return (
      <GlassCard 
        className="p-4 cursor-pointer hover:bg-accent/50 transition-colors"
        onClick={onClick}
      >
        <div className="flex gap-4">
          <div className="flex-shrink-0">
            <Badge variant="outline" className="text-xs">
              #{rank}
            </Badge>
          </div>
          
          <div className="flex-1 min-w-0">
            <div className="flex items-start justify-between mb-2">
              <h3 className="font-semibold truncate pr-2">
                {highlights?.title ? (
                  <span dangerouslySetInnerHTML={{ __html: highlights.title }} />
                ) : (
                  item.title
                )}
              </h3>
              
              <div className="flex items-center gap-2 flex-shrink-0">
                {score && (
                  <Badge variant="secondary" className="text-xs">
                    {Math.round(score * 100)}% match
                  </Badge>
                )}
                
                {item.thread_id && (
                  <Badge variant="outline" className="text-xs">
                    Thread ({item.thread_length || 1})
                  </Badge>
                )}
                
                {item.has_media && (
                  <Badge variant="outline" className="text-xs">
                    Media
                  </Badge>
                )}
              </div>
            </div>
            
            <p className="text-sm text-muted-foreground mb-2 line-clamp-2">
              {highlights?.content ? (
                <span dangerouslySetInnerHTML={{ __html: highlights.content }} />
              ) : (
                item.content.substring(0, 200) + (item.content.length > 200 ? '...' : '')
              )}
            </p>
            
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <span>@{item.author_username}</span>
              <span>•</span>
              <span>{new Date(item.created_at).toLocaleDateString()}</span>
              {item.total_engagement > 0 && (
                <>
                  <span>•</span>
                  <span>{item.total_engagement.toLocaleString()} engagement</span>
                </>
              )}
            </div>
            
            {item.categories && item.categories.length > 0 && (
              <div className="flex flex-wrap gap-1 mt-2">
                {item.categories.slice(0, 3).map(category => (
                  <Badge key={category} variant="secondary" className="text-xs">
                    {category}
                  </Badge>
                ))}
                {item.categories.length > 3 && (
                  <Badge variant="secondary" className="text-xs">
                    +{item.categories.length - 3} more
                  </Badge>
                )}
              </div>
            )}
          </div>
        </div>
      </GlassCard>
    )
  }
  
  return (
    <div className="relative">
      <Badge 
        variant="outline" 
        className="absolute top-2 left-2 z-10 text-xs"
      >
        #{rank}
      </Badge>
      
      <KnowledgeItemCard
        item={item}
        onClick={onClick}
        highlights={highlights}
        score={score}
      />
    </div>
  )
}
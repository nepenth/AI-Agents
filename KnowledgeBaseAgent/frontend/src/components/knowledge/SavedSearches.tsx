import React, { useState } from 'react'
import { Save, Search, Star, Trash2, Edit, Clock } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { GlassCard } from '@/components/ui/GlassCard'
import { Badge } from '@/components/ui/Badge'
import { Modal } from '@/components/ui/Modal'
import { useLocalStorage } from '@/hooks/useLocalStorage'
import type { SearchFilters } from './AdvancedSearch'

interface SavedSearch {
  id: string
  name: string
  filters: SearchFilters
  createdAt: string
  lastUsed?: string
  isFavorite: boolean
}

interface SavedSearchesProps {
  currentFilters: SearchFilters
  onLoadSearch: (filters: SearchFilters) => void
}

export function SavedSearches({ currentFilters, onLoadSearch }: SavedSearchesProps) {
  const [savedSearches, setSavedSearches] = useLocalStorage<SavedSearch[]>('saved-searches', [])
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [searchName, setSearchName] = useState('')
  const [editingSearch, setEditingSearch] = useState<SavedSearch | null>(null)
  
  const saveCurrentSearch = () => {
    if (!searchName.trim()) return
    
    const newSearch: SavedSearch = {
      id: Date.now().toString(),
      name: searchName.trim(),
      filters: currentFilters,
      createdAt: new Date().toISOString(),
      isFavorite: false
    }
    
    setSavedSearches(prev => [newSearch, ...prev])
    setSearchName('')
    setIsModalOpen(false)
  }
  
  const updateSearch = () => {
    if (!editingSearch || !searchName.trim()) return
    
    setSavedSearches(prev => prev.map(search => 
      search.id === editingSearch.id
        ? { ...search, name: searchName.trim(), filters: currentFilters }
        : search
    ))
    
    setSearchName('')
    setEditingSearch(null)
    setIsModalOpen(false)
  }
  
  const deleteSearch = (id: string) => {
    setSavedSearches(prev => prev.filter(search => search.id !== id))
  }
  
  const toggleFavorite = (id: string) => {
    setSavedSearches(prev => prev.map(search =>
      search.id === id ? { ...search, isFavorite: !search.isFavorite } : search
    ))
  }
  
  const loadSearch = (search: SavedSearch) => {
    setSavedSearches(prev => prev.map(s =>
      s.id === search.id ? { ...s, lastUsed: new Date().toISOString() } : s
    ))
    onLoadSearch(search.filters)
  }
  
  const openEditModal = (search: SavedSearch) => {
    setEditingSearch(search)
    setSearchName(search.name)
    setIsModalOpen(true)
  }
  
  const openSaveModal = () => {
    setEditingSearch(null)
    setSearchName('')
    setIsModalOpen(true)
  }
  
  const hasActiveFilters = () => {
    return currentFilters.query ||
           currentFilters.categories.length > 0 ||
           currentFilters.authors.length > 0 ||
           currentFilters.tags.length > 0 ||
           currentFilters.dateRange.start ||
           currentFilters.dateRange.end ||
           currentFilters.engagementRange.min ||
           currentFilters.engagementRange.max ||
           currentFilters.hasMedia !== null ||
           currentFilters.isThread !== null ||
           currentFilters.minThreadLength
  }
  
  const favoriteSearches = savedSearches.filter(s => s.isFavorite)
  const recentSearches = savedSearches
    .filter(s => !s.isFavorite)
    .sort((a, b) => {
      const aTime = a.lastUsed || a.createdAt
      const bTime = b.lastUsed || b.createdAt
      return new Date(bTime).getTime() - new Date(aTime).getTime()
    })
    .slice(0, 5)
  
  return (
    <div className="space-y-4">
      {/* Save Current Search */}
      {hasActiveFilters() && (
        <GlassCard className="p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Save className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm font-medium">Save current search</span>
            </div>
            <Button size="sm" onClick={openSaveModal}>
              Save Search
            </Button>
          </div>
        </GlassCard>
      )}
      
      {/* Favorite Searches */}
      {favoriteSearches.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-sm font-medium flex items-center gap-2">
            <Star className="h-4 w-4" />
            Favorite Searches
          </h3>
          <div className="space-y-2">
            {favoriteSearches.map(search => (
              <SavedSearchItem
                key={search.id}
                search={search}
                onLoad={() => loadSearch(search)}
                onEdit={() => openEditModal(search)}
                onDelete={() => deleteSearch(search.id)}
                onToggleFavorite={() => toggleFavorite(search.id)}
              />
            ))}
          </div>
        </div>
      )}
      
      {/* Recent Searches */}
      {recentSearches.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-sm font-medium flex items-center gap-2">
            <Clock className="h-4 w-4" />
            Recent Searches
          </h3>
          <div className="space-y-2">
            {recentSearches.map(search => (
              <SavedSearchItem
                key={search.id}
                search={search}
                onLoad={() => loadSearch(search)}
                onEdit={() => openEditModal(search)}
                onDelete={() => deleteSearch(search.id)}
                onToggleFavorite={() => toggleFavorite(search.id)}
              />
            ))}
          </div>
        </div>
      )}
      
      {/* Empty State */}
      {savedSearches.length === 0 && (
        <GlassCard className="p-8 text-center">
          <Search className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
          <h3 className="text-lg font-semibold mb-2">No saved searches</h3>
          <p className="text-muted-foreground mb-4">
            Save your frequently used searches for quick access
          </p>
        </GlassCard>
      )}
      
      {/* Save/Edit Modal */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => {
          setIsModalOpen(false)
          setEditingSearch(null)
          setSearchName('')
        }}
        title={editingSearch ? 'Edit Search' : 'Save Search'}
      >
        <div className="space-y-4">
          <div>
            <label className="text-sm font-medium mb-2 block">
              Search Name
            </label>
            <Input
              value={searchName}
              onChange={(e) => setSearchName(e.target.value)}
              placeholder="Enter a name for this search..."
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  editingSearch ? updateSearch() : saveCurrentSearch()
                }
              }}
            />
          </div>
          
          <div className="space-y-2">
            <label className="text-sm font-medium">Search Preview</label>
            <div className="text-xs text-muted-foreground space-y-1">
              {currentFilters.query && (
                <div>Query: "{currentFilters.query}"</div>
              )}
              {currentFilters.categories.length > 0 && (
                <div>Categories: {currentFilters.categories.join(', ')}</div>
              )}
              {currentFilters.authors.length > 0 && (
                <div>Authors: {currentFilters.authors.map(a => `@${a}`).join(', ')}</div>
              )}
              {currentFilters.searchType !== 'hybrid' && (
                <div>Search Type: {currentFilters.searchType}</div>
              )}
            </div>
          </div>
          
          <div className="flex gap-2 justify-end">
            <Button
              variant="outline"
              onClick={() => {
                setIsModalOpen(false)
                setEditingSearch(null)
                setSearchName('')
              }}
            >
              Cancel
            </Button>
            <Button
              onClick={editingSearch ? updateSearch : saveCurrentSearch}
              disabled={!searchName.trim()}
            >
              {editingSearch ? 'Update' : 'Save'} Search
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}

interface SavedSearchItemProps {
  search: SavedSearch
  onLoad: () => void
  onEdit: () => void
  onDelete: () => void
  onToggleFavorite: () => void
}

function SavedSearchItem({
  search,
  onLoad,
  onEdit,
  onDelete,
  onToggleFavorite
}: SavedSearchItemProps) {
  const getSearchSummary = (filters: SearchFilters) => {
    const parts = []
    
    if (filters.query) parts.push(`"${filters.query}"`)
    if (filters.categories.length > 0) parts.push(`${filters.categories.length} categories`)
    if (filters.authors.length > 0) parts.push(`${filters.authors.length} authors`)
    if (filters.hasMedia !== null) parts.push(filters.hasMedia ? 'with media' : 'text only')
    if (filters.isThread !== null) parts.push(filters.isThread ? 'threads' : 'single tweets')
    
    return parts.length > 0 ? parts.join(' • ') : 'All content'
  }
  
  return (
    <GlassCard className="p-3 hover:bg-accent/50 transition-colors">
      <div className="flex items-center justify-between">
        <div className="flex-1 min-w-0 cursor-pointer" onClick={onLoad}>
          <div className="flex items-center gap-2 mb-1">
            <h4 className="font-medium truncate">{search.name}</h4>
            {search.filters.searchType !== 'hybrid' && (
              <Badge variant="outline" className="text-xs">
                {search.filters.searchType}
              </Badge>
            )}
          </div>
          <p className="text-xs text-muted-foreground truncate">
            {getSearchSummary(search.filters)}
          </p>
          <p className="text-xs text-muted-foreground mt-1">
            {search.lastUsed ? (
              <>Last used {new Date(search.lastUsed).toLocaleDateString()}</>
            ) : (
              <>Created {new Date(search.createdAt).toLocaleDateString()}</>
            )}
          </p>
        </div>
        
        <div className="flex items-center gap-1 ml-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={onToggleFavorite}
            className="h-8 w-8 p-0"
          >
            <Star 
              className={`h-3 w-3 ${search.isFavorite ? 'fill-current text-yellow-500' : ''}`} 
            />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={onEdit}
            className="h-8 w-8 p-0"
          >
            <Edit className="h-3 w-3" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={onDelete}
            className="h-8 w-8 p-0 text-destructive hover:text-destructive"
          >
            <Trash2 className="h-3 w-3" />
          </Button>
        </div>
      </div>
    </GlassCard>
  )
}
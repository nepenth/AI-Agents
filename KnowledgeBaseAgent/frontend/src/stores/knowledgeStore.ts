import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import { KnowledgeItem, ContentItem, SearchResult, FilterState, PaginatedResponse } from '@/types';
import { knowledgeService, Category, SynthesisDocument } from '@/services/knowledgeService';

interface KnowledgeState {
  // Knowledge items
  knowledgeItems: KnowledgeItem[];
  knowledgeItemsLoading: boolean;
  knowledgeItemsTotal: number;
  currentKnowledgeItem: KnowledgeItem | null;
  
  // Content items
  contentItems: ContentItem[];
  contentItemsLoading: boolean;
  contentItemsTotal: number;
  currentContentItem: ContentItem | null;
  
  // Search
  searchResults: SearchResult[];
  searchLoading: boolean;
  searchQuery: string;
  searchTotal: number;
  
  // Categories and synthesis
  categories: Category[];
  synthesisDocuments: SynthesisDocument[];
  synthesisLoading: boolean;
  
  // Filters
  filters: FilterState;
  
  // UI state
  viewMode: 'grid' | 'list';
  selectedItems: string[];
  
  // Loading and error states
  loading: boolean;
  error: string | null;
  
  // Actions - Knowledge Items
  loadKnowledgeItems: (params?: any) => Promise<void>;
  loadKnowledgeItem: (id: string) => Promise<void>;
  createKnowledgeItem: (data: any) => Promise<KnowledgeItem>;
  updateKnowledgeItem: (id: string, data: any) => Promise<KnowledgeItem>;
  deleteKnowledgeItem: (id: string) => Promise<void>;
  
  // Actions - Content Items
  loadContentItems: (params?: any) => Promise<void>;
  loadContentItem: (id: string) => Promise<void>;
  deleteContentItem: (id: string) => Promise<void>;
  reprocessContentItem: (id: string) => Promise<void>;
  
  // Actions - Search
  searchKnowledge: (query: string, options?: any) => Promise<void>;
  clearSearch: () => void;
  
  // Actions - Categories and Synthesis
  loadCategories: () => Promise<void>;
  loadSynthesisDocuments: (params?: any) => Promise<void>;
  generateSynthesis: (params: any) => Promise<void>;
  
  // Actions - Filters and UI
  setFilters: (filters: Partial<FilterState>) => void;
  clearFilters: () => void;
  setViewMode: (mode: 'grid' | 'list') => void;
  toggleItemSelection: (id: string) => void;
  clearSelection: () => void;
  selectAll: () => void;
  
  // Actions - Bulk operations
  deleteSelectedItems: () => Promise<void>;
  exportKnowledge: (params?: any) => Promise<void>;
  
  // Utility
  clearError: () => void;
  reset: () => void;
}

export const useKnowledgeStore = create<KnowledgeState>()(
  devtools(
    (set, get) => ({
      // Initial state
      knowledgeItems: [],
      knowledgeItemsLoading: false,
      knowledgeItemsTotal: 0,
      currentKnowledgeItem: null,
      contentItems: [],
      contentItemsLoading: false,
      contentItemsTotal: 0,
      currentContentItem: null,
      searchResults: [],
      searchLoading: false,
      searchQuery: '',
      searchTotal: 0,
      categories: [],
      synthesisDocuments: [],
      synthesisLoading: false,
      filters: {},
      viewMode: 'grid',
      selectedItems: [],
      loading: false,
      error: null,

      // Knowledge Items Actions
      loadKnowledgeItems: async (params = {}) => {
        set({ knowledgeItemsLoading: true, error: null });
        try {
          const response = await knowledgeService.getKnowledgeItems(params);
          set({
            knowledgeItems: response.items,
            knowledgeItemsTotal: response.total,
            knowledgeItemsLoading: false,
          });
        } catch (error) {
          set({
            error: error instanceof Error ? error.message : 'Failed to load knowledge items',
            knowledgeItemsLoading: false,
          });
        }
      },

      loadKnowledgeItem: async (id: string) => {
        set({ loading: true, error: null });
        try {
          const item = await knowledgeService.getKnowledgeItem(id);
          set({
            currentKnowledgeItem: item,
            loading: false,
          });
        } catch (error) {
          set({
            error: error instanceof Error ? error.message : 'Failed to load knowledge item',
            loading: false,
          });
        }
      },

      createKnowledgeItem: async (data: any) => {
        set({ loading: true, error: null });
        try {
          const item = await knowledgeService.createKnowledgeItem(data);
          const { knowledgeItems } = get();
          set({
            knowledgeItems: [item, ...knowledgeItems],
            knowledgeItemsTotal: get().knowledgeItemsTotal + 1,
            loading: false,
          });
          return item;
        } catch (error) {
          set({
            error: error instanceof Error ? error.message : 'Failed to create knowledge item',
            loading: false,
          });
          throw error;
        }
      },

      updateKnowledgeItem: async (id: string, data: any) => {
        set({ loading: true, error: null });
        try {
          const updatedItem = await knowledgeService.updateKnowledgeItem(id, data);
          const { knowledgeItems } = get();
          set({
            knowledgeItems: knowledgeItems.map(item => 
              item.id === id ? updatedItem : item
            ),
            currentKnowledgeItem: get().currentKnowledgeItem?.id === id 
              ? updatedItem 
              : get().currentKnowledgeItem,
            loading: false,
          });
          return updatedItem;
        } catch (error) {
          set({
            error: error instanceof Error ? error.message : 'Failed to update knowledge item',
            loading: false,
          });
          throw error;
        }
      },

      deleteKnowledgeItem: async (id: string) => {
        set({ loading: true, error: null });
        try {
          await knowledgeService.deleteKnowledgeItem(id);
          const { knowledgeItems } = get();
          set({
            knowledgeItems: knowledgeItems.filter(item => item.id !== id),
            knowledgeItemsTotal: get().knowledgeItemsTotal - 1,
            currentKnowledgeItem: get().currentKnowledgeItem?.id === id 
              ? null 
              : get().currentKnowledgeItem,
            loading: false,
          });
        } catch (error) {
          set({
            error: error instanceof Error ? error.message : 'Failed to delete knowledge item',
            loading: false,
          });
          throw error;
        }
      },

      // Content Items Actions
      loadContentItems: async (params = {}) => {
        set({ contentItemsLoading: true, error: null });
        try {
          const response = await knowledgeService.getContentItems(params);
          set({
            contentItems: response.items,
            contentItemsTotal: response.total,
            contentItemsLoading: false,
          });
        } catch (error) {
          set({
            error: error instanceof Error ? error.message : 'Failed to load content items',
            contentItemsLoading: false,
          });
        }
      },

      loadContentItem: async (id: string) => {
        set({ loading: true, error: null });
        try {
          const item = await knowledgeService.getContentItem(id);
          set({
            currentContentItem: item,
            loading: false,
          });
        } catch (error) {
          set({
            error: error instanceof Error ? error.message : 'Failed to load content item',
            loading: false,
          });
        }
      },

      deleteContentItem: async (id: string) => {
        set({ loading: true, error: null });
        try {
          await knowledgeService.deleteContentItem(id);
          const { contentItems } = get();
          set({
            contentItems: contentItems.filter(item => item.id !== id),
            contentItemsTotal: get().contentItemsTotal - 1,
            loading: false,
          });
        } catch (error) {
          set({
            error: error instanceof Error ? error.message : 'Failed to delete content item',
            loading: false,
          });
          throw error;
        }
      },

      reprocessContentItem: async (id: string) => {
        set({ loading: true, error: null });
        try {
          await knowledgeService.reprocessContentItem(id);
          // Update the item status to processing
          const { contentItems } = get();
          set({
            contentItems: contentItems.map(item =>
              item.id === id ? { ...item, processing_state: 'processing' } : item
            ),
            loading: false,
          });
        } catch (error) {
          set({
            error: error instanceof Error ? error.message : 'Failed to reprocess content item',
            loading: false,
          });
          throw error;
        }
      },

      // Search Actions
      searchKnowledge: async (query: string, options = {}) => {
        set({ searchLoading: true, searchQuery: query, error: null });
        try {
          const response = await knowledgeService.searchKnowledge({
            query,
            ...options,
          });
          set({
            searchResults: response.results,
            searchTotal: response.total,
            searchLoading: false,
          });
        } catch (error) {
          set({
            error: error instanceof Error ? error.message : 'Search failed',
            searchLoading: false,
          });
        }
      },

      clearSearch: () => set({
        searchResults: [],
        searchQuery: '',
        searchTotal: 0,
      }),

      // Categories and Synthesis Actions
      loadCategories: async () => {
        try {
          const categories = await knowledgeService.getCategories();
          set({ categories });
        } catch (error) {
          console.error('Failed to load categories:', error);
        }
      },

      loadSynthesisDocuments: async (params = {}) => {
        set({ synthesisLoading: true });
        try {
          const documents = await knowledgeService.getSynthesisDocuments(params);
          set({
            synthesisDocuments: documents,
            synthesisLoading: false,
          });
        } catch (error) {
          set({
            error: error instanceof Error ? error.message : 'Failed to load synthesis documents',
            synthesisLoading: false,
          });
        }
      },

      generateSynthesis: async (params: any) => {
        set({ synthesisLoading: true, error: null });
        try {
          await knowledgeService.generateSynthesis(params);
          // Reload synthesis documents after generation
          await get().loadSynthesisDocuments();
        } catch (error) {
          set({
            error: error instanceof Error ? error.message : 'Failed to generate synthesis',
            synthesisLoading: false,
          });
          throw error;
        }
      },

      // Filter and UI Actions
      setFilters: (newFilters: Partial<FilterState>) => {
        const { filters } = get();
        set({ filters: { ...filters, ...newFilters } });
      },

      clearFilters: () => set({ filters: {} }),

      setViewMode: (mode: 'grid' | 'list') => set({ viewMode: mode }),

      toggleItemSelection: (id: string) => {
        const { selectedItems } = get();
        const isSelected = selectedItems.includes(id);
        set({
          selectedItems: isSelected
            ? selectedItems.filter(itemId => itemId !== id)
            : [...selectedItems, id],
        });
      },

      clearSelection: () => set({ selectedItems: [] }),

      selectAll: () => {
        const { knowledgeItems } = get();
        set({ selectedItems: knowledgeItems.map(item => item.id) });
      },

      // Bulk Operations
      deleteSelectedItems: async () => {
        const { selectedItems } = get();
        set({ loading: true, error: null });
        
        try {
          await Promise.all(
            selectedItems.map(id => knowledgeService.deleteKnowledgeItem(id))
          );
          
          const { knowledgeItems } = get();
          set({
            knowledgeItems: knowledgeItems.filter(item => !selectedItems.includes(item.id)),
            knowledgeItemsTotal: get().knowledgeItemsTotal - selectedItems.length,
            selectedItems: [],
            loading: false,
          });
        } catch (error) {
          set({
            error: error instanceof Error ? error.message : 'Failed to delete selected items',
            loading: false,
          });
          throw error;
        }
      },

      exportKnowledge: async (params = {}) => {
        try {
          const blob = await knowledgeService.exportKnowledge(params);
          const url = URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = `knowledge-export-${new Date().toISOString().split('T')[0]}.${params.format || 'json'}`;
          document.body.appendChild(a);
          a.click();
          document.body.removeChild(a);
          URL.revokeObjectURL(url);
        } catch (error) {
          set({
            error: error instanceof Error ? error.message : 'Export failed',
          });
          throw error;
        }
      },

      // Utility
      clearError: () => set({ error: null }),

      reset: () => set({
        knowledgeItems: [],
        knowledgeItemsTotal: 0,
        currentKnowledgeItem: null,
        contentItems: [],
        contentItemsTotal: 0,
        currentContentItem: null,
        searchResults: [],
        searchQuery: '',
        searchTotal: 0,
        selectedItems: [],
        filters: {},
        error: null,
        loading: false,
      }),
    }),
    {
      name: 'knowledge-store',
    }
  )
);
/**
 * Modern Synthesis Manager
 * 
 * Features:
 * - Browse synthesis documents with modern UI matching Knowledge Base layout
 * - Category-based organization
 * - Integration with unified database structure
 * - Document preview and full content viewing
 * - Export capabilities
 */

class ModernSynthesisManager extends BaseManager {
    constructor(options = {}) {
        super({
            enableLogging: true,
            autoInit: false,
            componentName: 'ModernSynthesisManager',
            ...options
        });

        // Synthesis state
        this.syntheses = new Map();
        this.filteredSyntheses = [];
        this.currentFilter = {
            category: 'all',
            search: '',
            sortBy: 'updated',
            sortOrder: 'desc'
        };

        this.selectedSynthesis = null;
        this.viewMode = 'grid'; // grid or list
    }

    async initializeElements() {
        this.elements.container = document.getElementById('main-content');
        if (!this.elements.container) {
            throw new Error('Main content container not found');
        }

        await this.createSynthesisInterface();

        // Cache interactive elements
        this.elements.searchInput = document.getElementById('synthesis-search');
        this.elements.categoryFilter = document.getElementById('category-filter');
        this.elements.sortSelect = document.getElementById('sort-select');
        this.elements.synthesisGrid = document.getElementById('synthesis-grid');
        this.elements.synthesisCount = document.getElementById('synthesis-count');
        this.elements.categoriesCount = document.getElementById('categories-count');
        this.elements.loadingState = document.getElementById('loading-state');
        this.elements.emptyState = document.getElementById('empty-state');
        this.elements.refreshBtn = document.getElementById('refresh-btn');
        this.elements.exportAllBtn = document.getElementById('export-all-btn');
    }

    async setupEventListeners() {
        this.eventService.setupStandardListeners(this, {
            buttons: [
                {
                    selector: this.elements.refreshBtn,
                    handler: this.handleRefresh,
                    debounce: 1000
                },
                {
                    selector: this.elements.exportAllBtn,
                    handler: this.handleExportAll,
                    debounce: 1000
                }
            ],
            inputs: [
                {
                    selector: this.elements.searchInput,
                    events: ['input'],
                    handler: this.handleSearch,
                    debounce: 300
                }
            ],
            customEvents: [
                {
                    event: 'change',
                    handler: (e) => {
                        if (e.target === this.elements.categoryFilter) {
                            this.handleCategoryFilter(e);
                        } else if (e.target === this.elements.sortSelect) {
                            this.handleSort(e);
                        }
                    }
                }
            ],
            delegated: [
                {
                    container: this.elements.synthesisGrid,
                    selector: '.item-action-btn',
                    event: 'click',
                    handler: this.handleItemAction
                },
                {
                    container: this.elements.synthesisGrid,
                    selector: '.kb-item',
                    event: 'click',
                    handler: this.handleItemClick
                }
            ]
        });
    }

    async loadInitialData() {
        try {
            this.showLoadingState();
            await this.loadSynthesisDocuments();
            this.applyFilters();
            this.updateStats();
        } catch (error) {
            this.logError('Failed to load initial synthesis data:', error);
            this.showEmptyState();
        }
    }

    async createSynthesisInterface() {
        this.elements.container.innerHTML = `
            <div class="modern-synthesis-container glass-panel-v3 animate-glass-fade-in">
                <!-- Header -->
                <header class="synthesis-header">
                    <div class="header-title">
                        <h1>
                            <i class="fas fa-layer-group"></i>
                            Synthesis Learning
                        </h1>
                        <p class="header-subtitle">AI-generated insights and summaries</p>
                    </div>
                    
                    <div class="header-actions">
                        <button id="refresh-btn" class="glass-button glass-button--small" title="Refresh">
                            <i class="fas fa-sync-alt"></i>
                        </button>
                        <button id="export-all-btn" class="glass-button glass-button--small" title="Export All">
                            <i class="fas fa-download"></i>
                        </button>
                    </div>
                </header>
                
                <!-- Controls -->
                <div class="synthesis-controls glass-panel-v3--secondary">
                    <div class="controls-left">
                        <div class="search-container">
                            <i class="fas fa-search"></i>
                            <input 
                                type="text" 
                                id="synthesis-search" 
                                placeholder="Search synthesis documents..."
                                class="glass-input"
                            >
                        </div>
                        
                        <select id="category-filter" class="glass-select">
                            <option value="all">All Categories</option>
                        </select>
                    </div>
                    
                    <div class="controls-right">
                        <select id="sort-select" class="glass-select">
                            <option value="updated-desc">Recently Updated</option>
                            <option value="updated-asc">Oldest First</option>
                            <option value="title-asc">Title A-Z</option>
                            <option value="title-desc">Title Z-A</option>
                            <option value="items-desc">Most Items</option>
                        </select>
                    </div>
                </div>
                
                <!-- Stats -->
                <div class="synthesis-stats">
                    <div class="stat-item">
                        <span class="stat-label">Total Documents</span>
                        <span id="synthesis-count" class="stat-value">--</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-label">Categories</span>
                        <span id="categories-count" class="stat-value">--</span>
                    </div>
                </div>
                
                <!-- Content -->
                <div class="synthesis-content">
                    <!-- Loading State -->
                    <div id="loading-state" class="loading-state">
                        <div class="loading-spinner"></div>
                        <span>Loading synthesis documents...</span>
                    </div>
                    
                    <!-- Empty State -->
                    <div id="empty-state" class="empty-state hidden">
                        <i class="fas fa-layer-group"></i>
                        <h3>No synthesis documents found</h3>
                        <p>Try adjusting your search or filter criteria</p>
                    </div>
                    
                    <!-- Synthesis Grid - Using same classes as Knowledge Base for consistency -->
                    <div id="synthesis-grid" class="items-grid grid-view">
                        <!-- Synthesis documents will be populated here -->
                    </div>
                </div>
            </div>
        `;
    }

    async loadSynthesisDocuments() {
        try {
            const response = await this.apiCall('/syntheses', {
                errorMessage: 'Failed to load synthesis documents',
                cache: true,
                cacheTTL: 60000 // 1 minute cache
            });

            this.syntheses.clear();

            // Handle different response formats
            let syntheses = [];
            if (Array.isArray(response)) {
                syntheses = response;
            } else if (response && response.synthesis_documents && Array.isArray(response.synthesis_documents)) {
                syntheses = response.synthesis_documents;
            } else if (response && response.data && Array.isArray(response.data)) {
                syntheses = response.data;
            }

            syntheses.forEach(synthesis => {
                this.syntheses.set(synthesis.id, synthesis);
            });

            this.log(`Loaded ${this.syntheses.size} synthesis documents`);
            this.updateCategoryFilter();

        } catch (error) {
            this.logError('Failed to load synthesis documents:', error);
            throw error;
        }
    }

    updateCategoryFilter() {
        if (!this.elements.categoryFilter) return;

        const categories = new Set();
        this.syntheses.forEach(synthesis => {
            if (synthesis.main_category) {
                categories.add(synthesis.main_category);
            }
        });

        // Clear existing options except "All Categories"
        this.elements.categoryFilter.innerHTML = '<option value="all">All Categories</option>';

        // Add category options
        Array.from(categories).sort().forEach(category => {
            const option = document.createElement('option');
            option.value = category;
            option.textContent = category;
            this.elements.categoryFilter.appendChild(option);
        });
    }

    applyFilters() {
        let filtered = Array.from(this.syntheses.values());

        // Apply category filter
        if (this.currentFilter.category !== 'all') {
            filtered = filtered.filter(synthesis =>
                synthesis.main_category === this.currentFilter.category
            );
        }

        // Apply search filter
        if (this.currentFilter.search) {
            const searchTerm = this.currentFilter.search.toLowerCase();
            filtered = filtered.filter(synthesis => {
                const title = (synthesis.synthesis_short_name || synthesis.synthesis_title || '').toLowerCase();
                const content = (synthesis.synthesis_content || '').toLowerCase();
                const category = (synthesis.main_category || '').toLowerCase();
                const subCategory = (synthesis.sub_category || '').toLowerCase();

                return title.includes(searchTerm) ||
                    content.includes(searchTerm) ||
                    category.includes(searchTerm) ||
                    subCategory.includes(searchTerm);
            });
        }

        // Apply sorting
        filtered.sort((a, b) => {
            const [sortBy, sortOrder] = this.currentFilter.sortBy.split('-');
            let comparison = 0;

            switch (sortBy) {
                case 'updated':
                    const dateA = new Date(a.last_updated || a.created_at || 0);
                    const dateB = new Date(b.last_updated || b.created_at || 0);
                    comparison = dateA - dateB;
                    break;
                case 'title':
                    const titleA = (a.synthesis_short_name || a.synthesis_title || '').toLowerCase();
                    const titleB = (b.synthesis_short_name || b.synthesis_title || '').toLowerCase();
                    comparison = titleA.localeCompare(titleB);
                    break;
                case 'items':
                    comparison = (a.item_count || 0) - (b.item_count || 0);
                    break;
            }

            return sortOrder === 'desc' ? -comparison : comparison;
        });

        this.filteredSyntheses = filtered;
        this.renderSyntheses();
        this.updateStats();
    }

    renderSyntheses() {
        if (!this.elements.synthesisGrid) return;

        if (this.filteredSyntheses.length === 0) {
            this.showEmptyState();
            return;
        }

        this.hideLoadingState();
        this.hideEmptyState();

        const synthesisHTML = this.filteredSyntheses.map(synthesis => this.createSynthesisHTML(synthesis)).join('');
        this.elements.synthesisGrid.innerHTML = synthesisHTML;
        this.elements.synthesisGrid.className = `items-grid ${this.viewMode}-view`;
    }

    createSynthesisHTML(synthesis) {
        const title = synthesis.synthesis_short_name || synthesis.synthesis_title || 'Untitled Synthesis';
        const category = synthesis.main_category || 'Uncategorized';
        const subCategory = synthesis.sub_category || '';
        const itemCount = synthesis.item_count || 0;
        const lastUpdated = this.formatDate(synthesis.last_updated || synthesis.created_at);
        const preview = this.createPreview(synthesis.synthesis_content || '');

        // Use same CSS classes as Knowledge Base items for consistency
        return `
            <div class="kb-item glass-panel-v3--interactive" data-item-id="${synthesis.id}" data-item-type="synthesis">
                <div class="item-header">
                    <div class="item-type">
                        <i class="fas fa-layer-group"></i>
                        <span>Synthesis Document</span>
                    </div>
                    <div class="item-actions">
                        <button class="item-action-btn" data-action="view" title="View">
                            <i class="fas fa-eye"></i>
                        </button>
                        <button class="item-action-btn" data-action="export" title="Export">
                            <i class="fas fa-download"></i>
                        </button>
                    </div>
                </div>
                
                <div class="item-content">
                    <h3 class="item-title">${title}</h3>
                    
                    <div class="item-categories">
                        <span class="category-badge main-category">${category}</span>
                        ${subCategory ? `<span class="category-badge sub-category">${subCategory}</span>` : ''}
                    </div>
                    
                    <div class="item-preview">${preview}</div>
                </div>
                
                <div class="item-footer">
                    <div class="item-metadata">
                        <span class="item-count">${itemCount} source items</span>
                        <span class="last-updated">Updated ${lastUpdated}</span>
                    </div>
                </div>
            </div>
        `;
    }

    createPreview(content) {
        if (!content) return 'No content available';

        // Remove markdown formatting and truncate
        const plainText = content
            .replace(/#{1,6}\s+/g, '') // Remove headers
            .replace(/\*\*(.*?)\*\*/g, '$1') // Remove bold
            .replace(/\*(.*?)\*/g, '$1') // Remove italic
            .replace(/`(.*?)`/g, '$1') // Remove inline code
            .replace(/\n+/g, ' ') // Replace newlines with spaces
            .trim();

        return plainText.length > 200 ? plainText.substring(0, 200) + '...' : plainText;
    }

    formatDate(dateString) {
        if (!dateString) return 'Unknown';

        try {
            const date = new Date(dateString);
            const now = new Date();
            const diffTime = Math.abs(now - date);
            const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

            if (diffDays === 1) return 'Yesterday';
            if (diffDays < 7) return `${diffDays} days ago`;
            if (diffDays < 30) return `${Math.ceil(diffDays / 7)} weeks ago`;
            if (diffDays < 365) return `${Math.ceil(diffDays / 30)} months ago`;

            return date.toLocaleDateString();
        } catch (error) {
            return 'Unknown';
        }
    }

    updateStats() {
        if (this.elements.synthesisCount) {
            this.elements.synthesisCount.textContent = this.filteredSyntheses.length;
        }

        if (this.elements.categoriesCount) {
            const categories = new Set();
            this.filteredSyntheses.forEach(synthesis => {
                if (synthesis.main_category) {
                    categories.add(synthesis.main_category);
                }
            });
            this.elements.categoriesCount.textContent = categories.size;
        }
    }

    showLoadingState() {
        if (this.elements.loadingState) {
            this.elements.loadingState.classList.remove('hidden');
        }
        if (this.elements.synthesisGrid) {
            this.elements.synthesisGrid.style.display = 'none';
        }
    }

    hideLoadingState() {
        if (this.elements.loadingState) {
            this.elements.loadingState.classList.add('hidden');
        }
        if (this.elements.synthesisGrid) {
            this.elements.synthesisGrid.style.display = 'grid';
        }
    }

    showEmptyState() {
        if (this.elements.emptyState) {
            this.elements.emptyState.classList.remove('hidden');
        }
        if (this.elements.synthesisGrid) {
            this.elements.synthesisGrid.style.display = 'none';
        }
    }

    hideEmptyState() {
        if (this.elements.emptyState) {
            this.elements.emptyState.classList.add('hidden');
        }
    }

    // Event Handlers
    handleRefresh = async () => {
        try {
            this.showLoadingState();
            await this.loadSynthesisDocuments();
            this.applyFilters();
            this.log('Synthesis documents refreshed');
        } catch (error) {
            this.logError('Failed to refresh synthesis documents:', error);
        }
    }

    handleExportAll = async () => {
        try {
            this.log('Exporting all synthesis documents...');
            // TODO: Implement export functionality
        } catch (error) {
            this.logError('Failed to export synthesis documents:', error);
        }
    }

    handleSearch = (e) => {
        this.currentFilter.search = e.target.value;
        this.applyFilters();
    }

    handleCategoryFilter = (e) => {
        this.currentFilter.category = e.target.value;
        this.applyFilters();
    }

    handleSort = (e) => {
        this.currentFilter.sortBy = e.target.value;
        this.applyFilters();
    }

    handleItemAction = (e) => {
        e.stopPropagation();
        const action = e.target.closest('.item-action-btn').dataset.action;
        const itemElement = e.target.closest('.kb-item');
        const itemId = itemElement.dataset.itemId;
        const synthesis = this.syntheses.get(parseInt(itemId));

        if (!synthesis) return;

        switch (action) {
            case 'view':
                this.viewSynthesis(synthesis);
                break;
            case 'export':
                this.exportSynthesis(synthesis);
                break;
        }
    }

    handleItemClick = (e) => {
        // Don't trigger if clicking on action buttons
        if (e.target.closest('.item-action-btn')) return;

        const itemId = e.currentTarget.dataset.itemId;
        const synthesis = this.syntheses.get(parseInt(itemId));

        if (synthesis) {
            this.viewSynthesis(synthesis);
        }
    }

    viewSynthesis(synthesis) {
        this.log(`Viewing synthesis: ${synthesis.synthesis_title}`);
        // TODO: Implement synthesis viewing modal or navigation
    }

    exportSynthesis(synthesis) {
        this.log(`Exporting synthesis: ${synthesis.synthesis_title}`);
        // TODO: Implement synthesis export functionality
    }

    cleanup() {
        this.cleanupService.cleanup(this);
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ModernSynthesisManager;
}
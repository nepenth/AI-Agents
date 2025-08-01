/**
 * Modern Knowledge Base Manager
 * 
 * Features:
 * - Browse knowledge base items with modern UI
 * - Category-based filtering and search
 * - Integration with unified database structure
 * - Responsive grid layout with glass morphism design
 * - Quick preview and full content viewing
 * - Export and sharing capabilities
 */

class ModernKnowledgeBaseManager extends BaseManager {
    constructor(options = {}) {
        super({
            enableLogging: true,
            autoInit: false,
            componentName: 'ModernKnowledgeBaseManager',
            ...options
        });
        
        // Knowledge base state
        this.items = new Map();
        this.categories = new Map();
        this.filteredItems = [];
        this.currentFilter = {
            category: 'all',
            search: '',
            sortBy: 'updated-desc'
        };
        
        // UI state
        this.viewMode = 'grid'; // 'grid' or 'list'
        this.selectedItem = null;
    }
    
    async initializeElements() {
        this.elements.container = document.getElementById('main-content');
        if (!this.elements.container) {
            throw new Error('Main content container not found');
        }
        
        await this.createKnowledgeBaseInterface();
        
        // Cache interactive elements
        this.elements.searchInput = document.getElementById('kb-search');
        this.elements.categoryFilter = document.getElementById('category-filter');
        this.elements.sortSelect = document.getElementById('sort-select');
        this.elements.viewToggle = document.getElementById('view-toggle');
        this.elements.itemsGrid = document.getElementById('items-grid');
        this.elements.itemsCount = document.getElementById('items-count');
        this.elements.loadingState = document.getElementById('loading-state');
        this.elements.emptyState = document.getElementById('empty-state');
        this.elements.refreshBtn = document.getElementById('refresh-btn');
        this.elements.exportBtn = document.getElementById('export-btn');
    }
    
    async setupEventListeners() {
        this.eventService.setupStandardListeners(this, {
            inputs: [
                {
                    selector: this.elements.searchInput,
                    events: ['input'],
                    handler: this.handleSearch,
                    debounce: 300
                },
                {
                    selector: this.elements.categoryFilter,
                    events: ['change'],
                    handler: this.handleCategoryFilter
                },
                {
                    selector: this.elements.sortSelect,
                    events: ['change'],
                    handler: this.handleSortChange
                }
            ],
            
            buttons: [
                {
                    selector: this.elements.viewToggle,
                    handler: this.handleViewToggle
                },
                {
                    selector: this.elements.refreshBtn,
                    handler: this.handleRefresh,
                    debounce: 1000
                },
                {
                    selector: this.elements.exportBtn,
                    handler: this.handleExportAll
                }
            ],
            
            delegated: [
                {
                    container: this.elements.itemsGrid,
                    selector: '.kb-item',
                    event: 'click',
                    handler: this.handleItemClick
                },
                {
                    container: this.elements.itemsGrid,
                    selector: '.item-action-btn',
                    event: 'click',
                    handler: this.handleItemAction
                }
            ],
            
            keyboard: [
                {
                    key: 'Escape',
                    handler: this.handleEscape
                }
            ]
        });
    }
    
    async loadInitialData() {
        try {
            this.showLoadingState();
            this.log('Starting to load initial data...');
            
            // Load knowledge base items
            await this.loadKnowledgeBaseItems();
            this.log(`Loaded ${this.items.size} items`);
            
            // Load categories for filtering
            this.extractCategories();
            this.log(`Extracted ${this.categories.size} categories`);
            
            // Apply initial filtering and display
            this.applyFilters();
            this.updateCategoryFilter();
            this.log('Applied filters and updated UI');
            
            this.setState({ 
                initialized: true,
                loading: false 
            });
            
            this.log('Knowledge Base Manager initialization completed');
            
        } catch (error) {
            this.setError(error, 'loading knowledge base data');
            this.showEmptyState('Failed to load knowledge base items');
        }
    }
    
    async createKnowledgeBaseInterface() {
        this.elements.container.innerHTML = `
            <div class="modern-kb-container glass-panel-v3 animate-glass-fade-in">
                <!-- Header -->
                <header class="kb-header">
                    <div class="header-title">
                        <h1>
                            <i class="fas fa-book-open"></i>
                            Knowledge Base
                        </h1>
                        <p class="header-subtitle">Explore your curated knowledge collection</p>
                    </div>
                    
                    <div class="header-actions">
                        <button id="refresh-btn" class="glass-button glass-button--small" title="Refresh">
                            <i class="fas fa-sync-alt"></i>
                        </button>
                        <button id="export-btn" class="glass-button glass-button--small" title="Export All">
                            <i class="fas fa-download"></i>
                        </button>
                    </div>
                </header>
                
                <!-- Controls -->
                <div class="kb-controls glass-panel-v3--secondary">
                    <div class="controls-left">
                        <div class="search-container">
                            <i class="fas fa-search"></i>
                            <input 
                                type="text" 
                                id="kb-search" 
                                placeholder="Search knowledge base..."
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
                            <option value="category-asc">Category A-Z</option>
                        </select>
                        
                        <div class="view-toggle-group">
                            <button id="view-toggle" class="glass-button glass-button--small" title="Toggle View">
                                <i class="fas fa-th"></i>
                            </button>
                        </div>
                    </div>
                </div>
                
                <!-- Stats -->
                <div class="kb-stats">
                    <div class="stat-item">
                        <span class="stat-label">Total Items</span>
                        <span id="items-count" class="stat-value">--</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-label">Categories</span>
                        <span id="categories-count" class="stat-value">--</span>
                    </div>
                </div>
                
                <!-- Content -->
                <div class="kb-content">
                    <!-- Loading State -->
                    <div id="loading-state" class="loading-state">
                        <div class="loading-spinner"></div>
                        <span>Loading knowledge base...</span>
                    </div>
                    
                    <!-- Empty State -->
                    <div id="empty-state" class="empty-state hidden">
                        <i class="fas fa-book-open"></i>
                        <h3>No items found</h3>
                        <p>Try adjusting your search or filter criteria</p>
                    </div>
                    
                    <!-- Items Grid -->
                    <div id="items-grid" class="items-grid">
                        <!-- Items will be populated here -->
                    </div>
                </div>
            </div>
        `;
    }
    
    async loadKnowledgeBaseItems() {
        try {
            this.items.clear();
            
            // Load knowledge base items from the correct API endpoint
            const response = await this.apiCall('/items', {
                errorMessage: 'Failed to load knowledge base items',
                cache: false,
                showLoading: false
            });
            
            if (Array.isArray(response)) {
                response.forEach(item => {
                    this.items.set(item.id, item);
                });
                this.log(`Loaded ${response.length} knowledge base items`);
            } else {
                this.logWarn('API returned non-array response:', response);
            }
            
            this.log(`Total items loaded: ${this.items.size}`);
            
        } catch (error) {
            this.logError('Failed to load knowledge base items:', error);
            throw error;
        }
    }
    
    extractCategories() {
        this.categories.clear();
        
        this.items.forEach(item => {
            const category = item.main_category || 'Uncategorized';
            if (!this.categories.has(category)) {
                this.categories.set(category, {
                    name: category,
                    count: 0,
                    items: []
                });
            }
            
            const categoryData = this.categories.get(category);
            categoryData.count++;
            categoryData.items.push(item);
        });
        
        this.log(`Extracted ${this.categories.size} categories`);
    }
    
    updateCategoryFilter() {
        if (!this.elements.categoryFilter) return;
        
        const options = ['<option value="all">All Categories</option>'];
        
        Array.from(this.categories.entries())
            .sort(([a], [b]) => a.localeCompare(b))
            .forEach(([categoryName, categoryData]) => {
                options.push(`
                    <option value="${categoryName}">
                        ${categoryName} (${categoryData.count})
                    </option>
                `);
            });
        
        this.elements.categoryFilter.innerHTML = options.join('');
    }
    
    applyFilters() {
        let filtered = Array.from(this.items.values());
        
        // Apply category filter
        if (this.currentFilter.category !== 'all') {
            filtered = filtered.filter(item => 
                (item.main_category || 'Uncategorized') === this.currentFilter.category
            );
        }
        
        // Apply search filter
        if (this.currentFilter.search) {
            const searchTerm = this.currentFilter.search.toLowerCase();
            filtered = filtered.filter(item => 
                (item.title || '').toLowerCase().includes(searchTerm) ||
                (item.content || '').toLowerCase().includes(searchTerm) ||
                (item.main_category || '').toLowerCase().includes(searchTerm) ||
                (item.sub_category || '').toLowerCase().includes(searchTerm)
            );
        }
        
        // Apply sorting
        const [sortBy, sortOrder] = this.currentFilter.sortBy.split('-');
        filtered.sort((a, b) => {
            let aVal, bVal;
            
            switch (sortBy) {
                case 'title':
                    aVal = (a.title || '').toLowerCase();
                    bVal = (b.title || '').toLowerCase();
                    break;
                case 'category':
                    aVal = (a.main_category || 'Uncategorized').toLowerCase();
                    bVal = (b.main_category || 'Uncategorized').toLowerCase();
                    break;
                case 'updated':
                default:
                    aVal = new Date(a.last_updated || a.created_at || 0);
                    bVal = new Date(b.last_updated || b.created_at || 0);
                    break;
            }
            
            const comparison = aVal < bVal ? -1 : aVal > bVal ? 1 : 0;
            return sortOrder === 'desc' ? -comparison : comparison;
        });
        
        this.filteredItems = filtered;
        this.renderItems();
        this.updateStats();
    }
    
    renderItems() {
        if (!this.elements.itemsGrid) return;
        
        if (this.filteredItems.length === 0) {
            this.showEmptyState();
            return;
        }
        
        this.hideLoadingState();
        this.hideEmptyState();
        
        const itemsHTML = this.filteredItems.map(item => this.createItemHTML(item)).join('');
        this.elements.itemsGrid.innerHTML = itemsHTML;
        this.elements.itemsGrid.className = `items-grid ${this.viewMode}-view`;
    }
    
    createItemHTML(item) {
        const title = item.title || 'Untitled';
        const category = item.main_category || 'Uncategorized';
        const subCategory = item.sub_category || '';
        const lastUpdated = this.formatDate(item.last_updated || item.created_at);
        const preview = this.createPreview(item.content || '');
        
        return `
            <div class="kb-item glass-panel-v3--interactive" data-item-id="${item.id}" data-item-type="kb_item">
                <div class="item-header">
                    <div class="item-type">
                        <i class="fas fa-file-alt"></i>
                        <span class="item-type-label">Knowledge Base Item</span>
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
                        <span class="last-updated">Updated ${lastUpdated}</span>
                        ${item.source_url ? `<span class="source-link"><i class="fas fa-external-link-alt"></i> Source</span>` : ''}
                    </div>
                </div>
            </div>
        `;
    }
    
    createPreview(content) {
        if (!content) return 'No content available';
        
        // Strip markdown and HTML, then truncate
        const plainText = content
            .replace(/[#*_`~\[\]()]/g, '') // Remove markdown
            .replace(/<[^>]*>/g, '') // Remove HTML
            .replace(/\s+/g, ' ') // Normalize whitespace
            .trim();
        
        return plainText.length > 200 
            ? plainText.substring(0, 200) + '...'
            : plainText;
    }
    
    formatDate(dateString) {
        if (!dateString) return 'Unknown';
        
        const date = new Date(dateString);
        const now = new Date();
        const diffMs = now - date;
        const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
        
        if (diffDays === 0) {
            return 'Today';
        } else if (diffDays === 1) {
            return 'Yesterday';
        } else if (diffDays < 7) {
            return `${diffDays} days ago`;
        } else if (diffDays < 30) {
            return `${Math.floor(diffDays / 7)} weeks ago`;
        } else {
            return date.toLocaleDateString();
        }
    }
    
    updateStats() {
        if (this.elements.itemsCount) {
            this.elements.itemsCount.textContent = this.filteredItems.length.toString();
        }
        
        const categoriesCountEl = document.getElementById('categories-count');
        if (categoriesCountEl) {
            categoriesCountEl.textContent = this.categories.size.toString();
        }
    }
    
    showLoadingState() {
        if (this.elements.loadingState) {
            this.elements.loadingState.classList.remove('hidden');
        }
        if (this.elements.itemsGrid) {
            this.elements.itemsGrid.classList.add('hidden');
        }
        if (this.elements.emptyState) {
            this.elements.emptyState.classList.add('hidden');
        }
    }
    
    hideLoadingState() {
        if (this.elements.loadingState) {
            this.elements.loadingState.classList.add('hidden');
        }
        if (this.elements.itemsGrid) {
            this.elements.itemsGrid.classList.remove('hidden');
        }
    }
    
    showEmptyState(message = null) {
        if (this.elements.emptyState) {
            this.elements.emptyState.classList.remove('hidden');
            if (message) {
                const messageEl = this.elements.emptyState.querySelector('p');
                if (messageEl) messageEl.textContent = message;
            }
        }
        if (this.elements.itemsGrid) {
            this.elements.itemsGrid.classList.add('hidden');
        }
        if (this.elements.loadingState) {
            this.elements.loadingState.classList.add('hidden');
        }
    }
    
    hideEmptyState() {
        if (this.elements.emptyState) {
            this.elements.emptyState.classList.add('hidden');
        }
    }    
   
 // Event Handlers
    handleSearch = (e) => {
        this.currentFilter.search = e.target.value.trim();
        this.applyFilters();
    }
    
    handleCategoryFilter = (e) => {
        this.currentFilter.category = e.target.value;
        this.applyFilters();
    }
    
    handleSortChange = (e) => {
        this.currentFilter.sortBy = e.target.value;
        this.applyFilters();
    }
    
    handleViewToggle = () => {
        this.viewMode = this.viewMode === 'grid' ? 'list' : 'grid';
        
        // Update toggle button icon
        const icon = this.elements.viewToggle.querySelector('i');
        if (icon) {
            icon.className = this.viewMode === 'grid' ? 'fas fa-th' : 'fas fa-list';
        }
        
        // Update grid class
        if (this.elements.itemsGrid) {
            this.elements.itemsGrid.className = `items-grid ${this.viewMode}-view`;
        }
        
        this.log(`View mode changed to: ${this.viewMode}`);
    }
    
    handleRefresh = async () => {
        try {
            this.log('Refreshing knowledge base data...');
            await this.loadInitialData();
        } catch (error) {
            this.setError(error, 'refreshing knowledge base data');
        }
    }
    
    handleExportAll = () => {
        try {
            const allItems = Array.from(this.items.values());
            const exportData = this.formatItemsForExport(allItems);
            const filename = `knowledge_base_export_${new Date().toISOString().split('T')[0]}.md`;
            
            this.downloadFile(exportData, filename, 'text/markdown');
            this.log(`Exported ${allItems.length} items to ${filename}`);
            
        } catch (error) {
            this.setError(error, 'exporting knowledge base items');
        }
    }
    
    handleItemClick = (e) => {
        const itemElement = e.target.closest('.kb-item');
        if (!itemElement) return;
        
        const itemId = itemElement.dataset.itemId;
        const itemType = itemElement.dataset.itemType;
        
        this.log(`Item clicked: ID=${itemId}, Type=${itemType}`);
        this.viewItem(itemId, itemType);
    }
    
    handleItemAction = (e) => {
        e.stopPropagation();
        
        const actionBtn = e.target.closest('.item-action-btn');
        if (!actionBtn) return;
        
        const action = actionBtn.dataset.action;
        const itemElement = e.target.closest('.kb-item');
        if (!itemElement) return;
        
        const itemId = itemElement.dataset.itemId;
        const itemType = itemElement.dataset.itemType;
        
        this.log(`Item action: ${action} on ID=${itemId}, Type=${itemType}`);
        
        switch (action) {
            case 'view':
                this.viewItem(itemId, itemType);
                break;
            case 'export':
                this.exportItem(itemId, itemType);
                break;
        }
    }
    
    handleEscape = () => {
        this.closeModal();
    }
    
    // Item Operations
    viewItem(itemId, itemType) {
        this.log(`Opening item: ID=${itemId}, Type=${itemType}`);
        this.openItemModal(itemId, itemType);
    }
    
    openItemModal(itemId, itemType) {
        const item = this.items.get(parseInt(itemId));
        if (!item) {
            this.logError(`Item with ID ${itemId} not found`);
            return;
        }
        
        this.selectedItem = item;
        this.createAndShowModal(item);
    }
    
    createAndShowModal(item) {
        // Remove existing modal if present
        const existingModal = document.getElementById('kb-item-modal');
        if (existingModal) {
            existingModal.remove();
        }
        
        const title = item.title || 'Untitled';
        const category = item.main_category || 'Uncategorized';
        const subCategory = item.sub_category || '';
        const content = item.content || 'No content available';
        const lastUpdated = new Date(item.last_updated || item.created_at).toLocaleString();
        const sourceUrl = item.source_url;
        const mediaFiles = item.kb_media_paths || [];
        
        // Create modal HTML
        const modalHTML = `
            <div id="kb-item-modal" class="modal-overlay">
                <div class="modal-container glass-panel-v3">
                    <div class="modal-header">
                        <div class="modal-title-section">
                            <h2 class="modal-title">${title}</h2>
                            <div class="modal-categories">
                                <span class="category-badge main-category">${category}</span>
                                ${subCategory ? `<span class="category-badge sub-category">${subCategory}</span>` : ''}
                            </div>
                        </div>
                        <div class="modal-actions">
                            <button id="modal-export-btn" class="glass-button glass-button--small" title="Export">
                                <i class="fas fa-download"></i>
                            </button>
                            ${sourceUrl ? `<button id="modal-source-btn" class="glass-button glass-button--small" title="View Source">
                                <i class="fas fa-external-link-alt"></i>
                            </button>` : ''}
                            <button id="modal-close-btn" class="glass-button glass-button--small" title="Close">
                                <i class="fas fa-times"></i>
                            </button>
                        </div>
                    </div>
                    
                    <div class="modal-metadata">
                        <div class="metadata-item">
                            <i class="fas fa-clock"></i>
                            <span>Last Updated: ${lastUpdated}</span>
                        </div>
                        ${item.tweet_id ? `<div class="metadata-item">
                            <i class="fas fa-hashtag"></i>
                            <span>Tweet ID: ${item.tweet_id}</span>
                        </div>` : ''}
                    </div>
                    
                    ${mediaFiles.length > 0 ? `
                    <div class="modal-media-section">
                        <h3><i class="fas fa-images"></i> Media Files</h3>
                        <div class="media-grid">
                            ${mediaFiles.map(mediaPath => `
                                <div class="media-item">
                                    <img src="/media/${mediaPath}" alt="Knowledge base media" 
                                         onclick="this.classList.toggle('expanded')" 
                                         title="Click to expand">
                                </div>
                            `).join('')}
                        </div>
                    </div>
                    ` : ''}
                    
                    <div class="modal-content-section">
                        <h3><i class="fas fa-file-text"></i> Content</h3>
                        <div class="modal-content">
                            ${this.formatContentForDisplay(content)}
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // Add modal to DOM
        document.body.insertAdjacentHTML('beforeend', modalHTML);
        
        // Setup modal event listeners
        this.setupModalEventListeners(item);
        
        // Show modal with animation
        requestAnimationFrame(() => {
            const modal = document.getElementById('kb-item-modal');
            if (modal) {
                modal.classList.add('show');
            }
        });
    }
    
    setupModalEventListeners(item) {
        const modal = document.getElementById('kb-item-modal');
        if (!modal) return;
        
        // Use EventListenerService for modal events
        this.eventService.setupStandardListeners(this, {
            buttons: [
                {
                    selector: '#modal-close-btn',
                    handler: this.closeModal
                },
                {
                    selector: '#modal-export-btn',
                    handler: () => this.exportItem(item.id, 'kb_item')
                },
                {
                    selector: '#modal-source-btn',
                    handler: () => {
                        if (item.source_url) {
                            window.open(item.source_url, '_blank');
                        }
                    },
                    condition: () => !!item.source_url
                }
            ],
            customEvents: [
                {
                    target: modal,
                    event: 'click',
                    handler: (e) => {
                        if (e.target === modal) {
                            this.closeModal();
                        }
                    }
                }
            ]
        });
    }
    
    closeModal = () => {
        const modal = document.getElementById('kb-item-modal');
        if (modal) {
            modal.classList.add('closing');
            setTimeout(() => {
                modal.remove();
            }, 300); // Match CSS transition duration
        }
        this.selectedItem = null;
    }
    
    formatContentForDisplay(content) {
        if (!content) return '<p class="no-content">No content available</p>';
        
        // Convert markdown-like formatting to HTML
        let formatted = content
            // Headers
            .replace(/^### (.*$)/gm, '<h3>$1</h3>')
            .replace(/^## (.*$)/gm, '<h2>$1</h2>')
            .replace(/^# (.*$)/gm, '<h1>$1</h1>')
            // Bold and italic
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            // Code blocks
            .replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>')
            .replace(/`(.*?)`/g, '<code>$1</code>')
            // Links
            .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>')
            // Line breaks
            .replace(/\n\n/g, '</p><p>')
            .replace(/\n/g, '<br>');
        
        // Wrap in paragraphs
        formatted = '<p>' + formatted + '</p>';
        
        // Clean up empty paragraphs
        formatted = formatted.replace(/<p><\/p>/g, '');
        
        return formatted;
    }
    
    exportItem(itemId, itemType) {
        const item = this.items.get(parseInt(itemId));
        if (!item) {
            this.logError(`Item with ID ${itemId} not found for export`);
            return;
        }
        
        try {
            const content = this.formatItemForExport(item);
            const filename = `${this.sanitizeFilename(item.title || 'item')}.md`;
            
            this.downloadFile(content, filename, 'text/markdown');
            this.log(`Exported item: ${item.title}`);
            
        } catch (error) {
            this.setError(error, 'exporting item');
        }
    }
    
    formatItemForExport(item) {
        const title = item.title || 'Untitled';
        const content = item.content || '';
        const category = item.main_category || 'Uncategorized';
        const subCategory = item.sub_category || '';
        const lastUpdated = item.last_updated || item.created_at;
        const sourceUrl = item.source_url || '';
        
        return `# ${title}

**Category:** ${category}${subCategory ? ` > ${subCategory}` : ''}
**Last Updated:** ${new Date(lastUpdated).toLocaleString()}
**Type:** Knowledge Base Item
${sourceUrl ? `**Source:** ${sourceUrl}` : ''}

---

${content}
`;
    }
    
    formatItemsForExport(items) {
        const header = `# Knowledge Base Export

**Export Date:** ${new Date().toLocaleString()}
**Total Items:** ${items.length}

---

`;
        
        const itemsContent = items.map(item => this.formatItemForExport(item)).join('\n\n---\n\n');
        
        return header + itemsContent;
    }
    
    sanitizeFilename(filename) {
        return filename
            .replace(/[^a-z0-9]/gi, '_')
            .replace(/_+/g, '_')
            .replace(/^_|_$/g, '')
            .toLowerCase();
    }
    
    downloadFile(content, filename, mimeType) {
        try {
            const blob = new Blob([content], { type: mimeType });
            const url = URL.createObjectURL(blob);
            
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            
            URL.revokeObjectURL(url);
            
        } catch (error) {
            this.logError('Failed to download file:', error);
            throw error;
        }
    }
    
    // State change handler
    onStateChange(newState, previousState) {
        // Handle loading state changes
        if (newState.loading !== previousState.loading) {
            if (newState.loading) {
                this.showLoadingState();
            } else {
                this.hideLoadingState();
            }
        }
        
        // Handle error state changes
        if (newState.error !== previousState.error) {
            if (newState.error) {
                this.logError('State error:', newState.error);
            }
        }
    }
    
    cleanup() {
        // Close any open modals
        this.closeModal();
        
        // Use CleanupService for comprehensive cleanup
        this.cleanupService.cleanup(this);
        
        // Clear component-specific data
        this.items.clear();
        this.categories.clear();
        this.filteredItems = [];
        this.selectedItem = null;
        
        // Call parent cleanup
        super.cleanup();
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ModernKnowledgeBaseManager;
}
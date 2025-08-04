/**

Modern Knowledge Base Manager
Features:
Browse knowledge base items with modern UI
Category-based filtering and search
Integration with unified database structure
Responsive grid layout with glass morphism design
Quick preview and full content viewing
Export and sharing capabilities
Safer content rendering with optional sanitization
Consistent ID handling and robust date parsing
Preferences persisted in localStorage
*/
console.log('🔍 Loading ModernKnowledgeBaseManager...');
class ModernKnowledgeBaseManager extends BaseManager {
    constructor(options = {}) {
        super({
            enableLogging: true,
            autoInit: false,
            componentName: 'ModernKnowledgeBaseManager',
            ...options
        });

        // External helpers (optional): markdownRenderer(text) -> HTML, htmlSanitizer(html) -> sanitizedHTML
        this.markdownRenderer = options.markdownRenderer || null;
        this.htmlSanitizer = options.htmlSanitizer || null;

        // API / media paths
        this.apiBase = options.apiBase || ''; // EnhancedAPIService already adds /api prefix
        this.mediaBase = options.mediaBase || '/data/media_cache'; // Flask route in web.py

        // Knowledge base state
        this.items = new Map(); // key: String(id), value: item
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

        // Load persisted preferences
        this.loadPreferences();
        // Reflect initial view mode icon and class
        this.applyViewModeUI();
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
    
                <div class="kb-content">
                    <div id="loading-state" class="loading-state">
                        <div class="loading-spinner"></div>
                        <span>Loading knowledge base...</span>
                    </div>
    
                    <div id="empty-state" class="empty-state hidden">
                        <i class="fas fa-book-open"></i>
                        <h3>No items found</h3>
                        <p>Try adjusting your search or filter criteria</p>
                    </div>
    
                    <div id="items-grid" class="items-grid">
                    </div>
                </div>
            </div>
        `;
    }

    async loadKnowledgeBaseItems() {
        try {
            this.items.clear();

            const response = await this.apiCall(`${this.apiBase}/items`, {
                errorMessage: 'Failed to load knowledge base items',
                cache: false,
                showLoading: false
            });

            if (Array.isArray(response)) {
                response.forEach(item => {
                    const idKey = String(item.id);

                    // Normalize dates
                    item._updatedAtMs = this.parseDateToMs(item.last_updated || item.created_at);
                    item._createdAtMs = this.parseDateToMs(item.created_at);

                    // Normalize media files from unified database
                    // Handle kb_media_paths
                    if (typeof item.kb_media_paths === 'string') {
                        try {
                            item.kb_media_paths = JSON.parse(item.kb_media_paths);
                        } catch {
                            item.kb_media_paths = [];
                        }
                    }
                    if (!Array.isArray(item.kb_media_paths)) {
                        item.kb_media_paths = [];
                    }

                    // Handle media_files from unified database
                    if (typeof item.media_files === 'string') {
                        try {
                            item.media_files = JSON.parse(item.media_files);
                        } catch {
                            item.media_files = [];
                        }
                    }
                    if (!Array.isArray(item.media_files)) {
                        item.media_files = [];
                    }

                    // Combine all media files for display (kb_media_paths already parsed above)
                    item.all_media_files = [...(item.kb_media_paths || []), ...(item.media_files || [])];

                    // Ensure content field exists (fallbacks)
                    if (!item.content) {
                        item.content = item.markdown_content || item.kb_content || item.full_text || item.description || '';
                    }

                    this.items.set(idKey, item);
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
            const category = (item.main_category || 'Uncategorized');
            const categoryKey = String(category);

            if (!this.categories.has(categoryKey)) {
                this.categories.set(categoryKey, {
                    name: category,
                    count: 0,
                    items: []
                });
            }

            const categoryData = this.categories.get(categoryKey);
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
                    <option value="${this.escapeAttr(categoryName)}">
                        ${this.escapeHTML(categoryData.name)} (${categoryData.count})
                    </option>
                `);
            });

        this.elements.categoryFilter.innerHTML = options.join('');

        if (this.currentFilter.category !== 'all' && !this.categories.has(this.currentFilter.category)) {
            this.currentFilter.category = 'all';
        }
        this.elements.categoryFilter.value = this.currentFilter.category;
    }

    applyFilters() {
        let filtered = Array.from(this.items.values());

        // Category filter
        if (this.currentFilter.category !== 'all') {
            const selected = this.currentFilter.category;
            filtered = filtered.filter(item =>
                String(item.main_category || 'Uncategorized') === selected
            );
        }

        // Search filter
        if (this.currentFilter.search) {
            const searchTerm = this.currentFilter.search.toLowerCase();
            filtered = filtered.filter(item =>
                (item.title || '').toLowerCase().includes(searchTerm) ||
                (item.content || '').toLowerCase().includes(searchTerm) ||
                (item.main_category || '').toLowerCase().includes(searchTerm) ||
                (item.sub_category || '').toLowerCase().includes(searchTerm)
            );
        }

        // Sort
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
                    aVal = a._updatedAtMs || 0;
                    bVal = b._updatedAtMs || 0;
                    break;
            }

            const comparison = aVal < bVal ? -1 : aVal > bVal ? 1 : 0;
            return sortOrder === 'desc' ? -comparison : comparison;
        });

        this.filteredItems = filtered;
        this.renderItems();
        this.updateStats();
        this.persistPreferences();
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

        // Preserve classes and only toggle view mode class
        this.applyViewModeUI();
    }

    createItemHTML(item) {
        // Smart title selection: prefer display_title, then content if title looks like a filename, then title
        let title = item.display_title;
        if (!title) {
            // If title looks like a filename (contains hyphens and no spaces), use content instead
            if (item.title && item.title.includes('-') && !item.title.includes(' ') && item.content) {
                title = item.content.split('\n')[0].substring(0, 60); // First line, max 60 chars
            } else {
                title = item.title || item.item_name;
            }
        }
        title = this.escapeHTML(title || 'Untitled');
        const category = this.escapeHTML(item.main_category || 'Uncategorized');
        const subCategory = this.escapeHTML(item.sub_category || '');
        const lastUpdated = this.formatRelativeDate(item.last_updated || item.created_at);
        const preview = this.createPreview(item.content || '');

        const idAttr = this.escapeAttr(String(item.id));
        const sourceLink = item.source_url ? `<span class="source-link"><i class="fas fa-external-link-alt"></i> Source</span>` : '';

        return `
            <div class="kb-item glass-panel-v3--interactive" data-item-id="${idAttr}" data-item-type="kb_item">
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
                        ${sourceLink}
                    </div>
                </div>
            </div>
        `;
    }

    createPreview(content) {
        if (!content) return 'No content available';
        const plainText = this.toPlainText(content).trim();
        return plainText.length > 200
            ? this.escapeHTML(plainText.substring(0, 200)) + '...'
            : this.escapeHTML(plainText);
    }

    toPlainText(content) {
        const withoutMd = String(content).replace(/[#*_`~$$$\(\)]/g, ' ');
        const withoutHtml = withoutMd.replace(/<[^>]*>/g, ' ');
        return withoutHtml.replace(/\s+/g, ' ');
    }

    formatRelativeDate(dateString) {
        if (!dateString) return 'Unknown';

        const dateMs = this.parseDateToMs(dateString);
        if (!dateMs) return 'Unknown';

        const date = new Date(dateMs);
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

    parseDateToMs(input) {
        if (!input) return 0;
        if (typeof input === 'number') return input;
        const ms = Date.parse(input);
        return Number.isNaN(ms) ? 0 : ms;
    }

    updateStats() {
        if (this.elements.itemsCount) {
            this.elements.itemsCount.textContent = String(this.filteredItems.length);
        }

        const categoriesCountEl = document.getElementById('categories-count');
        if (categoriesCountEl) {
            categoriesCountEl.textContent = String(this.categories.size);
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
        this.applyViewModeUI();
        this.persistPreferences();
        this.log(`View mode changed to: ${this.viewMode}`);
    }

    applyViewModeUI() {
        if (this.elements.viewToggle) {
            const icon = this.elements.viewToggle.querySelector('i');
            if (icon) {
                icon.className = this.viewMode === 'grid' ? 'fas fa-th' : 'fas fa-list';
            }
        }

        if (this.elements.itemsGrid) {
            this.elements.itemsGrid.classList.remove('grid-view', 'list-view');
            this.elements.itemsGrid.classList.add(`${this.viewMode}-view`);
            if (!this.elements.itemsGrid.classList.contains('items-grid')) {
                this.elements.itemsGrid.classList.add('items-grid');
            }
        }
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

        // If click originated from an action button, ignore here
        if (e.target.closest('.item-action-btn')) return;

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
        const key = String(itemId);
        const item = this.items.get(key);
        if (!item) {
            this.logError(`Item with ID ${itemId} not found`);
            return;
        }

        this.selectedItem = item;
        this.createAndShowModal(item);
    }

    createAndShowModal(item) {
        const existingModal = document.getElementById('kb-item-modal');
        if (existingModal) {
            existingModal.remove();
        }

        // Smart title selection: prefer display_title, then content if title looks like a filename, then title
        let title = item.display_title;
        if (!title) {
            // If title looks like a filename (contains hyphens and no spaces), use content instead
            if (item.title && item.title.includes('-') && !item.title.includes(' ') && item.content) {
                title = item.content.split('\n')[0].substring(0, 60); // First line, max 60 chars
            } else {
                title = item.title || item.item_name;
            }
        }
        title = this.escapeHTML(title || 'Untitled');
        const category = this.escapeHTML(item.main_category || 'Uncategorized');
        const subCategory = this.escapeHTML(item.sub_category || '');
        const content = item.content || 'No content available';
        const lastUpdated = new Date(this.parseDateToMs(item.last_updated || item.created_at)).toLocaleString();
        const sourceUrl = item.source_url;

        // Only use media_files since kb_media_paths often reference non-existent files
        const mediaFiles = item.media_files || [];

        const mediaGridHTML = mediaFiles.length > 0
            ? `
            <div class="modal-media-section">
                <h3><i class="fas fa-images"></i> Media Files</h3>
                <div class="media-grid">
                    ${mediaFiles.map(mediaPath => `
                        <div class="media-item">
                            <img src="${this.mediaUrl(mediaPath)}" alt="Knowledge base media"
                                 onclick="this.classList.toggle('expanded')"
                                 title="Click to expand" loading="lazy">
                        </div>
                    `).join('')}
                </div>
            </div>
            `
            : '';

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
                            <span>Last Updated: ${this.escapeHTML(lastUpdated)}</span>
                        </div>
                        ${item.tweet_id ? `<div class="metadata-item">
                            <i class="fas fa-hashtag"></i>
                            <span>Tweet ID: ${this.escapeHTML(String(item.tweet_id))}</span>
                        </div>` : ''}
                    </div>
    
                    ${mediaGridHTML}
    
                    <div class="modal-content-section">
                        <h3><i class="fas fa-file-text"></i> Content</h3>
                        <div class="modal-content">
                            ${this.renderContentHTML(content)}
                        </div>
                    </div>
                </div>
            </div>
        `;

        document.body.insertAdjacentHTML('beforeend', modalHTML);
        this.setupModalEventListeners(item);

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

        this.eventService.setupStandardListeners(this, {
            buttons: [
                {
                    selector: '#modal-close-btn',
                    handler: this.closeModal
                },
                {
                    selector: '#modal-export-btn',
                    handler: () => this.exportItem(String(item.id), 'kb_item')
                },
                {
                    selector: '#modal-source-btn',
                    handler: () => {
                        if (item.source_url) {
                            window.open(item.source_url, '_blank', 'noopener,noreferrer');
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
            }, 300);
        }
        this.selectedItem = null;
    }

    renderContentHTML(content) {
        let html = '';
        const text = String(content || '');

        if (this.markdownRenderer) {
            try {
                html = this.markdownRenderer(text);
            } catch {
                html = this.escapeHTML(text).replace(/\n/g, '<br>');
            }
        } else {
            const escaped = this.escapeHTML(text);
            html = `<p>${escaped.replace(/\n\n/g, '</p><p>').replace(/\n/g, '<br>')}</p>`;
        }

        if (this.htmlSanitizer) {
            try {
                html = this.htmlSanitizer(html);
            } catch {
                html = `<pre>${this.escapeHTML(text)}</pre>`;
            }
        }

        return html;
    }

    exportItem(itemId, itemType) {
        const key = String(itemId);
        const item = this.items.get(key);
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
Category: ${category}${subCategory ? ` > ${subCategory}` : ''}
Last Updated: ${new Date(this.parseDateToMs(lastUpdated)).toLocaleString()}
Type: Knowledge Base Item
${sourceUrl ? `**Source:** ${sourceUrl}` : ''}

${content}
`;
    }


    formatItemsForExport(items) {
        const header = `# Knowledge Base Export
    Export Date: ${new Date().toLocaleString()}
    Total Items: ${items.length}

`;


        const itemsContent = items.map(item => this.formatItemForExport(item)).join('\n\n---\n\n');

        return header + itemsContent;
    }

    sanitizeFilename(filename) {
        return String(filename)
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

    mediaUrl(path) {
        const pathStr = String(path);

        // Handle different media path formats
        if (pathStr.startsWith('data/media_cache/')) {
            // Full path from media_files - use direct route
            return `/${pathStr}`;
        } else {
            // Relative path from kb_media_paths - use API media route
            const safe = pathStr.split('/').map(encodeURIComponent).join('/');
            return `/api/media/${safe}`;
        }
    }

    // Preferences persistence
    loadPreferences() {
        try {
            const raw = localStorage.getItem('kb_manager_prefs');
            if (!raw) return;
            const prefs = JSON.parse(raw);
            if (prefs.viewMode === 'grid' || prefs.viewMode === 'list') {
                this.viewMode = prefs.viewMode;
            }
            if (typeof prefs.sortBy === 'string') {
                this.currentFilter.sortBy = prefs.sortBy;
                if (this.elements.sortSelect) {
                    this.elements.sortSelect.value = prefs.sortBy;
                }
            }
            if (typeof prefs.category === 'string') {
                this.currentFilter.category = prefs.category;
            }
            if (typeof prefs.search === 'string') {
                this.currentFilter.search = prefs.search;
                if (this.elements.searchInput) {
                    this.elements.searchInput.value = prefs.search;
                }
            }
        } catch {
            // ignore corrupt prefs
        }
    }

    persistPreferences() {
        try {
            const prefs = {
                viewMode: this.viewMode,
                sortBy: this.currentFilter.sortBy,
                category: this.currentFilter.category,
                search: this.currentFilter.search
            };
            localStorage.setItem('kb_manager_prefs', JSON.stringify(prefs));
        } catch {
            // ignore storage errors
        }
    }

    // Escaping helpers
    escapeHTML(str) {
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    escapeAttr(str) {
        return this.escapeHTML(str).replace(/"/g, '&quot;');
    }

    // State change handler
    onStateChange(newState, previousState) {
        if (newState.loading !== previousState.loading) {
            if (newState.loading) {
                this.showLoadingState();
            } else {
                this.hideLoadingState();
            }
        }

        if (newState.error !== previousState.error) {
            if (newState.error) {
                this.logError('State error:', newState.error);
            }
        }
    }

    cleanup() {
        this.closeModal();
        this.cleanupService.cleanup(this);
        this.items.clear();
        this.categories.clear();
        this.filteredItems = [];
        this.selectedItem = null;
        super.cleanup();
    }
}

console.log('✅ ModernKnowledgeBaseManager class defined successfully');

// Make available globally for browser usage
if (typeof window !== 'undefined') {
    window.ModernKnowledgeBaseManager = ModernKnowledgeBaseManager;
    console.log('✅ ModernKnowledgeBaseManager attached to window object');
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ModernKnowledgeBaseManager;
}

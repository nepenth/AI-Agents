/**
Modern Synthesis Manager (Redesigned)
From first-principles: The core purpose is to provide an intuitive, efficient way to browse and search synthesis documents (AI-generated summaries from knowledge base items), 
nested potentially by categories/sub-categories, inspired by Apple's Human Interface Guidelines. 
Usability: Sidebar for hierarchical navigation, main area for content display, real-time search, hover previews, modal for details. 
Modern UI: Glassmorphism with blurred panels, animations. 
Engineering: Maps for data, debounced search, lazy rendering, API integration.
*/
console.log('🔍 Loading ModernSynthesisManager (Redesigned)...');
class ModernSynthesisManager extends BaseManager {
    constructor(options = {}) {
        super({
            enableLogging: true,
            autoInit: false,
            componentName: 'ModernSynthesisManager',
            ...options
        });

        // Optional external helpers
        this.markdownRenderer = options.markdownRenderer || null;
        this.htmlSanitizer = options.htmlSanitizer || null;

        // API paths
        this.apiBase = options.apiBase || '';

        // Data structures
        this.documents = new Map(); // id (string) -> document object
        this.categoryTree = new Map(); // main_category -> Map(sub_category -> array of documents)

        // Current state
        this.currentFilter = {
            category: 'all',
            sub: null,
            search: '',
            sortBy: 'updated-desc'
        };

        // UI state
        this.viewMode = 'grid'; // 'grid' or 'list'
        this.selectedDocument = null;
    }

    async initializeElements() {
        this.elements.container = document.getElementById('main-content');
        if (!this.elements.container) {
            throw new Error('Main content container not found');
        }

        await this.createSynthesisInterface();

        // Cache elements
        this.elements.searchInput = document.getElementById('synthesis-search');
        this.elements.sortSelect = document.getElementById('sort-select');
        this.elements.viewToggle = document.getElementById('view-toggle');
        this.elements.categoryTree = document.getElementById('category-tree');
        this.elements.currentViewTitle = document.getElementById('current-view-title');
        this.elements.itemsList = document.getElementById('items-list');
        this.elements.itemsCount = document.getElementById('items-count');
        this.elements.categoriesCount = document.getElementById('categories-count');
        this.elements.showingCount = document.getElementById('showing-count');
        this.elements.loadingState = document.getElementById('loading-state');
        this.elements.emptyState = document.getElementById('empty-state');
        this.elements.refreshBtn = document.getElementById('refresh-btn');
        this.elements.exportBtn = document.getElementById('export-btn');

        // Load preferences
        this.loadPreferences();
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
                    container: this.elements.categoryTree,
                    selector: '.category-header',
                    event: 'click',
                    handler: this.handleToggleExpand
                },
                {
                    container: this.elements.categoryTree,
                    selector: '.sub-category-item, .all-categories',
                    event: 'click',
                    handler: this.handleSelectCategory
                },
                {
                    container: this.elements.itemsList,
                    selector: '.synthesis-item',
                    event: 'click',
                    handler: this.handleItemClick
                },
                {
                    container: this.elements.itemsList,
                    selector: '.item-action-btn',
                    event: 'click',
                    handler: this.handleItemAction
                },
                {
                    container: this.elements.itemsList,
                    selector: '.synthesis-item',
                    event: 'mouseenter',
                    handler: this.handleItemHoverIn
                },
                {
                    container: this.elements.itemsList,
                    selector: '.synthesis-item',
                    event: 'mouseleave',
                    handler: this.handleItemHoverOut
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
            this.log('Loading initial synthesis data...');

            await this.loadSynthesisDocuments();
            this.buildCategoryTree();
            this.renderSidebar();

            this.applyFilters();

            this.setState({
                initialized: true,
                loading: false
            });

            this.log('Initialization completed successfully');

        } catch (error) {
            this.setError(error, 'loading synthesis documents');
            this.showEmptyState('Failed to load synthesis documents');
        }
    }

    async createSynthesisInterface() {
        this.elements.container.innerHTML = `
            <style>
                .modern-synthesis-container {
                    height: 100%;
                    display: flex;
                    flex-direction: column;
                    padding: 1rem;
                    box-sizing: border-box;
                }
                .synthesis-header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 1rem;
                }
                .synthesis-body {
                    display: flex;
                    flex: 1;
                    overflow: hidden;
                }
                .synthesis-sidebar {
                    width: 300px;
                    min-width: 250px;
                    height: 100%;
                    overflow-y: auto;
                    padding: 1rem;
                    box-sizing: border-box;
                    background: rgba(255,255,255,0.05);
                    backdrop-filter: blur(10px);
                    border-right: 1px solid rgba(255,255,255,0.1);
                }
                .category-tree-list {
                    list-style: none;
                    padding: 0;
                    margin: 0;
                }
                .category-item, .all-categories {
                    margin-bottom: 0.5rem;
                }
                .category-header {
                    display: flex;
                    align-items: center;
                    cursor: pointer;
                    padding: 0.5rem;
                    border-radius: 8px;
                    transition: background 0.2s;
                }
                .category-header:hover {
                    background: rgba(255,255,255,0.05);
                }
                .category-header i {
                    margin-right: 0.5rem;
                }
                .expand-icon {
                    margin-left: auto;
                }
                .sub-categories {
                    list-style: none;
                    padding-left: 1.5rem;
                    margin: 0;
                }
                .sub-category-item {
                    display: flex;
                    align-items: center;
                    cursor: pointer;
                    padding: 0.5rem;
                    border-radius: 8px;
                    transition: background 0.2s;
                }
                .sub-category-item:hover {
                    background: rgba(255,255,255,0.05);
                }
                .sub-category-item i {
                    margin-right: 0.5rem;
                }
                .synthesis-main {
                    flex: 1;
                    padding: 1rem;
                    overflow-y: auto;
                    box-sizing: border-box;
                }
                .synthesis-controls {
                    display: flex;
                    align-items: center;
                    margin-bottom: 1rem;
                }
                .search-container {
                    flex: 1;
                    margin-right: 1rem;
                }
                .synthesis-stats {
                    display: flex;
                    gap: 1rem;
                    margin-bottom: 1rem;
                }
                .items-list {
                    display: grid;
                    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
                    gap: 1rem;
                }
                .items-list.list-view {
                    display: flex;
                    flex-direction: column;
                }
                .items-list.list-view .synthesis-item {
                    width: 100%;
                }
                .synthesis-item {
                    cursor: pointer;
                    padding: 1rem;
                    border-radius: 8px;
                    background: rgba(255,255,255,0.05);
                    backdrop-filter: blur(10px);
                    border: 1px solid rgba(255,255,255,0.1);
                    transition: transform 0.2s;
                }
                .synthesis-item:hover {
                    transform: translateY(-2px);
                }
                .hidden {
                    display: none;
                }
                /* Additional styles for modals, etc. can be added here */
            </style>
            <div class="modern-synthesis-container glass-panel-v3 animate-fade-in">
                <header class="synthesis-header">
                    <div class="header-title">
                        <h1><i class="fas fa-layer-group"></i> Synthesis Documents</h1>
                        <p class="header-subtitle">Explore AI-generated insights and summaries</p>
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

                <div class="synthesis-body">
                    <aside id="synthesis-sidebar" class="synthesis-sidebar glass-panel-v3">
                        <ul id="category-tree" class="category-tree-list"></ul>
                    </aside>

                    <section class="synthesis-main">
                        <h2 id="current-view-title" class="view-title">All Synthesis Documents</h2>

                        <div class="synthesis-controls">
                            <div class="search-container">
                                <i class="fas fa-search"></i>
                                <input type="text" id="synthesis-search" placeholder="Search by title, content, category..." class="glass-input">
                            </div>

                            <select id="sort-select" class="glass-select">
                                <option value="updated-desc">Recently Updated</option>
                                <option value="updated-asc">Oldest Updated</option>
                                <option value="title-asc">Title A-Z</option>
                                <option value="title-desc">Title Z-A</option>
                                <option value="category-asc">Category A-Z</option>
                            </select>

                            <button id="view-toggle" class="glass-button glass-button--small" title="Toggle View">
                                <i class="fas fa-th"></i>
                            </button>
                        </div>

                        <div class="synthesis-stats">
                            <div class="stat-item">
                                <span class="stat-label">Total Documents</span>
                                <span id="items-count" class="stat-value">--</span>
                            </div>
                            <div class="stat-item">
                                <span class="stat-label">Categories</span>
                                <span id="categories-count" class="stat-value">--</span>
                            </div>
                            <div class="stat-item">
                                <span class="stat-label">Showing</span>
                                <span id="showing-count" class="stat-value">--</span>
                            </div>
                        </div>

                        <div id="synthesis-main-content">
                            <div id="loading-state" class="loading-state">
                                <div class="loading-spinner"></div>
                                <span>Loading documents...</span>
                            </div>

                            <div id="empty-state" class="empty-state hidden">
                                <i class="fas fa-layer-group"></i>
                                <h3>No documents found</h3>
                                <p>Try adjusting your search or select a different category</p>
                            </div>

                            <div id="items-list" class="items-list grid-view"></div>
                        </div>
                    </section>
                </div>
            </div>
        `;
    }

    async loadSynthesisDocuments() {
        this.documents.clear();

        // First, get the list of synthesis documents
        const response = await this.apiCall(`${this.apiBase}/api/synthesis`, {
            errorMessage: 'Failed to load synthesis documents list',
            cache: false,
            showLoading: false
        });

        let syntheses = [];
        if (Array.isArray(response)) {
            syntheses = response;
        } else if (response && Array.isArray(response.synthesis_documents)) {
            syntheses = response.synthesis_documents;
        } else if (response && Array.isArray(response.data)) {
            syntheses = response.data;
        } else if (response && response.success && Array.isArray(response.data)) {
            syntheses = response.data;
        }

        if (Array.isArray(syntheses)) {
            this.log(`Loading full content for ${syntheses.length} synthesis documents...`);
            
            // Load full content for each document (with concurrency limit)
            const batchSize = 5; // Limit concurrent requests
            const batches = [];
            for (let i = 0; i < syntheses.length; i += batchSize) {
                batches.push(syntheses.slice(i, i + batchSize));
            }

            // Process batches sequentially to avoid overwhelming the server
            for (const batch of batches) {
                const batchPromises = batch.map(async (doc) => {
                    try {
                        const fullDoc = await this.apiCall(`${this.apiBase}/api/synthesis/${doc.id}`, {
                            errorMessage: `Failed to load full content for document ${doc.id}`,
                            cache: false,
                            showLoading: false
                        });
                        
                        if (fullDoc) {
                            const id = String(fullDoc.id);

                            // Debug logging for first document
                            if (doc.id === syntheses[0].id) {
                                this.log('First document full structure:', {
                                    id: fullDoc.id,
                                    synthesis_title: fullDoc.synthesis_title,
                                    synthesis_content_length: fullDoc.synthesis_content ? fullDoc.synthesis_content.length : 0,
                                    has_raw_json_content_parsed: !!fullDoc.raw_json_content_parsed
                                });
                            }

                            // Normalize dates
                            fullDoc._updatedAtMs = this.parseDateToMs(fullDoc.last_updated || fullDoc.created_at);
                            fullDoc._createdAtMs = this.parseDateToMs(fullDoc.created_at);

                            // Fallback title and content - handle multiple possible content fields
                            fullDoc.title = fullDoc.synthesis_title || fullDoc.synthesis_short_name || fullDoc.title || 'Untitled';
                            fullDoc.content = fullDoc.synthesis_content || fullDoc.content || '';

                            // If content is still empty, try to extract from raw_json_content_parsed
                            if (!fullDoc.content && fullDoc.raw_json_content_parsed) {
                                try {
                                    const parsed = typeof fullDoc.raw_json_content_parsed === 'string' 
                                        ? JSON.parse(fullDoc.raw_json_content_parsed) 
                                        : fullDoc.raw_json_content_parsed;
                                    
                                    // Try to construct content from parsed JSON structure
                                    if (parsed.title || parsed.key_findings || parsed.core_patterns) {
                                        fullDoc.content = this.constructContentFromParsedJSON(parsed);
                                    }
                                } catch (error) {
                                    this.logWarn(`Failed to parse raw_json_content_parsed for document ${id}:`, error);
                                }
                            }

                            // Debug final content length
                            if (doc.id === syntheses[0].id) {
                                this.log('Final content length for first document:', fullDoc.content ? fullDoc.content.length : 0);
                            }

                            this.documents.set(id, fullDoc);
                        }
                    } catch (error) {
                        this.logError(`Failed to load full content for document ${doc.id}:`, error);
                        // Fall back to using the summary data
                        const id = String(doc.id);
                        doc._updatedAtMs = this.parseDateToMs(doc.last_updated || doc.created_at);
                        doc._createdAtMs = this.parseDateToMs(doc.created_at);
                        doc.title = doc.title || 'Untitled';
                        doc.content = doc.summary || '';
                        this.documents.set(id, doc);
                    }
                });

                // Wait for current batch to complete before starting next batch
                await Promise.all(batchPromises);
            }
            
            this.log(`Loaded full content for ${this.documents.size} synthesis documents`);
        } else {
            this.logWarn('Non-array response from API:', response);
        }
    }

    buildCategoryTree() {
        this.categoryTree.clear();

        this.documents.forEach(doc => {
            const main = doc.main_category || 'Uncategorized';
            const sub = doc.sub_category || 'General';

            if (!this.categoryTree.has(main)) {
                this.categoryTree.set(main, new Map());
            }

            const subMap = this.categoryTree.get(main);
            if (!subMap.has(sub)) {
                subMap.set(sub, []);
            }

            subMap.get(sub).push(doc);
        });
    }

    renderSidebar() {
        if (!this.elements.categoryTree) return;

        let html = `
            <li class="all-categories" data-category="all">
                <div class="category-header all-header">
                    <i class="fas fa-layer-group"></i>
                    <span>All Synthesis Documents</span>
                </div>
            </li>
        `;

        Array.from(this.categoryTree.keys()).sort((a, b) => a.localeCompare(b)).forEach(main => {
            html += `
                <li class="category-item" data-category="${this.escapeAttr(main)}">
                    <div class="category-header">
                        <i class="fas fa-folder"></i>
                        <span>${this.escapeHTML(main)}</span>
                        <i class="fas fa-chevron-down expand-icon"></i>
                    </div>
                    <ul class="sub-categories hidden">
            `;

            Array.from(this.categoryTree.get(main).keys()).sort((a, b) => a.localeCompare(b)).forEach(sub => {
                html += `
                    <li class="sub-category-item" data-category="${this.escapeAttr(main)}" data-sub="${this.escapeAttr(sub)}">
                        <i class="fas fa-folder-open"></i>
                        <span>${this.escapeHTML(sub)}</span>
                    </li>
                `;
            });

            html += `</ul></li>`;
        });

        this.elements.categoryTree.innerHTML = html;
    }

    applyFilters() {
        let viewDocuments = [];

        if (this.currentFilter.search) {
            // Global search
            const term = this.currentFilter.search.toLowerCase();
            viewDocuments = Array.from(this.documents.values()).filter(doc => 
                (doc.title || '').toLowerCase().includes(term) ||
                (doc.content || '').toLowerCase().includes(term) ||
                (doc.main_category || '').toLowerCase().includes(term) ||
                (doc.sub_category || '').toLowerCase().includes(term)
            );
        } else {
            // Category/sub based
            if (this.currentFilter.category === 'all') {
                this.documents.forEach(doc => viewDocuments.push(doc));
            } else {
                const subMap = this.categoryTree.get(this.currentFilter.category);
                if (subMap) {
                    if (this.currentFilter.sub) {
                        viewDocuments = subMap.get(this.currentFilter.sub) || [];
                    } else {
                        subMap.forEach(docs => viewDocuments.push(...docs));
                    }
                }
            }
        }

        // Apply sorting
        const [sortBy, sortDir] = this.currentFilter.sortBy.split('-');
        viewDocuments.sort((a, b) => {
            let va, vb;
            switch (sortBy) {
                case 'title':
                    va = (a.title || '').toLowerCase();
                    vb = (b.title || '').toLowerCase();
                    break;
                case 'category':
                    va = (a.main_category || '').toLowerCase();
                    vb = (b.main_category || '').toLowerCase();
                    break;
                case 'updated':
                default:
                    va = a._updatedAtMs || 0;
                    vb = b._updatedAtMs || 0;
                    break;
            }
            if (va < vb) return sortDir === 'asc' ? -1 : 1;
            if (va > vb) return sortDir === 'asc' ? 1 : -1;
            return 0;
        });

        // Render
        this.renderDocuments(viewDocuments);

        // Update UI
        this.updateViewTitle();
        this.updateStats(viewDocuments.length);
        this.persistPreferences();
    }

    renderDocuments(docs) {
        if (!this.elements.itemsList) return;

        if (docs.length === 0) {
            this.showEmptyState();
            return;
        }

        this.hideLoadingState();
        this.hideEmptyState();

        let html = '';
        docs.forEach(doc => {
            html += this.createDocumentHTML(doc);
        });
        this.elements.itemsList.innerHTML = html;
    }

    updateViewTitle() {
        if (!this.elements.currentViewTitle) return;

        let title = '';
        if (this.currentFilter.search) {
            title = `Search Results for "${this.escapeHTML(this.currentFilter.search)}"`;
        } else if (this.currentFilter.sub) {
            title = `${this.escapeHTML(this.currentFilter.category)} > ${this.escapeHTML(this.currentFilter.sub)}`;
        } else if (this.currentFilter.category !== 'all') {
            title = this.escapeHTML(this.currentFilter.category);
        } else {
            title = 'All Synthesis Documents';
        }
        this.elements.currentViewTitle.textContent = title;
    }

    createDocumentHTML(doc) {
        const title = this.escapeHTML(doc.title);
        const category = this.escapeHTML(doc.main_category || 'Uncategorized');
        const sub = this.escapeHTML(doc.sub_category || '');
        const lastUpdated = this.formatRelativeDate(doc.last_updated || doc.created_at);
        const shortPreview = this.createPreview(doc.content || '', 200);
        const hoverPreview = this.createPreview(doc.content || '', 800);
        const id = this.escapeAttr(String(doc.id));
        const itemCount = doc.item_count || 0;

        return `
            <div class="synthesis-item glass-panel-v3--interactive" data-item-id="${id}" data-item-type="synthesis">
                <div class="item-header">
                    <div class="item-type">
                        <i class="fas fa-layer-group"></i>
                        <span>${title}</span>
                    </div>
                    <div class="item-actions">
                        <button class="item-action-btn" data-action="view" title="View Details">
                            <i class="fas fa-eye"></i>
                        </button>
                        <button class="item-action-btn" data-action="export" title="Export">
                            <i class="fas fa-download"></i>
                        </button>
                    </div>
                </div>

                <div class="item-content">
                    <div class="item-categories">
                        <span class="category-badge main-category">${category}</span>
                        ${sub ? `<span class="category-badge sub-category">${sub}</span>` : ''}
                    </div>
                    <div class="item-preview">${shortPreview}</div>
                </div>

                <div class="item-footer">
                    <span class="item-count">${itemCount} sources</span>
                    <span class="last-updated">Updated ${lastUpdated}</span>
                </div>

                <div class="item-hover-preview glass-panel-v3 hidden">
                    ${hoverPreview}
                </div>
            </div>
        `;
    }

    updateStats(showing) {
        if (this.elements.itemsCount) {
            this.elements.itemsCount.textContent = this.documents.size;
        }
        if (this.elements.categoriesCount) {
            this.elements.categoriesCount.textContent = this.categoryTree.size;
        }
        if (this.elements.showingCount) {
            this.elements.showingCount.textContent = showing;
        }
    }

    showLoadingState() {
        if (this.elements.loadingState) {
            this.elements.loadingState.classList.remove('hidden');
        }
        if (this.elements.itemsList) {
            this.elements.itemsList.classList.add('hidden');
        }
        if (this.elements.emptyState) {
            this.elements.emptyState.classList.add('hidden');
        }
    }

    hideLoadingState() {
        if (this.elements.loadingState) {
            this.elements.loadingState.classList.add('hidden');
        }
        if (this.elements.itemsList) {
            this.elements.itemsList.classList.remove('hidden');
        }
    }

    showEmptyState() {
        if (this.elements.emptyState) {
            const p = this.elements.emptyState.querySelector('p');
            if (p) {
                p.textContent = this.currentFilter.search ? `No results for "${this.escapeHTML(this.currentFilter.search)}"` : 'No documents in this category';
            }
            this.elements.emptyState.classList.remove('hidden');
        }
        if (this.elements.itemsList) {
            this.elements.itemsList.classList.add('hidden');
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

    handleToggleExpand = (e) => {
        const header = e.target.closest('.category-header');
        if (!header || header.classList.contains('all-header')) return;

        const subList = header.nextElementSibling;
        if (subList) {
            subList.classList.toggle('hidden');
            const icon = header.querySelector('.expand-icon');
            if (icon) {
                icon.classList.toggle('fa-chevron-down');
                icon.classList.toggle('fa-chevron-up');
            }
        }
    }

    handleSelectCategory = (e) => {
        const li = e.target.closest('li');
        if (!li) return;

        this.currentFilter.category = li.dataset.category;
        this.currentFilter.sub = li.dataset.sub || null;
        this.currentFilter.search = ''; // Clear search when changing category
        if (this.elements.searchInput) this.elements.searchInput.value = '';
        this.applyFilters();
    }

    handleSearch = (e) => {
        this.currentFilter.search = e.target.value.trim();
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
    }

    applyViewModeUI() {
        if (this.elements.viewToggle) {
            const icon = this.elements.viewToggle.querySelector('i');
            if (icon) {
                icon.className = this.viewMode === 'grid' ? 'fas fa-th' : 'fas fa-list';
            }
        }
        if (this.elements.itemsList) {
            this.elements.itemsList.classList.toggle('grid-view', this.viewMode === 'grid');
            this.elements.itemsList.classList.toggle('list-view', this.viewMode === 'list');
        }
    }

    handleRefresh = async () => {
        try {
            this.log('Refreshing synthesis documents...');
            await this.loadInitialData();
        } catch (error) {
            this.setError(error, 'refreshing synthesis documents');
        }
    }

    handleExportAll = () => {
        try {
            const allDocs = Array.from(this.documents.values());
            const content = this.formatDocumentsForExport(allDocs);
            const filename = `synthesis_documents_export_${new Date().toISOString().split('T')[0]}.md`;
            this.downloadFile(content, filename, 'text/markdown');
            this.log(`Exported ${allDocs.length} documents`);
        } catch (error) {
            this.setError(error, 'exporting all documents');
        }
    }

    handleItemClick = (e) => {
        if (e.target.closest('.item-action-btn')) return;
        const itemEl = e.target.closest('.synthesis-item');
        if (!itemEl) return;
        const id = itemEl.dataset.itemId;
        this.viewDocument(id);
    }

    handleItemAction = (e) => {
        e.stopPropagation();
        const btn = e.target.closest('.item-action-btn');
        if (!btn) return;
        const action = btn.dataset.action;
        const itemEl = btn.closest('.synthesis-item');
        if (!itemEl) return;
        const id = itemEl.dataset.itemId;

        if (action === 'view') {
            this.viewDocument(id);
        } else if (action === 'export') {
            this.exportDocument(id);
        }
    }

    handleItemHoverIn = (e) => {
        const item = e.target.closest('.synthesis-item');
        if (!item) return;
        const preview = item.querySelector('.item-hover-preview');
        if (preview) {
            preview.classList.remove('hidden');
        }
    }

    handleItemHoverOut = (e) => {
        const item = e.target.closest('.synthesis-item');
        if (!item) return;
        const preview = item.querySelector('.item-hover-preview');
        if (preview) {
            preview.classList.add('hidden');
        }
    }

    handleEscape = () => {
        this.closeModal();
    }

    viewDocument(id) {
        const doc = this.documents.get(String(id));
        if (doc) {
            this.selectedDocument = doc;
            this.createAndShowModal(doc);
        } else {
            this.logError(`Document ${id} not found`);
        }
    }

    createAndShowModal(doc) {
        const existingModal = document.getElementById('synthesis-modal');
        if (existingModal) {
            existingModal.remove();
        }

        const title = this.escapeHTML(doc.title);
        const category = this.escapeHTML(doc.main_category || 'Uncategorized');
        const subCategory = this.escapeHTML(doc.sub_category || '');
        const content = doc.content || 'No content available';
        const lastUpdated = new Date(this.parseDateToMs(doc.last_updated || doc.created_at)).toLocaleString();
        const itemCount = doc.item_count || 0;

        const modalHTML = `
            <div id="synthesis-modal" class="modal-overlay">
                <div class="modal-container glass-panel-v3 liquid-glass">
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
                        <div class="metadata-item">
                            <i class="fas fa-file-alt"></i>
                            <span>Source Items: ${itemCount}</span>
                        </div>
                    </div>

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
        this.setupModalEventListeners(doc);

        requestAnimationFrame(() => {
            const modal = document.getElementById('synthesis-modal');
            if (modal) {
                modal.classList.add('show');
            }
        });
    }

    setupModalEventListeners(doc) {
        const modal = document.getElementById('synthesis-modal');
        if (!modal) return;

        this.eventService.setupStandardListeners(this, {
            buttons: [
                {
                    selector: '#modal-close-btn',
                    handler: this.closeModal
                },
                {
                    selector: '#modal-export-btn',
                    handler: () => this.exportDocument(String(doc.id))
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
        const modal = document.getElementById('synthesis-modal');
        if (modal) {
            modal.classList.add('closing');
            setTimeout(() => {
                modal.remove();
            }, 300);
        }
        this.selectedDocument = null;
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

    exportDocument(id) {
        const doc = this.documents.get(String(id));
        if (!doc) {
            this.logError(`Document ${id} not found for export`);
            return;
        }

        try {
            const content = this.formatDocumentForExport(doc);
            const filename = `${this.sanitizeFilename(doc.title || 'document')}.md`;
            this.downloadFile(content, filename, 'text/markdown');
            this.log(`Exported document: ${doc.title}`);
        } catch (error) {
            this.setError(error, 'exporting document');
        }
    }

    formatDocumentForExport(doc) {
        const title = doc.title || 'Untitled';
        const content = doc.content || '';
        const category = doc.main_category || 'Uncategorized';
        const subCategory = doc.sub_category || '';
        const lastUpdated = doc.last_updated || doc.created_at;
        const itemCount = doc.item_count || 0;

        return `# ${title}
Category: ${category}${subCategory ? ` > ${subCategory}` : ''}
Last Updated: ${new Date(this.parseDateToMs(lastUpdated)).toLocaleString()}
Type: Synthesis Document
Sources: ${itemCount}

${content}
`;
    }

    formatDocumentsForExport(docs) {
        const header = `# Synthesis Documents Export
Export Date: ${new Date().toLocaleString()}
Total Documents: ${docs.length}

`;

        const docsContent = docs.map(doc => this.formatDocumentForExport(doc)).join('\n\n---\n\n');

        return header + docsContent;
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
            this.logError('Failed to download file', error);
            throw error;
        }
    }

    getDisplayTitle(doc) {
        return doc.title;
    }

    createPreview(content, maxLength) {
        if (!content) return 'No content available';
        const plainText = this.toPlainText(content).trim();
        return plainText.length > maxLength
            ? this.escapeHTML(plainText.substring(0, maxLength)) + '...'
            : this.escapeHTML(plainText);
    }

    constructContentFromParsedJSON(parsed) {
        let content = '';
        
        if (parsed.title) {
            content += `# ${parsed.title}\n\n`;
        }
        
        if (parsed.key_findings && Array.isArray(parsed.key_findings)) {
            content += '## Key Findings\n\n';
            parsed.key_findings.forEach(finding => {
                content += `- ${finding}\n`;
            });
            content += '\n';
        }
        
        if (parsed.core_patterns && Array.isArray(parsed.core_patterns)) {
            content += '## Core Patterns\n\n';
            parsed.core_patterns.forEach(pattern => {
                if (pattern.name) {
                    content += `### ${pattern.name}\n\n`;
                }
                if (pattern.description) {
                    content += `${pattern.description}\n\n`;
                }
                if (pattern.example) {
                    content += `**Example:** ${pattern.example}\n\n`;
                }
            });
        }
        
        if (parsed.implementation_strategies && Array.isArray(parsed.implementation_strategies)) {
            content += '## Implementation Strategies\n\n';
            parsed.implementation_strategies.forEach(strategy => {
                if (strategy.name) {
                    content += `### ${strategy.name}\n\n`;
                }
                if (strategy.description) {
                    content += `${strategy.description}\n\n`;
                }
                if (strategy.example) {
                    content += `**Example:** ${strategy.example}\n\n`;
                }
            });
        }
        
        if (parsed.tool_ecosystem && Array.isArray(parsed.tool_ecosystem)) {
            content += '## Tool Ecosystem\n\n';
            parsed.tool_ecosystem.forEach(tool => {
                if (tool.name) {
                    content += `**${tool.name}**`;
                    if (tool.type) content += ` (${tool.type})`;
                    if (tool.provider) content += ` - ${tool.provider}`;
                    content += '\n';
                    if (tool.capability) {
                        content += `${tool.capability}\n`;
                    }
                    content += '\n';
                }
            });
        }
        
        if (parsed.references && Array.isArray(parsed.references)) {
            content += '## References\n\n';
            parsed.references.forEach((ref, index) => {
                content += `${index + 1}. ${ref}\n`;
            });
        }
        
        return content;
    }

    toPlainText(content) {
        const withoutMd = String(content).replace(/[#*_`~\$\(\)]/g, ' ');
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

    loadPreferences() {
        try {
            const raw = localStorage.getItem('synthesis_manager_prefs');
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
            if (typeof prefs.sub === 'string' || prefs.sub === null) {
                this.currentFilter.sub = prefs.sub;
            }
            if (typeof prefs.search === 'string') {
                this.currentFilter.search = prefs.search;
                if (this.elements.searchInput) {
                    this.elements.searchInput.value = prefs.search;
                }
            }
        } catch {
            // Ignore corrupt prefs
        }
    }

    persistPreferences() {
        try {
            const prefs = {
                viewMode: this.viewMode,
                sortBy: this.currentFilter.sortBy,
                category: this.currentFilter.category,
                sub: this.currentFilter.sub,
                search: this.currentFilter.search
            };
            localStorage.setItem('synthesis_manager_prefs', JSON.stringify(prefs));
        } catch {
            // Ignore storage errors
        }
    }

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
        this.documents.clear();
        this.categoryTree.clear();
        this.selectedDocument = null;
        super.cleanup();
    }
}

console.log('✅ ModernSynthesisManager (Redesigned) defined');

if (typeof window !== 'undefined') {
    window.ModernSynthesisManager = ModernSynthesisManager;
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = ModernSynthesisManager;
}

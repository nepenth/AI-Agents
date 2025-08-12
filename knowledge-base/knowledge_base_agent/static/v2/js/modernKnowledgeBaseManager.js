/**
Modern Knowledge Base Manager (Redesigned)
From first-principles: The core purpose is to provide an intuitive, efficient way to browse and search a nested knowledge base (categories > sub-categories > items), 
inspired by Apple's Human Interface Guidelines emphasizing clarity (legible, understandable UI), deference (content-focused, minimal chrome), depth (layered hierarchy with glass effects for visual separation), 
and consistency (familiar navigation patterns like sidebar tree views in Finder/Notes apps). 
Usability: Sidebar for hierarchical navigation to reduce cognitive load, main area for focused content display, real-time search across all fields (global when active), hover previews for quick glances without disruption, 
modal for immersive detailed views. Modern UI: Glassmorphism ("liquid glass" trend 2025) with blurred, translucent panels for depth and fluidity, subtle animations for delight. 
Engineering: Efficient data structures (Maps for O(1) access), debounced search, lazy rendering, robust error handling via centralized API service.
*/
console.log('🔍 Loading ModernKnowledgeBaseManager (Redesigned)...');
class ModernKnowledgeBaseManager extends BaseManager {
    constructor(options = {}) {
        super({
            enableLogging: true,
            autoInit: false,
            componentName: 'ModernKnowledgeBaseManager',
            ...options
        });

        // Optional external helpers for content rendering and sanitization
        this.markdownRenderer = options.markdownRenderer || null;
        this.htmlSanitizer = options.htmlSanitizer || null;

        // API and media paths
        this.apiBase = options.apiBase || '';
        this.mediaBase = options.mediaBase || '/data/media_cache';

        // Data structures
        this.items = new Map(); // id (string) -> item object
        this.categoryTree = new Map(); // main_category -> Map(sub_category -> array of items)

        // Current state for filtering and sorting
        this.currentFilter = {
            category: 'all',
            sub: null,
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

        // Cache elements
        this.elements.searchInput = document.getElementById('kb-search');
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
        // Suggestion dropdown
        this.elements.suggest = document.getElementById('kb-suggest');

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
                    selector: this.elements.searchInput,
                    events: ['keydown'],
                    handler: this.handleSearchKeydown
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
                    selector: '.kb-item',
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
                    selector: '.kb-item',
                    event: 'mouseenter',
                    handler: this.handleItemHoverIn
                },
                {
                    container: this.elements.itemsList,
                    selector: '.kb-item',
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
            this.showLoadingOverlay('Loading knowledge base items...');
            this.log('Loading initial knowledge base data...');

            await this.loadKnowledgeBaseItems();
            this.buildCategoryTree();
            this.renderSidebar();

            this.applyFilters();

            this.setState({
                initialized: true,
                loading: false
            });

            this.log('Initialization completed successfully');

        } catch (error) {
            this.setError(error, 'loading knowledge base');
            this.showEmptyState('Failed to load knowledge base');
        } finally {
            this.hideLoadingOverlay();
        }
    }

    async createKnowledgeBaseInterface() {
        this.elements.container.innerHTML = `
            <style>
                .modern-kb-container {
                    min-height: 100vh;
                    display: flex;
                    flex-direction: column;
                    padding: 1rem;
                    box-sizing: border-box;
                }
                .kb-header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 1rem;
                }
                .kb-body {
                    display: flex;
                    flex: 1;
                    min-height: 0; /* allow children to size */
                    overflow: hidden;
                }
                .kb-sidebar {
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
                .kb-main {
                    flex: 1;
                    padding: 1rem;
                    display: flex;
                    flex-direction: column;
                    min-height: 0;
                    box-sizing: border-box;
                }
                .kb-controls {
                    display: flex;
                    align-items: center;
                    margin-bottom: 1rem;
                }
                .search-container {
                    flex: 1;
                    margin-right: 1rem;
                    position: relative;
                }
                /* suggestions */
                .suggest-panel { position:absolute; top: 110%; left:0; right:0; background: rgba(20,25,40,0.98); border:1px solid rgba(255,255,255,0.12); border-radius:10px; box-shadow: 0 12px 30px rgba(0,0,0,0.35); z-index: 50; max-height: 50vh; overflow:auto; }
                .suggest-item { padding:10px 12px; cursor:pointer; display:flex; align-items:center; gap:10px; }
                .suggest-item i { color:#60a5fa; }
                .suggest-item.active, .suggest-item:hover { background: rgba(255,255,255,0.06); }
                .kb-stats {
                    display: flex;
                    gap: 1rem;
                    margin-bottom: 1rem;
                }
                .items-list {
                    display: grid;
                    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
                    gap: 1rem;
                    flex: 1;
                    overflow: auto;
                }
                .items-list.list-view {
                    display: flex;
                    flex-direction: column;
                }
                .items-list.list-view .kb-item {
                    width: 100%;
                }
                .kb-item {
                    cursor: pointer;
                    padding: 1rem;
                    border-radius: 8px;
                    background: rgba(255,255,255,0.05);
                    backdrop-filter: blur(10px);
                    border: 1px solid rgba(255,255,255,0.1);
                    transition: transform 0.2s;
                }
                .kb-item:hover {
                    transform: translateY(-2px);
                }
                .hidden { display: none; }
                /* Modal: scrolling and fullscreen support */
                .modal-overlay {
                    position: fixed;
                    inset: 0;
                    background: rgba(0, 0, 0, 0.6);
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    z-index: 1000;
                    overflow: auto;
                }
                .modal-container {
                    width: 70vw;
                    max-width: 1600px;
                    max-height: 90vh;
                    overflow: auto;
                    display: flex;
                    flex-direction: column;
                    border-radius: 12px;
                }
                .modal-container.fullscreen {
                    width: 98vw;
                    height: 96vh;
                    max-height: 96vh;
                }
                .modal-header {
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    padding: 1rem;
                    border-bottom: 1px solid rgba(255,255,255,0.1);
                    position: sticky;
                    top: 0;
                    background: inherit;
                    z-index: 2;
                }
                .modal-metadata { display: flex; gap: 1rem; flex-wrap: wrap; padding: 0 1rem 1rem 1rem; }
                .modal-content-section { padding: 0 1rem 1rem 1rem; display: flex; flex-direction: column; min-height: 0; }
                .modal-content-section .modal-content { overflow-y: auto; max-height: calc(90vh - 160px); width: 100%; max-width: none; }
                .modal-content-section .modal-content pre { white-space: pre-wrap; word-wrap: break-word; }
                .modal-container.fullscreen .modal-content-section .modal-content { max-height: calc(96vh - 160px); }
            </style>
            <div class="modern-kb-container glass-panel-v3 animate-fade-in">
                <header class="kb-header">
                    <div class="header-title">
                        <h1><i class="fas fa-book-open"></i> Knowledge Base</h1>
                        <p class="header-subtitle">Discover and explore your curated insights</p>
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

                <div class="kb-body">
                    <aside id="kb-sidebar" class="kb-sidebar glass-panel-v3">
                        <ul id="category-tree" class="category-tree-list"></ul>
                    </aside>

                    <section class="kb-main">
                        <h2 id="current-view-title" class="view-title">All Knowledge Base</h2>

                        <div class="kb-controls">
                            <div class="search-container">
                                <i class="fas fa-search"></i>
                                <input type="text" id="kb-search" placeholder="Search by title, content, category..." class="glass-input">
                                <div id="kb-suggest" class="suggest-panel hidden"></div>
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

                        <div class="kb-stats">
                            <div class="stat-item">
                                <span class="stat-label">Total Items</span>
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

                        <div id="kb-main-content">
                            <div id="loading-state" class="loading-state">
                                <div class="loading-spinner"></div>
                                <span>Loading items...</span>
                            </div>

                            <div id="empty-state" class="empty-state hidden">
                                <i class="fas fa-book-open"></i>
                                <h3>No items found</h3>
                                <p>Try adjusting your search or select a different category</p>
                            </div>

                            <div id="items-list" class="items-list grid-view"></div>
                        </div>
                    </section>
                </div>
            </div>
        `;
    }

    async loadKnowledgeBaseItems() {
        this.items.clear();

        const response = await this.apiCall(`/items`, {
            errorMessage: 'Failed to load items',
            cache: false,
            showLoading: false
        });

        if (Array.isArray(response)) {
            response.forEach(item => {
                const id = String(item.id);

                // Normalize dates
                item._updatedAtMs = this.parseDateToMs(item.last_updated || item.created_at);
                item._createdAtMs = this.parseDateToMs(item.created_at);

                // Normalize media (safe JSON parse)
                try {
                    if (!Array.isArray(item.kb_media_paths)) {
                        item.kb_media_paths = typeof item.kb_media_paths === 'string' ? JSON.parse(item.kb_media_paths) : (item.kb_media_paths || []);
                    }
                } catch { item.kb_media_paths = []; }
                try {
                    if (!Array.isArray(item.media_files)) {
                        item.media_files = typeof item.media_files === 'string' ? JSON.parse(item.media_files) : (item.media_files || []);
                    }
                } catch { item.media_files = []; }
                item.all_media_files = [...item.kb_media_paths, ...item.media_files];

                // Fallback content
                item.content = item.content || item.markdown_content || item.kb_content || item.full_text || item.description || '';

                this.items.set(id, item);
            });
            this.log(`Loaded ${response.length} knowledge base items`);
        } else {
            this.logWarn('Non-array response from API');
        }
    }

    buildCategoryTree() {
        this.categoryTree.clear();

        this.items.forEach(item => {
            const main = item.main_category || 'Uncategorized';
            const sub = item.sub_category || 'General';

            if (!this.categoryTree.has(main)) {
                this.categoryTree.set(main, new Map());
            }

            const subMap = this.categoryTree.get(main);
            if (!subMap.has(sub)) {
                subMap.set(sub, []);
            }

            subMap.get(sub).push(item);
        });
    }

    renderSidebar() {
        if (!this.elements.categoryTree) return;

        let html = `
            <li class="all-categories" data-category="all">
                <div class="category-header all-header">
                    <i class="fas fa-book-open"></i>
                    <span>All Knowledge Base</span>
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
        let viewItems = [];

        if (this.currentFilter.search) {
            // Global search
            const term = this.currentFilter.search.toLowerCase();
            viewItems = Array.from(this.items.values()).filter(item => 
                (item.title || '').toLowerCase().includes(term) ||
                (item.content || '').toLowerCase().includes(term) ||
                (item.main_category || '').toLowerCase().includes(term) ||
                (item.sub_category || '').toLowerCase().includes(term) ||
                (item.tweet_id ? String(item.tweet_id).includes(term) : false)
            );
        } else {
            // Category/sub based
            if (this.currentFilter.category === 'all') {
                this.items.forEach(item => viewItems.push(item));
            } else {
                const subMap = this.categoryTree.get(this.currentFilter.category);
                if (subMap) {
                    if (this.currentFilter.sub) {
                        viewItems = subMap.get(this.currentFilter.sub) || [];
                    } else {
                        subMap.forEach(items => viewItems.push(...items));
                    }
                }
            }
        }

        // Apply sorting
        const [sortBy, sortDir] = this.currentFilter.sortBy.split('-');
        viewItems.sort((a, b) => {
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
        this.renderItems(viewItems);

        // Update UI
        this.updateViewTitle();
        this.updateStats(viewItems.length);
        this.persistPreferences();
    }

    renderItems(items) {
        if (!this.elements.itemsList) return;

        if (items.length === 0) {
            this.showEmptyState();
            return;
        }

        this.hideLoadingState();
        this.hideEmptyState();

        let html = '';
        items.forEach(item => {
            html += this.createItemHTML(item);
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
            title = 'All Knowledge Base';
        }
        this.elements.currentViewTitle.textContent = title;
    }

    createItemHTML(item) {
        const title = this.escapeHTML(this.getDisplayTitle(item));
        const category = this.escapeHTML(item.main_category || 'Uncategorized');
        const sub = this.escapeHTML(item.sub_category || '');
        const lastUpdated = this.formatRelativeDate(item.last_updated || item.created_at);
        const shortPreview = this.createPreview(item.content || '', 200);
        const hoverPreview = this.createPreview(item.content || '', 800);
        const id = this.escapeAttr(String(item.id));
        const sourceLink = item.source_url ? `<span class="source-link"><i class="fas fa-external-link-alt"></i> Source</span>` : '';

        return `
            <div class="kb-item glass-panel-v3--interactive" data-item-id="${id}" data-item-type="kb_item">
                <div class="item-header">
                    <div class="item-type">
                        <i class="fas fa-file-alt"></i>
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
                    <span class="last-updated">Updated ${lastUpdated}</span>
                    ${sourceLink}
                </div>

                <div class="item-hover-preview glass-panel-v3 hidden">
                    ${hoverPreview}
                </div>
            </div>
        `;
    }

    updateStats(showing) {
        if (this.elements.itemsCount) {
            this.elements.itemsCount.textContent = this.items.size;
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
                p.textContent = this.currentFilter.search ? `No results for "${this.escapeHTML(this.currentFilter.search)}"` : 'No items in this category';
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

    async handleSearch(e) {
        const term = (e.target.value || '').trim();
        this.currentFilter.search = term;
        if (!term) {
            this.applyFilters();
            this.hideSuggestions();
            return;
        }
        // Remote FTS-backed search
        try {
            this.showLoadingState();
            const res = await this.apiCall(`/search?q=${encodeURIComponent(term)}&type=kb&limit=50`, {
                errorMessage: 'Search failed',
                cache: false,
                showLoading: false
            });
            const results = (res && res.results) ? res.results : [];
            const top = results.slice(0, 10);
            this.showSuggestions(top);
            // Ensure we have items for these IDs
            const items = [];
            for (const r of top) {
                const id = String(r.id);
                let item = this.items.get(id);
                if (!item) {
                    try {
                        const full = await this.apiCall(`/items/${id}`, { errorMessage: `Failed to fetch item ${id}`, cache: false, showLoading: false });
                        if (full) {
                            this.items.set(id, full);
                            item = full;
                        }
                    } catch (_) { /* ignore individual fetch errors */ }
                }
                if (item) {
                    items.push({ ...item, _snippet: r.snippet || '' });
                }
            }
            // Render search results with snippets
            this.renderItemsWithSnippets(items);
            this.updateViewTitle();
            this.updateStats(items.length);
        } catch (err) {
            this.logWarn('Remote search failed, falling back to client filter', err);
            this.applyFilters();
        }
    }

    handleSearchKeydown = (e) => {
        if (!this.elements.suggest || this.elements.suggest.classList.contains('hidden')) return;
        const items = Array.from(this.elements.suggest.querySelectorAll('.suggest-item'));
        if (items.length === 0) return;
        const activeIdx = items.findIndex(el => el.classList.contains('active'));
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            const next = activeIdx < 0 ? 0 : Math.min(items.length - 1, activeIdx + 1);
            items.forEach(el => el.classList.remove('active'));
            items[next].classList.add('active');
            items[next].scrollIntoView({ block: 'nearest' });
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            const prev = activeIdx <= 0 ? 0 : activeIdx - 1;
            items.forEach(el => el.classList.remove('active'));
            items[prev].classList.add('active');
            items[prev].scrollIntoView({ block: 'nearest' });
        } else if (e.key === 'Enter') {
            if (activeIdx >= 0) {
                e.preventDefault();
                items[activeIdx].click();
            }
        } else if (e.key === 'Escape') {
            this.hideSuggestions();
        }
    }

    showSuggestions(results) {
        if (!this.elements.suggest) return;
        if (!results || results.length === 0) { this.hideSuggestions(); return; }
        const html = results.map((r, i) => `
            <div class="suggest-item ${i===0?'active':''}" data-id="${this.escapeAttr(String(r.id))}">
                <i class="fas fa-file-alt"></i>
                <div class="suggest-text">
                    <div class="suggest-title">${this.escapeHTML(r.title || 'Untitled')}</div>
                </div>
            </div>
        `).join('');
        this.elements.suggest.innerHTML = html;
        this.elements.suggest.classList.remove('hidden');
        // Click handlers
        this.elements.suggest.querySelectorAll('.suggest-item').forEach(el => {
            el.addEventListener('mousedown', (ev) => {
                ev.preventDefault();
                const id = el.getAttribute('data-id');
                if (id) this.viewItem(id);
                this.hideSuggestions();
            });
        });
    }

    hideSuggestions() {
        if (this.elements.suggest) {
            this.elements.suggest.classList.add('hidden');
            this.elements.suggest.innerHTML = '';
        }
    }

    renderItemsWithSnippets(items) {
        if (!this.elements.itemsList) return;
        if (!Array.isArray(items) || items.length === 0) {
            this.showEmptyState();
            return;
        }
        this.hideLoadingState();
        this.hideEmptyState();
        const html = items.map(item => {
            const base = this.createItemHTML(item);
            if (!item._snippet) return base;
            // Inject snippet below preview
            return base.replace(
                /<div class=\"item-preview\">[\s\S]*?<\/div>/,
                match => `${match}\n<div class=\"item-snippet\">${item._snippet}</div>`
            );
        }).join('');
        this.elements.itemsList.innerHTML = html;
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
            this.log('Refreshing knowledge base...');
            await this.loadInitialData();
        } catch (error) {
            this.setError(error, 'refreshing knowledge base');
        }
    }

    handleExportAll = () => {
        try {
            const allItems = Array.from(this.items.values());
            const content = this.formatItemsForExport(allItems);
            const filename = `knowledge_base_export_${new Date().toISOString().split('T')[0]}.md`;
            this.downloadFile(content, filename, 'text/markdown');
            this.log(`Exported ${allItems.length} items`);
        } catch (error) {
            this.setError(error, 'exporting all items');
        }
    }

    handleItemClick = (e) => {
        if (e.target.closest('.item-action-btn')) return;
        const itemEl = e.target.closest('.kb-item');
        if (!itemEl) return;
        const id = itemEl.dataset.itemId;
        this.viewItem(id);
    }

    handleItemAction = (e) => {
        e.stopPropagation();
        const btn = e.target.closest('.item-action-btn');
        if (!btn) return;
        const action = btn.dataset.action;
        const itemEl = btn.closest('.kb-item');
        if (!itemEl) return;
        const id = itemEl.dataset.itemId;

        if (action === 'view') {
            this.viewItem(id);
        } else if (action === 'export') {
            this.exportItem(id);
        }
    }

    handleItemHoverIn = (e) => {
        const item = e.target.closest('.kb-item');
        if (!item) return;
        const preview = item.querySelector('.item-hover-preview');
        if (preview) {
            preview.classList.remove('hidden');
        }
    }

    handleItemHoverOut = (e) => {
        const item = e.target.closest('.kb-item');
        if (!item) return;
        const preview = item.querySelector('.item-hover-preview');
        if (preview) {
            preview.classList.add('hidden');
        }
    }

    handleEscape = () => {
        this.closeModal();
    }

    async viewItem(id) {
        // Show a lightweight loading overlay while fetching full item
        this.showLoadingOverlay();
        let item = this.items.get(String(id));
        try {
            // Always fetch the full item to ensure complete content/media
            const full = await this.apiCall(`/items/${id}`, {
                errorMessage: `Failed to load knowledge base item ${id}`,
                cache: false,
                showLoading: false
            });
            if (full) {
                // Merge and normalize
                item = { ...(item || {}), ...full };
                // Ensure media arrays
                try { if (!Array.isArray(item.kb_media_paths)) item.kb_media_paths = item.kb_media_paths ? JSON.parse(item.kb_media_paths) : []; } catch { item.kb_media_paths = []; }
                try { if (!Array.isArray(item.media_files)) item.media_files = item.media_files ? JSON.parse(item.media_files) : []; } catch { item.media_files = []; }
                item.all_media_files = [...(item.kb_media_paths || []), ...(item.media_files || [])];
                // Content fallback
                item.content = item.content || item.markdown_content || item.kb_content || item.full_text || item.description || '';
                this.items.set(String(id), item);
            }
        } catch (error) {
            this.logWarn(`Falling back to cached item ${id} due to fetch error`, error);
        } finally { this.hideLoadingOverlay(); }
        if (item) {
            this.selectedItem = item;
            this.createAndShowModal(item);
        } else {
            this.logError(`Item ${id} not found`);
        }
    }

    showLoadingOverlay(message = 'Loading...') {
        if (document.getElementById('kb-loading-overlay')) return;
        const overlay = document.createElement('div');
        overlay.id = 'kb-loading-overlay';
        overlay.style.cssText = `position:fixed;inset:0;z-index:1500;display:flex;align-items:center;justify-content:center;background:rgba(0,0,0,0.35)`;
        overlay.innerHTML = `
            <div style="width:420px;max-width:90vw;background:rgba(20,25,40,0.9);border:1px solid rgba(255,255,255,0.15);border-radius:12px;padding:16px 18px;box-shadow:0 12px 30px rgba(0,0,0,0.4)">
                <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;color:#cbd5e1;font-weight:600">
                    <span>${this.escapeHTML(message)}</span>
                    <span id="kb-loading-progress" style="font-size:12px;color:#94a3b8">preparing…</span>
                </div>
                <div style="position:relative;height:8px;background:rgba(255,255,255,0.08);border-radius:6px;overflow:hidden">
                    <div id="kb-loading-bar" style="position:absolute;left:0;top:0;height:100%;width:20%;background:linear-gradient(90deg,#3b82f6,#06b6d4);animation:kbbar 1.4s ease-in-out infinite"></div>
                </div>
            </div>
            <style>@keyframes kbbar{0%{left:-20%}50%{left:50%}100%{left:100%}}</style>
        `;
        document.body.appendChild(overlay);
    }
    hideLoadingOverlay() {
        const el = document.getElementById('kb-loading-overlay');
        if (el) el.remove();
    }

    createAndShowModal(item) {
        const existingModal = document.getElementById('kb-item-modal');
        if (existingModal) {
            existingModal.remove();
        }

        const title = this.escapeHTML(this.getDisplayTitle(item));
        const category = this.escapeHTML(item.main_category || 'Uncategorized');
        const subCategory = this.escapeHTML(item.sub_category || '');
        const content = item.content_html || item.content || item.markdown_content || 'No content available';
        const lastUpdated = new Date(this.parseDateToMs(item.last_updated || item.created_at)).toLocaleString();
        const sourceUrl = item.source_url;

        const mediaFiles = item.all_media_files;

        const mediaGridHTML = mediaFiles.length > 0 ? `
            <div class="modal-media-section">
                <h3><i class="fas fa-images"></i> Media Files</h3>
                <div class="media-grid">
                    ${mediaFiles.map(path => `
                        <div class="media-item">
                            <img src="${this.mediaUrl(path)}" alt="Media" onclick="this.classList.toggle('expanded')" title="Click to expand" loading="lazy">
                        </div>
                    `).join('')}
                </div>
            </div>
        ` : '';

        const modalHTML = `
            <div id="kb-item-modal" class="modal-overlay">
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
                            <button id="kb-modal-scrolltop-btn" class="glass-button glass-button--small" title="Scroll to top">
                                <i class="fas fa-arrow-up"></i>
                            </button>
                            <button id="kb-modal-fullscreen-btn" class="glass-button glass-button--small" title="Toggle Fullscreen">
                                <i class="fas fa-expand"></i>
                            </button>
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
                    handler: () => this.exportItem(String(item.id))
                },
                {
                    selector: '#modal-source-btn',
                    handler: () => {
                        if (item.source_url) {
                            window.open(item.source_url, '_blank', 'noopener,noreferrer');
                        }
                    },
                    condition: () => !!item.source_url
                },
                {
                    selector: '#kb-modal-fullscreen-btn',
                    handler: () => {
                        const container = document.querySelector('#kb-item-modal .modal-container');
                        if (container) {
                            container.classList.toggle('fullscreen');
                            const icon = document.querySelector('#kb-modal-fullscreen-btn i');
                            if (icon) {
                                icon.classList.toggle('fa-expand');
                                icon.classList.toggle('fa-compress');
                            }
                        }
                    }
                },
                {
                    selector: '#kb-modal-scrolltop-btn',
                    handler: () => {
                        const content = document.querySelector('#kb-item-modal .modal-content');
                        if (content) content.scrollTo({ top: 0, behavior: 'smooth' });
                    }
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

        // Use shared content renderer if available
        if (window.ContentRenderer) {
            html = window.ContentRenderer.renderAndSanitize(text);
        } else if (this.markdownRenderer) {
            try { html = this.markdownRenderer(text); } catch { html = this.escapeHTML(text).replace(/\n/g, '<br>'); }
        } else {
            const escaped = this.escapeHTML(text);
            html = `<p>${escaped.replace(/\n\n/g, '</p><p>').replace(/\n/g, '<br>')}</p>`;
        }

        return html;
    }

    exportItem(id) {
        const item = this.items.get(String(id));
        if (!item) {
            this.logError(`Item ${id} not found for export`);
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
            this.logError('Failed to download file', error);
            throw error;
        }
    }

    mediaUrl(path) {
        const pathStr = String(path);
        if (pathStr.startsWith('data/media_cache/')) {
            return `/${pathStr}`;
        } else {
            const safe = pathStr.split('/').map(encodeURIComponent).join('/');
            return `/api/media/${safe}`;
        }
    }

    getDisplayTitle(item) {
        let candidate = item.display_title || item.title || item.item_name || 'Untitled';
        if (candidate.includes('-') && !candidate.includes(' ') && item.content) {
            candidate = item.content.split('\n')[0].substring(0, 60);
        }
        return candidate;
    }

    createPreview(content, maxLength) {
        if (!content) return 'No content available';
        const plainText = this.toPlainText(content).trim();
        return plainText.length > maxLength
            ? this.escapeHTML(plainText.substring(0, maxLength)) + '...'
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
            localStorage.setItem('kb_manager_prefs', JSON.stringify(prefs));
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
        this.items.clear();
        this.categoryTree.clear();
        this.selectedItem = null;
        super.cleanup();
    }
}

console.log('✅ ModernKnowledgeBaseManager (Redesigned) defined');

if (typeof window !== 'undefined') {
    window.ModernKnowledgeBaseManager = ModernKnowledgeBaseManager;
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = ModernKnowledgeBaseManager;
}

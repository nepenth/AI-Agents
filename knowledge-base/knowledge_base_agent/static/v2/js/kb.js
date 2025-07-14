/* V2 KB.JS - MODERN KNOWLEDGE BASE INTERFACE */

class KnowledgeBaseManager {
    constructor(api) {
        this.api = api;
        this.data = {
            items: [],
            syntheses: [],
            categories: new Map(),
            tree: new Map()
        };
        this.currentView = 'overview';
        this.currentCategory = null;
        this.currentSubcategory = null;
        this.currentItem = null;
        this.searchQuery = '';
        this.expandedCategories = new Set();
        
        // DOM elements - will be set after initialization
        this.elements = {};
        
        console.log('📚 KnowledgeBaseManager constructor called');
    }

    async initialize() {
        console.log('📚 KnowledgeBaseManager.initialize() called');
        
        try {
            // Load KB page content
            await this.loadPageContent();
            
            // Initialize DOM references
            this.initializeDOMReferences();
            
            // Set up all event listeners
            this.setupEventListeners();
            
            // Load knowledge base data
            await this.loadKnowledgeBaseData();
            
            // Build and render the tree
            this.buildCategoryTree();
            this.renderTree();
            
            // Show overview by default
            this.showOverview();
            
            console.log('✅ KnowledgeBaseManager initialized successfully');
        } catch (error) {
            console.error('❌ KnowledgeBaseManager initialization failed:', error);
            this.showError('Failed to initialize knowledge base interface');
        }
    }

    async loadPageContent() {
        const mainContent = document.getElementById('main-content');
        if (!mainContent) {
            throw new Error('Main content container not found');
        }

        const response = await fetch('/v2/page/kb');
        if (!response.ok) {
            throw new Error(`Failed to load KB content: ${response.status}`);
        }

        const html = await response.text();
        mainContent.innerHTML = html;
        console.log('📚 KB content loaded');
    }

    initializeDOMReferences() {
        const elements = {
            // Tree and navigation - matching synthesis structure
            tree: 'synthesis-tree-container',
            filter: 'v2-synthesis-search',
            clearSearch: 'kb-clear-search',
            expandAll: 'synthesis-expand-all',
            collapseAll: 'synthesis-collapse-all',
            
            // Header and breadcrumbs - matching synthesis structure
            homeBtn: 'synthesis-home-breadcrumb',
            breadcrumbTrail: 'synthesis-breadcrumb-trail',
            viewToggle: 'synthesis-view-mode',
            refreshBtn: 'synthesis-refresh-data',
            exportBtn: 'synthesis-export-all',
            
            // Statistics - matching synthesis structure
            totalCount: 'synthesis-total-docs',
            categoriesCount: 'synthesis-categories',
            subcategoriesCount: 'synthesis-items-analyzed',
            itemsCount: 'synthesis-last-generated',
            
            // Views - matching synthesis structure
            overview: 'synthesis-overview-view',
            categoryView: 'synthesis-category-view',
            itemDetail: 'synthesis-document-view',
            searchResults: 'synthesis-search-view',
            
            // Overview elements - matching synthesis structure
            overviewCategories: 'overview-synthesis-total',
            overviewSubcategories: 'overview-synthesis-categories',
            overviewItems: 'overview-items-synthesized',
            overviewSyntheses: 'overview-recent-count',
            recentItems: 'recent-items',
            
            // Category view elements - matching synthesis structure
            categoryTitle: 'synthesis-category-title',
            categoryDescription: 'synthesis-category-description',
            categoryLastUpdated: 'synthesis-category-updated',
            categoryItemCount: 'synthesis-category-docs',
            subcategoriesGrid: 'subcategories-grid',
            itemsContainer: 'synthesis-category-content',
            itemsSort: 'items-sort',
            itemsGridView: 'items-grid-view',
            itemsListView: 'items-list-view',
            
            // Item detail elements - matching synthesis structure
            itemCategory: 'item-category',
            itemSubcategory: 'item-subcategory',
            itemTitle: 'item-title',
            itemCreated: 'item-created',
            itemContent: 'synthesis-document-content',
            
            // Modal elements - matching synthesis structure
            modal: 'synthesis-document-modal',
            modalTitle: 'modal-document-title',
            modalContent: 'modal-document-content',
            modalCloseBtn: 'close-document-modal',
            modalExportBtn: 'modal-export-doc',
            
            // Search elements - matching synthesis structure
            searchResultsContent: 'synthesis-search-results-content',
            searchResultsCount: 'synthesis-search-results-count',
            searchSuggestions: 'synthesis-search-suggestions'
        };

        // Convert element IDs to actual DOM elements
        this.elements = {};
        for (const [key, id] of Object.entries(elements)) {
            this.elements[key] = document.getElementById(id);
            if (!this.elements[key]) {
                console.warn(`⚠️ Element not found: ${id}`);
            }
        }

        console.log('📚 DOM references initialized:', this.elements);
    }

    setupEventListeners() {
        // Search functionality
        this.elements.filter.addEventListener('input', (e) => {
            this.handleSearch(e.target.value);
        });

        if (this.elements.clearSearch) {
            this.elements.clearSearch.addEventListener('click', () => {
                this.clearSearch();
            });
        }

        // Tree controls
        if (this.elements.expandAll) {
            this.elements.expandAll.addEventListener('click', () => {
                this.expandAllCategories();
            });
        }

        if (this.elements.collapseAll) {
            this.elements.collapseAll.addEventListener('click', () => {
                this.collapseAllCategories();
            });
        }

        // Header actions
        if (this.elements.homeBtn) {
            this.elements.homeBtn.addEventListener('click', () => {
                this.showOverview();
            });
        }

        if (this.elements.refreshBtn) {
            this.elements.refreshBtn.addEventListener('click', () => {
                this.refresh();
            });
        }

        if (this.elements.exportBtn) {
            this.elements.exportBtn.addEventListener('click', () => {
                this.exportKnowledgeBase();
            });
        }

        // Tree navigation
        this.elements.tree.addEventListener('click', (e) => {
            this.handleTreeClick(e);
        });

        // View controls
        if (this.elements.itemsGridView) {
            this.elements.itemsGridView.addEventListener('click', () => {
                this.setItemsViewMode('grid');
            });
        }

        if (this.elements.itemsListView) {
            this.elements.itemsListView.addEventListener('click', () => {
                this.setItemsViewMode('list');
            });
        }

        // Sort controls
        if (this.elements.itemsSort) {
            this.elements.itemsSort.addEventListener('change', (e) => {
                this.sortItems(e.target.value);
            });
        }
    }

    async loadKnowledgeBaseData() {
        try {
            const response = await fetch('/api/kb/all');
            if (!response.ok) {
                throw new Error(`Failed to fetch KB data: ${response.status}`);
            }

            const data = await response.json();
            this.data.items = data.items || [];
            this.data.syntheses = data.syntheses || [];
            
            console.log(`📚 Loaded ${this.data.items.length} items and ${this.data.syntheses.length} syntheses`);
        } catch (error) {
            console.error('Error loading KB data:', error);
            throw error;
        }
    }

    buildCategoryTree() {
        // Simple method since we're now using direct item rendering
        console.log('📚 Building Knowledge Base tree structure...');
        console.log(`📊 Found ${this.data.items.length} items and ${this.data.syntheses.length} syntheses`);
        this.updateStatistics();
    }

    renderTree() {
        const treeContainer = this.elements.tree;
        if (!treeContainer) {
            console.warn('Tree container not found');
            return;
        }

        if (this.data.items.length === 0) {
            treeContainer.innerHTML = `
                <div class="placeholder-state">
                    <div class="placeholder-icon">
                        <i class="fas fa-folder-open"></i>
                    </div>
                    <h3 class="placeholder-title">No Knowledge Base Items</h3>
                    <p class="placeholder-description">
                        No knowledge base items found. Run the agent to populate your knowledge base.
                    </p>
                    <div class="placeholder-actions">
                        <button class="glass-button glass-button--primary" onclick="window.router.navigate('dashboard')">
                            <i class="fas fa-robot"></i>
                            <span>Go to Agent Dashboard</span>
                        </button>
                        <button class="glass-button glass-button--secondary" onclick="this.refresh()">
                            <i class="fas fa-sync-alt"></i>
                            <span>Refresh</span>
                        </button>
                    </div>
                </div>
            `;
            return;
        }

        // Group items by category
        const categorizedItems = {};
        this.data.items.forEach(item => {
            const category = item.main_category || 'Uncategorized';
            if (!categorizedItems[category]) {
                categorizedItems[category] = [];
            }
            categorizedItems[category].push(item);
        });

        // Sort categories and items
        const sortedCategories = Object.keys(categorizedItems).sort();
        
        let treeHTML = '<div class="synthesis-tree">';
        
        sortedCategories.forEach(category => {
            const items = categorizedItems[category].sort((a, b) => 
                new Date(b.last_updated || b.created_at) - new Date(a.last_updated || a.created_at)
            );
            
            const categoryId = `kb-category-${category.replace(/[^a-zA-Z0-9]/g, '-')}`;
            
            treeHTML += `
                <div class="tree-category" data-category="${category}">
                    <div class="category-header" data-category="${category}">
                        <i class="fas fa-chevron-right category-toggle"></i>
                        <i class="fas fa-folder category-icon"></i>
                        <span class="category-name">${this.escapeHtml(category)}</span>
                        <span class="category-count">(${items.length})</span>
                    </div>
                    <div class="subcategory-list" style="display: none;">
            `;
            
            items.forEach(item => {
                const lastUpdated = new Date(item.last_updated || item.created_at);
                const relativeTime = this.getRelativeTime(lastUpdated);
                
                treeHTML += `
                    <div class="tree-item synthesis-item" data-item-id="${item.id}" data-item-type="item">
                        <i class="fas fa-file-text item-icon"></i>
                        <div class="item-content">
                            <div class="item-title">${this.escapeHtml(item.display_title || item.title || 'Untitled')}</div>
                            <div class="item-meta">
                                <span class="item-category">${this.escapeHtml(item.sub_category || 'General')}</span>
                                <span class="item-updated">${relativeTime}</span>
                            </div>
                        </div>
                        <div class="item-actions">
                            <button class="item-action-btn" onclick="event.stopPropagation(); window.KnowledgeBaseManager.showItemDetail(${item.id}, 'item')" title="View">
                                <i class="fas fa-eye"></i>
                            </button>
                            <button class="item-action-btn" onclick="event.stopPropagation(); window.KnowledgeBaseManager.exportItem(${item.id})" title="Export">
                                <i class="fas fa-download"></i>
                            </button>
                        </div>
                    </div>
                `;
            });
            
            treeHTML += `
                    </div>
                </div>
            `;
        });
        
        treeHTML += '</div>';
        
        treeContainer.innerHTML = treeHTML;
        
        // Add click handlers for categories
        treeContainer.querySelectorAll('.category-header').forEach(header => {
            header.addEventListener('click', (e) => {
                e.preventDefault();
                this.toggleCategory(header);
            });
        });

        // Add click handlers for items
        treeContainer.querySelectorAll('.synthesis-item').forEach(item => {
            item.addEventListener('click', (e) => {
                if (!e.target.closest('.item-action-btn')) {
                    const itemId = item.getAttribute('data-item-id');
                    const itemType = item.getAttribute('data-item-type');
                    this.showItemDetail(itemId, itemType);
                }
            });
        });
    }

    handleTreeClick(e) {
        const target = e.target.closest('[data-category], [data-item-id]');
        if (!target) return;

        e.preventDefault();
        e.stopPropagation();

        if (target.hasAttribute('data-item-id')) {
            // Item clicked
            const itemId = target.getAttribute('data-item-id');
            const itemType = target.getAttribute('data-item-type');
            this.showItemDetail(itemId, itemType);
        } else if (target.hasAttribute('data-subcategory')) {
            // Subcategory clicked
            const category = target.getAttribute('data-category');
            const subcategory = target.getAttribute('data-subcategory');
            this.showCategory(category, subcategory);
        } else if (target.hasAttribute('data-category')) {
            // Category header clicked
            const category = target.getAttribute('data-category');
            
            if (target.classList.contains('tree-category-header')) {
                // Toggle expand/collapse
                this.toggleCategory(category);
            }
        }
    }

    toggleCategory(header) {
        const category = header.closest('.tree-category');
        const subcategoryList = category.querySelector('.subcategory-list');
        const toggle = header.querySelector('.category-toggle');
        
        if (subcategoryList.style.display === 'none') {
            subcategoryList.style.display = 'block';
            toggle.style.transform = 'rotate(90deg)';
            header.classList.add('expanded');
        } else {
            subcategoryList.style.display = 'none';
            toggle.style.transform = 'rotate(0deg)';
            header.classList.remove('expanded');
        }
    }

    expandAllCategories() {
        if (this.elements.tree) {
            const categories = this.elements.tree.querySelectorAll('.tree-category');
            categories.forEach(category => {
                const header = category.querySelector('.category-header');
                const subcategoryList = category.querySelector('.subcategory-list');
                const toggle = header.querySelector('.category-toggle');
                
                if (subcategoryList && subcategoryList.style.display === 'none') {
                    subcategoryList.style.display = 'block';
                    toggle.style.transform = 'rotate(90deg)';
                    header.classList.add('expanded');
                }
            });
        }
        console.log('📂 Expanded all categories');
    }

    collapseAllCategories() {
        if (this.elements.tree) {
            const categories = this.elements.tree.querySelectorAll('.tree-category');
            categories.forEach(category => {
                const header = category.querySelector('.category-header');
                const subcategoryList = category.querySelector('.subcategory-list');
                const toggle = header.querySelector('.category-toggle');
                
                if (subcategoryList && subcategoryList.style.display !== 'none') {
                    subcategoryList.style.display = 'none';
                    toggle.style.transform = 'rotate(0deg)';
                    header.classList.remove('expanded');
                }
            });
        }
        console.log('📁 Collapsed all categories');
    }

    handleSearch(query) {
        this.searchQuery = query.trim();
        
        if (this.searchQuery) {
            this.elements.clearSearch?.classList.remove('hidden');
            this.showSearchResults(this.searchQuery);
        } else {
            this.elements.clearSearch?.classList.add('hidden');
            this.showOverview();
        }
    }

    clearSearch() {
        this.elements.filter.value = '';
        this.searchQuery = '';
        this.elements.clearSearch?.classList.add('hidden');
        this.showOverview();
    }

    showSearchResults(query) {
        this.currentView = 'search';
        this.hideAllViews();
        this.elements.searchResults?.classList.add('active');

        // Update search header
        if (this.elements.searchQuery) {
            this.elements.searchQuery.textContent = `"${query}"`;
        }

        // Perform search
        const results = this.performSearch(query);
        
        if (this.elements.searchCount) {
            this.elements.searchCount.textContent = `${results.length} results`;
        }

        this.renderSearchResults(results);
    }

    performSearch(query) {
        const lowerQuery = query.toLowerCase();
        const results = [];

        // Search items
        this.data.items.forEach(item => {
            const searchableText = [
                item.title,
                item.display_title,
                item.description,
                item.main_category,
                item.sub_category
            ].join(' ').toLowerCase();

            if (searchableText.includes(lowerQuery)) {
                results.push({
                    type: 'item',
                    data: item,
                    relevance: this.calculateRelevance(searchableText, lowerQuery)
                });
            }
        });

        // Search syntheses
        this.data.syntheses.forEach(synthesis => {
            const searchableText = [
                synthesis.synthesis_title,
                synthesis.main_category,
                synthesis.sub_category
            ].join(' ').toLowerCase();

            if (searchableText.includes(lowerQuery)) {
                results.push({
                    type: 'synthesis',
                    data: synthesis,
                    relevance: this.calculateRelevance(searchableText, lowerQuery)
                });
            }
        });

        // Sort by relevance
        results.sort((a, b) => b.relevance - a.relevance);

        return results;
    }

    calculateRelevance(text, query) {
        const titleMatch = text.includes(query) ? 2 : 0;
        const wordCount = text.split(' ').length;
        const queryLength = query.length;
        
        return titleMatch + (queryLength / wordCount);
    }

    renderSearchResults(results) {
        const container = this.elements.searchResultsContent;
        if (!container) return;

        if (results.length === 0) {
            container.innerHTML = `
                <div class="search-no-results">
                    <div class="no-results-icon">
                        <i class="fas fa-search"></i>
                    </div>
                    <h3>No results found</h3>
                    <p>Try different keywords or check your spelling</p>
                </div>
            `;
            return;
        }

        let resultsHtml = '';
        results.forEach(result => {
            if (result.type === 'item') {
                resultsHtml += this.renderSearchResultItem(result.data);
            } else if (result.type === 'synthesis') {
                resultsHtml += this.renderSearchResultSynthesis(result.data);
            }
        });

        container.innerHTML = resultsHtml;
    }

    renderSearchResultItem(item) {
        return `
            <div class="search-result-item" data-item-id="${item.id}" data-item-type="item">
                <div class="result-icon">
                    <i class="fas fa-file-alt"></i>
                </div>
                <div class="result-content">
                    <h4 class="result-title">${this.escapeHtml(item.display_title || item.title)}</h4>
                    <p class="result-description">${this.escapeHtml(item.description || 'No description available')}</p>
                    <div class="result-meta">
                        <span class="result-category">${this.escapeHtml(item.main_category)} / ${this.escapeHtml(item.sub_category)}</span>
                        <span class="result-date">${this.formatDate(item.last_updated)}</span>
                    </div>
                </div>
            </div>
        `;
    }

    renderSearchResultSynthesis(synthesis) {
        return `
            <div class="search-result-item" data-item-id="${synthesis.id}" data-item-type="synthesis">
                <div class="result-icon">
                    <i class="fas fa-lightbulb"></i>
                </div>
                <div class="result-content">
                    <h4 class="result-title">${this.escapeHtml(synthesis.synthesis_title)}</h4>
                    <p class="result-description">Synthesis document</p>
                    <div class="result-meta">
                        <span class="result-category">${this.escapeHtml(synthesis.main_category)}${synthesis.sub_category ? ' / ' + this.escapeHtml(synthesis.sub_category) : ''}</span>
                        <span class="result-date">${this.formatDate(synthesis.last_updated)}</span>
                    </div>
                </div>
            </div>
        `;
    }

    showOverview() {
        this.currentView = 'overview';
        this.currentCategory = null;
        this.currentSubcategory = null;
        this.currentItem = null;
        
        this.hideAllViews();
        if (this.elements.overview) {
            this.elements.overview.classList.add('active');
        }
        this.updateBreadcrumbs();
        this.updateStatistics();
        
        console.log('📚 Showing Knowledge Base overview');
    }

    showCategory(categoryName, subcategoryName = null) {
        this.currentView = 'category';
        this.currentCategory = categoryName;
        this.currentSubcategory = subcategoryName;
        
        this.hideAllViews();
        this.elements.categoryView?.classList.add('active');
        this.updateBreadcrumbs();
        
        // Load category data
        this.loadCategoryView(categoryName, subcategoryName);
    }

    async showItemDetail(itemId, itemType) {
        this.currentView = 'item';
        this.hideAllViews();
        this.elements.itemDetail?.classList.add('active');
        
        try {
            await this.loadItemDetail(itemId, itemType);
        } catch (error) {
            console.error('Error loading item detail:', error);
            this.showError('Failed to load item details');
        }
    }

    async loadItemDetail(itemId, itemType) {
        const endpoint = itemType === 'synthesis' ? `/api/synthesis/${itemId}` : `/api/items/${itemId}`;
        
        const response = await fetch(endpoint);
        if (!response.ok) {
            throw new Error(`Failed to fetch item: ${response.status}`);
        }

        const item = await response.json();
        this.currentItem = item;
        this.renderItemDetail(item, itemType);
        this.updateBreadcrumbs();
    }

    renderItemDetail(item, itemType) {
        if (itemType === 'synthesis') {
            this.renderSynthesisDetail(item);
        } else {
            this.renderKBItemDetail(item);
        }
    }

    renderKBItemDetail(item) {
        // Update metadata
        if (this.elements.itemCategory) {
            this.elements.itemCategory.textContent = item.main_category;
        }
        if (this.elements.itemSubcategory) {
            this.elements.itemSubcategory.textContent = item.sub_category;
        }
        if (this.elements.itemTitle) {
            this.elements.itemTitle.textContent = item.display_title || item.title;
        }
        if (this.elements.itemCreated) {
            this.elements.itemCreated.textContent = this.formatDate(item.created_at);
        }
        if (this.elements.itemUpdated) {
            this.elements.itemUpdated.textContent = this.formatDate(item.last_updated);
        }
        if (this.elements.itemSource && item.source_url) {
            this.elements.itemSource.href = item.source_url;
            this.elements.itemSource.textContent = 'View Source';
        }
        if (this.elements.itemDescription) {
            this.elements.itemDescription.textContent = item.description || 'No description available';
        }

        // Render media
        this.renderItemMedia(item);

        // Render main content with fallback options
        if (this.elements.itemContent) {
            let contentToDisplay = '';
            
            if (item.content_html && item.content_html.trim()) {
                contentToDisplay = item.content_html;
            } else if (item.content && item.content.trim()) {
                contentToDisplay = this.escapeHtml(item.content);
            } else if (item.raw_json_content_parsed) {
                // Try to display structured content from raw JSON
                try {
                    const parsed = typeof item.raw_json_content_parsed === 'string' 
                        ? JSON.parse(item.raw_json_content_parsed) 
                        : item.raw_json_content_parsed;
                    
                    if (parsed && parsed.suggested_title) {
                        contentToDisplay = `
                            <div class="kb-item-fallback-content">
                                <h2>${this.escapeHtml(parsed.suggested_title)}</h2>
                                ${parsed.meta_description ? `<p class="meta-description">${this.escapeHtml(parsed.meta_description)}</p>` : ''}
                                ${parsed.introduction ? `<div class="introduction">${this.escapeHtml(parsed.introduction)}</div>` : ''}
                                ${parsed.sections ? this.renderJSONSections(parsed.sections) : ''}
                                ${parsed.key_takeaways ? this.renderKeyTakeaways(parsed.key_takeaways) : ''}
                                ${parsed.conclusion ? `<div class="conclusion">${this.escapeHtml(parsed.conclusion)}</div>` : ''}
                            </div>
                        `;
                    } else {
                        contentToDisplay = `<pre class="raw-json-content">${this.escapeHtml(JSON.stringify(parsed, null, 2))}</pre>`;
                    }
                } catch (error) {
                    console.warn('Failed to parse raw JSON content:', error);
                    contentToDisplay = item.raw_json_content ? `<pre class="raw-content">${this.escapeHtml(item.raw_json_content)}</pre>` : '';
                }
            } else if (item.file_path) {
                contentToDisplay = `
                    <div class="kb-item-placeholder">
                        <div class="placeholder-icon">
                            <i class="fas fa-file-alt"></i>
                        </div>
                        <h3>Knowledge Base Item</h3>
                        <p>This item is stored at: <code>${this.escapeHtml(item.file_path)}</code></p>
                        <p>Content processing may be incomplete. Try refreshing the knowledge base.</p>
                    </div>
                `;
            } else {
                contentToDisplay = `
                    <div class="kb-item-placeholder">
                        <div class="placeholder-icon">
                            <i class="fas fa-question-circle"></i>
                        </div>
                        <h3>No Content Available</h3>
                        <p>This knowledge base item doesn't have processed content yet.</p>
                    </div>
                `;
            }
            
            this.elements.itemContent.innerHTML = contentToDisplay;
        }
    }

    renderSynthesisDetail(synthesis) {
        // Update metadata
        if (this.elements.itemCategory) {
            this.elements.itemCategory.textContent = synthesis.main_category;
        }
        if (this.elements.itemSubcategory) {
            this.elements.itemSubcategory.textContent = synthesis.sub_category || 'Main Category';
        }
        if (this.elements.itemTitle) {
            this.elements.itemTitle.textContent = synthesis.synthesis_title;
        }
        if (this.elements.itemCreated) {
            this.elements.itemCreated.textContent = this.formatDate(synthesis.created_at);
        }
        if (this.elements.itemUpdated) {
            this.elements.itemUpdated.textContent = this.formatDate(synthesis.last_updated);
        }
        if (this.elements.itemDescription) {
            this.elements.itemDescription.textContent = `Synthesis document covering ${synthesis.item_count} items`;
        }

        // Hide media section for syntheses
        if (this.elements.itemMediaSection) {
            this.elements.itemMediaSection.style.display = 'none';
        }

        // Render synthesis content
        if (this.elements.itemContent) {
            this.elements.itemContent.innerHTML = synthesis.synthesis_content_html || this.escapeHtml(synthesis.synthesis_content || 'No content available');
        }
    }

    renderItemMedia(item) {
        const mediaSection = this.elements.itemMediaSection;
        if (!mediaSection) return;

        if (!item.media_files_for_template || item.media_files_for_template.length === 0) {
            mediaSection.style.display = 'none';
            return;
        }

        mediaSection.style.display = 'block';
        let mediaHtml = '<h3>Media</h3><div class="media-grid">';

        item.media_files_for_template.forEach(media => {
            if (media.type === 'image') {
                mediaHtml += `
                    <div class="media-item image-item">
                        <img src="${media.url}" alt="${media.name}" loading="lazy">
                        <div class="media-caption">${media.name}</div>
                    </div>
                `;
            } else if (media.type === 'video') {
                mediaHtml += `
                    <div class="media-item video-item">
                        <video controls>
                            <source src="${media.url}" type="video/mp4">
                            Your browser does not support the video tag.
                        </video>
                        <div class="media-caption">${media.name}</div>
                    </div>
                `;
            }
        });

        mediaHtml += '</div>';
        mediaSection.innerHTML = mediaHtml;
    }

    loadCategoryView(categoryName, subcategoryName) {
        const category = this.data.tree.get(categoryName);
        if (!category) return;

        // Update category header
        if (this.elements.categoryTitle) {
            this.elements.categoryTitle.textContent = subcategoryName ? subcategoryName : categoryName;
        }

        if (this.elements.categoryDescription) {
            this.elements.categoryDescription.textContent = subcategoryName 
                ? `Items in the ${subcategoryName} subcategory of ${categoryName}`
                : `All items and subcategories in ${categoryName}`;
        }

        const items = subcategoryName 
            ? category.subcategories.get(subcategoryName)?.items || []
            : this.getCategoryItems(category);

        if (this.elements.categoryItemCount) {
            this.elements.categoryItemCount.textContent = `${items.length} items`;
        }

        // Render subcategories (only if showing main category)
        if (!subcategoryName) {
            this.renderSubcategories(category.subcategories);
        } else {
            if (this.elements.subcategoriesGrid) {
                this.elements.subcategoriesGrid.innerHTML = '';
            }
        }

        // Render items
        this.renderCategoryItems(items);
    }

    getCategoryItems(category) {
        const items = [];
        for (const subcategory of category.subcategories.values()) {
            items.push(...subcategory.items);
        }
        return items;
    }

    renderSubcategories(subcategories) {
        const grid = this.elements.subcategoriesGrid;
        if (!grid) return;

        let html = '';
        for (const [name, subcategory] of subcategories) {
            html += `
                <div class="subcategory-card" data-category="${subcategory.parent}" data-subcategory="${name}">
                    <div class="subcategory-icon">
                        <i class="fas fa-folder-open"></i>
                    </div>
                    <div class="subcategory-info">
                        <h4 class="subcategory-name">${this.escapeHtml(name)}</h4>
                        <p class="subcategory-count">${subcategory.itemCount} items</p>
                        ${subcategory.synthesis ? '<div class="synthesis-badge"><i class="fas fa-lightbulb"></i> Has synthesis</div>' : ''}
                    </div>
                </div>
            `;
        }

        grid.innerHTML = html;

        // Add click handlers for subcategories
        grid.addEventListener('click', (e) => {
            const card = e.target.closest('.subcategory-card');
            if (card) {
                const category = card.getAttribute('data-category');
                const subcategory = card.getAttribute('data-subcategory');
                this.showCategory(category, subcategory);
            }
        });
    }

    renderCategoryItems(items) {
        const container = this.elements.itemsContainer;
        if (!container) return;

        if (items.length === 0) {
            container.innerHTML = `
                <div class="no-items">
                    <div class="no-items-icon">
                        <i class="fas fa-file-alt"></i>
                    </div>
                    <p>No items in this category</p>
                </div>
            `;
            return;
        }

        let html = '';
        items.forEach(item => {
            html += `
                <div class="item-card" data-item-id="${item.id}" data-item-type="item">
                    <div class="item-card-header">
                        <div class="item-icon">
                            <i class="fas fa-file-alt"></i>
                        </div>
                        <div class="item-meta">
                            <span class="item-date">${this.formatDate(item.last_updated)}</span>
                        </div>
                    </div>
                    <div class="item-card-content">
                        <h4 class="item-card-title">${this.escapeHtml(item.display_title || item.title)}</h4>
                        <p class="item-card-description">${this.escapeHtml(this.truncateText(item.description || '', 100))}</p>
                    </div>
                    <div class="item-card-footer">
                        <span class="item-category">${this.escapeHtml(item.main_category)} / ${this.escapeHtml(item.sub_category)}</span>
                    </div>
                </div>
            `;
        });

        container.innerHTML = html;

        // Add click handlers for items
        container.addEventListener('click', (e) => {
            const card = e.target.closest('.item-card');
            if (card) {
                const itemId = card.getAttribute('data-item-id');
                const itemType = card.getAttribute('data-item-type');
                this.showItemDetail(itemId, itemType);
            }
        });
    }

    loadRecentItems() {
        const container = this.elements.recentItems;
        if (!container) return;

        // Get recent items (sort by last_updated)
        const recentItems = [...this.data.items]
            .sort((a, b) => new Date(b.last_updated) - new Date(a.last_updated))
            .slice(0, 5);

        if (recentItems.length === 0) {
            container.innerHTML = '<p class="no-recent">No recent items</p>';
            return;
        }

        let html = '';
        recentItems.forEach(item => {
            html += `
                <div class="recent-item" data-item-id="${item.id}" data-item-type="item">
                    <div class="recent-item-icon">
                        <i class="fas fa-file-alt"></i>
                    </div>
                    <div class="recent-item-content">
                        <h5 class="recent-item-title">${this.escapeHtml(item.display_title || item.title)}</h5>
                        <p class="recent-item-meta">${this.escapeHtml(item.main_category)} / ${this.escapeHtml(item.sub_category)}</p>
                        <span class="recent-item-date">${this.formatDate(item.last_updated)}</span>
                    </div>
                </div>
            `;
        });

        container.innerHTML = html;

        // Add click handlers
        container.addEventListener('click', (e) => {
            const item = e.target.closest('.recent-item');
            if (item) {
                const itemId = item.getAttribute('data-item-id');
                const itemType = item.getAttribute('data-item-type');
                this.showItemDetail(itemId, itemType);
            }
        });
    }

    hideAllViews() {
        [this.elements.overview, this.elements.categoryView, this.elements.itemDetail, this.elements.searchResults]
            .forEach(view => view?.classList.remove('active'));
    }

    updateBreadcrumbs() {
        const trail = this.elements.breadcrumbTrail;
        if (!trail) return;

        let breadcrumbHtml = '';

        if (this.currentView === 'category') {
            breadcrumbHtml += `
                <i class="fas fa-chevron-right"></i>
                <button class="breadcrumb-btn" data-category="${this.currentCategory}">
                    <i class="fas fa-folder"></i>
                    <span>${this.escapeHtml(this.currentCategory)}</span>
                </button>
            `;

            if (this.currentSubcategory) {
                breadcrumbHtml += `
                    <i class="fas fa-chevron-right"></i>
                    <button class="breadcrumb-btn active">
                        <i class="fas fa-folder-open"></i>
                        <span>${this.escapeHtml(this.currentSubcategory)}</span>
                    </button>
                `;
            }
        } else if (this.currentView === 'item' && this.currentItem) {
            const item = this.currentItem;
            breadcrumbHtml += `
                <i class="fas fa-chevron-right"></i>
                <button class="breadcrumb-btn" data-category="${item.main_category || item.main_category}">
                    <i class="fas fa-folder"></i>
                    <span>${this.escapeHtml(item.main_category || item.main_category)}</span>
                </button>
                <i class="fas fa-chevron-right"></i>
                <button class="breadcrumb-btn" data-category="${item.main_category || item.main_category}" data-subcategory="${item.sub_category || item.sub_category}">
                    <i class="fas fa-folder-open"></i>
                    <span>${this.escapeHtml(item.sub_category || item.sub_category)}</span>
                </button>
                <i class="fas fa-chevron-right"></i>
                <span class="breadcrumb-current">
                    <i class="fas fa-file-alt"></i>
                    <span>${this.escapeHtml(item.display_title || item.synthesis_title || item.title)}</span>
                </span>
            `;
        } else if (this.currentView === 'search') {
            breadcrumbHtml += `
                <i class="fas fa-chevron-right"></i>
                <span class="breadcrumb-current">
                    <i class="fas fa-search"></i>
                    <span>Search Results</span>
                </span>
            `;
        }

        trail.innerHTML = breadcrumbHtml;

        // Add click handlers for breadcrumb navigation
        trail.addEventListener('click', (e) => {
            const btn = e.target.closest('.breadcrumb-btn');
            if (btn) {
                const category = btn.getAttribute('data-category');
                const subcategory = btn.getAttribute('data-subcategory');
                
                if (category) {
                    this.showCategory(category, subcategory);
                }
            }
        });
    }

    updateStatistics() {
        const totalItems = this.data.items.length;
        const totalSyntheses = this.data.syntheses.length;
        
        // Count unique categories and subcategories
        const categories = new Set();
        const subcategories = new Set();
        
        this.data.items.forEach(item => {
            categories.add(item.main_category || 'Uncategorized');
            subcategories.add(`${item.main_category || 'Uncategorized'}/${item.sub_category || 'General'}`);
        });
        
        const totalCategories = categories.size;
        const totalSubcategories = subcategories.size;

        // Update sidebar stats
        if (this.elements.totalCount) {
            this.elements.totalCount.textContent = totalItems;
        }
        if (this.elements.categoriesCount) {
            this.elements.categoriesCount.textContent = totalCategories;
        }
        if (this.elements.subcategoriesCount) {
            this.elements.subcategoriesCount.textContent = totalSubcategories;
        }
        if (this.elements.itemsCount) {
            this.elements.itemsCount.textContent = totalItems;
        }

        // Update overview stats
        if (this.elements.overviewCategories) {
            this.elements.overviewCategories.textContent = totalCategories;
        }
        if (this.elements.overviewSubcategories) {
            this.elements.overviewSubcategories.textContent = totalSubcategories;
        }
        if (this.elements.overviewItems) {
            this.elements.overviewItems.textContent = totalItems;
        }
        if (this.elements.overviewSyntheses) {
            this.elements.overviewSyntheses.textContent = totalSyntheses;
        }
    }

    async refresh() {
        console.log('🔄 Refreshing knowledge base...');
        try {
            await this.loadKnowledgeBaseData();
            this.buildCategoryTree();
            this.renderTree();
            this.updateStatistics();
            
            // Refresh current view
            if (this.currentView === 'overview') {
                this.showOverview();
            } else if (this.currentView === 'category') {
                this.showCategory(this.currentCategory, this.currentSubcategory);
            } else if (this.currentView === 'search') {
                this.showSearchResults(this.searchQuery);
            }
            
            console.log('✅ Knowledge base refreshed');
        } catch (error) {
            console.error('Error refreshing knowledge base:', error);
            this.showError('Failed to refresh knowledge base');
        }
    }

    exportKnowledgeBase() {
        console.log('📤 Exporting knowledge base...');
        // Implementation for export functionality
        alert('Export functionality coming soon!');
    }

    setItemsViewMode(mode) {
        // Toggle view mode buttons
        this.elements.itemsGridView?.classList.toggle('active', mode === 'grid');
        this.elements.itemsListView?.classList.toggle('active', mode === 'list');
        
        // Apply view mode to container
        this.elements.itemsContainer?.classList.toggle('list-view', mode === 'list');
    }

    sortItems(sortBy) {
        // Implementation for sorting items
        console.log(`Sorting items by: ${sortBy}`);
        // Re-render current view with sorted items
    }

    showError(message) {
        console.error(message);
        // You could implement a toast notification here
        alert(message); // Temporary simple error display
    }

    // Utility methods
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    truncateText(text, maxLength) {
        if (text.length <= maxLength) return text;
        return text.substring(0, maxLength).trim() + '...';
    }

    formatDate(dateString) {
        if (!dateString) return 'Unknown';
        const date = new Date(dateString);
        return date.toLocaleDateString([], { 
            year: 'numeric', 
            month: 'short', 
            day: 'numeric' 
        });
    }

    getRelativeTime(date) {
        const now = new Date();
        const diffMs = now - date;
        const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
        
        if (diffDays === 0) {
            const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
            if (diffHours === 0) {
                const diffMinutes = Math.floor(diffMs / (1000 * 60));
                return diffMinutes <= 1 ? 'Just now' : `${diffMinutes}m ago`;
            }
            return diffHours === 1 ? '1h ago' : `${diffHours}h ago`;
        } else if (diffDays === 1) {
            return 'Yesterday';
        } else if (diffDays < 7) {
            return `${diffDays}d ago`;
        } else if (diffDays < 30) {
            const weeks = Math.floor(diffDays / 7);
            return weeks === 1 ? '1w ago' : `${weeks}w ago`;
        } else if (diffDays < 365) {
            const months = Math.floor(diffDays / 30);
            return months === 1 ? '1mo ago' : `${months}mo ago`;
        } else {
            const years = Math.floor(diffDays / 365);
            return years === 1 ? '1y ago' : `${years}y ago`;
        }
    }

    exportItem(itemId) {
        console.log('Exporting item:', itemId);
        // Implement export functionality
    }

    cleanup() {
        // Clear any timeouts or intervals if needed
        console.log('🧹 Cleaning up KnowledgeBaseManager...');
    }

    renderJSONSections(sections) {
        if (!Array.isArray(sections)) return '';
        
        return sections.map(section => `
            <div class="content-section">
                <h3>${this.escapeHtml(section.heading || '')}</h3>
                ${section.content_paragraphs ? section.content_paragraphs.map(p => `<p>${this.escapeHtml(p)}</p>`).join('') : ''}
                ${section.code_blocks ? section.code_blocks.map(block => 
                    `<pre><code class="${block.language || ''}">${this.escapeHtml(block.code || '')}</code></pre>`
                ).join('') : ''}
                ${section.lists ? section.lists.map(list => 
                    `<${list.type === 'numbered' ? 'ol' : 'ul'}>${list.items.map(item => `<li>${this.escapeHtml(item)}</li>`).join('')}</${list.type === 'numbered' ? 'ol' : 'ul'}>`
                ).join('') : ''}
            </div>
        `).join('');
    }

    renderKeyTakeaways(takeaways) {
        if (!Array.isArray(takeaways)) return '';
        
        return `
            <div class="key-takeaways">
                <h3>Key Takeaways</h3>
                <ul>
                    ${takeaways.map(takeaway => `<li>${this.escapeHtml(takeaway)}</li>`).join('')}
                </ul>
            </div>
        `;
    }
}

// Make globally available for router usage
window.KnowledgeBaseManager = KnowledgeBaseManager; 
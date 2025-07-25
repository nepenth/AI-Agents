/**
 * Tweet Management Manager
 * 
 * Manages the tweet exploration, filtering, and control interface
 * following the established component-based architecture patterns.
 */
class TweetManagementManager {
    constructor(api) {
        console.log('🐦 TweetManagementManager constructor called with api:', api);
        this.api = api;
        this.initialized = false;
        this.currentFilters = {};
        this.currentSort = { field: 'updated_at', order: 'desc' };
        this.currentPage = 1;
        this.perPage = 50;
        this.selectedTweets = new Set();
        this.totalTweets = 0;
        this.filteredTweets = 0;
        this.tweets = [];
        this.categories = [];
        this.isLoading = false;
        
        // Debounce timers
        this.searchDebounceTimer = null;
        this.filterDebounceTimer = null;
        
        // Event listeners array for cleanup
        this.eventListeners = [];
        
        this.bindMethods();
    }

    async initialize() {
        console.log('🐦 TweetManagementManager.initialize() called');
        return this.init();
    }

    bindMethods() {
        // Bind all methods to maintain context - simplified to avoid undefined methods
        this.init = this.init.bind(this);
        this.setupEventListeners = this.setupEventListeners.bind(this);
        this.loadTweets = this.loadTweets.bind(this);
        this.loadCategories = this.loadCategories.bind(this);
        this.applyFilters = this.applyFilters.bind(this);
        this.handleSearch = this.handleSearch.bind(this);
        this.handleSort = this.handleSort.bind(this);
        this.renderTable = this.renderTable.bind(this);
        this.showTweetDetail = this.showTweetDetail.bind(this);
        this.showStatistics = this.showStatistics.bind(this);
    }

    async init() {
        if (this.initialized) return;

        try {
            console.log('Initializing Tweet Management Manager...');
            
            // Load initial data
            await Promise.all([
                this.loadCategories(),
                this.loadTweets()
            ]);
            
            this.setupEventListeners();
            this.updateUI();
            this.initialized = true;
            
            console.log('Tweet Management Manager initialized successfully');
        } catch (error) {
            console.error('Failed to initialize Tweet Management Manager:', error);
            this.showError('Failed to initialize tweet management interface');
        }
    }

    setupEventListeners() {
        // Search functionality
        const searchInput = document.getElementById('tweet-search-input');
        if (searchInput) {
            this.addEventListener(searchInput, 'input', this.handleSearch);
            this.addEventListener(searchInput, 'keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    this.applyFilters();
                }
            });
        }

        // Clear search button
        const clearSearchBtn = document.getElementById('clear-search-btn');
        if (clearSearchBtn) {
            this.addEventListener(clearSearchBtn, 'click', () => {
                searchInput.value = '';
                this.handleSearch();
            });
        }

        // Filter controls
        const filterSelects = ['status-filter', 'media-filter', 'category-filter'];
        filterSelects.forEach(id => {
            const element = document.getElementById(id);
            if (element) {
                this.addEventListener(element, 'change', this.applyFilters);
            }
        });

        // Advanced filters toggle
        const toggleAdvancedBtn = document.getElementById('toggle-advanced-filters');
        if (toggleAdvancedBtn) {
            this.addEventListener(toggleAdvancedBtn, 'click', this.toggleAdvancedFilters);
        }

        // Filter actions
        const clearFiltersBtn = document.getElementById('clear-all-filters');
        if (clearFiltersBtn) {
            this.addEventListener(clearFiltersBtn, 'click', this.clearAllFilters);
        }

        const applyFiltersBtn = document.getElementById('apply-filters-btn');
        if (applyFiltersBtn) {
            this.addEventListener(applyFiltersBtn, 'click', this.applyFilters);
        }

        // Sort controls
        const sortSelect = document.getElementById('sort-by-select');
        if (sortSelect) {
            this.addEventListener(sortSelect, 'change', this.handleSort);
        }

        const sortOrderBtn = document.getElementById('sort-order-btn');
        if (sortOrderBtn) {
            this.addEventListener(sortOrderBtn, 'click', this.toggleSortOrder);
        }

        // Pagination controls
        const perPageSelect = document.getElementById('per-page-select');
        if (perPageSelect) {
            this.addEventListener(perPageSelect, 'change', this.handlePerPageChange);
        }

        // Selection controls
        const selectAllCheckbox = document.getElementById('select-all-tweets');
        if (selectAllCheckbox) {
            this.addEventListener(selectAllCheckbox, 'change', this.handleSelectAll);
        }

        // Bulk operations
        const bulkOperationsBtn = document.getElementById('bulk-operations-btn');
        if (bulkOperationsBtn) {
            this.addEventListener(bulkOperationsBtn, 'click', this.showBulkOperations);
        }

        // Statistics
        const statisticsBtn = document.getElementById('tweet-statistics-btn');
        if (statisticsBtn) {
            this.addEventListener(statisticsBtn, 'click', this.showStatistics);
        }

        // Refresh
        const refreshBtn = document.getElementById('refresh-tweets-btn');
        if (refreshBtn) {
            this.addEventListener(refreshBtn, 'click', () => this.loadTweets(true));
        }

        // Modal close handlers
        this.setupModalHandlers();

        // Table sortable headers
        this.setupTableSorting();
    }

    setupModalHandlers() {
        // Tweet detail modal
        const tweetDetailModal = document.getElementById('tweet-detail-modal');
        const closeTweetDetailBtn = document.getElementById('close-tweet-detail');
        if (tweetDetailModal && closeTweetDetailBtn) {
            this.addEventListener(closeTweetDetailBtn, 'click', () => this.hideModal('tweet-detail-modal'));
            this.addEventListener(tweetDetailModal, 'click', (e) => {
                if (e.target === tweetDetailModal) this.hideModal('tweet-detail-modal');
            });
        }

        // Bulk operations modal
        const bulkOpsModal = document.getElementById('bulk-operations-modal');
        const closeBulkOpsBtn = document.getElementById('close-bulk-operations');
        const executeBulkBtn = document.getElementById('execute-bulk-operation');
        if (bulkOpsModal && closeBulkOpsBtn) {
            this.addEventListener(closeBulkOpsBtn, 'click', () => this.hideModal('bulk-operations-modal'));
            this.addEventListener(bulkOpsModal, 'click', (e) => {
                if (e.target === bulkOpsModal) this.hideModal('bulk-operations-modal');
            });
        }
        if (executeBulkBtn) {
            this.addEventListener(executeBulkBtn, 'click', this.executeBulkOperation);
        }

        // Statistics modal
        const statisticsModal = document.getElementById('statistics-modal');
        const closeStatsBtn = document.getElementById('close-statistics');
        if (statisticsModal && closeStatsBtn) {
            this.addEventListener(closeStatsBtn, 'click', () => this.hideModal('statistics-modal'));
            this.addEventListener(statisticsModal, 'click', (e) => {
                if (e.target === statisticsModal) this.hideModal('statistics-modal');
            });
        }
    }

    setupTableSorting() {
        const sortableHeaders = document.querySelectorAll('.tweet-table .sortable');
        sortableHeaders.forEach(header => {
            this.addEventListener(header, 'click', () => {
                const sortField = header.dataset.sort;
                if (sortField) {
                    if (this.currentSort.field === sortField) {
                        this.currentSort.order = this.currentSort.order === 'asc' ? 'desc' : 'asc';
                    } else {
                        this.currentSort.field = sortField;
                        this.currentSort.order = 'desc';
                    }
                    this.loadTweets();
                }
            });
        });
    }

    addEventListener(element, event, handler) {
        element.addEventListener(event, handler);
        this.eventListeners.push({ element, event, handler });
    }

    removeEventListeners() {
        this.eventListeners.forEach(({ element, event, handler }) => {
            element.removeEventListener(event, handler);
        });
        this.eventListeners = [];
    }

    async loadCategories() {
        try {
            console.log('Loading categories...');
            const response = await fetch('/api/v2/tweets/categories');
            console.log('Categories response status:', response.status);
            if (!response.ok) throw new Error('Failed to load categories');
            
            const result = await response.json();
            console.log('Categories result:', result);
            this.categories = result.data?.categories || [];
            console.log('Parsed categories count:', this.categories.length);
            this.populateCategoryFilter();
        } catch (error) {
            console.error('Error loading categories:', error);
        }
    }

    populateCategoryFilter() {
        const categoryFilter = document.getElementById('category-filter');
        if (!categoryFilter) return;

        // Clear existing options (except the first "All Categories")
        const firstOption = categoryFilter.firstElementChild;
        categoryFilter.innerHTML = '';
        if (firstOption) categoryFilter.appendChild(firstOption);

        // Add category options
        this.categories.forEach(category => {
            const option = document.createElement('option');
            option.value = `${category.main_category}:${category.sub_category}`;
            option.textContent = `${category.main_category} > ${category.sub_category}`;
            categoryFilter.appendChild(option);
        });
    }

    async loadTweets(forceRefresh = false) {
        if (this.isLoading && !forceRefresh) return;
        
        this.isLoading = true;
        this.showLoading();

        try {
            const params = new URLSearchParams({
                page: this.currentPage,
                per_page: this.perPage,
                sort_by: this.currentSort.field,
                sort_order: this.currentSort.order,
                ...this.currentFilters
            });

            console.log('Loading tweets with URL:', `/api/v2/tweets/explore?${params}`);
            const response = await fetch(`/api/v2/tweets/explore?${params}`);
            console.log('Tweets response status:', response.status);
            if (!response.ok) throw new Error('Failed to load tweets');

            const result = await response.json();
            console.log('Tweets result:', result);
            const data = result.data || {};
            this.tweets = data.tweets || [];
            this.totalTweets = data.pagination?.total_count || 0;
            this.filteredTweets = data.pagination?.total_count || 0;
            
            console.log('Parsed tweets:', this.tweets.length, 'Total:', this.totalTweets);
            
            this.updateUI();
            this.hideLoading();
            
        } catch (error) {
            console.error('Error loading tweets:', error);
            this.showError('Failed to load tweets');
            this.hideLoading();
        } finally {
            this.isLoading = false;
        }
    }

    handleSearch() {
        clearTimeout(this.searchDebounceTimer);
        this.searchDebounceTimer = setTimeout(() => {
            const searchInput = document.getElementById('tweet-search-input');
            const searchTerm = searchInput?.value.trim();
            
            if (searchTerm !== this.currentFilters.search) {
                this.currentFilters.search = searchTerm || undefined;
                this.currentPage = 1;
                this.applyFilters();
            }
        }, 300);
    }

    applyFilters() {
        clearTimeout(this.filterDebounceTimer);
        this.filterDebounceTimer = setTimeout(() => {
            this.currentFilters = this.collectFilterValues();
            this.currentPage = 1;
            this.selectedTweets.clear();
            this.loadTweets();
        }, 100);
    }

    collectFilterValues() {
        const filters = {};
        
        // Search term
        const searchInput = document.getElementById('tweet-search-input');
        if (searchInput?.value.trim()) {
            filters.search = searchInput.value.trim();
        }

        // Status filter
        const statusFilter = document.getElementById('status-filter');
        if (statusFilter?.value) {
            filters.status = statusFilter.value;
        }

        // Media filter
        const mediaFilter = document.getElementById('media-filter');
        if (mediaFilter?.value) {
            filters.has_media = mediaFilter.value === 'true';
        }

        // Category filter
        const categoryFilter = document.getElementById('category-filter');
        if (categoryFilter?.value) {
            const [mainCategory, subCategory] = categoryFilter.value.split(':');
            filters.main_category = mainCategory;
            filters.sub_category = subCategory;
        }

        // Date range filters
        const dateFrom = document.getElementById('date-from');
        const dateTo = document.getElementById('date-to');
        if (dateFrom?.value) filters.date_from = dateFrom.value;
        if (dateTo?.value) filters.date_to = dateTo.value;

        // Processing flag filters
        const flagFilters = ['cache-complete', 'media-processed', 'categories-processed', 'kb-item-created'];
        flagFilters.forEach(flagId => {
            const checkbox = document.getElementById(`filter-${flagId}`);
            if (checkbox?.checked) {
                const flagName = flagId.replace(/-/g, '_');
                filters[flagName] = true;
            }
        });

        return filters;
    }

    handleSort() {
        const sortSelect = document.getElementById('sort-by-select');
        if (sortSelect) {
            this.currentSort.field = sortSelect.value;
            this.currentPage = 1;
            this.loadTweets();
        }
    }

    toggleSortOrder() {
        this.currentSort.order = this.currentSort.order === 'asc' ? 'desc' : 'asc';
        this.currentPage = 1;
        this.updateSortOrderButton();
        this.loadTweets();
    }

    updateSortOrderButton() {
        const button = document.getElementById('sort-order-btn');
        if (button) {
            const icon = button.querySelector('i');
            if (icon) {
                icon.className = this.currentSort.order === 'asc' ? 
                    'fas fa-sort-amount-up' : 'fas fa-sort-amount-down';
            }
            button.dataset.order = this.currentSort.order;
        }
    }

    handlePerPageChange() {
        const perPageSelect = document.getElementById('per-page-select');
        if (perPageSelect) {
            this.perPage = parseInt(perPageSelect.value);
            this.currentPage = 1;
            this.loadTweets();
        }
    }

    handleSelectAll() {
        const selectAllCheckbox = document.getElementById('select-all-tweets');
        if (selectAllCheckbox) {
            if (selectAllCheckbox.checked) {
                // Select all visible tweets
                this.tweets.forEach(tweet => this.selectedTweets.add(tweet.tweet_id));
            } else {
                // Deselect all tweets
                this.selectedTweets.clear();
            }
            this.updateSelectionUI();
            this.renderTable();
        }
    }

    toggleAdvancedFilters() {
        const advancedFilters = document.getElementById('advanced-filters');
        const toggleButton = document.getElementById('toggle-advanced-filters');
        const toggleText = document.getElementById('advanced-filter-text');
        
        if (advancedFilters && toggleButton && toggleText) {
            const isVisible = advancedFilters.style.display !== 'none';
            advancedFilters.style.display = isVisible ? 'none' : 'block';
            toggleText.textContent = isVisible ? 'Advanced Filters' : 'Hide Advanced';
            
            const icon = toggleButton.querySelector('i');
            if (icon) {
                icon.className = isVisible ? 'fas fa-filter' : 'fas fa-filter-circle-xmark';
            }
        }
    }

    clearAllFilters() {
        // Clear search input
        const searchInput = document.getElementById('tweet-search-input');
        if (searchInput) searchInput.value = '';

        // Reset all select filters
        const selects = ['status-filter', 'media-filter', 'category-filter'];
        selects.forEach(id => {
            const select = document.getElementById(id);
            if (select) select.value = '';
        });

        // Clear date inputs
        const dateInputs = ['date-from', 'date-to'];
        dateInputs.forEach(id => {
            const input = document.getElementById(id);
            if (input) input.value = '';
        });

        // Uncheck all checkboxes
        const checkboxes = ['filter-cache-complete', 'filter-media-processed', 
                          'filter-categories-processed', 'filter-kb-item-created'];
        checkboxes.forEach(id => {
            const checkbox = document.getElementById(id);
            if (checkbox) checkbox.checked = false;
        });

        // Apply cleared filters
        this.currentFilters = {};
        this.currentPage = 1;
        this.loadTweets();
    }

    updateUI() {
        this.updateSummaryStats();
        this.updateSortOrderButton();
        this.renderTable();
        this.renderPagination();
        this.updateSelectionUI();
        this.updateTableHeaders();
    }

    updateSummaryStats() {
        const totalElement = document.getElementById('total-tweets-count');
        const filteredElement = document.getElementById('filtered-tweets-count');
        const selectedElement = document.getElementById('selected-tweets-count');

        if (totalElement) totalElement.textContent = this.totalTweets.toLocaleString();
        if (filteredElement) filteredElement.textContent = this.filteredTweets.toLocaleString();
        if (selectedElement) selectedElement.textContent = this.selectedTweets.size.toLocaleString();
    }

    updateTableHeaders() {
        const headers = document.querySelectorAll('.tweet-table .sortable');
        headers.forEach(header => {
            const sortField = header.dataset.sort;
            const icon = header.querySelector('.sort-icon');
            
            if (sortField === this.currentSort.field) {
                header.classList.add('active');
                if (icon) {
                    icon.className = this.currentSort.order === 'asc' ? 
                        'fas fa-sort-up sort-icon' : 'fas fa-sort-down sort-icon';
                }
            } else {
                header.classList.remove('active');
                if (icon) {
                    icon.className = 'fas fa-sort sort-icon';
                }
            }
        });
    }

    renderTable() {
        const tbody = document.getElementById('tweet-table-body');
        const emptyState = document.getElementById('empty-state');
        const tableWrapper = document.querySelector('.tweet-table-wrapper');

        if (!tbody) return;

        if (this.tweets.length === 0) {
            tbody.innerHTML = '';
            if (tableWrapper) tableWrapper.style.display = 'none';
            if (emptyState) emptyState.style.display = 'block';
            return;
        }

        if (tableWrapper) tableWrapper.style.display = 'block';
        if (emptyState) emptyState.style.display = 'none';

        tbody.innerHTML = this.tweets.map(tweet => this.renderTweetRow(tweet)).join('');

        // Add click handlers for table rows
        this.setupTableRowHandlers();
    }

    renderTweetRow(tweet) {
        const isSelected = this.selectedTweets.has(tweet.tweet_id);
        const status = this.getTweetStatus(tweet);
        const progress = this.calculateProgress(tweet);
        const mediaCount = tweet.media_count || 0;
        
        return `
            <tr class="${isSelected ? 'selected' : ''}" data-tweet-id="${tweet.tweet_id}">
                <td class="select-col">
                    <label class="glass-checkbox">
                        <input type="checkbox" ${isSelected ? 'checked' : ''} 
                               class="tweet-checkbox" data-tweet-id="${tweet.tweet_id}">
                        <span class="checkmark"></span>
                    </label>
                </td>
                <td class="tweet-id-col">
                    <button class="action-btn action-btn--primary tweet-detail-btn" 
                            data-tweet-id="${tweet.tweet_id}"
                            title="View Details">
                        ${tweet.tweet_id}
                    </button>
                </td>
                <td class="status-col">
                    <span class="status-badge status-badge--${status.type}">
                        <i class="${status.icon}"></i>
                        ${status.text}
                    </span>
                </td>
                <td class="category-col">
                    <div class="category-display">
                        <div class="main-category editable-field" 
                             data-tweet-id="${tweet.tweet_id}" 
                             data-field="main_category" 
                             title="Click to edit category">
                            ${tweet.main_category || '<span class="empty-field">Click to set</span>'}
                        </div>
                        <div class="sub-category editable-field" 
                             data-tweet-id="${tweet.tweet_id}" 
                             data-field="sub_category" 
                             title="Click to edit sub-category">
                            ${tweet.sub_category || '<span class="empty-field">Click to set</span>'}
                        </div>
                    </div>
                </td>
                <td class="media-col">
                    <div class="media-info">
                        ${mediaCount > 0 ? 
                            `<button class="media-preview-btn action-btn" data-tweet-id="${tweet.tweet_id}" title="Preview Media">
                                <i class="fas fa-image"></i> ${mediaCount}
                            </button>` : 
                            '<span class="no-media"><i class="fas fa-file-text"></i> 0</span>'
                        }
                    </div>
                </td>
                <td class="progress-col">
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: ${progress}%"></div>
                    </div>
                    <div class="progress-text">${progress}%</div>
                </td>
                <td class="updated-col">
                    ${this.formatDate(tweet.updated_at)}
                </td>
                <td class="actions-col">
                    <div class="action-buttons">
                        <button class="action-btn tweet-detail-btn" 
                                data-tweet-id="${tweet.tweet_id}"
                                title="View Details">
                            <i class="fas fa-eye"></i>
                        </button>
                        <button class="action-btn tweet-reprocess-btn" 
                                data-tweet-id="${tweet.tweet_id}"
                                title="Reprocess">
                            <i class="fas fa-redo"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `;
    }

    setupTableRowHandlers() {
        // Event delegation for table actions
        const tbody = document.getElementById('tweet-table-body');
        if (!tbody) return;

        // Remove existing event listeners to avoid duplicates
        tbody.removeEventListener('click', this.handleTableClick);
        tbody.removeEventListener('change', this.handleTableChange);

        // Add event listeners with delegation
        tbody.addEventListener('click', this.handleTableClick.bind(this));
        tbody.addEventListener('change', this.handleTableChange.bind(this));

        // Double-click to open details
        const rows = document.querySelectorAll('#tweet-table-body tr');
        rows.forEach(row => {
            this.addEventListener(row, 'dblclick', () => {
                const tweetId = row.dataset.tweetId;
                if (tweetId) this.showTweetDetail(tweetId);
            });
        });
    }

    handleTableClick(event) {
        console.log('🖱️ Table click detected:', event.target);
        
        // Handle different clickable elements
        let target = event.target;
        let tweetId = null;
        
        // Check if clicked on editable field
        if (target.classList.contains('editable-field')) {
            tweetId = target.dataset.tweetId;
            const field = target.dataset.field;
            console.log('📝 Editable field clicked:', field, 'Tweet ID:', tweetId);
            if (tweetId && field) {
                this.editField(tweetId, field, target);
                return;
            }
        }
        
        // Check if clicked on button or button child
        const button = target.closest('button');
        if (button) {
            tweetId = button.dataset.tweetId;
            console.log('🔘 Button clicked:', button.className, 'Tweet ID:', tweetId);
            
            if (!tweetId) {
                console.warn('❌ No tweetId found on button:', button);
                return;
            }
        } else {
            // Check if clicked on tweet row itself for details
            const row = target.closest('tr');
            if (row) {
                tweetId = row.dataset.tweetId;
                console.log('📋 Row clicked, Tweet ID:', tweetId);
                if (tweetId) {
                    this.showTweetDetail(tweetId);
                    return;
                }
            }
            return;
        }
        
        if (!tweetId) return;

        if (button.classList.contains('tweet-detail-btn')) {
            console.log('🔍 Showing tweet detail for:', tweetId);
            this.showTweetDetail(tweetId);
        } else if (button.classList.contains('tweet-reprocess-btn')) {
            console.log('🔄 Reprocessing tweet:', tweetId);
            this.reprocessTweet(tweetId);
        } else if (button.classList.contains('media-preview-btn')) {
            console.log('🖼️ Showing media preview for:', tweetId);
            this.showMediaPreview(tweetId);
        } else {
            console.log('❓ Unknown button clicked:', button.className);
        }
    }

    handleTableChange(event) {
        const target = event.target;
        if (!target.classList.contains('tweet-checkbox')) return;

        const tweetId = target.dataset.tweetId;
        if (tweetId) {
            this.toggleTweetSelection(tweetId);
        }
    }

    async showMediaPreview(tweetId) {
        try {
            const response = await fetch(`/api/v2/tweets/${tweetId}/detail`);
            if (!response.ok) throw new Error('Failed to load tweet details');

            const result = await response.json();
            const tweet = result.data;
            
            if (!tweet.all_downloaded_media_for_thread || tweet.all_downloaded_media_for_thread.length === 0) {
                this.showNotification('No media found for this tweet', 'warning');
                return;
            }

            this.renderMediaPreviewModal(tweet);
            this.showModal('media-preview-modal');
        } catch (error) {
            console.error('Error loading media preview:', error);
            this.showNotification('Failed to load media preview', 'error');
        }
    }

    renderMediaPreviewModal(tweet) {
        // Create modal if it doesn't exist
        let modal = document.getElementById('media-preview-modal');
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'media-preview-modal';
            modal.className = 'modal-overlay';
            modal.innerHTML = `
                <div class="modal glass-panel-v3 glass-panel-v3--primary media-preview-modal">
                    <div class="modal-header">
                        <h3><i class="fas fa-images"></i> Media Preview</h3>
                        <button class="modal-close" data-modal="media-preview-modal">
                            <i class="fas fa-times"></i>
                        </button>
                    </div>
                    <div class="modal-body">
                        <div id="media-preview-content"></div>
                    </div>
                </div>
            `;
            document.body.appendChild(modal);
        }

        const content = document.getElementById('media-preview-content');
        const mediaItems = tweet.all_downloaded_media_for_thread || [];
        
        content.innerHTML = `
            <div class="media-preview-header">
                <h4>Tweet: ${tweet.tweet_id}</h4>
                <p><strong>Title:</strong> ${tweet.display_title || 'No title'}</p>
                <p><strong>Media Count:</strong> ${mediaItems.length}</p>
            </div>
            <div class="media-gallery">
                ${mediaItems.map((mediaPath, index) => `
                    <div class="media-item">
                        <div class="media-container">
                            <img src="/${mediaPath}" 
                                 alt="Media ${index + 1}" 
                                 class="media-image"
                                 onclick="this.classList.toggle('enlarged')"
                                 title="Click to enlarge">
                        </div>
                        <div class="media-info">
                            <p><strong>File:</strong> ${mediaPath.split('/').pop()}</p>
                            <p><strong>Path:</strong> ${mediaPath}</p>
                        </div>
                    </div>
                `).join('')}
            </div>
            ${tweet.image_descriptions && tweet.image_descriptions.length > 0 ? `
                <div class="image-descriptions">
                    <h5>AI Image Descriptions:</h5>
                    ${tweet.image_descriptions.map((desc, index) => `
                        <div class="description-item">
                            <h6>Image ${index + 1}:</h6>
                            <div class="description-text">${desc}</div>
                        </div>
                    `).join('')}
                </div>
            ` : ''}
                 `;
     }

     async editField(tweetId, fieldName, element) {
        const currentValue = element.textContent.trim();
        const isEmptyField = element.querySelector('.empty-field');
        const actualValue = isEmptyField ? '' : currentValue;
        
        // Create inline editor
        const input = document.createElement('input');
        input.type = 'text';
        input.value = actualValue;
        input.className = 'field-editor';
        input.style.cssText = `
            width: 100%;
            background: var(--glass-bg);
            border: 1px solid var(--color-primary);
            border-radius: 4px;
            padding: 4px 8px;
            color: var(--text-primary);
            font-size: inherit;
        `;
        
        // Replace element content with input
        const originalContent = element.innerHTML;
        element.innerHTML = '';
        element.appendChild(input);
        input.focus();
        input.select();
        
        const saveEdit = async () => {
            const newValue = input.value.trim();
            
            try {
                const response = await fetch(`/api/v2/tweets/${tweetId}/update-field`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ 
                        field: fieldName, 
                        value: newValue 
                    })
                });
                
                if (!response.ok) throw new Error('Failed to update field');
                
                // Update display
                element.innerHTML = newValue || '<span class="empty-field">Click to set</span>';
                this.showNotification(`${fieldName} updated successfully`, 'success');
                
                // Refresh the row to show changes
                this.loadTweets();
                
            } catch (error) {
                console.error('Error updating field:', error);
                element.innerHTML = originalContent;
                this.showNotification(`Failed to update ${fieldName}`, 'error');
            }
        };
        
        const cancelEdit = () => {
            element.innerHTML = originalContent;
        };
        
        // Handle save/cancel
        input.addEventListener('blur', saveEdit);
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                saveEdit();
            } else if (e.key === 'Escape') {
                e.preventDefault();
                cancelEdit();
            }
        });
    }

     getTweetStatus(tweet) {
        if (tweet.has_errors) {
            return { type: 'error', icon: 'fas fa-exclamation-triangle', text: 'Error' };
        }
        
        if (tweet.kb_item_created) {
            return { type: 'completed', icon: 'fas fa-check-circle', text: 'Complete' };
        }
        
        if (tweet.cache_complete && (tweet.media_processed || tweet.media_count === 0) && tweet.categories_processed) {
            return { type: 'processing', icon: 'fas fa-cog fa-spin', text: 'Processing' };
        }
        
        return { type: 'pending', icon: 'fas fa-clock', text: 'Pending' };
    }

    calculateProgress(tweet) {
        let progress = 0;
        const totalSteps = 4;
        
        if (tweet.cache_complete) progress++;
        if (tweet.media_processed || tweet.media_count === 0) progress++;
        if (tweet.categories_processed) progress++;
        if (tweet.kb_item_created) progress++;
        
        return Math.round((progress / totalSteps) * 100);
    }

    formatDate(dateString) {
        if (!dateString) return '-';
        const date = new Date(dateString);
        return date.toLocaleString('en-US', {
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    }

    toggleTweetSelection(tweetId) {
        if (this.selectedTweets.has(tweetId)) {
            this.selectedTweets.delete(tweetId);
        } else {
            this.selectedTweets.add(tweetId);
        }
        this.updateSelectionUI();
    }

    updateSelectionUI() {
        const selectedCount = this.selectedTweets.size;
        const selectAllCheckbox = document.getElementById('select-all-tweets');
        const selectionActions = document.getElementById('selection-actions');
        const selectedCountElement = document.getElementById('selected-tweets-count');

        // Update select all checkbox state
        if (selectAllCheckbox) {
            if (selectedCount === 0) {
                selectAllCheckbox.checked = false;
                selectAllCheckbox.indeterminate = false;
            } else if (selectedCount === this.tweets.length) {
                selectAllCheckbox.checked = true;
                selectAllCheckbox.indeterminate = false;
            } else {
                selectAllCheckbox.checked = false;
                selectAllCheckbox.indeterminate = true;
            }
        }

        // Show/hide selection actions
        if (selectionActions) {
            selectionActions.style.display = selectedCount > 0 ? 'flex' : 'none';
        }

        // Update selected count
        if (selectedCountElement) {
            selectedCountElement.textContent = selectedCount.toLocaleString();
        }
    }

    renderPagination() {
        const paginationWrapper = document.getElementById('pagination-wrapper');
        const paginationInfo = document.getElementById('pagination-info-text');
        const pageNumbers = document.getElementById('page-numbers');
        
        if (!paginationWrapper) return;

        const totalPages = Math.ceil(this.filteredTweets / this.perPage);
        
        if (totalPages <= 1) {
            paginationWrapper.style.display = 'none';
            return;
        }

        paginationWrapper.style.display = 'flex';

        // Update pagination info
        if (paginationInfo) {
            const start = ((this.currentPage - 1) * this.perPage) + 1;
            const end = Math.min(this.currentPage * this.perPage, this.filteredTweets);
            paginationInfo.textContent = `Showing ${start}-${end} of ${this.filteredTweets.toLocaleString()} tweets`;
        }

        // Generate page numbers
        if (pageNumbers) {
            pageNumbers.innerHTML = this.generatePageNumbers(totalPages);
        }

        // Update navigation buttons
        this.updatePaginationButtons(totalPages);
    }

    generatePageNumbers(totalPages) {
        const pages = [];
        const current = this.currentPage;
        const showPages = 5; // Number of page buttons to show
        
        let start = Math.max(1, current - Math.floor(showPages / 2));
        let end = Math.min(totalPages, start + showPages - 1);
        
        // Adjust start if we're near the end
        if (end - start + 1 < showPages) {
            start = Math.max(1, end - showPages + 1);
        }

        for (let i = start; i <= end; i++) {
            const isActive = i === current;
            pages.push(`
                <button class="page-number ${isActive ? 'active' : ''}" 
                        onclick="tweetManagementManager.goToPage(${i})"
                        ${isActive ? 'disabled' : ''}>
                    ${i}
                </button>
            `);
        }

        return pages.join('');
    }

    updatePaginationButtons(totalPages) {
        const firstBtn = document.getElementById('first-page-btn');
        const prevBtn = document.getElementById('prev-page-btn');
        const nextBtn = document.getElementById('next-page-btn');
        const lastBtn = document.getElementById('last-page-btn');

        const isFirstPage = this.currentPage === 1;
        const isLastPage = this.currentPage === totalPages;

        if (firstBtn) {
            firstBtn.disabled = isFirstPage;
            firstBtn.onclick = () => this.goToPage(1);
        }

        if (prevBtn) {
            prevBtn.disabled = isFirstPage;
            prevBtn.onclick = () => this.goToPage(this.currentPage - 1);
        }

        if (nextBtn) {
            nextBtn.disabled = isLastPage;
            nextBtn.onclick = () => this.goToPage(this.currentPage + 1);
        }

        if (lastBtn) {
            lastBtn.disabled = isLastPage;
            lastBtn.onclick = () => this.goToPage(totalPages);
        }
    }

    goToPage(page) {
        if (page !== this.currentPage && page >= 1) {
            this.currentPage = page;
            this.loadTweets();
        }
    }

    showLoading() {
        const loadingState = document.getElementById('tweet-loading');
        const tableWrapper = document.querySelector('.tweet-table-wrapper');
        const emptyState = document.getElementById('empty-state');
        
        if (loadingState) loadingState.style.display = 'block';
        if (tableWrapper) tableWrapper.style.display = 'none';
        if (emptyState) emptyState.style.display = 'none';
    }

    hideLoading() {
        const loadingState = document.getElementById('tweet-loading');
        if (loadingState) loadingState.style.display = 'none';
    }

    showError(message) {
        const errorState = document.getElementById('error-state');
        const errorDescription = document.getElementById('error-description');
        const tableWrapper = document.querySelector('.tweet-table-wrapper');
        const emptyState = document.getElementById('empty-state');
        
        if (errorState) {
            errorState.style.display = 'block';
            if (errorDescription) errorDescription.textContent = message;
        }
        if (tableWrapper) tableWrapper.style.display = 'none';
        if (emptyState) emptyState.style.display = 'none';
    }

    async showTweetDetail(tweetId) {
        try {
            const response = await fetch(`/api/v2/tweets/${tweetId}/detail`);
            if (!response.ok) throw new Error('Failed to load tweet details');

            const tweetData = await response.json();
            this.renderTweetDetailModal(tweetData);
            this.showModal('tweet-detail-modal');
        } catch (error) {
            console.error('Error loading tweet details:', error);
            this.showNotification('Failed to load tweet details', 'error');
        }
    }

    renderTweetDetailModal(tweet) {
        const content = document.getElementById('tweet-detail-content');
        if (!content) return;

        const processingFlags = [
            { key: 'cache_complete', label: 'Cache Complete' },
            { key: 'media_processed', label: 'Media Processed' },
            { key: 'categories_processed', label: 'Categories Processed' },
            { key: 'kb_item_created', label: 'KB Item Created' }
        ];

        content.innerHTML = `
            <div class="tweet-detail-layout">
                <div class="tweet-basic-info glass-panel-v3 glass-panel-v3--tertiary">
                    <h4>Basic Information</h4>
                    <div class="info-grid">
                        <div class="info-item">
                            <label>Tweet ID:</label>
                            <span>${tweet.tweet_id}</span>
                        </div>
                        <div class="info-item">
                            <label>Created:</label>
                            <span>${this.formatDate(tweet.created_at)}</span>
                        </div>
                        <div class="info-item">
                            <label>Updated:</label>
                            <span>${this.formatDate(tweet.updated_at)}</span>
                        </div>
                        <div class="info-item">
                            <label>Media Count:</label>
                            <span>${tweet.media_count || 0}</span>
                        </div>
                    </div>
                </div>

                <div class="tweet-content glass-panel-v3 glass-panel-v3--tertiary">
                    <h4>Content</h4>
                    <div class="content-text">${tweet.content || 'No content available'}</div>
                </div>

                <div class="tweet-categories glass-panel-v3 glass-panel-v3--tertiary">
                    <h4>Categories</h4>
                    <div class="category-info">
                        <div class="category-item">
                            <label>Main Category:</label>
                            <span>${tweet.main_category || 'Not set'}</span>
                        </div>
                        <div class="category-item">
                            <label>Sub Category:</label>
                            <span>${tweet.sub_category || 'Not set'}</span>
                        </div>
                    </div>
                </div>

                <div class="processing-flags glass-panel-v3 glass-panel-v3--tertiary">
                    <h4>Processing Status</h4>
                    <div class="flags-grid">
                        ${processingFlags.map(flag => `
                            <label class="glass-checkbox">
                                <input type="checkbox" 
                                       id="detail-${flag.key}" 
                                       ${tweet[flag.key] ? 'checked' : ''}
                                       onchange="tweetManagementManager.updateTweetFlag('${tweet.tweet_id}', '${flag.key}', this.checked)">
                                <span class="checkmark"></span>
                                ${flag.label}
                            </label>
                        `).join('')}
                    </div>
                </div>

                <div class="reprocessing-controls glass-panel-v3 glass-panel-v3--tertiary">
                    <h4>Reprocessing Controls</h4>
                    <div class="reprocess-buttons">
                        <button class="glass-button glass-button--warning" 
                                onclick="tweetManagementManager.reprocessTweet('${tweet.tweet_id}', 'pipeline')">
                            <i class="fas fa-redo"></i>
                            Reprocess Pipeline
                        </button>
                        <button class="glass-button glass-button--danger" 
                                onclick="tweetManagementManager.reprocessTweet('${tweet.tweet_id}', 'full')">
                            <i class="fas fa-sync"></i>
                            Full Recache
                        </button>
                    </div>
                </div>

                ${tweet.error_details ? `
                    <div class="error-details glass-panel-v3 glass-panel-v3--tertiary">
                        <h4>Error Details</h4>
                        <pre class="error-text">${tweet.error_details}</pre>
                    </div>
                ` : ''}
            </div>
        `;
    }

    async updateTweetFlag(tweetId, flagName, value) {
        try {
            const response = await fetch(`/api/v2/tweets/${tweetId}/update-flags`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ [flagName]: value })
            });

            if (!response.ok) throw new Error('Failed to update flag');

            this.showNotification(`Flag ${flagName} updated successfully`, 'success');
            this.loadTweets(); // Refresh the table
        } catch (error) {
            console.error('Error updating flag:', error);
            this.showNotification('Failed to update flag', 'error');
        }
    }

    async reprocessTweet(tweetId, type = 'pipeline') {
        try {
            const response = await fetch(`/api/v2/tweets/${tweetId}/reprocess`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ reprocess_type: type })
            });

            if (!response.ok) throw new Error('Failed to trigger reprocessing');

            this.showNotification(`Reprocessing ${type} triggered successfully`, 'success');
            this.loadTweets(); // Refresh the table
        } catch (error) {
            console.error('Error triggering reprocessing:', error);
            this.showNotification('Failed to trigger reprocessing', 'error');
        }
    }

    showBulkOperations() {
        if (this.selectedTweets.size === 0) {
            this.showNotification('Please select tweets first', 'warning');
            return;
        }

        this.renderBulkOperationsModal();
        this.showModal('bulk-operations-modal');
    }

    renderBulkOperationsModal() {
        const content = document.getElementById('bulk-operations-content');
        if (!content) return;

        content.innerHTML = `
            <div class="bulk-operations-layout">
                <div class="selection-summary glass-panel-v3 glass-panel-v3--tertiary">
                    <h4>Selected Tweets</h4>
                    <p>${this.selectedTweets.size} tweet(s) selected for bulk operation</p>
                </div>

                <div class="operation-selection glass-panel-v3 glass-panel-v3--tertiary">
                    <h4>Operation Type</h4>
                    <div class="operation-options">
                        <label class="glass-radio">
                            <input type="radio" name="bulk-operation" value="reprocess-pipeline" checked>
                            <span class="radio-mark"></span>
                            Reprocess Pipeline
                        </label>
                        <label class="glass-radio">
                            <input type="radio" name="bulk-operation" value="reprocess-full">
                            <span class="radio-mark"></span>
                            Full Recache
                        </label>
                        <label class="glass-radio">
                            <input type="radio" name="bulk-operation" value="update-flags">
                            <span class="radio-mark"></span>
                            Update Flags
                        </label>
                        <label class="glass-radio">
                            <input type="radio" name="bulk-operation" value="delete">
                            <span class="radio-mark"></span>
                            Delete Tweets
                        </label>
                    </div>
                </div>

                <div class="operation-details glass-panel-v3 glass-panel-v3--tertiary" id="bulk-operation-details">
                    <!-- Operation-specific details will be populated here -->
                </div>
            </div>
        `;

        // Setup operation type change handler
        const radioButtons = content.querySelectorAll('input[name="bulk-operation"]');
        radioButtons.forEach(radio => {
            this.addEventListener(radio, 'change', () => {
                this.updateBulkOperationDetails(radio.value);
            });
        });

        // Initialize with first operation
        this.updateBulkOperationDetails('reprocess-pipeline');
    }

    updateBulkOperationDetails(operationType) {
        const detailsContainer = document.getElementById('bulk-operation-details');
        if (!detailsContainer) return;

        switch (operationType) {
            case 'reprocess-pipeline':
                detailsContainer.innerHTML = `
                    <h4>Reprocess Pipeline</h4>
                    <p>This will trigger reprocessing for the selected tweets without clearing the cache.</p>
                `;
                break;
            case 'reprocess-full':
                detailsContainer.innerHTML = `
                    <h4>Full Recache</h4>
                    <p class="warning-text">This will clear all processing flags and trigger a complete recache of the selected tweets.</p>
                `;
                break;
            case 'update-flags':
                detailsContainer.innerHTML = `
                    <h4>Update Processing Flags</h4>
                    <div class="flag-updates">
                        <label class="glass-checkbox">
                            <input type="checkbox" id="bulk-cache-complete">
                            <span class="checkmark"></span>
                            Cache Complete
                        </label>
                        <label class="glass-checkbox">
                            <input type="checkbox" id="bulk-media-processed">
                            <span class="checkmark"></span>
                            Media Processed
                        </label>
                        <label class="glass-checkbox">
                            <input type="checkbox" id="bulk-categories-processed">
                            <span class="checkmark"></span>
                            Categories Processed
                        </label>
                        <label class="glass-checkbox">
                            <input type="checkbox" id="bulk-kb-item-created">
                            <span class="checkmark"></span>
                            KB Item Created
                        </label>
                    </div>
                `;
                break;
            case 'delete':
                detailsContainer.innerHTML = `
                    <h4>Delete Tweets</h4>
                    <p class="danger-text">This will permanently delete the selected tweets from the database. This action cannot be undone.</p>
                    <label class="glass-checkbox">
                        <input type="checkbox" id="confirm-delete" required>
                        <span class="checkmark"></span>
                        I understand this action is permanent
                    </label>
                `;
                break;
        }
    }

    async executeBulkOperation() {
        const operationType = document.querySelector('input[name="bulk-operation"]:checked')?.value;
        if (!operationType) return;

        const tweetIds = Array.from(this.selectedTweets);
        
        try {
            let payload = { tweet_ids: tweetIds, operation: operationType };

            // Add operation-specific data
            if (operationType === 'update-flags') {
                const flags = {};
                ['cache-complete', 'media-processed', 'categories-processed', 'kb-item-created']
                    .forEach(flagId => {
                        const checkbox = document.getElementById(`bulk-${flagId}`);
                        if (checkbox?.checked) {
                            flags[flagId.replace(/-/g, '_')] = true;
                        }
                    });
                payload.flags = flags;
            } else if (operationType === 'delete') {
                const confirmCheckbox = document.getElementById('confirm-delete');
                if (!confirmCheckbox?.checked) {
                    this.showNotification('Please confirm the deletion', 'warning');
                    return;
                }
            }

            const response = await fetch('/api/v2/tweets/bulk-operations', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!response.ok) throw new Error('Bulk operation failed');

            const result = await response.json();
            this.showNotification(`Bulk operation completed: ${result.success_count} successful`, 'success');
            
            this.hideModal('bulk-operations-modal');
            this.selectedTweets.clear();
            this.loadTweets();

        } catch (error) {
            console.error('Error executing bulk operation:', error);
            this.showNotification('Bulk operation failed', 'error');
        }
    }

    async showStatistics() {
        try {
            const response = await fetch('/api/v2/tweets/statistics');
            if (!response.ok) throw new Error('Failed to load statistics');

            const stats = await response.json();
            this.renderStatisticsModal(stats);
            this.showModal('statistics-modal');
        } catch (error) {
            console.error('Error loading statistics:', error);
            this.showNotification('Failed to load statistics', 'error');
        }
    }

    renderStatisticsModal(stats) {
        const content = document.getElementById('statistics-content');
        if (!content) return;

        content.innerHTML = `
            <div class="statistics-layout">
                <div class="stats-overview glass-panel-v3 glass-panel-v3--tertiary">
                    <h4>Overview</h4>
                    <div class="stats-grid">
                        <div class="stat-card">
                            <div class="stat-value">${stats.total_tweets?.toLocaleString() || 0}</div>
                            <div class="stat-label">Total Tweets</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-value">${stats.processed_tweets?.toLocaleString() || 0}</div>
                            <div class="stat-label">Fully Processed</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-value">${stats.pending_tweets?.toLocaleString() || 0}</div>
                            <div class="stat-label">Pending</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-value">${stats.error_tweets?.toLocaleString() || 0}</div>
                            <div class="stat-label">With Errors</div>
                        </div>
                    </div>
                </div>

                <div class="processing-stats glass-panel-v3 glass-panel-v3--tertiary">
                    <h4>Processing Statistics</h4>
                    <div class="processing-breakdown">
                        <div class="processing-item">
                            <span>Cache Complete:</span>
                            <span>${stats.cache_complete?.toLocaleString() || 0}</span>
                        </div>
                        <div class="processing-item">
                            <span>Media Processed:</span>
                            <span>${stats.media_processed?.toLocaleString() || 0}</span>
                        </div>
                        <div class="processing-item">
                            <span>Categories Processed:</span>
                            <span>${stats.categories_processed?.toLocaleString() || 0}</span>
                        </div>
                        <div class="processing-item">
                            <span>KB Items Created:</span>
                            <span>${stats.kb_items_created?.toLocaleString() || 0}</span>
                        </div>
                    </div>
                </div>

                <div class="category-stats glass-panel-v3 glass-panel-v3--tertiary">
                    <h4>Category Distribution</h4>
                    <div class="category-breakdown">
                        ${(stats.category_distribution || []).map(cat => `
                            <div class="category-item">
                                <span>${cat.main_category} > ${cat.sub_category}:</span>
                                <span>${cat.count?.toLocaleString() || 0}</span>
                            </div>
                        `).join('')}
                    </div>
                </div>

                <div class="queue-stats glass-panel-v3 glass-panel-v3--tertiary">
                    <h4>Processing Queue</h4>
                    <div class="queue-breakdown">
                        <div class="queue-item">
                            <span>Unprocessed:</span>
                            <span>${stats.unprocessed_queue?.toLocaleString() || 0}</span>
                        </div>
                        <div class="queue-item">
                            <span>In Progress:</span>
                            <span>${stats.processing_queue?.toLocaleString() || 0}</span>
                        </div>
                        <div class="queue-item">
                            <span>Completed:</span>
                            <span>${stats.completed_queue?.toLocaleString() || 0}</span>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    showModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.style.display = 'flex';
            document.body.style.overflow = 'hidden';
        }
    }

    hideModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.style.display = 'none';
            document.body.style.overflow = '';
        }
    }

    showNotification(message, type = 'info') {
        // Use existing notification system if available
        if (window.uiManager && window.uiManager.showNotification) {
            window.uiManager.showNotification(message, type);
        } else {
            // Fallback to console logging
            console.log(`${type.toUpperCase()}: ${message}`);
        }
    }

    destroy() {
        this.removeEventListeners();
        this.selectedTweets.clear();
        this.initialized = false;
        
        // Clear any pending timers
        if (this.searchDebounceTimer) clearTimeout(this.searchDebounceTimer);
        if (this.filterDebounceTimer) clearTimeout(this.filterDebounceTimer);
    }
}

// Global instance
let tweetManagementManager = null;

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('tweet-management-panel')) {
        tweetManagementManager = new TweetManagementManager();
        tweetManagementManager.init();
    }
});

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = TweetManagementManager;
} 

// Make sure the class is available globally
window.TweetManagementManager = TweetManagementManager;
console.log('🐦 TweetManagementManager class loaded and available globally:', !!window.TweetManagementManager); 
/**
 * Modern Tweet Management Interface
 * 
 * Features:
 * - View all tweets stored in the unified database
 * - Processing status visualization
 * - Reprocessing controls for individual tweets
 * - Bulk operations for multiple tweets
 * - Advanced filtering and search
 * - Processing pipeline status tracking
 */

class ModernTweetManager extends BaseManager {
    constructor(options = {}) {
        super({
            enableLogging: true,
            autoInit: false,
            componentName: 'ModernTweetManager',
            ...options
        });
        
        // Tweet management state
        this.tweets = new Map();
        this.filteredTweets = [];
        this.selectedTweets = new Set();
        this.currentFilter = {
            status: 'all',
            category: 'all',
            search: '',
            sortBy: 'updated',
            sortOrder: 'desc'
        };
        
        // Processing statistics
        this.stats = {
            total: 0,
            cached: 0,
            processed: 0,
            errors: 0,
            pending: 0
        };
    }
    
    async initializeElements() {
        this.elements.container = document.getElementById('main-content');
        if (!this.elements.container) {
            throw new Error('Main content container not found');
        }
        
        await this.createTweetManagementInterface();
        
        // Cache interactive elements
        this.elements.searchInput = document.getElementById('tweet-search');
        this.elements.statusFilter = document.getElementById('status-filter');
        this.elements.categoryFilter = document.getElementById('category-filter');
        this.elements.sortSelect = document.getElementById('sort-select');
        this.elements.tweetsTable = document.getElementById('tweets-table');
        this.elements.selectAllBtn = document.getElementById('select-all-btn');
        this.elements.bulkActionsBtn = document.getElementById('bulk-actions-btn');
        this.elements.refreshBtn = document.getElementById('refresh-btn');
        this.elements.statsContainer = document.getElementById('stats-container');
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
                    selector: this.elements.statusFilter,
                    events: ['change'],
                    handler: this.handleStatusFilter
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
                    selector: this.elements.selectAllBtn,
                    handler: this.handleSelectAll
                },
                {
                    selector: this.elements.bulkActionsBtn,
                    handler: this.handleBulkActions
                },
                {
                    selector: this.elements.refreshBtn,
                    handler: this.handleRefresh,
                    debounce: 1000
                }
            ],
            
            delegated: [
                {
                    container: this.elements.tweetsTable,
                    selector: '.tweet-checkbox',
                    event: 'change',
                    handler: this.handleTweetSelection
                },
                {
                    container: this.elements.tweetsTable,
                    selector: '.reprocess-btn',
                    event: 'click',
                    handler: this.handleReprocessTweet
                },
                {
                    container: this.elements.tweetsTable,
                    selector: '.view-details-btn',
                    event: 'click',
                    handler: this.handleViewDetails
                }
            ]
        });
    }
    
    async loadInitialData() {
        try {
            this.showLoadingState();
            
            // Load tweets from the unified database
            await this.loadTweets();
            
            // Calculate statistics
            this.calculateStats();
            
            // Apply initial filtering and display
            this.applyFilters();
            this.updateStatsDisplay();
            
            this.setState({ 
                initialized: true,
                loading: false 
            });
            
        } catch (error) {
            this.setError(error, 'loading tweet data');
            this.showEmptyState('Failed to load tweet data');
        }
    }
    
    async createTweetManagementInterface() {
        this.elements.container.innerHTML = `
            <div class="modern-tweet-container glass-panel-v3 animate-glass-fade-in">
                <!-- Header -->
                <header class="tweet-header">
                    <div class="header-title">
                        <h1>
                            <i class="fab fa-twitter"></i>
                            Tweet Management
                        </h1>
                        <p class="header-subtitle">Manage and reprocess your tweet collection</p>
                    </div>
                    
                    <div class="header-actions">
                        <button id="refresh-btn" class="glass-button glass-button--small" title="Refresh Data">
                            <i class="fas fa-sync-alt"></i>
                        </button>
                        <button id="bulk-actions-btn" class="glass-button glass-button--small" title="Bulk Actions" disabled>
                            <i class="fas fa-tasks"></i>
                            <span>Actions</span>
                        </button>
                    </div>
                </header>
                
                <!-- Statistics -->
                <div id="stats-container" class="tweet-stats glass-panel-v3--secondary">
                    <div class="stat-item">
                        <div class="stat-icon">
                            <i class="fas fa-database"></i>
                        </div>
                        <div class="stat-content">
                            <div class="stat-value" id="total-tweets">--</div>
                            <div class="stat-label">Total Tweets</div>
                        </div>
                    </div>
                    
                    <div class="stat-item">
                        <div class="stat-icon success">
                            <i class="fas fa-check-circle"></i>
                        </div>
                        <div class="stat-content">
                            <div class="stat-value" id="processed-tweets">--</div>
                            <div class="stat-label">Fully Processed</div>
                        </div>
                    </div>
                    
                    <div class="stat-item">
                        <div class="stat-icon warning">
                            <i class="fas fa-clock"></i>
                        </div>
                        <div class="stat-content">
                            <div class="stat-value" id="pending-tweets">--</div>
                            <div class="stat-label">Pending</div>
                        </div>
                    </div>
                    
                    <div class="stat-item">
                        <div class="stat-icon error">
                            <i class="fas fa-exclamation-triangle"></i>
                        </div>
                        <div class="stat-content">
                            <div class="stat-value" id="error-tweets">--</div>
                            <div class="stat-label">Errors</div>
                        </div>
                    </div>
                </div>
                
                <!-- Controls -->
                <div class="tweet-controls glass-panel-v3--secondary">
                    <div class="controls-left">
                        <div class="search-container">
                            <i class="fas fa-search"></i>
                            <input 
                                type="text" 
                                id="tweet-search" 
                                placeholder="Search tweets..."
                                class="glass-input"
                            >
                        </div>
                        
                        <select id="status-filter" class="glass-select">
                            <option value="all">All Status</option>
                            <option value="complete">Fully Processed</option>
                            <option value="pending">Pending Processing</option>
                            <option value="error">Has Errors</option>
                            <option value="cached">Cached Only</option>
                        </select>
                        
                        <select id="category-filter" class="glass-select">
                            <option value="all">All Categories</option>
                        </select>
                    </div>
                    
                    <div class="controls-right">
                        <select id="sort-select" class="glass-select">
                            <option value="updated-desc">Recently Updated</option>
                            <option value="updated-asc">Oldest First</option>
                            <option value="created-desc">Recently Added</option>
                            <option value="created-asc">Oldest Added</option>
                            <option value="status-asc">Status A-Z</option>
                        </select>
                        
                        <button id="select-all-btn" class="glass-button glass-button--small">
                            <i class="fas fa-check-square"></i>
                            Select All
                        </button>
                    </div>
                </div>
                
                <!-- Content -->
                <div class="tweet-content">
                    <!-- Loading State -->
                    <div id="loading-state" class="loading-state">
                        <div class="loading-spinner"></div>
                        <span>Loading tweets...</span>
                    </div>
                    
                    <!-- Empty State -->
                    <div id="empty-state" class="empty-state hidden">
                        <i class="fab fa-twitter"></i>
                        <h3>No tweets found</h3>
                        <p>Try adjusting your search or filter criteria</p>
                    </div>
                    
                    <!-- Tweets Table -->
                    <div class="tweets-table-container">
                        <table id="tweets-table" class="tweets-table">
                            <thead>
                                <tr>
                                    <th class="select-column">
                                        <input type="checkbox" id="header-checkbox" class="tweet-checkbox">
                                    </th>
                                    <th class="tweet-column">Tweet</th>
                                    <th class="status-column">Processing Status</th>
                                    <th class="category-column">Category</th>
                                    <th class="date-column">Last Updated</th>
                                    <th class="actions-column">Actions</th>
                                </tr>
                            </thead>
                            <tbody id="tweets-tbody">
                                <!-- Tweets will be populated here -->
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
            
            <!-- Tweet Details Modal -->
            <div id="tweet-details-modal" class="tweet-modal hidden">
                <div class="modal-overlay"></div>
                <div class="modal-content">
                    <div class="modal-header">
                        <h3>Tweet Details</h3>
                        <button class="modal-close-btn">
                            <i class="fas fa-times"></i>
                        </button>
                    </div>
                    <div class="modal-body">
                        <!-- Tweet details will be populated here -->
                    </div>
                    <div class="modal-footer">
                        <button class="modal-btn secondary">Close</button>
                        <button class="modal-btn primary reprocess-modal-btn">Reprocess Tweet</button>
                    </div>
                </div>
            </div>
        `;
    }
    
    async loadTweets() {
        try {
            // CRITICAL FIX: Use the correct API endpoint for unified tweet model
            const response = await this.apiCall('/tweets/all', {
                errorMessage: 'Failed to load tweets',
                cache: false
            });
            
            this.tweets.clear();
            
            // Handle different response formats
            let tweets = [];
            if (Array.isArray(response)) {
                tweets = response;
            } else if (response && response.tweets && Array.isArray(response.tweets)) {
                tweets = response.tweets;
            } else if (response && response.data && Array.isArray(response.data)) {
                tweets = response.data;
            }
            
            tweets.forEach(tweet => {
                this.tweets.set(tweet.tweet_id || tweet.id, tweet);
            });
            
            this.log(`Loaded ${this.tweets.size} tweets from unified database`);
            this.updateCategoryFilter();
            
        } catch (error) {
            this.logError('Failed to load tweets:', error);
            // Try fallback endpoint
            try {
                this.logWarn('Trying fallback tweet endpoint...');
                const fallbackResponse = await this.apiCall('/tweets', {
                    errorMessage: 'Failed to load tweets from fallback endpoint',
                    cache: false
                });
                
                if (Array.isArray(fallbackResponse)) {
                    fallbackResponse.forEach(tweet => {
                        this.tweets.set(tweet.tweet_id || tweet.id, tweet);
                    });
                    this.log(`Loaded ${this.tweets.size} tweets from fallback endpoint`);
                } else {
                    throw new Error('No tweets found in fallback response');
                }
            } catch (fallbackError) {
                this.logError('Fallback tweet loading also failed:', fallbackError);
                throw error; // Throw original error
            }
        }
    }
    
    updateCategoryFilter() {
        if (!this.elements.categoryFilter) return;
        
        const categories = new Set();
        this.tweets.forEach(tweet => {
            const category = tweet.main_category || 'Uncategorized';
            categories.add(category);
        });
        
        const options = ['<option value="all">All Categories</option>'];
        
        Array.from(categories)
            .sort()
            .forEach(category => {
                const count = Array.from(this.tweets.values())
                    .filter(t => (t.main_category || 'Uncategorized') === category).length;
                options.push(`
                    <option value="${category}">
                        ${category} (${count})
                    </option>
                `);
            });
        
        this.elements.categoryFilter.innerHTML = options.join('');
    }
    
    calculateStats() {
        this.stats = {
            total: this.tweets.size,
            cached: 0,
            processed: 0,
            errors: 0,
            pending: 0
        };
        
        this.tweets.forEach(tweet => {
            if (tweet.processing_complete) {
                this.stats.processed++;
            } else if (tweet.cache_complete) {
                this.stats.cached++;
            } else {
                this.stats.pending++;
            }
            
            if (tweet.kbitem_error || tweet.llm_error) {
                this.stats.errors++;
            }
        });
    }
    
    updateStatsDisplay() {
        const elements = {
            total: document.getElementById('total-tweets'),
            processed: document.getElementById('processed-tweets'),
            pending: document.getElementById('pending-tweets'),
            errors: document.getElementById('error-tweets')
        };
        
        if (elements.total) elements.total.textContent = this.stats.total.toString();
        if (elements.processed) elements.processed.textContent = this.stats.processed.toString();
        if (elements.pending) elements.pending.textContent = this.stats.pending.toString();
        if (elements.errors) elements.errors.textContent = this.stats.errors.toString();
    }
    
    applyFilters() {
        let filtered = Array.from(this.tweets.values());
        
        // Apply status filter
        if (this.currentFilter.status !== 'all') {
            filtered = filtered.filter(tweet => {
                switch (this.currentFilter.status) {
                    case 'complete':
                        return tweet.processing_complete;
                    case 'pending':
                        return !tweet.processing_complete;
                    case 'error':
                        return tweet.kbitem_error || tweet.llm_error;
                    case 'cached':
                        return tweet.cache_complete && !tweet.processing_complete;
                    default:
                        return true;
                }
            });
        }
        
        // Apply category filter
        if (this.currentFilter.category !== 'all') {
            filtered = filtered.filter(tweet => 
                (tweet.main_category || 'Uncategorized') === this.currentFilter.category
            );
        }
        
        // Apply search filter
        if (this.currentFilter.search) {
            const searchTerm = this.currentFilter.search.toLowerCase();
            filtered = filtered.filter(tweet => 
                (tweet.full_text || '').toLowerCase().includes(searchTerm) ||
                (tweet.main_category || '').toLowerCase().includes(searchTerm) ||
                (tweet.sub_category || '').toLowerCase().includes(searchTerm) ||
                (tweet.tweet_id || '').toLowerCase().includes(searchTerm)
            );
        }
        
        // Apply sorting
        const [sortBy, sortOrder] = this.currentFilter.sortBy.split('-');
        filtered.sort((a, b) => {
            let aVal, bVal;
            
            switch (sortBy) {
                case 'created':
                    aVal = new Date(a.created_at || 0);
                    bVal = new Date(b.created_at || 0);
                    break;
                case 'updated':
                    aVal = new Date(a.updated_at || a.created_at || 0);
                    bVal = new Date(b.updated_at || b.created_at || 0);
                    break;
                case 'status':
                    aVal = this.getTweetStatusText(a);
                    bVal = this.getTweetStatusText(b);
                    break;
                default:
                    aVal = new Date(a.updated_at || a.created_at || 0);
                    bVal = new Date(b.updated_at || b.created_at || 0);
                    break;
            }
            
            const comparison = aVal < bVal ? -1 : aVal > bVal ? 1 : 0;
            return sortOrder === 'desc' ? -comparison : comparison;
        });
        
        this.filteredTweets = filtered;
        this.renderTweets();
    }
    
    renderTweets() {
        const tbody = document.getElementById('tweets-tbody');
        if (!tbody) return;
        
        if (this.filteredTweets.length === 0) {
            this.showEmptyState();
            return;
        }
        
        this.hideLoadingState();
        this.hideEmptyState();
        
        const tweetsHTML = this.filteredTweets.map(tweet => this.createTweetRowHTML(tweet)).join('');
        tbody.innerHTML = tweetsHTML;
    }
    
    createTweetRowHTML(tweet) {
        const statusInfo = this.getTweetStatusInfo(tweet);
        const category = tweet.main_category || 'Uncategorized';
        const subCategory = tweet.sub_category || '';
        const lastUpdated = this.formatDate(tweet.updated_at || tweet.created_at);
        const tweetPreview = this.createTweetPreview(tweet.full_text || '');
        
        return `
            <tr class="tweet-row" data-tweet-id="${tweet.tweet_id}">
                <td class="select-column">
                    <input type="checkbox" class="tweet-checkbox" data-tweet-id="${tweet.tweet_id}">
                </td>
                <td class="tweet-column">
                    <div class="tweet-preview">
                        <div class="tweet-id">${tweet.tweet_id}</div>
                        <div class="tweet-text">${tweetPreview}</div>
                        ${tweet.is_thread ? '<span class="thread-badge">Thread</span>' : ''}
                    </div>
                </td>
                <td class="status-column">
                    <div class="status-indicator ${statusInfo.class}">
                        <i class="${statusInfo.icon}"></i>
                        <span>${statusInfo.text}</span>
                    </div>
                    ${this.createProcessingStepsHTML(tweet)}
                </td>
                <td class="category-column">
                    <div class="category-info">
                        <div class="main-category">${category}</div>
                        ${subCategory ? `<div class="sub-category">${subCategory}</div>` : ''}
                    </div>
                </td>
                <td class="date-column">
                    <div class="date-info">
                        <div class="last-updated">${lastUpdated}</div>
                    </div>
                </td>
                <td class="actions-column">
                    <div class="action-buttons">
                        <button class="action-btn view-details-btn" data-tweet-id="${tweet.tweet_id}" title="View Details">
                            <i class="fas fa-eye"></i>
                        </button>
                        <button class="action-btn reprocess-btn" data-tweet-id="${tweet.tweet_id}" title="Reprocess">
                            <i class="fas fa-redo"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `;
    }
    
    getTweetStatusInfo(tweet) {
        if (tweet.processing_complete) {
            return {
                class: 'success',
                icon: 'fas fa-check-circle',
                text: 'Complete'
            };
        } else if (tweet.kbitem_error || tweet.llm_error) {
            return {
                class: 'error',
                icon: 'fas fa-exclamation-triangle',
                text: 'Error'
            };
        } else if (tweet.cache_complete) {
            return {
                class: 'warning',
                icon: 'fas fa-clock',
                text: 'Processing'
            };
        } else {
            return {
                class: 'pending',
                icon: 'fas fa-hourglass-start',
                text: 'Pending'
            };
        }
    }
    
    getTweetStatusText(tweet) {
        const statusInfo = this.getTweetStatusInfo(tweet);
        return statusInfo.text;
    }
    
    createProcessingStepsHTML(tweet) {
        const steps = [
            { key: 'cache_complete', label: 'Cache', icon: 'fas fa-download' },
            { key: 'media_processed', label: 'Media', icon: 'fas fa-image' },
            { key: 'categories_processed', label: 'Categories', icon: 'fas fa-tags' },
            { key: 'kb_item_created', label: 'KB Item', icon: 'fas fa-file-alt' }
        ];
        
        const stepsHTML = steps.map(step => {
            const isComplete = tweet[step.key];
            const stepClass = isComplete ? 'complete' : 'pending';
            
            return `
                <div class="processing-step ${stepClass}" title="${step.label}">
                    <i class="${step.icon}"></i>
                </div>
            `;
        }).join('');
        
        return `<div class="processing-steps">${stepsHTML}</div>`;
    }
    
    createTweetPreview(text) {
        if (!text) return 'No content available';
        
        const plainText = text
            .replace(/https?:\/\/[^\s]+/g, '[link]') // Replace URLs
            .replace(/\s+/g, ' ') // Normalize whitespace
            .trim();
        
        return plainText.length > 100 
            ? plainText.substring(0, 100) + '...'
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
        } else {
            return date.toLocaleDateString();
        }
    }
    
    showLoadingState() {
        const loadingState = document.getElementById('loading-state');
        const tableContainer = document.querySelector('.tweets-table-container');
        const emptyState = document.getElementById('empty-state');
        
        if (loadingState) loadingState.classList.remove('hidden');
        if (tableContainer) tableContainer.style.display = 'none';
        if (emptyState) emptyState.classList.add('hidden');
    }
    
    hideLoadingState() {
        const loadingState = document.getElementById('loading-state');
        const tableContainer = document.querySelector('.tweets-table-container');
        
        if (loadingState) loadingState.classList.add('hidden');
        if (tableContainer) tableContainer.style.display = 'block';
    }
    
    showEmptyState(message = null) {
        const emptyState = document.getElementById('empty-state');
        const tableContainer = document.querySelector('.tweets-table-container');
        const loadingState = document.getElementById('loading-state');
        
        if (emptyState) {
            emptyState.classList.remove('hidden');
            if (message) {
                const messageEl = emptyState.querySelector('p');
                if (messageEl) messageEl.textContent = message;
            }
        }
        if (tableContainer) tableContainer.style.display = 'none';
        if (loadingState) loadingState.classList.add('hidden');
    }
    
    hideEmptyState() {
        const emptyState = document.getElementById('empty-state');
        if (emptyState) emptyState.classList.add('hidden');
    }
    
    // Event Handlers
    handleSearch = (e) => {
        this.currentFilter.search = e.target.value.trim();
        this.applyFilters();
    }
    
    handleStatusFilter = (e) => {
        this.currentFilter.status = e.target.value;
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
    
    handleSelectAll = () => {
        const checkboxes = document.querySelectorAll('.tweet-checkbox:not(#header-checkbox)');
        const headerCheckbox = document.getElementById('header-checkbox');
        const isSelectingAll = !headerCheckbox.checked;
        
        checkboxes.forEach(checkbox => {
            checkbox.checked = isSelectingAll;
            const tweetId = checkbox.dataset.tweetId;
            if (isSelectingAll) {
                this.selectedTweets.add(tweetId);
            } else {
                this.selectedTweets.delete(tweetId);
            }
        });
        
        headerCheckbox.checked = isSelectingAll;
        this.updateBulkActionsButton();
    }
    
    handleTweetSelection = (e) => {
        const tweetId = e.target.dataset.tweetId;
        
        if (e.target.checked) {
            this.selectedTweets.add(tweetId);
        } else {
            this.selectedTweets.delete(tweetId);
        }
        
        this.updateBulkActionsButton();
        this.updateHeaderCheckbox();
    }
    
    updateBulkActionsButton() {
        if (this.elements.bulkActionsBtn) {
            this.elements.bulkActionsBtn.disabled = this.selectedTweets.size === 0;
            const span = this.elements.bulkActionsBtn.querySelector('span');
            if (span) {
                span.textContent = this.selectedTweets.size > 0 
                    ? `Actions (${this.selectedTweets.size})`
                    : 'Actions';
            }
        }
    }
    
    updateHeaderCheckbox() {
        const headerCheckbox = document.getElementById('header-checkbox');
        const totalCheckboxes = document.querySelectorAll('.tweet-checkbox:not(#header-checkbox)').length;
        
        if (headerCheckbox) {
            headerCheckbox.checked = this.selectedTweets.size === totalCheckboxes && totalCheckboxes > 0;
            headerCheckbox.indeterminate = this.selectedTweets.size > 0 && this.selectedTweets.size < totalCheckboxes;
        }
    }
    
    handleRefresh = async () => {
        await this.loadInitialData();
    }
    
    handleReprocessTweet = async (e) => {
        const tweetId = e.target.closest('.reprocess-btn').dataset.tweetId;
        await this.reprocessTweet(tweetId);
    }
    
    async reprocessTweet(tweetId) {
        try {
            const result = await this.apiCall(`/v2/tweets/${tweetId}/reprocess`, {
                method: 'POST',
                errorMessage: 'Failed to reprocess tweet',
                showLoading: true,
                loadingMessage: `Reprocessing tweet ${tweetId}...`
            });
            
            this.log(`Tweet ${tweetId} queued for reprocessing:`, result);
            
            // Show success message
            if (result && result.message) {
                // Could show a toast notification here
                console.log('Reprocess success:', result.message);
            }
            
            // Refresh the tweet data after a short delay to allow processing to start
            setTimeout(() => {
                this.handleRefresh();
            }, 1000);
            
        } catch (error) {
            this.setError(error, `reprocessing tweet ${tweetId}`);
        }
    }
    
    handleViewDetails = (e) => {
        const tweetId = e.target.closest('.view-details-btn').dataset.tweetId;
        this.showTweetDetails(tweetId);
    }
    
    showTweetDetails(tweetId) {
        const tweet = this.tweets.get(tweetId);
        if (!tweet) return;
        
        // This would open a modal with detailed tweet information
        console.log('Showing details for tweet:', tweet);
    }
    
    handleBulkActions = async () => {
        if (this.selectedTweets.size === 0) return;
        
        const selectedTweetIds = Array.from(this.selectedTweets);
        const confirmMessage = `Are you sure you want to reprocess ${selectedTweetIds.length} selected tweets?`;
        
        if (!confirm(confirmMessage)) return;
        
        try {
            this.log(`Starting bulk reprocessing of ${selectedTweetIds.length} tweets`);
            
            // Process tweets in batches to avoid overwhelming the server
            const batchSize = 5;
            const batches = [];
            for (let i = 0; i < selectedTweetIds.length; i += batchSize) {
                batches.push(selectedTweetIds.slice(i, i + batchSize));
            }
            
            let successCount = 0;
            let errorCount = 0;
            
            for (const batch of batches) {
                const batchPromises = batch.map(async (tweetId) => {
                    try {
                        await this.apiCall(`/v2/tweets/${tweetId}/reprocess`, {
                            method: 'POST',
                            errorMessage: `Failed to reprocess tweet ${tweetId}`
                        });
                        successCount++;
                        return { tweetId, success: true };
                    } catch (error) {
                        errorCount++;
                        this.logWarn(`Failed to reprocess tweet ${tweetId}:`, error);
                        return { tweetId, success: false, error };
                    }
                });
                
                await Promise.all(batchPromises);
                
                // Small delay between batches
                if (batches.indexOf(batch) < batches.length - 1) {
                    await new Promise(resolve => setTimeout(resolve, 500));
                }
            }
            
            this.log(`Bulk reprocessing completed: ${successCount} successful, ${errorCount} failed`);
            
            // Clear selections
            this.selectedTweets.clear();
            this.updateBulkActionsButton();
            this.updateHeaderCheckbox();
            
            // Refresh data after a delay
            setTimeout(() => {
                this.handleRefresh();
            }, 2000);
            
        } catch (error) {
            this.setError(error, 'bulk reprocessing tweets');
        }
    }
    
    cleanup() {
        this.cleanupService.cleanup(this);
    }
}

// Export for use in other modules
window.ModernTweetManager = ModernTweetManager;
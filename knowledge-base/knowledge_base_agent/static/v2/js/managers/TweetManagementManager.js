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
            console.log('🐦 Initializing Tweet Management Manager...');
            
            // Check if required DOM elements exist
            const panel = document.getElementById('tweet-management-panel');
            const tbody = document.getElementById('tweet-table-body');
            console.log('🐦 Panel found:', !!panel);
            console.log('🐦 Table body found:', !!tbody);
            
            // Load initial data
            console.log('🐦 Loading initial data...');
            await Promise.all([
                this.loadCategories(),
                this.loadTweets()
            ]);
            
            console.log('🐦 Setting up event listeners...');
            this.setupEventListeners();
            
            console.log('🐦 Updating UI...');
            this.updateUI();
            
            this.initialized = true;
            console.log('🐦 Tweet Management Manager initialized successfully');
        } catch (error) {
            console.error('🐦 Failed to initialize Tweet Management Manager:', error);
            this.showError('Failed to initialize tweet management interface');
        }
    }

    setupEventListeners() {
        // Refresh button
        const refreshBtn = document.getElementById('refresh-tweets-btn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.loadTweets(true));
        }

        // Set up table event delegation for buttons
        this.setupTableEventHandlers();
    }

    setupTableEventHandlers() {
        const tbody = document.getElementById('tweet-table-body');
        if (!tbody) return;

        // Use event delegation for dynamically created buttons
        tbody.addEventListener('click', (event) => {
            const target = event.target.closest('button');
            if (!target) return;

            const tweetId = target.dataset.tweetId;
            if (!tweetId) return;

            if (target.classList.contains('tweet-detail-btn')) {
                console.log('🔍 View details clicked for tweet:', tweetId);
                this.showTweetDetail(tweetId);
            } else if (target.classList.contains('tweet-reprocess-btn')) {
                console.log('🔄 Reprocess clicked for tweet:', tweetId);
                this.reprocessTweet(tweetId);
            }
        });

        // Handle checkbox changes
        tbody.addEventListener('change', (event) => {
            if (event.target.classList.contains('tweet-checkbox')) {
                const tweetId = event.target.dataset.tweetId;
                if (tweetId) {
                    this.toggleTweetSelection(tweetId);
                }
            }
        });
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
        } catch (error) {
            console.error('Error loading categories:', error);
        }
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

            console.log('🐦 Loading tweets with URL:', `/api/v2/tweets/explore?${params}`);
            const response = await fetch(`/api/v2/tweets/explore?${params}`);
            console.log('🐦 Tweets response status:', response.status);
            
            if (!response.ok) {
                const errorText = await response.text();
                console.error('🐦 API Error Response:', errorText);
                throw new Error(`Failed to load tweets: ${response.status} ${response.statusText}`);
            }

            const result = await response.json();
            console.log('🐦 Tweets API result:', result);
            
            if (!result.success) {
                throw new Error(result.error || 'API returned success: false');
            }
            
            const data = result.data || {};
            this.tweets = data.tweets || [];
            this.totalTweets = data.pagination?.total_count || 0;
            this.filteredTweets = data.pagination?.total_count || 0;
            
            console.log('🐦 Parsed tweets:', this.tweets.length, 'Total:', this.totalTweets);
            
            this.updateUI();
            this.hideLoading();
            
        } catch (error) {
            console.error('🐦 Error loading tweets:', error);
            this.showError(`Failed to load tweets: ${error.message}`);
            this.hideLoading();
        } finally {
            this.isLoading = false;
        }
    }

    updateUI() {
        this.renderTable();
    }

    renderTable() {
        console.log('🐦 renderTable called with', this.tweets.length, 'tweets');
        
        const tbody = document.getElementById('tweet-table-body');
        const emptyState = document.getElementById('empty-state');
        const tableWrapper = document.querySelector('.tweet-table-wrapper');

        if (!tbody) {
            console.error('🐦 tweet-table-body element not found!');
            return;
        }

        if (this.tweets.length === 0) {
            console.log('🐦 No tweets to display, showing empty state');
            tbody.innerHTML = '';
            if (tableWrapper) tableWrapper.style.display = 'none';
            if (emptyState) emptyState.style.display = 'block';
            return;
        }

        console.log('🐦 Rendering', this.tweets.length, 'tweets');
        if (tableWrapper) tableWrapper.style.display = 'block';
        if (emptyState) emptyState.style.display = 'none';

        try {
            const rows = this.tweets.map(tweet => this.renderTweetRow(tweet));
            tbody.innerHTML = rows.join('');
            console.log('🐦 Table rows rendered successfully');
        } catch (error) {
            console.error('🐦 Error rendering table rows:', error);
            this.showError(`Failed to render tweets: ${error.message}`);
        }
    }

    renderTweetRow(tweet) {
        const processing = tweet.processing_status || tweet;
        const status = this.getTweetStatus(tweet);
        const progress = this.calculateProgress(tweet);
        const mediaCount = tweet.media_count || 0;
        
        return `
            <tr data-tweet-id="${tweet.tweet_id}">
                <td class="select-col">
                    <input type="checkbox" class="tweet-checkbox" data-tweet-id="${tweet.tweet_id}">
                </td>
                <td class="tweet-id-col">
                    <button class="action-btn tweet-detail-btn" data-tweet-id="${tweet.tweet_id}">
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
                    ${tweet.main_category || 'Not set'} / ${tweet.sub_category || 'Not set'}
                </td>
                <td class="media-col">
                    ${mediaCount}
                </td>
                <td class="progress-col">
                    ${progress}%
                </td>
                <td class="updated-col">
                    ${this.formatDate(tweet.updated_at)}
                </td>
                <td class="actions-col">
                    <button class="action-btn tweet-detail-btn" data-tweet-id="${tweet.tweet_id}">
                        <i class="fas fa-eye"></i>
                    </button>
                    <button class="action-btn tweet-reprocess-btn" data-tweet-id="${tweet.tweet_id}">
                        <i class="fas fa-redo"></i>
                    </button>
                </td>
            </tr>
        `;
    }

    getTweetStatus(tweet) {
        const processing = tweet.processing_status || tweet;
        const hasErrors = tweet.last_error || tweet.has_errors;
        
        if (hasErrors) {
            return { type: 'error', icon: 'fas fa-exclamation-triangle', text: 'Error' };
        }
        
        if (processing.kb_item_created) {
            return { type: 'completed', icon: 'fas fa-check-circle', text: 'Complete' };
        }
        
        if (processing.cache_complete && (processing.media_processed || tweet.media_count === 0) && processing.categories_processed) {
            return { type: 'processing', icon: 'fas fa-cog fa-spin', text: 'Processing' };
        }
        
        return { type: 'pending', icon: 'fas fa-clock', text: 'Pending' };
    }

    calculateProgress(tweet) {
        const processing = tweet.processing_status || tweet;
        let progress = 0;
        const totalSteps = 4;
        
        if (processing.cache_complete) progress++;
        if (processing.media_processed || tweet.media_count === 0) progress++;
        if (processing.categories_processed) progress++;
        if (processing.kb_item_created) progress++;
        
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
        console.error('🐦 TweetManagementManager Error:', message);
        
        const errorState = document.getElementById('error-state');
        const errorDescription = document.getElementById('error-description');
        const tableWrapper = document.querySelector('.tweet-table-wrapper');
        const emptyState = document.getElementById('empty-state');
        const loadingState = document.getElementById('tweet-loading');
        
        // Hide other states
        if (tableWrapper) tableWrapper.style.display = 'none';
        if (emptyState) emptyState.style.display = 'none';
        if (loadingState) loadingState.style.display = 'none';
        
        // Show error state
        if (errorState) {
            errorState.style.display = 'block';
            if (errorDescription) errorDescription.textContent = message;
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

    toggleTweetSelection(tweetId) {
        if (this.selectedTweets.has(tweetId)) {
            this.selectedTweets.delete(tweetId);
        } else {
            this.selectedTweets.add(tweetId);
        }
        console.log('🐦 Selected tweets:', this.selectedTweets.size);
    }

    async showTweetDetail(tweetId) {
        try {
            console.log('🔍 Loading tweet details for:', tweetId);
            const response = await fetch(`/api/v2/tweets/${tweetId}/detail`);
            if (!response.ok) throw new Error('Failed to load tweet details');

            const result = await response.json();
            console.log('🔍 Tweet details loaded:', result);
            
            // For now, just show an alert with basic info
            const tweet = result.data;
            alert(`Tweet Details:
ID: ${tweet.tweet_id}
Title: ${tweet.display_title || 'No title'}
Category: ${tweet.main_category || 'Not set'} / ${tweet.sub_category || 'Not set'}
Status: Cache: ${tweet.processing_status?.cache_complete ? '✅' : '❌'}, Media: ${tweet.processing_status?.media_processed ? '✅' : '❌'}, Categories: ${tweet.processing_status?.categories_processed ? '✅' : '❌'}, KB Item: ${tweet.processing_status?.kb_item_created ? '✅' : '❌'}`);
            
        } catch (error) {
            console.error('🔍 Error loading tweet details:', error);
            this.showNotification('Failed to load tweet details', 'error');
        }
    }

    async reprocessTweet(tweetId, type = 'pipeline') {
        try {
            console.log('🔄 Reprocessing tweet:', tweetId, 'type:', type);
            
            // Set the reprocessing flag
            const flagResponse = await fetch(`/api/v2/tweets/${tweetId}/update-flags`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    force_reprocess_pipeline: true
                })
            });

            if (!flagResponse.ok) {
                throw new Error('Failed to set reprocessing flag');
            }

            // Trigger the actual reprocessing
            const response = await fetch(`/api/v2/tweets/${tweetId}/reprocess`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ reprocess_type: type })
            });

            if (!response.ok) throw new Error('Failed to trigger reprocessing');

            const result = await response.json();
            console.log('🔄 Reprocessing result:', result);
            this.showNotification(`Tweet marked for ${type} reprocessing`, 'success');
            
            // Refresh the table to show changes
            this.loadTweets();
            
        } catch (error) {
            console.error('🔄 Error triggering reprocessing:', error);
            this.showNotification('Failed to trigger reprocessing', 'error');
        }
    }

    // Stub methods for compatibility
    applyFilters() { console.log('applyFilters called'); }
    handleSearch() { console.log('handleSearch called'); }
    handleSort() { console.log('handleSort called'); }
    showStatistics() { console.log('showStatistics called'); }

    destroy() {
        this.initialized = false;
        if (this.searchDebounceTimer) clearTimeout(this.searchDebounceTimer);
        if (this.filterDebounceTimer) clearTimeout(this.filterDebounceTimer);
    }
}

// Global instance
let tweetManagementManager = null;

// Remove DOMContentLoaded initialization - let UI manager handle it

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = TweetManagementManager;
} 

// Make sure the class is available globally
window.TweetManagementManager = TweetManagementManager;
console.log('🐦 TweetManagementManager class loaded and available globally:', !!window.TweetManagementManager);
/**
 * Enhanced API Service
 * Eliminates duplicate fetch() calls across 10+ files
 * Provides centralized error handling, loading states, retry logic, and caching
 * 
 * Design Principles:
 * - Centralized error handling with user-friendly messages
 * - Automatic loading state management
 * - Request/response interceptors for transformation
 * - Intelligent retry logic with exponential backoff
 * - Request caching for performance optimization
 * - Comprehensive logging and debugging support
 */
class EnhancedAPIService {
    constructor(options = {}) {
        this.baseURL = options.baseURL || '/api';
        this.timeout = options.timeout || 30000; // 30 seconds default
        this.retryAttempts = options.retryAttempts || 3;
        this.retryDelay = options.retryDelay || 1000; // 1 second base delay
        this.enableCaching = options.enableCaching !== false;
        this.enableLogging = options.enableLogging !== false;
        
        // Request/Response interceptors
        this.requestInterceptors = [];
        this.responseInterceptors = [];
        this.errorInterceptors = [];
        
        // Cache management
        this.cache = new Map();
        this.cacheExpiry = new Map();
        this.defaultCacheTTL = options.defaultCacheTTL || 300000; // 5 minutes
        
        // Loading state management
        this.loadingStates = new Map();
        this.loadingCallbacks = new Map();
        
        // Request tracking
        this.activeRequests = new Map();
        this.requestId = 0;
        
        // Error handling
        this.globalErrorHandler = null;
        this.notificationSystem = null;
        
        // Initialize default interceptors
        this.setupDefaultInterceptors();
    }

    /**
     * Setup default request/response interceptors
     */
    setupDefaultInterceptors() {
        // Default request interceptor - add common headers and logging
        this.addRequestInterceptor((config) => {
            if (this.enableLogging) {
                console.log(`🌐 API Request: ${config.method} ${config.url}`, config);
            }
            
            // Add common headers
            config.headers = {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest',
                ...config.headers
            };
            
            return config;
        });

        // Default response interceptor - handle common response patterns
        this.addResponseInterceptor((response, config) => {
            if (this.enableLogging) {
                console.log(`✅ API Response: ${config.method} ${config.url}`, response);
            }
            
            return response;
        });

        // Default error interceptor - handle common error patterns
        this.addErrorInterceptor((error, config) => {
            if (this.enableLogging) {
                console.error(`❌ API Error: ${config.method} ${config.url}`, error);
            }
            
            // Show user-friendly error notifications
            this.showErrorNotification(error, config);
            
            return Promise.reject(error);
        });
    }

    /**
     * Add request interceptor
     * @param {Function} interceptor - Function to modify request config
     */
    addRequestInterceptor(interceptor) {
        this.requestInterceptors.push(interceptor);
    }

    /**
     * Add response interceptor
     * @param {Function} interceptor - Function to modify response data
     */
    addResponseInterceptor(interceptor) {
        this.responseInterceptors.push(interceptor);
    }

    /**
     * Add error interceptor
     * @param {Function} interceptor - Function to handle errors
     */
    addErrorInterceptor(interceptor) {
        this.errorInterceptors.push(interceptor);
    }

    /**
     * Set global error handler
     * @param {Function} handler - Global error handler function
     */
    setGlobalErrorHandler(handler) {
        this.globalErrorHandler = handler;
    }

    /**
     * Set notification system for user feedback
     * @param {Object} notificationSystem - Notification system instance
     */
    setNotificationSystem(notificationSystem) {
        this.notificationSystem = notificationSystem;
    }

    /**
     * Main request method with comprehensive error handling and features
     * @param {string} endpoint - API endpoint
     * @param {Object} options - Request options
     * @returns {Promise} Response data
     */
    async request(endpoint, options = {}) {
        const requestId = ++this.requestId;
        const config = this.buildRequestConfig(endpoint, options, requestId);
        
        try {
            // Check cache first
            if (this.shouldUseCache(config)) {
                const cachedResponse = this.getCachedResponse(config.cacheKey);
                if (cachedResponse) {
                    if (this.enableLogging) {
                        console.log(`💾 Cache Hit: ${config.method} ${config.url}`);
                    }
                    return cachedResponse;
                }
            }

            // Apply request interceptors
            const processedConfig = await this.applyRequestInterceptors(config);
            
            // Set loading state
            this.setLoadingState(processedConfig.loadingKey, true);
            
            // Make request with retry logic
            const response = await this.makeRequestWithRetry(processedConfig);
            
            // Apply response interceptors
            const processedResponse = await this.applyResponseInterceptors(response, processedConfig);
            
            // Cache response if applicable
            if (this.shouldCacheResponse(processedConfig)) {
                this.cacheResponse(processedConfig.cacheKey, processedResponse, processedConfig.cacheTTL);
            }
            
            return processedResponse;
            
        } catch (error) {
            // Apply error interceptors
            await this.applyErrorInterceptors(error, config);
            throw error;
            
        } finally {
            // Clear loading state
            this.setLoadingState(config.loadingKey, false);
            
            // Clean up active request tracking
            this.activeRequests.delete(requestId);
        }
    }

    /**
     * Build comprehensive request configuration
     */
    buildRequestConfig(endpoint, options, requestId) {
        const url = endpoint.startsWith('http') ? endpoint : `${this.baseURL}${endpoint}`;
        
        const config = {
            requestId,
            url,
            endpoint,
            method: options.method || 'GET',
            headers: { ...options.headers },
            body: options.body,
            timeout: options.timeout || this.timeout,
            retryAttempts: options.retryAttempts ?? this.retryAttempts,
            retryDelay: options.retryDelay || this.retryDelay,
            
            // Caching options
            cache: options.cache !== false && this.enableCaching,
            cacheTTL: options.cacheTTL || this.defaultCacheTTL,
            cacheKey: options.cacheKey || this.generateCacheKey(url, options),
            
            // Loading state options
            showLoading: options.showLoading !== false,
            loadingKey: options.loadingKey || `${options.method || 'GET'}_${endpoint}`,
            loadingMessage: options.loadingMessage,
            
            // Error handling options
            showErrors: options.showErrors !== false,
            errorMessage: options.errorMessage,
            
            // Transform options
            transformRequest: options.transformRequest,
            transformResponse: options.transformResponse,
            
            // Validation options
            validateResponse: options.validateResponse,
            
            // Original options for reference
            originalOptions: options
        };
        
        return config;
    }

    /**
     * Make request with retry logic and timeout handling
     */
    async makeRequestWithRetry(config, attempt = 1) {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), config.timeout);
        
        try {
            // Track active request
            this.activeRequests.set(config.requestId, { config, controller });
            
            // Prepare fetch options
            const fetchOptions = {
                method: config.method,
                headers: config.headers,
                signal: controller.signal
            };
            
            // Add body for non-GET requests
            if (config.body && config.method !== 'GET') {
                fetchOptions.body = typeof config.body === 'string' 
                    ? config.body 
                    : JSON.stringify(config.body);
            }
            
            // Make the request
            const response = await fetch(config.url, fetchOptions);
            
            // Clear timeout
            clearTimeout(timeoutId);
            
            // Handle HTTP errors
            if (!response.ok) {
                const error = await this.createHTTPError(response, config);
                throw error;
            }
            
            // Parse response
            const data = await this.parseResponse(response, config);
            
            return data;
            
        } catch (error) {
            clearTimeout(timeoutId);
            
            // Handle retry logic
            if (this.shouldRetry(error, config, attempt)) {
                const delay = this.calculateRetryDelay(attempt, config.retryDelay);
                
                if (this.enableLogging) {
                    console.warn(`🔄 Retrying request (${attempt}/${config.retryAttempts}) after ${delay}ms:`, config.url);
                }
                
                await this.delay(delay);
                return this.makeRequestWithRetry(config, attempt + 1);
            }
            
            throw error;
        }
    }

    /**
     * Parse response based on content type
     */
    async parseResponse(response, config) {
        const contentType = response.headers.get('content-type') || '';
        
        let data;
        if (contentType.includes('application/json')) {
            data = await response.json();
        } else if (contentType.includes('text/')) {
            data = await response.text();
        } else if (contentType.includes('application/octet-stream')) {
            data = await response.blob();
        } else {
            // Try JSON first, fallback to text
            try {
                data = await response.json();
            } catch {
                data = await response.text();
            }
        }
        
        // Apply response transformation
        if (config.transformResponse) {
            data = config.transformResponse(data, response, config);
        }
        
        // Apply response validation
        if (config.validateResponse) {
            const isValid = config.validateResponse(data, response, config);
            if (!isValid) {
                throw new Error('Response validation failed');
            }
        }
        
        return data;
    }

    /**
     * Create detailed HTTP error
     */
    async createHTTPError(response, config) {
        let errorData;
        try {
            const contentType = response.headers.get('content-type') || '';
            if (contentType.includes('application/json')) {
                errorData = await response.json();
            } else {
                errorData = await response.text();
            }
        } catch {
            errorData = response.statusText;
        }
        
        const error = new Error(`HTTP ${response.status}: ${response.statusText}`);
        error.status = response.status;
        error.statusText = response.statusText;
        error.response = response;
        error.data = errorData;
        error.config = config;
        error.isHTTPError = true;
        
        return error;
    }

    /**
     * Apply request interceptors
     */
    async applyRequestInterceptors(config) {
        let processedConfig = { ...config };
        
        for (const interceptor of this.requestInterceptors) {
            try {
                processedConfig = await interceptor(processedConfig) || processedConfig;
            } catch (error) {
                console.error('Request interceptor error:', error);
            }
        }
        
        return processedConfig;
    }

    /**
     * Apply response interceptors
     */
    async applyResponseInterceptors(response, config) {
        let processedResponse = response;
        
        for (const interceptor of this.responseInterceptors) {
            try {
                processedResponse = await interceptor(processedResponse, config) || processedResponse;
            } catch (error) {
                console.error('Response interceptor error:', error);
            }
        }
        
        return processedResponse;
    }

    /**
     * Apply error interceptors
     */
    async applyErrorInterceptors(error, config) {
        for (const interceptor of this.errorInterceptors) {
            try {
                await interceptor(error, config);
            } catch (interceptorError) {
                console.error('Error interceptor error:', interceptorError);
            }
        }
        
        // Call global error handler if set
        if (this.globalErrorHandler) {
            try {
                await this.globalErrorHandler(error, config);
            } catch (globalError) {
                console.error('Global error handler error:', globalError);
            }
        }
    }

    /**
     * Show user-friendly error notification
     */
    showErrorNotification(error, config) {
        if (!config.showErrors) return;
        
        let message = config.errorMessage;
        
        if (!message) {
            if (error.isHTTPError) {
                switch (error.status) {
                    case 400:
                        message = 'Invalid request. Please check your input.';
                        break;
                    case 401:
                        message = 'Authentication required. Please log in.';
                        break;
                    case 403:
                        message = 'Access denied. You don\'t have permission.';
                        break;
                    case 404:
                        message = 'Resource not found.';
                        break;
                    case 429:
                        message = 'Too many requests. Please try again later.';
                        break;
                    case 500:
                        message = 'Server error. Please try again later.';
                        break;
                    default:
                        message = `Request failed: ${error.message}`;
                }
            } else if (error.name === 'AbortError') {
                message = 'Request timed out. Please try again.';
            } else {
                message = 'Network error. Please check your connection.';
            }
        }
        
        // Show notification if system is available
        if (this.notificationSystem) {
            this.notificationSystem.error(message, {
                duration: 5000,
                actions: [
                    {
                        text: 'Retry',
                        action: () => this.request(config.endpoint, config.originalOptions)
                    }
                ]
            });
        } else {
            console.error('API Error:', message, error);
        }
    }

    /**
     * Loading state management
     */
    setLoadingState(key, isLoading) {
        if (!key) return;
        
        this.loadingStates.set(key, isLoading);
        
        // Trigger loading callbacks
        const callbacks = this.loadingCallbacks.get(key) || [];
        callbacks.forEach(callback => {
            try {
                callback(isLoading, key);
            } catch (error) {
                console.error('Loading callback error:', error);
            }
        });
        
        // Dispatch loading event
        document.dispatchEvent(new CustomEvent('api_loading_change', {
            detail: { key, isLoading }
        }));
    }

    /**
     * Subscribe to loading state changes
     */
    onLoadingChange(key, callback) {
        if (!this.loadingCallbacks.has(key)) {
            this.loadingCallbacks.set(key, []);
        }
        this.loadingCallbacks.get(key).push(callback);
        
        // Return unsubscribe function
        return () => {
            const callbacks = this.loadingCallbacks.get(key) || [];
            const index = callbacks.indexOf(callback);
            if (index > -1) {
                callbacks.splice(index, 1);
            }
        };
    }

    /**
     * Get current loading state
     */
    isLoading(key) {
        return this.loadingStates.get(key) || false;
    }

    /**
     * Cache management
     */
    shouldUseCache(config) {
        return config.cache && config.method === 'GET';
    }

    shouldCacheResponse(config) {
        return config.cache && config.method === 'GET';
    }

    generateCacheKey(url, options) {
        const key = `${options.method || 'GET'}_${url}`;
        if (options.body) {
            const bodyHash = this.hashCode(JSON.stringify(options.body));
            return `${key}_${bodyHash}`;
        }
        return key;
    }

    getCachedResponse(cacheKey) {
        if (!this.cache.has(cacheKey)) return null;
        
        const expiry = this.cacheExpiry.get(cacheKey);
        if (expiry && Date.now() > expiry) {
            this.cache.delete(cacheKey);
            this.cacheExpiry.delete(cacheKey);
            return null;
        }
        
        return this.cache.get(cacheKey);
    }

    cacheResponse(cacheKey, response, ttl) {
        this.cache.set(cacheKey, response);
        if (ttl > 0) {
            this.cacheExpiry.set(cacheKey, Date.now() + ttl);
        }
    }

    clearCache(pattern) {
        if (pattern) {
            // Clear cache entries matching pattern
            for (const key of this.cache.keys()) {
                if (key.includes(pattern)) {
                    this.cache.delete(key);
                    this.cacheExpiry.delete(key);
                }
            }
        } else {
            // Clear all cache
            this.cache.clear();
            this.cacheExpiry.clear();
        }
    }

    /**
     * Retry logic
     */
    shouldRetry(error, config, attempt) {
        if (attempt >= config.retryAttempts) return false;
        
        // Don't retry on client errors (4xx) except 429 (rate limit)
        if (error.isHTTPError && error.status >= 400 && error.status < 500 && error.status !== 429) {
            return false;
        }
        
        // Don't retry on abort errors (user cancelled)
        if (error.name === 'AbortError') return false;
        
        return true;
    }

    calculateRetryDelay(attempt, baseDelay) {
        // Exponential backoff with jitter
        const exponentialDelay = baseDelay * Math.pow(2, attempt - 1);
        const jitter = Math.random() * 0.1 * exponentialDelay;
        return Math.min(exponentialDelay + jitter, 30000); // Max 30 seconds
    }

    /**
     * Utility methods
     */
    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    hashCode(str) {
        let hash = 0;
        for (let i = 0; i < str.length; i++) {
            const char = str.charCodeAt(i);
            hash = ((hash << 5) - hash) + char;
            hash = hash & hash; // Convert to 32-bit integer
        }
        return hash.toString();
    }

    /**
     * Cancel all active requests
     */
    cancelAllRequests() {
        for (const [requestId, { controller }] of this.activeRequests) {
            controller.abort();
        }
        this.activeRequests.clear();
    }

    /**
     * Cancel specific request
     */
    cancelRequest(requestId) {
        const request = this.activeRequests.get(requestId);
        if (request) {
            request.controller.abort();
            this.activeRequests.delete(requestId);
        }
    }

    /**
     * Get request statistics
     */
    getStats() {
        return {
            activeRequests: this.activeRequests.size,
            cacheSize: this.cache.size,
            loadingStates: Object.fromEntries(this.loadingStates),
            interceptors: {
                request: this.requestInterceptors.length,
                response: this.responseInterceptors.length,
                error: this.errorInterceptors.length
            }
        };
    }

    /**
     * Convenience methods for common HTTP verbs
     */
    async get(endpoint, options = {}) {
        return this.request(endpoint, { ...options, method: 'GET' });
    }

    async post(endpoint, data, options = {}) {
        return this.request(endpoint, { ...options, method: 'POST', body: data });
    }

    async put(endpoint, data, options = {}) {
        return this.request(endpoint, { ...options, method: 'PUT', body: data });
    }

    async patch(endpoint, data, options = {}) {
        return this.request(endpoint, { ...options, method: 'PATCH', body: data });
    }

    async delete(endpoint, options = {}) {
        return this.request(endpoint, { ...options, method: 'DELETE' });
    }

    /**
     * Singleton pattern
     */
    static getInstance(options = {}) {
        if (!EnhancedAPIService.instance) {
            EnhancedAPIService.instance = new EnhancedAPIService(options);
        }
        return EnhancedAPIService.instance;
    }
}

// Create global instance
const apiService = EnhancedAPIService.getInstance();

// Make available globally
window.EnhancedAPIService = EnhancedAPIService;
window.apiService = apiService;

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { EnhancedAPIService, apiService };
}
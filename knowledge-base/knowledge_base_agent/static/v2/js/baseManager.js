/**
 * Base Manager Class
 * Provides common functionality for all consolidated managers
 * Ensures consistent patterns and service integration
 */
class BaseManager {
    constructor(options = {}) {
        this.options = {
            autoInit: true,
            enableLogging: true,
            enableCleanup: true,
            ...options
        };
        
        // Common properties
        this.elements = {};
        this.state = {};
        this.initialized = false;
        this.destroyed = false;
        
        // Service references
        this.durationFormatter = window.DurationFormatter;
        this.cleanupService = window.CleanupService;
        this.eventService = window.EventListenerService;
        this.apiService = window.apiService;
        
        // Component identification
        this.componentName = this.constructor.name;
        this.componentId = this.generateComponentId();
        
        // Auto-initialize if enabled
        if (this.options.autoInit) {
            this.init().catch(error => {
                console.error(`Failed to initialize ${this.componentName}:`, error);
            });
        }
    }

    /**
     * Initialize the component
     * Template method pattern - subclasses override specific steps
     */
    async init() {
        if (this.initialized || this.destroyed) return;
        
        try {
            this.log('Initializing...');
            
            // Initialization steps in order
            await this.validateDependencies();
            await this.initializeElements();
            await this.initializeState();
            await this.setupEventListeners();
            await this.loadInitialData();
            await this.finalizeInitialization();
            
            this.initialized = true;
            this.log('Initialized successfully');
            
            // Dispatch initialization event
            this.dispatchEvent('initialized', { component: this.componentName });
            
        } catch (error) {
            this.log('Initialization failed:', error);
            throw error;
        }
    }

    /**
     * Validate that required dependencies are available
     */
    async validateDependencies() {
        const requiredServices = ['DurationFormatter', 'CleanupService', 'EventListenerService', 'apiService'];
        const missing = requiredServices.filter(service => !window[service]);
        
        if (missing.length > 0) {
            throw new Error(`Missing required services: ${missing.join(', ')}`);
        }
    }

    /**
     * Initialize DOM elements
     * Override in subclasses to find and cache DOM elements
     */
    async initializeElements() {
        // Default implementation - override in subclasses
        this.log('Initializing elements (default implementation)');
    }

    /**
     * Initialize component state
     * Override in subclasses to set up initial state
     */
    async initializeState() {
        // Default implementation - override in subclasses
        this.state = {
            loading: false,
            error: null,
            data: null,
            ...this.state
        };
        this.log('State initialized');
    }

    /**
     * Setup event listeners using EventListenerService
     * Override in subclasses to define event configuration
     */
    async setupEventListeners() {
        // Default implementation - override in subclasses
        this.log('Setting up event listeners (default implementation)');
    }

    /**
     * Load initial data
     * Override in subclasses to load required data
     */
    async loadInitialData() {
        // Default implementation - override in subclasses
        this.log('Loading initial data (default implementation)');
    }

    /**
     * Finalize initialization
     * Override in subclasses for final setup steps
     */
    async finalizeInitialization() {
        // Default implementation - override in subclasses
        this.log('Finalizing initialization (default implementation)');
    }

    /**
     * Update component state
     * Provides consistent state management patterns
     */
    setState(updates, notify = true) {
        const previousState = { ...this.state };
        this.state = { ...this.state, ...updates };
        
        if (notify) {
            this.onStateChange(this.state, previousState);
            this.dispatchEvent('stateChange', { 
                newState: this.state, 
                previousState,
                component: this.componentName 
            });
        }
    }

    /**
     * Handle state changes
     * Override in subclasses to react to state changes
     */
    onStateChange(newState, previousState) {
        // Default implementation - override in subclasses
        this.log('State changed:', { newState, previousState });
    }

    /**
     * Show loading state
     */
    setLoading(isLoading, message = '') {
        this.setState({ 
            loading: isLoading, 
            loadingMessage: message 
        });
    }

    /**
     * Set error state
     */
    setError(error, context = '') {
        this.setState({ 
            error: error instanceof Error ? error.message : error,
            errorContext: context 
        });
        this.log('Error set:', error, context);
    }

    /**
     * Clear error state
     */
    clearError() {
        this.setState({ error: null, errorContext: null });
    }

    /**
     * Make API calls with consistent error handling
     */
    async apiCall(endpoint, options = {}) {
        try {
            this.setLoading(true, options.loadingMessage || 'Loading...');
            this.clearError();
            
            const result = await this.apiService.request(endpoint, {
                errorMessage: `Failed to ${options.action || 'load data'}`,
                ...options
            });
            
            return result;
            
        } catch (error) {
            this.setError(error, `API call to ${endpoint}`);
            throw error;
            
        } finally {
            this.setLoading(false);
        }
    }

    /**
     * Dispatch custom events
     */
    dispatchEvent(eventName, detail = {}) {
        const event = new CustomEvent(`${this.componentName.toLowerCase()}_${eventName}`, {
            detail: {
                component: this.componentName,
                componentId: this.componentId,
                timestamp: Date.now(),
                ...detail
            }
        });
        
        document.dispatchEvent(event);
        this.log('Event dispatched:', eventName, detail);
    }

    /**
     * Listen for events from other components
     */
    addEventListener(eventName, handler, options = {}) {
        if (this.eventService) {
            this.eventService.setupStandardListeners(this, {
                customEvents: [{
                    event: eventName,
                    handler: handler,
                    ...options
                }]
            });
        } else {
            // Fallback to direct event listener
            document.addEventListener(eventName, handler, options);
        }
    }

    /**
     * Refresh component data
     */
    async refresh() {
        this.log('Refreshing...');
        try {
            await this.loadInitialData();
            this.log('Refresh completed');
        } catch (error) {
            this.setError(error, 'refresh');
            throw error;
        }
    }

    /**
     * Reset component to initial state
     */
    async reset() {
        this.log('Resetting...');
        this.state = {};
        await this.initializeState();
        await this.loadInitialData();
        this.log('Reset completed');
    }

    /**
     * Cleanup resources
     */
    cleanup() {
        if (this.destroyed) return;
        
        this.log('Cleaning up...');
        
        // Use CleanupService for comprehensive cleanup
        if (this.cleanupService) {
            this.cleanupService.cleanup(this);
        }
        
        // Clear state
        this.state = {};
        this.elements = {};
        
        // Mark as destroyed
        this.destroyed = true;
        this.initialized = false;
        
        // Dispatch cleanup event
        this.dispatchEvent('destroyed', { component: this.componentName });
        
        this.log('Cleanup completed');
    }

    /**
     * Destroy component
     */
    destroy() {
        this.cleanup();
    }

    /**
     * Check if component is ready
     */
    isReady() {
        return this.initialized && !this.destroyed;
    }

    /**
     * Wait for component to be ready
     */
    async waitForReady(timeout = 5000) {
        if (this.isReady()) return;
        
        return new Promise((resolve, reject) => {
            const timeoutId = setTimeout(() => {
                reject(new Error(`Component ${this.componentName} failed to initialize within ${timeout}ms`));
            }, timeout);
            
            const checkReady = () => {
                if (this.isReady()) {
                    clearTimeout(timeoutId);
                    resolve();
                } else {
                    setTimeout(checkReady, 100);
                }
            };
            
            checkReady();
        });
    }

    /**
     * Generate unique component ID
     */
    generateComponentId() {
        return `${this.componentName.toLowerCase()}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }

    /**
     * Logging utility
     */
    log(...args) {
        if (this.options.enableLogging) {
            console.log(`[${this.componentName}]`, ...args);
        }
    }

    /**
     * Error logging utility
     */
    logError(...args) {
        console.error(`[${this.componentName}]`, ...args);
    }

    /**
     * Warning logging utility
     */
    logWarn(...args) {
        console.warn(`[${this.componentName}]`, ...args);
    }

    /**
     * Get component information
     */
    getInfo() {
        return {
            name: this.componentName,
            id: this.componentId,
            initialized: this.initialized,
            destroyed: this.destroyed,
            state: { ...this.state },
            options: { ...this.options }
        };
    }

    /**
     * Static method to create and initialize component
     */
    static async create(options = {}) {
        const instance = new this(options);
        if (!options.autoInit) {
            await instance.init();
        }
        return instance;
    }
}

// Make available globally
window.BaseManager = BaseManager;

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = BaseManager;
}
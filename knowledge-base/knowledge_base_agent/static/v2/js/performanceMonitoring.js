/* V2 PERFORMANCEMONITORING.JS - PERFORMANCE OPTIMIZATION AND MONITORING */

/**
 * PerformanceMonitor - Comprehensive performance monitoring and optimization
 * 
 * ARCHITECTURE:
 * - Monitors communication latency and throughput
 * - Implements event batching and rate limiting
 * - Tracks memory usage and DOM performance
 * - Provides performance metrics collection and reporting
 * - Optimizes virtual scrolling and DOM updates
 */
class PerformanceMonitor {
    constructor(config = {}) {
        this.config = {
            // Batching configuration
            batchSize: config.batchSize || 50,
            batchTimeout: config.batchTimeout || 1000,
            maxBatchDelay: config.maxBatchDelay || 5000,
            
            // Rate limiting configuration
            rateLimit: config.rateLimit || 100, // events per second
            rateLimitWindow: config.rateLimitWindow || 1000, // 1 second
            
            // Memory monitoring
            memoryCheckInterval: config.memoryCheckInterval || 30000, // 30 seconds
            memoryThreshold: config.memoryThreshold || 100 * 1024 * 1024, // 100MB
            
            // Performance monitoring
            metricsInterval: config.metricsInterval || 5000, // 5 seconds
            latencyThreshold: config.latencyThreshold || 2000, // 2 seconds (production appropriate)
            
            // DOM optimization
            virtualScrollThreshold: config.virtualScrollThreshold || 100,
            domUpdateBatchSize: config.domUpdateBatchSize || 20,
            
            ...config
        };
        
        // Event batching
        this.eventBatches = new Map();
        this.batchTimers = new Map();
        
        // Rate limiting
        this.rateLimitCounters = new Map();
        this.rateLimitTimers = new Map();
        
        // Performance metrics
        this.metrics = {
            events: {
                total: 0,
                batched: 0,
                rateLimited: 0,
                processed: 0
            },
            latency: {
                min: Infinity,
                max: 0,
                avg: 0,
                samples: []
            },
            throughput: {
                eventsPerSecond: 0,
                bytesPerSecond: 0,
                peakEventsPerSecond: 0
            },
            memory: {
                current: 0,
                peak: 0,
                samples: []
            },
            dom: {
                updates: 0,
                renders: 0,
                virtualScrollItems: 0
            }
        };
        
        // Performance observers
        this.observers = new Map();
        
        // Memory monitoring
        this.memoryTimer = null;
        this.metricsTimer = null;
        
        // DOM optimization
        this.domUpdateQueue = [];
        this.domUpdateTimer = null;
        this.virtualScrollManagers = new Map();
        
        this.init();
    }
    
    init() {
        this.setupPerformanceObservers();
        this.startMemoryMonitoring();
        this.startMetricsCollection();
        console.log('📊 PerformanceMonitor initialized');
    }
    
    setupPerformanceObservers() {
        // Performance Observer for navigation timing
        if ('PerformanceObserver' in window) {
            try {
                const navObserver = new PerformanceObserver((list) => {
                    this.handleNavigationEntries(list.getEntries());
                });
                navObserver.observe({ entryTypes: ['navigation'] });
                this.observers.set('navigation', navObserver);
                
                // Performance Observer for resource timing
                const resourceObserver = new PerformanceObserver((list) => {
                    this.handleResourceEntries(list.getEntries());
                });
                resourceObserver.observe({ entryTypes: ['resource'] });
                this.observers.set('resource', resourceObserver);
                
                // Performance Observer for measure timing
                const measureObserver = new PerformanceObserver((list) => {
                    this.handleMeasureEntries(list.getEntries());
                });
                measureObserver.observe({ entryTypes: ['measure'] });
                this.observers.set('measure', measureObserver);
                
            } catch (error) {
                console.warn('Performance Observer setup failed:', error);
            }
        }
    }
    
    handleNavigationEntries(entries) {
        entries.forEach(entry => {
            this.recordLatency('navigation', entry.loadEventEnd - entry.fetchStart);
        });
    }
    
    handleResourceEntries(entries) {
        entries.forEach(entry => {
            if (entry.name.includes('/api/') || entry.name.includes('/socket.io/')) {
                this.recordLatency('api', entry.responseEnd - entry.requestStart);
            }
        });
    }
    
    handleMeasureEntries(entries) {
        entries.forEach(entry => {
            this.recordLatency(entry.name, entry.duration);
        });
    }
    
    // Event batching implementation
    batchEvent(eventType, eventData) {
        this.metrics.events.total++;
        
        // Check rate limiting first
        if (this.isRateLimited(eventType)) {
            this.metrics.events.rateLimited++;
            return false;
        }
        
        // Get or create batch for this event type
        if (!this.eventBatches.has(eventType)) {
            this.eventBatches.set(eventType, []);
        }
        
        const batch = this.eventBatches.get(eventType);
        batch.push({
            data: eventData,
            timestamp: performance.now()
        });
        
        this.metrics.events.batched++;
        
        // Process batch if it reaches the size limit
        if (batch.length >= this.config.batchSize) {
            this.processBatch(eventType);
        } else {
            // Set timer to process batch after timeout
            this.scheduleBatchProcessing(eventType);
        }
        
        return true;
    }
    
    scheduleBatchProcessing(eventType) {
        // Clear existing timer
        if (this.batchTimers.has(eventType)) {
            clearTimeout(this.batchTimers.get(eventType));
        }
        
        // Set new timer
        const timer = setTimeout(() => {
            this.processBatch(eventType);
        }, this.config.batchTimeout);
        
        this.batchTimers.set(eventType, timer);
    }
    
    processBatch(eventType) {
        const batch = this.eventBatches.get(eventType);
        if (!batch || batch.length === 0) return;
        
        // Clear timer
        if (this.batchTimers.has(eventType)) {
            clearTimeout(this.batchTimers.get(eventType));
            this.batchTimers.delete(eventType);
        }
        
        // Process the batch
        const startTime = performance.now();
        
        try {
            this.processBatchedEvents(eventType, batch);
            this.metrics.events.processed += batch.length;
        } catch (error) {
            console.error(`Error processing batch for ${eventType}:`, error);
        }
        
        const processingTime = performance.now() - startTime;
        this.recordLatency(`batch_${eventType}`, processingTime);
        
        // Clear the batch
        this.eventBatches.set(eventType, []);
    }
    
    processBatchedEvents(eventType, events) {
        // Dispatch batched events based on type
        switch (eventType) {
            case 'log':
                this.processBatchedLogs(events);
                break;
            case 'progress':
                this.processBatchedProgress(events);
                break;
            case 'status':
                this.processBatchedStatus(events);
                break;
            default:
                // Generic batch processing
                events.forEach(event => {
                    document.dispatchEvent(new CustomEvent(eventType, {
                        detail: event.data
                    }));
                });
        }
    }
    
    processBatchedLogs(events) {
        // Batch process log events for better performance
        const logContainer = document.getElementById('logs-container');
        if (!logContainer) return;
        
        const fragment = document.createDocumentFragment();
        
        events.forEach(event => {
            const logElement = this.createLogElement(event.data);
            fragment.appendChild(logElement);
        });
        
        // Single DOM update for all logs
        logContainer.appendChild(fragment);
        
        // Trigger virtual scrolling update if needed
        this.updateVirtualScroll('logs', events.length);
    }
    
    processBatchedProgress(events) {
        // Batch process progress updates
        const progressUpdates = new Map();
        
        // Consolidate progress updates by operation
        events.forEach(event => {
            const operation = event.data.operation || 'default';
            progressUpdates.set(operation, event.data);
        });
        
        // Apply consolidated updates
        progressUpdates.forEach((data, operation) => {
            document.dispatchEvent(new CustomEvent('progress_update', {
                detail: data
            }));
        });
    }
    
    processBatchedStatus(events) {
        // Only process the latest status update
        const latestStatus = events[events.length - 1];
        document.dispatchEvent(new CustomEvent('status_update', {
            detail: latestStatus.data
        }));
    }
    
    // Rate limiting implementation
    isRateLimited(eventType) {
        const now = Date.now();
        const windowStart = now - this.config.rateLimitWindow;
        
        // Get or create counter for this event type
        if (!this.rateLimitCounters.has(eventType)) {
            this.rateLimitCounters.set(eventType, []);
        }
        
        const counter = this.rateLimitCounters.get(eventType);
        
        // Remove old entries outside the window
        while (counter.length > 0 && counter[0] < windowStart) {
            counter.shift();
        }
        
        // Check if rate limit exceeded
        if (counter.length >= this.config.rateLimit) {
            return true;
        }
        
        // Add current timestamp
        counter.push(now);
        
        return false;
    }
    
    // Memory monitoring
    startMemoryMonitoring() {
        if (!performance.memory) {
            console.warn('Memory monitoring not available in this browser');
            return;
        }
        
        this.memoryTimer = setInterval(() => {
            this.checkMemoryUsage();
        }, this.config.memoryCheckInterval);
    }
    
    checkMemoryUsage() {
        if (!performance.memory) return;
        
        const memoryInfo = {
            used: performance.memory.usedJSHeapSize,
            total: performance.memory.totalJSHeapSize,
            limit: performance.memory.jsHeapSizeLimit,
            timestamp: Date.now()
        };
        
        this.metrics.memory.current = memoryInfo.used;
        this.metrics.memory.peak = Math.max(this.metrics.memory.peak, memoryInfo.used);
        
        // Keep memory samples for trending
        this.metrics.memory.samples.push(memoryInfo);
        if (this.metrics.memory.samples.length > 100) {
            this.metrics.memory.samples.shift();
        }
        
        // Check memory threshold
        if (memoryInfo.used > this.config.memoryThreshold) {
            this.handleMemoryThresholdExceeded(memoryInfo);
        }
    }
    
    handleMemoryThresholdExceeded(memoryInfo) {
        console.warn('Memory threshold exceeded:', memoryInfo);
        
        // Trigger garbage collection if available
        if (window.gc) {
            window.gc();
        }
        
        // Emit memory warning event
        document.dispatchEvent(new CustomEvent('memory_warning', {
            detail: memoryInfo
        }));
        
        // Optimize memory usage
        this.optimizeMemoryUsage();
    }
    
    optimizeMemoryUsage() {
        // Clear old metrics samples
        this.metrics.latency.samples = this.metrics.latency.samples.slice(-50);
        this.metrics.memory.samples = this.metrics.memory.samples.slice(-50);
        
        // Clear old batches
        this.eventBatches.forEach((batch, eventType) => {
            if (batch.length > 0) {
                this.processBatch(eventType);
            }
        });
        
        // Optimize virtual scroll managers
        this.virtualScrollManagers.forEach(manager => {
            if (manager.optimize) {
                manager.optimize();
            }
        });
        
        console.log('Memory optimization completed');
    }
    
    // Performance metrics collection
    startMetricsCollection() {
        this.metricsTimer = setInterval(() => {
            this.collectMetrics();
        }, this.config.metricsInterval);
    }
    
    collectMetrics() {
        // Calculate throughput
        const now = Date.now();
        const timeWindow = this.config.metricsInterval;
        
        // Events per second
        const recentEvents = this.metrics.events.processed;
        this.metrics.throughput.eventsPerSecond = (recentEvents / timeWindow) * 1000;
        this.metrics.throughput.peakEventsPerSecond = Math.max(
            this.metrics.throughput.peakEventsPerSecond,
            this.metrics.throughput.eventsPerSecond
        );
        
        // Reset processed counter
        this.metrics.events.processed = 0;
        
        // Calculate average latency
        if (this.metrics.latency.samples.length > 0) {
            const sum = this.metrics.latency.samples.reduce((a, b) => a + b, 0);
            this.metrics.latency.avg = sum / this.metrics.latency.samples.length;
        }
        
        // Emit metrics event
        document.dispatchEvent(new CustomEvent('performance_metrics', {
            detail: { ...this.metrics, timestamp: now }
        }));
    }
    
    recordLatency(operation, duration) {
        this.metrics.latency.min = Math.min(this.metrics.latency.min, duration);
        this.metrics.latency.max = Math.max(this.metrics.latency.max, duration);
        
        // Keep samples for averaging
        this.metrics.latency.samples.push(duration);
        if (this.metrics.latency.samples.length > 100) {
            this.metrics.latency.samples.shift();
        }
        
        // Check latency threshold
        if (duration > this.config.latencyThreshold) {
            console.warn(`High latency detected for ${operation}: ${duration}ms`);
            document.dispatchEvent(new CustomEvent('high_latency', {
                detail: { operation, duration, timestamp: Date.now() }
            }));
        }
    }
    
    // DOM optimization
    queueDOMUpdate(updateFunction) {
        this.domUpdateQueue.push(updateFunction);
        
        if (!this.domUpdateTimer) {
            this.domUpdateTimer = requestAnimationFrame(() => {
                this.processDOMUpdates();
            });
        }
    }
    
    processDOMUpdates() {
        const startTime = performance.now();
        
        // Process updates in batches
        const batchSize = this.config.domUpdateBatchSize;
        const batch = this.domUpdateQueue.splice(0, batchSize);
        
        batch.forEach(updateFunction => {
            try {
                updateFunction();
                this.metrics.dom.updates++;
            } catch (error) {
                console.error('DOM update error:', error);
            }
        });
        
        const processingTime = performance.now() - startTime;
        this.recordLatency('dom_update_batch', processingTime);
        
        // Continue processing if more updates are queued
        if (this.domUpdateQueue.length > 0) {
            this.domUpdateTimer = requestAnimationFrame(() => {
                this.processDOMUpdates();
            });
        } else {
            this.domUpdateTimer = null;
        }
        
        this.metrics.dom.renders++;
    }
    
    // Virtual scrolling optimization
    createVirtualScrollManager(containerId, options = {}) {
        const manager = new VirtualScrollManager(containerId, {
            itemHeight: options.itemHeight || 50,
            bufferSize: options.bufferSize || 10,
            threshold: this.config.virtualScrollThreshold,
            ...options
        });
        
        this.virtualScrollManagers.set(containerId, manager);
        return manager;
    }
    
    updateVirtualScroll(containerId, itemCount) {
        const manager = this.virtualScrollManagers.get(containerId);
        if (manager) {
            manager.updateItemCount(itemCount);
            this.metrics.dom.virtualScrollItems += itemCount;
        }
    }
    
    // Performance measurement utilities
    startMeasure(name) {
        performance.mark(`${name}_start`);
    }
    
    endMeasure(name) {
        performance.mark(`${name}_end`);
        performance.measure(name, `${name}_start`, `${name}_end`);
    }
    
    // Public API
    getMetrics() {
        return { ...this.metrics };
    }
    
    getPerformanceReport() {
        return {
            metrics: this.getMetrics(),
            config: this.config,
            timestamp: Date.now(),
            uptime: performance.now(),
            memory: performance.memory ? {
                used: performance.memory.usedJSHeapSize,
                total: performance.memory.totalJSHeapSize,
                limit: performance.memory.jsHeapSizeLimit
            } : null
        };
    }
    
    resetMetrics() {
        this.metrics = {
            events: { total: 0, batched: 0, rateLimited: 0, processed: 0 },
            latency: { min: Infinity, max: 0, avg: 0, samples: [] },
            throughput: { eventsPerSecond: 0, bytesPerSecond: 0, peakEventsPerSecond: 0 },
            memory: { current: 0, peak: 0, samples: [] },
            dom: { updates: 0, renders: 0, virtualScrollItems: 0 }
        };
    }
    
    // Cleanup
    destroy() {
        // Clear timers
        if (this.memoryTimer) {
            clearInterval(this.memoryTimer);
        }
        
        if (this.metricsTimer) {
            clearInterval(this.metricsTimer);
        }
        
        if (this.domUpdateTimer) {
            cancelAnimationFrame(this.domUpdateTimer);
        }
        
        // Clear batch timers
        this.batchTimers.forEach(timer => clearTimeout(timer));
        
        // Disconnect observers
        this.observers.forEach(observer => observer.disconnect());
        
        // Clear virtual scroll managers
        this.virtualScrollManagers.forEach(manager => {
            if (manager.destroy) {
                manager.destroy();
            }
        });
        
        console.log('📊 PerformanceMonitor destroyed');
    }
    
    // Helper methods
    createLogElement(logData) {
        const element = document.createElement('div');
        element.className = 'log-message';
        element.textContent = logData.message || '';
        return element;
    }
}

// Make globally available
window.PerformanceMonitor = PerformanceMonitor;/**
 * 
VirtualScrollManager - Efficient virtual scrolling implementation
 * 
 * ARCHITECTURE:
 * - Renders only visible items for performance
 * - Maintains scroll position and handles large datasets
 * - Provides smooth scrolling experience
 * - Optimizes memory usage for long lists
 */
class VirtualScrollManager {
    constructor(containerId, options = {}) {
        this.container = document.getElementById(containerId);
        if (!this.container) {
            throw new Error(`Container ${containerId} not found`);
        }
        
        this.config = {
            itemHeight: options.itemHeight || 50,
            bufferSize: options.bufferSize || 10,
            threshold: options.threshold || 100,
            renderItem: options.renderItem || this.defaultRenderItem.bind(this),
            ...options
        };
        
        this.items = [];
        this.visibleItems = [];
        this.startIndex = 0;
        this.endIndex = 0;
        this.scrollTop = 0;
        this.containerHeight = 0;
        this.totalHeight = 0;
        
        // DOM elements
        this.viewport = null;
        this.content = null;
        this.spacerTop = null;
        this.spacerBottom = null;
        
        this.init();
    }
    
    init() {
        this.setupDOM();
        this.attachEventListeners();
        this.updateDimensions();
        console.log(`📜 VirtualScrollManager initialized for ${this.container.id}`);
    }
    
    setupDOM() {
        // Create virtual scroll structure
        this.container.innerHTML = '';
        this.container.style.position = 'relative';
        this.container.style.overflow = 'auto';
        
        // Viewport container
        this.viewport = document.createElement('div');
        this.viewport.style.position = 'relative';
        this.viewport.style.height = '100%';
        
        // Top spacer
        this.spacerTop = document.createElement('div');
        this.spacerTop.style.height = '0px';
        
        // Content container
        this.content = document.createElement('div');
        this.content.style.position = 'relative';
        
        // Bottom spacer
        this.spacerBottom = document.createElement('div');
        this.spacerBottom.style.height = '0px';
        
        // Assemble structure
        this.viewport.appendChild(this.spacerTop);
        this.viewport.appendChild(this.content);
        this.viewport.appendChild(this.spacerBottom);
        this.container.appendChild(this.viewport);
    }
    
    attachEventListeners() {
        this.container.addEventListener('scroll', () => {
            this.handleScroll();
        });
        
        window.addEventListener('resize', () => {
            this.updateDimensions();
            this.render();
        });
    }
    
    updateDimensions() {
        this.containerHeight = this.container.clientHeight;
        this.totalHeight = this.items.length * this.config.itemHeight;
        this.viewport.style.height = `${this.totalHeight}px`;
    }
    
    handleScroll() {
        this.scrollTop = this.container.scrollTop;
        this.calculateVisibleRange();
        this.render();
    }
    
    calculateVisibleRange() {
        const visibleStart = Math.floor(this.scrollTop / this.config.itemHeight);
        const visibleEnd = Math.ceil((this.scrollTop + this.containerHeight) / this.config.itemHeight);
        
        // Add buffer
        this.startIndex = Math.max(0, visibleStart - this.config.bufferSize);
        this.endIndex = Math.min(this.items.length, visibleEnd + this.config.bufferSize);
    }
    
    render() {
        // Clear content
        this.content.innerHTML = '';
        
        // Update spacers
        const topSpacerHeight = this.startIndex * this.config.itemHeight;
        const bottomSpacerHeight = (this.items.length - this.endIndex) * this.config.itemHeight;
        
        this.spacerTop.style.height = `${topSpacerHeight}px`;
        this.spacerBottom.style.height = `${bottomSpacerHeight}px`;
        
        // Render visible items
        const fragment = document.createDocumentFragment();
        
        for (let i = this.startIndex; i < this.endIndex; i++) {
            if (this.items[i]) {
                const element = this.config.renderItem(this.items[i], i);
                if (element) {
                    element.style.height = `${this.config.itemHeight}px`;
                    element.dataset.index = i;
                    fragment.appendChild(element);
                }
            }
        }
        
        this.content.appendChild(fragment);
        
        // Update visible items reference
        this.visibleItems = this.items.slice(this.startIndex, this.endIndex);
    }
    
    defaultRenderItem(item, index) {
        const element = document.createElement('div');
        element.className = 'virtual-scroll-item';
        element.textContent = typeof item === 'string' ? item : JSON.stringify(item);
        return element;
    }
    
    // Public API
    setItems(items) {
        this.items = items;
        this.updateDimensions();
        this.calculateVisibleRange();
        this.render();
    }
    
    addItem(item) {
        this.items.push(item);
        this.updateDimensions();
        
        // Auto-scroll to bottom if user is at bottom
        const isAtBottom = this.scrollTop + this.containerHeight >= this.totalHeight - 10;
        
        this.calculateVisibleRange();
        this.render();
        
        if (isAtBottom) {
            this.scrollToBottom();
        }
    }
    
    addItems(items) {
        this.items.push(...items);
        this.updateDimensions();
        this.calculateVisibleRange();
        this.render();
    }
    
    removeItem(index) {
        if (index >= 0 && index < this.items.length) {
            this.items.splice(index, 1);
            this.updateDimensions();
            this.calculateVisibleRange();
            this.render();
        }
    }
    
    updateItem(index, item) {
        if (index >= 0 && index < this.items.length) {
            this.items[index] = item;
            
            // Re-render if item is visible
            if (index >= this.startIndex && index < this.endIndex) {
                this.render();
            }
        }
    }
    
    updateItemCount(count) {
        // Optimize for adding items at the end
        if (count > this.items.length) {
            const newItems = new Array(count - this.items.length).fill(null);
            this.addItems(newItems);
        }
    }
    
    scrollToIndex(index) {
        if (index >= 0 && index < this.items.length) {
            const scrollTop = index * this.config.itemHeight;
            this.container.scrollTop = scrollTop;
        }
    }
    
    scrollToTop() {
        this.container.scrollTop = 0;
    }
    
    scrollToBottom() {
        this.container.scrollTop = this.totalHeight;
    }
    
    getVisibleItems() {
        return this.visibleItems;
    }
    
    getVisibleRange() {
        return {
            start: this.startIndex,
            end: this.endIndex,
            count: this.endIndex - this.startIndex
        };
    }
    
    optimize() {
        // Memory optimization - remove items beyond a certain limit
        const maxItems = 10000;
        if (this.items.length > maxItems) {
            const itemsToRemove = this.items.length - maxItems;
            this.items.splice(0, itemsToRemove);
            this.updateDimensions();
            this.calculateVisibleRange();
            this.render();
            
            console.log(`Optimized virtual scroll: removed ${itemsToRemove} items`);
        }
    }
    
    destroy() {
        // Remove event listeners
        window.removeEventListener('resize', this.updateDimensions);
        
        // Clear DOM
        if (this.container) {
            this.container.innerHTML = '';
        }
        
        console.log(`📜 VirtualScrollManager destroyed for ${this.container?.id}`);
    }
}

// Make globally available
window.VirtualScrollManager = VirtualScrollManager;
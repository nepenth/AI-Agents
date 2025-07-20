/* V2 PERFORMANCEOPTIMIZER.JS - ENHANCED PERFORMANCE OPTIMIZATION SYSTEM */

/**
 * PerformanceOptimizer - Advanced performance optimization for display components
 * 
 * ARCHITECTURE:
 * - Integrates with DisplayComponentCoordinator for optimized event handling
 * - Implements intelligent DOM update batching and throttling
 * - Provides memory usage monitoring and automatic cleanup
 * - Optimizes virtual scrolling performance for large datasets
 * - Reduces redundant component operations through smart caching
 * - Implements efficient component cleanup and resource management
 */
class PerformanceOptimizer {
    constructor(config = {}) {
        this.config = {
            // DOM Update Optimization
            domBatchSize: config.domBatchSize || 20,
            domBatchDelay: config.domBatchDelay || 16, // ~60fps
            domThrottleDelay: config.domThrottleDelay || 100,
            
            // Memory Management
            memoryCheckInterval: config.memoryCheckInterval || 30000,
            memoryThreshold: config.memoryThreshold || 150 * 1024 * 1024, // 150MB
            gcTriggerThreshold: config.gcTriggerThreshold || 200 * 1024 * 1024, // 200MB
            
            // Event Optimization
            eventBatchSize: config.eventBatchSize || 50,
            eventThrottleDelay: config.eventThrottleDelay || 50,
            eventDeduplicationWindow: config.eventDeduplicationWindow || 100,
            
            // Virtual Scrolling
            virtualScrollThreshold: config.virtualScrollThreshold || 100,
            virtualScrollBufferSize: config.virtualScrollBufferSize || 10,
            virtualScrollItemHeight: config.virtualScrollItemHeight || 50,
            
            // Component Optimization
            componentUpdateThrottle: config.componentUpdateThrottle || 100,
            componentCleanupInterval: config.componentCleanupInterval || 60000,
            redundantOperationThreshold: config.redundantOperationThreshold || 5,
            
            ...config
        };
        
        // DOM Update Management
        this.domUpdateQueue = [];
        this.domUpdateTimer = null;
        this.domUpdateInProgress = false;
        this.domThrottleTimers = new Map();
        
        // Memory Management
        this.memoryTimer = null;
        this.memoryHistory = [];
        this.lastGCTime = 0;
        this.memoryPressureLevel = 0; // 0-3 (none, low, medium, high)
        
        // Event Optimization
        this.eventCache = new Map();
        this.eventThrottleTimers = new Map();
        this.recentEvents = new Map();
        
        // Virtual Scrolling Management
        this.virtualScrollManagers = new Map();
        this.scrollOptimizationCache = new Map();
        
        // Component Optimization
        this.componentUpdateTimers = new Map();
        this.componentOperationCounts = new Map();
        this.componentCleanupTimer = null;
        
        // Performance Metrics
        this.metrics = {
            domUpdates: { batched: 0, throttled: 0, total: 0 },
            memory: { cleanups: 0, gcTriggers: 0, peakUsage: 0 },
            events: { deduplicated: 0, throttled: 0, cached: 0 },
            virtualScroll: { optimizations: 0, itemsRendered: 0 },
            components: { redundantOpsBlocked: 0, cleanupsPerformed: 0 }
        };
        
        this.init();
    }
    
    init() {
        this.setupMemoryMonitoring();
        this.setupComponentCleanup();
        this.integrateWithCoordinator();
        this.setupPerformanceObservers();
        
        console.log('⚡ PerformanceOptimizer initialized');
    }
    
    // === DOM UPDATE OPTIMIZATION ===
    
    optimizeDOMUpdate(updateFunction, elementId = null, priority = 'normal') {
        const update = {
            fn: updateFunction,
            elementId: elementId,
            priority: priority,
            timestamp: performance.now(),
            id: this.generateUpdateId()
        };
        
        // Check for throttling
        if (elementId && this.shouldThrottleDOMUpdate(elementId)) {
            this.throttleDOMUpdate(elementId, update);
            return;
        }
        
        this.domUpdateQueue.push(update);
        this.metrics.domUpdates.total++;
        
        this.scheduleDOMBatch();
    }
    
    shouldThrottleDOMUpdate(elementId) {
        const lastUpdate = this.domThrottleTimers.get(elementId);
        if (!lastUpdate) return false;
        
        const timeSinceLastUpdate = performance.now() - lastUpdate;
        return timeSinceLastUpdate < this.config.domThrottleDelay;
    }
    
    throttleDOMUpdate(elementId, update) {
        // Clear existing throttle timer
        const existingTimer = this.domThrottleTimers.get(`${elementId}_timer`);
        if (existingTimer) {
            clearTimeout(existingTimer);
        }
        
        // Set new throttle timer
        const timer = setTimeout(() => {
            this.domUpdateQueue.push(update);
            this.scheduleDOMBatch();
            this.domThrottleTimers.delete(`${elementId}_timer`);
        }, this.config.domThrottleDelay);
        
        this.domThrottleTimers.set(`${elementId}_timer`, timer);
        this.domThrottleTimers.set(elementId, performance.now());
        this.metrics.domUpdates.throttled++;
    }
    
    scheduleDOMBatch() {
        if (this.domUpdateTimer || this.domUpdateInProgress) return;
        
        this.domUpdateTimer = requestAnimationFrame(() => {
            this.processDOMBatch();
        });
    }
    
    processDOMBatch() {
        if (this.domUpdateQueue.length === 0) {
            this.domUpdateTimer = null;
            return;
        }
        
        this.domUpdateInProgress = true;
        const startTime = performance.now();
        
        // Sort by priority (high -> normal -> low)
        const priorityOrder = { high: 3, normal: 2, low: 1 };
        this.domUpdateQueue.sort((a, b) => 
            priorityOrder[b.priority] - priorityOrder[a.priority]
        );
        
        // Process batch
        const batchSize = Math.min(this.config.domBatchSize, this.domUpdateQueue.length);
        const batch = this.domUpdateQueue.splice(0, batchSize);
        
        // Group updates by element to avoid redundant operations
        const groupedUpdates = this.groupUpdatesByElement(batch);
        
        // Execute updates
        groupedUpdates.forEach(updates => {
            this.executeGroupedUpdates(updates);
        });
        
        const processingTime = performance.now() - startTime;
        this.metrics.domUpdates.batched += batch.length;
        
        // Record performance
        if (window.performanceMonitor) {
            window.performanceMonitor.recordLatency('dom_batch_processing', processingTime);
        }
        
        this.domUpdateInProgress = false;
        this.domUpdateTimer = null;
        
        // Continue processing if more updates are queued
        if (this.domUpdateQueue.length > 0) {
            this.scheduleDOMBatch();
        }
    }
    
    groupUpdatesByElement(updates) {
        const grouped = new Map();
        
        updates.forEach(update => {
            const key = update.elementId || 'global';
            if (!grouped.has(key)) {
                grouped.set(key, []);
            }
            grouped.get(key).push(update);
        });
        
        return Array.from(grouped.values());
    }
    
    executeGroupedUpdates(updates) {
        try {
            // Execute all updates for this element/group
            updates.forEach(update => {
                update.fn();
            });
        } catch (error) {
            console.error('DOM update batch error:', error);
        }
    }
    
    // === MEMORY OPTIMIZATION ===
    
    setupMemoryMonitoring() {
        if (!performance.memory) {
            console.warn('Memory monitoring not available');
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
        
        // Update metrics
        this.metrics.memory.peakUsage = Math.max(
            this.metrics.memory.peakUsage, 
            memoryInfo.used
        );
        
        // Add to history
        this.memoryHistory.push(memoryInfo);
        if (this.memoryHistory.length > 100) {
            this.memoryHistory.shift();
        }
        
        // Determine memory pressure level
        this.updateMemoryPressureLevel(memoryInfo);
        
        // Trigger cleanup if needed
        if (memoryInfo.used > this.config.memoryThreshold) {
            this.performMemoryCleanup();
        }
        
        // Trigger GC if available and needed
        if (memoryInfo.used > this.config.gcTriggerThreshold && 
            window.gc && 
            Date.now() - this.lastGCTime > 30000) {
            this.triggerGarbageCollection();
        }
    }
    
    updateMemoryPressureLevel(memoryInfo) {
        const usageRatio = memoryInfo.used / memoryInfo.limit;
        
        if (usageRatio > 0.8) {
            this.memoryPressureLevel = 3; // High
        } else if (usageRatio > 0.6) {
            this.memoryPressureLevel = 2; // Medium
        } else if (usageRatio > 0.4) {
            this.memoryPressureLevel = 1; // Low
        } else {
            this.memoryPressureLevel = 0; // None
        }
        
        // Adjust optimization aggressiveness based on pressure
        this.adjustOptimizationLevel();
    }
    
    adjustOptimizationLevel() {
        switch (this.memoryPressureLevel) {
            case 3: // High pressure
                this.config.domBatchSize = Math.max(5, this.config.domBatchSize * 0.5);
                this.config.eventBatchSize = Math.max(10, this.config.eventBatchSize * 0.5);
                break;
            case 2: // Medium pressure
                this.config.domBatchSize = Math.max(10, this.config.domBatchSize * 0.75);
                this.config.eventBatchSize = Math.max(25, this.config.eventBatchSize * 0.75);
                break;
            case 1: // Low pressure
                // Slightly more conservative
                break;
            case 0: // No pressure
                // Normal operation
                break;
        }
    }
    
    performMemoryCleanup() {
        console.log('🧹 Performing memory cleanup due to high usage');
        
        // Clear old event cache
        this.clearOldEventCache();
        
        // Optimize virtual scroll managers
        this.optimizeVirtualScrollManagers();
        
        // Clear component operation counts
        this.componentOperationCounts.clear();
        
        // Clear old DOM throttle timers
        this.clearOldThrottleTimers();
        
        // Trigger component cleanup
        this.triggerComponentCleanup();
        
        this.metrics.memory.cleanups++;
        
        // Emit memory cleanup event
        document.dispatchEvent(new CustomEvent('memory_cleanup_performed', {
            detail: { 
                memoryPressureLevel: this.memoryPressureLevel,
                timestamp: Date.now()
            }
        }));
    }
    
    triggerGarbageCollection() {
        if (window.gc) {
            console.log('🗑️ Triggering garbage collection');
            window.gc();
            this.lastGCTime = Date.now();
            this.metrics.memory.gcTriggers++;
        }
    }
    
    // === EVENT OPTIMIZATION ===
    
    optimizeEvent(eventType, eventData, componentName = null) {
        const eventKey = this.generateEventKey(eventType, eventData, componentName);
        
        // Check for recent duplicate
        if (this.isDuplicateEvent(eventKey)) {
            this.metrics.events.deduplicated++;
            return false; // Skip duplicate
        }
        
        // Check for cached result
        const cachedResult = this.eventCache.get(eventKey);
        if (cachedResult && this.isCacheValid(cachedResult)) {
            this.metrics.events.cached++;
            return cachedResult.result;
        }
        
        // Check for throttling
        if (this.shouldThrottleEvent(eventType, componentName)) {
            this.throttleEvent(eventType, eventData, componentName);
            this.metrics.events.throttled++;
            return false;
        }
        
        // Record recent event
        this.recordRecentEvent(eventKey);
        
        return true; // Allow event
    }
    
    generateEventKey(eventType, eventData, componentName) {
        const dataHash = this.hashObject(eventData);
        return `${eventType}_${componentName || 'global'}_${dataHash}`;
    }
    
    hashObject(obj) {
        return JSON.stringify(obj).split('').reduce((hash, char) => {
            return ((hash << 5) - hash) + char.charCodeAt(0);
        }, 0).toString(36);
    }
    
    isDuplicateEvent(eventKey) {
        const recent = this.recentEvents.get(eventKey);
        if (!recent) return false;
        
        const timeSinceLastEvent = Date.now() - recent.timestamp;
        return timeSinceLastEvent < this.config.eventDeduplicationWindow;
    }
    
    recordRecentEvent(eventKey) {
        this.recentEvents.set(eventKey, {
            timestamp: Date.now()
        });
        
        // Clean old entries periodically
        if (this.recentEvents.size > 1000) {
            this.cleanOldRecentEvents();
        }
    }
    
    cleanOldRecentEvents() {
        const cutoff = Date.now() - this.config.eventDeduplicationWindow * 10;
        
        for (const [key, data] of this.recentEvents.entries()) {
            if (data.timestamp < cutoff) {
                this.recentEvents.delete(key);
            }
        }
    }
    
    shouldThrottleEvent(eventType, componentName) {
        const throttleKey = `${eventType}_${componentName || 'global'}`;
        const lastEvent = this.eventThrottleTimers.get(throttleKey);
        
        if (!lastEvent) return false;
        
        const timeSinceLastEvent = Date.now() - lastEvent;
        return timeSinceLastEvent < this.config.eventThrottleDelay;
    }
    
    throttleEvent(eventType, eventData, componentName) {
        const throttleKey = `${eventType}_${componentName || 'global'}`;
        this.eventThrottleTimers.set(throttleKey, Date.now());
    }
    
    clearOldEventCache() {
        const cutoff = Date.now() - 300000; // 5 minutes
        
        for (const [key, data] of this.eventCache.entries()) {
            if (data.timestamp < cutoff) {
                this.eventCache.delete(key);
            }
        }
    }
    
    isCacheValid(cachedData) {
        const age = Date.now() - cachedData.timestamp;
        return age < 60000; // 1 minute cache validity
    }
    
    // === VIRTUAL SCROLLING OPTIMIZATION ===
    
    optimizeVirtualScrolling(containerId, items, options = {}) {
        const cacheKey = `${containerId}_${items.length}`;
        
        // Check if optimization is needed
        if (items.length < this.config.virtualScrollThreshold) {
            return null; // No virtual scrolling needed
        }
        
        // Check cache for existing optimization
        const cached = this.scrollOptimizationCache.get(cacheKey);
        if (cached && this.isScrollCacheValid(cached)) {
            return cached.manager;
        }
        
        // Create or update virtual scroll manager
        let manager = this.virtualScrollManagers.get(containerId);
        
        if (!manager) {
            manager = this.createVirtualScrollManager(containerId, options);
        }
        
        // Optimize manager settings based on memory pressure
        this.adjustVirtualScrollSettings(manager);
        
        // Update items
        manager.setItems(items);
        
        // Cache the optimization
        this.scrollOptimizationCache.set(cacheKey, {
            manager: manager,
            timestamp: Date.now(),
            itemCount: items.length
        });
        
        this.metrics.virtualScroll.optimizations++;
        this.metrics.virtualScroll.itemsRendered += items.length;
        
        return manager;
    }
    
    createVirtualScrollManager(containerId, options) {
        const manager = new VirtualScrollManager(containerId, {
            itemHeight: options.itemHeight || this.config.virtualScrollItemHeight,
            bufferSize: options.bufferSize || this.config.virtualScrollBufferSize,
            threshold: this.config.virtualScrollThreshold,
            renderItem: options.renderItem,
            ...options
        });
        
        this.virtualScrollManagers.set(containerId, manager);
        return manager;
    }
    
    adjustVirtualScrollSettings(manager) {
        // Adjust buffer size based on memory pressure
        switch (this.memoryPressureLevel) {
            case 3: // High pressure
                manager.config.bufferSize = Math.max(2, manager.config.bufferSize * 0.5);
                break;
            case 2: // Medium pressure
                manager.config.bufferSize = Math.max(5, manager.config.bufferSize * 0.75);
                break;
        }
    }
    
    optimizeVirtualScrollManagers() {
        this.virtualScrollManagers.forEach(manager => {
            if (manager.optimize) {
                manager.optimize();
            }
        });
    }
    
    isScrollCacheValid(cached) {
        const age = Date.now() - cached.timestamp;
        return age < 300000; // 5 minutes
    }
    
    // === COMPONENT OPTIMIZATION ===
    
    optimizeComponentOperation(componentName, operationType, operationData) {
        const operationKey = `${componentName}_${operationType}`;
        
        // Track operation frequency
        const count = this.componentOperationCounts.get(operationKey) || 0;
        this.componentOperationCounts.set(operationKey, count + 1);
        
        // Check for redundant operations
        if (this.isRedundantOperation(operationKey, operationData)) {
            this.metrics.components.redundantOpsBlocked++;
            return false; // Block redundant operation
        }
        
        // Throttle high-frequency operations
        if (this.shouldThrottleComponentOperation(componentName, operationType)) {
            this.throttleComponentOperation(componentName, operationType, operationData);
            return false; // Throttled
        }
        
        return true; // Allow operation
    }
    
    isRedundantOperation(operationKey, operationData) {
        const count = this.componentOperationCounts.get(operationKey) || 0;
        
        // Consider redundant if same operation called many times recently
        if (count > this.config.redundantOperationThreshold) {
            const recentCalls = this.getRecentOperationCalls(operationKey);
            
            // Check if all recent calls have identical data
            if (recentCalls.length > 2) {
                const allIdentical = recentCalls.every(call => 
                    JSON.stringify(call.data) === JSON.stringify(operationData)
                );
                
                if (allIdentical) {
                    return true; // Redundant
                }
            }
        }
        
        return false;
    }
    
    getRecentOperationCalls(operationKey) {
        // This would be implemented with a more sophisticated tracking system
        // For now, return empty array
        return [];
    }
    
    shouldThrottleComponentOperation(componentName, operationType) {
        const throttleKey = `${componentName}_${operationType}`;
        const lastOperation = this.componentUpdateTimers.get(throttleKey);
        
        if (!lastOperation) return false;
        
        const timeSinceLastOperation = Date.now() - lastOperation;
        return timeSinceLastOperation < this.config.componentUpdateThrottle;
    }
    
    throttleComponentOperation(componentName, operationType, operationData) {
        const throttleKey = `${componentName}_${operationType}`;
        this.componentUpdateTimers.set(throttleKey, Date.now());
    }
    
    setupComponentCleanup() {
        this.componentCleanupTimer = setInterval(() => {
            this.performComponentCleanup();
        }, this.config.componentCleanupInterval);
    }
    
    performComponentCleanup() {
        // Clear old operation counts
        const cutoff = Date.now() - this.config.componentCleanupInterval;
        
        // Reset operation counts periodically
        if (this.componentOperationCounts.size > 100) {
            this.componentOperationCounts.clear();
        }
        
        // Clear old component update timers
        this.clearOldComponentTimers();
        
        this.metrics.components.cleanupsPerformed++;
    }
    
    triggerComponentCleanup() {
        // Trigger cleanup on all registered components
        if (window.displayCoordinator) {
            const components = window.displayCoordinator.getAllComponents();
            
            components.forEach(component => {
                if (component.instance && typeof component.instance.cleanup === 'function') {
                    try {
                        component.instance.cleanup();
                    } catch (error) {
                        console.warn(`Component cleanup failed for ${component.name}:`, error);
                    }
                }
            });
        }
    }
    
    clearOldComponentTimers() {
        const cutoff = Date.now() - this.config.componentUpdateThrottle * 10;
        
        for (const [key, timestamp] of this.componentUpdateTimers.entries()) {
            if (timestamp < cutoff) {
                this.componentUpdateTimers.delete(key);
            }
        }
    }
    
    clearOldThrottleTimers() {
        const cutoff = Date.now() - this.config.domThrottleDelay * 10;
        
        for (const [key, timestamp] of this.domThrottleTimers.entries()) {
            if (typeof timestamp === 'number' && timestamp < cutoff) {
                this.domThrottleTimers.delete(key);
            }
        }
    }
    
    // === INTEGRATION WITH COMPONENT COORDINATOR ===
    
    integrateWithCoordinator() {
        if (!window.displayCoordinator) return;
        
        // Listen for component batch processing events
        document.addEventListener('component_batch_processed', (event) => {
            this.handleComponentBatchProcessed(event.detail);
        });
        
        // Enhance coordinator with performance optimization
        this.enhanceCoordinatorPerformance();
    }
    
    enhanceCoordinatorPerformance() {
        const coordinator = window.displayCoordinator;
        if (!coordinator) return;
        
        // Override coordinateEvent to add optimization
        const originalCoordinateEvent = coordinator.coordinateEvent.bind(coordinator);
        
        coordinator.coordinateEvent = (eventType, eventData) => {
            // Apply event optimization
            if (this.optimizeEvent(eventType, eventData)) {
                return originalCoordinateEvent(eventType, eventData);
            }
            // Event was optimized away (deduplicated, throttled, etc.)
        };
        
        console.log('⚡ Enhanced DisplayComponentCoordinator with performance optimization');
    }
    
    handleComponentBatchProcessed(detail) {
        const { batchSize, processingTime, eventTypes } = detail;
        
        // Adjust optimization parameters based on performance
        if (processingTime > 50) { // Slow batch processing
            this.config.eventBatchSize = Math.max(10, this.config.eventBatchSize * 0.8);
        } else if (processingTime < 10) { // Fast batch processing
            this.config.eventBatchSize = Math.min(100, this.config.eventBatchSize * 1.1);
        }
    }
    
    // === PERFORMANCE OBSERVERS ===
    
    setupPerformanceObservers() {
        if (!('PerformanceObserver' in window)) return;
        
        try {
            // Observe long tasks
            const longTaskObserver = new PerformanceObserver((list) => {
                list.getEntries().forEach(entry => {
                    if (entry.duration > 50) { // Long task threshold
                        console.warn(`Long task detected: ${entry.duration.toFixed(2)}ms`);
                        this.handleLongTask(entry);
                    }
                });
            });
            
            longTaskObserver.observe({ entryTypes: ['longtask'] });
            
        } catch (error) {
            console.warn('Performance observer setup failed:', error);
        }
    }
    
    handleLongTask(entry) {
        // Increase optimization aggressiveness temporarily
        const originalBatchSize = this.config.domBatchSize;
        const originalEventBatchSize = this.config.eventBatchSize;
        
        this.config.domBatchSize = Math.max(5, this.config.domBatchSize * 0.5);
        this.config.eventBatchSize = Math.max(10, this.config.eventBatchSize * 0.5);
        
        // Restore after a delay
        setTimeout(() => {
            this.config.domBatchSize = originalBatchSize;
            this.config.eventBatchSize = originalEventBatchSize;
        }, 5000);
    }
    
    // === PUBLIC API ===
    
    getOptimizationMetrics() {
        return {
            ...this.metrics,
            memoryPressureLevel: this.memoryPressureLevel,
            activeOptimizations: {
                domUpdatesQueued: this.domUpdateQueue.length,
                virtualScrollManagers: this.virtualScrollManagers.size,
                eventCacheSize: this.eventCache.size,
                componentOperationCounts: this.componentOperationCounts.size
            },
            config: { ...this.config }
        };
    }
    
    getPerformanceReport() {
        return {
            metrics: this.getOptimizationMetrics(),
            memoryHistory: this.memoryHistory.slice(-10), // Last 10 samples
            timestamp: Date.now(),
            uptime: performance.now()
        };
    }
    
    resetMetrics() {
        this.metrics = {
            domUpdates: { batched: 0, throttled: 0, total: 0 },
            memory: { cleanups: 0, gcTriggers: 0, peakUsage: 0 },
            events: { deduplicated: 0, throttled: 0, cached: 0 },
            virtualScroll: { optimizations: 0, itemsRendered: 0 },
            components: { redundantOpsBlocked: 0, cleanupsPerformed: 0 }
        };
    }
    
    // === CLEANUP ===
    
    destroy() {
        // Clear timers
        if (this.memoryTimer) {
            clearInterval(this.memoryTimer);
        }
        
        if (this.componentCleanupTimer) {
            clearInterval(this.componentCleanupTimer);
        }
        
        if (this.domUpdateTimer) {
            cancelAnimationFrame(this.domUpdateTimer);
        }
        
        // Clear throttle timers
        this.domThrottleTimers.forEach(timer => {
            if (typeof timer === 'number') {
                clearTimeout(timer);
            }
        });
        
        this.eventThrottleTimers.clear();
        
        // Destroy virtual scroll managers
        this.virtualScrollManagers.forEach(manager => {
            if (manager.destroy) {
                manager.destroy();
            }
        });
        
        // Clear data structures
        this.domUpdateQueue = [];
        this.eventCache.clear();
        this.recentEvents.clear();
        this.componentOperationCounts.clear();
        this.scrollOptimizationCache.clear();
        
        console.log('⚡ PerformanceOptimizer destroyed');
    }
    
    // === UTILITY METHODS ===
    
    generateUpdateId() {
        return `update_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }
}

// Make globally available
window.PerformanceOptimizer = PerformanceOptimizer;

// Auto-initialize if performance monitor is available
if (window.PerformanceMonitor && !window.performanceOptimizer) {
    window.performanceOptimizer = new PerformanceOptimizer();
}
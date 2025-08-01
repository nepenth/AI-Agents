/**
 * Centralized Cleanup Service
 * Eliminates duplicate cleanup() methods across 8 files
 * Provides standardized resource cleanup patterns
 */
class CleanupService {
    /**
     * Perform comprehensive cleanup for a component
     * @param {Object} component - Component instance to clean up
     * @param {Object} options - Cleanup options
     * @param {boolean} options.clearTimeouts - Clear timeouts (default: true)
     * @param {boolean} options.clearIntervals - Clear intervals (default: true)
     * @param {boolean} options.removeEventListeners - Remove event listeners (default: true)
     * @param {boolean} options.cleanupManagers - Cleanup sub-managers (default: true)
     * @param {boolean} options.logCleanup - Log cleanup actions (default: true)
     */
    static cleanup(component, options = {}) {
        const {
            clearTimeouts = true,
            clearIntervals = true,
            removeEventListeners = true,
            cleanupManagers = true,
            logCleanup = true
        } = options;

        const componentName = component.constructor.name || 'Component';
        
        if (logCleanup) {
            console.log(`🧹 Cleaning up ${componentName}...`);
        }

        // Clear timeouts
        if (clearTimeouts) {
            this.clearTimeouts(component);
        }

        // Clear intervals
        if (clearIntervals) {
            this.clearIntervals(component);
        }

        // Remove event listeners
        if (removeEventListeners) {
            this.removeEventListeners(component);
        }

        // Cleanup sub-managers
        if (cleanupManagers) {
            this.cleanupManagers(component);
        }

        // Component-specific cleanup
        this.performCustomCleanup(component);

        if (logCleanup) {
            console.log(`✅ ${componentName} cleanup completed`);
        }
    }

    /**
     * Clear all timeouts associated with a component
     * @param {Object} component - Component instance
     */
    static clearTimeouts(component) {
        const timeoutProperties = [
            'timeout', 'timeoutId', 'typingTimeout', 'loadTimeout',
            'connectionTimeout', 'retryTimeout', 'debounceTimeout',
            'pollingTimeout', 'refreshTimeout', 'delayTimeout'
        ];

        timeoutProperties.forEach(prop => {
            if (component[prop]) {
                clearTimeout(component[prop]);
                component[prop] = null;
            }
        });

        // Handle timeout arrays
        if (component.timeouts && Array.isArray(component.timeouts)) {
            component.timeouts.forEach(timeout => clearTimeout(timeout));
            component.timeouts = [];
        }
    }

    /**
     * Clear all intervals associated with a component
     * @param {Object} component - Component instance
     */
    static clearIntervals(component) {
        const intervalProperties = [
            'interval', 'intervalId', 'pollingInterval', 'refreshInterval',
            'updateInterval', 'monitoringInterval', 'heartbeatInterval',
            'statusInterval', 'progressInterval', 'cleanupInterval'
        ];

        intervalProperties.forEach(prop => {
            if (component[prop]) {
                clearInterval(component[prop]);
                component[prop] = null;
            }
        });

        // Handle interval arrays
        if (component.intervals && Array.isArray(component.intervals)) {
            component.intervals.forEach(interval => clearInterval(interval));
            component.intervals = [];
        }
    }

    /**
     * Remove event listeners associated with a component
     * @param {Object} component - Component instance
     */
    static removeEventListeners(component) {
        // Remove document event listeners
        if (component.eventListeners && Array.isArray(component.eventListeners)) {
            component.eventListeners.forEach(({ element, event, handler, options }) => {
                element.removeEventListener(event, handler, options);
            });
            component.eventListeners = [];
        }

        // Remove window event listeners
        if (component.windowEventListeners && Array.isArray(component.windowEventListeners)) {
            component.windowEventListeners.forEach(({ event, handler, options }) => {
                window.removeEventListener(event, handler, options);
            });
            component.windowEventListeners = [];
        }

        // Remove SocketIO listeners
        if (component.socketListeners && Array.isArray(component.socketListeners)) {
            component.socketListeners.forEach(({ event, handler }) => {
                if (window.socket) {
                    window.socket.off(event, handler);
                }
            });
            component.socketListeners = [];
        }
    }

    /**
     * Cleanup sub-managers and child components
     * @param {Object} component - Component instance
     */
    static cleanupManagers(component) {
        // Cleanup managers object
        if (component.managers && typeof component.managers === 'object') {
            Object.values(component.managers).forEach(manager => {
                if (manager && typeof manager.cleanup === 'function') {
                    try {
                        manager.cleanup();
                    } catch (error) {
                        console.warn(`Manager cleanup failed:`, error);
                    }
                }
            });
        }

        // Cleanup individual manager properties
        const managerProperties = [
            'manager', 'subManager', 'childManager', 'componentManager',
            'displayManager', 'stateManager', 'eventManager', 'apiManager'
        ];

        managerProperties.forEach(prop => {
            if (component[prop] && typeof component[prop].cleanup === 'function') {
                try {
                    component[prop].cleanup();
                } catch (error) {
                    console.warn(`${prop} cleanup failed:`, error);
                }
            }
        });
    }

    /**
     * Perform component-specific cleanup based on component type
     * @param {Object} component - Component instance
     */
    static performCustomCleanup(component) {
        const componentName = component.constructor.name;

        switch (componentName) {
            case 'ChatManager':
                this.cleanupChatManager(component);
                break;
            case 'SimplifiedLogsManager':
                this.cleanupLogsManager(component);
                break;
            case 'KnowledgeBaseManager':
                this.cleanupKBManager(component);
                break;
            case 'ScheduleManager':
                this.cleanupScheduleManager(component);
                break;
            case 'SynthesisManager':
                this.cleanupSynthesisManager(component);
                break;
            case 'StaticPagesManager':
                this.cleanupStaticPagesManager(component);
                break;
            case 'Dashboard':
            case 'UIManager':
                this.cleanupUIManager(component);
                break;
            default:
                // Generic cleanup for unknown components
                this.cleanupGenericComponent(component);
                break;
        }
    }

    /**
     * Chat-specific cleanup
     */
    static cleanupChatManager(component) {
        // Clear typing indicators
        if (component.typingTimeout) {
            clearTimeout(component.typingTimeout);
            component.typingTimeout = null;
        }
        
        // Clear any pending requests
        if (component.abortController) {
            component.abortController.abort();
            component.abortController = null;
        }
    }

    /**
     * Logs manager specific cleanup
     */
    static cleanupLogsManager(component) {
        // Clear log buffers
        if (component.logBuffer) {
            component.logBuffer = [];
        }
        
        // Clear log cache
        if (component.logCache) {
            component.logCache.clear();
        }
    }

    /**
     * Knowledge Base manager specific cleanup
     */
    static cleanupKBManager(component) {
        // Clear search debounce
        if (component.searchDebounce) {
            clearTimeout(component.searchDebounce);
            component.searchDebounce = null;
        }
        
        // Clear cached data
        if (component.cache) {
            component.cache.clear();
        }
    }

    /**
     * Schedule manager specific cleanup
     */
    static cleanupScheduleManager(component) {
        // Clear schedule timers
        if (component.scheduleTimer) {
            clearTimeout(component.scheduleTimer);
            component.scheduleTimer = null;
        }
    }

    /**
     * Synthesis manager specific cleanup
     */
    static cleanupSynthesisManager(component) {
        // Clear synthesis state
        if (component.synthesisState) {
            component.synthesisState = null;
        }
    }

    /**
     * Static pages manager specific cleanup
     */
    static cleanupStaticPagesManager(component) {
        // Clear page cache
        if (component.pageCache) {
            component.pageCache.clear();
        }
    }

    /**
     * UI manager specific cleanup
     */
    static cleanupUIManager(component) {
        // Cleanup all registered managers
        if (component.managers) {
            Object.values(component.managers).forEach(manager => {
                if (manager && typeof manager.cleanup === 'function') {
                    try {
                        manager.cleanup();
                    } catch (error) {
                        console.warn(`Manager cleanup failed:`, error);
                    }
                }
            });
        }
    }

    /**
     * Generic component cleanup
     */
    static cleanupGenericComponent(component) {
        // Clear any remaining properties that look like resources
        const resourceProperties = [
            'cache', 'buffer', 'queue', 'pool', 'connection',
            'request', 'response', 'stream', 'worker'
        ];

        resourceProperties.forEach(prop => {
            if (component[prop]) {
                // Try to cleanup if it has a cleanup method
                if (typeof component[prop].cleanup === 'function') {
                    component[prop].cleanup();
                }
                // Try to close if it has a close method
                else if (typeof component[prop].close === 'function') {
                    component[prop].close();
                }
                // Try to clear if it's a Map or Set
                else if (typeof component[prop].clear === 'function') {
                    component[prop].clear();
                }
                
                component[prop] = null;
            }
        });
    }

    /**
     * Register event listener for automatic cleanup tracking
     * @param {Object} component - Component instance
     * @param {Element} element - Element to add listener to
     * @param {string} event - Event name
     * @param {Function} handler - Event handler
     * @param {Object} options - Event options
     */
    static addEventListenerWithCleanup(component, element, event, handler, options = {}) {
        // Initialize event listeners array if not exists
        if (!component.eventListeners) {
            component.eventListeners = [];
        }

        // Add the event listener
        element.addEventListener(event, handler, options);

        // Track it for cleanup
        component.eventListeners.push({ element, event, handler, options });
    }

    /**
     * Register timeout for automatic cleanup tracking
     * @param {Object} component - Component instance
     * @param {Function} callback - Timeout callback
     * @param {number} delay - Timeout delay
     * @returns {number} Timeout ID
     */
    static setTimeoutWithCleanup(component, callback, delay) {
        const timeoutId = setTimeout(callback, delay);
        
        // Initialize timeouts array if not exists
        if (!component.timeouts) {
            component.timeouts = [];
        }
        
        component.timeouts.push(timeoutId);
        return timeoutId;
    }

    /**
     * Register interval for automatic cleanup tracking
     * @param {Object} component - Component instance
     * @param {Function} callback - Interval callback
     * @param {number} delay - Interval delay
     * @returns {number} Interval ID
     */
    static setIntervalWithCleanup(component, callback, delay) {
        const intervalId = setInterval(callback, delay);
        
        // Initialize intervals array if not exists
        if (!component.intervals) {
            component.intervals = [];
        }
        
        component.intervals.push(intervalId);
        return intervalId;
    }
}

// Make available globally
window.CleanupService = CleanupService;

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = CleanupService;
}
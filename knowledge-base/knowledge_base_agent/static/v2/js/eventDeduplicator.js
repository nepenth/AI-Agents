/* EVENT DEDUPLICATION SYSTEM */

/**
 * Centralized event deduplication system to prevent duplicate log messages
 * and status updates from multiple sources (SocketIO + API polling)
 */
class EventDeduplicator {
    constructor(options = {}) {
        this.options = {
            maxCacheSize: options.maxCacheSize || 1000,
            cacheTimeoutMs: options.cacheTimeoutMs || 30000, // 30 seconds
            debugMode: options.debugMode || false,
            ...options
        };
        
        // Cache for seen events
        this.eventCache = new Map();
        this.eventTimestamps = new Map();
        
        // Statistics
        this.stats = {
            totalEvents: 0,
            duplicatesBlocked: 0,
            cacheCleanups: 0
        };
        
        // Start cleanup interval
        this.cleanupInterval = setInterval(() => {
            this.cleanupExpiredEvents();
        }, this.options.cacheTimeoutMs / 2);
        
        console.log('🔄 EventDeduplicator initialized with options:', this.options);
    }
    
    /**
     * Generate a unique ID for an event based on its content
     */
    generateEventId(eventType, data) {
        let idComponents = [eventType];
        
        switch (eventType) {
            case 'log':
            case 'live_log':
                // For logs: use message content + level + approximate timestamp
                const message = data.message || '';
                const level = data.level || 'INFO';
                const timestamp = data.timestamp || '';
                
                // Use first 100 chars of message to avoid very long IDs
                const messageHash = message.substring(0, 100);
                
                // Round timestamp to nearest second to catch near-duplicates
                const roundedTimestamp = timestamp ? 
                    new Date(timestamp).toISOString().substring(0, 19) : 
                    new Date().toISOString().substring(0, 19);
                
                idComponents.push(level, messageHash, roundedTimestamp);
                break;
                
            case 'agent_status_update':
            case 'status_update':
                // For status: use running state + phase message + task_id
                const isRunning = data.is_running || false;
                const phaseMessage = data.current_phase_message || data.message || '';
                const taskId = data.task_id || '';
                
                idComponents.push(isRunning.toString(), phaseMessage, taskId);
                break;
                
            case 'phase_update':
            case 'phase_start':
            case 'phase_complete':
            case 'phase_error':
                // For phases: use phase_id + status + message + progress
                const phaseId = data.phase_id || data.phase_name || '';
                const status = data.status || '';
                const phaseMsg = data.message || '';
                const progress = data.progress || data.percentage || 0;
                
                idComponents.push(phaseId, status, phaseMsg, progress.toString());
                break;
                
            case 'progress_update':
                // For progress: use current + total + operation
                const current = data.current || data.processed_count || 0;
                const total = data.total || data.total_count || 0;
                const operation = data.operation || '';
                
                idComponents.push(current.toString(), total.toString(), operation);
                break;
                
            case 'gpu_stats':
                // For GPU stats: use timestamp rounded to nearest 5 seconds
                const gpuTimestamp = new Date();
                const roundedGpuTime = Math.floor(gpuTimestamp.getTime() / 5000) * 5000;
                
                idComponents.push(roundedGpuTime.toString());
                break;
                
            default:
                // For unknown events: use JSON hash
                try {
                    const jsonStr = JSON.stringify(data);
                    const hash = this.simpleHash(jsonStr);
                    idComponents.push(hash.toString());
                } catch (e) {
                    idComponents.push(Math.random().toString());
                }
        }
        
        return idComponents.join('|');
    }
    
    /**
     * Simple hash function for generating consistent IDs
     */
    simpleHash(str) {
        let hash = 0;
        if (str.length === 0) return hash;
        
        for (let i = 0; i < str.length; i++) {
            const char = str.charCodeAt(i);
            hash = ((hash << 5) - hash) + char;
            hash = hash & hash; // Convert to 32-bit integer
        }
        
        return Math.abs(hash);
    }
    
    /**
     * Check if an event is a duplicate and should be blocked
     */
    isDuplicate(eventType, data, source = 'unknown') {
        this.stats.totalEvents++;
        
        const eventId = this.generateEventId(eventType, data);
        const now = Date.now();
        
        // Check if we've seen this event recently
        if (this.eventCache.has(eventId)) {
            const lastSeen = this.eventTimestamps.get(eventId);
            const timeDiff = now - lastSeen;
            
            // If seen within timeout period, it's a duplicate
            if (timeDiff < this.options.cacheTimeoutMs) {
                this.stats.duplicatesBlocked++;
                
                if (this.options.debugMode) {
                    console.log(`🔄 Blocked duplicate ${eventType} from ${source}:`, {
                        eventId: eventId.substring(0, 50) + '...',
                        timeDiff,
                        data: eventType === 'log' ? data.message?.substring(0, 100) : data
                    });
                }
                
                return true;
            }
        }
        
        // Not a duplicate - cache it
        this.eventCache.set(eventId, true);
        this.eventTimestamps.set(eventId, now);
        
        // Cleanup if cache is getting too large
        if (this.eventCache.size > this.options.maxCacheSize) {
            this.cleanupOldestEvents();
        }
        
        if (this.options.debugMode && eventType === 'log') {
            console.log(`🔄 Allowed ${eventType} from ${source}:`, {
                eventId: eventId.substring(0, 50) + '...',
                message: data.message?.substring(0, 100)
            });
        }
        
        return false;
    }
    
    /**
     * Clean up expired events from cache
     */
    cleanupExpiredEvents() {
        const now = Date.now();
        const expiredIds = [];
        
        for (const [eventId, timestamp] of this.eventTimestamps.entries()) {
            if (now - timestamp > this.options.cacheTimeoutMs) {
                expiredIds.push(eventId);
            }
        }
        
        expiredIds.forEach(eventId => {
            this.eventCache.delete(eventId);
            this.eventTimestamps.delete(eventId);
        });
        
        if (expiredIds.length > 0) {
            this.stats.cacheCleanups++;
            console.log(`🔄 Cleaned up ${expiredIds.length} expired events from cache`);
        }
    }
    
    /**
     * Clean up oldest events when cache is full
     */
    cleanupOldestEvents() {
        const entries = Array.from(this.eventTimestamps.entries());
        entries.sort((a, b) => a[1] - b[1]); // Sort by timestamp
        
        const toRemove = entries.slice(0, Math.floor(this.options.maxCacheSize * 0.2)); // Remove oldest 20%
        
        toRemove.forEach(([eventId]) => {
            this.eventCache.delete(eventId);
            this.eventTimestamps.delete(eventId);
        });
        
        console.log(`🔄 Cleaned up ${toRemove.length} oldest events from full cache`);
    }
    
    /**
     * Get deduplication statistics
     */
    getStats() {
        return {
            ...this.stats,
            cacheSize: this.eventCache.size,
            duplicateRate: this.stats.totalEvents > 0 ? 
                (this.stats.duplicatesBlocked / this.stats.totalEvents * 100).toFixed(2) + '%' : '0%'
        };
    }
    
    /**
     * Reset statistics
     */
    resetStats() {
        this.stats = {
            totalEvents: 0,
            duplicatesBlocked: 0,
            cacheCleanups: 0
        };
    }
    
    /**
     * Clear all cached events
     */
    clearCache() {
        this.eventCache.clear();
        this.eventTimestamps.clear();
        console.log('🔄 Event deduplication cache cleared');
    }
    
    /**
     * Cleanup resources
     */
    destroy() {
        if (this.cleanupInterval) {
            clearInterval(this.cleanupInterval);
            this.cleanupInterval = null;
        }
        
        this.clearCache();
        console.log('🔄 EventDeduplicator destroyed');
    }
}

// Make available globally
window.EventDeduplicator = EventDeduplicator;
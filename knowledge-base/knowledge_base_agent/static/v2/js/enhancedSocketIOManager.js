/**
 * Enhanced SocketIO Manager
 * 
 * Provides comprehensive SocketIO client functionality with:
 * - Event validation and error handling
 * - Automatic reconnection with exponential backoff
 * - Event routing and distribution
 * - Connection status monitoring
 * - Event buffering during outages
 * - Comprehensive error recovery
 */

class EnhancedSocketIOManager {
    constructor(options = {}) {
        this.options = {
            transports: ['polling', 'websocket'],
            path: '/socket.io',
            timeout: 20000,
            forceNew: true,
            autoConnect: true,
            maxReconnectAttempts: 10,
            reconnectDelay: 1000,
            maxReconnectDelay: 30000,
            reconnectDelayGrowth: 1.5,
            ...options
        };
        
        // Connection state
        this.socket = null;
        this.isConnected = false;
        this.isConnecting = false;
        this.connectionAttempts = 0;
        this.lastConnectionTime = null;
        this.connectionId = null;
        
        // Event handling
        this.eventHandlers = new Map();
        this.eventBuffer = [];
        this.maxBufferSize = 1000;
        this.eventStats = {
            received: 0,
            processed: 0,
            errors: 0,
            buffered: 0
        };
        
        // Reconnection management
        this.reconnectTimer = null;
        this.heartbeatTimer = null;
        this.heartbeatInterval = 30000; // 30 seconds
        
        // Event validation
        this.validator = new SocketEventValidator();
        
        // Status callbacks
        this.statusCallbacks = new Set();
        
        this.initialize();
    }
    
    initialize() {
        console.log('🔌 Initializing Enhanced SocketIO Manager...');
        
        if (!window.io) {
            console.error('❌ Socket.IO library not loaded');
            this.notifyStatusChange('error', 'Socket.IO library not available');
            return;
        }
        
        this.connect();
    }
    
    connect() {
        if (this.isConnecting || this.isConnected) {
            console.log('⚠️ Connection already in progress or established');
            return;
        }
        
        this.isConnecting = true;
        this.connectionAttempts++;
        
        console.log(`🔄 Attempting connection (attempt ${this.connectionAttempts})...`);
        
        try {
            this.socket = window.io(this.options);
            this.setupEventListeners();
            this.notifyStatusChange('connecting', 'Establishing connection...');
        } catch (error) {
            console.error('❌ Failed to create socket connection:', error);
            this.handleConnectionError(error);
        }
    }
    
    setupEventListeners() {
        if (!this.socket) return;
        
        // Connection events
        this.socket.on('connect', () => this.handleConnect());
        this.socket.on('disconnect', (reason) => this.handleDisconnect(reason));
        this.socket.on('connect_error', (error) => this.handleConnectionError(error));
        this.socket.on('reconnect', (attemptNumber) => this.handleReconnect(attemptNumber));
        this.socket.on('reconnect_error', (error) => this.handleReconnectError(error));
        this.socket.on('reconnect_failed', () => this.handleReconnectFailed());
        
        // Application events
        this.setupApplicationEventListeners();
        
        // Heartbeat
        this.socket.on('pong', () => this.handleHeartbeat());
    }
    
    setupApplicationEventListeners() {
        // Core application events with validation
        const coreEvents = [
            'log', 'live_log', 'log_batch',
            'phase_update', 'phase_status_update', 'phase_start', 'phase_complete', 'phase_error',
            'progress_update', 'task_progress',
            'agent_status', 'agent_status_update', 'status_update',
            'agent_run_completed', 'generic_update'
        ];
        
        coreEvents.forEach(eventName => {
            this.socket.on(eventName, (data) => {
                this.handleIncomingEvent(eventName, data);
            });
        });
        
        // Batch events
        this.socket.on('log_batch', (data) => this.handleBatchEvent('log', data));
        this.socket.on('phase_update_batch', (data) => this.handleBatchEvent('phase_update', data));
        this.socket.on('progress_update_batch', (data) => this.handleBatchEvent('progress_update', data));
    }
    
    handleConnect() {
        console.log('✅ Socket.IO connected successfully');
        
        this.isConnected = true;
        this.isConnecting = false;
        this.connectionAttempts = 0;
        this.lastConnectionTime = new Date();
        this.connectionId = this.socket.id;
        
        // Clear reconnection timer
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }
        
        // Start heartbeat
        this.startHeartbeat();
        
        // Process buffered events
        this.processBufferedEvents();
        
        this.notifyStatusChange('connected', 'Connected successfully');
    }
    
    handleDisconnect(reason) {
        console.log(`🔌 Socket.IO disconnected: ${reason}`);
        
        this.isConnected = false;
        this.isConnecting = false;
        
        // Stop heartbeat
        this.stopHeartbeat();
        
        // Handle different disconnect reasons
        if (reason === 'io server disconnect') {
            // Server initiated disconnect, don't reconnect automatically
            this.notifyStatusChange('disconnected', 'Disconnected by server');
        } else {
            // Client-side disconnect, attempt reconnection
            this.notifyStatusChange('reconnecting', 'Connection lost, attempting to reconnect...');
            this.scheduleReconnection();
        }
    }
    
    handleConnectionError(error) {
        console.error('❌ Socket.IO connection error:', error);
        
        this.isConnecting = false;
        this.eventStats.errors++;
        
        this.notifyStatusChange('error', `Connection error: ${error.message || error}`);
        this.scheduleReconnection();
    }
    
    handleReconnect(attemptNumber) {
        console.log(`✅ Socket.IO reconnected after ${attemptNumber} attempts`);
        this.notifyStatusChange('connected', `Reconnected after ${attemptNumber} attempts`);
    }
    
    handleReconnectError(error) {
        console.error(`❌ Socket.IO reconnection error (attempt ${this.connectionAttempts}):`, error);
        this.eventStats.errors++;
    }
    
    handleReconnectFailed() {
        console.error('❌ Socket.IO reconnection failed - max attempts reached');
        this.notifyStatusChange('failed', 'Reconnection failed - max attempts reached');
    }
    
    scheduleReconnection() {
        if (this.reconnectTimer || this.connectionAttempts >= this.options.maxReconnectAttempts) {
            return;
        }
        
        const delay = Math.min(
            this.options.reconnectDelay * Math.pow(this.options.reconnectDelayGrowth, this.connectionAttempts - 1),
            this.options.maxReconnectDelay
        );
        
        console.log(`⏰ Scheduling reconnection in ${delay}ms (attempt ${this.connectionAttempts + 1})`);
        
        this.reconnectTimer = setTimeout(() => {
            this.reconnectTimer = null;
            this.connect();
        }, delay);
    }
    
    handleIncomingEvent(eventName, data) {
        this.eventStats.received++;
        
        try {
            // Validate event data
            const validationResult = this.validator.validateEvent(eventName, data);
            if (!validationResult.isValid) {
                console.warn(`⚠️ Invalid event data for '${eventName}':`, validationResult.error);
                this.eventStats.errors++;
                return;
            }
            
            // Use sanitized data
            const sanitizedData = validationResult.sanitizedData;
            
            // Route event to registered handlers
            this.routeEvent(eventName, sanitizedData);
            
            this.eventStats.processed++;
            
        } catch (error) {
            console.error(`❌ Error processing event '${eventName}':`, error);
            this.eventStats.errors++;
        }
    }
    
    handleBatchEvent(baseEventName, batchData) {
        if (!batchData || !Array.isArray(batchData.events)) {
            console.warn(`⚠️ Invalid batch data for '${baseEventName}':`, batchData);
            return;
        }
        
        console.log(`📦 Processing batch of ${batchData.events.length} '${baseEventName}' events`);
        
        // Process each event in the batch
        batchData.events.forEach((eventData, index) => {
            try {
                this.handleIncomingEvent(baseEventName, eventData);
            } catch (error) {
                console.error(`❌ Error processing batch event ${index} for '${baseEventName}':`, error);
            }
        });
    }
    
    routeEvent(eventName, data) {
        // Get handlers for this event
        const handlers = this.eventHandlers.get(eventName) || new Set();
        
        if (handlers.size === 0) {
            // Buffer unhandled events if not connected
            if (!this.isConnected) {
                this.bufferEvent(eventName, data);
            }
            return;
        }
        
        // Call all registered handlers
        handlers.forEach(handler => {
            try {
                handler(data, eventName);
            } catch (error) {
                console.error(`❌ Error in event handler for '${eventName}':`, error);
            }
        });
        
        // Also emit as custom event for legacy compatibility
        this.emitCustomEvent(eventName, data);
    }
    
    emitCustomEvent(eventName, data) {
        const customEvent = new CustomEvent(eventName, { 
            detail: data,
            bubbles: true,
            cancelable: true
        });
        document.dispatchEvent(customEvent);
    }
    
    bufferEvent(eventName, data) {
        if (this.eventBuffer.length >= this.maxBufferSize) {
            // Remove oldest event
            this.eventBuffer.shift();
        }
        
        this.eventBuffer.push({
            eventName,
            data,
            timestamp: new Date().toISOString()
        });
        
        this.eventStats.buffered++;
    }
    
    processBufferedEvents() {
        if (this.eventBuffer.length === 0) return;
        
        console.log(`📦 Processing ${this.eventBuffer.length} buffered events`);
        
        const events = [...this.eventBuffer];
        this.eventBuffer = [];
        
        events.forEach(({ eventName, data }) => {
            this.routeEvent(eventName, data);
        });
    }
    
    startHeartbeat() {
        this.stopHeartbeat();
        
        this.heartbeatTimer = setInterval(() => {
            if (this.isConnected && this.socket) {
                this.socket.emit('ping');
            }
        }, this.heartbeatInterval);
    }
    
    stopHeartbeat() {
        if (this.heartbeatTimer) {
            clearInterval(this.heartbeatTimer);
            this.heartbeatTimer = null;
        }
    }
    
    handleHeartbeat() {
        // Heartbeat received, connection is healthy
        console.debug('💓 Heartbeat received');
    }
    
    // Public API methods
    
    on(eventName, handler) {
        if (!this.eventHandlers.has(eventName)) {
            this.eventHandlers.set(eventName, new Set());
        }
        
        this.eventHandlers.get(eventName).add(handler);
        
        // Return unsubscribe function
        return () => this.off(eventName, handler);
    }
    
    off(eventName, handler) {
        const handlers = this.eventHandlers.get(eventName);
        if (handlers) {
            handlers.delete(handler);
            if (handlers.size === 0) {
                this.eventHandlers.delete(eventName);
            }
        }
    }
    
    emit(eventName, data) {
        if (!this.isConnected || !this.socket) {
            console.warn(`⚠️ Cannot emit '${eventName}' - not connected`);
            return false;
        }
        
        try {
            this.socket.emit(eventName, data);
            return true;
        } catch (error) {
            console.error(`❌ Error emitting '${eventName}':`, error);
            return false;
        }
    }
    
    disconnect() {
        console.log('🔌 Manually disconnecting Socket.IO');
        
        this.stopHeartbeat();
        
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }
        
        if (this.socket) {
            this.socket.disconnect();
            this.socket = null;
        }
        
        this.isConnected = false;
        this.isConnecting = false;
        
        this.notifyStatusChange('disconnected', 'Manually disconnected');
    }
    
    reconnect() {
        console.log('🔄 Manually triggering reconnection');
        
        this.disconnect();
        
        setTimeout(() => {
            this.connectionAttempts = 0;
            this.connect();
        }, 1000);
    }
    
    onStatusChange(callback) {
        this.statusCallbacks.add(callback);
        
        // Return unsubscribe function
        return () => this.statusCallbacks.delete(callback);
    }
    
    notifyStatusChange(status, message) {
        const statusData = {
            status,
            message,
            timestamp: new Date().toISOString(),
            connectionId: this.connectionId,
            isConnected: this.isConnected,
            connectionAttempts: this.connectionAttempts
        };
        
        console.log(`📡 Connection status: ${status} - ${message}`);
        
        this.statusCallbacks.forEach(callback => {
            try {
                callback(statusData);
            } catch (error) {
                console.error('❌ Error in status callback:', error);
            }
        });
        
        // Emit as custom event
        this.emitCustomEvent('socket_status_change', statusData);
    }
    
    getStatus() {
        return {
            isConnected: this.isConnected,
            isConnecting: this.isConnecting,
            connectionAttempts: this.connectionAttempts,
            lastConnectionTime: this.lastConnectionTime,
            connectionId: this.connectionId,
            eventStats: { ...this.eventStats },
            bufferSize: this.eventBuffer.length,
            hasHandlers: this.eventHandlers.size > 0
        };
    }
    
    getStats() {
        return {
            ...this.eventStats,
            bufferSize: this.eventBuffer.length,
            handlersCount: this.eventHandlers.size,
            connectionAttempts: this.connectionAttempts,
            isConnected: this.isConnected
        };
    }
    
    resetStats() {
        this.eventStats = {
            received: 0,
            processed: 0,
            errors: 0,
            buffered: 0
        };
    }
}

/**
 * Socket Event Validator
 * 
 * Validates and sanitizes incoming SocketIO events
 */
class SocketEventValidator {
    constructor() {
        this.validationRules = {
            log: this.validateLogEvent,
            live_log: this.validateLogEvent,
            phase_update: this.validatePhaseEvent,
            phase_status_update: this.validatePhaseEvent,
            progress_update: this.validateProgressEvent,
            agent_status: this.validateStatusEvent,
            agent_status_update: this.validateStatusEvent
        };
    }
    
    validateEvent(eventName, data) {
        try {
            // Basic validation
            if (data === null || data === undefined) {
                return {
                    isValid: false,
                    error: 'Event data is null or undefined',
                    sanitizedData: null
                };
            }
            
            // Get specific validator
            const validator = this.validationRules[eventName];
            if (validator) {
                return validator.call(this, data);
            }
            
            // Default validation for unknown events
            return this.validateGenericEvent(data);
            
        } catch (error) {
            return {
                isValid: false,
                error: `Validation error: ${error.message}`,
                sanitizedData: null
            };
        }
    }
    
    validateLogEvent(data) {
        const sanitized = {
            message: String(data.message || ''),
            level: String(data.level || 'INFO').toUpperCase(),
            timestamp: data.timestamp || new Date().toISOString()
        };
        
        // Validate log level
        const validLevels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'];
        if (!validLevels.includes(sanitized.level)) {
            sanitized.level = 'INFO';
        }
        
        // Truncate very long messages
        if (sanitized.message.length > 5000) {
            sanitized.message = sanitized.message.substring(0, 4997) + '...';
            sanitized.truncated = true;
        }
        
        return {
            isValid: true,
            error: null,
            sanitizedData: sanitized
        };
    }
    
    validatePhaseEvent(data) {
        const sanitized = {
            phase_id: String(data.phase_id || ''),
            status: String(data.status || '').toLowerCase(),
            message: String(data.message || ''),
            timestamp: data.timestamp || new Date().toISOString()
        };
        
        // Validate phase status
        const validStatuses = ['pending', 'active', 'in_progress', 'completed', 'error', 'skipped', 'interrupted'];
        if (!validStatuses.includes(sanitized.status)) {
            return {
                isValid: false,
                error: `Invalid phase status: ${sanitized.status}`,
                sanitizedData: null
            };
        }
        
        // Add progress data if present
        if (data.processed_count !== undefined && data.total_count !== undefined) {
            try {
                sanitized.processed_count = parseInt(data.processed_count);
                sanitized.total_count = parseInt(data.total_count);
                
                if (sanitized.processed_count < 0 || sanitized.total_count < 0) {
                    return {
                        isValid: false,
                        error: 'Progress counts cannot be negative',
                        sanitizedData: null
                    };
                }
                
                if (sanitized.total_count > 0) {
                    sanitized.percentage = Math.round((sanitized.processed_count / sanitized.total_count) * 100);
                }
            } catch (error) {
                // Remove invalid progress data
                delete sanitized.processed_count;
                delete sanitized.total_count;
            }
        }
        
        return {
            isValid: true,
            error: null,
            sanitizedData: sanitized
        };
    }
    
    validateProgressEvent(data) {
        try {
            const processed = parseInt(data.processed_count);
            const total = parseInt(data.total_count);
            
            if (processed < 0 || total < 0) {
                return {
                    isValid: false,
                    error: 'Progress counts cannot be negative',
                    sanitizedData: null
                };
            }
            
            if (total > 0 && processed > total) {
                return {
                    isValid: false,
                    error: 'Processed count cannot exceed total',
                    sanitizedData: null
                };
            }
            
            const sanitized = {
                processed_count: processed,
                total_count: total,
                percentage: total > 0 ? Math.round((processed / total) * 100) : 0,
                phase: String(data.phase || ''),
                timestamp: data.timestamp || new Date().toISOString()
            };
            
            return {
                isValid: true,
                error: null,
                sanitizedData: sanitized
            };
            
        } catch (error) {
            return {
                isValid: false,
                error: 'Invalid progress data format',
                sanitizedData: null
            };
        }
    }
    
    validateStatusEvent(data) {
        const sanitized = {
            is_running: Boolean(data.is_running),
            current_phase_id: data.current_phase_id ? String(data.current_phase_id) : null,
            current_phase_message: String(data.current_phase_message || ''),
            timestamp: data.timestamp || new Date().toISOString()
        };
        
        // Add optional fields if present
        if (data.task_id) {
            sanitized.task_id = String(data.task_id);
        }
        
        if (data.active_run_preferences) {
            sanitized.active_run_preferences = data.active_run_preferences;
        }
        
        return {
            isValid: true,
            error: null,
            sanitizedData: sanitized
        };
    }
    
    validateGenericEvent(data) {
        // Basic sanitization for unknown event types
        const sanitized = {
            ...data,
            timestamp: data.timestamp || new Date().toISOString()
        };
        
        return {
            isValid: true,
            error: null,
            sanitizedData: sanitized
        };
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { EnhancedSocketIOManager, SocketEventValidator };
} else {
    window.EnhancedSocketIOManager = EnhancedSocketIOManager;
    window.SocketEventValidator = SocketEventValidator;
}
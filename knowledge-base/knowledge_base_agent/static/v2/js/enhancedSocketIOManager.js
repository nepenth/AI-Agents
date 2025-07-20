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
            cancelable: true\n        });\n        document.dispatchEvent(customEvent);\n    }\n    \n    bufferEvent(eventName, data) {\n        if (this.eventBuffer.length >= this.maxBufferSize) {\n            // Remove oldest event\n            this.eventBuffer.shift();\n        }\n        \n        this.eventBuffer.push({\n            eventName,\n            data,\n            timestamp: new Date().toISOString()\n        });\n        \n        this.eventStats.buffered++;\n    }\n    \n    processBufferedEvents() {\n        if (this.eventBuffer.length === 0) return;\n        \n        console.log(`📦 Processing ${this.eventBuffer.length} buffered events`);\n        \n        const events = [...this.eventBuffer];\n        this.eventBuffer = [];\n        \n        events.forEach(({ eventName, data }) => {\n            this.routeEvent(eventName, data);\n        });\n    }\n    \n    startHeartbeat() {\n        this.stopHeartbeat();\n        \n        this.heartbeatTimer = setInterval(() => {\n            if (this.isConnected && this.socket) {\n                this.socket.emit('ping');\n            }\n        }, this.heartbeatInterval);\n    }\n    \n    stopHeartbeat() {\n        if (this.heartbeatTimer) {\n            clearInterval(this.heartbeatTimer);\n            this.heartbeatTimer = null;\n        }\n    }\n    \n    handleHeartbeat() {\n        // Heartbeat received, connection is healthy\n        console.debug('💓 Heartbeat received');\n    }\n    \n    // Public API methods\n    \n    on(eventName, handler) {\n        if (!this.eventHandlers.has(eventName)) {\n            this.eventHandlers.set(eventName, new Set());\n        }\n        \n        this.eventHandlers.get(eventName).add(handler);\n        \n        // Return unsubscribe function\n        return () => this.off(eventName, handler);\n    }\n    \n    off(eventName, handler) {\n        const handlers = this.eventHandlers.get(eventName);\n        if (handlers) {\n            handlers.delete(handler);\n            if (handlers.size === 0) {\n                this.eventHandlers.delete(eventName);\n            }\n        }\n    }\n    \n    emit(eventName, data) {\n        if (!this.isConnected || !this.socket) {\n            console.warn(`⚠️ Cannot emit '${eventName}' - not connected`);\n            return false;\n        }\n        \n        try {\n            this.socket.emit(eventName, data);\n            return true;\n        } catch (error) {\n            console.error(`❌ Error emitting '${eventName}':`, error);\n            return false;\n        }\n    }\n    \n    disconnect() {\n        console.log('🔌 Manually disconnecting Socket.IO');\n        \n        this.stopHeartbeat();\n        \n        if (this.reconnectTimer) {\n            clearTimeout(this.reconnectTimer);\n            this.reconnectTimer = null;\n        }\n        \n        if (this.socket) {\n            this.socket.disconnect();\n            this.socket = null;\n        }\n        \n        this.isConnected = false;\n        this.isConnecting = false;\n        \n        this.notifyStatusChange('disconnected', 'Manually disconnected');\n    }\n    \n    reconnect() {\n        console.log('🔄 Manually triggering reconnection');\n        \n        this.disconnect();\n        \n        setTimeout(() => {\n            this.connectionAttempts = 0;\n            this.connect();\n        }, 1000);\n    }\n    \n    onStatusChange(callback) {\n        this.statusCallbacks.add(callback);\n        \n        // Return unsubscribe function\n        return () => this.statusCallbacks.delete(callback);\n    }\n    \n    notifyStatusChange(status, message) {\n        const statusData = {\n            status,\n            message,\n            timestamp: new Date().toISOString(),\n            connectionId: this.connectionId,\n            isConnected: this.isConnected,\n            connectionAttempts: this.connectionAttempts\n        };\n        \n        console.log(`📡 Connection status: ${status} - ${message}`);\n        \n        this.statusCallbacks.forEach(callback => {\n            try {\n                callback(statusData);\n            } catch (error) {\n                console.error('❌ Error in status callback:', error);\n            }\n        });\n        \n        // Emit as custom event\n        this.emitCustomEvent('socket_status_change', statusData);\n    }\n    \n    getStatus() {\n        return {\n            isConnected: this.isConnected,\n            isConnecting: this.isConnecting,\n            connectionAttempts: this.connectionAttempts,\n            lastConnectionTime: this.lastConnectionTime,\n            connectionId: this.connectionId,\n            eventStats: { ...this.eventStats },\n            bufferSize: this.eventBuffer.length,\n            hasHandlers: this.eventHandlers.size > 0\n        };\n    }\n    \n    getStats() {\n        return {\n            ...this.eventStats,\n            bufferSize: this.eventBuffer.length,\n            handlersCount: this.eventHandlers.size,\n            connectionAttempts: this.connectionAttempts,\n            isConnected: this.isConnected\n        };\n    }\n    \n    resetStats() {\n        this.eventStats = {\n            received: 0,\n            processed: 0,\n            errors: 0,\n            buffered: 0\n        };\n    }\n}\n\n/**\n * Socket Event Validator\n * \n * Validates and sanitizes incoming SocketIO events\n */\nclass SocketEventValidator {\n    constructor() {\n        this.validationRules = {\n            log: this.validateLogEvent,\n            live_log: this.validateLogEvent,\n            phase_update: this.validatePhaseEvent,\n            phase_status_update: this.validatePhaseEvent,\n            progress_update: this.validateProgressEvent,\n            agent_status: this.validateStatusEvent,\n            agent_status_update: this.validateStatusEvent\n        };\n    }\n    \n    validateEvent(eventName, data) {\n        try {\n            // Basic validation\n            if (data === null || data === undefined) {\n                return {\n                    isValid: false,\n                    error: 'Event data is null or undefined',\n                    sanitizedData: null\n                };\n            }\n            \n            // Get specific validator\n            const validator = this.validationRules[eventName];\n            if (validator) {\n                return validator.call(this, data);\n            }\n            \n            // Default validation for unknown events\n            return this.validateGenericEvent(data);\n            \n        } catch (error) {\n            return {\n                isValid: false,\n                error: `Validation error: ${error.message}`,\n                sanitizedData: null\n            };\n        }\n    }\n    \n    validateLogEvent(data) {\n        const sanitized = {\n            message: String(data.message || ''),\n            level: String(data.level || 'INFO').toUpperCase(),\n            timestamp: data.timestamp || new Date().toISOString()\n        };\n        \n        // Validate log level\n        const validLevels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'];\n        if (!validLevels.includes(sanitized.level)) {\n            sanitized.level = 'INFO';\n        }\n        \n        // Truncate very long messages\n        if (sanitized.message.length > 5000) {\n            sanitized.message = sanitized.message.substring(0, 4997) + '...';\n            sanitized.truncated = true;\n        }\n        \n        return {\n            isValid: true,\n            error: null,\n            sanitizedData: sanitized\n        };\n    }\n    \n    validatePhaseEvent(data) {\n        const sanitized = {\n            phase_id: String(data.phase_id || ''),\n            status: String(data.status || '').toLowerCase(),\n            message: String(data.message || ''),\n            timestamp: data.timestamp || new Date().toISOString()\n        };\n        \n        // Validate phase status\n        const validStatuses = ['pending', 'active', 'in_progress', 'completed', 'error', 'skipped', 'interrupted'];\n        if (!validStatuses.includes(sanitized.status)) {\n            return {\n                isValid: false,\n                error: `Invalid phase status: ${sanitized.status}`,\n                sanitizedData: null\n            };\n        }\n        \n        // Add progress data if present\n        if (data.processed_count !== undefined && data.total_count !== undefined) {\n            try {\n                sanitized.processed_count = parseInt(data.processed_count);\n                sanitized.total_count = parseInt(data.total_count);\n                \n                if (sanitized.processed_count < 0 || sanitized.total_count < 0) {\n                    return {\n                        isValid: false,\n                        error: 'Progress counts cannot be negative',\n                        sanitizedData: null\n                    };\n                }\n                \n                if (sanitized.total_count > 0) {\n                    sanitized.percentage = Math.round((sanitized.processed_count / sanitized.total_count) * 100);\n                }\n            } catch (error) {\n                // Remove invalid progress data\n                delete sanitized.processed_count;\n                delete sanitized.total_count;\n            }\n        }\n        \n        return {\n            isValid: true,\n            error: null,\n            sanitizedData: sanitized\n        };\n    }\n    \n    validateProgressEvent(data) {\n        try {\n            const processed = parseInt(data.processed_count);\n            const total = parseInt(data.total_count);\n            \n            if (processed < 0 || total < 0) {\n                return {\n                    isValid: false,\n                    error: 'Progress counts cannot be negative',\n                    sanitizedData: null\n                };\n            }\n            \n            if (total > 0 && processed > total) {\n                return {\n                    isValid: false,\n                    error: 'Processed count cannot exceed total',\n                    sanitizedData: null\n                };\n            }\n            \n            const sanitized = {\n                processed_count: processed,\n                total_count: total,\n                percentage: total > 0 ? Math.round((processed / total) * 100) : 0,\n                phase: String(data.phase || ''),\n                timestamp: data.timestamp || new Date().toISOString()\n            };\n            \n            return {\n                isValid: true,\n                error: null,\n                sanitizedData: sanitized\n            };\n            \n        } catch (error) {\n            return {\n                isValid: false,\n                error: 'Invalid progress data format',\n                sanitizedData: null\n            };\n        }\n    }\n    \n    validateStatusEvent(data) {\n        const sanitized = {\n            is_running: Boolean(data.is_running),\n            current_phase_id: data.current_phase_id ? String(data.current_phase_id) : null,\n            current_phase_message: String(data.current_phase_message || ''),\n            timestamp: data.timestamp || new Date().toISOString()\n        };\n        \n        // Add optional fields if present\n        if (data.task_id) {\n            sanitized.task_id = String(data.task_id);\n        }\n        \n        if (data.active_run_preferences) {\n            sanitized.active_run_preferences = data.active_run_preferences;\n        }\n        \n        return {\n            isValid: true,\n            error: null,\n            sanitizedData: sanitized\n        };\n    }\n    \n    validateGenericEvent(data) {\n        // Basic sanitization for unknown event types\n        const sanitized = {\n            ...data,\n            timestamp: data.timestamp || new Date().toISOString()\n        };\n        \n        return {\n            isValid: true,\n            error: null,\n            sanitizedData: sanitized\n        };\n    }\n}\n\n// Export for use in other modules\nif (typeof module !== 'undefined' && module.exports) {\n    module.exports = { EnhancedSocketIOManager, SocketEventValidator };\n} else {\n    window.EnhancedSocketIOManager = EnhancedSocketIOManager;\n    window.SocketEventValidator = SocketEventValidator;\n}"
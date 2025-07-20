/* V2 ERRORHANDLING.JS - ERROR HANDLING AND RECOVERY IMPLEMENTATION */

/**
 * RedisConnectionManager - Manages Redis connections with automatic reconnection
 * 
 * ARCHITECTURE:
 * - Handles Redis connection failures with exponential backoff
 * - Provides connection pooling and health monitoring
 * - Implements circuit breaker pattern for resilience
 * - Buffers operations during outages
 */
class RedisConnectionManager {
    constructor(config = {}) {
        this.config = {
            host: config.host || 'localhost',
            port: config.port || 6379,
            maxRetries: config.maxRetries || 10,
            retryDelay: config.retryDelay || 1000,
            maxRetryDelay: config.maxRetryDelay || 30000,
            backoffFactor: config.backoffFactor || 2,
            healthCheckInterval: config.healthCheckInterval || 30000,
            circuitBreakerThreshold: config.circuitBreakerThreshold || 5,
            circuitBreakerTimeout: config.circuitBreakerTimeout || 60000,
            ...config
        };
        
        this.connection = null;
        this.isConnected = false;
        this.retryAttempts = 0;
        this.lastError = null;
        this.connectionPromise = null;
        
        // Circuit breaker state
        this.circuitState = 'CLOSED'; // CLOSED, OPEN, HALF_OPEN
        this.failureCount = 0;
        this.lastFailureTime = null;
        
        // Operation buffer for offline scenarios
        this.operationBuffer = [];
        this.maxBufferSize = config.maxBufferSize || 1000;
        
        // Health monitoring
        this.healthCheckTimer = null;
        
        // Event listeners
        this.eventListeners = new Map();
        
        this.init();
    }
    
    init() {
        this.startHealthCheck();
        console.log('🔗 RedisConnectionManager initialized');
    }
    
    async connect() {
        if (this.connectionPromise) {
            return this.connectionPromise;
        }
        
        this.connectionPromise = this._attemptConnection();
        return this.connectionPromise;
    }
    
    async _attemptConnection() {
        try {
            // Check circuit breaker
            if (this.circuitState === 'OPEN') {
                if (Date.now() - this.lastFailureTime < this.config.circuitBreakerTimeout) {
                    throw new Error('Circuit breaker is OPEN');
                } else {
                    this.circuitState = 'HALF_OPEN';
                    console.log('🔄 Circuit breaker moving to HALF_OPEN state');
                }
            }
            
            // Simulate Redis connection (in real implementation, this would use actual Redis client)
            console.log(`🔗 Attempting Redis connection to ${this.config.host}:${this.config.port}`);
            
            // For frontend simulation, we'll use a mock connection
            this.connection = await this._createMockConnection();
            
            this.isConnected = true;
            this.retryAttempts = 0;
            this.failureCount = 0;
            this.circuitState = 'CLOSED';
            this.connectionPromise = null;
            
            console.log('✅ Redis connection established');
            this.emit('connected', { timestamp: new Date() });
            
            // Process buffered operations
            await this._processBufferedOperations();
            
            return this.connection;
            
        } catch (error) {
            this.lastError = error;
            this.isConnected = false;
            this.failureCount++;
            this.lastFailureTime = Date.now();
            
            console.error(`❌ Redis connection failed: ${error.message}`);
            this.emit('connection_error', { error, attempt: this.retryAttempts });
            
            // Check circuit breaker threshold
            if (this.failureCount >= this.config.circuitBreakerThreshold) {
                this.circuitState = 'OPEN';
                console.log('🚨 Circuit breaker opened due to repeated failures');
                this.emit('circuit_breaker_opened', { failureCount: this.failureCount });
            }
            
            // Schedule retry if not at max attempts
            if (this.retryAttempts < this.config.maxRetries) {
                await this._scheduleRetry();
                return this._attemptConnection();
            } else {
                this.connectionPromise = null;
                this.emit('max_retries_reached', { attempts: this.retryAttempts });
                throw new Error(`Max retry attempts (${this.config.maxRetries}) reached`);
            }
        }
    }
    
    async _createMockConnection() {
        // Simulate connection delay and potential failure
        await new Promise(resolve => setTimeout(resolve, 100));
        
        // Simulate random connection failures for testing
        if (Math.random() < 0.1) { // 10% failure rate
            throw new Error('Connection timeout');
        }
        
        return {
            id: `redis_conn_${Date.now()}`,
            host: this.config.host,
            port: this.config.port,
            connected: true,
            lastActivity: new Date()
        };
    }
    
    async _scheduleRetry() {
        this.retryAttempts++;
        const delay = Math.min(
            this.config.retryDelay * Math.pow(this.config.backoffFactor, this.retryAttempts - 1),
            this.config.maxRetryDelay
        );
        
        console.log(`⏳ Scheduling Redis reconnection attempt ${this.retryAttempts} in ${delay}ms`);
        this.emit('retry_scheduled', { attempt: this.retryAttempts, delay });
        
        await new Promise(resolve => setTimeout(resolve, delay));
    }
    
    async _processBufferedOperations() {
        if (this.operationBuffer.length === 0) return;
        
        console.log(`📦 Processing ${this.operationBuffer.length} buffered operations`);
        
        const operations = [...this.operationBuffer];
        this.operationBuffer = [];
        
        for (const operation of operations) {
            try {
                await this._executeOperation(operation);
            } catch (error) {
                console.error('Failed to process buffered operation:', error);
                // Re-buffer failed operations
                this.bufferOperation(operation);
            }
        }
    }
    
    async executeOperation(operation) {
        if (!this.isConnected) {
            // Buffer operation if not connected
            this.bufferOperation(operation);
            
            // Attempt to reconnect
            try {
                await this.connect();
                return await this._executeOperation(operation);
            } catch (error) {
                throw new Error(`Operation failed - Redis not available: ${error.message}`);
            }
        }
        
        return await this._executeOperation(operation);
    }
    
    async _executeOperation(operation) {
        try {
            // Simulate Redis operation execution
            const result = await this._simulateRedisOperation(operation);
            
            // Update connection activity
            if (this.connection) {
                this.connection.lastActivity = new Date();
            }
            
            return result;
            
        } catch (error) {
            this.handleOperationError(error);
            throw error;
        }
    }
    
    async _simulateRedisOperation(operation) {
        // Simulate different Redis operations
        await new Promise(resolve => setTimeout(resolve, 10));
        
        switch (operation.type) {
            case 'SET':
                return { success: true, key: operation.key, value: operation.value };
            case 'GET':
                return { success: true, key: operation.key, value: `mock_value_${operation.key}` };
            case 'LPUSH':
                return { success: true, key: operation.key, length: Math.floor(Math.random() * 100) };
            case 'PUBLISH':
                return { success: true, channel: operation.channel, subscribers: Math.floor(Math.random() * 10) };
            default:
                return { success: true, operation: operation.type };
        }
    }
    
    bufferOperation(operation) {
        if (this.operationBuffer.length >= this.maxBufferSize) {
            // Remove oldest operation to make room
            const removed = this.operationBuffer.shift();
            console.warn('⚠️ Operation buffer full, dropping oldest operation:', removed);
            this.emit('operation_dropped', { operation: removed });
        }
        
        operation.bufferedAt = new Date();
        this.operationBuffer.push(operation);
        
        console.log(`📦 Buffered operation: ${operation.type} (buffer size: ${this.operationBuffer.length})`);
        this.emit('operation_buffered', { operation, bufferSize: this.operationBuffer.length });
    }
    
    handleOperationError(error) {
        console.error('Redis operation error:', error);
        
        // Check if error indicates connection loss
        if (this.isConnectionError(error)) {
            this.isConnected = false;
            this.connection = null;
            this.emit('connection_lost', { error, timestamp: new Date() });
            
            // Attempt reconnection
            this.connect().catch(reconnectError => {
                console.error('Reconnection failed:', reconnectError);
            });
        }
    }
    
    isConnectionError(error) {
        const connectionErrorPatterns = [
            'connection timeout',
            'connection refused',
            'connection lost',
            'network error',
            'socket error'
        ];
        
        const errorMessage = error.message.toLowerCase();
        return connectionErrorPatterns.some(pattern => errorMessage.includes(pattern));
    }
    
    startHealthCheck() {
        if (this.healthCheckTimer) {
            clearInterval(this.healthCheckTimer);
        }
        
        this.healthCheckTimer = setInterval(async () => {
            await this.performHealthCheck();
        }, this.config.healthCheckInterval);
    }
    
    async performHealthCheck() {
        if (!this.isConnected) return;
        
        try {
            // Perform a simple ping operation
            await this.executeOperation({ type: 'PING' });
            
            this.emit('health_check_passed', { timestamp: new Date() });
            
        } catch (error) {
            console.warn('Health check failed:', error);
            this.emit('health_check_failed', { error, timestamp: new Date() });
            
            // Mark as disconnected and attempt reconnection
            this.isConnected = false;
            this.connection = null;
            
            this.connect().catch(reconnectError => {
                console.error('Health check reconnection failed:', reconnectError);
            });
        }
    }
    
    getConnectionStatus() {
        return {
            isConnected: this.isConnected,
            circuitState: this.circuitState,
            retryAttempts: this.retryAttempts,
            failureCount: this.failureCount,
            bufferSize: this.operationBuffer.length,
            lastError: this.lastError?.message,
            connection: this.connection ? {
                id: this.connection.id,
                lastActivity: this.connection.lastActivity
            } : null
        };
    }
    
    // Event system
    on(event, callback) {
        if (!this.eventListeners.has(event)) {
            this.eventListeners.set(event, []);
        }
        this.eventListeners.get(event).push(callback);
    }
    
    off(event, callback) {
        if (this.eventListeners.has(event)) {
            const callbacks = this.eventListeners.get(event);
            const index = callbacks.indexOf(callback);
            if (index > -1) {
                callbacks.splice(index, 1);
            }
        }
    }
    
    emit(event, data) {
        if (this.eventListeners.has(event)) {
            this.eventListeners.get(event).forEach(callback => {
                try {
                    callback(data);
                } catch (error) {
                    console.error(`Error in event listener for ${event}:`, error);
                }
            });
        }
    }
    
    disconnect() {
        if (this.healthCheckTimer) {
            clearInterval(this.healthCheckTimer);
            this.healthCheckTimer = null;
        }
        
        this.isConnected = false;
        this.connection = null;
        this.connectionPromise = null;
        
        console.log('🔌 Redis connection manager disconnected');
        this.emit('disconnected', { timestamp: new Date() });
    }
}

/**
 * SocketIOReconnectionManager - Manages SocketIO connections with advanced reconnection logic
 * 
 * ARCHITECTURE:
 * - Implements exponential backoff with jitter
 * - Provides fallback to polling mode
 * - Handles connection state synchronization
 * - Buffers events during disconnections
 */
class SocketIOReconnectionManager {
    constructor(socketManager, config = {}) {
        this.socketManager = socketManager;
        this.config = {
            maxReconnectAttempts: config.maxReconnectAttempts || 15,
            baseDelay: config.baseDelay || 1000,
            maxDelay: config.maxDelay || 30000,
            backoffFactor: config.backoffFactor || 1.5,
            jitterFactor: config.jitterFactor || 0.1,
            pollingFallbackDelay: config.pollingFallbackDelay || 60000,
            connectionTimeout: config.connectionTimeout || 10000,
            heartbeatInterval: config.heartbeatInterval || 25000,
            ...config
        };
        
        this.reconnectAttempts = 0;
        this.isReconnecting = false;
        this.reconnectTimer = null;
        this.heartbeatTimer = null;
        this.connectionStartTime = null;
        
        // Event buffering
        this.eventBuffer = [];
        this.maxBufferSize = config.maxBufferSize || 500;
        
        // Fallback polling
        this.pollingManager = null;
        this.isPollingMode = false;
        
        // Connection state
        this.connectionState = 'DISCONNECTED'; // DISCONNECTED, CONNECTING, CONNECTED, RECONNECTING
        this.lastDisconnectReason = null;
        this.connectionHistory = [];
        
        // Event listeners
        this.eventListeners = new Map();
        
        this.init();
    }
    
    init() {
        this.setupSocketListeners();
        console.log('🔄 SocketIOReconnectionManager initialized');
    }
    
    setupSocketListeners() {
        if (!this.socketManager || !this.socketManager.socket) return;
        
        const socket = this.socketManager.socket;
        
        socket.on('connect', () => {
            this.handleConnect();
        });
        
        socket.on('disconnect', (reason) => {
            this.handleDisconnect(reason);
        });
        
        socket.on('connect_error', (error) => {
            this.handleConnectError(error);
        });
        
        socket.on('reconnect', (attemptNumber) => {
            this.handleReconnect(attemptNumber);
        });
        
        socket.on('reconnect_error', (error) => {
            this.handleReconnectError(error);
        });
        
        socket.on('reconnect_failed', () => {
            this.handleReconnectFailed();
        });
    }
    
    handleConnect() {
        console.log('✅ SocketIO connected successfully');
        
        this.connectionState = 'CONNECTED';
        this.reconnectAttempts = 0;
        this.isReconnecting = false;
        this.connectionStartTime = new Date();
        
        // Clear reconnect timer
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }
        
        // Start heartbeat
        this.startHeartbeat();
        
        // Process buffered events
        this.processBufferedEvents();
        
        // Disable polling fallback if active
        if (this.isPollingMode) {
            this.disablePollingFallback();
        }
        
        // Record connection
        this.recordConnection('CONNECTED');
        
        this.emit('connected', {
            timestamp: new Date(),
            attemptNumber: this.reconnectAttempts
        });
    }
    
    handleDisconnect(reason) {
        console.log(`🔌 SocketIO disconnected: ${reason}`);
        
        this.connectionState = 'DISCONNECTED';
        this.lastDisconnectReason = reason;
        this.isReconnecting = false;
        
        // Stop heartbeat
        this.stopHeartbeat();
        
        // Record disconnection
        this.recordConnection('DISCONNECTED', reason);
        
        this.emit('disconnected', {
            reason,
            timestamp: new Date(),
            connectionDuration: this.connectionStartTime ? 
                new Date() - this.connectionStartTime : null
        });
        
        // Determine if we should attempt reconnection
        if (this.shouldAttemptReconnection(reason)) {
            this.scheduleReconnection();
        } else {
            console.log('🚫 Not attempting reconnection due to disconnect reason:', reason);
        }
    }
    
    handleConnectError(error) {
        console.error('❌ SocketIO connection error:', error);
        
        this.connectionState = 'DISCONNECTED';
        this.recordConnection('ERROR', error.message);
        
        this.emit('connection_error', {
            error,
            timestamp: new Date(),
            attemptNumber: this.reconnectAttempts
        });
    }
    
    handleReconnect(attemptNumber) {
        console.log(`🔄 SocketIO reconnected after ${attemptNumber} attempts`);
        this.handleConnect();
    }
    
    handleReconnectError(error) {
        console.error(`❌ SocketIO reconnection error (attempt ${this.reconnectAttempts}):`, error);
        
        this.emit('reconnect_error', {
            error,
            attemptNumber: this.reconnectAttempts,
            timestamp: new Date()
        });
    }
    
    handleReconnectFailed() {
        console.error('❌ SocketIO reconnection failed - max attempts reached');
        
        this.connectionState = 'DISCONNECTED';
        this.isReconnecting = false;
        
        this.emit('reconnect_failed', {
            maxAttempts: this.config.maxReconnectAttempts,
            timestamp: new Date()
        });
        
        // Enable polling fallback
        this.enablePollingFallback();
    }
    
    shouldAttemptReconnection(reason) {
        // Don't reconnect for certain reasons
        const noReconnectReasons = [
            'io server disconnect',
            'io client disconnect',
            'ping timeout'
        ];
        
        return !noReconnectReasons.includes(reason);
    }
    
    scheduleReconnection() {
        if (this.isReconnecting || this.reconnectAttempts >= this.config.maxReconnectAttempts) {
            return;
        }
        
        this.isReconnecting = true;
        this.connectionState = 'RECONNECTING';
        this.reconnectAttempts++;
        
        const delay = this.calculateReconnectDelay();
        
        console.log(`⏳ Scheduling SocketIO reconnection attempt ${this.reconnectAttempts} in ${delay}ms`);
        
        this.emit('reconnect_scheduled', {
            attemptNumber: this.reconnectAttempts,
            delay,
            timestamp: new Date()
        });
        
        this.reconnectTimer = setTimeout(() => {
            this.attemptReconnection();
        }, delay);
    }
    
    calculateReconnectDelay() {
        // Exponential backoff with jitter
        const exponentialDelay = this.config.baseDelay * 
            Math.pow(this.config.backoffFactor, this.reconnectAttempts - 1);
        
        const cappedDelay = Math.min(exponentialDelay, this.config.maxDelay);
        
        // Add jitter to prevent thundering herd
        const jitter = cappedDelay * this.config.jitterFactor * Math.random();
        
        return Math.floor(cappedDelay + jitter);
    }
    
    attemptReconnection() {
        if (!this.isReconnecting) return;
        
        console.log(`🔄 Attempting SocketIO reconnection (${this.reconnectAttempts}/${this.config.maxReconnectAttempts})`);
        
        try {
            // Attempt to reconnect
            if (this.socketManager && this.socketManager.socket) {
                this.socketManager.socket.connect();
            } else {
                // Reinitialize socket manager
                this.socketManager.connect();
            }
            
        } catch (error) {
            console.error('Reconnection attempt failed:', error);
            this.handleReconnectError(error);
            
            // Schedule next attempt
            if (this.reconnectAttempts < this.config.maxReconnectAttempts) {
                this.scheduleReconnection();
            } else {
                this.handleReconnectFailed();
            }
        }
    }
    
    startHeartbeat() {
        if (this.heartbeatTimer) {
            clearInterval(this.heartbeatTimer);
        }
        
        this.heartbeatTimer = setInterval(() => {
            this.sendHeartbeat();
        }, this.config.heartbeatInterval);
    }
    
    stopHeartbeat() {
        if (this.heartbeatTimer) {
            clearInterval(this.heartbeatTimer);
            this.heartbeatTimer = null;
        }
    }
    
    sendHeartbeat() {
        if (this.socketManager && this.socketManager.socket && this.socketManager.socket.connected) {
            try {
                this.socketManager.socket.emit('heartbeat', {
                    timestamp: new Date().toISOString(),
                    clientId: this.socketManager.clientId || 'unknown'
                });
            } catch (error) {
                console.warn('Heartbeat failed:', error);
            }
        }
    }
    
    bufferEvent(eventName, data) {
        if (this.eventBuffer.length >= this.maxBufferSize) {
            // Remove oldest event
            const removed = this.eventBuffer.shift();
            console.warn('⚠️ Event buffer full, dropping oldest event:', removed);
            this.emit('event_dropped', { event: removed });
        }
        
        const bufferedEvent = {
            eventName,
            data,
            timestamp: new Date(),
            bufferedAt: new Date()
        };
        
        this.eventBuffer.push(bufferedEvent);
        
        console.log(`📦 Buffered event: ${eventName} (buffer size: ${this.eventBuffer.length})`);
        this.emit('event_buffered', { event: bufferedEvent, bufferSize: this.eventBuffer.length });
    }
    
    processBufferedEvents() {
        if (this.eventBuffer.length === 0) return;
        
        console.log(`📦 Processing ${this.eventBuffer.length} buffered events`);
        
        const events = [...this.eventBuffer];
        this.eventBuffer = [];
        
        events.forEach(event => {
            try {
                if (this.socketManager && this.socketManager.socket) {
                    this.socketManager.socket.emit(event.eventName, event.data);
                }
            } catch (error) {
                console.error('Failed to process buffered event:', error);
                // Re-buffer failed event
                this.bufferEvent(event.eventName, event.data);
            }
        });
        
        this.emit('events_processed', { count: events.length });
    }
    
    enablePollingFallback() {
        if (this.isPollingMode) return;
        
        console.log('🔄 Enabling polling fallback mode');
        
        this.isPollingMode = true;
        this.pollingManager = new PollingFallbackManager(this.config);
        
        this.pollingManager.start();
        
        this.emit('polling_enabled', { timestamp: new Date() });
        
        // Schedule attempt to return to SocketIO
        setTimeout(() => {
            this.attemptSocketIOReturn();
        }, this.config.pollingFallbackDelay);
    }
    
    disablePollingFallback() {
        if (!this.isPollingMode) return;
        
        console.log('✅ Disabling polling fallback mode');
        
        this.isPollingMode = false;
        
        if (this.pollingManager) {
            this.pollingManager.stop();
            this.pollingManager = null;
        }
        
        this.emit('polling_disabled', { timestamp: new Date() });
    }
    
    attemptSocketIOReturn() {
        if (!this.isPollingMode) return;
        
        console.log('🔄 Attempting to return to SocketIO from polling mode');
        
        // Reset reconnection attempts for fresh start
        this.reconnectAttempts = 0;
        this.scheduleReconnection();
    }
    
    recordConnection(state, reason = null) {
        const record = {
            state,
            reason,
            timestamp: new Date(),
            attemptNumber: this.reconnectAttempts
        };
        
        this.connectionHistory.push(record);
        
        // Limit history size
        if (this.connectionHistory.length > 100) {
            this.connectionHistory.shift();
        }
    }
    
    getConnectionStatus() {
        return {
            state: this.connectionState,
            isConnected: this.connectionState === 'CONNECTED',
            isReconnecting: this.isReconnecting,
            reconnectAttempts: this.reconnectAttempts,
            maxReconnectAttempts: this.config.maxReconnectAttempts,
            lastDisconnectReason: this.lastDisconnectReason,
            eventBufferSize: this.eventBuffer.length,
            isPollingMode: this.isPollingMode,
            connectionDuration: this.connectionStartTime ? 
                new Date() - this.connectionStartTime : null,
            history: this.connectionHistory.slice(-10) // Last 10 events
        };
    }
    
    // Event system
    on(event, callback) {
        if (!this.eventListeners.has(event)) {
            this.eventListeners.set(event, []);
        }
        this.eventListeners.get(event).push(callback);
    }
    
    off(event, callback) {
        if (this.eventListeners.has(event)) {
            const callbacks = this.eventListeners.get(event);
            const index = callbacks.indexOf(callback);
            if (index > -1) {
                callbacks.splice(index, 1);
            }
        }
    }
    
    emit(event, data) {
        if (this.eventListeners.has(event)) {
            this.eventListeners.get(event).forEach(callback => {
                try {
                    callback(data);
                } catch (error) {
                    console.error(`Error in event listener for ${event}:`, error);
                }
            });
        }
    }
    
    forceReconnect() {
        console.log('🔄 Forcing SocketIO reconnection');
        
        this.reconnectAttempts = 0;
        this.isReconnecting = false;
        
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }
        
        this.scheduleReconnection();
    }
    
    disconnect() {
        console.log('🔌 SocketIOReconnectionManager disconnecting');
        
        this.isReconnecting = false;
        this.connectionState = 'DISCONNECTED';
        
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }
        
        this.stopHeartbeat();
        this.disablePollingFallback();
        
        this.emit('manager_disconnected', { timestamp: new Date() });
    }
}

/**
 * PollingFallbackManager - Provides REST API polling when SocketIO fails
 */
class PollingFallbackManager {
    constructor(config = {}) {
        this.config = {
            pollInterval: config.pollInterval || 2000,
            endpoints: config.endpoints || [
                '/api/agent/status',
                '/api/logs/recent',
                '/api/gpu-stats'
            ],
            maxErrors: config.maxErrors || 5,
            ...config
        };
        
        this.isActive = false;
        this.pollTimers = new Map();
        this.errorCounts = new Map();
        this.lastData = new Map();
    }
    
    start() {
        if (this.isActive) return;
        
        console.log('📊 Starting polling fallback mode');
        this.isActive = true;
        
        this.config.endpoints.forEach(endpoint => {
            this.startPolling(endpoint);
        });
    }
    
    startPolling(endpoint) {
        if (this.pollTimers.has(endpoint)) {
            clearInterval(this.pollTimers.get(endpoint));
        }
        
        const timer = setInterval(async () => {
            try {
                const response = await fetch(endpoint);
                const data = await response.json();
                
                // Reset error count on success
                this.errorCounts.set(endpoint, 0);
                
                // Check if data changed
                const lastData = this.lastData.get(endpoint);
                if (JSON.stringify(data) !== JSON.stringify(lastData)) {
                    this.lastData.set(endpoint, data);
                    this.handlePollingData(endpoint, data);
                }
                
            } catch (error) {
                this.handlePollingError(endpoint, error);
            }
        }, this.config.pollInterval);
        
        this.pollTimers.set(endpoint, timer);
    }
    
    handlePollingData(endpoint, data) {
        // Convert polling data to events
        switch (endpoint) {
            case '/api/agent/status':
                document.dispatchEvent(new CustomEvent('agent_status_update', { detail: data }));
                break;
            case '/api/logs/recent':
                if (data.logs) {
                    data.logs.forEach(log => {
                        document.dispatchEvent(new CustomEvent('log', { detail: log }));
                    });
                }
                break;
            case '/api/gpu-stats':
                document.dispatchEvent(new CustomEvent('gpu_stats_update', { detail: data }));
                break;
        }
    }
    
    handlePollingError(endpoint, error) {
        const errorCount = (this.errorCounts.get(endpoint) || 0) + 1;
        this.errorCounts.set(endpoint, errorCount);
        
        console.warn(`Polling error for ${endpoint} (${errorCount}/${this.config.maxErrors}):`, error);
        
        if (errorCount >= this.config.maxErrors) {
            console.error(`Max errors reached for ${endpoint}, stopping polling`);
            this.stopPolling(endpoint);
        }
    }
    
    stopPolling(endpoint) {
        if (this.pollTimers.has(endpoint)) {
            clearInterval(this.pollTimers.get(endpoint));
            this.pollTimers.delete(endpoint);
        }
    }
    
    stop() {
        if (!this.isActive) return;
        
        console.log('📊 Stopping polling fallback mode');
        this.isActive = false;
        
        this.pollTimers.forEach((timer, endpoint) => {
            clearInterval(timer);
        });
        
        this.pollTimers.clear();
        this.errorCounts.clear();
        this.lastData.clear();
    }
}

// Make globally available
window.RedisConnectionManager = RedisConnectionManager;
window.SocketIOReconnectionManager = SocketIOReconnectionManager;
window.PollingFallbackManager = PollingFallbackManager;
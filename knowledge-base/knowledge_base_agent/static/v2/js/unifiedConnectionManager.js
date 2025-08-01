/**
 * Unified Connection Manager
 * Consolidates all connection management classes:
 * - SmartConnectionManager, EnhancedSocketIOManager
 * - RedisConnectionManager, SocketIOReconnectionManager
 * - PollingFallbackManager
 * 
 * Provides single source of truth for all connection states and strategies
 */
class UnifiedConnectionManager extends BaseManager {
    constructor(options = {}) {
        super({
            enableLogging: true,
            autoInit: false,
            ...options
        });

        // Connection state management
        this.connectionState = {
            socketIO: {
                status: 'disconnected', // disconnected, connecting, connected, error
                socket: null,
                reconnectAttempts: 0,
                lastConnected: null,
                lastError: null
            },
            redis: {
                status: 'unknown',
                lastCheck: null,
                isHealthy: true
            },
            api: {
                status: 'unknown',
                lastCheck: null,
                responseTime: null,
                isHealthy: true
            },
            overall: 'initializing' // initializing, healthy, degraded, offline
        };

        // Connection configuration
        this.config = {
            socketIO: {
                url: this.getSocketIOUrl(),
                options: {
                    transports: ['websocket', 'polling'],
                    timeout: 10000,
                    reconnection: true,
                    reconnectionAttempts: 5,
                    reconnectionDelay: 1000,
                    reconnectionDelayMax: 5000,
                    maxReconnectionAttempts: 10,
                    forceNew: false,
                    autoConnect: true,
                    upgrade: true
                }
            },
            polling: {
                enabled: true,
                interval: 5000, // 5 seconds
                endpoints: {
                    agent: '/api/agent/status',
                    logs: '/api/logs/recent',
                    gpu: '/api/gpu/stats'
                }
            },
            healthCheck: {
                interval: 30000, // 30 seconds
                timeout: 5000,
                endpoints: ['/api/health', '/api/agent/status']
            },
            fallback: {
                enablePolling: true,
                pollingInterval: 3000,
                maxFailures: 3,
                backoffMultiplier: 1.5
            },
            ...options.config
        };

        // Event handlers and callbacks
        this.eventHandlers = new Map();
        this.connectionCallbacks = new Map();
        
        // Polling and health check timers
        this.timers = {
            polling: null,
            healthCheck: null,
            reconnect: null
        };

        // Performance tracking
        this.metrics = {
            connectionAttempts: 0,
            successfulConnections: 0,
            failedConnections: 0,
            totalDowntime: 0,
            lastDowntimeStart: null
        };
    }

    /**
     * Initialize connection elements and state
     */
    async initializeElements() {
        this.log('Initializing connection elements...');

        // Connection status indicators
        this.elements.indicators = {
            socketIO: document.getElementById('socketio-status') || this.createStatusIndicator('socketio'),
            api: document.getElementById('api-status') || this.createStatusIndicator('api'),
            overall: document.getElementById('connection-status') || this.createStatusIndicator('overall')
        };

        // Connection controls
        this.elements.controls = {
            reconnect: document.getElementById('reconnect-btn'),
            togglePolling: document.getElementById('toggle-polling-btn'),
            connectionInfo: document.getElementById('connection-info')
        };

        this.log('Connection elements initialized');
    }

    /**
     * Initialize connection state and start connections
     */
    async initializeState() {
        await super.initializeState();

        // Set initial connection state
        this.setState({
            connectionState: { ...this.connectionState },
            config: { ...this.config },
            metrics: { ...this.metrics }
        });

        // Start connection initialization
        await this.initializeConnections();

        this.log('Connection state initialized');
    }

    /**
     * Setup event listeners for connection management
     */
    async setupEventListeners() {
        this.log('Setting up connection event listeners...');

        this.eventService.setupStandardListeners(this, {
            // Connection control buttons
            buttons: [
                {
                    selector: this.elements.controls.reconnect,
                    handler: () => this.reconnectAll(),
                    debounce: 1000,
                    condition: () => this.elements.controls.reconnect
                },
                {
                    selector: this.elements.controls.togglePolling,
                    handler: () => this.togglePolling(),
                    debounce: 500,
                    condition: () => this.elements.controls.togglePolling
                }
            ],

            // System events
            customEvents: [
                // SocketIO events from the global loader
                {
                    event: 'socketio-ready',
                    handler: () => this.handleSocketIOReady()
                },
                {
                    event: 'socketio-failed',
                    handler: (e) => this.handleSocketIOFailed(e.detail)
                },

                // Page visibility changes
                {
                    target: document,
                    event: 'visibilitychange',
                    handler: () => this.handleVisibilityChange()
                },

                // Network status changes
                {
                    target: window,
                    event: 'online',
                    handler: () => this.handleNetworkOnline()
                },
                {
                    target: window,
                    event: 'offline',
                    handler: () => this.handleNetworkOffline()
                },

                // Before page unload
                {
                    target: window,
                    event: 'beforeunload',
                    handler: () => this.handleBeforeUnload()
                }
            ]
        });

        this.log('Connection event listeners setup completed');
    }

    /**
     * Initialize all connections
     */
    async initializeConnections() {
        this.log('Initializing all connections...');

        try {
            // Update overall status
            this.updateConnectionState('overall', 'initializing');

            // Initialize SocketIO connection (if available)
            await this.initializeSocketIO();

            // Start health checking
            this.startHealthChecking();

            // Start polling fallback if needed
            if (this.shouldStartPolling()) {
                this.startPolling();
            }

            // Update overall status based on individual connections
            this.updateOverallStatus();

            this.log('All connections initialized');

        } catch (error) {
            this.logError('Failed to initialize connections:', error);
            this.updateConnectionState('overall', 'offline');
            throw error;
        }
    }

    /**
     * SocketIO connection management
     */
    async initializeSocketIO() {
        this.log('Initializing SocketIO connection...');

        // Check if SocketIO is available globally
        if (window.socket && window.socket.connected) {
            this.log('Using existing SocketIO connection');
            this.connectionState.socketIO.socket = window.socket;
            this.setupSocketIOListeners();
            this.updateConnectionState('socketIO', 'connected');
            return;
        }

        // Wait for SocketIO to be loaded by the global loader
        if (window.SOCKETIO_LOADING) {
            this.log('Waiting for SocketIO to load...');
            await this.waitForSocketIO();
        }

        // If SocketIO failed to load, enable polling fallback
        if (window.SOCKETIO_DISABLED || window.REST_API_MODE) {
            this.log('SocketIO disabled, using polling fallback');
            this.updateConnectionState('socketIO', 'error');
            this.startPolling();
            return;
        }

        // Initialize SocketIO connection
        if (window.socket) {
            this.connectionState.socketIO.socket = window.socket;
            this.setupSocketIOListeners();
            
            if (window.socket.connected) {
                this.updateConnectionState('socketIO', 'connected');
            } else {
                this.updateConnectionState('socketIO', 'connecting');
            }
        }
    }

    /**
     * Setup SocketIO event listeners
     */
    setupSocketIOListeners() {
        const socket = this.connectionState.socketIO.socket;
        if (!socket) return;

        this.log('Setting up SocketIO event listeners...');

        // Connection events
        socket.on('connect', () => this.handleSocketIOConnect());
        socket.on('disconnect', (reason) => this.handleSocketIODisconnect(reason));
        socket.on('connect_error', (error) => this.handleSocketIOError(error));
        socket.on('reconnect', (attemptNumber) => this.handleSocketIOReconnect(attemptNumber));
        socket.on('reconnect_error', (error) => this.handleSocketIOReconnectError(error));
        socket.on('reconnect_failed', () => this.handleSocketIOReconnectFailed());

        // Application events - delegate to registered handlers
        const appEvents = [
            'log', 'live_log', 'log_batch',
            'phase_update', 'phase_status_update', 'phase_start', 'phase_complete', 'phase_error',
            'progress_update', 'task_progress',
            'agent_status', 'agent_status_update', 'status_update',
            'agent_run_completed', 'generic_update',
            'gpu_stats', 'gpu_stats_update'
        ];

        appEvents.forEach(eventName => {
            socket.on(eventName, (data) => this.handleApplicationEvent(eventName, data));
        });

        this.log('SocketIO event listeners setup completed');
    }

    /**
     * SocketIO event handlers
     */
    handleSocketIOConnect() {
        this.log('SocketIO connected');
        
        this.updateConnectionState('socketIO', 'connected');
        this.connectionState.socketIO.lastConnected = new Date();
        this.connectionState.socketIO.reconnectAttempts = 0;
        
        this.metrics.successfulConnections++;
        
        // Stop polling if it was running
        if (this.timers.polling) {
            this.stopPolling();
        }
        
        this.updateOverallStatus();
        this.dispatchConnectionEvent('socketio_connected');
    }

    handleSocketIODisconnect(reason) {
        this.log('SocketIO disconnected:', reason);
        
        this.updateConnectionState('socketIO', 'disconnected');
        this.connectionState.socketIO.lastError = reason;
        
        // Start downtime tracking
        if (!this.metrics.lastDowntimeStart) {
            this.metrics.lastDowntimeStart = new Date();
        }
        
        // Start polling fallback
        if (this.config.fallback.enablePolling) {
            this.startPolling();
        }
        
        this.updateOverallStatus();
        this.dispatchConnectionEvent('socketio_disconnected', { reason });
    }

    handleSocketIOError(error) {
        this.logError('SocketIO connection error:', error);
        
        this.updateConnectionState('socketIO', 'error');
        this.connectionState.socketIO.lastError = error.message || error;
        
        this.metrics.failedConnections++;
        
        this.updateOverallStatus();
        this.dispatchConnectionEvent('socketio_error', { error });
    }

    handleSocketIOReconnect(attemptNumber) {
        this.log('SocketIO reconnected after', attemptNumber, 'attempts');
        
        // Update downtime tracking
        if (this.metrics.lastDowntimeStart) {
            this.metrics.totalDowntime += new Date() - this.metrics.lastDowntimeStart;
            this.metrics.lastDowntimeStart = null;
        }
        
        this.handleSocketIOConnect();
    }

    handleSocketIOReconnectError(error) {
        this.connectionState.socketIO.reconnectAttempts++;
        this.logWarn('SocketIO reconnection failed:', error, 'Attempt:', this.connectionState.socketIO.reconnectAttempts);
        
        this.dispatchConnectionEvent('socketio_reconnect_error', { error, attempts: this.connectionState.socketIO.reconnectAttempts });
    }

    handleSocketIOReconnectFailed() {
        this.logError('SocketIO reconnection failed permanently');
        
        this.updateConnectionState('socketIO', 'error');
        
        // Start polling as permanent fallback
        this.startPolling();
        
        this.updateOverallStatus();
        this.dispatchConnectionEvent('socketio_reconnect_failed');
    }

    /**
     * Application event delegation
     */
    handleApplicationEvent(eventName, data) {
        // Dispatch to registered handlers
        const handlers = this.eventHandlers.get(eventName) || [];
        handlers.forEach(handler => {
            try {
                handler(data);
            } catch (error) {
                this.logError(`Error in ${eventName} handler:`, error);
            }
        });

        // Dispatch as custom DOM event
        this.dispatchEvent('applicationEvent', { eventName, data });
        
        // Also dispatch the specific event
        document.dispatchEvent(new CustomEvent(eventName, { detail: data }));
    }

    /**
     * Polling fallback management
     */
    startPolling() {
        if (this.timers.polling) return; // Already polling

        this.log('Starting polling fallback...');

        const pollInterval = this.config.polling.interval;
        
        this.timers.polling = setInterval(async () => {
            await this.performPollingUpdate();
        }, pollInterval);

        this.dispatchConnectionEvent('polling_started');
    }

    stopPolling() {
        if (!this.timers.polling) return;

        this.log('Stopping polling fallback...');

        clearInterval(this.timers.polling);
        this.timers.polling = null;

        this.dispatchConnectionEvent('polling_stopped');
    }

    async performPollingUpdate() {
        try {
            // Poll agent status
            const agentStatus = await this.apiCall('/api/agent/status', {
                timeout: 3000,
                showErrors: false,
                cache: false
            });

            if (agentStatus) {
                this.handleApplicationEvent('agent_status_update', agentStatus);
            }

            // Poll recent logs
            const logs = await this.apiCall('/api/logs/recent', {
                timeout: 3000,
                showErrors: false,
                cache: false
            });

            if (logs && logs.length > 0) {
                logs.forEach(log => {
                    this.handleApplicationEvent('log', log);
                });
            }

            // Update API connection status
            this.updateConnectionState('api', 'connected');

        } catch (error) {
            this.logWarn('Polling update failed:', error);
            this.updateConnectionState('api', 'error');
        }
    }

    /**
     * Health checking
     */
    startHealthChecking() {
        if (this.timers.healthCheck) return;

        this.log('Starting health checking...');

        const checkInterval = this.config.healthCheck.interval;
        
        this.timers.healthCheck = setInterval(async () => {
            await this.performHealthCheck();
        }, checkInterval);

        // Perform initial health check
        this.performHealthCheck();
    }

    stopHealthChecking() {
        if (!this.timers.healthCheck) return;

        clearInterval(this.timers.healthCheck);
        this.timers.healthCheck = null;
    }

    async performHealthCheck() {
        this.log('Performing health check...');

        try {
            const startTime = Date.now();
            
            // Check API health
            const healthResponse = await this.apiCall('/api/health', {
                timeout: this.config.healthCheck.timeout,
                showErrors: false,
                cache: false
            });

            const responseTime = Date.now() - startTime;
            
            this.connectionState.api.responseTime = responseTime;
            this.connectionState.api.lastCheck = new Date();
            this.connectionState.api.isHealthy = true;
            
            this.updateConnectionState('api', 'connected');

        } catch (error) {
            this.connectionState.api.lastCheck = new Date();
            this.connectionState.api.isHealthy = false;
            
            this.updateConnectionState('api', 'error');
            this.logWarn('Health check failed:', error);
        }

        this.updateOverallStatus();
    }

    /**
     * Connection state management
     */
    updateConnectionState(connectionType, status) {
        const previousStatus = this.connectionState[connectionType]?.status;
        
        if (this.connectionState[connectionType]) {
            this.connectionState[connectionType].status = status;
        }

        // Update UI indicators
        this.updateStatusIndicator(connectionType, status);

        // Dispatch status change event if changed
        if (previousStatus !== status) {
            this.dispatchConnectionEvent('status_changed', {
                connectionType,
                previousStatus,
                currentStatus: status
            });
        }

        this.log(`${connectionType} connection status:`, status);
    }

    updateOverallStatus() {
        const socketIOStatus = this.connectionState.socketIO.status;
        const apiStatus = this.connectionState.api.status;

        let overallStatus;

        if (socketIOStatus === 'connected' && apiStatus === 'connected') {
            overallStatus = 'healthy';
        } else if (socketIOStatus === 'connected' || apiStatus === 'connected') {
            overallStatus = 'degraded';
        } else if (socketIOStatus === 'connecting' || apiStatus === 'connecting') {
            overallStatus = 'connecting';
        } else {
            overallStatus = 'offline';
        }

        const previousStatus = this.connectionState.overall;
        this.connectionState.overall = overallStatus;

        this.updateStatusIndicator('overall', overallStatus);

        if (previousStatus !== overallStatus) {
            this.dispatchConnectionEvent('overall_status_changed', {
                previousStatus,
                currentStatus: overallStatus
            });
        }
    }

    /**
     * UI management
     */
    createStatusIndicator(type) {
        const indicator = document.createElement('div');
        indicator.id = `${type}-status`;
        indicator.className = `connection-status-indicator status-${type}`;
        indicator.innerHTML = `
            <div class="status-dot"></div>
            <span class="status-text">${type}</span>
        `;
        
        // Add to appropriate container
        const container = document.querySelector('.connection-indicators') || 
                         document.querySelector('.header-controls') ||
                         document.body;
        
        container.appendChild(indicator);
        return indicator;
    }

    updateStatusIndicator(connectionType, status) {
        const indicator = this.elements.indicators[connectionType];
        if (!indicator) return;

        // Update classes
        indicator.className = `connection-status-indicator status-${connectionType} status-${status}`;
        
        // Update text
        const statusText = indicator.querySelector('.status-text');
        if (statusText) {
            statusText.textContent = `${connectionType}: ${status}`;
        }

        // Update tooltip
        indicator.title = this.getStatusTooltip(connectionType, status);
    }

    getStatusTooltip(connectionType, status) {
        const connection = this.connectionState[connectionType];
        if (!connection) return `${connectionType}: ${status}`;

        let tooltip = `${connectionType}: ${status}`;
        
        if (connection.lastConnected) {
            tooltip += `\nLast connected: ${connection.lastConnected.toLocaleString()}`;
        }
        
        if (connection.lastError) {
            tooltip += `\nLast error: ${connection.lastError}`;
        }
        
        if (connection.responseTime) {
            tooltip += `\nResponse time: ${connection.responseTime}ms`;
        }

        return tooltip;
    }

    /**
     * Event management
     */
    registerEventHandler(eventName, handler) {
        if (!this.eventHandlers.has(eventName)) {
            this.eventHandlers.set(eventName, []);
        }
        
        this.eventHandlers.get(eventName).push(handler);
        
        // Return unregister function
        return () => {
            const handlers = this.eventHandlers.get(eventName) || [];
            const index = handlers.indexOf(handler);
            if (index > -1) {
                handlers.splice(index, 1);
            }
        };
    }

    dispatchConnectionEvent(eventName, data = {}) {
        const event = new CustomEvent(`connection_${eventName}`, {
            detail: {
                connectionState: { ...this.connectionState },
                metrics: { ...this.metrics },
                timestamp: Date.now(),
                ...data
            }
        });
        
        document.dispatchEvent(event);
        this.log('Connection event dispatched:', eventName, data);
    }

    /**
     * System event handlers
     */
    handleSocketIOReady() {
        this.log('SocketIO ready event received');
        this.initializeSocketIO();
    }

    handleSocketIOFailed(detail) {
        this.log('SocketIO failed event received:', detail);
        this.updateConnectionState('socketIO', 'error');
        this.startPolling();
    }

    handleVisibilityChange() {
        if (document.hidden) {
            this.log('Page hidden - reducing connection activity');
            // Could reduce polling frequency here
        } else {
            this.log('Page visible - resuming normal connection activity');
            // Perform immediate health check
            this.performHealthCheck();
        }
    }

    handleNetworkOnline() {
        this.log('Network online - attempting to reconnect');
        this.reconnectAll();
    }

    handleNetworkOffline() {
        this.log('Network offline - updating connection status');
        this.updateConnectionState('socketIO', 'offline');
        this.updateConnectionState('api', 'offline');
        this.updateOverallStatus();
    }

    handleBeforeUnload() {
        this.log('Page unloading - cleaning up connections');
        this.cleanup();
    }

    /**
     * Utility methods
     */
    getSocketIOUrl() {
        const protocol = window.location.protocol === 'https:' ? 'https:' : 'http:';
        const host = window.location.hostname;
        const port = window.location.port || (protocol === 'https:' ? '443' : '80');
        return `${protocol}//${host}:${port}`;
    }

    async waitForSocketIO(timeout = 10000) {
        return new Promise((resolve, reject) => {
            const checkInterval = 100;
            let elapsed = 0;
            
            const check = () => {
                if (!window.SOCKETIO_LOADING) {
                    resolve();
                } else if (elapsed >= timeout) {
                    reject(new Error('SocketIO loading timeout'));
                } else {
                    elapsed += checkInterval;
                    setTimeout(check, checkInterval);
                }
            };
            
            check();
        });
    }

    shouldStartPolling() {
        return this.config.fallback.enablePolling && 
               (this.connectionState.socketIO.status !== 'connected');
    }

    togglePolling() {
        if (this.timers.polling) {
            this.stopPolling();
        } else {
            this.startPolling();
        }
    }

    async reconnectAll() {
        this.log('Reconnecting all connections...');

        try {
            // Reconnect SocketIO
            if (this.connectionState.socketIO.socket) {
                this.connectionState.socketIO.socket.disconnect();
                this.connectionState.socketIO.socket.connect();
            } else {
                await this.initializeSocketIO();
            }

            // Perform health check
            await this.performHealthCheck();

            this.log('Reconnection completed');

        } catch (error) {
            this.logError('Reconnection failed:', error);
        }
    }

    /**
     * Public API methods
     */
    getConnectionStatus() {
        return {
            ...this.connectionState,
            metrics: { ...this.metrics }
        };
    }

    isConnected() {
        return this.connectionState.overall === 'healthy' || 
               this.connectionState.overall === 'degraded';
    }

    isSocketIOConnected() {
        return this.connectionState.socketIO.status === 'connected';
    }

    isAPIConnected() {
        return this.connectionState.api.status === 'connected';
    }

    getMetrics() {
        return { ...this.metrics };
    }

    /**
     * Cleanup
     */
    cleanup() {
        this.log('Cleaning up connections...');

        // Stop all timers
        Object.values(this.timers).forEach(timer => {
            if (timer) clearInterval(timer);
        });

        // Disconnect SocketIO
        if (this.connectionState.socketIO.socket) {
            this.connectionState.socketIO.socket.disconnect();
        }

        // Clear event handlers
        this.eventHandlers.clear();

        // Call parent cleanup
        super.cleanup();

        this.log('Connection cleanup completed');
    }
}

// Make available globally
window.UnifiedConnectionManager = UnifiedConnectionManager;

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = UnifiedConnectionManager;
}
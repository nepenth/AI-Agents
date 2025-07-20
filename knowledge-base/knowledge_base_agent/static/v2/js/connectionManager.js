/* SMART CONNECTION MANAGER */

/**
 * Intelligent connection manager that chooses between SocketIO and API polling
 * based on connection availability and reliability
 */
class SmartConnectionManager {
    constructor(api, options = {}) {
        this.api = api;
        this.options = {
            pollingInterval: options.pollingInterval || 2000,
            connectionCheckInterval: options.connectionCheckInterval || 5000,
            maxReconnectAttempts: options.maxReconnectAttempts || 5,
            fallbackDelay: options.fallbackDelay || 3000,
            debugMode: options.debugMode || false,
            ...options
        };
        
        // Connection state
        this.socketIOAvailable = false;
        this.socketIOConnected = false;
        this.pollingActive = false;
        this.preferredSource = 'socketio'; // 'socketio' or 'polling'
        this.currentSource = null;
        
        // Event handlers
        this.eventHandlers = new Map();
        this.pollingIntervals = new Map();
        
        // Statistics
        this.stats = {
            socketIOEvents: 0,
            pollingEvents: 0,
            connectionSwitches: 0,
            lastSwitch: null
        };
        
        // Initialize
        this.init();
    }
    
    async init() {
        console.log('🔌 SmartConnectionManager initializing...');
        
        // Check if SocketIO is available
        this.checkSocketIOAvailability();
        
        // Set up connection monitoring
        this.startConnectionMonitoring();
        
        // Choose initial connection method
        await this.selectConnectionMethod();
        
        console.log('🔌 SmartConnectionManager initialized with source:', this.currentSource);
    }
    
    checkSocketIOAvailability() {
        this.socketIOAvailable = !!(window.io && window.socket);
        
        if (this.socketIOAvailable) {
            this.setupSocketIOListeners();
        }
        
        console.log('🔌 SocketIO availability:', this.socketIOAvailable);
    }
    
    setupSocketIOListeners() {
        if (!window.socket) return;
        
        // Monitor connection state
        window.socket.on('connect', () => {
            this.socketIOConnected = true;
            console.log('🔌 SocketIO connected');
            this.onConnectionChange();
        });
        
        window.socket.on('disconnect', () => {
            this.socketIOConnected = false;
            console.log('🔌 SocketIO disconnected');
            this.onConnectionChange();
        });
        
        window.socket.on('connect_error', (error) => {
            console.warn('🔌 SocketIO connection error:', error);
            this.socketIOConnected = false;
            this.onConnectionChange();
        });
    }
    
    startConnectionMonitoring() {
        setInterval(() => {
            this.checkConnectionHealth();
        }, this.options.connectionCheckInterval);
    }
    
    async checkConnectionHealth() {
        // Check SocketIO health
        if (this.socketIOAvailable && window.socket) {
            this.socketIOConnected = window.socket.connected;
        }
        
        // If current source is unhealthy, switch
        if (this.currentSource === 'socketio' && !this.socketIOConnected) {
            console.log('🔌 SocketIO unhealthy, considering switch to polling');
            await this.selectConnectionMethod();
        } else if (this.currentSource === 'polling' && this.socketIOConnected) {
            console.log('🔌 SocketIO recovered, considering switch from polling');
            await this.selectConnectionMethod();
        }
    }
    
    async selectConnectionMethod() {
        const previousSource = this.currentSource;
        
        // Prefer SocketIO if available and connected
        if (this.socketIOAvailable && this.socketIOConnected) {
            this.currentSource = 'socketio';
            await this.activateSocketIO();
            this.deactivatePolling();
        } else {
            this.currentSource = 'polling';
            this.deactivateSocketIO();
            await this.activatePolling();
        }
        
        // Track connection switches
        if (previousSource && previousSource !== this.currentSource) {
            this.stats.connectionSwitches++;
            this.stats.lastSwitch = new Date().toISOString();
            console.log(`🔌 Connection switched from ${previousSource} to ${this.currentSource}`);
            
            // Emit connection change event
            this.emitEvent('connection_changed', {
                from: previousSource,
                to: this.currentSource,
                timestamp: this.stats.lastSwitch
            });
        }
    }
    
    async activateSocketIO() {
        if (!this.socketIOAvailable || !window.socket) return;
        
        console.log('🔌 Activating SocketIO event listeners');
        
        // Set up event forwarding from SocketIO to our event system
        const socketEvents = [
            'log',
            'live_log', 
            'agent_status_update',
            'status_update',
            'phase_update',
            'phase_start',
            'phase_complete', 
            'phase_error',
            'progress_update',
            'gpu_stats',
            'logs_cleared'
        ];
        
        socketEvents.forEach(eventName => {
            // Remove existing listener to prevent duplicates
            window.socket.off(eventName);
            
            // Add new listener
            window.socket.on(eventName, (data) => {
                this.stats.socketIOEvents++;
                this.emitEvent(eventName, data, 'socketio');
            });
        });
        
        // Request initial data
        if (window.socket.connected) {
            window.socket.emit('request_initial_status_and_git_config');
            window.socket.emit('request_initial_logs');
            window.socket.emit('request_gpu_stats');
        }
    }
    
    deactivateSocketIO() {
        if (!window.socket) return;
        
        console.log('🔌 Deactivating SocketIO event listeners');
        
        // Remove all our event listeners
        const socketEvents = [
            'log', 'live_log', 'agent_status_update', 'status_update',
            'phase_update', 'phase_start', 'phase_complete', 'phase_error',
            'progress_update', 'gpu_stats', 'logs_cleared'
        ];
        
        socketEvents.forEach(eventName => {
            window.socket.off(eventName);
        });
    }
    
    async activatePolling() {
        console.log('🔌 Activating API polling');
        this.pollingActive = true;
        
        // Start polling for different data types
        this.startPolling('agent_status', '/agent/status', this.options.pollingInterval);
        this.startPolling('logs', '/logs/recent', this.options.pollingInterval + 500); // Offset to spread load
        this.startPolling('gpu_stats', '/gpu-stats', this.options.pollingInterval * 2); // Less frequent
        
        // Load initial data
        await this.loadInitialPollingData();
    }
    
    deactivatePolling() {
        console.log('🔌 Deactivating API polling');
        this.pollingActive = false;
        
        // Stop all polling intervals
        this.pollingIntervals.forEach((interval, name) => {
            clearInterval(interval);
            console.log(`🔌 Stopped polling for ${name}`);
        });
        this.pollingIntervals.clear();
    }
    
    startPolling(name, endpoint, interval) {
        // Clear existing interval if any
        if (this.pollingIntervals.has(name)) {
            clearInterval(this.pollingIntervals.get(name));
        }
        
        // Start new polling interval
        const intervalId = setInterval(async () => {
            if (!this.pollingActive) return;
            
            try {
                const response = await this.api.request(endpoint);
                this.handlePollingResponse(name, response);
            } catch (error) {
                if (this.options.debugMode) {
                    console.warn(`🔌 Polling failed for ${name}:`, error);
                }
            }
        }, interval);
        
        this.pollingIntervals.set(name, intervalId);
        console.log(`🔌 Started polling ${name} every ${interval}ms`);
    }
    
    async loadInitialPollingData() {
        try {
            // Load initial data in parallel
            const [statusResponse, logsResponse, gpuResponse] = await Promise.allSettled([
                this.api.request('/agent/status'),
                this.api.request('/logs/recent'),
                this.api.request('/gpu-stats')
            ]);
            
            if (statusResponse.status === 'fulfilled') {
                this.handlePollingResponse('agent_status', statusResponse.value);
            }
            
            if (logsResponse.status === 'fulfilled') {
                this.handlePollingResponse('logs', logsResponse.value);
            }
            
            if (gpuResponse.status === 'fulfilled') {
                this.handlePollingResponse('gpu_stats', gpuResponse.value);
            }
            
        } catch (error) {
            console.error('🔌 Failed to load initial polling data:', error);
        }
    }
    
    handlePollingResponse(type, data) {
        this.stats.pollingEvents++;
        
        switch (type) {
            case 'agent_status':
                this.emitEvent('agent_status_update', data, 'polling');
                
                // Extract phase information if available
                if (data.current_phase_message || data.phase_id) {
                    this.emitEvent('phase_update', {
                        phase_id: data.phase_id || 'unknown',
                        status: data.is_running ? 'running' : 'idle',
                        message: data.current_phase_message,
                        progress: data.progress_percentage || data.progress
                    }, 'polling');
                }
                break;
                
            case 'logs':
                if (data.logs && data.logs.length > 0) {
                    data.logs.forEach(log => {
                        this.emitEvent('log', {
                            message: log.message,
                            level: log.level,
                            timestamp: new Date().toISOString()
                        }, 'polling');
                    });
                }
                break;
                
            case 'gpu_stats':
                if (data.gpus) {
                    this.emitEvent('gpu_stats', { gpus: data.gpus }, 'polling');
                }
                break;
        }
    }
    
    emitEvent(eventName, data, source = 'unknown') {
        // Create custom event
        const event = new CustomEvent(eventName, { 
            detail: { ...data, _source: source, _timestamp: Date.now() }
        });
        
        // Emit to document
        document.dispatchEvent(event);
        
        if (this.options.debugMode) {
            console.log(`🔌 Emitted ${eventName} from ${source}:`, data);
        }
    }
    
    onConnectionChange() {
        // Debounce connection changes
        clearTimeout(this.connectionChangeTimeout);
        this.connectionChangeTimeout = setTimeout(() => {
            this.selectConnectionMethod();
        }, this.options.fallbackDelay);
    }
    
    /**
     * Get current connection status
     */
    getStatus() {
        return {
            currentSource: this.currentSource,
            socketIOAvailable: this.socketIOAvailable,
            socketIOConnected: this.socketIOConnected,
            pollingActive: this.pollingActive,
            stats: this.stats
        };
    }
    
    /**
     * Force switch to specific connection method
     */
    async forceSwitch(method) {
        if (method === 'socketio' && !this.socketIOAvailable) {
            throw new Error('SocketIO not available');
        }
        
        console.log(`🔌 Force switching to ${method}`);
        
        if (method === 'socketio') {
            this.currentSource = 'socketio';
            await this.activateSocketIO();
            this.deactivatePolling();
        } else {
            this.currentSource = 'polling';
            this.deactivateSocketIO();
            await this.activatePolling();
        }
    }
    
    /**
     * Cleanup resources
     */
    destroy() {
        console.log('🔌 SmartConnectionManager destroying...');
        
        this.deactivatePolling();
        this.deactivateSocketIO();
        
        if (this.connectionChangeTimeout) {
            clearTimeout(this.connectionChangeTimeout);
        }
        
        console.log('🔌 SmartConnectionManager destroyed');
    }
}

// Make available globally
window.SmartConnectionManager = SmartConnectionManager;
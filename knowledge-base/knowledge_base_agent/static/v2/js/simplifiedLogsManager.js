/* SIMPLIFIED LOGS MANAGER - CLEAN ARCHITECTURE */

/**
 * Enhanced Live Logs Manager with PostgreSQL backend support
 * 
 * ARCHITECTURE:
 * 1. Page Load: Fetch logs via PostgreSQL REST API
 * 2. Active Tasks: Use SocketIO events for real-time updates + PostgreSQL polling
 * 3. Historical Tasks: Load complete logs from PostgreSQL for completed tasks
 * 4. Fallback: PostgreSQL polling if SocketIO fails
 */
class SimplifiedLogsManager {
    constructor(api) {
        this.api = api;
        
        // UI Elements
        this.logsContainer = document.getElementById('logs-container');
        this.clearLogsBtn = document.getElementById('clear-logs-btn');
        this.connectionStatus = document.getElementById('connection-status');
        this.logCount = document.getElementById('log-count');
        
        // State management
        this.logs = [];
        this.maxLogs = 500; // Limit logs in memory
        this.autoScroll = true;
        this.isInitialized = false;
        // Prefer a single source of truth when possible
        this.usePostgreSQL = false;
        // Dedupe recent logs by sequence or message hash
        this.recentLogKeys = new Set();
        this.maxRecentKeys = 1000;
        
        // PostgreSQL logging state
        this.currentTaskId = null;
        this.latestSequenceNumber = 0;
        this.isHistoricalMode = false;
        this.postgresqlPolling = null;
        this.postgresqlPollingInterval = 3000; // 3 seconds for PostgreSQL polling
        
        // Connection management
        this.socketConnected = false;
        this.emergencyPolling = null;
        this.emergencyPollingInterval = 5000; // 5 seconds
        
        // Statistics
        this.stats = {
            totalLogs: 0,
            logsFromSocket: 0,
            logsFromPolling: 0,
            connectionSwitches: 0,
            filteredLogs: 0,
            displayedLogs: 0
        };

        if (!this.logsContainer) {
            console.warn('Logs container not found - SimplifiedLogsManager disabled');
            return;
        }
        
        this.init();
    }

    async init() {
        console.log('📝 SimplifiedLogsManager initializing...');
        
        // Set up event listeners
        this.setupEventListeners();
        
        // Set up SocketIO listeners
        this.setupSocketIOListeners();
        
        // Load initial logs
        await this.loadInitialLogs();
        
        // Mark as initialized
        this.isInitialized = true;
        
        console.log('✅ SimplifiedLogsManager initialized');
    }

    setupEventListeners() {
        // Use centralized EventListenerService
        EventListenerService.setupStandardListeners(this, {
            buttons: [
                {
                    selector: this.clearLogsBtn,
                    handler: () => this.clearLogs(),
                    debounce: 500 // Prevent accidental double-clicks
                }
            ],
            customEvents: [
                {
                    target: this.logsContainer,
                    event: 'scroll',
                    handler: () => {
                        const { scrollTop, scrollHeight, clientHeight } = this.logsContainer;
                        this.autoScroll = scrollTop + clientHeight >= scrollHeight - 10;
                    },
                    throttle: 100 // Throttle scroll events for performance
                },
                {
                    target: this.logsContainer,
                    event: 'dblclick',
                    handler: () => {
                        this.autoScroll = !this.autoScroll;
                        if (this.autoScroll) {
                            this.scrollToBottom();
                            this.showConnectionMessage('Auto-scroll enabled', 'info');
                        } else {
                            this.showConnectionMessage('Auto-scroll disabled', 'info');
                        }
                    }
                },
                {
                    event: 'socketio-ready',
                    handler: () => this.initializeSocketIOListeners()
                },
                {
                    event: 'socketio-failed',
                    handler: () => {
                        console.warn('SocketIO not available - using polling fallback');
                        this.startEmergencyPolling();
                    }
                }
            ],
            keyboard: [
                {
                    key: 'l',
                    ctrlKey: true,
                    handler: () => this.clearLogs()
                }
            ]
        });
    }

    setupSocketIOListeners() {
        // Listen for SocketIO ready event from the async loader
        document.addEventListener('socketio-ready', () => {
            this.initializeSocketIOListeners();
        });
        
        document.addEventListener('socketio-failed', () => {
            console.warn('SocketIO not available - using polling fallback');
            this.startEmergencyPolling();
        });
        
        // Check if SocketIO is already available (in case we missed the event)
        if (window.socket) {
            this.initializeSocketIOListeners();
        } else {
            // Start with polling until SocketIO is available
            this.startEmergencyPolling();
        }
    }
    
    initializeSocketIOListeners() {
        if (!window.socket) {
            console.warn('SocketIO not available - using polling fallback');
            this.startEmergencyPolling();
            return;
        }
        
        console.log('📝 Setting up SocketIO listeners for logs');
        
        // Stop emergency polling since SocketIO is available
        this.stopEmergencyPolling();

        // Connection status monitoring
        window.socket.on('connect', () => {
            this.socketConnected = true;
            this.stats.connectionSwitches++;
            console.log('🔌 SocketIO connected');
            this.updateConnectionStatus('connected');
            this.stopEmergencyPolling();
        });

        window.socket.on('disconnect', () => {
            this.socketConnected = false;
            this.stats.connectionSwitches++;
            console.log('🔌 SocketIO disconnected');
            this.updateConnectionStatus('disconnected');
            this.startEmergencyPolling();
        });

        window.socket.on('connect_error', (error) => {
            console.warn('🔌 SocketIO connection error:', error);
            this.updateConnectionStatus('error');
            this.startEmergencyPolling();
            
            // Enhanced reconnection logic
            this.handleConnectionError(error);
        });
        
        // Add reconnection event handlers
        window.socket.on('reconnect', (attemptNumber) => {
            console.log(`🔌 SocketIO reconnected after ${attemptNumber} attempts`);
            this.updateConnectionStatus('connected');
            this.stopEmergencyPolling();
            this.showConnectionMessage('Connection restored', 'success');
        });
        
        window.socket.on('reconnect_attempt', (attemptNumber) => {
            console.log(`🔌 SocketIO reconnection attempt ${attemptNumber}`);
            this.updateConnectionStatus('reconnecting');
        });
        
        window.socket.on('reconnect_error', (error) => {
            console.warn('🔌 SocketIO reconnection error:', error);
            this.updateConnectionStatus('error');
        });
        
        window.socket.on('reconnect_failed', () => {
            console.error('🔌 SocketIO reconnection failed - switching to polling mode');
            this.updateConnectionStatus('polling');
            this.showConnectionMessage('Connection failed - using polling mode', 'warning');
        });

        // Log event listeners - SINGLE SOURCE OF TRUTH
        window.socket.on('log', (logData) => {
            if (!this.usePostgreSQL) {
                this.handleNewLog(logData, 'socketio');
            }
        });

        window.socket.on('live_log', (logData) => {
            if (!this.usePostgreSQL) {
                this.handleNewLog(logData, 'socketio');
            }
        });

        // CRITICAL FIX: Add phase update listeners
        window.socket.on('phase_update', (phaseData) => {
            this.handlePhaseUpdate(phaseData, 'socketio');
        });

        window.socket.on('phase_status_update', (phaseData) => {
            this.handlePhaseUpdate(phaseData, 'socketio');
        });

        window.socket.on('task_progress', (progressData) => {
            this.handleProgressUpdate(progressData, 'socketio');
        });

        // Other real-time events
        window.socket.on('logs_cleared', () => {
            this.handleLogsCleared();
        });

        // Initial connection status
        this.socketConnected = window.socket.connected;
        this.updateConnectionStatus(this.socketConnected ? 'connected' : 'disconnected');
    }

    async loadInitialLogs() {
        try {
            console.log('📝 Loading initial logs...');
            this.showLoadingState();
            
            // CRITICAL FIX: Clean log flow - check agent status first to determine approach
            const statusResponse = await this.api.getAgentStatus();
            const agentIsRunning = statusResponse?.is_running || false;
            const currentTaskId = statusResponse?.current_task_id || statusResponse?.task_id;
            
            if (agentIsRunning && currentTaskId) {
                // Agent is running - load recent logs for this task only
                console.log(`📝 Agent is running with task: ${currentTaskId}, loading task-specific logs`);
                this.currentTaskId = currentTaskId;
                
                const success = await this.loadPostgreSQLLogs(currentTaskId, false);
                if (success) {
                    // Start PostgreSQL polling for new logs (no SocketIO duplication)
                    this.startPostgreSQLPolling();
                } else {
                    this.showEmptyState('No logs available for current task. Logs will appear as the agent runs.');
                }
            } else {
                // Agent is idle - try to load recent historical logs
                console.log('📝 Agent is idle, loading recent historical logs');
                this.usePostgreSQL = true; // prefer PG for consistency
                try {
                    const recentLogsResponse = await this.api.getRecentLogs();
                    console.log('📝 Recent logs API response:', recentLogsResponse);
                    
                    if (recentLogsResponse && recentLogsResponse.logs && recentLogsResponse.logs.length > 0) {
                        console.log(`📝 Found ${recentLogsResponse.logs.length} recent historical logs`);
                        this.displayInitialLogs(recentLogsResponse.logs);
                    } else {
                        this.showEmptyState('No recent logs available. Start an agent run to see live logs.');
                    }
                } catch (apiError) {
                    console.warn('⚠️ Failed to load recent logs:', apiError);
                    this.showEmptyState('No recent logs available. Start an agent run to see live logs.');
                }
            }
            
        } catch (error) {
            console.error('❌ Failed to load initial logs:', error);
            this.showErrorState('Failed to load logs: ' + error.message);
        }
    }

    async loadPostgreSQLLogs(taskId, isHistorical = false) {
        try {
            console.log(`📝 Loading PostgreSQL logs for task: ${taskId} (historical: ${isHistorical})`);
            
            let logsResponse;
            if (isHistorical) {
                // Load all logs for historical task
                logsResponse = await this.api.request(`/v2/logs/${taskId}?limit=1000`);
            } else {
                // Load recent logs for active task
                logsResponse = await this.api.request(`/v2/logs/${taskId}/recent?since_sequence=${this.latestSequenceNumber}&limit=200`);
            }
            
            if (logsResponse?.success && logsResponse.logs && logsResponse.logs.length > 0) {
                console.log(`📝 Loaded ${logsResponse.logs.length} PostgreSQL logs`);
                
                if (isHistorical) {
                    this.displayInitialLogs(logsResponse.logs);
                    this.isHistoricalMode = true;
                } else {
                    // For active tasks, append new logs
                    logsResponse.logs.forEach(log => {
                        this.addLogToDisplay(this.normalizePostgreSQLLog(log), true);
                    });
                    
                    // Update latest sequence number
                    if (logsResponse.latest_sequence) {
                        this.latestSequenceNumber = logsResponse.latest_sequence;
                    }
                }
                
                return true;
            } else if (isHistorical) {
                this.showEmptyState('No logs found for this completed task.');
                return false;
            }
            
            return false;
            
        } catch (error) {
            console.error('❌ Failed to load PostgreSQL logs:', error);
            if (isHistorical) {
                this.showErrorState('Failed to load historical logs: ' + error.message);
            }
            return false;
        }
    }

    normalizePostgreSQLLog(pgLog) {
        // Convert PostgreSQL log format to our standard format
        return {
            message: pgLog.message || '',
            level: pgLog.level || 'INFO',
            timestamp: pgLog.timestamp || new Date().toISOString(),
            component: pgLog.component || 'system',
            phase: pgLog.phase || null,
            sequence_number: pgLog.sequence_number || 0,
            metadata: pgLog.metadata || null,
            progress_data: pgLog.progress_data || null,
            error_data: pgLog.error_data || null
        };
    }

    startPostgreSQLPolling() {
        if (this.postgresqlPolling || this.isHistoricalMode) {
            return; // Already polling or in historical mode
        }
        
        console.log('🔄 Starting PostgreSQL polling for real-time updates');
        
        this.postgresqlPolling = setInterval(async () => {
            if (this.currentTaskId && !this.isHistoricalMode) {
                try {
                    await this.loadPostgreSQLLogs(this.currentTaskId, false);
                } catch (error) {
                    console.warn('⚠️ PostgreSQL polling failed:', error);
                }
            }
        }, this.postgresqlPollingInterval);
    }

    stopPostgreSQLPolling() {
        if (this.postgresqlPolling) {
            console.log('✅ Stopping PostgreSQL polling');
            clearInterval(this.postgresqlPolling);
            this.postgresqlPolling = null;
        }
    }

    displayInitialLogs(logs) {
        // Clear any existing content
        this.logs = [];
        this.logsContainer.innerHTML = '';
        
        // Process and display logs
        logs.forEach(log => {
            this.addLogToDisplay(log, false); // Don't scroll for initial batch
        });
        
        // Update UI
        this.updateLogCount();
        this.scrollToBottom();
        
        console.log(`✅ Displayed ${logs.length} initial logs`);
    }

    handleNewLog(logData, source) {
        if (!this.isInitialized) {
            console.log('📝 Received log before initialization, queuing...');
            // Could queue logs here if needed
            return;
        }
        
        // Track statistics
        this.stats.totalLogs++;
        if (source === 'socketio') {
            this.stats.logsFromSocket++;
        } else {
            this.stats.logsFromPolling++;
        }
        
        // Add log to display
        this.addLogToDisplay(logData, true);
        
        console.log(`📝 New log from ${source}:`, logData.message?.substring(0, 100));
    }

    addLogToDisplay(logData, shouldScroll = true) {
        // Normalize log data format
        const normalizedLog = this.normalizeLogData(logData);
        
        // Dedupe: build a key from sequence or message+timestamp
        const key = normalizedLog.sequence_number ?? `${normalizedLog.timestamp}|${normalizedLog.level}|${normalizedLog.message}`;
        if (this.recentLogKeys.has(key)) {
            return; // skip duplicate
        }
        this.recentLogKeys.add(key);
        if (this.recentLogKeys.size > this.maxRecentKeys) {
            // Trim set by deleting oldest entry (approximate by slicing last N)
            this.recentLogKeys = new Set(Array.from(this.recentLogKeys).slice(-Math.floor(this.maxRecentKeys * 0.8)));
        }
        
        // Filter out noisy logs and track statistics
        if (this.shouldFilterLog(normalizedLog)) {
            this.stats.filteredLogs++;
            return;
        }
        
        // Track displayed logs
        this.stats.displayedLogs++;
        
        // Add to logs array
        this.logs.push(normalizedLog);
        
        // Limit logs in memory
        if (this.logs.length > this.maxLogs) {
            this.logs.shift();
            // Remove oldest log from DOM
            const firstLogElement = this.logsContainer.firstElementChild;
            if (firstLogElement) {
                firstLogElement.remove();
            }
        }
        
        // Create and append log element
        const logElement = this.createLogElement(normalizedLog);
        this.logsContainer.appendChild(logElement);
        
        // Update UI
        this.updateLogCount();
        
        // Auto-scroll if enabled
        if (shouldScroll && this.autoScroll) {
            this.scrollToBottom();
        }
    }

    normalizeLogData(logData) {
        // Handle different log formats from different sources
        return {
            message: logData.message || '',
            level: logData.level || 'INFO',
            timestamp: logData.timestamp || new Date().toISOString(),
            component: logData.component || 'system'
        };
    }

    shouldFilterLog(logData) {
        const message = logData.message || '';
        const level = logData.level || 'INFO';
        
        // WHITELIST APPROACH: Always show agent execution logs
        const agentPatterns = [
            '🚀', '✅', '❌', '📚', '💾', '🔄', '⚡',
            'agent', 'phase', 'processing', 'completed', 'failed', 'error',
            'task started', 'task completed', 'execution', 'celery', 'pipeline'
        ];
        
        // Never filter agent-relevant logs
        if (agentPatterns.some(pattern => 
            message.toLowerCase().includes(pattern.toLowerCase()))) {
            return false;
        }
        
        // Never filter errors/warnings/critical logs
        if (['ERROR', 'WARNING', 'CRITICAL'].includes(level)) {
            return false;
        }
        
        // MINIMAL NOISE FILTERING: Only filter truly noisy patterns
        const noisePatterns = [
            'GET /socket.io/',
            'POST /socket.io/',
            'GET /api/agent/status',
            'GET /api/logs/recent',
            'HTTP/1.1" 200',
            'HTTP/1.1" 304'
        ];
        
        // Log filtering statistics in debug mode
        const shouldFilter = noisePatterns.some(pattern => message.includes(pattern));
        if (window.DEBUG_LOGGING && shouldFilter) {
            console.debug(`[SimplifiedLogsManager] Filtered noise log: ${message.substring(0, 50)}...`);
        }
        
        return shouldFilter;
    }

    createLogElement(logData) {
        const logElement = document.createElement('div');
        logElement.className = `log-entry log-${logData.level.toLowerCase()}`;
        
        // Format timestamp
        const timestamp = new Date(logData.timestamp).toLocaleTimeString();
        
        // Create log content
        logElement.innerHTML = `
            <span class="log-timestamp">${timestamp}</span>
            <span class="log-level">${logData.level}</span>
            <span class="log-message">${this.escapeHtml(logData.message)}</span>
        `;
        
        return logElement;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // Emergency polling - only when SocketIO fails
    startEmergencyPolling() {
        if (this.emergencyPolling) {
            return; // Already polling
        }
        
        console.log('🚨 Starting emergency polling (SocketIO unavailable)');
        this.updateConnectionStatus('polling');
        
        this.emergencyPolling = setInterval(async () => {
            try {
                const response = await this.api.getRecentLogs();
                if (response?.logs && response.logs.length > 0) {
                    // Only add logs we haven't seen (simple timestamp check)
                    const lastLogTime = this.logs.length > 0 ? 
                        new Date(this.logs[this.logs.length - 1].timestamp).getTime() : 0;
                    
                    const newLogs = response.logs.filter(log => {
                        const logTime = new Date(log.timestamp || Date.now()).getTime();
                        return logTime > lastLogTime;
                    });
                    
                    newLogs.forEach(log => {
                        this.handleNewLog(log, 'polling');
                    });
                }
            } catch (error) {
                console.warn('⚠️ Emergency polling failed:', error);
            }
        }, this.emergencyPollingInterval);
    }

    stopEmergencyPolling() {
        if (this.emergencyPolling) {
            console.log('✅ Stopping emergency polling (SocketIO restored)');
            clearInterval(this.emergencyPolling);
            this.emergencyPolling = null;
        }
    }

    // UI State Management
    showLoadingState() {
        this.logsContainer.innerHTML = `
            <div class="logs-state loading-state">
                <div class="loading-spinner"></div>
                <p>Loading recent logs...</p>
            </div>
        `;
    }

    showEmptyState(message) {
        this.logsContainer.innerHTML = `
            <div class="logs-state empty-state">
                <i class="fas fa-info-circle"></i>
                <p>${message}</p>
            </div>
        `;
    }

    showErrorState(message) {
        this.logsContainer.innerHTML = `
            <div class="logs-state error-state">
                <i class="fas fa-exclamation-triangle"></i>
                <p>${message}</p>
                <button onclick="window.location.reload()" class="retry-btn">Retry</button>
            </div>
        `;
    }

    updateConnectionStatus(status) {
        if (!this.connectionStatus) return;
        
        const statusConfig = {
            connected: { icon: '🟢', text: 'Connected', class: 'connected' },
            disconnected: { icon: '🔴', text: 'Disconnected', class: 'disconnected' },
            polling: { icon: '🟡', text: 'Polling', class: 'polling' },
            error: { icon: '🔴', text: 'Error', class: 'error' }
        };
        
        const config = statusConfig[status] || statusConfig.error;
        
        this.connectionStatus.innerHTML = `
            <span class="status-icon">${config.icon}</span>
            <span class="status-text">${config.text}</span>
        `;
        this.connectionStatus.className = `connection-status ${config.class}`;
    }

    updateLogCount() {
        if (this.logCount) {
            this.logCount.textContent = this.logs.length;
        }
    }

    scrollToBottom() {
        if (this.logsContainer) {
            this.logsContainer.scrollTop = this.logsContainer.scrollHeight;
        }
    }

    handleConnectionError(error) {
        // Enhanced connection error handling with intelligent recovery
        console.warn('🔌 Handling connection error:', error);
        
        // Track connection error statistics
        if (!this.connectionErrorStats) {
            this.connectionErrorStats = {
                totalErrors: 0,
                consecutiveErrors: 0,
                lastErrorTime: null,
                errorTypes: {}
            };
        }
        
        this.connectionErrorStats.totalErrors++;
        this.connectionErrorStats.consecutiveErrors++;
        this.connectionErrorStats.lastErrorTime = Date.now();
        
        // Track error types for diagnostics
        const errorType = error?.type || error?.message || 'unknown';
        this.connectionErrorStats.errorTypes[errorType] = 
            (this.connectionErrorStats.errorTypes[errorType] || 0) + 1;
        
        // Implement intelligent recovery strategy
        if (this.connectionErrorStats.consecutiveErrors >= 3) {
            // After 3 consecutive errors, show user notification
            this.showConnectionMessage(
                `Connection issues detected. Switching to polling mode.`, 
                'warning'
            );
            
            // Increase emergency polling frequency for better responsiveness
            this.emergencyPollingInterval = Math.max(2000, this.emergencyPollingInterval - 1000);
        }
        
        // Reset consecutive errors on successful connection (handled in connect event)
    }

    showConnectionMessage(message, type = 'info') {
        // Create temporary message
        const messageEl = document.createElement('div');
        messageEl.className = `connection-message ${type}`;
        messageEl.textContent = message;
        messageEl.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 10px 15px;
            background: var(--glass-bg);
            border: 1px solid var(--glass-border);
            border-radius: 8px;
            z-index: 1000;
            backdrop-filter: blur(10px);
        `;
        
        document.body.appendChild(messageEl);
        
        // Remove after 3 seconds
        setTimeout(() => {
            if (messageEl.parentNode) {
                messageEl.parentNode.removeChild(messageEl);
            }
        }, 3000);
    }

    // Public methods
    async clearLogs() {
        try {
            // Clear server logs
            await this.api.clearLogs();
            
            // Clear local logs
            this.logs = [];
            this.logsContainer.innerHTML = '';
            this.updateLogCount();
            
            this.showEmptyState('Logs cleared. New logs will appear here.');
            console.log('✅ Logs cleared');
            
        } catch (error) {
            console.error('❌ Failed to clear logs:', error);
            this.showConnectionMessage('Failed to clear logs: ' + error.message, 'error');
        }
    }

    handleLogsCleared() {
        // Handle logs cleared event from server
        this.logs = [];
        this.logsContainer.innerHTML = '';
        this.updateLogCount();
        this.showEmptyState('Logs cleared by server. New logs will appear here.');
        console.log('📝 Logs cleared by server');
    }

    // CRITICAL FIX: Add missing phase update handler
    handlePhaseUpdate(phaseData, source) {
        console.log(`📊 Phase update from ${source}:`, phaseData);
        
        // Emit custom event for other components (Agent Dashboard will handle the display)
        this.dispatchCustomEvent('phase_update', phaseData);
    }

    // CRITICAL FIX: Add missing progress update handler
    handleProgressUpdate(progressData, source) {
        console.log(`📈 Progress update from ${source}:`, progressData);
        
        // Emit custom event for other components (Agent Dashboard will handle the display)
        this.dispatchCustomEvent('progress_update', progressData);
    }

    // REMOVED: updateAgentStatusPanel method - agent status footer was removed from logs panel
    // Agent status is now only displayed in the main Agent Dashboard panel

    // CRITICAL FIX: Add custom event dispatcher
    dispatchCustomEvent(eventName, data) {
        // Create custom events to replace SocketIO events
        const event = new CustomEvent(eventName, { detail: data });
        document.dispatchEvent(event);
    }

    // Get statistics
    getStats() {
        const filteringPercentage = this.stats.totalLogs > 0 
            ? ((this.stats.filteredLogs / this.stats.totalLogs) * 100).toFixed(2)
            : 0;
            
        return {
            ...this.stats,
            currentLogs: this.logs.length,
            socketConnected: this.socketConnected,
            emergencyPolling: !!this.emergencyPolling,
            autoScroll: this.autoScroll,
            filteringPercentage: `${filteringPercentage}%`
        };
    }

    // Get filtering diagnostics
    getFilteringDiagnostics() {
        const total = this.stats.totalLogs;
        const filtered = this.stats.filteredLogs;
        const displayed = this.stats.displayedLogs;
        
        return {
            totalProcessed: total,
            filtered: filtered,
            displayed: displayed,
            filteringRate: total > 0 ? ((filtered / total) * 100).toFixed(2) + '%' : '0%',
            displayRate: total > 0 ? ((displayed / total) * 100).toFixed(2) + '%' : '0%',
            efficiency: filtered > 0 ? 'Filtering active' : 'No filtering applied',
            recommendation: filtered > displayed * 0.5 
                ? 'Consider reducing filter strictness' 
                : 'Filtering levels appropriate'
        };
    }

    // Enable debug mode for filtering
    enableFilteringDebug() {
        window.DEBUG_LOGGING = true;
        console.log('🐛 Filtering debug mode enabled');
        console.log('📊 Current filtering stats:', this.getFilteringDiagnostics());
    }

    // Disable debug mode
    disableFilteringDebug() {
        window.DEBUG_LOGGING = false;
        console.log('🐛 Filtering debug mode disabled');
    }

    // Public method to load historical logs for completed tasks
    async loadHistoricalLogs(taskId) {
        try {
            console.log(`📚 Loading historical logs for completed task: ${taskId}`);
            
            // Stop any active polling
            this.stopPostgreSQLPolling();
            this.stopEmergencyPolling();
            
            // Reset state for historical mode
            this.currentTaskId = taskId;
            this.latestSequenceNumber = 0;
            this.isHistoricalMode = true;
            
            // Load logs from PostgreSQL
            const success = await this.loadPostgreSQLLogs(taskId, true);
            
            if (success) {
                this.showConnectionMessage(`Loaded historical logs for task ${taskId}`, 'success');
                return true;
            } else {
                this.showConnectionMessage(`No logs found for task ${taskId}`, 'warning');
                return false;
            }
            
        } catch (error) {
            console.error('❌ Failed to load historical logs:', error);
            this.showErrorState(`Failed to load historical logs: ${error.message}`);
            return false;
        }
    }

    // Public method to switch back to live mode
    async switchToLiveMode() {
        try {
            console.log('🔄 Switching to live mode...');
            
            // Reset historical mode
            this.isHistoricalMode = false;
            this.currentTaskId = null;
            this.latestSequenceNumber = 0;
            
            // Clear current logs
            this.logs = [];
            this.logsContainer.innerHTML = '';
            this.updateLogCount();
            
            // Load initial logs for current agent state
            await this.loadInitialLogs();
            
            this.showConnectionMessage('Switched to live mode', 'success');
            return true;
            
        } catch (error) {
            console.error('❌ Failed to switch to live mode:', error);
            this.showErrorState(`Failed to switch to live mode: ${error.message}`);
            return false;
        }
    }

    // Public method to get current mode info
    getModeInfo() {
        return {
            isHistoricalMode: this.isHistoricalMode,
            currentTaskId: this.currentTaskId,
            latestSequenceNumber: this.latestSequenceNumber,
            postgresqlPolling: !!this.postgresqlPolling,
            socketConnected: this.socketConnected
        };
    }

    // Cleanup
    cleanup() {
        console.log('🧹 Cleaning up SimplifiedLogsManager...');
        
        // Stop polling first
        this.stopEmergencyPolling();
        this.stopPostgreSQLPolling();
        
        // Use centralized CleanupService for comprehensive cleanup
        CleanupService.cleanup(this, { logCleanup: false }); // We already logged above
        
        // Remove SocketIO listeners manually since they're not tracked
        if (window.socket) {
            window.socket.off('connect');
            window.socket.off('disconnect');
            window.socket.off('connect_error');
            window.socket.off('log');
            window.socket.off('live_log');
            window.socket.off('logs_cleared');
        }
        
        console.log('✅ SimplifiedLogsManager cleanup complete');
    }
}

// Make available globally
window.SimplifiedLogsManager = SimplifiedLogsManager;
window.LiveLogsManager = SimplifiedLogsManager; // Alias for backward compatibility
window.SimplifiedLogsManager = SimplifiedLogsManager;
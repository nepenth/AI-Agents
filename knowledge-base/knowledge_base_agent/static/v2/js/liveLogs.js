/* V2 LIVELOGS.JS - PURE API POLLING LIVE LOGS MANAGER */

/**
 * Live Logs Manager implementing pure API polling architecture
 * 
 * ARCHITECTURE:
 * - REST API: All log operations (get recent logs, clear logs)
 * - Polling: Real-time log updates via API polling (1.5 second intervals)
 * - Custom Events: Notifications from polling system
 * - UI State: Managed locally with auto-scroll and log buffering
 */
class LiveLogsManager {
    constructor(api) {
        this.api = api;
        
        // UI Elements
        this.logsContainer = document.getElementById('logs-container');
        this.clearLogsBtn = document.getElementById('clear-logs-btn');
        this.agentStatusText = document.getElementById('agent-status-text-logs');
        this.logCount = document.getElementById('log-count');
        this.etcTime = document.getElementById('agent-etc-time');
        this.phaseProgressText = document.getElementById('phase-progress-text');
        this.phaseProgressBar = document.getElementById('phase-progress-bar');
        
        // State management
        this.logs = [];
        this.maxLogs = 500; // Limit number of logs in memory
        this.autoScroll = true;
        this.isClearing = false;
        this.currentPhase = null;
        
        // Log deduplication
        this.seenLogIds = new Set(); // Track logs we've already displayed
        
        // Filtering statistics
        this.filteringStats = {
            totalLogs: 0,
            filteredLogs: 0,
            displayedLogs: 0
        };

        if (!this.logsContainer) return;
        this.init();
    }

    init() {
        this.attachEventListeners();
        this.setupEventListeners();
        this.loadInitialLogs();
    }

    async loadInitialLogs() {
        try {
            // Check if agent is running to determine log loading strategy
            const statusResponse = await this.api.getAgentStatus();
            const agentIsRunning = statusResponse?.is_running || false;
            const currentTaskId = statusResponse?.current_task_id || statusResponse?.task_id;
            
            if (agentIsRunning && currentTaskId) {
                // Agent is running - initialize with running state
                console.log(`📝 Loading logs for active task: ${currentTaskId}`);
                
                // Update agent status display immediately
                this.updateAgentStatus(true, statusResponse.current_phase_message || 'Running...', statusResponse);
                
                // Try to load recent logs from PostgreSQL if available
                try {
                    const pgResponse = await this.api.request(`/v2/logs/${currentTaskId}/recent?limit=200`);
                    if (pgResponse?.success && pgResponse.logs && pgResponse.logs.length > 0) {
                        this.addInitialLogs(pgResponse.logs);
                        console.log(`✅ Loaded ${pgResponse.logs.length} logs for running task`);
                        return;
                    }
                } catch (pgError) {
                    console.warn('PostgreSQL logs not available, falling back to legacy API');
                }
                
                // If no PostgreSQL logs, try legacy API
                const response = await this.api.getRecentLogs();
                if (response && response.success && response.logs && response.logs.length > 0) {
                    this.addInitialLogs(response.logs);
                    console.log(`✅ Loaded ${response.logs.length} logs from legacy API for running task`);
                } else {
                    // No logs yet for running task - show status
                    this.showInfo(`Agent is running (Task: ${currentTaskId.substring(0, 8)}...) - logs will appear here as processing continues.`);
                }
            } else {
                // Agent is idle - load any recent logs
                const response = await this.api.getRecentLogs();
                if (response && response.success) {
                    if (response.logs && response.logs.length > 0) {
                        this.addInitialLogs(response.logs);
                        console.log(`✅ Loaded ${response.logs.length} recent logs (agent idle)`);
                    } else {
                        // No recent logs - show the helpful message from API
                        const message = response.message || 'No recent agent activity. Start an agent run to see live logs.';
                        this.showInfo(message);
                    }
                } else {
                    // API returned error
                    const errorMsg = response?.message || response?.error || 'Failed to load recent logs';
                    this.showError(errorMsg);
                }
                
                // Update status display for idle state
                this.updateAgentStatus(false, 'Idle', { status: 'IDLE' });
            }
        } catch (error) {
            console.error('Failed to load initial logs:', error);
            this.showError('Failed to load recent logs: ' + error.message);
        }
    }

    attachEventListeners() {
        if (this.clearLogsBtn) {
            this.clearLogsBtn.addEventListener('click', () => this.clearLogs());
        }

        // Auto-scroll toggle when user scrolls manually
        if (this.logsContainer) {
            this.logsContainer.addEventListener('scroll', () => {
                const { scrollTop, scrollHeight, clientHeight } = this.logsContainer;
                this.autoScroll = scrollTop + clientHeight >= scrollHeight - 10;
            });

            // Double-click to toggle auto-scroll
            this.logsContainer.addEventListener('dblclick', () => {
                this.autoScroll = !this.autoScroll;
                if (this.autoScroll) {
                    this.scrollToBottom();
                    this.showInfo('Auto-scroll enabled');
                } else {
                    this.showInfo('Auto-scroll disabled');
                }
            });
        }

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.key === 'l') {
                e.preventDefault();
                this.clearLogs();
            }
        });
    }

    setupEventListeners() {
        // Custom event listeners for polling-based log notifications
        document.addEventListener('log', (event) => {
            this.addLog(event.detail);
        });

        document.addEventListener('logs_cleared', () => {
            this.handleLogsCleared();
        });

        // Listen for agent status updates from polling
        document.addEventListener('agent_status_update', (event) => {
            const statusData = event.detail;
            this.updateAgentStatus(statusData.is_running, statusData.current_phase_message, statusData);
        });

        // Enhanced SocketIO connection recovery if available
        if (window.socket) {
            // Add reconnection event handlers for better connection recovery
            window.socket.on('reconnect', (attemptNumber) => {
                console.log(`🔌 SocketIO reconnected after ${attemptNumber} attempts`);
                this.showConnectionMessage('Connection restored', 'success');
            });
            
            window.socket.on('reconnect_attempt', (attemptNumber) => {
                console.log(`🔌 SocketIO reconnection attempt ${attemptNumber}`);
            });
            
            window.socket.on('reconnect_error', (error) => {
                console.warn('🔌 SocketIO reconnection error:', error);
            });
            
            window.socket.on('reconnect_failed', () => {
                console.error('🔌 SocketIO reconnection failed - relying on API polling');
                this.showConnectionMessage('Connection failed - using API polling', 'warning');
            });
        }

        // Listen for phase updates from execution plan
        document.addEventListener('phase_update', (event) => {
            const phaseData = event.detail;
            this.updateAgentStatus(true, phaseData.message, phaseData);
        });

        // CRITICAL FIX: Listen for running task detection on page load
        document.addEventListener('running_task_detected', (event) => {
            console.log('📝 LiveLogs: Running task detected, initializing with task state');
            const taskStatus = event.detail.status;
            
            // Update status immediately
            this.updateAgentStatus(
                true, 
                taskStatus.current_phase_message || 'Running...', 
                taskStatus
            );
            
            // If we don't have logs yet, try to load them for this specific task
            if (this.logs.length === 0 && taskStatus.task_id) {
                this.loadLogsForTask(taskStatus.task_id);
            }
        });
    }

    updateAgentStatus(isRunning, phaseMessage, statusData = {}) {
        // Update agent status indicator in the header
        const statusIndicator = document.getElementById('agent-status-indicator');
        const statusText = document.getElementById('agent-status-text-main');
        
        if (statusIndicator && statusText) {
            if (isRunning) {
                statusIndicator.className = 'glass-badge glass-badge--success glass-badge--pulse';
                statusText.textContent = 'Running';
            } else {
                statusIndicator.className = 'glass-badge glass-badge--primary';
                statusText.textContent = 'Idle';
            }
        }
        
        // Update status text in logs panel
        if (this.agentStatusText) {
            this.agentStatusText.textContent = isRunning ? 'Running' : 'Idle';
        }
        
        // Update phase message if provided
        if (phaseMessage && this.currentPhase !== phaseMessage) {
            this.currentPhase = phaseMessage;
            console.log(`📊 Agent phase: ${phaseMessage}`);
        }
        
        // Update ETC and progress if available
        if (statusData.etc_seconds && this.etcTime) {
            const etcMinutes = Math.ceil(statusData.etc_seconds / 60);
            this.etcTime.textContent = `${etcMinutes}m`;
        }
        
        if (statusData.progress !== undefined && this.phaseProgressBar) {
            this.phaseProgressBar.style.width = `${statusData.progress}%`;
            if (this.phaseProgressText) {
                this.phaseProgressText.textContent = `${statusData.progress}%`;
            }
        }
    }

    addLog(log) {
        const { message, level, timestamp } = log;
        
        // Use global event deduplicator if available
        if (window.uiManager && window.uiManager.eventDeduplicator) {
            if (window.uiManager.eventDeduplicator.isDuplicate('log', log, log._source || 'unknown')) {
                return; // Skip duplicate
            }
        } else {
            // Fallback to local deduplication
            const logId = this.createLogId(log);
            
            // Skip if we've already seen this exact log
            if (this.seenLogIds.has(logId)) {
                return;
            }
            
            // Mark this log as seen
            this.seenLogIds.add(logId);
            
            // Clean up old log IDs to prevent memory leaks (keep last 1000)
            if (this.seenLogIds.size > 1000) {
                const oldIds = Array.from(this.seenLogIds).slice(0, 200);
                oldIds.forEach(id => this.seenLogIds.delete(id));
            }
        }
        
        // Track filtering statistics
        this.filteringStats.totalLogs++;
        
        // Filter out noisy HTTP request logs
        if (this.shouldFilterLog(message, level)) {
            this.filteringStats.filteredLogs++;
            return;
        }
        
        // Track displayed logs
        this.filteringStats.displayedLogs++;
        
        // Manage seen log IDs to prevent memory leaks
        if (this.seenLogIds.size > 1000) {
            const idsArray = Array.from(this.seenLogIds);
            const toKeep = idsArray.slice(-500); // Keep last 500
            this.seenLogIds = new Set(toKeep);
        }
        
        // Create log element with enhanced styling for multi-line support
        const logElement = document.createElement('div');
        logElement.className = 'log-message';
        logElement.dataset.level = level;
        logElement.style.transition = 'none'; // Remove any hover transitions
        logElement.style.transform = 'none'; // Prevent any transform effects
        
        // Enhanced styling for better readability and multi-line support
        logElement.style.cssText += `
            display: flex;
            align-items: flex-start;
            gap: var(--space-2);
            padding: var(--space-2) var(--space-3);
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Roboto Mono', monospace;
            font-size: 0.875rem;
            line-height: 1.5;
            word-wrap: break-word;
            overflow-wrap: break-word;
            white-space: pre-wrap;
        `;
        
        // Add timestamp if available
        const time = timestamp ? new Date(timestamp).toLocaleTimeString() : new Date().toLocaleTimeString();
        logElement.innerHTML = `
            <span class="log-time" style="
                color: var(--text-tertiary); 
                font-size: var(--font-size-xs); 
                white-space: nowrap;
                min-width: 80px;
                flex-shrink: 0;
                margin-top: 2px;
            ">
                ${time}
            </span>
            <span class="log-content" style="
                flex: 1;
                color: var(--text-primary);
                word-break: break-word;
                white-space: pre-wrap;
                line-height: 1.5;
            ">${this.escapeHtml(message)}</span>
        `;
        
        this.logsContainer.appendChild(logElement);
        
        // Manage log buffer
        this.logs.push(log);
        if (this.logs.length > this.maxLogs) {
            this.logs.shift();
            const firstChild = this.logsContainer.firstElementChild;
            if (firstChild) {
                firstChild.remove();
            }
        }

        // Auto-scroll if enabled - force scroll to bottom
        if (this.autoScroll) {
            // Use multiple methods to ensure scrolling works
            requestAnimationFrame(() => {
                this.logsContainer.scrollTop = this.logsContainer.scrollHeight;
                // Also try scrollIntoView as backup
                logElement.scrollIntoView({ behavior: 'smooth', block: 'end' });
            });
        }

        // Update log count
        this.updateLogCount();

        // Highlight critical errors
        if (level === 'ERROR' || level === 'CRITICAL') {
            logElement.style.animation = 'pulse 1s ease-in-out';
        }
    }

    shouldFilterLog(message, level) {
        // WHITELIST APPROACH: Always show agent execution logs
        const agentPatterns = [
            '🚀', '✅', '❌', '📚', '💾', '🔄', '⚡',
            'agent', 'phase', 'processing', 'completed', 'failed', 'error',
            'task started', 'task completed', 'execution', 'celery'
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
        
        // FILTER DEBUG MESSAGES: Remove debug messages that clutter the logs
        const debugPatterns = [
            '🧪 PIPELINE TEST:',
            'TASK ID VERIFICATION:',
            'DEBUG_AGENT_RUN:',
            'Flask app context created',
            'Task state initialized in database',
            'About to call agent.run()',
            'Agent instance created successfully',
            'Entering agent.run() method',
            'initialize() completed successfully'
        ];
        
        // Filter out debug messages
        if (debugPatterns.some(pattern => message.includes(pattern))) {
            return true;
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
        
        return noisePatterns.some(pattern => message.includes(pattern));
    }

    addInitialLogs(logs) {
        if (!this.logsContainer) return;
        
        this.logsContainer.innerHTML = '';
        this.logs = [];
        
        logs.forEach(log => {
            this.addLog(log);
        });
        
        this.scrollToBottom();
    }

    async clearLogs() {
        if (this.isClearing) return;
        
        this.isClearing = true;
        try {
            await this.api.clearLogs();
            this.logsContainer.innerHTML = '';
            this.logs = [];
            this.updateLogCount();
            this.showInfo('Logs cleared');
        } catch (error) {
            console.error('Failed to clear logs:', error);
            this.showError('Failed to clear logs');
        } finally {
            this.isClearing = false;
        }
    }

    handleLogsCleared() {
        this.logsContainer.innerHTML = '';
        this.logs = [];
        this.updateLogCount();
    }

    updateLogCount() {
        if (this.logCount) {
            this.logCount.textContent = this.logs.length;
        }
    }

    scrollToBottom() {
        if (this.logsContainer) {
            requestAnimationFrame(() => {
                this.logsContainer.scrollTop = this.logsContainer.scrollHeight;
            });
        }
    }

    showInfo(message) {
        this.addLog({
            message: `ℹ️ ${message}`,
            level: 'INFO',
            timestamp: new Date().toISOString()
        });
    }

    showError(message) {
        this.addLog({
            message: `❌ ${message}`,
            level: 'ERROR',
            timestamp: new Date().toISOString()
        });
    }

    createLogId(log) {
        // Create a unique ID for log deduplication based on message content and timestamp
        const { message, level, timestamp } = log;
        
        // Use a combination of timestamp, level, and first 100 chars of message
        const messageKey = message ? message.substring(0, 100) : '';
        const timeKey = timestamp || new Date().toISOString();
        
        // For better deduplication, also include a hash of the full message
        const messageHash = this.simpleHash(message || '');
        
        // Create a hash-like ID
        return `${timeKey}_${level}_${messageHash}_${messageKey}`.replace(/[^a-zA-Z0-9_-]/g, '_');
    }

    simpleHash(str) {
        // Simple hash function for better deduplication
        let hash = 0;
        if (str.length === 0) return hash;
        for (let i = 0; i < str.length; i++) {
            const char = str.charCodeAt(i);
            hash = ((hash << 5) - hash) + char;
            hash = hash & hash; // Convert to 32-bit integer
        }
        return Math.abs(hash).toString(36);
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // Get filtering diagnostics
    getFilteringDiagnostics() {
        const total = this.filteringStats.totalLogs;
        const filtered = this.filteringStats.filteredLogs;
        const displayed = this.filteringStats.displayedLogs;
        
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
        console.log('🐛 LiveLogsManager filtering debug mode enabled');
        console.log('📊 Current filtering stats:', this.getFilteringDiagnostics());
    }

    // Disable debug mode
    disableFilteringDebug() {
        window.DEBUG_LOGGING = false;
        console.log('🐛 LiveLogsManager filtering debug mode disabled');
    }

    showConnectionMessage(message, type = 'info') {
        // Create temporary connection status message
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
            color: var(--text-primary);
        `;
        
        // Add type-specific styling
        if (type === 'success') {
            messageEl.style.borderColor = 'var(--success-color)';
            messageEl.style.backgroundColor = 'rgba(34, 197, 94, 0.1)';
        } else if (type === 'warning') {
            messageEl.style.borderColor = 'var(--warning-color)';
            messageEl.style.backgroundColor = 'rgba(251, 191, 36, 0.1)';
        } else if (type === 'error') {
            messageEl.style.borderColor = 'var(--error-color)';
            messageEl.style.backgroundColor = 'rgba(239, 68, 68, 0.1)';
        }
        
        document.body.appendChild(messageEl);
        
        // Remove after 3 seconds
        setTimeout(() => {
            if (messageEl.parentNode) {
                messageEl.parentNode.removeChild(messageEl);
            }
        }, 3000);
    }

    // Get comprehensive statistics
    getStats() {
        const filteringPercentage = this.filteringStats.totalLogs > 0 
            ? ((this.filteringStats.filteredLogs / this.filteringStats.totalLogs) * 100).toFixed(2)
            : 0;
            
        return {
            ...this.filteringStats,
            currentLogs: this.logs.length,
            maxLogs: this.maxLogs,
            autoScroll: this.autoScroll,
            seenLogIds: this.seenLogIds.size,
            filteringPercentage: `${filteringPercentage}%`
        };
    }

    async loadLogsForTask(taskId) {
        try {
            console.log(`📝 Loading logs for specific task: ${taskId}`);
            
            // Try PostgreSQL logs first
            try {
                const pgResponse = await this.api.request(`/v2/logs/${taskId}/recent?limit=200`);
                if (pgResponse?.success && pgResponse.logs && pgResponse.logs.length > 0) {
                    this.addInitialLogs(pgResponse.logs);
                    console.log(`✅ Loaded ${pgResponse.logs.length} logs for task ${taskId}`);
                    return;
                }
            } catch (pgError) {
                console.warn('PostgreSQL logs not available for task, trying legacy API');
            }
            
            // Fallback to legacy API
            const response = await this.api.getRecentLogs();
            if (response && response.success && response.logs && response.logs.length > 0) {
                this.addInitialLogs(response.logs);
                console.log(`✅ Loaded ${response.logs.length} logs from legacy API for task ${taskId}`);
            } else {
                this.showInfo(`Loading logs for task ${taskId.substring(0, 8)}... - logs will appear as processing continues.`);
            }
        } catch (error) {
            console.error(`Failed to load logs for task ${taskId}:`, error);
            this.showError(`Failed to load logs for task: ${error.message}`);
        }
    }

    cleanup() {
        // Clean up event listeners and intervals
        console.log('Cleaning up LiveLogsManager...');
        
        // Clear deduplication tracking
        this.seenLogIds.clear();
        
        // Note: recentStartupMessages is not used in this implementation
        // but kept for potential future use or compatibility
    }
}

// Make globally available
window.LiveLogsManager = LiveLogsManager;
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
        this.agentStatusText = document.getElementById('agent-status-text');
        this.logCount = document.getElementById('log-count');
        
        // State management
        this.logs = [];
        this.maxLogs = 500; // Limit number of logs in memory
        this.autoScroll = true;
        this.isClearing = false;

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
            // Load recent logs via REST API
            const response = await this.api.getRecentLogs();
            if (response && response.logs) {
                this.addInitialLogs(response.logs);
            }
        } catch (error) {
            console.error('Failed to load initial logs:', error);
            this.showError('Failed to load recent logs');
        }
    }

    attachEventListeners() {
        if (this.clearLogsBtn) {
            this.clearLogsBtn.addEventListener('click', () => this.clearLogs());
        }

        // Auto-scroll toggle when user scrolls manually
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

        document.addEventListener('logs_cleared', (event) => {
            this.handleLogsCleared();
        });
    }

    addLog(log) {
        const { message, level, timestamp } = log;
        
        // Filter out noisy HTTP request logs
        if (this.shouldFilterLog(message, level)) {
            return;
        }
        
        // Create log element with enhanced styling
        const logElement = document.createElement('div');
        logElement.className = 'log-message';
        logElement.dataset.level = level;
        
        // Add timestamp if available
        const time = timestamp ? new Date(timestamp).toLocaleTimeString() : new Date().toLocaleTimeString();
        logElement.innerHTML = `
            <span class="log-time" style="color: var(--text-tertiary); font-size: var(--font-size-xs); margin-right: var(--space-2);">
                ${time}
            </span>
            <span class="log-content">${this.escapeHtml(message)}</span>
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

        // Auto-scroll if enabled
        if (this.autoScroll) {
            this.scrollToBottom();
        }

        // Update log count
        this.updateLogCount();

        // Highlight critical errors
        if (level === 'ERROR' || level === 'CRITICAL') {
            logElement.style.animation = 'pulse 1s ease-in-out';
        }
    }

    shouldFilterLog(message, level) {
        // Filter out all HTTP request logs - we only want agent execution logs
        if (level === 'INFO' && message.includes(' - - [')) {
            const httpPatterns = [
                // API endpoints (polling noise)
                '/api/logs/recent',
                '/api/agent/status', 
                '/api/gpu-stats',
                '/api/preferences',
                '/api/system/info',
                // Static assets
                '/static/',
                '/favicon.ico',
                // Page requests
                'GET /',
                'GET /v2',
                '"GET',
                'HTTP/1.1" 200',
                'HTTP/1.1" 304',
                'HTTP/1.1" 404',
                // Common web requests
                'Successfully rendered template',
                'V2 page request received'
            ];
            
            return httpPatterns.some(pattern => message.includes(pattern));
        }
        
        // Filter out other web server noise
        const webServerPatterns = [
            'Invalid Date', // Date parsing issues in frontend
            'Web logging re-configured',
            'Application configuration loaded',
            'Successfully rendered template',
            'V2 page request',
            'template v2/index.html',
            '- INFO -', // Generic INFO logs that are usually HTTP
            '10.0.11.66 -' // IP address logs (usually HTTP)
        ];
        
        return webServerPatterns.some(pattern => message.includes(pattern));
    }

    addInitialLogs(logs) {
        this.logsContainer.innerHTML = '';
        this.logs = [];
        
        logs.forEach(log => this.addLog(log));
        this.scrollToBottom();
    }

    async clearLogs() {
        if (this.isClearing) {
            return;
        }

        try {
            this.isClearing = true;
            
            // Update UI immediately for responsiveness
            this.logsContainer.innerHTML = '<div class="log-message" style="text-align: center; color: var(--text-secondary); font-style: italic;">Clearing logs...</div>';
            
            // Use REST API for primary operation
            const result = await this.api.clearLogs();
            
            if (result.success) {
                this.logs = [];
                this.logsContainer.innerHTML = '';
                this.updateLogCount();
                this.showSuccess('Logs cleared successfully');
            } else {
                throw new Error(result.error || 'Failed to clear logs');
            }
            
        } catch (error) {
            console.error('Failed to clear logs:', error);
            this.showError(`Failed to clear logs: ${error.message}`);
            // Restore logs on error
            this.loadInitialLogs();
        } finally {
            this.isClearing = false;
        }
    }

    handleLogsCleared() {
        // Handle real-time notification that logs were cleared
        this.logs = [];
        this.logsContainer.innerHTML = '';
        this.updateLogCount();
    }

    scrollToBottom() {
        this.logsContainer.scrollTop = this.logsContainer.scrollHeight;
    }

    updateLogCount() {
        if (this.logCount) {
            this.logCount.textContent = this.logs.length;
        }
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    updateAgentStatus(isRunning, statusMessage = null) {
        if (!this.agentStatusText) return;

        if (isRunning) {
            this.agentStatusText.textContent = statusMessage || 'Running';
            this.agentStatusText.className = 'status-text status-running';
        } else {
            this.agentStatusText.textContent = statusMessage || 'Idle';
            this.agentStatusText.className = 'status-text status-idle';
        }
    }

    // === NOTIFICATION HELPERS ===
    
    showSuccess(message) {
        this.showNotification(message, 'success');
    }

    showError(message) {
        this.showNotification(message, 'error');
    }

    showInfo(message) {
        this.showNotification(message, 'info');
    }

    showNotification(message, type) {
        // Use global notification system if available
        if (window.uiManager && window.uiManager.showNotification) {
            window.uiManager.showNotification(message, type);
        } else {
            // Fallback to console
            console.log(`[${type.toUpperCase()}] ${message}`);
        }
    }

    // === PUBLIC API ===
    
    exportLogs() {
        const logsText = this.logs.map(log => {
            const time = log.timestamp ? new Date(log.timestamp).toISOString() : new Date().toISOString();
            return `[${time}] ${log.level}: ${log.message}`;
        }).join('\n');

        const blob = new Blob([logsText], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `knowledge-base-logs-${new Date().toISOString().split('T')[0]}.txt`;
        a.click();
        URL.revokeObjectURL(url);
        
        this.showSuccess('Logs exported successfully');
    }

    toggleAutoScroll() {
        this.autoScroll = !this.autoScroll;
        if (this.autoScroll) {
            this.scrollToBottom();
        }
        return this.autoScroll;
    }

    filterLogs(level = null) {
        const logElements = this.logsContainer.querySelectorAll('.log-message');
        logElements.forEach(element => {
            if (!level || element.dataset.level === level) {
                element.style.display = 'block';
            } else {
                element.style.display = 'none';
            }
        });
    }

    searchLogs(query) {
        if (!query) {
            this.filterLogs(); // Show all
            return;
        }

        const logElements = this.logsContainer.querySelectorAll('.log-message');
        logElements.forEach(element => {
            const content = element.textContent.toLowerCase();
            if (content.includes(query.toLowerCase())) {
                element.style.display = 'block';
                // Highlight search terms
                element.style.backgroundColor = 'rgba(255, 255, 0, 0.1)';
            } else {
                element.style.display = 'none';
            }
        });
    }
}

// Make globally available for non-module usage
window.LiveLogsManager = LiveLogsManager; 
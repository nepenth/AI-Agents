/**
 * Enhanced Live Logs Manager
 * 
 * Provides comprehensive live log display functionality with:
 * - Virtual scrolling for performance with large log volumes
 * - Advanced filtering (level, task_id, component, search text)
 * - Structured data display with expandable JSON formatting
 * - Log export functionality with multiple format options
 * - Real-time log highlighting for recent entries and errors
 * - Auto-scroll behavior with user control and bottom detection
 * - Log entry limit management with configurable retention
 */

class EnhancedLiveLogsManager {
    constructor(api, options = {}) {
        this.api = api;
        this.options = {
            maxLogs: 1000,
            virtualScrollThreshold: 100,
            autoScrollDelay: 100,
            highlightDuration: 3000,
            exportFormats: ['json', 'csv', 'txt'],
            filterDebounceDelay: 300,
            ...options
        };
        
        // State management
        this.logs = [];
        this.filteredLogs = [];
        this.displayedLogs = [];
        this.filters = {
            level: 'all',
            taskId: '',
            component: '',
            searchText: '',
            dateRange: null
        };
        
        // UI state
        this.autoScroll = true;
        this.isClearing = false;
        this.isExporting = false;
        this.virtualScrollEnabled = false;
        this.virtualScrollTop = 0;
        this.itemHeight = 60; // Estimated height per log entry
        this.visibleRange = { start: 0, end: 0 };
        
        // Performance tracking
        this.stats = {
            totalLogs: 0,
            filteredCount: 0,
            displayedCount: 0,
            lastUpdateTime: null,
            renderTime: 0
        };
        
        // UI Elements
        this.elements = {};
        
        // Event handlers
        this.boundHandlers = {
            scroll: this.handleScroll.bind(this),
            resize: this.handleResize.bind(this),
            keydown: this.handleKeydown.bind(this)
        };
        
        this.initialize();
    }
    
    initialize() {
        console.log('🔍 Initializing Enhanced Live Logs Manager...');
        
        this.setupElements();
        this.setupEventListeners();
        this.setupVirtualScrolling();
        this.loadInitialLogs();
        
        console.log('✅ Enhanced Live Logs Manager initialized');
    }
    
    setupElements() {
        // Main container
        this.elements.container = document.getElementById('logs-container');
        if (!this.elements.container) {
            console.error('❌ Logs container not found');
            return;
        }
        
        // Create enhanced UI structure
        this.createEnhancedUI();
        
        // Get references to created elements
        this.elements.toolbar = this.elements.container.querySelector('.logs-toolbar');
        this.elements.filters = this.elements.container.querySelector('.logs-filters');
        this.elements.viewport = this.elements.container.querySelector('.logs-viewport');
        this.elements.content = this.elements.container.querySelector('.logs-content');
        this.elements.stats = this.elements.container.querySelector('.logs-stats');
        
        // Filter elements
        this.elements.levelFilter = this.elements.filters.querySelector('#log-level-filter');
        this.elements.taskIdFilter = this.elements.filters.querySelector('#log-task-filter');
        this.elements.componentFilter = this.elements.filters.querySelector('#log-component-filter');
        this.elements.searchFilter = this.elements.filters.querySelector('#log-search-filter');
        this.elements.clearFiltersBtn = this.elements.filters.querySelector('#clear-filters-btn');
        
        // Toolbar elements
        this.elements.clearLogsBtn = this.elements.toolbar.querySelector('#clear-logs-btn');
        this.elements.exportBtn = this.elements.toolbar.querySelector('#export-logs-btn');
        this.elements.autoScrollToggle = this.elements.toolbar.querySelector('#auto-scroll-toggle');
        this.elements.virtualScrollToggle = this.elements.toolbar.querySelector('#virtual-scroll-toggle');
    }
    
    createEnhancedUI() {
        const container = this.elements.container;
        
        // Clear existing content
        container.innerHTML = '';
        
        // Create enhanced structure
        container.innerHTML = `
            <div class="logs-toolbar">
                <div class="toolbar-group">
                    <button id="clear-logs-btn" class="btn btn-sm btn-outline-danger" title="Clear all logs (Ctrl+L)">
                        <i class="bi bi-trash"></i> Clear
                    </button>
                    <button id="export-logs-btn" class="btn btn-sm btn-outline-primary" title="Export logs">
                        <i class="bi bi-download"></i> Export
                    </button>
                </div>
                <div class="toolbar-group">
                    <div class="form-check form-switch">
                        <input class="form-check-input" type="checkbox" id="auto-scroll-toggle" checked>
                        <label class="form-check-label" for="auto-scroll-toggle">Auto-scroll</label>
                    </div>
                    <div class="form-check form-switch">
                        <input class="form-check-input" type="checkbox" id="virtual-scroll-toggle">
                        <label class="form-check-label" for="virtual-scroll-toggle">Virtual scroll</label>
                    </div>
                </div>
            </div>
            
            <div class="logs-filters">
                <div class="row g-2">
                    <div class="col-md-2">
                        <select id="log-level-filter" class="form-select form-select-sm">
                            <option value="all">All Levels</option>
                            <option value="DEBUG">Debug</option>
                            <option value="INFO">Info</option>
                            <option value="WARNING">Warning</option>
                            <option value="ERROR">Error</option>
                            <option value="CRITICAL">Critical</option>
                        </select>
                    </div>
                    <div class="col-md-2">
                        <input type="text" id="log-task-filter" class="form-control form-control-sm" placeholder="Task ID...">
                    </div>
                    <div class="col-md-2">
                        <input type="text" id="log-component-filter" class="form-control form-control-sm" placeholder="Component...">
                    </div>
                    <div class="col-md-4">
                        <input type="text" id="log-search-filter" class="form-control form-control-sm" placeholder="Search logs...">
                    </div>
                    <div class="col-md-2">
                        <button id="clear-filters-btn" class="btn btn-sm btn-outline-secondary w-100">
                            <i class="bi bi-x-circle"></i> Clear Filters
                        </button>
                    </div>
                </div>
            </div>
            
            <div class="logs-stats">
                <small class="text-muted">
                    <span id="logs-count">0</span> logs 
                    (<span id="filtered-count">0</span> filtered, 
                    <span id="displayed-count">0</span> displayed)
                    | Last update: <span id="last-update">Never</span>
                    | Render time: <span id="render-time">0ms</span>
                </small>
            </div>
            
            <div class="logs-viewport">
                <div class="logs-content"></div>
            </div>
        `;
        
        // Add CSS classes
        container.classList.add('enhanced-logs-container');
    }
    
    setupEventListeners() {
        // Toolbar events
        if (this.elements.clearLogsBtn) {
            this.elements.clearLogsBtn.addEventListener('click', () => this.clearLogs());
        }
        
        if (this.elements.exportBtn) {
            this.elements.exportBtn.addEventListener('click', () => this.showExportDialog());
        }
        
        if (this.elements.autoScrollToggle) {
            this.elements.autoScrollToggle.addEventListener('change', (e) => {
                this.autoScroll = e.target.checked;
                if (this.autoScroll) {
                    this.scrollToBottom();
                }
            });
        }
        
        if (this.elements.virtualScrollToggle) {
            this.elements.virtualScrollToggle.addEventListener('change', (e) => {
                this.virtualScrollEnabled = e.target.checked;
                this.updateDisplay();
            });
        }
        
        // Filter events with debouncing
        const filterElements = [
            this.elements.levelFilter,
            this.elements.taskIdFilter,
            this.elements.componentFilter,
            this.elements.searchFilter
        ];
        
        filterElements.forEach(element => {
            if (element) {
                element.addEventListener('input', this.debounce(() => {
                    this.updateFilters();
                }, this.options.filterDebounceDelay));
            }
        });
        
        if (this.elements.clearFiltersBtn) {
            this.elements.clearFiltersBtn.addEventListener('click', () => this.clearFilters());
        }
        
        // Viewport events
        if (this.elements.viewport) {
            this.elements.viewport.addEventListener('scroll', this.boundHandlers.scroll);
        }
        
        // Global events
        window.addEventListener('resize', this.boundHandlers.resize);
        document.addEventListener('keydown', this.boundHandlers.keydown);
        
        // Custom events for log updates
        document.addEventListener('log', (event) => {
            this.addLog(event.detail);
        });
        
        document.addEventListener('live_log', (event) => {
            this.addLog(event.detail);
        });
        
        document.addEventListener('log_batch', (event) => {
            this.addLogBatch(event.detail);
        });
    }
    
    setupVirtualScrolling() {
        if (!this.elements.viewport) return;
        
        // Calculate item height from CSS or use default
        const testItem = document.createElement('div');
        testItem.className = 'log-entry';
        testItem.style.visibility = 'hidden';
        testItem.innerHTML = '<div class="log-content">Test</div>';
        
        this.elements.content.appendChild(testItem);
        this.itemHeight = testItem.offsetHeight || 60;
        this.elements.content.removeChild(testItem);
        
        console.log(`📏 Virtual scroll item height: ${this.itemHeight}px`);
    }
    
    async loadInitialLogs() {
        try {
            console.log('📥 Loading initial logs...');
            
            const response = await this.api.getRecentLogs();
            if (response && response.logs) {
                this.addInitialLogs(response.logs);
                console.log(`✅ Loaded ${response.logs.length} initial logs`);
            }
        } catch (error) {
            console.error('❌ Failed to load initial logs:', error);
            this.showError('Failed to load recent logs');
        }
    }
    
    addInitialLogs(logs) {
        const startTime = performance.now();
        
        // Process and add logs
        logs.forEach(log => {
            this.logs.push(this.processLogEntry(log));
        });
        
        // Update display
        this.applyFilters();
        this.updateDisplay();
        this.updateStats();
        
        const renderTime = performance.now() - startTime;
        this.stats.renderTime = renderTime;
        
        console.log(`📊 Initial logs rendered in ${renderTime.toFixed(2)}ms`);
    }
    
    addLog(logData) {
        const processedLog = this.processLogEntry(logData);
        
        // Add to logs array
        this.logs.push(processedLog);
        
        // Maintain log limit
        if (this.logs.length > this.options.maxLogs) {
            const removed = this.logs.splice(0, this.logs.length - this.options.maxLogs);
            console.log(`🗑️ Removed ${removed.length} old logs to maintain limit`);
        }
        
        // Apply filters and update display
        this.applyFilters();
        this.updateDisplay();
        this.updateStats();
        
        // Highlight new entry
        this.highlightNewEntry(processedLog.id);
        
        // Auto-scroll if enabled
        if (this.autoScroll) {
            setTimeout(() => this.scrollToBottom(), this.options.autoScrollDelay);
        }
    }
    
    addLogBatch(batchData) {
        if (!batchData || !Array.isArray(batchData.events)) {
            console.warn('⚠️ Invalid log batch data:', batchData);
            return;
        }
        
        console.log(`📦 Processing batch of ${batchData.events.length} logs`);
        
        const startTime = performance.now();
        
        // Process all logs in batch
        const processedLogs = batchData.events.map(log => this.processLogEntry(log));
        
        // Add to logs array
        this.logs.push(...processedLogs);
        
        // Maintain log limit
        if (this.logs.length > this.options.maxLogs) {
            const excess = this.logs.length - this.options.maxLogs;
            this.logs.splice(0, excess);
        }
        
        // Update display
        this.applyFilters();
        this.updateDisplay();
        this.updateStats();
        
        const renderTime = performance.now() - startTime;
        console.log(`📊 Batch processed in ${renderTime.toFixed(2)}ms`);
        
        // Auto-scroll if enabled
        if (this.autoScroll) {
            setTimeout(() => this.scrollToBottom(), this.options.autoScrollDelay);
        }
    }
    
    processLogEntry(logData) {
        const timestamp = new Date(logData.timestamp || Date.now());
        
        return {
            id: `log-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
            timestamp,
            level: (logData.level || 'INFO').toUpperCase(),
            message: logData.message || '',
            component: logData.component || 'unknown',
            taskId: logData.task_id || logData.taskId || '',
            structuredData: logData.structured_data || logData.data || null,
            raw: logData,
            isNew: true
        };
    }
    
    updateFilters() {
        // Get current filter values
        this.filters.level = this.elements.levelFilter?.value || 'all';
        this.filters.taskId = this.elements.taskIdFilter?.value.trim() || '';
        this.filters.component = this.elements.componentFilter?.value.trim() || '';
        this.filters.searchText = this.elements.searchFilter?.value.trim() || '';
        
        console.log('🔍 Filters updated:', this.filters);
        
        // Apply filters and update display
        this.applyFilters();
        this.updateDisplay();
        this.updateStats();
    }
    
    applyFilters() {
        const startTime = performance.now();
        
        this.filteredLogs = this.logs.filter(log => {
            // Level filter
            if (this.filters.level !== 'all' && log.level !== this.filters.level) {
                return false;
            }
            
            // Task ID filter
            if (this.filters.taskId && !log.taskId.includes(this.filters.taskId)) {
                return false;
            }
            
            // Component filter
            if (this.filters.component && !log.component.toLowerCase().includes(this.filters.component.toLowerCase())) {
                return false;
            }
            
            // Search text filter
            if (this.filters.searchText) {
                const searchLower = this.filters.searchText.toLowerCase();
                const searchableText = `${log.message} ${log.component} ${log.taskId}`.toLowerCase();
                if (!searchableText.includes(searchLower)) {
                    return false;
                }
            }
            
            return true;
        });
        
        const filterTime = performance.now() - startTime;
        console.log(`🔍 Filtered ${this.logs.length} logs to ${this.filteredLogs.length} in ${filterTime.toFixed(2)}ms`);
    }
    
    updateDisplay() {
        if (!this.elements.content) return;
        
        const startTime = performance.now();
        
        if (this.virtualScrollEnabled && this.filteredLogs.length > this.options.virtualScrollThreshold) {
            this.renderVirtualScrollContent();
        } else {
            this.renderFullContent();
        }
        
        const renderTime = performance.now() - startTime;
        this.stats.renderTime = renderTime;
        
        console.log(`🎨 Display updated in ${renderTime.toFixed(2)}ms`);
    }
    
    renderFullContent() {
        const fragment = document.createDocumentFragment();
        
        this.filteredLogs.forEach(log => {
            const logElement = this.createLogElement(log);
            fragment.appendChild(logElement);
        });
        
        this.elements.content.innerHTML = '';
        this.elements.content.appendChild(fragment);
        
        this.displayedLogs = [...this.filteredLogs];
    }
    
    renderVirtualScrollContent() {
        const viewport = this.elements.viewport;
        const content = this.elements.content;
        
        const viewportHeight = viewport.clientHeight;
        const scrollTop = viewport.scrollTop;
        
        // Calculate visible range
        const startIndex = Math.floor(scrollTop / this.itemHeight);
        const endIndex = Math.min(
            startIndex + Math.ceil(viewportHeight / this.itemHeight) + 5, // Buffer
            this.filteredLogs.length
        );
        
        this.visibleRange = { start: startIndex, end: endIndex };
        
        // Set content height for scrollbar
        const totalHeight = this.filteredLogs.length * this.itemHeight;
        content.style.height = `${totalHeight}px`;
        
        // Clear and render visible items
        const fragment = document.createDocumentFragment();
        const container = document.createElement('div');
        container.style.transform = `translateY(${startIndex * this.itemHeight}px)`;
        
        for (let i = startIndex; i < endIndex; i++) {
            if (this.filteredLogs[i]) {
                const logElement = this.createLogElement(this.filteredLogs[i]);
                container.appendChild(logElement);
            }
        }
        
        fragment.appendChild(container);
        content.innerHTML = '';
        content.appendChild(fragment);
        
        this.displayedLogs = this.filteredLogs.slice(startIndex, endIndex);
        
        console.log(`📊 Virtual scroll: showing ${endIndex - startIndex} of ${this.filteredLogs.length} logs`);
    }
    
    createLogElement(log) {
        const logElement = document.createElement('div');
        logElement.className = `log-entry log-${log.level.toLowerCase()}`;
        logElement.id = log.id;
        
        if (log.isNew) {
            logElement.classList.add('log-new');
        }
        
        const timeStr = log.timestamp.toLocaleTimeString();
        const hasStructuredData = log.structuredData && Object.keys(log.structuredData).length > 0;
        
        logElement.innerHTML = `
            <div class="log-header">
                <span class="log-timestamp">${timeStr}</span>
                <span class="log-level badge bg-${this.getLevelColor(log.level)}">${log.level}</span>
                ${log.component ? `<span class="log-component badge bg-secondary">${log.component}</span>` : ''}
                ${log.taskId ? `<span class="log-task-id badge bg-info">${log.taskId}</span>` : ''}
                ${hasStructuredData ? '<button class="btn btn-sm btn-outline-primary toggle-structured" title="Toggle structured data"><i class="bi bi-code"></i></button>' : ''}
            </div>
            <div class="log-message">${this.escapeHtml(log.message)}</div>
            ${hasStructuredData ? `<div class="log-structured" style="display: none;"><pre><code>${JSON.stringify(log.structuredData, null, 2)}</code></pre></div>` : ''}
        `;
        
        // Add structured data toggle
        if (hasStructuredData) {
            const toggleBtn = logElement.querySelector('.toggle-structured');
            const structuredDiv = logElement.querySelector('.log-structured');
            
            toggleBtn.addEventListener('click', () => {
                const isVisible = structuredDiv.style.display !== 'none';
                structuredDiv.style.display = isVisible ? 'none' : 'block';
                toggleBtn.innerHTML = isVisible ? '<i class="bi bi-code"></i>' : '<i class="bi bi-code-slash"></i>';
            });
        }
        
        return logElement;
    }
    
    getLevelColor(level) {
        const colors = {
            'DEBUG': 'secondary',
            'INFO': 'primary',
            'WARNING': 'warning',
            'ERROR': 'danger',
            'CRITICAL': 'dark'
        };
        return colors[level] || 'secondary';
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    highlightNewEntry(logId) {
        setTimeout(() => {
            const element = document.getElementById(logId);
            if (element) {
                element.classList.add('log-highlight');
                
                setTimeout(() => {
                    element.classList.remove('log-new', 'log-highlight');
                }, this.options.highlightDuration);
            }
        }, 50);
    }
    
    updateStats() {
        this.stats.totalLogs = this.logs.length;
        this.stats.filteredCount = this.filteredLogs.length;
        this.stats.displayedCount = this.displayedLogs.length;
        this.stats.lastUpdateTime = new Date();
        
        // Update UI
        const statsElements = {
            'logs-count': this.stats.totalLogs,
            'filtered-count': this.stats.filteredCount,
            'displayed-count': this.stats.displayedCount,
            'last-update': this.stats.lastUpdateTime.toLocaleTimeString(),
            'render-time': `${this.stats.renderTime.toFixed(1)}ms`
        };
        
        Object.entries(statsElements).forEach(([id, value]) => {
            const element = document.getElementById(id);
            if (element) {
                element.textContent = value;
            }
        });
    }
    
    clearFilters() {
        // Reset filter values
        if (this.elements.levelFilter) this.elements.levelFilter.value = 'all';
        if (this.elements.taskIdFilter) this.elements.taskIdFilter.value = '';
        if (this.elements.componentFilter) this.elements.componentFilter.value = '';
        if (this.elements.searchFilter) this.elements.searchFilter.value = '';
        
        // Update filters
        this.updateFilters();
        
        console.log('🧹 Filters cleared');
    }
    
    async clearLogs() {
        if (this.isClearing) return;
        
        this.isClearing = true;
        
        try {
            // Clear via API
            await this.api.clearLogs();
            
            // Clear local logs
            this.logs = [];
            this.filteredLogs = [];
            this.displayedLogs = [];
            
            // Update display
            this.updateDisplay();
            this.updateStats();
            
            console.log('🧹 Logs cleared successfully');
            
        } catch (error) {
            console.error('❌ Failed to clear logs:', error);
            this.showError('Failed to clear logs');
        } finally {
            this.isClearing = false;
        }
    }
    
    showExportDialog() {
        const modal = document.createElement('div');
        modal.className = 'modal fade';
        modal.innerHTML = `
            <div class="modal-dialog">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">Export Logs</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <div class="mb-3">
                            <label class="form-label">Export Format</label>
                            <select class="form-select" id="export-format">
                                <option value="json">JSON</option>
                                <option value="csv">CSV</option>
                                <option value="txt">Plain Text</option>
                            </select>
                        </div>
                        <div class="mb-3">
                            <div class="form-check">
                                <input class="form-check-input" type="checkbox" id="export-filtered" checked>
                                <label class="form-check-label" for="export-filtered">
                                    Export only filtered logs (${this.filteredLogs.length} entries)
                                </label>
                            </div>
                        </div>
                        <div class="mb-3">
                            <div class="form-check">
                                <input class="form-check-input" type="checkbox" id="include-structured">
                                <label class="form-check-label" for="include-structured">
                                    Include structured data
                                </label>
                            </div>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                        <button type="button" class="btn btn-primary" id="export-confirm">Export</button>
                    </div>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        const bootstrapModal = new bootstrap.Modal(modal);
        bootstrapModal.show();
        
        modal.querySelector('#export-confirm').addEventListener('click', () => {
            const format = modal.querySelector('#export-format').value;
            const useFiltered = modal.querySelector('#export-filtered').checked;
            const includeStructured = modal.querySelector('#include-structured').checked;
            
            this.exportLogs(format, useFiltered, includeStructured);
            bootstrapModal.hide();
        });
        
        modal.addEventListener('hidden.bs.modal', () => {
            document.body.removeChild(modal);
        });
    }
    
    exportLogs(format, useFiltered = true, includeStructured = false) {
        const logsToExport = useFiltered ? this.filteredLogs : this.logs;
        
        let content = '';
        let filename = `logs-${new Date().toISOString().split('T')[0]}`;
        let mimeType = 'text/plain';
        
        switch (format) {
            case 'json':
                content = JSON.stringify(logsToExport.map(log => {
                    const exportLog = {
                        timestamp: log.timestamp.toISOString(),
                        level: log.level,
                        message: log.message,
                        component: log.component,
                        taskId: log.taskId
                    };
                    
                    if (includeStructured && log.structuredData) {
                        exportLog.structuredData = log.structuredData;
                    }
                    
                    return exportLog;
                }), null, 2);
                filename += '.json';
                mimeType = 'application/json';
                break;
                
            case 'csv':
                const headers = ['Timestamp', 'Level', 'Component', 'Task ID', 'Message'];
                if (includeStructured) headers.push('Structured Data');
                
                content = headers.join(',') + '\n';
                content += logsToExport.map(log => {
                    const row = [
                        log.timestamp.toISOString(),
                        log.level,
                        log.component,
                        log.taskId,
                        `"${log.message.replace(/"/g, '""')}"`
                    ];
                    
                    if (includeStructured) {
                        row.push(`"${JSON.stringify(log.structuredData || {}).replace(/"/g, '""')}"`);
                    }
                    
                    return row.join(',');
                }).join('\n');
                filename += '.csv';
                mimeType = 'text/csv';
                break;
                
            case 'txt':
            default:
                content = logsToExport.map(log => {
                    let line = `[${log.timestamp.toISOString()}] ${log.level} ${log.component}${log.taskId ? ` (${log.taskId})` : ''}: ${log.message}`;
                    
                    if (includeStructured && log.structuredData) {
                        line += `\n  Structured Data: ${JSON.stringify(log.structuredData)}`;
                    }
                    
                    return line;
                }).join('\n');
                filename += '.txt';
                break;
        }
        
        // Create and trigger download
        const blob = new Blob([content], { type: mimeType });
        const url = URL.createObjectURL(blob);
        
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        
        URL.revokeObjectURL(url);
        
        console.log(`📥 Exported ${logsToExport.length} logs as ${format.toUpperCase()}`);
    }
    
    scrollToBottom() {
        if (this.elements.viewport) {
            this.elements.viewport.scrollTop = this.elements.viewport.scrollHeight;
        }
    }
    
    handleScroll() {
        if (!this.elements.viewport) return;
        
        const { scrollTop, scrollHeight, clientHeight } = this.elements.viewport;
        
        // Update auto-scroll state
        const wasAutoScroll = this.autoScroll;
        this.autoScroll = scrollTop + clientHeight >= scrollHeight - 10;
        
        // Update toggle if state changed
        if (wasAutoScroll !== this.autoScroll && this.elements.autoScrollToggle) {
            this.elements.autoScrollToggle.checked = this.autoScroll;
        }
        
        // Update virtual scroll if enabled
        if (this.virtualScrollEnabled) {
            this.updateDisplay();
        }
    }
    
    handleResize() {
        if (this.virtualScrollEnabled) {
            this.updateDisplay();
        }
    }
    
    handleKeydown(event) {
        // Keyboard shortcuts
        if (event.ctrlKey) {
            switch (event.key) {
                case 'l':
                    event.preventDefault();
                    this.clearLogs();
                    break;
                case 'f':
                    event.preventDefault();
                    if (this.elements.searchFilter) {
                        this.elements.searchFilter.focus();
                    }
                    break;
                case 'e':
                    event.preventDefault();
                    this.showExportDialog();
                    break;
            }
        }
        
        // Escape to clear search
        if (event.key === 'Escape' && this.elements.searchFilter === document.activeElement) {
            this.elements.searchFilter.value = '';
            this.updateFilters();
        }
    }
    
    showError(message) {
        console.error('❌', message);
        // Could integrate with notification system
    }
    
    showInfo(message) {
        console.log('ℹ️', message);
        // Could integrate with notification system
    }
    
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }
    
    getStats() {
        return {
            ...this.stats,
            filters: { ...this.filters },
            virtualScrollEnabled: this.virtualScrollEnabled,
            autoScroll: this.autoScroll,
            visibleRange: { ...this.visibleRange }
        };
    }
    
    destroy() {
        // Remove event listeners
        if (this.elements.viewport) {
            this.elements.viewport.removeEventListener('scroll', this.boundHandlers.scroll);
        }
        
        window.removeEventListener('resize', this.boundHandlers.resize);
        document.removeEventListener('keydown', this.boundHandlers.keydown);
        
        // Clear data
        this.logs = [];
        this.filteredLogs = [];
        this.displayedLogs = [];
        
        console.log('🧹 Enhanced Live Logs Manager destroyed');
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = EnhancedLiveLogsManager;
} else {
    window.EnhancedLiveLogsManager = EnhancedLiveLogsManager;
}
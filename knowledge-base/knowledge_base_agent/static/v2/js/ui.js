/* V2 UI.JS - PURE API POLLING UI ORCHESTRATOR */

/**
 * Enhanced Dashboard Manager with Task State Management
 * Coordinates all dashboard components with comprehensive state tracking
 */
class DashboardManager {
    constructor(api) {
        this.api = api;
        this.managers = {};
        this.taskStateManager = null;
        console.log('🎛️ DashboardManager constructor called');
    }

    async initialize() {
        console.log('🎛️ DashboardManager.initialize() called');

        try {
            // Step 1: Initialize Task State Manager
            console.log('🔄 Step 1: Initializing Task State Manager...');
            if (window.taskStateManager) {
                this.taskStateManager = window.taskStateManager;
                this.setupTaskStateListeners();
                console.log('✅ Step 1: Task State Manager connected');
            } else {
                console.warn('⚠️ Task State Manager not available');
            }

            // Step 2: Load dashboard content
            console.log('📄 Step 2: Loading dashboard content...');
            await this.loadDashboardContent();
            console.log('✅ Step 2: Dashboard content loaded');

            // Step 3: Check manager availability
            console.log('🔍 Step 3: Checking manager class availability...');
            const availableManagers = {
                AgentControlManager: !!window.AgentControlManager,
                ExecutionPlanManager: !!window.ExecutionPlanManager,
                LiveLogsManager: !!window.LiveLogsManager,
                GpuStatusManager: !!window.GpuStatusManager
            };
            console.log('Manager availability:', availableManagers);

            // Step 4: Initialize managers one by one with error handling
            console.log('🔧 Step 4: Initializing managers...');

            if (window.AgentControlManager) {
                console.log('Initializing AgentControlManager...');
                this.managers.agentControls = new window.AgentControlManager(this.api);
                console.log('✅ AgentControlManager initialized');
            } else {
                console.error('❌ AgentControlManager not available');
            }

            if (window.ExecutionPlanManager) {
                console.log('Initializing ExecutionPlanManager...');
                this.managers.executionPlan = new window.ExecutionPlanManager();
                console.log('✅ ExecutionPlanManager initialized');
            } else {
                console.error('❌ ExecutionPlanManager not available');
            }

            if (window.LiveLogsManager) {
                console.log('Initializing LiveLogsManager...');
                this.managers.liveLogs = new window.LiveLogsManager(this.api);
                console.log('✅ LiveLogsManager initialized');
            } else {
                console.error('❌ LiveLogsManager not available');
            }

            if (window.GpuStatusManager) {
                console.log('Initializing GpuStatusManager...');
                this.managers.gpuStatus = new window.GpuStatusManager(this.api);
                console.log('✅ GpuStatusManager initialized');
            } else {
                console.error('❌ GpuStatusManager not available');
            }

            if (window.HistoricalTasksManager) {
                console.log('Initializing HistoricalTasksManager...');
                this.managers.historicalTasks = new window.HistoricalTasksManager(this.api);
                console.log('✅ HistoricalTasksManager initialized');
            } else {
                console.error('❌ HistoricalTasksManager not available');
            }

            // Initialize new display components
            if (window.PhaseDisplayManager) {
                console.log('Initializing PhaseDisplayManager...');
                this.managers.phaseDisplay = new window.PhaseDisplayManager();
                console.log('✅ PhaseDisplayManager initialized');
            } else {
                console.error('❌ PhaseDisplayManager not available');
            }

            if (window.ProgressDisplayManager) {
                console.log('Initializing ProgressDisplayManager...');
                this.managers.progressDisplay = new window.ProgressDisplayManager();
                console.log('✅ ProgressDisplayManager initialized');
            } else {
                console.error('❌ ProgressDisplayManager not available');
            }

            if (window.TaskDisplayManager) {
                console.log('Initializing TaskDisplayManager...');
                this.managers.taskDisplay = new window.TaskDisplayManager();
                console.log('✅ TaskDisplayManager initialized');
            } else {
                console.error('❌ TaskDisplayManager not available');
            }

            // Initialize error handling and notification systems
            if (window.NotificationSystem) {
                console.log('Initializing NotificationSystem...');
                this.managers.notifications = new window.NotificationSystem({
                    position: 'top-right',
                    maxNotifications: 5
                });
                console.log('✅ NotificationSystem initialized');
            } else {
                console.error('❌ NotificationSystem not available');
            }

            if (window.RedisConnectionManager) {
                console.log('Initializing RedisConnectionManager...');
                this.managers.redisConnection = new window.RedisConnectionManager({
                    host: 'localhost',
                    port: 6379,
                    maxRetries: 10
                });
                console.log('✅ RedisConnectionManager initialized');
            } else {
                console.error('❌ RedisConnectionManager not available');
            }

            if (window.SocketIOReconnectionManager && window.socket) {
                console.log('Initializing SocketIOReconnectionManager...');
                this.managers.socketIOReconnection = new window.SocketIOReconnectionManager(
                    { socket: window.socket },
                    {
                        maxReconnectAttempts: 15,
                        baseDelay: 1000,
                        maxDelay: 30000
                    }
                );
                console.log('✅ SocketIOReconnectionManager initialized');
            } else {
                console.error('❌ SocketIOReconnectionManager not available or no socket');
            }

            // Initialize performance monitoring
            if (window.PerformanceMonitor) {
                console.log('Initializing PerformanceMonitor...');
                this.managers.performance = new window.PerformanceMonitor({
                    batchSize: 50,
                    batchTimeout: 1000,
                    rateLimit: 100,
                    memoryCheckInterval: 30000,
                    metricsInterval: 5000
                });
                console.log('✅ PerformanceMonitor initialized');
            } else {
                console.error('❌ PerformanceMonitor not available');
            }

            // Initialize performance optimizer
            if (window.PerformanceOptimizer) {
                console.log('Initializing PerformanceOptimizer...');
                this.managers.performanceOptimizer = new window.PerformanceOptimizer({
                    domBatchSize: 20,
                    domBatchDelay: 16,
                    memoryThreshold: 150 * 1024 * 1024,
                    eventBatchSize: 50,
                    virtualScrollThreshold: 100
                });
                console.log('✅ PerformanceOptimizer initialized');
            } else {
                console.error('❌ PerformanceOptimizer not available');
            }

            console.log('✅ All dashboard components initialized successfully');

        } catch (error) {
            console.error('❌ DashboardManager initialization failed:', error);
            console.error('Error stack:', error.stack);

            // Show user-friendly error with more detail
            const mainContent = document.getElementById('main-content');
            if (mainContent) {
                mainContent.innerHTML = `
                    <div class="error-state" style="
                        display: flex;
                        flex-direction: column;
                        align-items: center;
                        justify-content: center;
                        height: 50vh;
                        padding: var(--space-6);
                        text-align: center;
                        gap: var(--space-4);
                    ">
                        <i class="fas fa-exclamation-triangle" style="
                            font-size: 3rem;
                            color: var(--color-warning);
                        "></i>
                        <h3 style="margin: 0; color: var(--text-primary);">Dashboard Initialization Failed</h3>
                        <p style="margin: 0; color: var(--text-secondary);">Error: ${error.message}</p>
                        <details style="margin-top: var(--space-2); color: var(--text-tertiary); font-size: var(--font-size-sm);">
                            <summary>Technical Details</summary>
                            <pre style="margin-top: var(--space-2); text-align: left; overflow: auto; max-width: 100%;">${error.stack || 'No stack trace available'}</pre>
                        </details>
                        <button onclick="location.reload()" class="glass-button glass-button--primary">
                            <i class="fas fa-refresh"></i> Reload Page
                        </button>
                    </div>
                `;
            }

            throw error; // Re-throw to let router handle it
        }
    }

    async loadDashboardContent() {
        try {
            console.log('📄 Loading dashboard content from /v2/page/index...');

            const mainContent = document.getElementById('main-content');
            if (!mainContent) {
                throw new Error('Main content container (#main-content) not found in DOM');
            }

            console.log('📄 Main content container found, showing loading indicator...');

            // Show loading indicator
            mainContent.innerHTML = `
                <div class="loading-container" style="
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    height: 50vh;
                    gap: var(--space-4);
                ">
                    <div class="loading-spinner" style="
                        width: 48px;
                        height: 48px;
                        border: 4px solid rgba(255, 255, 255, 0.1);
                        border-top: 4px solid var(--primary-blue);
                        border-radius: 50%;
                        animation: spin 1s linear infinite;
                    "></div>
                    <p style="color: var(--text-secondary); margin: 0;">Loading dashboard...</p>
                </div>
            `;

            console.log('📄 Fetching dashboard content...');

            // Create a timeout promise for the fetch request
            const timeoutPromise = new Promise((_, reject) => {
                setTimeout(() => reject(new Error('Request timeout after 10 seconds')), 10000);
            });

            // Race the fetch against the timeout
            const fetchPromise = fetch('/v2/page/index');
            const response = await Promise.race([fetchPromise, timeoutPromise]);

            console.log('📄 Fetch response status:', response.status, response.statusText);

            if (!response.ok) {
                throw new Error(`Failed to load dashboard content: ${response.status} ${response.statusText}`);
            }

            const html = await response.text();
            console.log('📄 Dashboard HTML loaded, length:', html.length);

            // Basic validation of the HTML content
            if (!html || html.trim().length === 0) {
                throw new Error('Received empty content from server');
            }

            // Load dashboard HTML with fade transition
            mainContent.style.opacity = '0';
            mainContent.innerHTML = html;

            // Fade in
            setTimeout(() => {
                mainContent.style.opacity = '1';
                console.log('📄 Dashboard content displayed with fade-in');
            }, 100);

            console.log('✅ Dashboard content loaded successfully');

        } catch (error) {
            console.error('❌ Failed to load dashboard content:', error);

            // Show error with fallback
            const mainContent = document.getElementById('main-content');
            if (mainContent) {
                mainContent.innerHTML = `
                    <div class="error-state" style="
                        display: flex;
                        flex-direction: column;
                        align-items: center;
                        justify-content: center;
                        height: 50vh;
                        padding: var(--space-6);
                        text-align: center;
                        gap: var(--space-4);
                    ">
                        <i class="fas fa-exclamation-triangle" style="
                            font-size: 3rem;
                            color: var(--color-warning);
                        "></i>
                        <h3 style="margin: 0; color: var(--text-primary);">Failed to Load Dashboard Content</h3>
                        <p style="margin: 0; color: var(--text-secondary);">Error: ${error.message}</p>
                        <div style="display: flex; gap: var(--space-3); flex-wrap: wrap; justify-content: center;">
                            <button onclick="location.reload()" class="glass-button glass-button--primary">
                                <i class="fas fa-refresh"></i> Reload Page
                            </button>
                            <button onclick="fetch('/v2/page/index').then(r => r.text()).then(html => document.getElementById('main-content').innerHTML = html).catch(e => console.error(e))" 
                                    class="glass-button glass-button--secondary">
                                <i class="fas fa-retry"></i> Retry Load
                            </button>
                        </div>
                    </div>
                `;
            }

            throw error;
        }
    }

    /**
     * Set up task state event listeners for comprehensive state management
     */
    setupTaskStateListeners() {
        if (!this.taskStateManager) return;

        // Task restored on page load
        this.taskStateManager.on('taskRestored', (task) => {
            console.log('🔄 Task state restored:', task.task_id);
            this.handleTaskRestored(task);
        });

        // No active task found
        this.taskStateManager.on('noActiveTask', () => {
            console.log('ℹ️ No active task found');
            this.handleNoActiveTask();
        });

        // Task started
        this.taskStateManager.on('taskStarted', (task) => {
            console.log('🚀 Task started:', task.task_id);
            this.handleTaskStarted(task);
        });

        // Task progress updates
        this.taskStateManager.on('taskProgress', (status) => {
            this.handleTaskProgress(status);
        });

        // Task completed
        this.taskStateManager.on('taskCompleted', (status) => {
            console.log('✅ Task completed:', status.task_id);
            this.handleTaskCompleted(status);
        });

        // Task stopped
        this.taskStateManager.on('taskStopped', (data) => {
            console.log('⏹️ Task stopped:', data.task_id);
            this.handleTaskStopped(data);
        });

        // Task errors
        this.taskStateManager.on('taskError', (error) => {
            console.error('❌ Task error:', error);
            this.handleTaskError(error);
        });

        // Agent reset
        this.taskStateManager.on('agentReset', (data) => {
            console.log('🔄 Agent reset:', data);
            this.handleAgentReset(data);
        });
    }

    /**
     * Handle task restored on page load
     */
    handleTaskRestored(task) {
        // Update all UI components with restored task state
        if (this.managers.agentControls) {
            this.managers.agentControls.updateStatus({
                is_running: task.is_running,
                current_phase_message: task.current_phase_message || 'Processing...',
                task_id: task.task_id
            });
        }

        if (this.managers.executionPlan && task.run_report) {
            this.managers.executionPlan.updateFromRunReport(task.run_report);
        }

        if (this.managers.liveLogs && task.logs) {
            this.managers.liveLogs.displayLogs(task.logs);
        }

        // Show notification about restored task
        if (this.managers.notifications) {
            this.managers.notifications.show({
                type: 'info',
                title: 'Task State Restored',
                message: `Restored active task: ${task.human_readable_name || task.task_id}`,
                duration: 5000
            });
        }
    }

    /**
     * Handle no active task found
     */
    handleNoActiveTask() {
        // Ensure UI is in idle state
        if (this.managers.agentControls) {
            this.managers.agentControls.updateStatus({
                is_running: false,
                current_phase_message: 'Idle',
                task_id: null
            });
        }
    }

    /**
     * Handle task started
     */
    handleTaskStarted(task) {
        // Update UI for new task
        if (this.managers.agentControls) {
            this.managers.agentControls.updateStatus({
                is_running: true,
                current_phase_message: 'Starting...',
                task_id: task.task_id
            });
        }

        // Clear previous logs
        if (this.managers.liveLogs) {
            this.managers.liveLogs.clearLogs();
        }

        // Show notification
        if (this.managers.notifications) {
            this.managers.notifications.show({
                type: 'success',
                title: 'Task Started',
                message: `Started: ${task.human_readable_name || task.task_id}`,
                duration: 3000
            });
        }
    }

    /**
     * Handle task progress updates
     */
    handleTaskProgress(status) {
        // Update progress displays
        if (this.managers.progressDisplay) {
            this.managers.progressDisplay.updateProgress({
                progress: status.progress_percentage || 0,
                phase_id: status.current_phase_id,
                message: status.current_phase_message
            });
        }

        // Update agent controls
        if (this.managers.agentControls) {
            this.managers.agentControls.updateStatus({
                is_running: status.is_running,
                current_phase_message: status.current_phase_message,
                task_id: status.task_id
            });
        }

        // Update execution plan if available
        if (this.managers.executionPlan && status.run_report) {
            this.managers.executionPlan.updateFromRunReport(status.run_report);
        }
    }

    /**
     * Handle task completed
     */
    handleTaskCompleted(status) {
        // Update UI to show completion
        if (this.managers.agentControls) {
            this.managers.agentControls.updateStatus({
                is_running: false,
                current_phase_message: 'Completed',
                task_id: status.task_id
            });
        }

        if (this.managers.progressDisplay) {
            this.managers.progressDisplay.updateProgress({
                progress: 100,
                phase_id: 'completed',
                message: 'Task completed successfully'
            });
        }

        // Show completion notification
        if (this.managers.notifications) {
            const isSuccess = status.status === 'SUCCESS';
            this.managers.notifications.show({
                type: isSuccess ? 'success' : 'error',
                title: isSuccess ? 'Task Completed' : 'Task Failed',
                message: isSuccess ? 
                    `Successfully completed: ${status.human_readable_name || status.task_id}` :
                    `Task failed: ${status.error_message || 'Unknown error'}`,
                duration: isSuccess ? 5000 : 10000
            });
        }
    }

    /**
     * Handle task stopped
     */
    handleTaskStopped(data) {
        // Update UI to show stopped state
        if (this.managers.agentControls) {
            this.managers.agentControls.updateStatus({
                is_running: false,
                current_phase_message: 'Stopped',
                task_id: data.task_id
            });
        }

        // Show notification
        if (this.managers.notifications) {
            this.managers.notifications.show({
                type: 'warning',
                title: 'Task Stopped',
                message: `Task ${data.task_id} was stopped`,
                duration: 3000
            });
        }
    }

    /**
     * Handle task errors
     */
    handleTaskError(error) {
        console.error('Task error:', error);

        // Show error notification
        if (this.managers.notifications) {
            this.managers.notifications.show({
                type: 'error',
                title: 'Task Error',
                message: error.message || 'An unknown error occurred',
                duration: 10000
            });
        }
    }

    /**
     * Handle agent reset
     */
    handleAgentReset(data) {
        // Reset all UI components
        if (this.managers.agentControls) {
            this.managers.agentControls.updateStatus({
                is_running: false,
                current_phase_message: 'Idle',
                task_id: null
            });
        }

        if (this.managers.progressDisplay) {
            this.managers.progressDisplay.reset();
        }

        if (this.managers.executionPlan) {
            this.managers.executionPlan.reset();
        }

        // Show notification
        if (this.managers.notifications) {
            this.managers.notifications.show({
                type: 'info',
                title: 'Agent Reset',
                message: 'Agent state has been reset to idle',
                duration: 3000
            });
        }
    }

    cleanup() {
        console.log('🧹 Cleaning up Dashboard...');

        // Cleanup all managers
        Object.values(this.managers).forEach(manager => {
            if (typeof manager.cleanup === 'function') {
                manager.cleanup();
            }
        });

        this.managers = {};
    }
}

/**
 * API Client for REST-first operations
 * Following our hybrid architecture: REST APIs are PRIMARY, SocketIO is for notifications
 */
class APIClient {
    constructor() {
        this.baseURL = '/api';
    }

    async request(endpoint, options = {}) {
        const url = `${this.baseURL}${endpoint}`;
        const config = {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        };

        if (config.body && typeof config.body === 'object') {
            config.body = JSON.stringify(config.body);
        }

        try {
            const response = await fetch(url, config);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                return await response.json();
            }

            return await response.text();
        } catch (error) {
            console.error(`API request failed: ${endpoint}`, error);
            throw error;
        }
    }

    // === AGENT OPERATIONS (V2 Celery) ===
    // Updated to target the new Celery-enabled API endpoints.
    async startAgent(preferences) {
        return this.request('/v2/agent/start', {
            method: 'POST',
            body: { preferences: preferences }
        });
    }

    async stopAgent(taskId = null) {
        return this.request('/v2/agent/stop', {
            method: 'POST',
            body: { task_id: taskId }
        });
    }

    async getAgentStatus() {
        return this.request('/agent/status');
    }

    // === SYSTEM OPERATIONS ===
    async getSystemInfo() {
        return this.request('/system/info');
    }

    async getPreferences() {
        return this.request('/preferences');
    }

    async updatePreferences(preferences) {
        return this.request('/preferences', {
            method: 'POST',
            body: preferences
        });
    }

    // === LOG OPERATIONS ===
    async getRecentLogs() {
        return this.request('/logs/recent');
    }

    async clearLogs() {
        return this.request('/v2/logs/clear', {
            method: 'POST'
        });
    }

    // === KNOWLEDGE BASE OPERATIONS ===
    async getKBItems() {
        return this.request('/items');
    }

    async getKBItem(id) {
        return this.request(`/items/${id}`);
    }

    async getSyntheses() {
        return this.request('/syntheses');
    }

    async getSynthesis(id) {
        return this.request(`/synthesis/${id}`);
    }
}

/**
 * Theme Manager for dark/light mode switching
 */
class ThemeManager {
    constructor(toggleCheckboxId) {
        this.toggleCheckbox = document.getElementById(toggleCheckboxId);
        if (!this.toggleCheckbox) return;
        this.init();
    }

    init() {
        // Check for saved theme preference or default to system preference
        const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        const savedTheme = localStorage.getItem('theme');

        if (savedTheme) {
            document.body.className = savedTheme;
            this.toggleCheckbox.checked = savedTheme === 'dark-mode';
        } else {
            document.body.className = prefersDark ? 'dark-mode' : 'light-mode';
            this.toggleCheckbox.checked = prefersDark;
        }

        this.toggleCheckbox.addEventListener('change', this.toggleTheme.bind(this));

        // Listen for system theme changes
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
            if (!localStorage.getItem('theme')) {
                document.body.className = e.matches ? 'dark-mode' : 'light-mode';
                this.toggleCheckbox.checked = e.matches;
            }
        });
    }

    toggleTheme() {
        const newTheme = this.toggleCheckbox.checked ? 'dark-mode' : 'light-mode';
        document.body.className = newTheme;
        localStorage.setItem('theme', newTheme);

        // Dispatch custom event for other components to react
        window.dispatchEvent(new CustomEvent('themeChanged', {
            detail: { theme: newTheme }
        }));
    }
}

/**
 * Sidebar Manager for responsive navigation
 */
class SidebarManager {
    constructor() {
        this.sidebarToggle = document.getElementById('sidebar-toggle');
        this.pageContainer = document.querySelector('.page-container');
        this.overlay = null;
        this.isCollapsed = false;

        if (!this.sidebarToggle || !this.pageContainer) return;
        this.init();
    }

    init() {
        this.sidebarToggle.addEventListener('click', () => {
            this.toggleSidebar();
        });

        // Close sidebar when clicking outside on mobile
        document.addEventListener('click', (e) => {
            if (window.innerWidth <= 768 &&
                this.isCollapsed &&
                !e.target.closest('.sidebar') &&
                !e.target.closest('#sidebar-toggle')) {
                this.expandSidebar();
            }
        });

        // Handle resize events
        window.addEventListener('resize', () => {
            if (window.innerWidth > 768 && this.overlay) {
                this.removeOverlay();
            }
        });

        // Handle keyboard navigation
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.isCollapsed && window.innerWidth <= 768) {
                this.expandSidebar();
            }
        });
    }

    toggleSidebar() {
        if (this.isCollapsed) {
            this.expandSidebar();
        } else {
            this.collapseSidebar();
        }
    }

    collapseSidebar() {
        this.pageContainer.classList.add('sidebar-collapsed');
        this.isCollapsed = true;

        // Don't change the icon - CSS will handle the rotation

        // Add overlay for mobile
        if (window.innerWidth <= 768) {
            this.createOverlay();
        }

        console.log('Sidebar collapsed');
    }

    expandSidebar() {
        this.pageContainer.classList.remove('sidebar-collapsed');
        this.isCollapsed = false;

        // Don't change the icon - CSS will handle the rotation

        this.removeOverlay();

        console.log('Sidebar expanded');
    }

    createOverlay() {
        if (this.overlay) return;

        this.overlay = document.createElement('div');
        this.overlay.className = 'sidebar-overlay';
        this.overlay.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.5);
            z-index: 99;
            backdrop-filter: blur(2px);
        `;

        this.overlay.addEventListener('click', () => {
            this.expandSidebar();
        });

        document.body.appendChild(this.overlay);
    }

    removeOverlay() {
        if (this.overlay) {
            document.body.removeChild(this.overlay);
            this.overlay = null;
        }
    }
}

/**
 * Main UI Manager implementing REST-first + SocketIO hybrid architecture
 */
class UIManager {
    constructor() {
        // Initialize API client for REST operations
        this.api = new APIClient();

        // Initialize state tracking for task completion detection
        this.lastKnownRunningState = false;

        // Establish Socket.IO connection for real-time updates (if server supports it)
        try {
            if (window.io) {
                // Use long-polling transport only; gevent server doesn’t support native WebSocket
                window.socket = window.io({ transports: ['polling'], path: '/socket.io' });
                console.log('🔌 Socket.IO connection established');
            } else {
                console.warn('Socket.IO library not loaded – real-time socket updates disabled.');
            }
        } catch (err) {
            console.error('Failed to initialize Socket.IO:', err);
        }

        // Initialize polling for real-time updates (replaces SocketIO)
        this.pollingIntervals = {};
        this.lastLogTimestamp = null;
        this.initializePolling();

        // Initialize core UI components only
        this.sidebarManager = new SidebarManager();
        this.themeManager = new ThemeManager('theme-toggle');
        this.dashboardManager = null; // Will be initialized when dashboard loads

        // Initialize utility manager for Celery management
        if (window.UtilityManager) {
            this.utilityManager = new UtilityManager(this.api);
        }

        // Initialize UI effects if available
        if (window.UIEffects) {
            this.effects = new window.UIEffects();
        }

        this.initializeApp();
    }

    initializePolling() {
        console.log('📊 Setting up API polling for real-time features...');

        // CRITICAL FIX: Completely disable API polling for logs when SocketIO is available
        // This prevents duplicate logs from appearing in the console
        
        if (!window.socket) {
            console.log('🔌 SocketIO not available - using API polling for all updates');
            this.startPolling('status', '/agent/status', 3000);
            this.startPolling('logs', '/logs/recent', 2500);
            this.startPolling('gpu-stats', '/gpu-stats', 5000);
            console.log('✅ API polling started (SocketIO unavailable)');
        } else {
            // SocketIO is available - set up connection monitoring
            this.setupSocketIOMonitoring();
            
            // Only poll status as backup (no logs polling to prevent duplicates)
            this.startPolling('status', '/agent/status', 15000); // 15 seconds (very infrequent backup)
            
            // CRITICAL FIX: Always poll GPU stats since SocketIO doesn't handle them
            this.startPolling('gpu-stats', '/gpu-stats', 5000); // GPU stats every 5 seconds
            
            console.log('✅ SocketIO available - minimal polling enabled, logs via SocketIO only, GPU stats via polling');
        }
    }

    setupSocketIOMonitoring() {
        if (!window.socket) return;

        // Monitor SocketIO connection status
        window.socket.on('connect', () => {
            console.log('🔌 SocketIO connected - stopping log polling to prevent duplicates');
            this.stopLogPolling();
        });

        window.socket.on('disconnect', () => {
            console.log('🔌 SocketIO disconnected - starting emergency log polling');
            this.startPolling('logs', '/logs/recent', 3000); // Emergency polling
        });

        window.socket.on('connect_error', () => {
            console.log('🔌 SocketIO connection error - starting emergency log polling');
            this.startPolling('logs', '/logs/recent', 3000); // Emergency polling
        });
    }

    stopLogPolling() {
        if (this.pollingIntervals['logs']) {
            clearInterval(this.pollingIntervals['logs']);
            delete this.pollingIntervals['logs'];
            console.log('🛑 Stopped log polling to prevent duplicates');
        }
    }

    startPolling(name, endpoint, interval) {
        // Clear any existing interval
        if (this.pollingIntervals[name]) {
            clearInterval(this.pollingIntervals[name]);
        }

        // Start new polling interval
        this.pollingIntervals[name] = setInterval(async () => {
            try {
                let url = endpoint;

                // Add timestamp parameter for logs to get only new logs
                if (name === 'logs' && this.lastLogTimestamp) {
                    url += `?since=${encodeURIComponent(this.lastLogTimestamp)}`;
                }

                const response = await this.api.request(url);
                this.handlePollingResponse(name, response);
            } catch (error) {
                console.warn(`⚠️ Polling failed for ${name}:`, error);
                // Don't show error notifications for polling failures
            }
        }, interval);

        console.log(`📊 Started polling ${name} every ${interval}ms`);
    }

    handlePollingResponse(type, data) {
        switch (type) {
            case 'status':
                this.handleStatusUpdate(data);
                break;
            case 'logs':
                this.handleLogsUpdate(data);
                break;
            case 'gpu-stats':
                this.handleGpuStatsUpdate(data);
                break;
        }
    }

    handleStatusUpdate(statusData) {
        // CRITICAL FIX: Detect task completion
        const wasRunning = this.lastKnownRunningState;
        const isRunning = statusData.is_running;
        this.lastKnownRunningState = isRunning;

        // Check for task completion (was running, now not running)
        if (wasRunning && !isRunning) {
            console.log('🎉 Task completion detected!');
            this.handleTaskCompletion(statusData);
        }

        // Check for completion status in progress data
        if (statusData.progress && statusData.progress.status) {
            const progressStatus = statusData.progress.status.toLowerCase();
            if (progressStatus === 'success' || progressStatus === 'failure' || progressStatus === 'completed') {
                console.log(`🎉 Task completion detected via progress status: ${progressStatus}`);
                this.handleTaskCompletion(statusData);
            }
        }

        // Emit custom events for status updates (replacing SocketIO events)
        if (statusData.is_running !== undefined) {
            this.dispatchCustomEvent('agent_status_update', statusData);
        }

        // Extract and emit phase updates if available
        if (statusData.progress && statusData.progress.phase_id) {
            const phaseData = {
                phase_id: statusData.progress.phase_id,
                status: statusData.progress.status || (statusData.is_running ? 'running' : 'idle'),
                message: statusData.progress.message || statusData.current_phase_message,
                progress: statusData.progress.progress,
                processed_count: statusData.progress.processed_count,
                total_count: statusData.progress.total_count
            };

            this.dispatchCustomEvent('phase_update', phaseData);
            console.log('📊 Phase update emitted:', phaseData);
        }

        // ENHANCED: Check for phase information in the main status data
        if (statusData.phase_id || statusData.current_phase_message) {
            const phaseData = {
                phase_id: statusData.phase_id || 'unknown',
                status: statusData.is_running ? 'running' : 'idle',
                message: statusData.current_phase_message,
                progress: statusData.progress_percentage || statusData.progress || 0,
                processed_count: statusData.processed_count,
                total_count: statusData.total_count
            };

            this.dispatchCustomEvent('phase_update', phaseData);
            console.log('📊 Phase update from status emitted:', phaseData);
        }

        // ENHANCED: Parse phase information from progress data structure
        if (statusData.progress) {
            const progressData = statusData.progress;
            if (progressData.phase_id || progressData.message) {
                const phaseData = {
                    phase_id: progressData.phase_id || 'processing',
                    status: progressData.status || (statusData.is_running ? 'running' : 'idle'),
                    message: progressData.message || statusData.current_phase_message || 'Processing...',
                    progress: parseInt(progressData.progress) || 0,
                    processed_count: progressData.processed_count,
                    total_count: progressData.total_count
                };

                this.dispatchCustomEvent('phase_update', phaseData);
                console.log('📊 Enhanced phase update from progress data:', phaseData);
            }
        }

        // ENHANCED: Parse Celery task meta information for phase data
        if (statusData.celery_status && statusData.celery_status.info) {
            const celeryInfo = statusData.celery_status.info;
            if (celeryInfo.phase_id || celeryInfo.message) {
                const phaseData = {
                    phase_id: celeryInfo.phase_id || 'processing',
                    status: celeryInfo.status || (statusData.is_running ? 'running' : 'idle'),
                    message: celeryInfo.message || statusData.current_phase_message || 'Processing...',
                    progress: parseInt(celeryInfo.progress) || 0,
                    processed_count: celeryInfo.processed_count,
                    total_count: celeryInfo.total_count
                };

                this.dispatchCustomEvent('phase_update', phaseData);
                console.log('📊 Phase update from Celery meta:', phaseData);
            }
        }

        // ENHANCED: Update agent status panel directly
        this.updateAgentStatusPanel(statusData);
    }

    updateAgentStatusPanel(statusData) {
        // Update the agent status text in the logs panel
        const agentStatusText = document.getElementById('agent-status-text-logs');
        const phaseProgressText = document.getElementById('phase-progress-text');
        const phaseProgressBar = document.getElementById('phase-progress-bar');
        const agentPhaseProgress = document.getElementById('agent-phase-progress');
        const agentEtcDisplay = document.getElementById('agent-etc-display');
        const agentEtcTime = document.getElementById('agent-etc-time');

        if (agentStatusText) {
            if (statusData.is_running) {
                agentStatusText.textContent = 'Running';
                agentStatusText.className = 'glass-badge glass-badge--success status-text status-running';
            } else {
                agentStatusText.textContent = 'Idle';
                agentStatusText.className = 'glass-badge glass-badge--primary status-text status-idle';
            }
        }

        // Update phase progress if we have progress data
        if (statusData.progress || statusData.current_phase_message) {
            const progressData = statusData.progress || {};
            const progress = parseInt(progressData.progress) || 0;
            const message = progressData.message || statusData.current_phase_message || 'Processing...';

            if (phaseProgressText) {
                phaseProgressText.textContent = message;
            }

            if (phaseProgressBar) {
                phaseProgressBar.style.width = `${progress}%`;
            }

            // Show progress panel if agent is running and we have meaningful progress
            if (agentPhaseProgress && statusData.is_running && (progress > 0 || message !== 'Idle')) {
                agentPhaseProgress.style.display = 'block';
            } else if (agentPhaseProgress) {
                agentPhaseProgress.style.display = 'none';
            }
        } else if (agentPhaseProgress) {
            // Hide progress panel if no progress data
            agentPhaseProgress.style.display = 'none';
        }

        // Update ETC display if available
        if (statusData.etc_seconds && agentEtcTime && agentEtcDisplay) {
            const etcMinutes = Math.ceil(statusData.etc_seconds / 60);
            agentEtcTime.textContent = `${etcMinutes}m`;
            agentEtcDisplay.style.display = 'block';
        } else if (agentEtcDisplay) {
            agentEtcDisplay.style.display = 'none';
        }

        console.log('📊 Agent status panel updated:', {
            running: statusData.is_running,
            progress: statusData.progress,
            message: statusData.current_phase_message
        });
    }

    handleLogsUpdate(logsData) {
        if (logsData.logs && logsData.logs.length > 0) {
            // Note: The /api/logs/recent endpoint returns logs in a different format
            // Each log has: {level: "INFO", message: "timestamp - level - message"}

            // Emit custom events for each log
            logsData.logs.forEach(log => {
                // Extract timestamp from the message if possible
                const timestampMatch = log.message.match(/^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})/);
                const timestamp = timestampMatch ? timestampMatch[1] : new Date().toISOString();

                // Create a normalized log format
                const normalizedLog = {
                    message: log.message,
                    level: log.level,
                    timestamp: timestamp
                };

                this.dispatchCustomEvent('log', normalizedLog);
            });
        }
    }

    handleGpuStatsUpdate(gpuData) {
        if (gpuData.gpus) {
            this.dispatchCustomEvent('gpu_stats', { gpus: gpuData.gpus });
        }
    }

    dispatchCustomEvent(eventName, data) {
        // Create custom events to replace SocketIO events
        const event = new CustomEvent(eventName, { detail: data });
        document.dispatchEvent(event);
    }

    stopPolling() {
        console.log('📊 Stopping all polling intervals...');
        Object.keys(this.pollingIntervals).forEach(name => {
            if (this.pollingIntervals[name]) {
                clearInterval(this.pollingIntervals[name]);
                delete this.pollingIntervals[name];
            }
        });
    }

    async initializeApp() {
        try {
            console.log('🚀 Initializing V2 UI with pure API polling architecture...');

            // Add necessary CSS animations if not present
            this.addRequiredStyles();

            // Set up custom event listeners for polling responses
            this.setupEventListeners();

            // Load initial system data via REST API
            await this.loadInitialData();

            // Initialize UI effects after data is loaded
            if (this.effects && typeof this.effects.initLiquidGlassEffect === 'function') {
                this.effects.initLiquidGlassEffect();
            }

            // Bridge key Socket.IO events into the same CustomEvent bus that polling uses
            if (window.socket) {
                // Legacy events
                window.socket.on('log', (data) => this.dispatchCustomEvent('log', data));
                window.socket.on('agent_status_update', (data) => this.dispatchCustomEvent('agent_status_update', data));
                window.socket.on('phase_update', (data) => this.dispatchCustomEvent('phase_update', data));
                window.socket.on('progress_update', (data) => this.dispatchCustomEvent('progress_update', data));

                // Enhanced structured events from EnhancedRealtimeManager
                window.socket.on('phase_start', (data) => this.dispatchCustomEvent('phase_start', data));
                window.socket.on('phase_complete', (data) => this.dispatchCustomEvent('phase_complete', data));
                window.socket.on('phase_error', (data) => this.dispatchCustomEvent('phase_error', data));
                window.socket.on('live_log', (data) => this.dispatchCustomEvent('live_log', data));

                // Batch events for high-volume scenarios
                window.socket.on('log_batch', (data) => {
                    if (data.events) {
                        data.events.forEach(event => this.dispatchCustomEvent('log', event));
                    }
                });
                window.socket.on('phase_update_batch', (data) => {
                    if (data.events) {
                        data.events.forEach(event => this.dispatchCustomEvent('phase_update', event));
                    }
                });

                console.log('✅ Enhanced SocketIO event listeners registered');
            }

            // Initialize the router for SPA navigation
            console.log('🧭 Initializing router...');
            this.router = new Router(this.api);
            console.log('✅ Router initialized');

            console.log('✅ V2 UI core initialized successfully');
        } catch (error) {
            console.error('❌ Failed to initialize V2 UI:', error);
            this.showErrorNotification('Failed to initialize application');
        }
    }

    addRequiredStyles() {
        // Add loading spinner animation if not already present
        if (!document.getElementById('ui-required-styles')) {
            const style = document.createElement('style');
            style.id = 'ui-required-styles';
            style.textContent = `
                @keyframes spin {
                    0% { transform: rotate(0deg); }
                    100% { transform: rotate(360deg); }
                }
                
                .loading-spinner {
                    animation: spin 1s linear infinite;
                }
                
                .error-state {
                    animation: fadeIn 0.3s ease-in;
                }
                
                @keyframes fadeIn {
                    from { opacity: 0; transform: translateY(20px); }
                    to { opacity: 1; transform: translateY(0); }
                }
                
                /* Fix log entries - remove hover effects and ensure proper scrolling */
                .log-message {
                    transition: none !important;
                    transform: none !important;
                    padding: 0.5rem;
                    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
                    font-family: var(--font-mono, monospace);
                    font-size: 0.8rem;
                    line-height: 1.4;
                    margin: 0;
                }
                
                .log-message:hover {
                    background: none !important;
                    transform: none !important;
                    scale: none !important;
                }
                
                /* Ensure logs panel has proper layout */
                .logs-panel-content {
                    height: 100% !important;
                    display: flex !important;
                    flex-direction: column !important;
                }
                
                #logs-container {
                    scroll-behavior: smooth;
                    overflow-y: auto;
                    flex: 1 !important;
                    max-height: none !important;
                    min-height: 200px;
                }
                
                #logs-container::-webkit-scrollbar {
                    width: 6px;
                }
                
                #logs-container::-webkit-scrollbar-track {
                    background: rgba(255, 255, 255, 0.05);
                    border-radius: 3px;
                }
                
                #logs-container::-webkit-scrollbar-thumb {
                    background: rgba(255, 255, 255, 0.2);
                    border-radius: 3px;
                }
                
                #logs-container::-webkit-scrollbar-thumb:hover {
                    background: rgba(255, 255, 255, 0.3);
                }
                
                /* Fixed footer styling */
                #agent-status-footer {
                    position: sticky !important;
                    bottom: 0 !important;
                    z-index: 10 !important;
                }
                
                /* Reduce spacing on dashboard panels */
                .dashboard-main-area {
                    gap: 1rem !important;
                    margin-bottom: 1rem !important;
                }
                
                .dashboard-panel {
                    padding: 1rem !important;
                }
                
                .dashboard-panel .panel-header {
                    margin-bottom: 0.75rem !important;
                    padding-bottom: 0.5rem !important;
                }
                
                .dashboard-panel .panel-content {
                    padding: 0 !important;
                }
                
                /* Reduce GPU status panel spacing */
                #gpu-status-panel {
                    padding: 1rem !important;
                    margin-bottom: 1rem !important;
                }
                
                #gpu-status-panel .panel-header {
                    margin-bottom: 0.75rem !important;
                    padding-bottom: 0.5rem !important;
                }
                
                /* Reduce agent controls panel spacing */
                #agent-controls-panel {
                    padding: 1rem !important;
                    margin-bottom: 1rem !important;
                }
                
                .agent-controls-header {
                    margin-bottom: 0.75rem !important;
                }
            `;
            document.head.appendChild(style);
        }
    }

    async loadInitialData() {
        try {
            console.log('📊 Loading initial system data...');
            
            // CRITICAL FIX: Load agent status FIRST to detect running tasks
            console.log('🔍 Checking for running agent tasks...');
            const agentStatus = await this.api.getAgentStatus().catch(e => {
                console.warn('Could not load agent status:', e.message);
                return { is_running: false, error: e.message };
            });

            if (agentStatus && !agentStatus.error) {
                console.log('✅ Agent status loaded:', agentStatus);
                
                // Dispatch initial agent status to all components
                this.dispatchCustomEvent('agent_status_update', agentStatus);
                
                // If agent is running, dispatch additional initialization events
                if (agentStatus.is_running && agentStatus.task_id) {
                    console.log('🔄 Agent is running, dispatching initialization events...');
                    
                    // Dispatch phase update if we have phase information
                    if (agentStatus.progress && agentStatus.progress.phase_id) {
                        this.dispatchCustomEvent('phase_update', {
                            phase_id: agentStatus.progress.phase_id,
                            status: agentStatus.progress.status || 'running',
                            message: agentStatus.progress.message || agentStatus.current_phase_message,
                            progress: agentStatus.progress.progress || 0,
                            processed_count: agentStatus.progress.processed_count,
                            total_count: agentStatus.progress.total_count
                        });
                    }
                    
                    // Dispatch a special initialization event for running tasks
                    this.dispatchCustomEvent('running_task_detected', {
                        task_id: agentStatus.task_id,
                        status: agentStatus
                    });
                    
                    console.log('✅ Running task initialization events dispatched');
                }
            }

            // Load basic system information via REST API
            const systemInfo = await this.api.getSystemInfo().catch(e => {
                console.warn('Could not load system info:', e.message);
                return { error: e.message };
            });

            if (systemInfo && !systemInfo.error) {
                this.updateSystemInfo(systemInfo);
            }

            console.log('📊 Initial system data loaded');
        } catch (error) {
            console.error('Failed to load initial data:', error);
        }
    }

    setupEventListeners() {
        console.log('📊 Setting up custom event listeners for polling-based updates...');

        // Listen for custom events generated by polling responses
        document.addEventListener('agent_status_update', (event) => {
            this.handleAgentStatusEvent(event.detail);
        });

        document.addEventListener('gpu_stats', (event) => {
            this.handleGpuStatsEvent(event.detail);
        });

        document.addEventListener('log', (event) => {
            this.handleLogEvent(event.detail);
        });

        // Listen for phase updates from the agent
        document.addEventListener('phase_update', (event) => {
            this.handlePhaseUpdateEvent(event.detail);
        });

        // CRITICAL FIX: Listen for running task detection to initialize all components
        document.addEventListener('running_task_detected', (event) => {
            console.log('🔄 UI Manager: Running task detected, ensuring all components are initialized');
            const taskStatus = event.detail.status;
            
            // Forward to dashboard manager if available
            if (this.dashboardManager && this.dashboardManager.managers) {
                // Initialize LiveLogsManager with running task
                if (this.dashboardManager.managers.liveLogs) {
                    this.dashboardManager.managers.liveLogs.updateAgentStatus(
                        true, 
                        taskStatus.current_phase_message || 'Running...', 
                        taskStatus
                    );
                }
                
                // Initialize other managers as needed
                if (this.dashboardManager.managers.agentControls) {
                    this.dashboardManager.managers.agentControls.updateStatus(taskStatus);
                }
            }
        });
    }

    handleTaskCompletion(statusData) {
        console.log('🎉 Handling task completion:', statusData);
        
        // Dispatch completion event to all components
        this.dispatchCustomEvent('agent_execution_completed', {
            status: statusData,
            task_id: statusData.task_id,
            final_status: statusData.status || 'completed'
        });
        
        // Try to load and display run report
        if (statusData.task_id) {
            this.loadAndDisplayRunReport(statusData.task_id);
        }
        
        // Update UI components
        if (this.dashboardManager && this.dashboardManager.managers) {
            // Update agent controls
            if (this.dashboardManager.managers.agentControls) {
                this.dashboardManager.managers.agentControls.updateStatus({
                    ...statusData,
                    is_running: false
                });
            }
            
            // Update execution plan
            if (this.dashboardManager.managers.executionPlan) {
                // Reset execution plan after a delay to show completion
                setTimeout(() => {
                    this.dashboardManager.managers.executionPlan.resetAllPhases();
                }, 3000);
            }
            
            // Update live logs
            if (this.dashboardManager.managers.liveLogs) {
                this.dashboardManager.managers.liveLogs.updateAgentStatus(
                    false, 
                    'Task completed', 
                    statusData
                );
            }
        }
        
        // Show completion notification
        this.showCompletionNotification(statusData);
    }

    async loadAndDisplayRunReport(taskId) {
        try {
            console.log(`📊 Loading run report for task: ${taskId}`);
            
            // Try to get detailed task status which should include run report
            const response = await this.api.request(`/v2/agent/status/${taskId}`);
            
            if (response && response.run_report) {
                console.log('📊 Run report found:', response.run_report);
                
                // Display run report in logs
                if (response.run_report.log_lines) {
                    response.run_report.log_lines.forEach(line => {
                        this.dispatchCustomEvent('log', {
                            message: line,
                            level: 'INFO',
                            timestamp: new Date().toISOString(),
                            task_id: taskId,
                            component: 'run_report'
                        });
                    });
                }
                
                // Dispatch run report event
                this.dispatchCustomEvent('run_report_available', {
                    task_id: taskId,
                    run_report: response.run_report
                });
            } else {
                console.log('📊 No run report found in task status');
            }
        } catch (error) {
            console.error('❌ Failed to load run report:', error);
        }
    }

    showCompletionNotification(statusData) {
        const isSuccess = statusData.status !== 'FAILURE' && statusData.status !== 'error';
        const message = isSuccess ? 
            '🎉 Agent execution completed successfully!' : 
            '❌ Agent execution completed with errors';
        
        // Try to use notification system if available
        if (this.dashboardManager && this.dashboardManager.managers.notifications) {
            this.dashboardManager.managers.notifications.show({
                type: isSuccess ? 'success' : 'error',
                title: 'Agent Execution Complete',
                message: message,
                duration: 5000
            });
        } else {
            // Fallback to console
            console.log(message);
        }
    }

    handleAgentStatusEvent(data) {
        // Update UI elements based on agent status
        console.log('📊 Agent status update:', data);
        // Forward to any components that need it
    }

    handleGpuStatsEvent(data) {
        // Update GPU stats displays
        console.log('📊 GPU stats update:', data);
        // Forward to any components that need it
    }

    handleLogEvent(data) {
        // Handle new log entries
        console.log('📊 New log entry:', data);
        // Forward to any components that need it
    }

    handlePhaseUpdateEvent(data) {
        // Handle phase update events
        console.log('📊 Phase update:', data);
        // Forward to LiveLogsManager for status display
        if (this.dashboardManager && this.dashboardManager.managers.liveLogs) {
            this.dashboardManager.managers.liveLogs.updateAgentStatus(true, data.message, data);
        }
    }

    async emitAPIEvent(eventType, data) {
        // Replace SocketIO events with direct API calls
        try {
            switch (eventType) {
                case 'start_agent':
                    // Use APIClient so base URL is already applied – only supply the v2 path.
                    return await this.api.request('/v2/agent/start', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ preferences: data })
                    });
                case 'stop_agent':
                    return await this.api.request('/v2/agent/stop', {
                        method: 'POST'
                    });
                case 'clear_logs':
                    return await this.api.request('/v2/logs/clear', {
                        method: 'POST'
                    });
                default:
                    console.warn(`⚠️ Unknown event type: ${eventType}`);
                    return { success: false, error: 'Unknown event type' };
            }
        } catch (error) {
            console.error(`❌ API event failed: ${eventType}`, error);
            return { success: false, error: error.message };
        }
    }

    updateSystemInfo(systemInfo) {
        // Update any system info displays
        const systemInfoElements = document.querySelectorAll('[data-system-info]');
        systemInfoElements.forEach(el => {
            const infoType = el.dataset.systemInfo;
            if (systemInfo[infoType] !== undefined) {
                el.textContent = systemInfo[infoType];
            }
        });
    }

    // === NOTIFICATION SYSTEM ===

    showNotification(message, type = 'info', duration = 5000) {
        const notification = document.createElement('div');
        notification.className = `notification notification--${type}`;
        notification.innerHTML = `
            <div style="display: flex; align-items: center; gap: var(--space-3);">
                <i class="fas ${this.getNotificationIcon(type)}"></i>
                <span>${message}</span>
                <button onclick="this.parentElement.parentElement.remove()" 
                        style="background: none; border: none; color: inherit; cursor: pointer; margin-left: auto;">
                    <i class="fas fa-times"></i>
                </button>
            </div>
        `;

        document.body.appendChild(notification);

        // Auto remove after duration
        setTimeout(() => {
            if (notification.parentElement) {
                notification.style.animation = 'slide-up 300ms ease-out reverse';
                setTimeout(() => notification.remove(), 300);
            }
        }, duration);
    }

    getNotificationIcon(type) {
        const icons = {
            success: 'fa-check-circle',
            warning: 'fa-exclamation-triangle',
            error: 'fa-times-circle',
            info: 'fa-info-circle'
        };
        return icons[type] || icons.info;
    }

    showSuccessNotification(message) { this.showNotification(message, 'success'); }
    showWarningNotification(message) { this.showNotification(message, 'warning'); }
    showErrorNotification(message) { this.showNotification(message, 'error'); }
    showInfoNotification(message) { this.showNotification(message, 'info'); }
}

/**
 * Router for Single Page Application navigation
 */
class Router {
    constructor(api) {
        this.api = api;
        this.currentManager = null;
        this.currentRoute = null;
        this.navigationDebounceTimeout = null;
        this.initializationPromise = null;

        this.routes = {
            'dashboard': {
                title: 'Agent Dashboard',
                endpoint: '/v2/page/index',
                manager: () => {
                    if (!window.DashboardManager) {
                        console.error('DashboardManager not available');
                        return null;
                    }
                    return new window.DashboardManager(this.api);
                }
            },
            'chat': {
                title: 'Chat Interface',
                endpoint: '/v2/page/chat',
                manager: () => window.ChatManager ? new window.ChatManager(this.api) : null
            },
            'kb': {
                title: 'Knowledge Base',
                endpoint: '/v2/page/kb',
                manager: () => window.KnowledgeBaseManager ? new window.KnowledgeBaseManager(this.api) : null
            },
            'synthesis': {
                title: 'Synthesis Documents',
                endpoint: '/v2/page/synthesis',
                manager: () => window.SynthesisManager ? new window.SynthesisManager(this.api) : (window.StaticPagesManager ? new window.StaticPagesManager('synthesis', this.api) : null)
            },
            'schedule': {
                title: 'Schedules',
                endpoint: '/v2/page/schedule',
                manager: () => window.ScheduleManager ? new window.ScheduleManager(this.api) : (window.StaticPagesManager ? new window.StaticPagesManager('schedule', this.api) : null)
            },
            'tweets': {
                title: 'Tweet Management',
                endpoint: '/v2/page/tweets',
                manager: () => {
                    console.log('🐦 Creating TweetManagementManager, available:', !!window.TweetManagementManager);
                    return window.TweetManagementManager ? new window.TweetManagementManager(this.api) : null;
                }
            }
        };

        this.init();
    }

    init() {
        // Set up navigation event listeners with proper delegation
        this.setupNavigation();

        // Handle initial route with proper initialization
        this.handleInitialRoute();
    }

    setupNavigation() {
        // Use single delegated event listener to avoid conflicts
        document.addEventListener('click', (e) => {
            // Find the closest element with data-page attribute
            const pageLink = e.target.closest('[data-page]');
            if (pageLink) {
                e.preventDefault();
                e.stopPropagation();
                const page = pageLink.getAttribute('data-page');
                console.log(`🧭 Navigation clicked: ${page}`);
                this.debouncedNavigateTo(page);
            }
        }, true); // Use capture phase to catch events early

        // Listen for hash changes
        window.addEventListener('hashchange', () => {
            console.log('🧭 Hash change detected');
            this.handleRouteChange();
        });

        // Listen for popstate (browser back/forward)
        window.addEventListener('popstate', (e) => {
            console.log('🧭 Popstate detected');
            this.handleRouteChange();
        });
    }

    debouncedNavigateTo(path) {
        // Clear any pending navigation
        if (this.navigationDebounceTimeout) {
            clearTimeout(this.navigationDebounceTimeout);
        }

        // Debounce navigation to prevent double-clicks and race conditions
        this.navigationDebounceTimeout = setTimeout(() => {
            this.navigateTo(path);
        }, 100);
    }

    handleInitialRoute() {
        // Wait for DOM to be fully ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => {
                this.performInitialNavigation();
            });
        } else {
            // DOM is already ready
            setTimeout(() => {
                this.performInitialNavigation();
            }, 100);
        }
    }

    performInitialNavigation() {
        const hash = window.location.hash.substring(1) || 'dashboard';
        console.log(`🧭 Initial navigation to: ${hash}`);
        this.navigateTo(hash);
    }

    handleRouteChange() {
        const hash = window.location.hash.substring(1) || 'dashboard';

        // Only navigate if the route actually changed
        if (hash !== this.currentRoute) {
            console.log(`🧭 Route change: ${this.currentRoute} → ${hash}`);
            this.debouncedNavigateTo(hash);
        }
    }

    async navigateTo(path) {
        // Prevent navigation to the same route
        if (path === this.currentRoute && this.currentManager) {
            console.log(`⚠️ Already on route: ${path}`);
            return;
        }

        // Prevent concurrent navigation
        if (this.initializationPromise) {
            console.log(`⚠️ Navigation to ${path} queued - waiting for current navigation to complete`);
            try {
                await this.initializationPromise;
            } catch (error) {
                console.warn('Previous navigation failed, continuing with new navigation:', error);
            }
        }

        // Create new initialization promise
        this.initializationPromise = this.performNavigation(path);

        try {
            await this.initializationPromise;
        } catch (error) {
            console.error(`Navigation to ${path} failed:`, error);
            this.showError(`Failed to load ${path}: ${error.message}`);
        } finally {
            this.initializationPromise = null;
        }
    }

    async performNavigation(path) {
        console.log(`🧭 Performing navigation to: ${path}`);

        const route = this.routes[path];
        if (!route) {
            throw new Error(`Route not found: ${path}`);
        }
        
        console.log(`🧭 Found route for ${path}:`, route);

        try {
            // Update state immediately
            this.currentRoute = path;

            // Clean up current manager
            await this.cleanupCurrentManager();

            // Update UI state
            this.updatePageState(path, route.title);

            // Load page content first
            await this.loadPageContent(route.endpoint);

            // Create and initialize new manager after content is loaded
            console.log(`🧭 Calling route.manager() for ${path}...`);
            const manager = route.manager();
            console.log(`🧭 Manager created:`, !!manager, manager);
            if (manager) {
                console.log(`🧭 Initializing manager for ${path}...`);

                // Initialize the manager
                if (typeof manager.initialize === 'function') {
                    await manager.initialize();
                }

                // Set as current manager only after successful initialization
                this.currentManager = manager;
                
                // Also set global reference for direct access (for debugging/compatibility)
                if (path === 'tweets' && manager) {
                    window.tweetManagementManager = manager;
                }
            } else {
                console.log(`⚠️ No manager available for route: ${path} (content-only page)`);
            }

            console.log(`✅ Successfully navigated to ${path}`);

        } catch (error) {
            // Reset state on error
            this.currentRoute = null;
            this.currentManager = null;
            throw error;
        }
    }

    async loadPageContent(endpoint) {
        const mainContent = document.getElementById('main-content');
        if (!mainContent) {
            throw new Error('Main content container (#main-content) not found in DOM');
        }

        console.log(`📄 Loading page content from ${endpoint}...`);

        // Show loading indicator
        mainContent.innerHTML = `
            <div class="loading-container" style="
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                height: 50vh;
                gap: var(--space-4);
            ">
                <div class="loading-spinner" style="
                    width: 48px;
                    height: 48px;
                    border: 4px solid rgba(255, 255, 255, 0.1);
                    border-top: 4px solid var(--primary-blue);
                    border-radius: 50%;
                    animation: spin 1s linear infinite;
                "></div>
                <p style="color: var(--text-secondary); margin: 0;">Loading page...</p>
            </div>
        `;

        // Create a timeout promise for the fetch request
        const timeoutPromise = new Promise((_, reject) => {
            setTimeout(() => reject(new Error('Request timeout after 10 seconds')), 10000);
        });

        // Race the fetch against the timeout
        const fetchPromise = fetch(endpoint);
        const response = await Promise.race([fetchPromise, timeoutPromise]);

        console.log(`📄 Fetch response status: ${response.status} ${response.statusText}`);

        if (!response.ok) {
            throw new Error(`Failed to load page content: ${response.status} ${response.statusText}`);
        }

        const html = await response.text();
        console.log(`📄 Page HTML loaded, length: ${html.length}`);

        // Basic validation of the HTML content
        if (!html || html.trim().length === 0) {
            throw new Error('Received empty content from server');
        }

        // Load page HTML with fade transition
        mainContent.style.opacity = '0';
        mainContent.innerHTML = html;

        // Fade in
        setTimeout(() => {
            mainContent.style.opacity = '1';
            console.log(`📄 Page content displayed with fade-in`);
        }, 100);

        console.log(`✅ Page content loaded successfully`);
    }

    async cleanupCurrentManager() {
        if (this.currentManager && typeof this.currentManager.cleanup === 'function') {
            try {
                await this.currentManager.cleanup();
                console.log('🧹 Current manager cleaned up');
            } catch (error) {
                console.warn('Error cleaning up current manager:', error);
            }
        }
        this.currentManager = null;
    }

    updatePageState(path, title) {
        // Update page title
        document.title = `KB Agent - ${title}`;

        // Update URL hash if needed
        const currentHash = window.location.hash.substring(1);
        if (currentHash !== path) {
            // Use replaceState to avoid triggering hashchange event
            history.replaceState(null, null, `#${path}`);
        }

        // Remove existing page classes from body
        document.body.classList.remove('page-dashboard', 'page-chat', 'page-kb', 'page-synthesis', 'page-schedule');

        // Add current page class to body for CSS scoping
        document.body.classList.add(`page-${path}`);

        // Update active navigation link
        this.updateActiveNavLink(path);
    }

    updateActiveNavLink(path) {
        // Remove active class from all nav links
        document.querySelectorAll('.liquid-nav-item').forEach(link => {
            link.classList.remove('active');
        });

        // Add active class to current nav link
        const activeLink = document.querySelector(`[data-page="${path}"]`);
        if (activeLink) {
            activeLink.classList.add('active');
            console.log(`🎯 Updated active nav link: ${path}`);
        }
    }

    showError(message) {
        const mainContent = document.getElementById('main-content');
        if (mainContent) {
            mainContent.innerHTML = `
                <div class="error-container" style="
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    height: 50vh;
                    gap: var(--space-4);
                    text-align: center;
                ">
                    <div class="error-icon" style="
                        width: 64px;
                        height: 64px;
                        border-radius: 50%;
                        background: var(--error-color);
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        color: white;
                        font-size: 24px;
                    ">
                        <i class="fas fa-exclamation-triangle"></i>
                    </div>
                    <h2 style="color: var(--text-primary); margin: 0;">Navigation Error</h2>
                    <p style="color: var(--text-secondary); margin: 0; max-width: 400px;">${message}</p>
                    <button onclick="window.uiManager.router.navigateTo('dashboard')" class="glass-button glass-button--primary">
                        <i class="fas fa-home"></i>
                        Return to Dashboard
                    </button>
                </div>
            `;
        }
    }

    // Method to get current route
    getCurrentRoute() {
        return this.currentRoute;
    }

    // Method to check if navigation is in progress
    isNavigating() {
        return this.initializationPromise !== null;
    }
}

// Initialize the application when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    // Initialize the main UI manager
    window.uiManager = new UIManager();

    // --- Sidebar Toggle Functionality ---
    const pageContainer = document.querySelector('.page-container');
    const sidebarToggle = document.getElementById('sidebar-toggle');

    if (sidebarToggle && pageContainer) {
        sidebarToggle.addEventListener('click', (e) => {
            e.preventDefault();
            pageContainer.classList.toggle('sidebar-collapsed');

            // Store the collapsed state in localStorage
            const isCollapsed = pageContainer.classList.contains('sidebar-collapsed');
            localStorage.setItem('sidebar-collapsed', isCollapsed);
        });

        // Restore the collapsed state from localStorage
        const wasCollapsed = localStorage.getItem('sidebar-collapsed') === 'true';
        if (wasCollapsed) {
            pageContainer.classList.add('sidebar-collapsed');
        }
    }
});

// Make all classes globally available for non-module usage
window.UIManager = UIManager;
window.APIClient = APIClient;
window.ThemeManager = ThemeManager;
window.SidebarManager = SidebarManager;
window.Router = Router;
window.DashboardManager = DashboardManager; 
/* V2 UI.JS - ENHANCED WITH DEDUPLICATION AND SMART CONNECTION MANAGEMENT */

/**
 * Dashboard Manager - Coordinates all dashboard components
 * Uses globally available manager classes (no imports needed)
 */
class DashboardManager {
    constructor(api) {
        this.api = api;
        this.managers = {};
        console.log('🎛️ DashboardManager constructor called');
    }

    async initialize() {
        console.log('🎛️ DashboardManager.initialize() called');

        try {
            // Step 1: Load dashboard content
            console.log('📄 Step 1: Loading dashboard content...');
            await this.loadDashboardContent();
            console.log('✅ Step 1: Dashboard content loaded');

            // Step 2: Check manager availability
            console.log('🔍 Step 2: Checking manager class availability...');
            const availableManagers = {
                AgentControlManager: !!window.AgentControlManager,
                ExecutionPlanManager: !!window.ExecutionPlanManager,
                LiveLogsManager: !!window.LiveLogsManager,
                GpuStatusManager: !!window.GpuStatusManager
            };
            console.log('Manager availability:', availableManagers);

            // Step 3: Initialize managers one by one with error handling
            console.log('🔧 Step 3: Initializing managers...');

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

    cleanup() {
        console.log('🧹 Cleaning up DashboardManager...');
        
        // Clean up all managers
        Object.keys(this.managers).forEach(managerKey => {
            const manager = this.managers[managerKey];
            if (manager && typeof manager.cleanup === 'function') {
                try {
                    manager.cleanup();
                    console.log(`✅ ${managerKey} cleaned up`);
                } catch (error) {
                    console.error(`❌ Error cleaning up ${managerKey}:`, error);
                }
            }
        });
        
        // Use centralized CleanupService
        if (window.CleanupService) {
            CleanupService.cleanup(this);
        }
        
        // Clear managers object after cleanup
        this.managers = {};
        
        console.log('✅ DashboardManager cleanup complete');
    }
}

/**
 * API Client for REST-first operations
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

    // Alias for backward compatibility
    async savePreferences(preferences) {
        return this.updatePreferences(preferences);
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
 * Legacy Theme Manager for dark/light mode switching (ui-fixed)
 */
class UIFixedThemeManager {
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

        // Add overlay for mobile
        if (window.innerWidth <= 768) {
            this.createOverlay();
        }

        console.log('Sidebar collapsed');
    }

    expandSidebar() {
        this.pageContainer.classList.remove('sidebar-collapsed');
        this.isCollapsed = false;

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
 * Enhanced UI Manager with smart connection management and deduplication
 */
class UIManager {
    constructor() {
        // Initialize API client for REST operations
        this.api = new APIClient();

        // Initialize event deduplication system
        this.eventDeduplicator = new EventDeduplicator({
            maxCacheSize: 1000,
            cacheTimeoutMs: 30000,
            debugMode: false // Set to true for debugging
        });

        // Initialize smart connection manager
        this.connectionManager = new SmartConnectionManager(this.api, {
            pollingInterval: 2500,
            connectionCheckInterval: 5000,
            debugMode: false // Set to true for debugging
        });

        // Initialize connection state - start with REST API, upgrade to Socket.IO when available
        this.connectionMode = 'rest'; // 'rest' or 'socketio'
        this.socketIOReady = false;
        
        // Set up Socket.IO integration when it becomes available
        this.initializeSocketIOIntegration();

        // Initialize core UI components only
        this.sidebarManager = new SidebarManager();
        this.themeManager = new UIFixedThemeManager('theme-toggle');
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

    initializeSocketIOIntegration() {
        console.log('🔌 Initializing Socket.IO integration...');
        
        // Start with REST API mode - this is our reliable baseline
        this.connectionMode = 'rest';
        this.socketIOReady = false;
        
        // Set up event listeners for when Socket.IO becomes available
        // This integrates with the layout template's Socket.IO loading
        document.addEventListener('socketio_ready', (event) => {
            console.log('✅ Socket.IO ready event received');
            this.upgradeToSocketIO();
        });
        
        // Also listen for the hyphenated version for compatibility
        document.addEventListener('socketio-ready', (event) => {
            console.log('✅ Socket.IO ready event received (hyphenated)');
            this.upgradeToSocketIO();
        });
        
        // Also check if Socket.IO is already available (in case we missed the event)
        this.checkForExistingSocketIO();
        
        // Set up periodic upgrade check (non-blocking, low frequency)
        this.setupSocketIOUpgradeCheck();
    }
    
    checkForExistingSocketIO() {
        if (window.socket && window.socket.connected) {
            console.log('✅ Socket.IO already connected - upgrading connection mode');
            this.upgradeToSocketIO();
        } else if (window.io && window.socket) {
            console.log('🔌 Socket.IO available but not connected - setting up connection handlers');
            this.setupSocketIOHandlers();
        }
    }
    
    setupSocketIOUpgradeCheck() {
        // Low-frequency check for Socket.IO availability (every 5 seconds, max 3 attempts)
        let attempts = 0;
        const maxAttempts = 3;
        
        const upgradeCheck = setInterval(() => {
            attempts++;
            
            if (this.connectionMode === 'socketio') {
                // Already upgraded, stop checking
                clearInterval(upgradeCheck);
                return;
            }
            
            if (window.socket && window.socket.connected) {
                console.log('✅ Socket.IO connection detected - upgrading');
                this.upgradeToSocketIO();
                clearInterval(upgradeCheck);
            } else if (attempts >= maxAttempts) {
                console.log('ℹ️ Socket.IO upgrade check complete - staying in REST API mode');
                clearInterval(upgradeCheck);
            }
        }, 5000);
    }
    
    setupSocketIOHandlers() {
        if (!window.socket) return;
        
        window.socket.on('connect', () => {
            console.log('✅ Socket.IO connected - upgrading connection mode');
            this.upgradeToSocketIO();
        });
        
        window.socket.on('disconnect', () => {
            console.log('⚠️ Socket.IO disconnected - falling back to REST API mode');
            this.downgradeToREST();
        });
        
        window.socket.on('reconnect', () => {
            console.log('✅ Socket.IO reconnected - upgrading connection mode');
            this.upgradeToSocketIO();
        });
    }
    
    upgradeToSocketIO() {
        if (this.connectionMode === 'socketio') return; // Already upgraded
        
        console.log('⬆️ Upgrading to Socket.IO mode');
        this.connectionMode = 'socketio';
        this.socketIOReady = true;
        
        // Set up Socket.IO handlers if not already done
        this.setupSocketIOHandlers();
        
        // Notify connection manager about the upgrade
        if (this.connectionManager && typeof this.connectionManager.upgradeToSocketIO === 'function') {
            this.connectionManager.upgradeToSocketIO();
        }
        
        // Dispatch event for other components
        document.dispatchEvent(new CustomEvent('connection_upgraded', {
            detail: { from: 'rest', to: 'socketio' }
        }));
    }
    
    downgradeToREST() {
        if (this.connectionMode === 'rest') return; // Already in REST mode
        
        console.log('⬇️ Downgrading to REST API mode');
        this.connectionMode = 'rest';
        this.socketIOReady = false;
        
        // Notify connection manager about the downgrade
        if (this.connectionManager && typeof this.connectionManager.downgradeToREST === 'function') {
            this.connectionManager.downgradeToREST();
        }
        
        // Dispatch event for other components
        document.dispatchEvent(new CustomEvent('connection_downgraded', {
            detail: { from: 'socketio', to: 'rest' }
        }));
    }

    async initializeApp() {
        try {
            console.log('🚀 Initializing V2 UI with enhanced connection management...');

            // Add necessary CSS animations if not present
            this.addRequiredStyles();

            // Set up enhanced event listeners with deduplication
            this.setupEnhancedEventListeners();
            
            // Set up navigation event listeners
            this.setupNavigationListeners();

            // Load initial system data via REST API
            await this.loadInitialData();

            // Load initial page content (dashboard)
            await this.loadPage('index');

            // Initialize UI effects after data is loaded
            if (this.effects && typeof this.effects.initLiquidGlassEffect === 'function') {
                this.effects.initLiquidGlassEffect();
            }

            console.log('✅ V2 UI initialized successfully');

        } catch (error) {
            console.error('❌ Failed to initialize V2 UI:', error);
            this.showErrorNotification('Failed to initialize application: ' + error.message);
        }
    }

    setupEnhancedEventListeners() {
        console.log('🔧 Setting up enhanced event listeners with deduplication...');

        // Set up deduplication for all event types
        const eventTypes = [
            'log', 'live_log', 'agent_status_update', 'status_update',
            'phase_update', 'phase_start', 'phase_complete', 'phase_error',
            'progress_update', 'gpu_stats', 'logs_cleared'
        ];

        eventTypes.forEach(eventType => {
            document.addEventListener(eventType, (event) => {
                const data = event.detail;
                const source = data._source || 'unknown';

                // Apply deduplication
                if (!this.eventDeduplicator.isDuplicate(eventType, data, source)) {
                    // Event is not a duplicate, process it
                    this.handleDeduplicatedEvent(eventType, data, source);
                }
            });
        });

        // Set up connection status monitoring
        document.addEventListener('connection_changed', (event) => {
            const { from, to } = event.detail;
            console.log(`🔌 Connection changed from ${from} to ${to}`);
            this.showInfoNotification(`Connection switched to ${to}`);
        });

        console.log('✅ Enhanced event listeners set up');
    }

    setupNavigationListeners() {
        console.log('🧭 Setting up navigation event listeners...');

        // Handle sidebar navigation clicks
        document.addEventListener('click', (e) => {
            const navItem = e.target.closest('.liquid-nav-item');
            if (navItem) {
                e.preventDefault();
                
                const pageName = navItem.dataset.page;
                if (pageName) {
                    // Update active state
                    document.querySelectorAll('.liquid-nav-item').forEach(item => {
                        item.classList.remove('active');
                    });
                    navItem.classList.add('active');
                    
                    // Load the page
                    this.loadPage(pageName === 'dashboard' ? 'index' : pageName);
                }
            }
        });

        console.log('✅ Navigation event listeners set up');
    }

    handleDeduplicatedEvent(eventType, data, source) {
        // Log the event for debugging
        if (eventType === 'log' || eventType === 'live_log') {
            console.log(`📝 Processing ${eventType} from ${source}:`, data.message?.substring(0, 100));
        }

        // Emit the event to the original event system for backward compatibility
        const originalEvent = new CustomEvent(eventType, { detail: data });
        document.dispatchEvent(originalEvent);
    }

    async loadInitialData() {
        try {
            console.log('📊 Loading initial system data...');

            // Load system info and preferences in parallel
            const [systemInfo, preferences] = await Promise.allSettled([
                this.api.getSystemInfo(),
                this.api.getPreferences()
            ]);

            if (systemInfo.status === 'fulfilled') {
                console.log('✅ System info loaded');
            }

            if (preferences.status === 'fulfilled') {
                console.log('✅ Preferences loaded');
            }

        } catch (error) {
            console.error('❌ Failed to load initial data:', error);
        }
    }

    addRequiredStyles() {
        // Add CSS for loading spinner if not present
        if (!document.querySelector('#loading-spinner-styles')) {
            const style = document.createElement('style');
            style.id = 'loading-spinner-styles';
            style.textContent = `
                @keyframes spin {
                    0% { transform: rotate(0deg); }
                    100% { transform: rotate(360deg); }
                }
            `;
            document.head.appendChild(style);
        }
    }

    showSuccessNotification(message) {
        console.log('✅ ' + message);
        // Could integrate with notification system if available
    }

    showErrorNotification(message) {
        console.error('❌ ' + message);
        // Could integrate with notification system if available
    }

    showInfoNotification(message) {
        console.log('ℹ️ ' + message);
        // Could integrate with notification system if available
    }

    // Router functionality
    async loadPage(pageName) {
        try {
            console.log(`📄 Loading page: ${pageName}`);

            // Clean up existing page managers when switching pages
            if (this.dashboardManager && pageName !== 'index') {
                this.dashboardManager.cleanup();
                this.dashboardManager = null;
            }
            if (this.chatManager && pageName !== 'chat') {
                this.chatManager.cleanup();
                this.chatManager = null;
            }
            if (this.knowledgeBaseManager && pageName !== 'kb') {
                this.knowledgeBaseManager.cleanup();
                this.knowledgeBaseManager = null;
            }
            if (this.synthesisManager && pageName !== 'synthesis') {
                this.synthesisManager.cleanup();
                this.synthesisManager = null;
            }
            if (this.tweetManager && pageName !== 'tweets') {
                this.tweetManager.cleanup();
                this.tweetManager = null;
            }
            if (this.scheduleManager && pageName !== 'schedule') {
                this.scheduleManager.cleanup();
                this.scheduleManager = null;
            }

            // Load page content
            const response = await fetch(`/v2/page/${pageName}`);
            if (!response.ok) {
                throw new Error(`Failed to load page: ${response.status}`);
            }

            const html = await response.text();
            const mainContent = document.getElementById('main-content');
            if (mainContent) {
                mainContent.innerHTML = html;

                // Initialize page-specific managers
                if (pageName === 'index') {
                    this.dashboardManager = new DashboardManager(this.api);
                    await this.dashboardManager.initialize();
                } else if (pageName === 'chat') {
                    // Initialize modern chat manager
                    if (window.ModernChatManager) {
                        console.log('🎯 Initializing ModernChatManager...');
                        this.chatManager = new ModernChatManager();
                        await this.chatManager.init();
                        console.log('✅ ModernChatManager initialized');
                    } else {
                        console.error('❌ ModernChatManager not available');
                    }
                } else if (pageName === 'kb') {
                    // Initialize modern knowledge base manager
                    if (window.ModernKnowledgeBaseManager) {
                        console.log('🎯 Initializing ModernKnowledgeBaseManager...');
                        this.knowledgeBaseManager = new ModernKnowledgeBaseManager();
                        await this.knowledgeBaseManager.init();
                        console.log('✅ ModernKnowledgeBaseManager initialized');
                    } else {
                        console.error('❌ ModernKnowledgeBaseManager not available');
                    }
                } else if (pageName === 'tweets') {
                    // Initialize modern tweet manager
                    if (window.ModernTweetManager) {
                        console.log('🎯 Initializing ModernTweetManager...');
                        this.tweetManager = new ModernTweetManager();
                        await this.tweetManager.init();
                        console.log('✅ ModernTweetManager initialized');
                    } else {
                        console.error('❌ ModernTweetManager not available');
                    }
                } else if (pageName === 'synthesis') {
                    // Initialize modern synthesis manager
                    if (window.ModernSynthesisManager) {
                        console.log('🎯 Initializing ModernSynthesisManager...');
                        this.synthesisManager = new ModernSynthesisManager();
                        await this.synthesisManager.init();
                        console.log('✅ ModernSynthesisManager initialized');
                    } else {
                        console.error('❌ ModernSynthesisManager not available');
                    }
                } else if (pageName === 'schedule') {
                    // Initialize modern schedule manager
                    if (window.ModernScheduleManager) {
                        console.log('🎯 Initializing ModernScheduleManager...');
                        this.scheduleManager = new ModernScheduleManager();
                        await this.scheduleManager.init();
                        console.log('✅ ModernScheduleManager initialized');
                    } else {
                        console.error('❌ ModernScheduleManager not available');
                    }
                }
            }

            console.log(`✅ Page loaded: ${pageName}`);

        } catch (error) {
            console.error(`❌ Failed to load page ${pageName}:`, error);
            this.showErrorNotification(`Failed to load page: ${error.message}`);
        }
    }

    // Cleanup method
    cleanup() {
        console.log('🧹 Cleaning up UIManager...');

        // Clean up dashboard manager and its components
        if (this.dashboardManager) {
            this.dashboardManager.cleanup();
            this.dashboardManager = null;
        }

        // Clean up page managers
        if (this.chatManager) {
            this.chatManager.cleanup();
            this.chatManager = null;
        }
        if (this.knowledgeBaseManager) {
            this.knowledgeBaseManager.cleanup();
            this.knowledgeBaseManager = null;
        }
        if (this.synthesisManager) {
            this.synthesisManager.cleanup();
            this.synthesisManager = null;
        }
        if (this.tweetManager) {
            this.tweetManager.cleanup();
            this.tweetManager = null;
        }
        if (this.scheduleManager) {
            this.scheduleManager.cleanup();
            this.scheduleManager = null;
        }

        // Handle special cleanup for connectionManager and eventDeduplicator
        if (this.connectionManager) {
            this.connectionManager.destroy();
        }

        if (this.eventDeduplicator) {
            this.eventDeduplicator.destroy();
        }
        
        // Use centralized CleanupService for comprehensive cleanup
        if (window.CleanupService) {
            CleanupService.cleanup(this, { logCleanup: false }); // We already logged above
        }

        console.log('✅ UIManager cleanup complete');
    }
}

// Initialize the application when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    console.log('🚀 DOM loaded, initializing V2 UI...');

    // Make sure required classes are available
    if (!window.EventDeduplicator) {
        console.error('❌ EventDeduplicator not available - please include eventDeduplicator.js');
        return;
    }

    if (!window.SmartConnectionManager) {
        console.error('❌ SmartConnectionManager not available - please include connectionManager.js');
        return;
    }

    // Initialize the main UI manager
    window.uiManager = new UIManager();

    // Set up page routing
    window.addEventListener('beforeunload', () => {
        if (window.uiManager) {
            window.uiManager.cleanup();
        }
    });
});

// Export for global access
window.UIManager = UIManager;
window.DashboardManager = DashboardManager;
window.APIClient = APIClient;
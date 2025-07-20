/* SIMPLIFIED UI MANAGER - CLEAN ARCHITECTURE */

/**
 * Simplified UI Manager following clean architecture principles
 * 
 * ARCHITECTURE:
 * - Load initial state via REST API on page load
 * - Use SocketIO for real-time updates only
 * - Simple fallback to polling only when SocketIO fails
 * - No complex deduplication or hybrid systems
 */

/**
 * Simple Connection Monitor - tracks SocketIO health
 */
class SimpleConnectionMonitor {
    constructor() {
        this.isConnected = false;
        this.connectionCallbacks = [];
        this.disconnectionCallbacks = [];
        
        this.init();
    }
    
    init() {
        if (!window.socket) {
            console.warn('🔌 SocketIO not available');
            return;
        }
        
        window.socket.on('connect', () => {
            this.isConnected = true;
            console.log('🔌 SocketIO connected');
            this.connectionCallbacks.forEach(callback => callback());
        });
        
        window.socket.on('disconnect', () => {
            this.isConnected = false;
            console.log('🔌 SocketIO disconnected');
            this.disconnectionCallbacks.forEach(callback => callback());
        });
        
        // Set initial state
        this.isConnected = window.socket.connected;
    }
    
    onConnect(callback) {
        this.connectionCallbacks.push(callback);
    }
    
    onDisconnect(callback) {
        this.disconnectionCallbacks.push(callback);
    }
    
    getStatus() {
        return {
            connected: this.isConnected,
            available: !!window.socket
        };
    }
}

/**
 * Dashboard Manager - Coordinates all dashboard components
 */
class SimplifiedDashboardManager {
    constructor(api) {
        this.api = api;
        this.managers = {};
        console.log('🎛️ SimplifiedDashboardManager constructor called');
    }

    async initialize() {
        console.log('🎛️ SimplifiedDashboardManager.initialize() called');
        
        try {
            // Step 1: Load dashboard content
            await this.loadDashboardContent();
            
            // Step 2: Initialize managers
            await this.initializeManagers();
            
            console.log('✅ All dashboard components initialized successfully');
            
        } catch (error) {
            console.error('❌ DashboardManager initialization failed:', error);
            this.showErrorState(error);
            throw error;
        }
    }

    async loadDashboardContent() {
        try {
            const mainContent = document.getElementById('main-content');
            if (!mainContent) {
                throw new Error('Main content container not found');
            }
            
            // Show loading
            mainContent.innerHTML = `
                <div class="loading-container">
                    <div class="loading-spinner"></div>
                    <p>Loading dashboard...</p>
                </div>
            `;
            
            // Fetch content
            const response = await fetch('/v2/page/index');
            if (!response.ok) {
                throw new Error(`Failed to load dashboard: ${response.status}`);
            }
            
            const html = await response.text();
            if (!html || html.trim().length === 0) {
                throw new Error('Received empty content from server');
            }
            
            // Display content
            mainContent.innerHTML = html;
            
            console.log('✅ Dashboard content loaded');
            
        } catch (error) {
            console.error('❌ Failed to load dashboard content:', error);
            throw error;
        }
    }

    async initializeManagers() {
        // Initialize SimplifiedLogsManager (our new clean implementation)
        if (window.SimplifiedLogsManager) {
            console.log('Initializing SimplifiedLogsManager...');
            this.managers.logs = new window.SimplifiedLogsManager(this.api);
            console.log('✅ SimplifiedLogsManager initialized');
        }
        
        // Initialize other managers if available
        if (window.AgentControlManager) {
            console.log('Initializing AgentControlManager...');
            this.managers.agentControls = new window.AgentControlManager(this.api);
            console.log('✅ AgentControlManager initialized');
        }
        
        if (window.GpuStatusManager) {
            console.log('Initializing GpuStatusManager...');
            this.managers.gpuStatus = new window.GpuStatusManager(this.api);
            console.log('✅ GpuStatusManager initialized');
        }
        
        // Initialize execution plan manager
        if (window.ExecutionPlanManager) {
            console.log('Initializing ExecutionPlanManager...');
            this.managers.executionPlan = new window.ExecutionPlanManager();
            console.log('✅ ExecutionPlanManager initialized');
        }
    }

    showErrorState(error) {
        const mainContent = document.getElementById('main-content');
        if (mainContent) {
            mainContent.innerHTML = `
                <div class="error-state">
                    <i class="fas fa-exclamation-triangle"></i>
                    <h3>Dashboard Initialization Failed</h3>
                    <p>Error: ${error.message}</p>
                    <button onclick="location.reload()" class="glass-button glass-button--primary">
                        <i class="fas fa-refresh"></i> Reload Page
                    </button>
                </div>
            `;
        }
    }

    cleanup() {
        console.log('🧹 Cleaning up Dashboard...');
        
        Object.values(this.managers).forEach(manager => {
            if (typeof manager.cleanup === 'function') {
                manager.cleanup();
            }
        });
        
        this.managers = {};
    }
}

/**
 * API Client for REST operations
 */
class SimpleAPIClient {
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

    // Agent operations
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

    // Log operations
    async getRecentLogs(limit = 200) {
        return this.request(`/logs/recent?limit=${limit}`);
    }

    async clearLogs() {
        return this.request('/v2/logs/clear', {
            method: 'POST'
        });
    }

    // System operations
    async getSystemInfo() {
        return this.request('/system/info');
    }

    async getPreferences() {
        return this.request('/preferences');
    }

    // Knowledge base operations
    async getKBItems() {
        return this.request('/items');
    }

    async getSyntheses() {
        return this.request('/syntheses');
    }
}

/**
 * Theme Manager
 */
class SimpleThemeManager {
    constructor(toggleCheckboxId) {
        this.toggleCheckbox = document.getElementById(toggleCheckboxId);
        if (!this.toggleCheckbox) return;
        this.init();
    }

    init() {
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
        
        window.dispatchEvent(new CustomEvent('themeChanged', { 
            detail: { theme: newTheme } 
        }));
    }
}

/**
 * Sidebar Manager
 */
class SimpleSidebarManager {
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

        document.addEventListener('click', (e) => {
            if (window.innerWidth <= 768 && 
                this.isCollapsed &&
                !e.target.closest('.sidebar') && 
                !e.target.closest('#sidebar-toggle')) {
                this.expandSidebar();
            }
        });

        window.addEventListener('resize', () => {
            if (window.innerWidth > 768 && this.overlay) {
                this.removeOverlay();
            }
        });

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
        
        if (window.innerWidth <= 768) {
            this.createOverlay();
        }
    }

    expandSidebar() {
        this.pageContainer.classList.remove('sidebar-collapsed');
        this.isCollapsed = false;
        this.removeOverlay();
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
 * Main Simplified UI Manager
 */
class SimplifiedUIManager {
    constructor() {
        // Initialize core components
        this.api = new SimpleAPIClient();
        this.connectionMonitor = new SimpleConnectionMonitor();
        
        // Initialize UI components
        this.sidebarManager = new SimpleSidebarManager();
        this.themeManager = new SimpleThemeManager('theme-toggle');
        this.dashboardManager = null; // Will be initialized when dashboard loads
        
        // Initialize utility manager if available
        if (window.UtilityManager) {
            this.utilityManager = new UtilityManager(this.api);
        }
        
        // Initialize UI effects if available
        if (window.UIEffects) {
            this.effects = new window.UIEffects();
        }

        this.initializeApp();
    }

    async initializeApp() {
        try {
            console.log('🚀 Initializing Simplified UI...');
            
            // Set up SocketIO connection if available
            this.setupSocketIO();
            
            // Load initial system data
            await this.loadInitialData();
            
            // Initialize UI effects
            if (this.effects && typeof this.effects.initLiquidGlassEffect === 'function') {
                this.effects.initLiquidGlassEffect();
            }
            
            console.log('✅ Simplified UI initialized successfully');
            
        } catch (error) {
            console.error('❌ Failed to initialize Simplified UI:', error);
        }
    }

    setupSocketIO() {
        if (!window.socket) {
            console.warn('SocketIO not available - using REST API only');
            return;
        }

        // Set up basic SocketIO connection
        try {
            console.log('🔌 Setting up SocketIO connection...');
            
            // Connection monitoring is handled by SimpleConnectionMonitor
            this.connectionMonitor.onConnect(() => {
                console.log('🔌 SocketIO connection established');
                this.showNotification('Real-time connection established', 'success');
            });
            
            this.connectionMonitor.onDisconnect(() => {
                console.log('🔌 SocketIO connection lost');
                this.showNotification('Connection lost - using fallback mode', 'warning');
            });
            
        } catch (error) {
            console.error('Failed to set up SocketIO:', error);
        }
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

    showNotification(message, type = 'info') {
        console.log(`${type === 'success' ? '✅' : type === 'warning' ? '⚠️' : 'ℹ️'} ${message}`);
        
        // Create simple notification
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.textContent = message;
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 12px 16px;
            background: var(--glass-bg);
            border: 1px solid var(--glass-border);
            border-radius: 8px;
            color: var(--text-primary);
            z-index: 1000;
            backdrop-filter: blur(10px);
            max-width: 300px;
        `;
        
        document.body.appendChild(notification);
        
        // Remove after 4 seconds
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 4000);
    }

    // Router functionality
    async loadPage(pageName) {
        try {
            console.log(`📄 Loading page: ${pageName}`);
            
            // Clean up existing dashboard if switching pages
            if (this.dashboardManager && pageName !== 'index') {
                this.dashboardManager.cleanup();
                this.dashboardManager = null;
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
                
                // Initialize dashboard manager for index page
                if (pageName === 'index') {
                    this.dashboardManager = new SimplifiedDashboardManager(this.api);
                    await this.dashboardManager.initialize();
                }
            }
            
            console.log(`✅ Page loaded: ${pageName}`);
            
        } catch (error) {
            console.error(`❌ Failed to load page ${pageName}:`, error);
            this.showNotification(`Failed to load page: ${error.message}`, 'error');
        }
    }

    // Get system status
    getStatus() {
        return {
            connection: this.connectionMonitor.getStatus(),
            managers: Object.keys(this.dashboardManager?.managers || {}),
            initialized: !!this.dashboardManager
        };
    }

    // Cleanup method
    cleanup() {
        console.log('🧹 Cleaning up SimplifiedUIManager...');
        
        if (this.dashboardManager) {
            this.dashboardManager.cleanup();
        }
        
        console.log('✅ SimplifiedUIManager cleanup complete');
    }
}

// Initialize the application when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    console.log('🚀 DOM loaded, initializing Simplified UI...');
    
    // Initialize the main UI manager
    window.simplifiedUIManager = new SimplifiedUIManager();
    
    // Set up page routing
    window.addEventListener('beforeunload', () => {
        if (window.simplifiedUIManager) {
            window.simplifiedUIManager.cleanup();
        }
    });
});

// Export for global access
window.SimplifiedUIManager = SimplifiedUIManager;
window.SimplifiedDashboardManager = SimplifiedDashboardManager;
window.SimpleAPIClient = SimpleAPIClient;
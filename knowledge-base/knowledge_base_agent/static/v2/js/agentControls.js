/* V2 AGENTCONTROLS.JS - COMPREHENSIVE AGENT CONTROL MANAGER */

/**
 * Agent Control Manager implementing comprehensive preference management
 * Matches the UserPreferences dataclass with all granular skip and force flags
 */
class AgentControlManager {
    constructor(api) {
        this.api = api;
        
        // UI Elements
        this.runAgentBtn = document.getElementById('run-agent-btn');
        this.stopAgentBtn = document.getElementById('stop-agent-btn');
        this.clearAllBtn = document.getElementById('clear-all-options');
        this.statusIndicator = document.getElementById('agent-status-indicator');
        this.statusText = document.getElementById('agent-status-text');
        
        // Collapsible preferences elements
        this.togglePreferencesBtn = document.getElementById('toggle-preferences-btn');
        this.preferencesSection = document.getElementById('collapsible-preferences');
        this.toggleIcon = document.getElementById('toggle-preferences-icon');
        
        // Collapsible utilities elements
        this.toggleUtilitiesBtn = document.getElementById('toggle-utilities-btn');
        this.utilitiesSection = document.getElementById('collapsible-utilities');
        this.utilitiesIcon = document.getElementById('toggle-utilities-icon');
        
        // Get all preference buttons
        this.prefButtons = document.querySelectorAll('[data-pref]');
        this.modeButtons = document.querySelectorAll('[data-mode="true"]');
        
        // State management
        this.isRunning = false;
        this.currentPreferences = null;
        this.loadingState = false;
        
        // Execution plan elements
        this.executionPlanManager = new ExecutionPlanManager();
        
        this.init();
    }

    init() {
        this.attachEventListeners();
        this.setupEventListeners();
        this.loadInitialState();
        this.initSocketListeners(); // Add this line
    }

    async loadInitialState() {
        try {
            // Load current agent status
            const status = await this.api.getAgentStatus();
            this.updateStatus(status);
            
            // Load saved preferences
            const preferences = await this.api.getPreferences();
            if (preferences) {
                this.restorePreferences(preferences);
            } else {
                // Set default state
                this.setDefaultPreferences();
            }
        } catch (error) {
            console.error('Failed to load initial state:', error);
            this.setDefaultPreferences();
        }
    }

    attachEventListeners() {
        // Main control buttons
        this.runAgentBtn?.addEventListener('click', () => this.runAgent());
        this.stopAgentBtn?.addEventListener('click', () => this.stopAgent());
        this.clearAllBtn?.addEventListener('click', () => this.clearAllOptions());
        
        // Toggle preferences button
        this.togglePreferencesBtn?.addEventListener('click', () => this.togglePreferences());
        
        // Toggle utilities button
        this.toggleUtilitiesBtn?.addEventListener('click', () => this.toggleUtilities());
        
        // Preference buttons
        this.prefButtons.forEach(button => {
            button.addEventListener('click', (e) => this.handlePrefButtonClick(e));
        });
        
        // Utility buttons
        this.attachUtilityEventListeners();
    }

    setupEventListeners() {
        // Custom event listeners for polling-based notifications
        document.addEventListener('agent_status_update', (event) => {
            this.updateStatus(event.detail);
        });

        document.addEventListener('agent_run_completed', (event) => {
            this.handleRunCompleted(event.detail);
        });

        document.addEventListener('agent_error', (event) => {
            this.handleAgentError(event.detail);
        });
    }

    initSocketListeners() {
        if (!window.socket) {
            console.error("Socket.IO not initialized. Real-time updates for agent controls are disabled.");
            return;
        }

        // This is the primary real-time listener for overall agent status
        window.socket.on('agent_status', (data) => {
            console.log('Received agent_status:', data);
            this.updateStatus(data);
        });
        
        // Optional: Listen for task ID to enable stop button immediately
        window.socket.on('agent_status_update', (data) => {
             if (data.task_id) {
                this.taskId = data.task_id;
             }
             this.updateStatus(data);
        });
    }

    handlePrefButtonClick(e) {
        if (this.isRunning) {
            this.showWarning('Cannot change preferences while agent is running');
            return;
        }

        const clickedButton = e.currentTarget;
        const isActive = clickedButton.classList.contains('active');
        const prefType = clickedButton.dataset.pref;
        const isMode = clickedButton.dataset.mode === 'true';

        // Handle exclusive run mode buttons
        if (isMode) {
            this.clearAllModes();
            clickedButton.classList.add('active'); // Always activate the clicked mode button
        } else {
            // Handle regular toggle buttons (skip/force flags)
            if (isActive) {
                clickedButton.classList.remove('active');
            } else {
                clickedButton.classList.add('active');
            }
        }

        // Handle special cases
        this.handleSpecialPreferences(prefType, clickedButton.classList.contains('active'));

        // Update UI state and notify other components
        const preferences = this.getPreferences();
        this.validatePreferences(preferences);
        
        // Update execution plan based on preferences
        this.executionPlanManager.updateExecutionPlan(preferences);
        
        const event = new CustomEvent('preferences-updated', { 
            detail: { preferences, source: 'user' } 
        });
        document.dispatchEvent(event);
    }

    clearAllModes() {
        // Clear all run mode buttons
        this.modeButtons.forEach(btn => {
            btn.classList.remove('active');
        });
    }

    handleSpecialPreferences(prefType, isActive) {
        // Handle force_reprocess_content special case - activates all granular force flags
        if (prefType === 'force_reprocess_content' && isActive) {
            const forceButtons = [
                'force-reprocess-media-btn',
                'force-reprocess-llm-btn', 
                'force-reprocess-kb-item-btn'
            ];
            
            forceButtons.forEach(btnId => {
                const btn = document.getElementById(btnId);
                if (btn) {
                    btn.classList.add('active');
                }
            });
        }
    }

    async runAgent() {
        if (this.isRunning || this.loadingState) {
            return;
        }

        try {
            this.setLoadingState(true);
            const preferences = this.getPreferences();
            
            // Validate preferences before sending
            if (!this.validatePreferences(preferences)) {
                throw new Error('Invalid preferences configuration');
            }

            console.log('🚀 Starting agent with preferences:', preferences);
            
            // Use REST API for primary operation
            const result = await this.api.startAgent(preferences);
            
            if (result.success) {
                this.currentPreferences = preferences;
                this.showSuccess(result.message || 'Agent started successfully');
                
                // Save preferences for next time
                await this.api.updatePreferences(preferences).catch(console.warn);
            } else {
                throw new Error(result.error || 'Failed to start agent');
            }
            
        } catch (error) {
            console.error('❌ Failed to start agent:', error);
            this.showError(`Failed to start agent: ${error.message}`);
        } finally {
            this.setLoadingState(false);
        }
    }

    async stopAgent() {
        if (!this.isRunning || this.loadingState) {
            return;
        }

        try {
            this.setLoadingState(true);
            console.log('🛑 Stopping agent');
            
            // Use REST API for primary operation
            const result = await this.api.stopAgent();
            
            if (result.success) {
                this.showSuccess(result.message || 'Agent stop request sent');
            } else {
                throw new Error(result.error || 'Failed to stop agent');
            }
            
        } catch (error) {
            console.error('❌ Failed to stop agent:', error);
            this.showError(`Failed to stop agent: ${error.message}`);
        } finally {
            this.setLoadingState(false);
        }
    }

    getPreferences() {
        // Determine run mode
        let runMode = "full_pipeline"; // Default
        this.modeButtons.forEach(btn => {
            if (btn.classList.contains('active')) {
                runMode = btn.dataset.pref;
            }
        });

        // Get all skip flags
        const skipFlags = {};
        const skipButtons = document.querySelectorAll('[data-pref^="skip_"]');
        skipButtons.forEach(btn => {
            const flagName = btn.dataset.pref;
            skipFlags[flagName] = btn.classList.contains('active');
        });

        // Get all force flags
        const forceFlags = {};
        const forceButtons = document.querySelectorAll('[data-pref^="force_"]');
        forceButtons.forEach(btn => {
            const flagName = btn.dataset.pref;
            forceFlags[flagName] = btn.classList.contains('active');
        });

        // Build comprehensive preferences object matching UserPreferences dataclass
        const preferences = {
            run_mode: runMode,
            
            // Skip flags
            skip_fetch_bookmarks: skipFlags.skip_fetch_bookmarks || false,
            skip_process_content: skipFlags.skip_process_content || false,
            skip_readme_generation: skipFlags.skip_readme_generation || false,
            skip_git_push: skipFlags.skip_git_push || false,
            skip_synthesis_generation: skipFlags.skip_synthesis_generation || false,
            skip_embedding_generation: skipFlags.skip_embedding_generation || false,
            
            // Force flags
            force_recache_tweets: forceFlags.force_recache_tweets || false,
            force_regenerate_synthesis: forceFlags.force_regenerate_synthesis || false,
            force_regenerate_embeddings: forceFlags.force_regenerate_embeddings || false,
            force_regenerate_readme: forceFlags.force_regenerate_readme || false,
            
            // Granular force flags for content processing phases
            force_reprocess_media: forceFlags.force_reprocess_media || false,
            force_reprocess_llm: forceFlags.force_reprocess_llm || false,
            force_reprocess_kb_item: forceFlags.force_reprocess_kb_item || false,
            
            // Legacy/combined flag
            force_reprocess_content: forceFlags.force_reprocess_content || false,
            
            // Additional options that might be configurable in the future
            synthesis_mode: "comprehensive",
            synthesis_min_items: 3,
            synthesis_max_items: 50
        };

        return preferences;
    }

    validatePreferences(preferences) {
        // Ensure exactly one run mode is selected
        const validModes = ['full_pipeline', 'fetch_only', 'synthesis_only', 'embedding_only', 'git_sync_only'];
        if (!validModes.includes(preferences.run_mode)) {
            this.showWarning('Please select a valid run mode');
            return false;
        }

        // Warn about conflicting preferences
        if (preferences.run_mode === 'synthesis_only' && preferences.skip_synthesis_generation) {
            this.showWarning('Synthesis Only mode conflicts with Skip Synthesis option');
            return false;
        }

        if (preferences.run_mode === 'embedding_only' && preferences.skip_embedding_generation) {
            this.showWarning('Embedding Only mode conflicts with Skip Embedding option');
            return false;
        }

        return true;
    }

    restorePreferences(preferences) {
        if (!preferences) return;

        console.log('Restoring preferences:', preferences);

        // Restore run mode
        this.clearAllModes();
        const modeButton = document.querySelector(`[data-pref="${preferences.run_mode}"]`);
        if (modeButton) {
            modeButton.classList.add('active');
        } else {
            // Default to full pipeline
            document.getElementById('full-pipeline-btn')?.classList.add('active');
        }

        // Restore skip flags
        Object.keys(preferences).forEach(key => {
            if (key.startsWith('skip_') && preferences[key]) {
                const btn = document.querySelector(`[data-pref="${key}"]`);
                if (btn) {
                    btn.classList.add('active');
                }
            }
        });

        // Restore force flags
        Object.keys(preferences).forEach(key => {
            if (key.startsWith('force_') && preferences[key]) {
                const btn = document.querySelector(`[data-pref="${key}"]`);
                if (btn) {
                    btn.classList.add('active');
                }
            }
        });
        
        // Update execution plan after restoring preferences
        this.executionPlanManager.updateExecutionPlan(preferences);
    }

    setDefaultPreferences() {
        // Clear all preferences and set defaults
        this.prefButtons.forEach(button => button.classList.remove('active'));
        
        // Set default run mode to full pipeline
        const fullPipelineBtn = document.getElementById('full-pipeline-btn');
        if (fullPipelineBtn) {
            fullPipelineBtn.classList.add('active');
        }
        
        // Set default skip_readme_generation to true (as per UserPreferences default)
        const skipReadmeBtn = document.getElementById('skip-readme-generation-btn');
        if (skipReadmeBtn) {
            skipReadmeBtn.classList.add('active');
        }
        
        // Update execution plan with default preferences
        const defaultPreferences = this.getPreferences();
        this.executionPlanManager.updateExecutionPlan(defaultPreferences);
    }

    clearAllOptions() {
        if (this.isRunning) {
            this.showWarning('Cannot change preferences while agent is running');
            return;
        }

        // Clear all preference buttons
        this.prefButtons.forEach(button => button.classList.remove('active'));
        
        // Set defaults
        this.setDefaultPreferences();

        const preferences = this.getPreferences();
        
        // Update execution plan
        this.executionPlanManager.updateExecutionPlan(preferences);
        
        const event = new CustomEvent('preferences-updated', { 
            detail: { preferences, source: 'clear' } 
        });
        document.dispatchEvent(event);
        
        this.showInfo('All preferences cleared and reset to defaults');
    }

    togglePreferences() {
        const isCollapsed = this.preferencesSection?.classList.contains('collapsed');
        
        if (isCollapsed) {
            // Expand
            this.preferencesSection.classList.remove('collapsed');
            this.toggleIcon?.classList.add('rotated');
        } else {
            // Collapse
            this.preferencesSection?.classList.add('collapsed');
            this.toggleIcon?.classList.remove('rotated');
        }
        
        console.log(`🔽 Preferences ${isCollapsed ? 'expanded' : 'collapsed'}`);
    }

    updateStatus(status) {
        if (!status) return;

        const wasRunning = this.isRunning;
        this.isRunning = status.is_running || false;

        // Update status text and indicator
        if (this.statusText) {
            this.statusText.textContent = status.current_phase_message || 'Idle';
        }

        // Update button states when status changes
        if (wasRunning !== this.isRunning) {
            this.updateButtonStates(this.isRunning);
        }

        this.updateStatusIndicator(status);
    }

    updateButtonStates(isRunning) {
        if (this.runAgentBtn) {
            this.runAgentBtn.style.display = isRunning ? 'none' : 'inline-flex';
        }
        
        if (this.stopAgentBtn) {
            this.stopAgentBtn.style.display = isRunning ? 'inline-flex' : 'none';
        }

        // Disable preference buttons while running
        this.prefButtons.forEach(button => {
            if (button !== this.runAgentBtn && button !== this.stopAgentBtn) {
                button.disabled = isRunning;
                if (isRunning) {
                    button.style.opacity = '0.5';
                    button.style.cursor = 'not-allowed';
                } else {
                    button.style.opacity = '';
                    button.style.cursor = '';
                }
            }
        });
    }

    updateStatusIndicator(status) {
        if (!this.statusIndicator) return;

        // Remove all status classes
        this.statusIndicator.classList.remove('status-indicator--online', 'status-indicator--offline', 'status-indicator--warning', 'status-indicator--error');

        if (status.is_running) {
            this.statusIndicator.classList.add('status-indicator--online');
        } else if (status.stop_flag_status) {
            this.statusIndicator.classList.add('status-indicator--warning');
        } else {
            this.statusIndicator.classList.add('status-indicator--offline');
        }
    }

    setLoadingState(loading) {
        this.loadingState = loading;
        
        if (this.runAgentBtn) {
            this.runAgentBtn.disabled = loading;
            if (loading) {
                this.runAgentBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Starting...';
            } else {
                this.runAgentBtn.innerHTML = '<i class="fas fa-play"></i> Run Agent';
            }
        }
        
        if (this.stopAgentBtn) {
            this.stopAgentBtn.disabled = loading;
            if (loading) {
                this.stopAgentBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Stopping...';
            } else {
                this.stopAgentBtn.innerHTML = '<i class="fas fa-stop"></i> Stop Agent';
            }
        }
    }

    handleRunCompleted(data) {
        this.showSuccess('Agent run completed successfully');
    }

    handleAgentError(data) {
        this.showError(`Agent error: ${data.message || 'Unknown error'}`);
    }

    onPreferencesChanged(preferences) {
        // Handle external preference changes
        this.restorePreferences(preferences);
    }

    showSuccess(message) {
        this.showNotification(message, 'success');
    }

    showError(message) {
        this.showNotification(message, 'error');
    }

    showWarning(message) {
        this.showNotification(message, 'warning');
    }

    showInfo(message) {
        this.showNotification(message, 'info');
    }

    showNotification(message, type) {
        console.log(`[${type.toUpperCase()}] ${message}`);
        // You can implement actual notification UI here if needed
    }

    // === UTILITY DROPDOWN FUNCTIONALITY ===

    toggleUtilities() {
        const isCollapsed = this.utilitiesSection?.classList.contains('collapsed');
        
        if (isCollapsed) {
            // Expand
            this.utilitiesSection.classList.remove('collapsed');
            this.utilitiesIcon?.classList.add('rotated');
        } else {
            // Collapse
            this.utilitiesSection?.classList.add('collapsed');
            this.utilitiesIcon?.classList.remove('rotated');
        }
        
        console.log(`🔧 Utilities ${isCollapsed ? 'expanded' : 'collapsed'}`);
    }

    attachUtilityEventListeners() {
        // Celery Management
        document.getElementById('clear-celery-queue-btn')?.addEventListener('click', () => this.clearCeleryQueue());
        document.getElementById('purge-celery-tasks-btn')?.addEventListener('click', () => this.purgeCeleryTasks());
        document.getElementById('restart-celery-workers-btn')?.addEventListener('click', () => this.restartCeleryWorkers());
        document.getElementById('celery-status-btn')?.addEventListener('click', () => this.getCeleryStatus());

        // System Utilities
        document.getElementById('clear-redis-cache-btn')?.addEventListener('click', () => this.clearRedisCache());
        document.getElementById('cleanup-temp-files-btn')?.addEventListener('click', () => this.cleanupTempFiles());
        document.getElementById('system-health-check-btn')?.addEventListener('click', () => this.systemHealthCheck());

        // Debug Tools
        document.getElementById('export-logs-btn')?.addEventListener('click', () => this.exportLogs());
        document.getElementById('test-connections-btn')?.addEventListener('click', () => this.testConnections());
        document.getElementById('debug-info-btn')?.addEventListener('click', () => this.getDebugInfo());
    }

    // === CELERY MANAGEMENT UTILITIES ===

    async clearCeleryQueue() {
        if (!confirm('Are you sure you want to clear the Celery task queue? This will remove all pending tasks.')) {
            return;
        }

        try {
            this.showInfo('Clearing Celery task queue...');
            const result = await this.api.request('/utilities/celery/clear-queue', { method: 'POST' });
            
            if (result.success) {
                this.showSuccess(`Queue cleared: ${result.message}`);
            } else {
                throw new Error(result.error || 'Failed to clear queue');
            }
        } catch (error) {
            console.error('Failed to clear Celery queue:', error);
            this.showError(`Failed to clear queue: ${error.message}`);
        }
    }

    async purgeCeleryTasks() {
        if (!confirm('Are you sure you want to purge ALL Celery tasks? This will remove all pending, active, and reserved tasks. This action cannot be undone.')) {
            return;
        }

        try {
            this.showInfo('Purging all Celery tasks...');
            const result = await this.api.request('/utilities/celery/purge-all', { method: 'POST' });
            
            if (result.success) {
                this.showSuccess(`Tasks purged: ${result.message}`);
            } else {
                throw new Error(result.error || 'Failed to purge tasks');
            }
        } catch (error) {
            console.error('Failed to purge Celery tasks:', error);
            this.showError(`Failed to purge tasks: ${error.message}`);
        }
    }

    async restartCeleryWorkers() {
        if (!confirm('Are you sure you want to restart Celery workers? This will interrupt any running tasks.')) {
            return;
        }

        try {
            this.showInfo('Restarting Celery workers...');
            const result = await this.api.request('/utilities/celery/restart-workers', { method: 'POST' });
            
            if (result.success) {
                this.showSuccess(`Workers restarted: ${result.message}`);
            } else {
                throw new Error(result.error || 'Failed to restart workers');
            }
        } catch (error) {
            console.error('Failed to restart Celery workers:', error);
            this.showError(`Failed to restart workers: ${error.message}`);
        }
    }

    async getCeleryStatus() {
        try {
            this.showInfo('Getting Celery worker status...');
            const result = await this.api.request('/utilities/celery/status');
            
            if (result.success) {
                const status = result.data;
                let message = `Workers: ${status.active_workers || 0} active, ${status.total_workers || 0} total\n`;
                message += `Tasks: ${status.active_tasks || 0} active, ${status.pending_tasks || 0} pending`;
                
                alert(`Celery Status:\n\n${message}`);
                this.showSuccess('Celery status retrieved');
            } else {
                throw new Error(result.error || 'Failed to get status');
            }
        } catch (error) {
            console.error('Failed to get Celery status:', error);
            this.showError(`Failed to get status: ${error.message}`);
        }
    }

    // === SYSTEM UTILITIES ===

    async clearRedisCache() {
        if (!confirm('Are you sure you want to clear the Redis cache? This will remove all cached data.')) {
            return;
        }

        try {
            this.showInfo('Clearing Redis cache...');
            const result = await this.api.request('/utilities/system/clear-redis', { method: 'POST' });
            
            if (result.success) {
                this.showSuccess(`Redis cache cleared: ${result.message}`);
            } else {
                throw new Error(result.error || 'Failed to clear cache');
            }
        } catch (error) {
            console.error('Failed to clear Redis cache:', error);
            this.showError(`Failed to clear cache: ${error.message}`);
        }
    }

    async cleanupTempFiles() {
        if (!confirm('Are you sure you want to cleanup temporary files? This will remove temporary processing files.')) {
            return;
        }

        try {
            this.showInfo('Cleaning up temporary files...');
            const result = await this.api.request('/utilities/system/cleanup-temp', { method: 'POST' });
            
            if (result.success) {
                this.showSuccess(`Cleanup completed: ${result.message}`);
            } else {
                throw new Error(result.error || 'Failed to cleanup files');
            }
        } catch (error) {
            console.error('Failed to cleanup temp files:', error);
            this.showError(`Failed to cleanup: ${error.message}`);
        }
    }

    async systemHealthCheck() {
        try {
            this.showInfo('Running system health check...');
            const result = await this.api.request('/utilities/system/health-check');
            
            if (result.success) {
                const health = result.data;
                let message = `System Health Check:\n\n`;
                message += `Redis: ${health.redis ? '✅ Connected' : '❌ Disconnected'}\n`;
                message += `Database: ${health.database ? '✅ Connected' : '❌ Disconnected'}\n`;
                message += `Celery: ${health.celery ? '✅ Running' : '❌ Not Running'}\n`;
                message += `Disk Space: ${health.disk_space || 'Unknown'}\n`;
                message += `Memory Usage: ${health.memory_usage || 'Unknown'}`;
                
                alert(message);
                this.showSuccess('Health check completed');
            } else {
                throw new Error(result.error || 'Failed to run health check');
            }
        } catch (error) {
            console.error('Failed to run health check:', error);
            this.showError(`Health check failed: ${error.message}`);
        }
    }

    // === DEBUG TOOLS ===

    async exportLogs() {
        try {
            this.showInfo('Exporting logs...');
            const result = await this.api.request('/utilities/debug/export-logs');
            
            if (result.success) {
                // Create download link
                const blob = new Blob([result.data], { type: 'text/plain' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `knowledge-base-logs-${new Date().toISOString().split('T')[0]}.txt`;
                a.click();
                URL.revokeObjectURL(url);
                
                this.showSuccess('Logs exported successfully');
            } else {
                throw new Error(result.error || 'Failed to export logs');
            }
        } catch (error) {
            console.error('Failed to export logs:', error);
            this.showError(`Failed to export logs: ${error.message}`);
        }
    }

    async testConnections() {
        try {
            this.showInfo('Testing connections...');
            const result = await this.api.request('/utilities/debug/test-connections');
            
            if (result.success) {
                const tests = result.data;
                let message = `Connection Tests:\n\n`;
                
                Object.entries(tests).forEach(([service, status]) => {
                    message += `${service}: ${status.connected ? '✅ Connected' : '❌ Failed'}\n`;
                    if (status.error) {
                        message += `  Error: ${status.error}\n`;
                    }
                });
                
                alert(message);
                this.showSuccess('Connection tests completed');
            } else {
                throw new Error(result.error || 'Failed to test connections');
            }
        } catch (error) {
            console.error('Failed to test connections:', error);
            this.showError(`Connection tests failed: ${error.message}`);
        }
    }

    async getDebugInfo() {
        try {
            this.showInfo('Gathering debug information...');
            const result = await this.api.request('/utilities/debug/info');
            
            if (result.success) {
                const info = result.data;
                let message = `Debug Information:\n\n`;
                message += `Version: ${info.version || 'Unknown'}\n`;
                message += `Python: ${info.python_version || 'Unknown'}\n`;
                message += `Platform: ${info.platform || 'Unknown'}\n`;
                message += `Uptime: ${info.uptime || 'Unknown'}\n`;
                message += `Active Tasks: ${info.active_tasks || 0}\n`;
                message += `Memory Usage: ${info.memory_usage || 'Unknown'}\n`;
                message += `CPU Usage: ${info.cpu_usage || 'Unknown'}`;
                
                alert(message);
                this.showSuccess('Debug info retrieved');
            } else {
                throw new Error(result.error || 'Failed to get debug info');
            }
        } catch (error) {
            console.error('Failed to get debug info:', error);
            this.showError(`Failed to get debug info: ${error.message}`);
        }
    }
}

// Duplicate ExecutionPlanManager definition removed – the real class lives in
// static/v2/js/executionPlan.js. 

// Make globally available for non-module usage
window.AgentControlManager = AgentControlManager;
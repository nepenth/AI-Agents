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
        
        // Preference buttons
        this.prefButtons.forEach(button => {
            button.addEventListener('click', (e) => this.handlePrefButtonClick(e));
        });
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
}

// Duplicate ExecutionPlanManager definition removed – the real class lives in
// static/v2/js/executionPlan.js. 

// Make globally available for non-module usage
window.AgentControlManager = AgentControlManager;
/* V2 HISTORICALTASKS.JS - HISTORICAL TASK VIEWING AND MANAGEMENT */

/**
 * HistoricalTasksManager - Manages viewing and interaction with completed tasks
 * 
 * FEATURES:
 * - Loads recent completed tasks from API
 * - Displays task history in dropdown
 * - Shows historical task logs in Live Logs
 * - Disables agent controls when viewing historical tasks
 * - Provides task details and execution reports
 */
class HistoricalTasksManager {
    constructor(api) {
        this.api = api;
        
        // UI Elements
        this.toggleCompletedTasksBtn = document.getElementById('toggle-completed-tasks-btn');
        this.completedTasksSection = document.getElementById('collapsible-completed-tasks');
        this.completedTasksList = document.getElementById('completed-tasks-list');
        this.toggleIcon = document.getElementById('toggle-completed-tasks-icon');
        
        // State
        this.isCollapsed = true;
        this.completedTasks = [];
        this.selectedHistoricalTask = null;
        this.isViewingHistoricalTask = false;
        
        // References to other managers
        this.liveLogsManager = null;
        this.agentControlManager = null;
        this.simplifiedLogsManager = null;
        
        this.init();
    }
    
    init() {
        this.setupEventListeners();
        this.loadCompletedTasks();
        
        // Register with component coordinator
        if (window.displayCoordinator) {
            window.displayCoordinator.registerComponent('HistoricalTasksManager', this, {
                priority: 70,
                dependencies: ['LiveLogsManager', 'AgentControlManager']
            });
        }
        
        console.log('📚 HistoricalTasksManager initialized');
    }
    
    setupEventListeners() {
        // Collapsible toggle
        if (this.toggleCompletedTasksBtn) {
            this.toggleCompletedTasksBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.toggleCollapsible();
            });
        }
        
        // Listen for new task completions to refresh the list
        document.addEventListener('task_completed', () => {
            this.loadCompletedTasks();
        });
        
        // Listen for agent status updates
        document.addEventListener('agent_status_update', (event) => {
            // If agent starts running while viewing historical task, exit historical view
            if (event.detail.is_running && this.isViewingHistoricalTask) {
                this.exitHistoricalView();
            }
        });
    }
    
    async loadCompletedTasks() {
        try {
            // FIX: Use correct API method - the APIClient doesn't have a .get() method
            const response = await this.api.request('/v2/agent/history?limit=5');
            
            if (response.success) {
                this.completedTasks = response.tasks;
                this.renderTaskList();
            } else {
                console.error('Failed to load completed tasks:', response.error);
                this.renderError('Failed to load completed tasks: ' + (response.error || 'Unknown error'));
            }
        } catch (error) {
            console.error('Error loading completed tasks:', error);
            this.renderError('Error loading completed tasks: ' + error.message);
        }
    }
    
    renderTaskList() {
        if (!this.completedTasksList) return;
        
        if (this.completedTasks.length === 0) {
            this.completedTasksList.innerHTML = `
                <div class="no-tasks" style="text-align: center; padding: var(--space-4); color: var(--text-secondary);">
                    <i class="fas fa-inbox" style="font-size: 2em; margin-bottom: var(--space-2); opacity: 0.5;"></i>
                    <p>No completed tasks found</p>
                    <small>Run an agent task to see it appear here</small>
                </div>
            `;
            return;
        }
        
        const tasksHtml = this.completedTasks.map(task => {
            const statusIcon = task.status === 'SUCCESS' ? 
                '<i class="fas fa-check-circle" style="color: var(--success-color);"></i>' :
                '<i class="fas fa-exclamation-circle" style="color: var(--error-color);"></i>';
            
            const completedDate = new Date(task.completed_at).toLocaleString();
            
            return `
                <div class="task-item" data-task-id="${task.task_id}" 
                     style="padding: var(--space-3); border: 1px solid var(--glass-border-secondary); 
                            border-radius: var(--radius-sm); margin-bottom: var(--space-2); 
                            cursor: pointer; transition: all 0.2s ease;">
                    <div style="display: flex; justify-content: between; align-items: flex-start; gap: var(--space-2);">
                        <div style="flex: 1;">
                            <div style="display: flex; align-items: center; gap: var(--space-2); margin-bottom: var(--space-1);">
                                ${statusIcon}
                                <strong style="color: var(--text-primary); font-size: var(--font-size-sm);">
                                    ${task.human_readable_name}
                                </strong>
                            </div>
                            <div style="font-size: var(--font-size-xs); color: var(--text-secondary); margin-bottom: var(--space-1);">
                                Completed: ${completedDate}
                            </div>
                            <div style="display: flex; gap: var(--space-3); font-size: var(--font-size-xs); color: var(--text-tertiary);">
                                <span><i class="fas fa-clock"></i> ${task.duration}</span>
                                <span><i class="fas fa-list"></i> ${task.processed_count} items</span>
                                ${task.error_count > 0 ? `<span><i class="fas fa-exclamation-triangle"></i> ${task.error_count} errors</span>` : ''}
                            </div>
                        </div>
                        <div style="display: flex; flex-direction: column; align-items: center; gap: var(--space-1);">
                            <button class="view-task-btn liquid-button liquid-button--sm liquid-button--primary" 
                                    data-task-id="${task.task_id}" style="font-size: var(--font-size-xs);">
                                <i class="fas fa-eye"></i> View
                            </button>
                        </div>
                    </div>
                </div>
            `;
        }).join('');
        
        this.completedTasksList.innerHTML = tasksHtml;
        
        // Add event listeners to task items and view buttons
        this.completedTasksList.querySelectorAll('.task-item').forEach(item => {
            item.addEventListener('mouseenter', () => {
                item.style.backgroundColor = 'var(--glass-bg-secondary)';
                item.style.borderColor = 'var(--glass-border-primary)';
            });
            
            item.addEventListener('mouseleave', () => {
                item.style.backgroundColor = 'transparent';
                item.style.borderColor = 'var(--glass-border-secondary)';
            });
        });
        
        this.completedTasksList.querySelectorAll('.view-task-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const taskId = btn.getAttribute('data-task-id');
                this.viewHistoricalTask(taskId);
            });
        });
    }
    
    renderError(message) {
        if (!this.completedTasksList) return;
        
        this.completedTasksList.innerHTML = `
            <div class="error-state" style="text-align: center; padding: var(--space-4); color: var(--error-color);">
                <i class="fas fa-exclamation-triangle" style="font-size: 2em; margin-bottom: var(--space-2);"></i>
                <p>${message}</p>
                <button class="retry-btn liquid-button liquid-button--sm liquid-button--secondary" 
                        style="margin-top: var(--space-2);">
                    <i class="fas fa-redo"></i> Retry
                </button>
            </div>
        `;
        
        // Add retry functionality
        const retryBtn = this.completedTasksList.querySelector('.retry-btn');
        if (retryBtn) {
            retryBtn.addEventListener('click', () => {
                this.loadCompletedTasks();
            });
        }
    }
    
    toggleCollapsible() {
        if (this.isCollapsed) {
            this.expandCollapsible();
        } else {
            this.collapseCollapsible();
        }
    }
    
    expandCollapsible() {
        if (!this.completedTasksSection) return;
        
        this.completedTasksSection.classList.remove('collapsed');
        this.completedTasksSection.style.maxHeight = this.completedTasksSection.scrollHeight + 'px';
        this.isCollapsed = false;
        
        // Rotate icon
        if (this.toggleIcon) {
            this.toggleIcon.style.transform = 'rotate(180deg)';
        }
        
        // Refresh task list when expanding
        this.loadCompletedTasks();
    }
    
    collapseCollapsible() {
        if (!this.completedTasksSection) return;
        
        this.completedTasksSection.classList.add('collapsed');
        this.completedTasksSection.style.maxHeight = '0px';
        this.isCollapsed = true;
        
        // Reset icon rotation
        if (this.toggleIcon) {
            this.toggleIcon.style.transform = 'rotate(0deg)';
        }
    }
    
    async viewHistoricalTask(taskId) {
        try {
            // Collapse the section
            this.collapseCollapsible();
            
            // Load detailed task information
            const response = await this.api.request(`/v2/agent/history/${taskId}`);
            
            if (!response.success) {
                throw new Error(response.error || 'Failed to load task details');
            }
            
            const taskDetails = response.task;
            this.selectedHistoricalTask = taskDetails;
            this.isViewingHistoricalTask = true;
            
            // Disable agent controls
            this.disableAgentControls();
            
            // Show historical task in Live Logs
            this.displayHistoricalTaskInLogs(taskDetails);
            
            // Update UI to show we're in historical view mode
            this.showHistoricalViewIndicator(taskDetails);
            
        } catch (error) {
            console.error('Error viewing historical task:', error);
            this.showNotification('Error loading historical task: ' + error.message, 'error');
        }
    }
    
    async displayHistoricalTaskInLogs(taskDetails) {
        // Get reference to Simplified Logs Manager (PostgreSQL-enabled)
        if (!this.simplifiedLogsManager) {
            this.simplifiedLogsManager = window.simplifiedLogsManager || 
                                        (window.displayCoordinator && window.displayCoordinator.getComponent('SimplifiedLogsManager'));
        }
        
        if (!this.simplifiedLogsManager) {
            console.error('SimplifiedLogsManager not available');
            return;
        }
        
        try {
            // Load historical logs from PostgreSQL
            console.log(`📚 Loading historical logs for task: ${taskDetails.task_id}`);
            const success = await this.simplifiedLogsManager.loadHistoricalLogs(taskDetails.task_id);
            
            if (success) {
                console.log('✅ Historical logs loaded successfully');
                
                // Add a header to indicate historical view
                this.addHistoricalViewHeader(taskDetails);
                
            } else {
                console.warn('⚠️ No PostgreSQL logs found, falling back to legacy logs');
                
                // Fallback to legacy log display if PostgreSQL logs not available
                this.displayLegacyHistoricalLogs(taskDetails);
            }
            
        } catch (error) {
            console.error('❌ Error loading historical logs:', error);
            
            // Fallback to legacy log display
            this.displayLegacyHistoricalLogs(taskDetails);
        }
    }

    addHistoricalViewHeader(taskDetails) {
        // Add header information to the logs display
        const logsContainer = document.getElementById('logs-container');
        if (logsContainer) {
            const headerElement = document.createElement('div');
            headerElement.className = 'historical-logs-header';
            headerElement.style.cssText = `
                background: var(--glass-bg-secondary);
                border: 1px solid var(--glass-border-primary);
                border-radius: var(--radius-md);
                padding: var(--space-3);
                margin-bottom: var(--space-3);
                font-size: var(--font-size-sm);
            `;
            
            headerElement.innerHTML = `
                <div style="display: flex; align-items: center; gap: var(--space-2); margin-bottom: var(--space-2);">
                    <i class="fas fa-history" style="color: var(--primary-color);"></i>
                    <strong style="color: var(--text-primary);">Historical Task View</strong>
                </div>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: var(--space-2); font-size: var(--font-size-xs); color: var(--text-secondary);">
                    <div><strong>Task:</strong> ${taskDetails.human_readable_name}</div>
                    <div><strong>Status:</strong> ${taskDetails.status}</div>
                    <div><strong>Duration:</strong> ${taskDetails.duration}</div>
                    <div><strong>Completed:</strong> ${new Date(taskDetails.completed_at).toLocaleString()}</div>
                </div>
            `;
            
            // Insert at the top of logs container
            logsContainer.insertBefore(headerElement, logsContainer.firstChild);
        }
    }

    displayLegacyHistoricalLogs(taskDetails) {
        // Fallback method for when PostgreSQL logs are not available
        console.log('📋 Using legacy log display method');
        
        // Get reference to Live Logs Manager as fallback
        if (!this.liveLogsManager) {
            this.liveLogsManager = window.liveLogsManager || 
                                   (window.displayCoordinator && window.displayCoordinator.getComponent('LiveLogsManager'));
        }
        
        if (!this.liveLogsManager) {
            console.error('No log manager available');
            return;
        }
        
        // Clear current logs
        this.liveLogsManager.clearLogs();
        
        // Add historical task header
        this.liveLogsManager.addLogEntry({
            level: 'INFO',
            message: '📚 HISTORICAL TASK VIEW (Legacy Mode)',
            timestamp: new Date().toISOString(),
            module: 'HistoricalTasksManager'
        });
        
        this.liveLogsManager.addLogEntry({
            level: 'INFO',
            message: `Task: ${taskDetails.human_readable_name}`,
            timestamp: new Date().toISOString(),
            module: 'HistoricalTasksManager'
        });
        
        this.liveLogsManager.addLogEntry({
            level: 'INFO',
            message: `Status: ${taskDetails.status} | Duration: ${taskDetails.duration}`,
            timestamp: new Date().toISOString(),
            module: 'HistoricalTasksManager'
        });
        
        this.liveLogsManager.addLogEntry({
            level: 'INFO',
            message: '='.repeat(80),
            timestamp: new Date().toISOString(),
            module: 'HistoricalTasksManager'
        });
        
        // Display run report if available
        if (taskDetails.run_report && taskDetails.run_report.log_lines) {
            taskDetails.run_report.log_lines.forEach(line => {
                this.liveLogsManager.addLogEntry({
                    level: 'INFO',
                    message: line,
                    timestamp: new Date().toISOString(),
                    module: 'TaskReport'
                });
            });
        }
        
        // Display historical logs if available
        if (taskDetails.logs && taskDetails.logs.length > 0) {
            this.liveLogsManager.addLogEntry({
                level: 'INFO',
                message: '📋 ORIGINAL TASK EXECUTION LOGS:',
                timestamp: new Date().toISOString(),
                module: 'HistoricalTasksManager'
            });
            
            taskDetails.logs.forEach(logEntry => {
                this.liveLogsManager.addLogEntry({
                    level: logEntry.level || 'INFO',
                    message: logEntry.message,
                    timestamp: logEntry.timestamp,
                    module: logEntry.module || 'Agent'
                });
            });
        }
        
        // Add footer
        this.liveLogsManager.addLogEntry({
            level: 'INFO',
            message: '='.repeat(80),
            timestamp: new Date().toISOString(),
            module: 'HistoricalTasksManager'
        });
        
        this.liveLogsManager.addLogEntry({
            level: 'INFO',
            message: '📚 End of historical task view. Click "Exit Historical View" to return to live mode.',
            timestamp: new Date().toISOString(),
            module: 'HistoricalTasksManager'
        });
    }
    
    showHistoricalViewIndicator(taskDetails) {
        // Create or update historical view indicator
        let indicator = document.getElementById('historical-view-indicator');
        
        if (!indicator) {
            indicator = document.createElement('div');
            indicator.id = 'historical-view-indicator';
            indicator.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                z-index: 1001;
                background: var(--warning-color);
                color: white;
                padding: var(--space-3);
                border-radius: var(--radius-md);
                box-shadow: var(--shadow-lg);
                display: flex;
                align-items: center;
                gap: var(--space-2);
                font-size: var(--font-size-sm);
                font-weight: 600;
            `;
            
            document.body.appendChild(indicator);
        }
        
        indicator.innerHTML = `
            <i class="fas fa-history"></i>
            <span>Viewing: ${taskDetails.human_readable_name}</span>
            <button id="exit-historical-view-btn" style="
                background: rgba(255,255,255,0.2);
                border: none;
                color: white;
                padding: var(--space-1) var(--space-2);
                border-radius: var(--radius-sm);
                cursor: pointer;
                font-size: var(--font-size-xs);
            ">
                <i class="fas fa-times"></i> Exit
            </button>
        `;
        
        // Add exit functionality
        const exitBtn = document.getElementById('exit-historical-view-btn');
        if (exitBtn) {
            exitBtn.addEventListener('click', () => {
                this.exitHistoricalView();
            });
        }
    }
    
    disableAgentControls() {
        // Get reference to Agent Control Manager
        if (!this.agentControlManager) {
            this.agentControlManager = window.agentControlManager || 
                                      (window.displayCoordinator && window.displayCoordinator.getComponent('AgentControlManager'));
        }
        
        // Disable agent control buttons
        const controlButtons = document.querySelectorAll('#run-agent-btn, #stop-agent-btn, #clear-all-options, [data-pref], [data-mode]');
        controlButtons.forEach(btn => {
            btn.disabled = true;
            btn.style.opacity = '0.5';
            btn.style.cursor = 'not-allowed';
        });
        
        // Add disabled state message
        const agentControlPanel = document.getElementById('agent-control-panel');
        if (agentControlPanel) {
            let disabledMessage = document.getElementById('historical-view-disabled-message');
            if (!disabledMessage) {
                disabledMessage = document.createElement('div');
                disabledMessage.id = 'historical-view-disabled-message';
                disabledMessage.style.cssText = `
                    background: var(--warning-bg);
                    border: 1px solid var(--warning-color);
                    color: var(--warning-text);
                    padding: var(--space-2);
                    border-radius: var(--radius-sm);
                    margin-bottom: var(--space-3);
                    font-size: var(--font-size-sm);
                    display: flex;
                    align-items: center;
                    gap: var(--space-2);
                `;
                disabledMessage.innerHTML = `
                    <i class="fas fa-info-circle"></i>
                    <span>Agent controls disabled while viewing historical task</span>
                `;
                
                agentControlPanel.insertBefore(disabledMessage, agentControlPanel.firstChild);
            }
        }
    }
    
    async exitHistoricalView() {
        this.isViewingHistoricalTask = false;
        this.selectedHistoricalTask = null;
        
        // Re-enable agent controls
        this.enableAgentControls();
        
        // Remove historical view indicator
        const indicator = document.getElementById('historical-view-indicator');
        if (indicator) {
            indicator.remove();
        }
        
        // Remove historical view header if it exists
        const headerElement = document.querySelector('.historical-logs-header');
        if (headerElement) {
            headerElement.remove();
        }
        
        // Switch back to live mode using PostgreSQL logs manager
        if (this.simplifiedLogsManager) {
            try {
                await this.simplifiedLogsManager.switchToLiveMode();
                console.log('✅ Successfully switched to live mode via PostgreSQL logs manager');
            } catch (error) {
                console.error('❌ Error switching to live mode:', error);
                
                // Fallback to legacy method
                if (this.liveLogsManager) {
                    this.liveLogsManager.clearLogs();
                    this.liveLogsManager.addLogEntry({
                        level: 'INFO',
                        message: '🔄 Returned to live log mode (fallback)',
                        timestamp: new Date().toISOString(),
                        module: 'HistoricalTasksManager'
                    });
                }
            }
        } else if (this.liveLogsManager) {
            // Fallback to legacy logs manager
            this.liveLogsManager.clearLogs();
            this.liveLogsManager.addLogEntry({
                level: 'INFO',
                message: '🔄 Returned to live log mode',
                timestamp: new Date().toISOString(),
                module: 'HistoricalTasksManager'
            });
        }
        
        console.log('📚 Exited historical task view');
    }
    
    enableAgentControls() {
        // Re-enable agent control buttons
        const controlButtons = document.querySelectorAll('#run-agent-btn, #stop-agent-btn, #clear-all-options, [data-pref], [data-mode]');
        controlButtons.forEach(btn => {
            btn.disabled = false;
            btn.style.opacity = '';
            btn.style.cursor = '';
        });
        
        // Remove disabled state message
        const disabledMessage = document.getElementById('historical-view-disabled-message');
        if (disabledMessage) {
            disabledMessage.remove();
        }
    }
    
    showNotification(message, type = 'info') {
        // Use existing notification system if available
        if (window.notificationSystem) {
            window.notificationSystem.show(message, type);
        } else {
            // Fallback to console
            console.log(`[${type.toUpperCase()}] ${message}`);
        }
    }
    
    // Public API methods
    isInHistoricalView() {
        return this.isViewingHistoricalTask;
    }
    
    getCurrentHistoricalTask() {
        return this.selectedHistoricalTask;
    }
    
    refreshTaskList() {
        this.loadCompletedTasks();
    }
}

// Export for global access
window.HistoricalTasksManager = HistoricalTasksManager;
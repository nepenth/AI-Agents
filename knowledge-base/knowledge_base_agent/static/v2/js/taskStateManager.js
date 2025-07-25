/**
 * Enhanced Task State Management for Frontend
 * 
 * Provides comprehensive task lifecycle management, state persistence,
 * and automatic state recovery for the Knowledge Base Agent frontend.
 */

class TaskStateManager {
    constructor() {
        this.currentTask = null;
        this.taskHistory = [];
        this.eventListeners = new Map();
        this.pollingInterval = null;
        this.pollingFrequency = 3000; // 3 seconds
        
        // Initialize on page load
        this.initialize();
    }
    
    /**
     * Initialize task state manager and restore state on page load
     */
    async initialize() {
        console.log('🔄 Initializing Task State Manager...');
        
        try {
            // Check for active task on page load
            await this.restoreActiveTask();
            
            // Set up periodic status checking
            this.startPolling();
            
            console.log('✅ Task State Manager initialized successfully');
        } catch (error) {
            console.error('❌ Failed to initialize Task State Manager:', error);
        }
    }
    
    /**
     * Restore active task state on page load
     */
    async restoreActiveTask() {
        try {
            const response = await fetch('/api/v2/agent/active');
            const data = await response.json();
            
            if (data.active_task) {
                this.currentTask = data.active_task;
                console.log('🔄 Restored active task:', this.currentTask.task_id);
                
                // Emit task restored event
                this.emit('taskRestored', this.currentTask);
                
                // Update UI to reflect restored state
                this.updateUIForActiveTask(this.currentTask);
                
                return this.currentTask;
            } else {
                console.log('ℹ️ No active task found on page load');
                this.emit('noActiveTask');
                return null;
            }
        } catch (error) {
            console.error('❌ Failed to restore active task:', error);
            this.emit('restoreError', error);
            return null;
        }
    }
    
    /**
     * Start a new agent task
     */
    async startTask(preferences = {}) {
        try {
            // Check if there's already an active task
            if (this.currentTask && this.currentTask.is_running) {
                throw new Error('Another task is already running');
            }
            
            const response = await fetch('/api/v2/agent/start', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ preferences })
            });
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || 'Failed to start task');
            }
            
            // Update current task
            this.currentTask = {
                task_id: data.task_id,
                human_readable_name: data.human_readable_name,
                is_running: true,
                status: 'PENDING',
                preferences: preferences,
                created_at: new Date().toISOString()
            };
            
            console.log('🚀 Started new task:', this.currentTask.task_id);
            
            // Emit task started event
            this.emit('taskStarted', this.currentTask);
            
            // Start polling for updates
            this.startPolling();
            
            return this.currentTask;
            
        } catch (error) {
            console.error('❌ Failed to start task:', error);
            this.emit('taskError', error);
            throw error;
        }
    }
    
    /**
     * Stop the current task
     */
    async stopTask(taskId = null) {
        try {
            const targetTaskId = taskId || (this.currentTask ? this.currentTask.task_id : null);
            
            if (!targetTaskId) {
                throw new Error('No task to stop');
            }
            
            const response = await fetch('/api/v2/agent/stop', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ task_id: targetTaskId })
            });
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || 'Failed to stop task');
            }
            
            console.log('⏹️ Stopped task:', targetTaskId);
            
            // Update current task status
            if (this.currentTask && this.currentTask.task_id === targetTaskId) {
                this.currentTask.is_running = false;
                this.currentTask.status = 'STOPPED';
            }
            
            // Emit task stopped event
            this.emit('taskStopped', { task_id: targetTaskId });
            
            return data;
            
        } catch (error) {
            console.error('❌ Failed to stop task:', error);
            this.emit('taskError', error);
            throw error;
        }
    }
    
    /**
     * Get detailed status for a specific task
     */
    async getTaskStatus(taskId) {
        try {
            const response = await fetch(`/api/v2/agent/status/${taskId}`);
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || 'Failed to get task status');
            }
            
            // Update current task if this is the active task
            if (this.currentTask && this.currentTask.task_id === taskId) {
                this.currentTask = { ...this.currentTask, ...data };
            }
            
            return data;
            
        } catch (error) {
            console.error(`❌ Failed to get status for task ${taskId}:`, error);
            throw error;
        }
    }
    
    /**
     * Get job history with pagination and filtering
     */
    async getJobHistory(options = {}) {
        try {
            const params = new URLSearchParams();
            
            if (options.limit) params.append('limit', options.limit);
            if (options.offset) params.append('offset', options.offset);
            if (options.job_type) params.append('job_type', options.job_type);
            if (options.status) params.append('status', options.status);
            
            const response = await fetch(`/api/v2/jobs/history?${params}`);
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || 'Failed to get job history');
            }
            
            this.taskHistory = data.jobs;
            return data;
            
        } catch (error) {
            console.error('❌ Failed to get job history:', error);
            throw error;
        }
    }
    
    /**
     * Reset agent state (emergency recovery)
     */
    async resetAgentState() {
        try {
            const response = await fetch('/api/agent/reset-state', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || 'Failed to reset agent state');
            }
            
            // Clear current task
            this.currentTask = null;
            
            console.log('🔄 Agent state reset successfully');
            
            // Emit reset event
            this.emit('agentReset', data);
            
            // Stop polling
            this.stopPolling();
            
            return data;
            
        } catch (error) {
            console.error('❌ Failed to reset agent state:', error);
            this.emit('resetError', error);
            throw error;
        }
    }
    
    /**
     * Start polling for task status updates
     */
    startPolling() {
        if (this.pollingInterval) {
            clearInterval(this.pollingInterval);
        }
        
        this.pollingInterval = setInterval(async () => {
            if (this.currentTask && this.currentTask.is_running) {
                try {
                    const status = await this.getTaskStatus(this.currentTask.task_id);
                    
                    // Check if task completed
                    if (!status.is_running && this.currentTask.is_running) {
                        console.log('✅ Task completed:', this.currentTask.task_id);
                        this.currentTask.is_running = false;
                        this.emit('taskCompleted', status);
                        
                        // Stop polling when task completes
                        this.stopPolling();
                    } else if (status.is_running) {
                        // Emit progress update
                        this.emit('taskProgress', status);
                    }
                    
                } catch (error) {
                    console.error('❌ Error polling task status:', error);
                    // Don't emit error for polling failures to avoid spam
                }
            } else {
                // No active task, stop polling
                this.stopPolling();
            }
        }, this.pollingFrequency);
        
        console.log('🔄 Started task status polling');
    }
    
    /**
     * Stop polling for task status updates
     */
    stopPolling() {
        if (this.pollingInterval) {
            clearInterval(this.pollingInterval);
            this.pollingInterval = null;
            console.log('⏹️ Stopped task status polling');
        }
    }
    
    /**
     * Update UI components for active task
     */
    updateUIForActiveTask(task) {
        // Update agent status display
        if (window.agentControls) {
            window.agentControls.updateStatus({
                is_running: task.is_running,
                current_phase_message: task.current_phase_message || 'Processing...',
                task_id: task.task_id
            });
        }
        
        // Update execution plan if available
        if (window.executionPlan && task.run_report) {
            window.executionPlan.updateFromRunReport(task.run_report);
        }
        
        // Update logs display
        if (window.liveLogs && task.logs) {
            window.liveLogs.displayLogs(task.logs);
        }
        
        // Update progress display
        if (window.progressDisplay) {
            window.progressDisplay.updateProgress({
                progress: task.progress_percentage || 0,
                phase_id: task.current_phase_id,
                message: task.current_phase_message
            });
        }
    }
    
    /**
     * Add event listener
     */
    on(event, callback) {
        if (!this.eventListeners.has(event)) {
            this.eventListeners.set(event, []);
        }
        this.eventListeners.get(event).push(callback);
    }
    
    /**
     * Remove event listener
     */
    off(event, callback) {
        if (this.eventListeners.has(event)) {
            const listeners = this.eventListeners.get(event);
            const index = listeners.indexOf(callback);
            if (index > -1) {
                listeners.splice(index, 1);
            }
        }
    }
    
    /**
     * Emit event to listeners
     */
    emit(event, data) {
        if (this.eventListeners.has(event)) {
            this.eventListeners.get(event).forEach(callback => {
                try {
                    callback(data);
                } catch (error) {
                    console.error(`Error in event listener for ${event}:`, error);
                }
            });
        }
    }
    
    /**
     * Get current task information
     */
    getCurrentTask() {
        return this.currentTask;
    }
    
    /**
     * Check if there's an active task
     */
    hasActiveTask() {
        return this.currentTask && this.currentTask.is_running;
    }
    
    /**
     * Get task history
     */
    getTaskHistory() {
        return this.taskHistory;
    }
    
    /**
     * Cleanup resources
     */
    destroy() {
        this.stopPolling();
        this.eventListeners.clear();
        this.currentTask = null;
        this.taskHistory = [];
    }
}

// Create global instance
window.taskStateManager = new TaskStateManager();

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = TaskStateManager;
}
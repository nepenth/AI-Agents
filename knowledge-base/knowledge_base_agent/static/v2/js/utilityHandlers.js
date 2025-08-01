/* ===== UTILITY HANDLERS FOR CELERY MANAGEMENT ===== */

class UtilityManager {
    constructor(api) {
        this.api = api;
        this.init();
    }
    
    init() {
        this.setupEventListeners();
        console.log('🔧 Utility Manager initialized');
    }
    
    setupEventListeners() {
        // Use centralized EventListenerService
        EventListenerService.setupStandardListeners(this, {
            buttons: [
                // Celery Task Management
                {
                    selector: '#clear-celery-queue-btn',
                    handler: () => this.clearTaskQueue(),
                    debounce: 1000 // Prevent accidental double-clicks
                },
                {
                    selector: '#purge-celery-tasks-btn',
                    handler: () => this.purgeAllTasks(),
                    debounce: 1000
                },
                {
                    selector: '#restart-celery-workers-btn',
                    handler: () => this.restartWorkers(),
                    debounce: 2000 // Longer debounce for restart operations
                },
                {
                    selector: '#celery-status-btn',
                    handler: () => this.showWorkerStatus(),
                    debounce: 500
                },
                {
                    selector: '#clear-old-tasks-btn',
                    handler: () => this.clearOldTasks(),
                    debounce: 1000
                },
                {
                    selector: '#stuck-tasks-btn',
                    handler: () => this.checkStuckTasks(),
                    debounce: 500
                },
                {
                    selector: '#revoke-tasks-btn',
                    handler: () => this.revokeTasks(),
                    debounce: 1000
                },
                {
                    selector: '#flush-redis-btn',
                    handler: () => this.flushRedis(),
                    debounce: 2000 // Longer debounce for destructive operations
                },
                
                // System Utilities
                {
                    selector: '#clear-redis-cache-btn',
                    handler: () => this.clearRedisCache(),
                    debounce: 1000
                },
                {
                    selector: '#cleanup-temp-files-btn',
                    handler: () => this.cleanupTempFiles(),
                    debounce: 1000
                },
                {
                    selector: '#system-health-check-btn',
                    handler: () => this.systemHealthCheck(),
                    debounce: 500
                },
                
                // Debug Tools
                {
                    selector: '#export-logs-btn',
                    handler: () => this.exportLogs(),
                    debounce: 1000
                },
                {
                    selector: '#test-connections-btn',
                    handler: () => this.testConnections(),
                    debounce: 500
                },
                {
                    selector: '#debug-info-btn',
                    handler: () => this.showDebugInfo(),
                    debounce: 500
                }
            ]
        });
    }
    
    // ===== CELERY TASK MANAGEMENT METHODS =====
    
    async clearTaskQueue() {
        try {
            this.showLoading('clear-celery-queue-btn', 'Clearing...');
            
            const response = await fetch('/api/v2/celery/clear-queue', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.showNotification('Task queue cleared successfully', 'success');
                console.log('✅ Celery queue cleared');
            } else {
                this.showNotification(`Failed to clear queue: ${result.error}`, 'error');
                console.error('❌ Failed to clear Celery queue:', result.error);
            }
        } catch (error) {
            this.showNotification(`Error clearing queue: ${error.message}`, 'error');
            console.error('❌ Error clearing Celery queue:', error);
        } finally {
            this.hideLoading('clear-celery-queue-btn', 'Clear Queue');
        }
    }
    
    async purgeAllTasks() {
        if (!confirm('Are you sure you want to purge ALL tasks? This will stop all running tasks and clear the queue.')) {
            return;
        }
        
        try {
            this.showLoading('purge-celery-tasks-btn', 'Purging...');
            
            const response = await fetch('/api/v2/celery/purge-tasks', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.showNotification('All tasks purged successfully', 'success');
                console.log('✅ All Celery tasks purged');
                
                // Update agent state to reflect stopped tasks
                this.updateAgentStateAfterPurge();
            } else {
                this.showNotification(`Failed to purge tasks: ${result.error}`, 'error');
                console.error('❌ Failed to purge Celery tasks:', result.error);
            }
        } catch (error) {
            this.showNotification(`Error purging tasks: ${error.message}`, 'error');
            console.error('❌ Error purging Celery tasks:', error);
        } finally {
            this.hideLoading('purge-celery-tasks-btn', 'Purge All');
        }
    }
    
    async restartWorkers() {
        if (!confirm('Are you sure you want to restart Celery workers? This may interrupt running tasks.')) {
            return;
        }
        
        try {
            this.showLoading('restart-celery-workers-btn', 'Restarting...');
            
            const response = await fetch('/api/v2/celery/restart-workers', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.showNotification('Worker restart signal sent', 'success');
                console.log('✅ Celery workers restart signal sent');
            } else {
                this.showNotification(`Failed to restart workers: ${result.error}`, 'error');
                console.error('❌ Failed to restart Celery workers:', result.error);
            }
        } catch (error) {
            this.showNotification(`Error restarting workers: ${error.message}`, 'error');
            console.error('❌ Error restarting Celery workers:', error);
        } finally {
            this.hideLoading('restart-celery-workers-btn', 'Restart Workers');
        }
    }
    
    async showWorkerStatus() {
        try {
            this.showLoading('celery-status-btn', 'Checking...');
            
            const response = await fetch('/api/v2/celery/status');
            const result = await response.json();
            
            if (result.success) {
                this.displayWorkerStatusModal(result.data);
            } else {
                this.showNotification(`Failed to get worker status: ${result.error}`, 'error');
                console.error('❌ Failed to get Celery status:', result.error);
            }
        } catch (error) {
            this.showNotification(`Error getting worker status: ${error.message}`, 'error');
            console.error('❌ Error getting Celery status:', error);
        } finally {
            this.hideLoading('celery-status-btn', 'Status');
        }
    }
    
    displayWorkerStatusModal(statusData) {
        const modal = document.createElement('div');
        modal.className = 'utility-modal';
        modal.innerHTML = `
            <div class="utility-modal-overlay"></div>
            <div class="utility-modal-content">
                <div class="utility-modal-header">
                    <h3>Celery Worker Status</h3>
                    <button class="utility-modal-close">&times;</button>
                </div>
                <div class="utility-modal-body">
                    <div class="status-summary">
                        <div class="status-item">
                            <span class="status-label">Active Tasks:</span>
                            <span class="status-value">${statusData.total_active}</span>
                        </div>
                        <div class="status-item">
                            <span class="status-label">Scheduled Tasks:</span>
                            <span class="status-value">${statusData.total_scheduled}</span>
                        </div>
                        <div class="status-item">
                            <span class="status-label">Workers:</span>
                            <span class="status-value">${Object.keys(statusData.workers || {}).length}</span>
                        </div>
                    </div>
                    
                    <div class="worker-details">
                        <h4>Worker Details:</h4>
                        <pre>${JSON.stringify(statusData, null, 2)}</pre>
                    </div>
                </div>
            </div>
        `;
        
        modal.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            z-index: 10000;
            display: flex;
            align-items: center;
            justify-content: center;
        `;
        
        document.body.appendChild(modal);
        
        const closeModal = () => {
            document.body.removeChild(modal);
        };
        
        modal.querySelector('.utility-modal-close').addEventListener('click', closeModal);
        modal.querySelector('.utility-modal-overlay').addEventListener('click', closeModal);
        
        // Close on escape
        const escapeHandler = (e) => {
            if (e.key === 'Escape') {
                closeModal();
                document.removeEventListener('keydown', escapeHandler);
            }
        };
        document.addEventListener('keydown', escapeHandler);
    }
    
    // ===== ADVANCED CELERY MANAGEMENT METHODS =====
    
    async clearOldTasks() {
        const modal = this.createClearOldTasksModal();
        document.body.appendChild(modal);
    }
    
    createClearOldTasksModal() {
        const modal = document.createElement('div');
        modal.className = 'utility-modal';
        modal.innerHTML = `
            <div class="utility-modal-overlay"></div>
            <div class="utility-modal-content">
                <div class="utility-modal-header">
                    <h3>Clear Old Tasks</h3>
                    <button class="utility-modal-close">&times;</button>
                </div>
                <div class="utility-modal-body">
                    <div class="form-group">
                        <label for="older-than-hours">Clear tasks older than (hours):</label>
                        <input type="number" id="older-than-hours" value="24" min="1" max="720">
                    </div>
                    
                    <div class="form-group">
                        <label>Status filter (optional):</label>
                        <div class="checkbox-group">
                            <label><input type="checkbox" value="SUCCESS"> SUCCESS</label>
                            <label><input type="checkbox" value="FAILURE"> FAILURE</label>
                            <label><input type="checkbox" value="REVOKED"> REVOKED</label>
                        </div>
                    </div>
                    
                    <div class="form-group">
                        <label>
                            <input type="checkbox" id="dry-run-checkbox" checked>
                            Dry run (preview only)
                        </label>
                    </div>
                    
                    <div class="modal-actions">
                        <button id="clear-old-tasks-execute" class="btn btn-primary">Execute</button>
                        <button class="utility-modal-close btn btn-secondary">Cancel</button>
                    </div>
                </div>
            </div>
        `;
        
        modal.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            z-index: 10000;
            display: flex;
            align-items: center;
            justify-content: center;
        `;
        
        const closeModal = () => document.body.removeChild(modal);
        
        modal.querySelector('.utility-modal-close').addEventListener('click', closeModal);
        modal.querySelector('.utility-modal-overlay').addEventListener('click', closeModal);
        
        modal.querySelector('#clear-old-tasks-execute').addEventListener('click', async () => {
            const olderThan = parseInt(modal.querySelector('#older-than-hours').value);
            const statusCheckboxes = modal.querySelectorAll('.checkbox-group input[type="checkbox"]:checked');
            const status = Array.from(statusCheckboxes).map(cb => cb.value);
            const dryRun = modal.querySelector('#dry-run-checkbox').checked;
            
            await this.executeClearOldTasks(olderThan, status, dryRun);
            closeModal();
        });
        
        return modal;
    }
    
    async executeClearOldTasks(olderThan, status, dryRun) {
        try {
            const response = await fetch('/api/v2/celery/clear-old-tasks', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    older_than: olderThan,
                    status: status,
                    dry_run: dryRun
                })
            });
            
            const result = await response.json();
            
            if (result.success) {
                if (dryRun) {
                    this.showTaskPreviewModal(result.tasks, `Would delete ${result.tasks.length} tasks`);
                } else {
                    this.showNotification(`Cleared ${result.deleted_count} old tasks`, 'success');
                }
            } else {
                this.showNotification(`Failed to clear old tasks: ${result.error}`, 'error');
            }
        } catch (error) {
            this.showNotification(`Error clearing old tasks: ${error.message}`, 'error');
        }
    }
    
    async checkStuckTasks() {
        try {
            this.showLoading('stuck-tasks-btn', 'Checking...');
            
            const response = await fetch('/api/v2/celery/stuck-tasks?max_runtime=3');
            const result = await response.json();
            
            if (result.success) {
                if (result.stuck_tasks.length > 0) {
                    this.showStuckTasksModal(result.stuck_tasks);
                } else {
                    this.showNotification('No stuck tasks found', 'success');
                }
            } else {
                this.showNotification(`Failed to check stuck tasks: ${result.error}`, 'error');
            }
        } catch (error) {
            this.showNotification(`Error checking stuck tasks: ${error.message}`, 'error');
        } finally {
            this.hideLoading('stuck-tasks-btn', 'Check Stuck');
        }
    }
    
    showStuckTasksModal(stuckTasks) {
        const modal = document.createElement('div');
        modal.className = 'utility-modal';
        modal.innerHTML = `
            <div class="utility-modal-overlay"></div>
            <div class="utility-modal-content">
                <div class="utility-modal-header">
                    <h3>Stuck Tasks (${stuckTasks.length})</h3>
                    <button class="utility-modal-close">&times;</button>
                </div>
                <div class="utility-modal-body">
                    <div class="stuck-tasks-list">
                        ${stuckTasks.map(task => `
                            <div class="stuck-task-item">
                                <div class="task-info">
                                    <strong>Task ID:</strong> ${task.task_id}<br>
                                    <strong>Status:</strong> ${task.status}<br>
                                    <strong>Runtime:</strong> ${task.runtime_hours}h<br>
                                    <strong>Phase:</strong> ${task.current_phase_message || 'Unknown'}
                                </div>
                                <button class="btn btn-danger btn-sm revoke-task-btn" data-task-id="${task.task_id}">
                                    Revoke
                                </button>
                            </div>
                        `).join('')}
                    </div>
                    <div class="modal-actions">
                        <button id="revoke-all-stuck" class="btn btn-danger">Revoke All Stuck Tasks</button>
                        <button class="utility-modal-close btn btn-secondary">Close</button>
                    </div>
                </div>
            </div>
        `;
        
        modal.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            z-index: 10000;
            display: flex;
            align-items: center;
            justify-content: center;
        `;
        
        document.body.appendChild(modal);
        
        const closeModal = () => document.body.removeChild(modal);
        
        modal.querySelector('.utility-modal-close').addEventListener('click', closeModal);
        modal.querySelector('.utility-modal-overlay').addEventListener('click', closeModal);
        
        // Individual revoke buttons
        modal.querySelectorAll('.revoke-task-btn').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                const taskId = e.target.dataset.taskId;
                await this.revokeSpecificTask(taskId);
                e.target.disabled = true;
                e.target.textContent = 'Revoked';
            });
        });
        
        // Revoke all button
        modal.querySelector('#revoke-all-stuck').addEventListener('click', async () => {
            const taskIds = stuckTasks.map(task => task.task_id);
            for (const taskId of taskIds) {
                await this.revokeSpecificTask(taskId);
            }
            closeModal();
            this.showNotification(`Revoked ${taskIds.length} stuck tasks`, 'success');
        });
    }
    
    async revokeTasks() {
        if (!confirm('Are you sure you want to revoke ALL active tasks?')) {
            return;
        }
        
        try {
            this.showLoading('revoke-tasks-btn', 'Revoking...');
            
            const response = await fetch('/api/v2/celery/revoke-tasks', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ all_active: true })
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.showNotification(`Revoked ${result.revoked_tasks.length} tasks`, 'success');
                this.updateAgentStateAfterPurge();
            } else {
                this.showNotification(`Failed to revoke tasks: ${result.error}`, 'error');
            }
        } catch (error) {
            this.showNotification(`Error revoking tasks: ${error.message}`, 'error');
        } finally {
            this.hideLoading('revoke-tasks-btn', 'Revoke Active');
        }
    }
    
    async revokeSpecificTask(taskId) {
        try {
            const response = await fetch('/api/v2/celery/revoke-tasks', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ task_id: taskId })
            });
            
            const result = await response.json();
            
            if (result.success) {
                console.log(`✅ Revoked task: ${taskId}`);
            } else {
                console.error(`❌ Failed to revoke task ${taskId}:`, result.error);
            }
        } catch (error) {
            console.error(`❌ Error revoking task ${taskId}:`, error);
        }
    }
    
    async flushRedis() {
        if (!confirm('Are you sure you want to flush ALL task data from Redis? This will clear all progress and logs.')) {
            return;
        }
        
        try {
            this.showLoading('flush-redis-btn', 'Flushing...');
            
            const response = await fetch('/api/v2/celery/flush-redis', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.showNotification('Redis task data flushed successfully', 'success');
                console.log('✅ Redis task data flushed');
            } else {
                this.showNotification(`Failed to flush Redis: ${result.error}`, 'error');
                console.error('❌ Failed to flush Redis:', result.error);
            }
        } catch (error) {
            this.showNotification(`Error flushing Redis: ${error.message}`, 'error');
            console.error('❌ Error flushing Redis:', error);
        } finally {
            this.hideLoading('flush-redis-btn', 'Flush Redis');
        }
    }
    
    showTaskPreviewModal(tasks, title) {
        const modal = document.createElement('div');
        modal.className = 'utility-modal';
        modal.innerHTML = `
            <div class="utility-modal-overlay"></div>
            <div class="utility-modal-content">
                <div class="utility-modal-header">
                    <h3>${title}</h3>
                    <button class="utility-modal-close">&times;</button>
                </div>
                <div class="utility-modal-body">
                    <div class="task-preview-list">
                        ${tasks.map(task => `
                            <div class="task-preview-item">
                                <strong>ID:</strong> ${task.task_id}<br>
                                <strong>Status:</strong> ${task.status}<br>
                                <strong>Created:</strong> ${new Date(task.created_at).toLocaleString()}
                            </div>
                        `).join('')}
                    </div>
                </div>
            </div>
        `;
        
        modal.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            z-index: 10000;
            display: flex;
            align-items: center;
            justify-content: center;
        `;
        
        document.body.appendChild(modal);
        
        const closeModal = () => document.body.removeChild(modal);
        modal.querySelector('.utility-modal-close').addEventListener('click', closeModal);
        modal.querySelector('.utility-modal-overlay').addEventListener('click', closeModal);
    }
    
    // ===== SYSTEM UTILITIES METHODS =====
    
    async clearRedisCache() {
        if (!confirm('Are you sure you want to clear the Redis cache? This may affect system performance temporarily.')) {
            return;
        }
        
        try {
            this.showLoading('clear-redis-cache-btn', 'Clearing...');
            
            const response = await fetch('/api/utilities/system/clear-redis', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.showNotification('Redis cache cleared successfully', 'success');
                console.log('✅ Redis cache cleared');
            } else {
                this.showNotification(`Failed to clear Redis cache: ${result.error}`, 'error');
                console.error('❌ Failed to clear Redis cache:', result.error);
            }
        } catch (error) {
            this.showNotification(`Error clearing Redis cache: ${error.message}`, 'error');
            console.error('❌ Error clearing Redis cache:', error);
        } finally {
            this.hideLoading('clear-redis-cache-btn', 'Clear Redis Cache');
        }
    }
    
    async cleanupTempFiles() {
        if (!confirm('Are you sure you want to cleanup temporary files? This will remove old temporary files.')) {
            return;
        }
        
        try {
            this.showLoading('cleanup-temp-files-btn', 'Cleaning...');
            
            const response = await fetch('/api/utilities/system/cleanup-temp', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.showNotification(result.message, 'success');
                console.log('✅ Temp files cleaned up');
            } else {
                this.showNotification(`Failed to cleanup temp files: ${result.error}`, 'error');
                console.error('❌ Failed to cleanup temp files:', result.error);
            }
        } catch (error) {
            this.showNotification(`Error cleaning up temp files: ${error.message}`, 'error');
            console.error('❌ Error cleaning up temp files:', error);
        } finally {
            this.hideLoading('cleanup-temp-files-btn', 'Cleanup Temp Files');
        }
    }
    
    async systemHealthCheck() {
        try {
            this.showLoading('system-health-check-btn', 'Checking...');
            
            const response = await fetch('/api/utilities/system/health-check');
            const result = await response.json();
            
            if (result.success) {
                this.showHealthCheckModal(result.health_status);
            } else {
                this.showNotification(`Health check failed: ${result.error}`, 'error');
                console.error('❌ Health check failed:', result.error);
            }
        } catch (error) {
            this.showNotification(`Error running health check: ${error.message}`, 'error');
            console.error('❌ Error running health check:', error);
        } finally {
            this.hideLoading('system-health-check-btn', 'Health Check');
        }
    }
    
    showHealthCheckModal(healthStatus) {
        const modal = document.createElement('div');
        modal.className = 'utility-modal';
        
        // Calculate overall health
        const allChecks = Object.values(healthStatus);
        const healthyCount = allChecks.filter(check => check.status === 'healthy').length;
        const overallHealth = healthyCount === allChecks.length ? 'healthy' : 'issues';
        
        modal.innerHTML = `
            <div class="utility-modal-overlay"></div>
            <div class="utility-modal-content">
                <div class="utility-modal-header">
                    <h3>System Health Check</h3>
                    <div class="health-indicator ${overallHealth}">
                        <i class="fas fa-${overallHealth === 'healthy' ? 'check-circle' : 'exclamation-triangle'}"></i>
                        ${overallHealth === 'healthy' ? 'All Systems Healthy' : 'Issues Detected'}
                    </div>
                    <button class="utility-modal-close">&times;</button>
                </div>
                <div class="utility-modal-body">
                    <div class="health-checks">
                        ${Object.entries(healthStatus).map(([service, check]) => `
                            <div class="health-check-item ${check.status}">
                                <div class="health-check-header">
                                    <i class="fas fa-${check.status === 'healthy' ? 'check-circle' : 'times-circle'}"></i>
                                    <strong>${service.replace('_', ' ').toUpperCase()}</strong>
                                    <span class="health-status">${check.status}</span>
                                </div>
                                ${check.message ? `<div class="health-check-message">${check.message}</div>` : ''}
                                ${check.details ? `<div class="health-check-details">${JSON.stringify(check.details, null, 2)}</div>` : ''}
                            </div>
                        `).join('')}
                    </div>
                </div>
            </div>
        `;
        
        modal.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            z-index: 10000;
            display: flex;
            align-items: center;
            justify-content: center;
        `;
        
        document.body.appendChild(modal);
        
        const closeModal = () => document.body.removeChild(modal);
        modal.querySelector('.utility-modal-close').addEventListener('click', closeModal);
        modal.querySelector('.utility-modal-overlay').addEventListener('click', closeModal);
    }
    
    // ===== DEBUG TOOLS METHODS =====
    
    async exportLogs() {
        try {
            this.showLoading('export-logs-btn', 'Exporting...');
            
            const response = await fetch('/api/utilities/debug/export-logs');
            
            if (response.ok) {
                // Check if it's a JSON error response or a file download
                const contentType = response.headers.get('content-type');
                
                if (contentType && contentType.includes('application/json')) {
                    const result = await response.json();
                    this.showNotification(`Failed to export logs: ${result.error}`, 'error');
                } else {
                    // It's a file download
                    const blob = await response.blob();
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `system-logs-${new Date().toISOString().split('T')[0]}.zip`;
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    window.URL.revokeObjectURL(url);
                    
                    this.showNotification('Logs exported successfully', 'success');
                    console.log('✅ Logs exported');
                }
            } else {
                this.showNotification('Failed to export logs', 'error');
            }
        } catch (error) {
            this.showNotification(`Error exporting logs: ${error.message}`, 'error');
            console.error('❌ Error exporting logs:', error);
        } finally {
            this.hideLoading('export-logs-btn', 'Export Logs');
        }
    }
    
    async testConnections() {
        try {
            this.showLoading('test-connections-btn', 'Testing...');
            
            const response = await fetch('/api/utilities/debug/test-connections');
            const result = await response.json();
            
            if (result.success) {
                this.showConnectionTestModal(result.connections);
            } else {
                this.showNotification(`Connection test failed: ${result.error}`, 'error');
                console.error('❌ Connection test failed:', result.error);
            }
        } catch (error) {
            this.showNotification(`Error testing connections: ${error.message}`, 'error');
            console.error('❌ Error testing connections:', error);
        } finally {
            this.hideLoading('test-connections-btn', 'Test Connections');
        }
    }
    
    showConnectionTestModal(connections) {
        const modal = document.createElement('div');
        modal.className = 'utility-modal';
        
        // Calculate overall connection health
        const allConnections = Object.values(connections);
        const healthyCount = allConnections.filter(conn => conn.status === 'connected').length;
        const overallHealth = healthyCount === allConnections.length ? 'healthy' : 'issues';
        
        modal.innerHTML = `
            <div class="utility-modal-overlay"></div>
            <div class="utility-modal-content">
                <div class="utility-modal-header">
                    <h3>Connection Test Results</h3>
                    <div class="health-indicator ${overallHealth}">
                        <i class="fas fa-${overallHealth === 'healthy' ? 'check-circle' : 'exclamation-triangle'}"></i>
                        ${healthyCount}/${allConnections.length} Connected
                    </div>
                    <button class="utility-modal-close">&times;</button>
                </div>
                <div class="utility-modal-body">
                    <div class="connection-tests">
                        ${Object.entries(connections).map(([service, conn]) => `
                            <div class="connection-test-item ${conn.status}">
                                <div class="connection-test-header">
                                    <i class="fas fa-${conn.status === 'connected' ? 'check-circle' : 'times-circle'}"></i>
                                    <strong>${service.replace('_', ' ').toUpperCase()}</strong>
                                    <span class="connection-status">${conn.status}</span>
                                </div>
                                ${conn.message ? `<div class="connection-test-message">${conn.message}</div>` : ''}
                                ${conn.details ? `<div class="connection-test-details">${JSON.stringify(conn.details, null, 2)}</div>` : ''}
                            </div>
                        `).join('')}
                    </div>
                </div>
            </div>
        `;
        
        modal.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            z-index: 10000;
            display: flex;
            align-items: center;
            justify-content: center;
        `;
        
        document.body.appendChild(modal);
        
        const closeModal = () => document.body.removeChild(modal);
        modal.querySelector('.utility-modal-close').addEventListener('click', closeModal);
        modal.querySelector('.utility-modal-overlay').addEventListener('click', closeModal);
    }
    
    async showDebugInfo() {
        try {
            this.showLoading('debug-info-btn', 'Loading...');
            
            const response = await fetch('/api/utilities/debug/info');
            const result = await response.json();
            
            if (result.success) {
                this.showDebugInfoModal(result.debug_info);
            } else {
                this.showNotification(`Failed to get debug info: ${result.error}`, 'error');
                console.error('❌ Failed to get debug info:', result.error);
            }
        } catch (error) {
            this.showNotification(`Error getting debug info: ${error.message}`, 'error');
            console.error('❌ Error getting debug info:', error);
        } finally {
            this.hideLoading('debug-info-btn', 'Debug Info');
        }
    }
    
    showDebugInfoModal(debugInfo) {
        const modal = document.createElement('div');
        modal.className = 'utility-modal';
        modal.innerHTML = `
            <div class="utility-modal-overlay"></div>
            <div class="utility-modal-content">
                <div class="utility-modal-header">
                    <h3>System Debug Information</h3>
                    <button class="utility-modal-close">&times;</button>
                </div>
                <div class="utility-modal-body">
                    <div class="debug-info-sections">
                        ${Object.entries(debugInfo).map(([section, data]) => `
                            <div class="debug-info-section">
                                <h4>${section.replace('_', ' ').toUpperCase()}</h4>
                                <div class="debug-info-content">
                                    ${typeof data === 'object' ? 
                                        `<pre>${JSON.stringify(data, null, 2)}</pre>` : 
                                        `<div class="debug-info-value">${data}</div>`
                                    }
                                </div>
                            </div>
                        `).join('')}
                    </div>
                    <div class="modal-actions">
                        <button id="copy-debug-info" class="btn btn-secondary">Copy to Clipboard</button>
                        <button class="utility-modal-close btn btn-secondary">Close</button>
                    </div>
                </div>
            </div>
        `;
        
        modal.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            z-index: 10000;
            display: flex;
            align-items: center;
            justify-content: center;
        `;
        
        document.body.appendChild(modal);
        
        const closeModal = () => document.body.removeChild(modal);
        modal.querySelector('.utility-modal-close').addEventListener('click', closeModal);
        modal.querySelector('.utility-modal-overlay').addEventListener('click', closeModal);
        
        // Copy to clipboard functionality
        modal.querySelector('#copy-debug-info').addEventListener('click', async () => {
            try {
                const debugText = JSON.stringify(debugInfo, null, 2);
                await navigator.clipboard.writeText(debugText);
                this.showNotification('Debug info copied to clipboard', 'success');
            } catch (error) {
                this.showNotification('Failed to copy debug info', 'error');
            }
        });
    }
    
    // ===== UTILITY HELPER METHODS =====
    
    updateAgentStateAfterPurge() {
        // Update UI to reflect that agent is no longer running
        const statusIndicator = document.getElementById('agent-status-indicator');
        const statusText = document.getElementById('agent-status-text-main');
        
        if (statusIndicator && statusText) {
            statusIndicator.className = 'glass-badge glass-badge--primary';
            statusText.textContent = 'Idle';
        }
        
        // Reset execution plan
        document.dispatchEvent(new CustomEvent('agent_status_update', {
            detail: {
                is_running: false,
                status: 'idle',
                current_phase_message: 'Tasks purged - agent idle'
            }
        }));
    }
    
    showLoading(buttonId, loadingText) {
        const button = document.getElementById(buttonId);
        if (button) {
            button.disabled = true;
            button.dataset.originalText = button.textContent;
            button.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${loadingText}`;
        }
    }
    
    hideLoading(buttonId, originalText) {
        const button = document.getElementById(buttonId);
        if (button) {
            button.disabled = false;
            button.innerHTML = button.dataset.originalText || originalText;
        }
    }
    
    showNotification(message, type = 'info') {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `utility-notification utility-notification--${type}`;
        notification.textContent = message;
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: var(--glass-bg);
            backdrop-filter: blur(12px);
            border: 1px solid var(--glass-border);
            border-radius: var(--border-radius);
            padding: var(--space-3);
            color: var(--text-primary);
            font-size: 0.9rem;
            z-index: 10001;
            max-width: 300px;
            animation: slideInRight 0.3s ease-out;
        `;
        
        // Add type-specific styling
        if (type === 'success') {
            notification.style.borderColor = 'var(--accent-green)';
        } else if (type === 'error') {
            notification.style.borderColor = 'var(--accent-red)';
        } else if (type === 'warning') {
            notification.style.borderColor = 'var(--accent-orange)';
        }
        
        document.body.appendChild(notification);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (notification.parentNode) {
                notification.style.animation = 'slideOutRight 0.3s ease-out';
                setTimeout(() => {
                    if (notification.parentNode) {
                        notification.parentNode.removeChild(notification);
                    }
                }, 300);
            }
        }, 5000);
    }
}

// ===== CSS STYLES =====

// Add required CSS animations and styles
const utilityHandlersStyle = document.createElement('style');
utilityHandlersStyle.textContent = `
    @keyframes slideInRight {
        from {
            opacity: 0;
            transform: translateX(100px);
        }
        to {
            opacity: 1;
            transform: translateX(0);
        }
    }
    
    @keyframes slideOutRight {
        from {
            opacity: 1;
            transform: translateX(0);
        }
        to {
            opacity: 0;
            transform: translateX(100px);
        }
    }
    
    .utility-modal-overlay {
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0, 0, 0, 0.6);
        backdrop-filter: blur(4px);
    }
    
    .utility-modal-content {
        position: relative;
        background: var(--glass-bg);
        backdrop-filter: blur(24px);
        border: 1px solid var(--glass-border);
        border-radius: var(--border-radius-lg);
        box-shadow: var(--glass-shadow-hover);
        max-width: 600px;
        max-height: 80vh;
        overflow: hidden;
    }
    
    .utility-modal-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: var(--space-4);
        border-bottom: 1px solid var(--glass-border);
    }
    
    .utility-modal-header h3 {
        margin: 0;
        color: var(--text-primary);
    }
    
    .utility-modal-close {
        background: none;
        border: none;
        color: var(--text-secondary);
        font-size: 1.5rem;
        cursor: pointer;
        padding: var(--space-1);
    }
    
    .utility-modal-close:hover {
        color: var(--text-primary);
    }
    
    .utility-modal-body {
        padding: var(--space-4);
        max-height: 60vh;
        overflow-y: auto;
    }
    
    .status-summary {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
        gap: var(--space-3);
        margin-bottom: var(--space-4);
    }
    
    .status-item {
        display: flex;
        justify-content: space-between;
        padding: var(--space-2);
        background: rgba(255, 255, 255, 0.05);
        border-radius: var(--border-radius);
    }
    
    .status-label {
        color: var(--text-secondary);
        font-size: 0.9rem;
    }
    
    .status-value {
        color: var(--text-primary);
        font-weight: var(--font-weight-semibold);
    }
    
    .worker-details pre {
        background: rgba(0, 0, 0, 0.3);
        padding: var(--space-3);
        border-radius: var(--border-radius);
        color: var(--text-secondary);
        font-size: 0.8rem;
        overflow-x: auto;
        max-height: 300px;
        overflow-y: auto;
    }
    
    .form-group {
        margin-bottom: var(--space-4);
    }
    
    .form-group label {
        display: block;
        margin-bottom: var(--space-2);
        color: var(--text-primary);
        font-weight: var(--font-weight-medium);
    }
    
    .form-group input[type="number"] {
        width: 100%;
        padding: var(--space-2);
        background: rgba(255, 255, 255, 0.1);
        border: 1px solid var(--glass-border);
        border-radius: var(--border-radius);
        color: var(--text-primary);
        font-size: 0.9rem;
    }
    
    .checkbox-group {
        display: flex;
        flex-direction: column;
        gap: var(--space-2);
    }
    
    .checkbox-group label {
        display: flex;
        align-items: center;
        gap: var(--space-2);
        margin-bottom: 0;
        font-weight: normal;
    }
    
    .checkbox-group input[type="checkbox"] {
        margin: 0;
    }
    
    .modal-actions {
        display: flex;
        gap: var(--space-3);
        justify-content: flex-end;
        margin-top: var(--space-4);
        padding-top: var(--space-4);
        border-top: 1px solid var(--glass-border);
    }
    
    .btn {
        padding: var(--space-2) var(--space-4);
        border: none;
        border-radius: var(--border-radius);
        cursor: pointer;
        font-size: 0.9rem;
        font-weight: var(--font-weight-medium);
        transition: all 0.2s ease;
    }
    
    .btn-primary {
        background: var(--accent-blue);
        color: white;
    }
    
    .btn-primary:hover {
        background: var(--accent-blue-hover, #0056b3);
    }
    
    .btn-secondary {
        background: rgba(255, 255, 255, 0.1);
        color: var(--text-primary);
        border: 1px solid var(--glass-border);
    }
    
    .btn-secondary:hover {
        background: rgba(255, 255, 255, 0.2);
    }
    
    .btn-danger {
        background: var(--accent-red);
        color: white;
    }
    
    .btn-danger:hover {
        background: var(--accent-red-hover, #c82333);
    }
    
    .btn-sm {
        padding: var(--space-1) var(--space-2);
        font-size: 0.8rem;
    }
    
    .stuck-tasks-list {
        max-height: 400px;
        overflow-y: auto;
        margin-bottom: var(--space-4);
    }
    
    .stuck-task-item {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        padding: var(--space-3);
        background: rgba(255, 255, 255, 0.05);
        border-radius: var(--border-radius);
        margin-bottom: var(--space-2);
    }
    
    .task-info {
        flex: 1;
        color: var(--text-secondary);
        font-size: 0.9rem;
        line-height: 1.4;
    }
    
    .task-preview-list {
        max-height: 400px;
        overflow-y: auto;
        margin-bottom: var(--space-4);
    }
    
    .task-preview-item {
        padding: var(--space-3);
        background: rgba(255, 255, 255, 0.05);
        border-radius: var(--border-radius);
        margin-bottom: var(--space-2);
        color: var(--text-secondary);
        font-size: 0.9rem;
        line-height: 1.4;
    }
    
    .health-indicator {
        display: flex;
        align-items: center;
        gap: var(--space-2);
        padding: var(--space-2) var(--space-3);
        border-radius: var(--border-radius);
        font-size: 0.9rem;
        font-weight: var(--font-weight-medium);
    }
    
    .health-indicator.healthy {
        background: rgba(34, 197, 94, 0.1);
        color: var(--accent-green);
        border: 1px solid rgba(34, 197, 94, 0.3);
    }
    
    .health-indicator.issues {
        background: rgba(239, 68, 68, 0.1);
        color: var(--accent-red);
        border: 1px solid rgba(239, 68, 68, 0.3);
    }
    
    .health-checks, .connection-tests {
        display: flex;
        flex-direction: column;
        gap: var(--space-3);
        max-height: 400px;
        overflow-y: auto;
    }
    
    .health-check-item, .connection-test-item {
        padding: var(--space-3);
        background: rgba(255, 255, 255, 0.05);
        border-radius: var(--border-radius);
        border-left: 3px solid transparent;
    }
    
    .health-check-item.healthy, .connection-test-item.connected {
        border-left-color: var(--accent-green);
    }
    
    .health-check-item.unhealthy, .connection-test-item.failed {
        border-left-color: var(--accent-red);
    }
    
    .health-check-header, .connection-test-header {
        display: flex;
        align-items: center;
        gap: var(--space-2);
        margin-bottom: var(--space-2);
    }
    
    .health-status, .connection-status {
        margin-left: auto;
        padding: var(--space-1) var(--space-2);
        border-radius: var(--border-radius-sm);
        font-size: 0.8rem;
        font-weight: var(--font-weight-medium);
        text-transform: uppercase;
    }
    
    .health-check-message, .connection-test-message {
        color: var(--text-secondary);
        font-size: 0.9rem;
        margin-bottom: var(--space-2);
    }
    
    .health-check-details, .connection-test-details {
        background: rgba(0, 0, 0, 0.3);
        padding: var(--space-2);
        border-radius: var(--border-radius);
        font-family: var(--font-mono);
        font-size: 0.8rem;
        color: var(--text-secondary);
        overflow-x: auto;
    }
    
    .debug-info-sections {
        max-height: 500px;
        overflow-y: auto;
    }
    
    .debug-info-section {
        margin-bottom: var(--space-4);
        padding: var(--space-3);
        background: rgba(255, 255, 255, 0.05);
        border-radius: var(--border-radius);
    }
    
    .debug-info-section h4 {
        margin: 0 0 var(--space-3) 0;
        color: var(--text-primary);
        font-size: 0.9rem;
        font-weight: var(--font-weight-semibold);
    }
    
    .debug-info-content pre {
        background: rgba(0, 0, 0, 0.3);
        padding: var(--space-3);
        border-radius: var(--border-radius);
        font-family: var(--font-mono);
        font-size: 0.8rem;
        color: var(--text-secondary);
        overflow-x: auto;
        margin: 0;
    }
    
    .debug-info-value {
        color: var(--text-primary);
        font-size: 0.9rem;
    }
`;
document.head.appendChild(utilityHandlersStyle);

// Make available globally
window.UtilityManager = UtilityManager;
/* V2 TASKDISPLAY.JS - TASK-SPECIFIC STATUS AND LOG ISOLATION */

/**
 * TaskDisplayManager - Task-specific status and log isolation
 * 
 * ARCHITECTURE:
 * - Manages multiple concurrent task displays
 * - Provides task-specific log filtering and isolation
 * - Integrates with PhaseDisplayManager and ProgressDisplayManager
 * - Supports task switching and multi-task monitoring
 */
class TaskDisplayManager {
    constructor() {
        this.tasks = new Map();
        this.activeTaskId = null;
        this.taskHistory = [];
        
        // UI Elements
        this.taskContainer = document.getElementById('task-container');
        this.taskSwitcher = document.getElementById('task-switcher');
        this.taskTabs = document.getElementById('task-tabs');
        
        // Configuration
        this.maxTasks = 10; // Maximum number of concurrent tasks to track
        this.taskRetention = 24 * 60 * 60 * 1000; // 24 hours
        
        this.init();
    }
    
    init() {
        this.setupEventListeners();
        this.createTaskContainer();
        
        // Register with component coordinator
        if (window.displayCoordinator) {
            window.displayCoordinator.registerComponent('TaskDisplayManager', this, {
                priority: 60,
                dependencies: []
            });
        }
        
        console.log('📋 TaskDisplayManager initialized');
    }
    
    setupEventListeners() {
        // Use centralized EventListenerService
        EventListenerService.setupStandardListeners(this, {
            customEvents: [
                {
                    event: 'task_started',
                    handler: (e) => this.handleTaskStarted(e.detail)
                },
                {
                    event: 'task_completed',
                    handler: (e) => this.handleTaskCompleted(e.detail)
                },
                {
                    event: 'task_error',
                    handler: (e) => this.handleTaskError(e.detail)
                },
                {
                    event: 'log',
                    handler: (e) => this.handleLogEvent(e.detail)
                },
                {
                    event: 'phase_start',
                    handler: (e) => this.handlePhaseEvent('start', e.detail)
                },
                {
                    event: 'phase_complete',
                    handler: (e) => this.handlePhaseEvent('complete', e.detail)
                },
                {
                    event: 'phase_error',
                    handler: (e) => this.handlePhaseEvent('error', e.detail)
                },
                {
                    event: 'progress_update',
                    handler: (e) => this.handleProgressEvent(e.detail)
                },
                {
                    event: 'agent_status_update',
                    handler: (e) => this.handleAgentStatusUpdate(e.detail)
                }
            ]
        });
    }
    
    createTaskContainer() {
        // Try to integrate with existing header first
        this.integrateWithExistingHeader();
        
        // If no integration possible, create minimal task switcher
        if (!this.taskSwitcher) {
            this.createMinimalTaskSwitcher();
        }
    }
    
    integrateWithExistingHeader() {
        // Try to integrate with agent controls header
        const agentHeader = document.querySelector('.agent-controls-header');
        if (agentHeader && !document.getElementById('task-switcher')) {
            const taskSwitcher = document.createElement('div');
            taskSwitcher.id = 'task-switcher';
            taskSwitcher.className = 'task-switcher-compact';
            taskSwitcher.innerHTML = `
                <select id="task-selector" class="glass-select glass-select--sm">
                    <option value="">Current Task</option>
                </select>
                <button id="task-info-btn" class="glass-button glass-button--sm" title="Task Information" style="display: none;">
                    <i class="fas fa-info-circle"></i>
                </button>
            `;
            
            agentHeader.appendChild(taskSwitcher);
            
            this.taskSwitcher = taskSwitcher;
            this.taskSelector = document.getElementById('task-selector');
            this.taskInfoBtn = document.getElementById('task-info-btn');
            
            // Add event listeners
            this.taskSelector.addEventListener('change', (e) => {
                this.switchToTask(e.target.value);
            });
            
            this.taskInfoBtn.addEventListener('click', () => {
                this.showTaskInfo();
            });
            
            console.log('📋 TaskDisplayManager integrated with agent header');
            return;
        }
        
        // Try to integrate with status footer
        const statusFooter = document.getElementById('agent-status-footer');
        if (statusFooter && !document.getElementById('task-switcher')) {
            const taskInfo = document.createElement('div');
            taskInfo.id = 'task-info-section';
            taskInfo.className = 'task-info-integrated';
            taskInfo.style.cssText = `
                margin-top: var(--space-2);
                padding-top: var(--space-2);
                border-top: 1px solid var(--glass-border-secondary);
                display: none;
            `;
            taskInfo.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: center; font-size: var(--font-size-xs);">
                    <span>Task: <span id="current-task-id" style="color: var(--text-secondary);">None</span></span>
                    <span id="task-duration" style="color: var(--text-tertiary);">--</span>
                </div>
            `;
            
            statusFooter.appendChild(taskInfo);
            
            this.taskInfoSection = taskInfo;
            this.currentTaskIdElement = document.getElementById('current-task-id');
            this.taskDurationElement = document.getElementById('task-duration');
            
            console.log('📋 TaskDisplayManager integrated with status footer');
            return;
        }
    }
    
    createMinimalTaskSwitcher() {
        // Create minimal floating task switcher as fallback
        const taskSwitcher = document.createElement('div');
        taskSwitcher.id = 'task-switcher-minimal';
        taskSwitcher.className = 'task-switcher-minimal';
        taskSwitcher.style.cssText = `
            position: fixed;
            top: 10px;
            right: 10px;
            background: var(--glass-bg-primary);
            border: 1px solid var(--glass-border-primary);
            border-radius: var(--radius-base);
            padding: var(--space-2);
            z-index: 1000;
            display: none;
            backdrop-filter: blur(10px);
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
        `;
        taskSwitcher.innerHTML = `
            <div style="display: flex; align-items: center; gap: var(--space-2);">
                <i class="fas fa-tasks" style="color: var(--text-tertiary);"></i>
                <select id="task-selector" class="glass-select glass-select--sm" style="min-width: 120px;">
                    <option value="">No Tasks</option>
                </select>
                <button id="task-close-btn" style="background: none; border: none; color: var(--text-tertiary); cursor: pointer;">
                    <i class="fas fa-times"></i>
                </button>
            </div>
        `;
        
        document.body.appendChild(taskSwitcher);
        
        this.taskSwitcher = taskSwitcher;
        this.taskSelector = document.getElementById('task-selector');
        
        // Add event listeners
        this.taskSelector.addEventListener('change', (e) => {
            this.switchToTask(e.target.value);
        });
        
        const closeBtn = taskSwitcher.querySelector('#task-close-btn');
        closeBtn.addEventListener('click', () => {
            taskSwitcher.style.display = 'none';
        });
        
        console.log('📋 TaskDisplayManager created minimal switcher');
    }
    
    handleTaskStarted(data) {
        let { task_id, task_type, preferences, timestamp } = data;
        
        if (!task_id) {
            // Generate a task ID if not provided
            task_id = this.generateTaskId();
        }
        
        // Ensure task_id is a string
        if (typeof task_id === 'object') {
            console.warn('Task ID received as object:', task_id);
            task_id = task_id.toString();
        }
        
        console.log(`📋 Task started: ${task_id}`, data);
        
        const task = {
            id: task_id,
            type: task_type || 'agent_execution',
            status: 'running',
            startTime: new Date(timestamp || Date.now()),
            endTime: null,
            duration: null,
            preferences: preferences,
            human_readable_name: null, // Will be fetched from API
            logs: [],
            phases: new Map(),
            progress: new Map(),
            errors: [],
            statistics: {
                totalLogs: 0,
                errorCount: 0,
                warningCount: 0,
                phaseCount: 0,
                completedPhases: 0
            }
        };
        
        // Fetch human-readable name from API
        this.fetchTaskName(task_id).then(name => {
            if (name) {
                task.human_readable_name = name;
                this.updateTaskSelector();
            }
        }).catch(err => {
            console.warn('Failed to fetch task name:', err);
        });
        
        this.tasks.set(task_id, task);
        this.activeTaskId = task_id;
        
        // Create task display
        this.createTaskDisplay(task);
        
        // Update UI
        this.updateTaskSelector();
        this.switchToTask(task_id);
        
        // Add to history
        this.taskHistory.push({
            action: 'started',
            taskId: task_id,
            timestamp: task.startTime,
            data: data
        });
        
        // Clean up old tasks
        this.cleanupOldTasks();
    }
    
    handleTaskCompleted(data) {
        const { task_id, result, timestamp } = data;
        const task = this.tasks.get(task_id);
        
        if (!task) return;
        
        console.log(`✅ Task completed: ${task_id}`, data);
        
        task.status = 'completed';
        task.endTime = new Date(timestamp || Date.now());
        task.duration = task.endTime - task.startTime;
        task.result = result;
        
        // Update task display
        this.updateTaskDisplay(task);
        
        // Add to history
        this.taskHistory.push({
            action: 'completed',
            taskId: task_id,
            timestamp: task.endTime,
            data: data
        });
        
        // Auto-hide completed tasks after delay
        setTimeout(() => {
            this.archiveTask(task_id);
        }, 30000); // 30 seconds
    }
    
    handleTaskError(data) {
        const { task_id, error, traceback, timestamp } = data;
        const task = this.tasks.get(task_id);
        
        if (!task) return;
        
        console.error(`❌ Task error: ${task_id}`, data);
        
        task.status = 'error';
        task.endTime = new Date(timestamp || Date.now());
        task.duration = task.endTime - task.startTime;
        task.errors.push({
            error: error,
            traceback: traceback,
            timestamp: task.endTime
        });
        
        // Update task display
        this.updateTaskDisplay(task);
        
        // Add to history
        this.taskHistory.push({
            action: 'error',
            taskId: task_id,
            timestamp: task.endTime,
            data: data
        });
    }
    
    handleLogEvent(data) {
        const { task_id, message, level, timestamp, component } = data;
        
        if (!task_id) return;
        
        const task = this.tasks.get(task_id);
        if (!task) {
            // Create task if it doesn't exist (for logs that arrive before task_started event)
            this.handleTaskStarted({ task_id: task_id, task_type: 'unknown' });
            return;
        }
        
        // Add log to task
        const logEntry = {
            message: message,
            level: level,
            timestamp: new Date(timestamp || Date.now()),
            component: component
        };
        
        task.logs.push(logEntry);
        task.statistics.totalLogs++;
        
        if (level === 'ERROR' || level === 'CRITICAL') {
            task.statistics.errorCount++;
        } else if (level === 'WARNING') {
            task.statistics.warningCount++;
        }
        
        // Limit log history per task
        if (task.logs.length > 1000) {
            task.logs.shift();
        }
        
        // Update task display if it's the active task
        if (this.activeTaskId === task_id) {
            this.updateTaskLogs(task);
        }
    }
    
    handlePhaseEvent(eventType, data) {
        const { task_id, phase_name } = data;
        
        if (!task_id) return;
        
        const task = this.tasks.get(task_id);
        if (!task) return;
        
        // Update phase information
        let phase = task.phases.get(phase_name);
        if (!phase) {
            phase = {
                name: phase_name,
                status: 'pending',
                startTime: null,
                endTime: null,
                duration: null,
                progress: { current: 0, total: 0 }
            };
            task.phases.set(phase_name, phase);
            task.statistics.phaseCount++;
        }
        
        switch (eventType) {
            case 'start':
                phase.status = 'running';
                phase.startTime = new Date(data.start_time || Date.now());
                break;
            case 'complete':
                phase.status = 'completed';
                phase.endTime = new Date(data.end_time || Date.now());
                phase.duration = phase.endTime - phase.startTime;
                task.statistics.completedPhases++;
                break;
            case 'error':
                phase.status = 'error';
                phase.endTime = new Date(data.timestamp || Date.now());
                phase.duration = phase.endTime - phase.startTime;
                phase.error = data.error;
                break;
        }
        
        // Update task display if it's the active task
        if (this.activeTaskId === task_id) {
            this.updateTaskPhases(task);
        }
    }
    
    handleProgressEvent(data) {
        const { task_id, operation, current, total, percentage } = data;
        
        if (!task_id) return;
        
        const task = this.tasks.get(task_id);
        if (!task) return;
        
        // Update progress information
        const progressId = operation || 'default';
        task.progress.set(progressId, {
            operation: operation,
            current: current || 0,
            total: total || 100,
            percentage: percentage || (total > 0 ? (current / total) * 100 : 0),
            timestamp: new Date()
        });
        
        // Update task display if it's the active task
        if (this.activeTaskId === task_id) {
            this.updateTaskProgress(task);
        }
    }
    
    handleAgentStatusUpdate(data) {
        const { is_running, task_id } = data;
        
        if (is_running && task_id && !this.tasks.has(task_id)) {
            // New task detected
            this.handleTaskStarted({ 
                task_id: task_id, 
                task_type: 'agent_execution',
                timestamp: Date.now()
            });
        }
    }
    
    createTaskDisplay(task) {
        // Instead of creating complex displays, just update integrated components
        this.updateIntegratedTaskDisplay(task);
        
        // Show task switcher if it was hidden
        if (this.taskSwitcher) {
            this.taskSwitcher.style.display = 'block';
        }
        
        // Show task info section if available
        if (this.taskInfoSection) {
            this.taskInfoSection.style.display = 'block';
        }
        
        // Show task info button if available
        if (this.taskInfoBtn) {
            this.taskInfoBtn.style.display = 'inline-block';
        }
    }
    
    updateIntegratedTaskDisplay(task) {
        // Update task selector
        this.updateTaskSelector();
        
        // Update integrated task info
        if (this.currentTaskIdElement) {
            this.currentTaskIdElement.textContent = task.id;
        }
        
        if (this.taskDurationElement && task.startTime) {
            const duration = new Date() - task.startTime;
            this.taskDurationElement.textContent = this.formatDuration(duration);
        }
        
        // Update task info button tooltip
        if (this.taskInfoBtn) {
            this.taskInfoBtn.title = `Task: ${task.id} | Status: ${task.status} | Type: ${task.type}`;
        }
    }
    
    showTaskInfo() {
        if (!this.activeTaskId) return;
        
        const task = this.tasks.get(this.activeTaskId);
        if (!task) return;
        
        // Create simple task info modal/tooltip
        const existingModal = document.getElementById('task-info-modal');
        if (existingModal) {
            existingModal.remove();
        }
        
        const modal = document.createElement('div');
        modal.id = 'task-info-modal';
        modal.style.cssText = `
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: var(--glass-bg-primary);
            border: 1px solid var(--glass-border-primary);
            border-radius: var(--radius-lg);
            padding: var(--space-4);
            z-index: 10000;
            backdrop-filter: blur(10px);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
            max-width: 400px;
            width: 90%;
        `;
        
        modal.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: var(--space-3);">
                <h4 style="margin: 0; color: var(--text-primary);">Task Information</h4>
                <button id="task-info-close" style="background: none; border: none; color: var(--text-tertiary); cursor: pointer; font-size: var(--font-size-lg);">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            <div style="color: var(--text-secondary); font-size: var(--font-size-sm); line-height: 1.5;">
                <div style="margin-bottom: var(--space-2);"><strong>ID:</strong> ${task.id}</div>
                <div style="margin-bottom: var(--space-2);"><strong>Type:</strong> ${task.type}</div>
                <div style="margin-bottom: var(--space-2);"><strong>Status:</strong> 
                    <span style="color: ${task.status === 'running' ? 'var(--success-green)' : task.status === 'error' ? 'var(--error-red)' : 'var(--text-primary)'};">
                        ${task.status}
                    </span>
                </div>
                <div style="margin-bottom: var(--space-2);"><strong>Started:</strong> ${task.startTime.toLocaleString()}</div>
                ${task.endTime ? `<div style="margin-bottom: var(--space-2);"><strong>Ended:</strong> ${task.endTime.toLocaleString()}</div>` : ''}
                <div style="margin-bottom: var(--space-2);"><strong>Duration:</strong> ${this.formatDuration(task.duration || (new Date() - task.startTime))}</div>
                <div style="margin-bottom: var(--space-2);"><strong>Logs:</strong> ${task.statistics.totalLogs}</div>
                <div style="margin-bottom: var(--space-2);"><strong>Phases:</strong> ${task.statistics.completedPhases}/${task.statistics.phaseCount}</div>
                <div><strong>Errors:</strong> ${task.statistics.errorCount}</div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        // Add close functionality
        const closeBtn = modal.querySelector('#task-info-close');
        const closeModal = () => {
            modal.remove();
        };
        
        closeBtn.addEventListener('click', closeModal);
        
        // Close on outside click
        setTimeout(() => {
            document.addEventListener('click', function outsideClick(e) {
                if (!modal.contains(e.target)) {
                    closeModal();
                    document.removeEventListener('click', outsideClick);
                }
            });
        }, 100);
        
        // Close on escape key
        document.addEventListener('keydown', function escapeKey(e) {
            if (e.key === 'Escape') {
                closeModal();
                document.removeEventListener('keydown', escapeKey);
            }
        });
    }
    
    updateTaskDisplay(task) {
        const taskElement = document.getElementById(`task-${task.id}`);
        if (!taskElement) return;
        
        // Update status
        const statusIcon = taskElement.querySelector('.task-status-icon');
        const statusText = taskElement.querySelector('.task-status');
        
        const statusIcons = {
            'running': 'fas fa-play-circle',
            'completed': 'fas fa-check-circle',
            'error': 'fas fa-exclamation-circle',
            'cancelled': 'fas fa-stop-circle'
        };
        
        if (statusIcon) {
            statusIcon.className = statusIcons[task.status] || 'fas fa-question-circle';
        }
        
        if (statusText) {
            statusText.textContent = task.status;
            statusText.className = `task-status task-status-${task.status}`;
        }
        
        // Update statistics
        this.updateTaskStatistics(task);
    }
    
    updateTaskStatistics(task) {
        const logCountElement = document.getElementById(`task-${task.id}-log-count`);
        const phaseCountElement = document.getElementById(`task-${task.id}-phase-count`);
        const errorCountElement = document.getElementById(`task-${task.id}-error-count`);
        
        if (logCountElement) {
            logCountElement.textContent = task.statistics.totalLogs;
        }
        
        if (phaseCountElement) {
            phaseCountElement.textContent = `${task.statistics.completedPhases}/${task.statistics.phaseCount}`;
        }
        
        if (errorCountElement) {
            errorCountElement.textContent = task.statistics.errorCount;
        }
    }
    
    updateTaskLogs(task) {
        const logsContainer = document.getElementById(`task-${task.id}-logs`);
        if (!logsContainer) return;
        
        // Show recent logs (last 10)
        const recentLogs = task.logs.slice(-10);
        
        if (recentLogs.length === 0) {
            logsContainer.innerHTML = '<div class="no-logs">No logs yet</div>';
            return;
        }
        
        logsContainer.innerHTML = recentLogs.map(log => `
            <div class="task-log-entry log-level-${log.level.toLowerCase()}">
                <span class="log-time">${log.timestamp.toLocaleTimeString()}</span>
                <span class="log-level">${log.level}</span>
                <span class="log-message">${this.escapeHtml(log.message)}</span>
            </div>
        `).join('');
    }
    
    updateTaskPhases(task) {
        const phasesContainer = document.getElementById(`task-${task.id}-phases`);
        if (!phasesContainer) return;
        
        const phases = Array.from(task.phases.values());
        
        if (phases.length === 0) {
            phasesContainer.innerHTML = '<div class="no-phases">No phases yet</div>';
            return;
        }
        
        phasesContainer.innerHTML = phases.map(phase => `
            <div class="task-phase-entry phase-status-${phase.status}">
                <i class="fas ${this.getPhaseIcon(phase.status)}"></i>
                <span class="phase-name">${phase.name}</span>
                <span class="phase-status">${phase.status}</span>
                ${phase.duration ? `<span class="phase-duration">${this.formatDuration(phase.duration)}</span>` : ''}
            </div>
        `).join('');
    }
    
    updateTaskProgress(task) {
        const progressContainer = document.getElementById(`task-${task.id}-progress`);
        if (!progressContainer) return;
        
        const progressItems = Array.from(task.progress.values());
        
        if (progressItems.length === 0) {
            progressContainer.innerHTML = '<div class="no-progress">No progress data</div>';
            return;
        }
        
        progressContainer.innerHTML = progressItems.map(progress => `
            <div class="task-progress-entry">
                <div class="progress-header">
                    <span class="progress-operation">${progress.operation || 'Processing'}</span>
                    <span class="progress-percentage">${Math.round(progress.percentage)}%</span>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: ${progress.percentage}%"></div>
                </div>
                <div class="progress-details">
                    ${progress.current}/${progress.total}
                </div>
            </div>
        `).join('');
    }
    
    updateTaskSelector() {
        if (!this.taskSelector) return;
        
        const activeTasks = Array.from(this.tasks.values())
            .filter(task => task.status === 'running')
            .sort((a, b) => b.startTime - a.startTime);
        
        this.taskSelector.innerHTML = activeTasks.length > 0 
            ? activeTasks.map(task => `
                <option value="${task.id}" ${task.id === this.activeTaskId ? 'selected' : ''}>
                    ${task.human_readable_name || `Task ${task.id}`}
                </option>
            `).join('')
            : '<option value="">No active tasks</option>';
    }
    
    switchToTask(taskId) {
        if (!taskId || !this.tasks.has(taskId)) {
            this.activeTaskId = null;
            if (this.taskContainer) {
                this.showNoTasksMessage();
            }
            return;
        }
        
        this.activeTaskId = taskId;
        
        // Hide all task displays if a dedicated container exists
        if (this.taskContainer) {
            this.taskContainer.querySelectorAll('.task-display').forEach(element => {
                element.style.display = 'none';
            });
        }
        
        // Show selected task
        const taskElement = document.getElementById(`task-${taskId}`);
        if (taskElement) {
            taskElement.style.display = 'block';
        }
        
        // Hide no-tasks message if container exists
        if (this.taskContainer) {
            const noTasksMessage = this.taskContainer.querySelector('.no-tasks-message');
            if (noTasksMessage) {
                noTasksMessage.style.display = 'none';
            }
        }
        
        // Update task selector
        if (this.taskSelector) {
            this.taskSelector.value = taskId;
        }
    }
    
    closeTask(taskId) {
        const task = this.tasks.get(taskId);
        if (!task) return;
        
        // Remove task display
        const taskElement = document.getElementById(`task-${taskId}`);
        if (taskElement) {
            taskElement.remove();
        }
        
        // Remove from tasks map
        this.tasks.delete(taskId);
        
        // Update active task
        if (this.activeTaskId === taskId) {
            const remainingTasks = Array.from(this.tasks.keys());
            this.activeTaskId = remainingTasks.length > 0 ? remainingTasks[0] : null;
            
            if (this.activeTaskId) {
                this.switchToTask(this.activeTaskId);
            } else {
                this.showNoTasksMessage();
            }
        }
        
        // Update task selector
        this.updateTaskSelector();
    }
    
    archiveTask(taskId) {
        const task = this.tasks.get(taskId);
        if (!task || task.status === 'running') return;
        
        // Move to history and remove from active tasks
        this.taskHistory.push({
            action: 'archived',
            taskId: taskId,
            timestamp: new Date(),
            task: { ...task }
        });
        
        this.closeTask(taskId);
    }
    
    clearCompletedTasks() {
        const completedTasks = Array.from(this.tasks.values())
            .filter(task => task.status === 'completed' || task.status === 'error');
        
        completedTasks.forEach(task => {
            this.archiveTask(task.id);
        });
        
        console.log(`📋 Cleared ${completedTasks.length} completed tasks`);
    }
    
    cleanupOldTasks() {
        const now = new Date();
        const tasksToRemove = [];
        
        this.tasks.forEach((task, taskId) => {
            if (task.status !== 'running' && 
                task.endTime && 
                (now - task.endTime) > this.taskRetention) {
                tasksToRemove.push(taskId);
            }
        });
        
        tasksToRemove.forEach(taskId => {
            this.archiveTask(taskId);
        });
        
        // Limit total number of tasks
        if (this.tasks.size > this.maxTasks) {
            const oldestTasks = Array.from(this.tasks.values())
                .filter(task => task.status !== 'running')
                .sort((a, b) => a.startTime - b.startTime)
                .slice(0, this.tasks.size - this.maxTasks);
            
            oldestTasks.forEach(task => {
                this.archiveTask(task.id);
            });
        }
    }
    
    showNoTasksMessage() {
        if (!this.taskContainer) return;
        // Hide all task displays
        this.taskContainer.querySelectorAll('.task-display').forEach(element => {
            element.style.display = 'none';
        });
        
        // Show no-tasks message
        const noTasksMessage = this.taskContainer.querySelector('.no-tasks-message');
        if (noTasksMessage) {
            noTasksMessage.style.display = 'block';
        }
    }
    
    async fetchTaskName(taskId) {
        try {
            const response = await fetch(`/api/v2/agent/status/${taskId}`);
            if (response.ok) {
                const data = await response.json();
                return data.human_readable_name;
            }
        } catch (error) {
            console.warn('Failed to fetch task name:', error);
        }
        return null;
    }
    
    generateTaskId() {
        return `task_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }
    
    getPhaseIcon(status) {
        const icons = {
            'pending': 'fa-clock',
            'running': 'fa-spinner fa-spin',
            'completed': 'fa-check',
            'error': 'fa-exclamation-triangle'
        };
        return icons[status] || 'fa-question';
    }
    
    formatDuration(milliseconds) {
        // Use centralized DurationFormatter service
        return DurationFormatter.format(milliseconds);
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    // === PUBLIC API ===
    
    getTask(taskId) {
        return this.tasks.get(taskId);
    }
    
    getAllTasks() {
        return Array.from(this.tasks.values());
    }
    
    getActiveTasks() {
        return Array.from(this.tasks.values()).filter(task => task.status === 'running');
    }
    
    getTaskHistory() {
        return [...this.taskHistory];
    }
    
    updateTaskLogs(taskId, logData) {
        this.handleLogEvent({ ...logData, task_id: taskId });
    }
    
    updateTaskStatus(taskId, status, data = {}) {
        const task = this.tasks.get(taskId);
        if (!task) return;
        
        task.status = status;
        
        if (status === 'completed') {
            this.handleTaskCompleted({ task_id: taskId, ...data });
        } else if (status === 'error') {
            this.handleTaskError({ task_id: taskId, ...data });
        }
    }
    
    getTaskStatistics() {
        const stats = {
            total: this.tasks.size,
            running: 0,
            completed: 0,
            error: 0,
            totalLogs: 0,
            totalPhases: 0
        };
        
        this.tasks.forEach(task => {
            stats[task.status] = (stats[task.status] || 0) + 1;
            stats.totalLogs += task.statistics.totalLogs;
            stats.totalPhases += task.statistics.phaseCount;
        });
        
        return stats;
    }
}

// Make globally available
window.TaskDisplayManager = TaskDisplayManager;
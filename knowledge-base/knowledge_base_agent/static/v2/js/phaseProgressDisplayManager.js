/**
 * Phase and Progress Display Manager
 * 
 * Provides comprehensive real-time phase status and progress visualization with:
 * - PhaseDisplayManager for real-time phase status visualization
 * - ProgressDisplayManager for progress bars and ETC calculations
 * - ExecutionPlanManager integration for visual phase progress tracking
 * - TaskDisplayManager for task-specific status and log isolation
 * - Status indicator components with real-time updates
 * - Error state visualization with expandable error details
 */

class PhaseDisplayManager {
    constructor(container) {
        this.container = container;
        this.phases = new Map();
        this.currentPhase = null;
        this.phaseHistory = [];
        
        this.initialize();
    }
    
    initialize() {
        console.log('🎭 Initializing Phase Display Manager...');
        
        this.createPhaseDisplay();
        this.setupEventListeners();
        
        console.log('✅ Phase Display Manager initialized');
    }
    
    createPhaseDisplay() {
        if (!this.container) return;
        
        this.container.innerHTML = `
            <div class="phase-display">
                <div class="phase-header">
                    <h5 class="phase-title">Processing Phases</h5>
                    <div class="phase-controls">
                        <button class="btn btn-sm btn-outline-secondary" id="phase-history-btn" title="View phase history">
                            <i class="bi bi-clock-history"></i>
                        </button>
                        <button class="btn btn-sm btn-outline-secondary" id="phase-reset-btn" title="Reset phase display">
                            <i class="bi bi-arrow-clockwise"></i>
                        </button>
                    </div>
                </div>
                <div class="phase-timeline" id="phase-timeline"></div>
                <div class="current-phase" id="current-phase">
                    <div class="phase-status">Ready</div>
                    <div class="phase-message">Waiting for agent to start...</div>
                </div>
            </div>
        `;
        
        this.elements = {
            timeline: this.container.querySelector('#phase-timeline'),
            currentPhase: this.container.querySelector('#current-phase'),
            historyBtn: this.container.querySelector('#phase-history-btn'),
            resetBtn: this.container.querySelector('#phase-reset-btn')
        };
    }
    
    setupEventListeners() {
        // Phase update events
        document.addEventListener('phase_update', (event) => {
            this.handlePhaseUpdate(event.detail);
        });
        
        document.addEventListener('phase_start', (event) => {
            this.handlePhaseStart(event.detail);
        });
        
        document.addEventListener('phase_complete', (event) => {
            this.handlePhaseComplete(event.detail);
        });
        
        document.addEventListener('phase_error', (event) => {
            this.handlePhaseError(event.detail);
        });
        
        // Control buttons
        if (this.elements.historyBtn) {
            this.elements.historyBtn.addEventListener('click', () => this.showPhaseHistory());
        }
        
        if (this.elements.resetBtn) {
            this.elements.resetBtn.addEventListener('click', () => this.resetDisplay());
        }
    }
    
    handlePhaseUpdate(data) {
        const phaseId = data.phase_id || data.phaseId;
        const status = data.status;
        const message = data.message || '';
        
        this.updatePhase(phaseId, status, message, data);
    }
    
    handlePhaseStart(data) {
        const phaseId = data.phase_id || data.phaseId;
        this.updatePhase(phaseId, 'active', data.message || 'Starting...', data);
    }
    
    handlePhaseComplete(data) {
        const phaseId = data.phase_id || data.phaseId;
        this.updatePhase(phaseId, 'completed', data.message || 'Completed', data);
    }
    
    handlePhaseError(data) {
        const phaseId = data.phase_id || data.phaseId;
        this.updatePhase(phaseId, 'error', data.message || 'Error occurred', data);
    }
    
    updatePhase(phaseId, status, message, data = {}) {
        if (!phaseId) return;
        
        const phase = {
            id: phaseId,
            status,
            message,
            timestamp: new Date(),
            data: { ...data }
        };
        
        this.phases.set(phaseId, phase);
        
        if (status === 'active' || status === 'in_progress') {
            this.currentPhase = phase;
        }
        
        this.phaseHistory.push({ ...phase });
        
        this.updateDisplay();
    }
    
    updateDisplay() {
        this.updateTimeline();
        this.updateCurrentPhase();
    }
    
    updateTimeline() {
        if (!this.elements.timeline) return;
        
        const timeline = this.elements.timeline;
        timeline.innerHTML = '';
        
        // Create timeline items for each phase
        this.phases.forEach((phase, phaseId) => {
            const timelineItem = document.createElement('div');
            timelineItem.className = `timeline-item phase-${phase.status}`;
            timelineItem.innerHTML = `
                <div class="timeline-marker">
                    <i class="bi ${this.getPhaseIcon(phase.status)}"></i>
                </div>
                <div class="timeline-content">
                    <div class="timeline-title">${this.formatPhaseId(phaseId)}</div>
                    <div class="timeline-message">${phase.message}</div>
                    <div class="timeline-time">${phase.timestamp.toLocaleTimeString()}</div>
                </div>
            `;
            
            // Add click handler for details
            timelineItem.addEventListener('click', () => {
                this.showPhaseDetails(phase);
            });
            
            timeline.appendChild(timelineItem);
        });
    }
    
    updateCurrentPhase() {
        if (!this.elements.currentPhase) return;
        
        const currentPhase = this.elements.currentPhase;
        
        if (this.currentPhase) {
            currentPhase.innerHTML = `
                <div class="phase-status phase-${this.currentPhase.status}">
                    <i class="bi ${this.getPhaseIcon(this.currentPhase.status)}"></i>
                    ${this.currentPhase.status.toUpperCase()}
                </div>
                <div class="phase-message">${this.currentPhase.message}</div>
                <div class="phase-details">
                    <small class="text-muted">
                        Phase: ${this.formatPhaseId(this.currentPhase.id)} | 
                        Started: ${this.currentPhase.timestamp.toLocaleTimeString()}
                    </small>
                </div>
            `;
        } else {
            currentPhase.innerHTML = `
                <div class="phase-status">Ready</div>
                <div class="phase-message">Waiting for agent to start...</div>
            `;
        }
    }
    
    getPhaseIcon(status) {
        const icons = {
            'pending': 'bi-clock',
            'active': 'bi-play-circle-fill',
            'in_progress': 'bi-arrow-repeat',
            'completed': 'bi-check-circle-fill',
            'error': 'bi-exclamation-triangle-fill',
            'skipped': 'bi-skip-forward-circle',
            'interrupted': 'bi-pause-circle-fill'
        };
        return icons[status] || 'bi-circle';
    }
    
    formatPhaseId(phaseId) {
        return phaseId.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    }
    
    showPhaseDetails(phase) {
        const modal = document.createElement('div');
        modal.className = 'modal fade';
        modal.innerHTML = `
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">Phase Details: ${this.formatPhaseId(phase.id)}</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <div class="row">
                            <div class="col-md-6">
                                <strong>Status:</strong> 
                                <span class="badge bg-${this.getStatusColor(phase.status)}">${phase.status}</span>
                            </div>
                            <div class="col-md-6">
                                <strong>Timestamp:</strong> ${phase.timestamp.toLocaleString()}
                            </div>
                        </div>
                        <div class="mt-3">
                            <strong>Message:</strong>
                            <p>${phase.message}</p>
                        </div>
                        ${Object.keys(phase.data).length > 0 ? `
                            <div class="mt-3">
                                <strong>Additional Data:</strong>
                                <pre class="bg-light p-2 rounded"><code>${JSON.stringify(phase.data, null, 2)}</code></pre>
                            </div>
                        ` : ''}
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                    </div>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        const bootstrapModal = new bootstrap.Modal(modal);
        bootstrapModal.show();
        
        modal.addEventListener('hidden.bs.modal', () => {
            document.body.removeChild(modal);
        });
    }
    
    showPhaseHistory() {
        const modal = document.createElement('div');
        modal.className = 'modal fade';
        modal.innerHTML = `
            <div class="modal-dialog modal-xl">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">Phase History</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <div class="table-responsive">
                            <table class="table table-striped">
                                <thead>
                                    <tr>
                                        <th>Time</th>
                                        <th>Phase</th>
                                        <th>Status</th>
                                        <th>Message</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${this.phaseHistory.map(phase => `
                                        <tr>
                                            <td>${phase.timestamp.toLocaleTimeString()}</td>
                                            <td>${this.formatPhaseId(phase.id)}</td>
                                            <td><span class="badge bg-${this.getStatusColor(phase.status)}">${phase.status}</span></td>
                                            <td>${phase.message}</td>
                                        </tr>
                                    `).join('')}
                                </tbody>
                            </table>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                    </div>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        const bootstrapModal = new bootstrap.Modal(modal);
        bootstrapModal.show();
        
        modal.addEventListener('hidden.bs.modal', () => {
            document.body.removeChild(modal);
        });
    }
    
    getStatusColor(status) {
        const colors = {
            'pending': 'secondary',
            'active': 'primary',
            'in_progress': 'info',
            'completed': 'success',
            'error': 'danger',
            'skipped': 'warning',
            'interrupted': 'dark'
        };
        return colors[status] || 'secondary';
    }
    
    resetDisplay() {
        this.phases.clear();
        this.currentPhase = null;
        this.phaseHistory = [];
        this.updateDisplay();
        
        console.log('🔄 Phase display reset');
    }
}

class ProgressDisplayManager {
    constructor(container) {
        this.container = container;
        this.progressBars = new Map();
        this.etcCalculator = new ETCCalculator();
        
        this.initialize();
    }
    
    initialize() {
        console.log('📊 Initializing Progress Display Manager...');
        
        this.createProgressDisplay();
        this.setupEventListeners();
        
        console.log('✅ Progress Display Manager initialized');
    }
    
    createProgressDisplay() {
        if (!this.container) return;
        
        this.container.innerHTML = `
            <div class="progress-display">
                <div class="progress-header">
                    <h5 class="progress-title">Progress Overview</h5>
                    <div class="progress-summary" id="progress-summary">
                        <span class="badge bg-info">Ready</span>
                    </div>
                </div>
                <div class="progress-bars" id="progress-bars"></div>
                <div class="etc-display" id="etc-display">
                    <div class="etc-item">
                        <span class="etc-label">Estimated Completion:</span>
                        <span class="etc-value" id="etc-time">--:--</span>
                    </div>
                    <div class="etc-item">
                        <span class="etc-label">Remaining:</span>
                        <span class="etc-value" id="etc-remaining">--</span>
                    </div>
                </div>
            </div>
        `;
        
        this.elements = {
            progressBars: this.container.querySelector('#progress-bars'),
            progressSummary: this.container.querySelector('#progress-summary'),
            etcTime: this.container.querySelector('#etc-time'),
            etcRemaining: this.container.querySelector('#etc-remaining')
        };
    }
    
    setupEventListeners() {
        document.addEventListener('progress_update', (event) => {
            this.handleProgressUpdate(event.detail);
        });
        
        document.addEventListener('phase_update', (event) => {
            if (event.detail.processed_count !== undefined && event.detail.total_count !== undefined) {
                this.handleProgressUpdate(event.detail);
            }
        });
    }
    
    handleProgressUpdate(data) {
        const phaseId = data.phase || data.phase_id || 'default';
        const processed = parseInt(data.processed_count || 0);
        const total = parseInt(data.total_count || 0);
        
        if (total > 0) {
            this.updateProgressBar(phaseId, processed, total, data);
            this.updateETC(phaseId, processed, total);
        }
    }
    
    updateProgressBar(phaseId, processed, total, data = {}) {
        const percentage = Math.round((processed / total) * 100);
        
        let progressBar = this.progressBars.get(phaseId);
        
        if (!progressBar) {
            progressBar = this.createProgressBar(phaseId);
            this.progressBars.set(phaseId, progressBar);
        }
        
        // Update progress bar
        const bar = progressBar.querySelector('.progress-bar');
        const label = progressBar.querySelector('.progress-label');
        const stats = progressBar.querySelector('.progress-stats');
        
        bar.style.width = `${percentage}%`;
        bar.setAttribute('aria-valuenow', percentage);
        
        label.textContent = this.formatPhaseId(phaseId);
        stats.textContent = `${processed}/${total} (${percentage}%)`;
        
        // Update color based on progress
        bar.className = `progress-bar ${this.getProgressColor(percentage)}`;
        
        // Add error indication if present
        if (data.error_count && data.error_count > 0) {
            stats.textContent += ` | ${data.error_count} errors`;
            bar.classList.add('progress-bar-striped');
        }
    }
    
    createProgressBar(phaseId) {
        const progressContainer = document.createElement('div');
        progressContainer.className = 'progress-container mb-3';
        progressContainer.innerHTML = `
            <div class="d-flex justify-content-between align-items-center mb-1">
                <span class="progress-label">${this.formatPhaseId(phaseId)}</span>
                <span class="progress-stats">0/0 (0%)</span>
            </div>
            <div class="progress">
                <div class="progress-bar" role="progressbar" style="width: 0%" aria-valuenow="0" aria-valuemin="0" aria-valuemax="100"></div>
            </div>
        `;
        
        this.elements.progressBars.appendChild(progressContainer);
        return progressContainer;
    }
    
    getProgressColor(percentage) {
        if (percentage < 25) return 'bg-danger';
        if (percentage < 50) return 'bg-warning';
        if (percentage < 75) return 'bg-info';
        return 'bg-success';
    }
    
    updateETC(phaseId, processed, total) {
        const etc = this.etcCalculator.calculateETC(phaseId, processed, total);
        
        if (etc.estimatedCompletion) {
            this.elements.etcTime.textContent = etc.estimatedCompletion.toLocaleTimeString();
            this.elements.etcRemaining.textContent = etc.remainingTime;
        }
        
        // Update summary
        const overallProgress = this.calculateOverallProgress();
        this.elements.progressSummary.innerHTML = `
            <span class="badge bg-${this.getProgressColor(overallProgress.percentage)}">
                ${overallProgress.percentage}% Complete
            </span>
        `;
    }
    
    calculateOverallProgress() {
        let totalProcessed = 0;
        let totalItems = 0;
        
        this.progressBars.forEach((progressBar) => {
            const stats = progressBar.querySelector('.progress-stats').textContent;
            const match = stats.match(/(\d+)\/(\d+)/);
            if (match) {
                totalProcessed += parseInt(match[1]);
                totalItems += parseInt(match[2]);
            }
        });
        
        const percentage = totalItems > 0 ? Math.round((totalProcessed / totalItems) * 100) : 0;
        
        return {
            processed: totalProcessed,
            total: totalItems,
            percentage
        };
    }
    
    formatPhaseId(phaseId) {
        return phaseId.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    }
    
    reset() {
        this.progressBars.clear();
        this.elements.progressBars.innerHTML = '';
        this.elements.etcTime.textContent = '--:--';
        this.elements.etcRemaining.textContent = '--';
        this.elements.progressSummary.innerHTML = '<span class="badge bg-info">Ready</span>';
        
        console.log('🔄 Progress display reset');
    }
}

class ETCCalculator {
    constructor() {
        this.phaseStartTimes = new Map();
        this.phaseRates = new Map();
    }
    
    calculateETC(phaseId, processed, total) {
        const now = new Date();
        
        // Initialize phase tracking
        if (!this.phaseStartTimes.has(phaseId)) {
            this.phaseStartTimes.set(phaseId, now);
        }
        
        const startTime = this.phaseStartTimes.get(phaseId);
        const elapsedMs = now - startTime;
        const elapsedMinutes = elapsedMs / (1000 * 60);
        
        if (processed === 0 || elapsedMinutes < 0.1) {
            return { estimatedCompletion: null, remainingTime: 'Calculating...' };
        }
        
        // Calculate processing rate
        const rate = processed / elapsedMinutes; // items per minute
        this.phaseRates.set(phaseId, rate);
        
        // Calculate remaining time
        const remaining = total - processed;
        const remainingMinutes = remaining / rate;
        
        const estimatedCompletion = new Date(now.getTime() + (remainingMinutes * 60 * 1000));
        const remainingTime = this.formatDuration(remainingMinutes);
        
        return {
            estimatedCompletion,
            remainingTime,
            rate: Math.round(rate * 100) / 100
        };
    }
    
    formatDuration(minutes) {
        if (minutes < 1) {
            return `${Math.round(minutes * 60)}s`;
        } else if (minutes < 60) {
            return `${Math.round(minutes)}m`;
        } else {
            const hours = Math.floor(minutes / 60);
            const mins = Math.round(minutes % 60);
            return `${hours}h ${mins}m`;
        }
    }
}

class TaskDisplayManager {
    constructor(container) {
        this.container = container;
        this.tasks = new Map();
        this.currentTask = null;
        
        this.initialize();
    }
    
    initialize() {
        console.log('📋 Initializing Task Display Manager...');
        
        this.createTaskDisplay();
        this.setupEventListeners();
        
        console.log('✅ Task Display Manager initialized');
    }
    
    createTaskDisplay() {
        if (!this.container) return;
        
        this.container.innerHTML = `
            <div class="task-display">
                <div class="task-header">
                    <h5 class="task-title">Current Task</h5>
                    <div class="task-controls">
                        <select class="form-select form-select-sm" id="task-selector">
                            <option value="">Select Task...</option>
                        </select>
                    </div>
                </div>
                <div class="task-info" id="task-info">
                    <div class="task-status">No active task</div>
                </div>
                <div class="task-logs" id="task-logs">
                    <div class="logs-container" style="height: 200px; overflow-y: auto; border: 1px solid #dee2e6; border-radius: 0.375rem; padding: 0.5rem;">
                        <div class="text-muted text-center">Task logs will appear here...</div>
                    </div>
                </div>
            </div>
        `;
        
        this.elements = {
            taskSelector: this.container.querySelector('#task-selector'),
            taskInfo: this.container.querySelector('#task-info'),
            taskLogs: this.container.querySelector('#task-logs .logs-container')
        };
    }
    
    setupEventListeners() {
        // Task selection
        if (this.elements.taskSelector) {
            this.elements.taskSelector.addEventListener('change', (e) => {
                this.selectTask(e.target.value);
            });
        }
        
        // Agent status updates
        document.addEventListener('agent_status_update', (event) => {
            if (event.detail.task_id) {
                this.updateTask(event.detail.task_id, event.detail);
            }
        });
        
        // Log events with task isolation
        document.addEventListener('log', (event) => {
            if (event.detail.task_id && this.currentTask === event.detail.task_id) {
                this.addTaskLog(event.detail);
            }
        });
    }
    
    updateTask(taskId, data) {
        this.tasks.set(taskId, {
            id: taskId,
            status: data.is_running ? 'running' : 'completed',
            phase: data.current_phase_id || 'unknown',
            message: data.current_phase_message || '',
            lastUpdate: new Date(),
            data
        });
        
        this.updateTaskSelector();
        
        if (this.currentTask === taskId) {
            this.updateTaskInfo();
        }
    }
    
    updateTaskSelector() {
        if (!this.elements.taskSelector) return;
        
        const currentValue = this.elements.taskSelector.value;
        
        this.elements.taskSelector.innerHTML = '<option value="">Select Task...</option>';
        
        this.tasks.forEach((task, taskId) => {
            const option = document.createElement('option');
            option.value = taskId;
            option.textContent = `${taskId} (${task.status})`;
            this.elements.taskSelector.appendChild(option);
        });
        
        // Restore selection
        if (currentValue) {
            this.elements.taskSelector.value = currentValue;
        }
    }
    
    selectTask(taskId) {
        this.currentTask = taskId;
        this.updateTaskInfo();
        this.clearTaskLogs();
        
        console.log(`📋 Selected task: ${taskId}`);
    }
    
    updateTaskInfo() {
        if (!this.elements.taskInfo || !this.currentTask) {
            this.elements.taskInfo.innerHTML = '<div class="task-status">No active task</div>';
            return;
        }
        
        const task = this.tasks.get(this.currentTask);
        if (!task) return;
        
        this.elements.taskInfo.innerHTML = `
            <div class="task-status">
                <span class="badge bg-${task.status === 'running' ? 'success' : 'secondary'}">
                    ${task.status.toUpperCase()}
                </span>
            </div>
            <div class="task-details">
                <div><strong>Task ID:</strong> ${task.id}</div>
                <div><strong>Current Phase:</strong> ${task.phase}</div>
                <div><strong>Message:</strong> ${task.message}</div>
                <div><strong>Last Update:</strong> ${task.lastUpdate.toLocaleTimeString()}</div>
            </div>
        `;
    }
    
    addTaskLog(logData) {
        if (!this.elements.taskLogs) return;
        
        const logEntry = document.createElement('div');
        logEntry.className = `log-entry log-${(logData.level || 'info').toLowerCase()}`;
        logEntry.innerHTML = `
            <div class="log-time">${new Date().toLocaleTimeString()}</div>
            <div class="log-content">${logData.message}</div>
        `;
        
        this.elements.taskLogs.appendChild(logEntry);
        
        // Auto-scroll to bottom
        this.elements.taskLogs.scrollTop = this.elements.taskLogs.scrollHeight;
        
        // Limit log entries
        const maxLogs = 100;
        while (this.elements.taskLogs.children.length > maxLogs) {
            this.elements.taskLogs.removeChild(this.elements.taskLogs.firstChild);
        }
    }
    
    clearTaskLogs() {
        if (this.elements.taskLogs) {
            this.elements.taskLogs.innerHTML = '<div class="text-muted text-center">Task logs will appear here...</div>';
        }
    }
}

// Integrated Phase and Progress Display Manager
class IntegratedPhaseProgressManager {
    constructor(options = {}) {
        this.options = {
            phaseContainer: '#phase-display-container',
            progressContainer: '#progress-display-container',
            taskContainer: '#task-display-container',
            ...options
        };
        
        this.managers = {};
        
        this.initialize();
    }
    
    initialize() {
        console.log('🎭📊📋 Initializing Integrated Phase Progress Manager...');
        
        // Initialize individual managers
        const phaseContainer = document.querySelector(this.options.phaseContainer);
        if (phaseContainer) {
            this.managers.phase = new PhaseDisplayManager(phaseContainer);
        }
        
        const progressContainer = document.querySelector(this.options.progressContainer);
        if (progressContainer) {
            this.managers.progress = new ProgressDisplayManager(progressContainer);
        }
        
        const taskContainer = document.querySelector(this.options.taskContainer);
        if (taskContainer) {
            this.managers.task = new TaskDisplayManager(taskContainer);
        }
        
        console.log('✅ Integrated Phase Progress Manager initialized');
    }
    
    reset() {
        Object.values(this.managers).forEach(manager => {
            if (manager.reset) {
                manager.reset();
            } else if (manager.resetDisplay) {
                manager.resetDisplay();
            }
        });
        
        console.log('🔄 All displays reset');
    }
    
    getStats() {
        const stats = {};
        
        Object.entries(this.managers).forEach(([name, manager]) => {
            if (manager.getStats) {
                stats[name] = manager.getStats();
            }
        });
        
        return stats;
    }
    
    destroy() {
        Object.values(this.managers).forEach(manager => {
            if (manager.destroy) {
                manager.destroy();
            }
        });
        
        console.log('🧹 Integrated Phase Progress Manager destroyed');
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        PhaseDisplayManager,
        ProgressDisplayManager,
        ETCCalculator,
        TaskDisplayManager,
        IntegratedPhaseProgressManager
    };
} else {
    window.PhaseDisplayManager = PhaseDisplayManager;
    window.ProgressDisplayManager = ProgressDisplayManager;
    window.ETCCalculator = ETCCalculator;
    window.TaskDisplayManager = TaskDisplayManager;
    window.IntegratedPhaseProgressManager = IntegratedPhaseProgressManager;
}
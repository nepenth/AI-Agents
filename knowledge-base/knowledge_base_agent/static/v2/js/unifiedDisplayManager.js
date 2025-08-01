/**
 * Unified Display Manager
 * Consolidates all display-related managers:
 * - LegacyPhaseDisplayManager, PhaseDisplayManager, EnhancedProgressDisplayManager
 * - ProgressDisplayManager, TaskDisplayManager, EnhancedTaskDisplayManager
 * - IntegratedPhaseProgressManager
 * 
 * Provides coordinated display updates and consistent styling
 */
class UnifiedDisplayManager extends BaseManager {
    constructor(options = {}) {
        super({
            enableLogging: true,
            autoInit: false,
            ...options
        });

        // Display state management
        this.displayState = {
            currentPhase: null,
            phases: new Map(),
            progressBars: new Map(),
            tasks: new Map(),
            activeTask: null,
            displayMode: 'integrated' // integrated, separate, minimal
        };

        // Display configuration
        this.config = {
            maxPhases: 20,
            maxProgressBars: 10,
            maxTasks: 5,
            animationDuration: 300,
            updateThrottle: 100,
            autoCleanup: true,
            ...options.config
        };

        // Performance optimization
        this.updateQueue = [];
        this.isUpdating = false;
        this.lastUpdate = 0;
    }

    /**
     * Initialize display elements
     */
    async initializeElements() {
        this.log('Initializing display elements...');

        // Main display containers
        this.elements.containers = {
            main: document.getElementById('main-content'),
            dashboard: document.querySelector('.dashboard-main-area'),
            phases: document.getElementById('phase-list') || document.querySelector('.execution-plan-phases'),
            progress: document.getElementById('progress-container') || document.querySelector('.progress-display'),
            tasks: document.getElementById('task-display') || document.querySelector('.task-container'),
            logs: document.getElementById('logs-container') || document.querySelector('.logs-panel')
        };

        // Phase display elements
        this.elements.phases = {
            container: this.elements.containers.phases,
            list: document.getElementById('phase-list'),
            current: document.getElementById('current-phase'),
            elapsed: document.getElementById('phase-elapsed-time'),
            etc: document.getElementById('phase-etc-time'),
            status: document.getElementById('phase-status')
        };

        // Progress display elements
        this.elements.progress = {
            container: this.elements.containers.progress,
            bars: document.querySelectorAll('.progress-bar'),
            overlay: document.getElementById('progress-overlay'),
            modal: document.getElementById('progress-modal')
        };

        // Task display elements
        this.elements.tasks = {
            container: this.elements.containers.tasks,
            selector: document.getElementById('task-selector'),
            info: document.getElementById('task-info'),
            duration: document.getElementById('task-duration'),
            status: document.getElementById('task-status'),
            logs: document.getElementById('task-logs')
        };

        // Create missing containers if needed
        await this.createMissingContainers();

        this.log('Display elements initialized');
    }

    /**
     * Create missing display containers
     */
    async createMissingContainers() {
        // Create unified display container if it doesn't exist
        if (!document.getElementById('unified-display-container')) {
            const container = document.createElement('div');
            container.id = 'unified-display-container';
            container.className = 'unified-display-container';
            container.innerHTML = `
                <div class="unified-display-header">
                    <div class="display-controls">
                        <button id="display-mode-toggle" class="glass-button glass-button--small">
                            <i class="fas fa-expand"></i>
                        </button>
                        <button id="display-refresh" class="glass-button glass-button--small">
                            <i class="fas fa-refresh"></i>
                        </button>
                    </div>
                </div>
                <div class="unified-display-content">
                    <div class="display-section" id="phase-display-section">
                        <h3 class="display-section-title">Phase Progress</h3>
                        <div id="unified-phase-container"></div>
                    </div>
                    <div class="display-section" id="progress-display-section">
                        <h3 class="display-section-title">Progress Tracking</h3>
                        <div id="unified-progress-container"></div>
                    </div>
                    <div class="display-section" id="task-display-section">
                        <h3 class="display-section-title">Task Information</h3>
                        <div id="unified-task-container"></div>
                    </div>
                </div>
            `;

            // Insert into appropriate location
            const targetContainer = this.elements.containers.dashboard || this.elements.containers.main;
            if (targetContainer) {
                targetContainer.appendChild(container);
            }
        }
    }

    /**
     * Initialize display state
     */
    async initializeState() {
        await super.initializeState();

        // Initialize display-specific state
        this.setState({
            displayState: { ...this.displayState },
            config: { ...this.config }
        });

        // Load any persisted display preferences
        await this.loadDisplayPreferences();

        this.log('Display state initialized');
    }

    /**
     * Setup event listeners for display management
     */
    async setupEventListeners() {
        this.log('Setting up display event listeners...');

        this.eventService.setupStandardListeners(this, {
            // Display control buttons
            buttons: [
                {
                    selector: '#display-mode-toggle',
                    handler: () => this.toggleDisplayMode(),
                    debounce: 300
                },
                {
                    selector: '#display-refresh',
                    handler: () => this.refreshAllDisplays(),
                    debounce: 1000
                }
            ],

            // Custom events for display updates
            customEvents: [
                // Phase events
                {
                    event: 'phase_start',
                    handler: (e) => this.handlePhaseStart(e.detail),
                    throttle: this.config.updateThrottle
                },
                {
                    event: 'phase_update',
                    handler: (e) => this.handlePhaseUpdate(e.detail),
                    throttle: this.config.updateThrottle
                },
                {
                    event: 'phase_complete',
                    handler: (e) => this.handlePhaseComplete(e.detail),
                    throttle: this.config.updateThrottle
                },
                {
                    event: 'phase_error',
                    handler: (e) => this.handlePhaseError(e.detail),
                    throttle: this.config.updateThrottle
                },

                // Progress events
                {
                    event: 'progress_update',
                    handler: (e) => this.handleProgressUpdate(e.detail),
                    throttle: this.config.updateThrottle
                },
                {
                    event: 'progress_complete',
                    handler: (e) => this.handleProgressComplete(e.detail)
                },

                // Task events
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

                // Agent status events
                {
                    event: 'agent_status_update',
                    handler: (e) => this.handleAgentStatusUpdate(e.detail),
                    throttle: this.config.updateThrottle
                }
            ]
        });

        this.log('Display event listeners setup completed');
    }

    /**
     * Load initial display data
     */
    async loadInitialData() {
        this.log('Loading initial display data...');

        try {
            // Load current agent status
            const agentStatus = await this.apiCall('/api/agent/status', {
                action: 'load agent status',
                cache: true,
                cacheTTL: 5000
            });

            if (agentStatus) {
                this.updateFromAgentStatus(agentStatus);
            }

            // Load active task information
            const activeTask = await this.apiCall('/api/v2/agent/active', {
                action: 'load active task',
                cache: true,
                cacheTTL: 5000
            });

            if (activeTask && activeTask.success) {
                this.handleTaskStarted(activeTask.data);
            }

            this.log('Initial display data loaded');
        } catch (error) {
            this.logError('Failed to load initial display data:', error);
            // Don't throw - display should work even without initial data
        }
    }

    /**
     * Phase management methods
     */
    handlePhaseStart(data) {
        const phaseId = data.phase_id || data.phaseId || data.id;
        const phaseName = data.phase_name || data.name || data.message;

        this.log('Phase started:', phaseId, phaseName);

        const phase = {
            id: phaseId,
            name: phaseName,
            status: 'running',
            startTime: new Date(),
            progress: 0,
            message: data.message || '',
            estimatedDuration: data.estimated_duration || null
        };

        this.displayState.phases.set(phaseId, phase);
        this.displayState.currentPhase = phaseId;

        this.queueUpdate(() => this.renderPhaseDisplay());
        this.dispatchEvent('phaseDisplayUpdated', { phase, action: 'started' });
    }

    handlePhaseUpdate(data) {
        const phaseId = data.phase_id || data.phaseId || data.id;
        const phase = this.displayState.phases.get(phaseId);

        if (!phase) {
            this.logWarn('Phase update for unknown phase:', phaseId);
            return;
        }

        // Update phase data
        Object.assign(phase, {
            progress: data.progress || phase.progress,
            message: data.message || phase.message,
            status: data.status || phase.status,
            lastUpdate: new Date()
        });

        this.queueUpdate(() => this.renderPhaseDisplay());
        this.dispatchEvent('phaseDisplayUpdated', { phase, action: 'updated' });
    }

    handlePhaseComplete(data) {
        const phaseId = data.phase_id || data.phaseId || data.id;
        const phase = this.displayState.phases.get(phaseId);

        if (!phase) {
            this.logWarn('Phase completion for unknown phase:', phaseId);
            return;
        }

        // Update phase as completed
        Object.assign(phase, {
            status: 'completed',
            progress: 100,
            endTime: new Date(),
            duration: new Date() - phase.startTime,
            message: data.message || 'Completed'
        });

        this.queueUpdate(() => this.renderPhaseDisplay());
        this.dispatchEvent('phaseDisplayUpdated', { phase, action: 'completed' });

        // Auto-cleanup old phases if enabled
        if (this.config.autoCleanup) {
            this.cleanupOldPhases();
        }
    }

    handlePhaseError(data) {
        const phaseId = data.phase_id || data.phaseId || data.id;
        const phase = this.displayState.phases.get(phaseId);

        if (!phase) {
            this.logWarn('Phase error for unknown phase:', phaseId);
            return;
        }

        // Update phase as errored
        Object.assign(phase, {
            status: 'error',
            endTime: new Date(),
            duration: new Date() - phase.startTime,
            error: data.error || data.message || 'Unknown error'
        });

        this.queueUpdate(() => this.renderPhaseDisplay());
        this.dispatchEvent('phaseDisplayUpdated', { phase, action: 'error' });
    }

    /**
     * Progress management methods
     */
    handleProgressUpdate(data) {
        const progressId = data.progress_id || data.id || 'default';
        
        let progressBar = this.displayState.progressBars.get(progressId);
        if (!progressBar) {
            progressBar = {
                id: progressId,
                name: data.name || 'Progress',
                progress: 0,
                total: data.total || 100,
                startTime: new Date()
            };
            this.displayState.progressBars.set(progressId, progressBar);
        }

        // Update progress data
        Object.assign(progressBar, {
            progress: data.progress || data.current || progressBar.progress,
            total: data.total || progressBar.total,
            message: data.message || progressBar.message,
            lastUpdate: new Date()
        });

        // Calculate ETC if we have timing data
        if (progressBar.progress > 0 && progressBar.startTime) {
            const elapsed = new Date() - progressBar.startTime;
            const rate = progressBar.progress / elapsed;
            const remaining = (progressBar.total - progressBar.progress) / rate;
            progressBar.etc = remaining;
        }

        this.queueUpdate(() => this.renderProgressDisplay());
        this.dispatchEvent('progressDisplayUpdated', { progressBar, action: 'updated' });
    }

    handleProgressComplete(data) {
        const progressId = data.progress_id || data.id || 'default';
        const progressBar = this.displayState.progressBars.get(progressId);

        if (progressBar) {
            progressBar.progress = progressBar.total;
            progressBar.status = 'completed';
            progressBar.endTime = new Date();
            progressBar.duration = progressBar.endTime - progressBar.startTime;

            this.queueUpdate(() => this.renderProgressDisplay());
            this.dispatchEvent('progressDisplayUpdated', { progressBar, action: 'completed' });
        }
    }

    /**
     * Task management methods
     */
    handleTaskStarted(data) {
        const taskId = data.task_id || data.id;
        
        const task = {
            id: taskId,
            name: data.name || data.human_readable_name || 'Agent Task',
            status: 'running',
            startTime: new Date(),
            phases: new Map(),
            logs: [],
            statistics: {
                totalLogs: 0,
                completedPhases: 0,
                phaseCount: 0
            }
        };

        this.displayState.tasks.set(taskId, task);
        this.displayState.activeTask = taskId;

        this.queueUpdate(() => this.renderTaskDisplay());
        this.dispatchEvent('taskDisplayUpdated', { task, action: 'started' });
    }

    handleTaskCompleted(data) {
        const taskId = data.task_id || data.id;
        const task = this.displayState.tasks.get(taskId);

        if (task) {
            task.status = 'completed';
            task.endTime = new Date();
            task.duration = task.endTime - task.startTime;

            this.queueUpdate(() => this.renderTaskDisplay());
            this.dispatchEvent('taskDisplayUpdated', { task, action: 'completed' });

            // Clear active task if this was it
            if (this.displayState.activeTask === taskId) {
                this.displayState.activeTask = null;
            }
        }
    }

    handleTaskError(data) {
        const taskId = data.task_id || data.id;
        const task = this.displayState.tasks.get(taskId);

        if (task) {
            task.status = 'error';
            task.error = data.error || data.message || 'Unknown error';
            task.endTime = new Date();
            task.duration = task.endTime - task.startTime;

            this.queueUpdate(() => this.renderTaskDisplay());
            this.dispatchEvent('taskDisplayUpdated', { task, action: 'error' });
        }
    }

    /**
     * Rendering methods
     */
    renderPhaseDisplay() {
        const container = document.getElementById('unified-phase-container');
        if (!container) return;

        const phases = Array.from(this.displayState.phases.values());
        const currentPhase = phases.find(p => p.id === this.displayState.currentPhase);

        container.innerHTML = `
            ${currentPhase ? this.renderCurrentPhase(currentPhase) : ''}
            <div class="phase-list">
                ${phases.map(phase => this.renderPhaseItem(phase)).join('')}
            </div>
        `;
    }

    renderCurrentPhase(phase) {
        const elapsed = phase.endTime ? 
            phase.duration : 
            (new Date() - phase.startTime);
        
        const elapsedText = this.durationFormatter.format(elapsed);
        const etcText = phase.etc ? 
            this.durationFormatter.formatETC(phase.etc) : 
            '--';

        return `
            <div class="current-phase-display">
                <div class="current-phase-header">
                    <h4 class="current-phase-name">${phase.name}</h4>
                    <span class="current-phase-status status-${phase.status}">${phase.status}</span>
                </div>
                <div class="current-phase-progress">
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: ${phase.progress}%"></div>
                    </div>
                    <div class="progress-text">${phase.progress}%</div>
                </div>
                <div class="current-phase-timing">
                    <span class="elapsed-time">Elapsed: ${elapsedText}</span>
                    <span class="etc-time">${etcText}</span>
                </div>
                ${phase.message ? `<div class="current-phase-message">${phase.message}</div>` : ''}
            </div>
        `;
    }

    renderPhaseItem(phase) {
        const statusIcon = this.getPhaseStatusIcon(phase.status);
        const duration = phase.duration ? 
            this.durationFormatter.format(phase.duration) : 
            '--';

        return `
            <div class="phase-item phase-${phase.status}" data-phase-id="${phase.id}">
                <div class="phase-icon">${statusIcon}</div>
                <div class="phase-info">
                    <div class="phase-name">${phase.name}</div>
                    <div class="phase-meta">
                        <span class="phase-duration">${duration}</span>
                        <span class="phase-progress">${phase.progress}%</span>
                    </div>
                </div>
            </div>
        `;
    }

    renderProgressDisplay() {
        const container = document.getElementById('unified-progress-container');
        if (!container) return;

        const progressBars = Array.from(this.displayState.progressBars.values());

        container.innerHTML = progressBars.map(bar => `
            <div class="progress-item" data-progress-id="${bar.id}">
                <div class="progress-header">
                    <span class="progress-name">${bar.name}</span>
                    <span class="progress-percentage">${Math.round((bar.progress / bar.total) * 100)}%</span>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: ${(bar.progress / bar.total) * 100}%"></div>
                </div>
                ${bar.message ? `<div class="progress-message">${bar.message}</div>` : ''}
                ${bar.etc ? `<div class="progress-etc">ETC: ${this.durationFormatter.format(bar.etc)}</div>` : ''}
            </div>
        `).join('');
    }

    renderTaskDisplay() {
        const container = document.getElementById('unified-task-container');
        if (!container) return;

        const activeTask = this.displayState.activeTask ? 
            this.displayState.tasks.get(this.displayState.activeTask) : 
            null;

        if (!activeTask) {
            container.innerHTML = '<div class="no-active-task">No active task</div>';
            return;
        }

        const duration = activeTask.duration || (new Date() - activeTask.startTime);
        const durationText = this.durationFormatter.format(duration);

        container.innerHTML = `
            <div class="active-task-display">
                <div class="task-header">
                    <h4 class="task-name">${activeTask.name}</h4>
                    <span class="task-status status-${activeTask.status}">${activeTask.status}</span>
                </div>
                <div class="task-timing">
                    <span class="task-duration">Duration: ${durationText}</span>
                    <span class="task-start">Started: ${activeTask.startTime.toLocaleTimeString()}</span>
                </div>
                <div class="task-statistics">
                    <div class="stat-item">
                        <span class="stat-label">Phases:</span>
                        <span class="stat-value">${activeTask.statistics.completedPhases}/${activeTask.statistics.phaseCount}</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-label">Logs:</span>
                        <span class="stat-value">${activeTask.statistics.totalLogs}</span>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Utility methods
     */
    getPhaseStatusIcon(status) {
        const icons = {
            'running': '<i class="fas fa-spinner fa-spin"></i>',
            'completed': '<i class="fas fa-check-circle"></i>',
            'error': '<i class="fas fa-exclamation-circle"></i>',
            'pending': '<i class="fas fa-clock"></i>'
        };
        return icons[status] || icons.pending;
    }

    queueUpdate(updateFunction) {
        this.updateQueue.push(updateFunction);
        
        if (!this.isUpdating) {
            this.processUpdateQueue();
        }
    }

    async processUpdateQueue() {
        if (this.isUpdating) return;
        
        this.isUpdating = true;
        
        try {
            while (this.updateQueue.length > 0) {
                const updateFunction = this.updateQueue.shift();
                await updateFunction();
                
                // Throttle updates to prevent overwhelming the UI
                const now = Date.now();
                if (now - this.lastUpdate < this.config.updateThrottle) {
                    await new Promise(resolve => setTimeout(resolve, this.config.updateThrottle));
                }
                this.lastUpdate = now;
            }
        } finally {
            this.isUpdating = false;
        }
    }

    cleanupOldPhases() {
        const phases = Array.from(this.displayState.phases.values());
        const completedPhases = phases.filter(p => p.status === 'completed');
        
        if (completedPhases.length > this.config.maxPhases) {
            // Remove oldest completed phases
            completedPhases
                .sort((a, b) => a.endTime - b.endTime)
                .slice(0, completedPhases.length - this.config.maxPhases)
                .forEach(phase => {
                    this.displayState.phases.delete(phase.id);
                });
        }
    }

    toggleDisplayMode() {
        const modes = ['integrated', 'separate', 'minimal'];
        const currentIndex = modes.indexOf(this.displayState.displayMode);
        const nextIndex = (currentIndex + 1) % modes.length;
        
        this.displayState.displayMode = modes[nextIndex];
        this.applyDisplayMode();
        
        this.log('Display mode changed to:', this.displayState.displayMode);
    }

    applyDisplayMode() {
        const container = document.getElementById('unified-display-container');
        if (container) {
            container.className = `unified-display-container mode-${this.displayState.displayMode}`;
        }
    }

    async refreshAllDisplays() {
        this.log('Refreshing all displays...');
        
        try {
            this.renderPhaseDisplay();
            this.renderProgressDisplay();
            this.renderTaskDisplay();
            
            this.log('All displays refreshed');
        } catch (error) {
            this.setError(error, 'refreshing displays');
        }
    }

    async loadDisplayPreferences() {
        try {
            const preferences = localStorage.getItem('unifiedDisplayPreferences');
            if (preferences) {
                const parsed = JSON.parse(preferences);
                this.displayState.displayMode = parsed.displayMode || 'integrated';
                this.config = { ...this.config, ...parsed.config };
            }
        } catch (error) {
            this.logWarn('Failed to load display preferences:', error);
        }
    }

    saveDisplayPreferences() {
        try {
            const preferences = {
                displayMode: this.displayState.displayMode,
                config: this.config
            };
            localStorage.setItem('unifiedDisplayPreferences', JSON.stringify(preferences));
        } catch (error) {
            this.logWarn('Failed to save display preferences:', error);
        }
    }

    updateFromAgentStatus(status) {
        if (status.is_running && status.current_task_id) {
            this.handleTaskStarted({
                task_id: status.current_task_id,
                name: 'Agent Task',
                status: 'running'
            });
        }

        if (status.current_phase_message) {
            this.handlePhaseUpdate({
                phase_id: 'current',
                message: status.current_phase_message,
                status: 'running'
            });
        }
    }

    /**
     * Public API methods
     */
    getCurrentPhase() {
        return this.displayState.currentPhase ? 
            this.displayState.phases.get(this.displayState.currentPhase) : 
            null;
    }

    getActiveTask() {
        return this.displayState.activeTask ? 
            this.displayState.tasks.get(this.displayState.activeTask) : 
            null;
    }

    getAllPhases() {
        return Array.from(this.displayState.phases.values());
    }

    getAllProgressBars() {
        return Array.from(this.displayState.progressBars.values());
    }

    getAllTasks() {
        return Array.from(this.displayState.tasks.values());
    }

    clearAllDisplays() {
        this.displayState.phases.clear();
        this.displayState.progressBars.clear();
        this.displayState.tasks.clear();
        this.displayState.currentPhase = null;
        this.displayState.activeTask = null;
        
        this.refreshAllDisplays();
        this.log('All displays cleared');
    }
}

// Make available globally
window.UnifiedDisplayManager = UnifiedDisplayManager;

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = UnifiedDisplayManager;
}
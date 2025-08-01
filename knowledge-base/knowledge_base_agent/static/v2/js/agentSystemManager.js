/**
 * Agent System Manager
 * Consolidates AgentControlManager, TaskStateManager, and ExecutionPlanManager
 * Provides unified interface for agent operations and monitoring
 */
class AgentSystemManager extends BaseManager {
    constructor(options = {}) {
        super({
            enableLogging: true,
            autoInit: false,
            ...options
        });

        // Agent state management
        this.agentState = {
            isRunning: false,
            currentTaskId: null,
            currentPhase: null,
            preferences: {},
            executionPlan: null,
            history: []
        };

        // Task management
        this.taskState = {
            activeTasks: new Map(),
            completedTasks: new Map(),
            currentTask: null
        };

        // Configuration
        this.config = {
            maxHistoryItems: 50,
            autoRefreshInterval: 5000,
            taskTimeout: 300000, // 5 minutes
            ...options.config
        };
    }

    /**
     * Initialize agent system elements
     */
    async initializeElements() {
        this.log('Initializing agent system elements...');

        // Agent control elements
        this.elements.controls = {
            runBtn: document.getElementById('run-agent-btn'),
            stopBtn: document.getElementById('stop-agent-btn'),
            clearBtn: document.getElementById('clear-all-btn'),
            preferencesPanel: document.getElementById('preferences-panel'),
            statusIndicator: document.getElementById('agent-status-indicator')
        };

        // Task state elements
        this.elements.tasks = {
            selector: document.getElementById('task-selector'),
            info: document.getElementById('task-info'),
            status: document.getElementById('task-status'),
            progress: document.getElementById('task-progress')
        };

        // Execution plan elements
        this.elements.execution = {
            container: document.getElementById('execution-plan-container'),
            phaseList: document.getElementById('phase-list'),
            currentPhase: document.getElementById('current-phase'),
            progressBar: document.getElementById('execution-progress')
        };

        this.log('Agent system elements initialized');
    }    /*
*
     * Initialize agent system state
     */
    async initializeState() {
        await super.initializeState();

        // Load current agent state
        await this.loadAgentState();

        // Load active tasks
        await this.loadActiveTasks();

        this.setState({
            agentState: { ...this.agentState },
            taskState: { ...this.taskState }
        });

        this.log('Agent system state initialized');
    }

    /**
     * Setup event listeners for agent system
     */
    async setupEventListeners() {
        this.log('Setting up agent system event listeners...');

        this.eventService.setupStandardListeners(this, {
            // Agent control buttons
            buttons: [
                {
                    selector: this.elements.controls.runBtn,
                    handler: () => this.startAgent(),
                    debounce: 1000,
                    condition: () => this.elements.controls.runBtn
                },
                {
                    selector: this.elements.controls.stopBtn,
                    handler: () => this.stopAgent(),
                    debounce: 1000,
                    condition: () => this.elements.controls.stopBtn
                },
                {
                    selector: this.elements.controls.clearBtn,
                    handler: () => this.clearAllOptions(),
                    debounce: 500,
                    condition: () => this.elements.controls.clearBtn
                }
            ],

            // Task selection
            inputs: [
                {
                    selector: this.elements.tasks.selector,
                    events: ['change'],
                    handler: (e) => this.switchTask(e.target.value),
                    condition: () => this.elements.tasks.selector
                }
            ],

            // System events
            customEvents: [
                {
                    event: 'agent_status_update',
                    handler: (e) => this.handleAgentStatusUpdate(e.detail)
                },
                {
                    event: 'task_started',
                    handler: (e) => this.handleTaskStarted(e.detail)
                },
                {
                    event: 'task_completed',
                    handler: (e) => this.handleTaskCompleted(e.detail)
                },
                {
                    event: 'phase_start',
                    handler: (e) => this.handlePhaseStart(e.detail)
                },
                {
                    event: 'phase_complete',
                    handler: (e) => this.handlePhaseComplete(e.detail)
                }
            ]
        });

        this.log('Agent system event listeners setup completed');
    }

    /**
     * Load initial agent system data
     */
    async loadInitialData() {
        this.log('Loading initial agent system data...');

        try {
            // Load current agent status
            await this.loadAgentState();

            // Load task history
            await this.loadTaskHistory();

            // Update UI
            this.updateAgentUI();
            this.updateTaskUI();

            this.log('Initial agent system data loaded');
        } catch (error) {
            this.setError(error, 'loading initial agent system data');
        }
    }

    /**
     * Agent control methods
     */
    async startAgent() {
        this.log('Starting agent...');

        try {
            this.setLoading(true, 'Starting agent...');

            const preferences = this.collectPreferences();
            
            const response = await this.apiCall('/api/v2/agent/start', {
                method: 'POST',
                body: { preferences },
                action: 'start agent'
            });

            if (response.success) {
                this.handleTaskStarted({
                    task_id: response.task_id,
                    name: response.human_readable_name || 'Agent Task'
                });
            }

            this.log('Agent started successfully');

        } catch (error) {
            this.setError(error, 'starting agent');
        }
    }

    async stopAgent() {
        this.log('Stopping agent...');

        try {
            this.setLoading(true, 'Stopping agent...');

            const response = await this.apiCall('/api/v2/agent/stop', {
                method: 'POST',
                action: 'stop agent'
            });

            if (response.success) {
                this.agentState.isRunning = false;
                this.updateAgentUI();
            }

            this.log('Agent stopped successfully');

        } catch (error) {
            this.setError(error, 'stopping agent');
        }
    }

    /**
     * Task management methods
     */
    async loadAgentState() {
        try {
            const status = await this.apiCall('/api/agent/status', {
                action: 'load agent status',
                cache: true,
                cacheTTL: 5000
            });

            if (status) {
                this.agentState.isRunning = status.is_running || false;
                this.agentState.currentTaskId = status.current_task_id;
                this.agentState.currentPhase = status.current_phase_message;
            }

        } catch (error) {
            this.logWarn('Failed to load agent state:', error);
        }
    }

    async loadActiveTasks() {
        try {
            const activeTask = await this.apiCall('/api/v2/agent/active', {
                action: 'load active task',
                cache: true,
                cacheTTL: 5000
            });

            if (activeTask && activeTask.success) {
                this.taskState.currentTask = activeTask.data;
            }

        } catch (error) {
            this.logWarn('Failed to load active tasks:', error);
        }
    }

    async loadTaskHistory() {
        try {
            const history = await this.apiCall('/api/v2/jobs/history', {
                action: 'load task history',
                cache: true,
                cacheTTL: 30000
            });

            if (history && history.success) {
                this.agentState.history = history.data.jobs || [];
            }

        } catch (error) {
            this.logWarn('Failed to load task history:', error);
        }
    }

    /**
     * Event handlers
     */
    handleAgentStatusUpdate(data) {
        this.agentState.isRunning = data.is_running || false;
        this.agentState.currentTaskId = data.current_task_id;
        this.agentState.currentPhase = data.current_phase_message;

        this.updateAgentUI();
        this.dispatchEvent('agentStateChanged', { agentState: this.agentState });
    }

    handleTaskStarted(data) {
        const task = {
            id: data.task_id || data.id,
            name: data.name || data.human_readable_name || 'Agent Task',
            status: 'running',
            startTime: new Date(),
            phases: new Map()
        };

        this.taskState.activeTasks.set(task.id, task);
        this.taskState.currentTask = task;

        this.updateTaskUI();
        this.dispatchEvent('taskStateChanged', { taskState: this.taskState });
    }

    handleTaskCompleted(data) {
        const taskId = data.task_id || data.id;
        const task = this.taskState.activeTasks.get(taskId);

        if (task) {
            task.status = 'completed';
            task.endTime = new Date();
            task.duration = task.endTime - task.startTime;

            this.taskState.completedTasks.set(taskId, task);
            this.taskState.activeTasks.delete(taskId);

            if (this.taskState.currentTask?.id === taskId) {
                this.taskState.currentTask = null;
            }

            this.updateTaskUI();
        }
    }

    handlePhaseStart(data) {
        const currentTask = this.taskState.currentTask;
        if (currentTask) {
            const phase = {
                id: data.phase_id || data.id,
                name: data.phase_name || data.name,
                status: 'running',
                startTime: new Date()
            };

            currentTask.phases.set(phase.id, phase);
            this.agentState.currentPhase = phase.name;

            this.updateAgentUI();
        }
    }

    handlePhaseComplete(data) {
        const currentTask = this.taskState.currentTask;
        if (currentTask) {
            const phaseId = data.phase_id || data.id;
            const phase = currentTask.phases.get(phaseId);

            if (phase) {
                phase.status = 'completed';
                phase.endTime = new Date();
                phase.duration = phase.endTime - phase.startTime;
            }
        }
    }

    /**
     * UI update methods
     */
    updateAgentUI() {
        // Update status indicator
        if (this.elements.controls.statusIndicator) {
            const status = this.agentState.isRunning ? 'running' : 'idle';
            this.elements.controls.statusIndicator.className = `agent-status-indicator status-${status}`;
            this.elements.controls.statusIndicator.textContent = status.toUpperCase();
        }

        // Update control buttons
        if (this.elements.controls.runBtn) {
            this.elements.controls.runBtn.disabled = this.agentState.isRunning;
        }

        if (this.elements.controls.stopBtn) {
            this.elements.controls.stopBtn.disabled = !this.agentState.isRunning;
        }

        // Update current phase display
        if (this.elements.execution.currentPhase && this.agentState.currentPhase) {
            this.elements.execution.currentPhase.textContent = this.agentState.currentPhase;
        }
    }

    updateTaskUI() {
        const currentTask = this.taskState.currentTask;

        // Update task selector
        if (this.elements.tasks.selector) {
            const tasks = Array.from(this.taskState.activeTasks.values());
            this.elements.tasks.selector.innerHTML = tasks.map(task => 
                `<option value="${task.id}" ${task.id === currentTask?.id ? 'selected' : ''}>${task.name}</option>`
            ).join('');
        }

        // Update task info
        if (this.elements.tasks.info && currentTask) {
            const duration = currentTask.endTime ? 
                currentTask.duration : 
                (new Date() - currentTask.startTime);

            this.elements.tasks.info.innerHTML = `
                <div class="task-name">${currentTask.name}</div>
                <div class="task-duration">Duration: ${this.durationFormatter.format(duration)}</div>
                <div class="task-phases">Phases: ${currentTask.phases.size}</div>
            `;
        }

        // Update task status
        if (this.elements.tasks.status && currentTask) {
            this.elements.tasks.status.className = `task-status status-${currentTask.status}`;
            this.elements.tasks.status.textContent = currentTask.status.toUpperCase();
        }
    }

    /**
     * Utility methods
     */
    collectPreferences() {
        const preferences = {};
        
        // Collect preferences from UI elements
        const checkboxes = document.querySelectorAll('.preference-checkbox');
        checkboxes.forEach(checkbox => {
            preferences[checkbox.name] = checkbox.checked;
        });

        const selects = document.querySelectorAll('.preference-select');
        selects.forEach(select => {
            preferences[select.name] = select.value;
        });

        return preferences;
    }

    clearAllOptions() {
        const checkboxes = document.querySelectorAll('.preference-checkbox');
        checkboxes.forEach(checkbox => {
            checkbox.checked = false;
        });

        const selects = document.querySelectorAll('.preference-select');
        selects.forEach(select => {
            select.selectedIndex = 0;
        });

        this.log('All preferences cleared');
    }

    switchTask(taskId) {
        const task = this.taskState.activeTasks.get(taskId);
        if (task) {
            this.taskState.currentTask = task;
            this.updateTaskUI();
            this.log('Switched to task:', taskId);
        }
    }

    /**
     * Public API methods
     */
    getAgentState() {
        return { ...this.agentState };
    }

    getTaskState() {
        return { ...this.taskState };
    }

    getCurrentTask() {
        return this.taskState.currentTask;
    }

    isAgentRunning() {
        return this.agentState.isRunning;
    }

    getTaskHistory() {
        return [...this.agentState.history];
    }
}

// Make available globally
window.AgentSystemManager = AgentSystemManager;

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = AgentSystemManager;
}
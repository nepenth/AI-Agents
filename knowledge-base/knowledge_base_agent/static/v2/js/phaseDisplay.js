/* V2 PHASEDISPLAY.JS - PHASE AND PROGRESS DISPLAY COMPONENTS */

/**
 * PhaseDisplayManager - Real-time phase status visualization
 * 
 * ARCHITECTURE:
 * - Integrates with ExecutionPlanManager for visual phase progress tracking
 * - Listens to Redis-based events via custom event system
 * - Provides comprehensive phase status updates with timing and error handling
 * - Supports both main phases and sub-phases with hierarchical display
 */
class PhaseDisplayManager {
    constructor() {
        this.phases = new Map();
        this.currentPhase = null;
        this.phaseStartTimes = new Map();
        this.phaseHistory = [];
        
        // UI Elements
        this.phaseContainer = document.getElementById('phase-list');
        this.currentPhaseDisplay = document.getElementById('current-phase-display');
        this.phaseTimingDisplay = document.getElementById('phase-timing-display');
        
        // Phase definitions with hierarchical structure
        this.phaseDefinitions = {
            'initialization': {
                name: 'Initialization',
                description: 'Initializing agent components and validation',
                parent: null,
                estimatedDuration: 30,
                icon: 'fas fa-cog'
            },
            'fetch_bookmarks': {
                name: 'Fetch Bookmarks',
                description: 'Fetching bookmarks from Twitter/X',
                parent: null,
                estimatedDuration: 60,
                icon: 'fas fa-download'
            },
            'content_processing': {
                name: 'Content Processing',
                description: 'Processing tweet content through multiple phases',
                parent: null,
                estimatedDuration: 300,
                icon: 'fas fa-cogs',
                children: ['tweet_caching', 'media_analysis', 'llm_processing', 'kb_item_generation', 'database_sync']
            },
            'tweet_caching': {
                name: 'Tweet Caching',
                description: 'Caching tweet data and metadata',
                parent: 'content_processing',
                estimatedDuration: 60,
                icon: 'fas fa-database'
            },
            'media_analysis': {
                name: 'Media Analysis',
                description: 'Analyzing images and videos with AI',
                parent: 'content_processing',
                estimatedDuration: 120,
                icon: 'fas fa-image'
            },
            'llm_processing': {
                name: 'LLM Processing',
                description: 'Processing content with language models',
                parent: 'content_processing',
                estimatedDuration: 180,
                icon: 'fas fa-brain'
            },
            'kb_item_generation': {
                name: 'KB Item Generation',
                description: 'Generating knowledge base items',
                parent: 'content_processing',
                estimatedDuration: 90,
                icon: 'fas fa-file-alt'
            },
            'database_sync': {
                name: 'Database Sync',
                description: 'Synchronizing data to database',
                parent: 'content_processing',
                estimatedDuration: 30,
                icon: 'fas fa-sync'
            },
            'synthesis_generation': {
                name: 'Synthesis Generation',
                description: 'Generating category syntheses',
                parent: null,
                estimatedDuration: 120,
                icon: 'fas fa-layer-group'
            },
            'embedding_generation': {
                name: 'Embedding Generation',
                description: 'Generating vector embeddings',
                parent: null,
                estimatedDuration: 90,
                icon: 'fas fa-vector-square'
            },
            'readme_generation': {
                name: 'README Generation',
                description: 'Generating README files',
                parent: null,
                estimatedDuration: 60,
                icon: 'fas fa-file-text'
            },
            'git_sync': {
                name: 'Git Sync',
                description: 'Syncing changes to Git repository',
                parent: null,
                estimatedDuration: 45,
                icon: 'fab fa-git-alt'
            }
        };
        
        this.init();
    }
    
    init() {
        this.setupEventListeners();
        this.initializePhaseDisplay();
        
        // Register with component coordinator
        if (window.displayCoordinator) {
            window.displayCoordinator.registerComponent('PhaseDisplayManager', this, {
                priority: 80,
                dependencies: []
            });
        }
        
        console.log('🎯 PhaseDisplayManager initialized');
    }
    
    setupEventListeners() {
        // Listen for phase events from enhanced logging system
        document.addEventListener('phase_start', (event) => {
            this.handlePhaseStart(event.detail);
        });
        
        document.addEventListener('phase_complete', (event) => {
            this.handlePhaseComplete(event.detail);
        });
        
        document.addEventListener('phase_error', (event) => {
            this.handlePhaseError(event.detail);
        });
        
        document.addEventListener('phase_update', (event) => {
            this.handlePhaseUpdate(event.detail);
        });
        
        // Listen for agent status changes
        document.addEventListener('agent_status_update', (event) => {
            this.handleAgentStatusUpdate(event.detail);
        });
    }
    
    initializePhaseDisplay() {
        // Use existing phase list instead of creating new panels
        this.phaseList = document.getElementById('phase-list');
        
        if (this.phaseList) {
            // Map existing phase elements to our phase system
            this.mapExistingPhases();
            console.log('✅ PhaseDisplayManager integrated with existing phase list');
        } else {
            console.warn('Phase list not found, will integrate when available');
        }
        
        // Use existing status indicator instead of creating new one
        this.statusIndicator = document.getElementById('agent-status-text-main');
        
        // Use existing current phase display if available
        this.currentPhaseDisplay = document.getElementById('current-phase-display');
        this.phaseTimingDisplay = document.getElementById('phase-timing-display');
        
        // If current phase display doesn't exist, integrate with status indicator
        if (!this.currentPhaseDisplay && this.statusIndicator) {
            this.integrateWithStatusIndicator();
        }
        
        // Initialize all phases in pending state
        Object.keys(this.phaseDefinitions).forEach(phaseId => {
            this.initializePhase(phaseId);
        });
    }
    
    createCurrentPhaseDisplay() {
        // Create current phase display if it doesn't exist
        const container = document.querySelector('.dashboard-main-area') || document.body;
        
        const currentPhasePanel = document.createElement('div');
        currentPhasePanel.id = 'current-phase-panel';
        currentPhasePanel.className = 'glass-panel-v3--secondary dashboard-panel';
        currentPhasePanel.innerHTML = `
            <div class="panel-header">
                <h3><i class="fas fa-play-circle"></i> Current Phase</h3>
            </div>
            <div class="panel-content">
                <div id="current-phase-display" class="current-phase-display">
                    <div class="phase-status-idle">
                        <i class="fas fa-pause-circle"></i>
                        <span>Agent Idle</span>
                    </div>
                </div>
                <div id="phase-timing-display" class="phase-timing-display" style="display: none;">
                    <div class="timing-info">
                        <span class="timing-label">Elapsed:</span>
                        <span id="phase-elapsed-time">--</span>
                    </div>
                    <div class="timing-info">
                        <span class="timing-label">ETC:</span>
                        <span id="phase-etc-time">--</span>
                    </div>
                </div>
            </div>
        `;
        
        container.appendChild(currentPhasePanel);
        
        this.currentPhaseDisplay = document.getElementById('current-phase-display');
        this.phaseTimingDisplay = document.getElementById('phase-timing-display');
    }
    
    createPhaseTimingDisplay() {
        if (!this.phaseTimingDisplay && this.currentPhaseDisplay) {
            const timingDiv = document.createElement('div');
            timingDiv.id = 'phase-timing-display';
            timingDiv.className = 'phase-timing-display';
            timingDiv.style.display = 'none';
            timingDiv.innerHTML = `
                <div class="timing-info">
                    <span class="timing-label">Elapsed:</span>
                    <span id="phase-elapsed-time">--</span>
                </div>
                <div class="timing-info">
                    <span class="timing-label">ETC:</span>
                    <span id="phase-etc-time">--</span>
                </div>
            `;
            
            this.currentPhaseDisplay.parentNode.appendChild(timingDiv);
            this.phaseTimingDisplay = timingDiv;
        }
    }
    
    mapExistingPhases() {
        // Map existing phase elements in the execution plan to our phase system
        if (!this.phaseList) return;
        
        const existingPhaseElements = this.phaseList.querySelectorAll('.phase-item');
        console.log(`🔗 Found ${existingPhaseElements.length} existing phase elements to map`);
        
        existingPhaseElements.forEach(element => {
            const phaseId = element.dataset.phaseId || element.id;
            if (phaseId && this.phaseDefinitions[phaseId]) {
                // Add progress bar to existing phase element if it doesn't exist
                this.addProgressBarToPhaseElement(element, phaseId);
                console.log(`✅ Mapped existing phase element: ${phaseId}`);
            }
        });
    }
    
    addProgressBarToPhaseElement(phaseElement, phaseId) {
        // Add progress bar to existing phase element
        let progressBar = phaseElement.querySelector('.phase-progress-bar');
        if (!progressBar) {
            progressBar = document.createElement('div');
            progressBar.className = 'phase-progress-bar';
            progressBar.innerHTML = '<div class="progress-fill"></div>';
            progressBar.style.display = 'none'; // Hidden by default
            phaseElement.appendChild(progressBar);
        }
        return progressBar;
    }
    
    integrateWithStatusIndicator() {
        // If no dedicated current phase display, integrate with the main status indicator
        if (!this.statusIndicator) return;
        
        console.log('🔗 Integrating PhaseDisplayManager with status indicator');
        
        // Store original status text
        this.originalStatusText = this.statusIndicator.textContent;
        
        // Add phase information to status indicator when phases are running
        this.statusIndicatorIntegrated = true;
    }
    
    updateStatusIndicatorWithPhase(phase) {
        if (!this.statusIndicatorIntegrated || !this.statusIndicator) return;
        
        if (phase && phase.status === 'running') {
            // Update status indicator with current phase
            this.statusIndicator.textContent = `${phase.name} - ${phase.message || 'Running'}`;
            this.statusIndicator.className = 'glass-badge glass-badge--primary glass-badge--pulse';
        } else {
            // Restore original status
            this.statusIndicator.textContent = this.originalStatusText || 'Idle';
            this.statusIndicator.className = 'glass-badge glass-badge--primary';
        }
    }
    
    initializePhase(phaseId) {
        const definition = this.phaseDefinitions[phaseId];
        if (!definition) return;
        
        const phase = {
            id: phaseId,
            ...definition,
            status: 'pending',
            startTime: null,
            endTime: null,
            duration: null,
            progress: { current: 0, total: 0 },
            error: null,
            message: null
        };
        
        this.phases.set(phaseId, phase);
    }
    
    handlePhaseStart(data) {
        const { phase_name, phase_description, estimated_duration, start_time, task_id } = data;
        
        console.log(`🎯 Phase started: ${phase_name}`, data);
        
        const phase = this.phases.get(phase_name) || this.createDynamicPhase(phase_name, phase_description);
        
        phase.status = 'running';
        phase.startTime = new Date(start_time || Date.now());
        phase.message = phase_description || `Running ${phase.name}`;
        phase.estimatedDuration = estimated_duration || phase.estimatedDuration;
        phase.taskId = task_id;
        
        this.phaseStartTimes.set(phase_name, phase.startTime);
        this.currentPhase = phase_name;
        
        // Update displays
        this.updatePhaseDisplay(phase);
        this.updateCurrentPhaseDisplay(phase);
        this.startTimingUpdates(phase);
        
        // Update execution plan if available
        if (window.executionPlanManager) {
            window.executionPlanManager.updatePhase(phase_name, 'running', phase.message);
        }
        
        // Add to history
        this.phaseHistory.push({
            phase: phase_name,
            action: 'start',
            timestamp: phase.startTime,
            data: data
        });
    }
    
    handlePhaseComplete(data) {
        const { phase_name, result, success, end_time, task_id } = data;
        
        console.log(`✅ Phase completed: ${phase_name}`, data);
        
        const phase = this.phases.get(phase_name);
        if (!phase) return;
        
        phase.status = success !== false ? 'completed' : 'error';
        phase.endTime = new Date(end_time || Date.now());
        phase.duration = phase.endTime - phase.startTime;
        phase.result = result;
        phase.message = success !== false ? `Completed ${phase.name}` : 'Completed with errors';
        
        // Update displays
        this.updatePhaseDisplay(phase);
        this.stopTimingUpdates(phase);
        
        // Update execution plan if available
        if (window.executionPlanManager) {
            window.executionPlanManager.updatePhase(phase_name, phase.status, phase.message);
        }
        
        // Update sub-phases when parent phase completes
        this.updateSubPhasesOnParentComplete(phase_name, phase.status);
        
        // Move to next phase or idle
        this.handlePhaseTransition(phase_name);
        
        // Add to history
        this.phaseHistory.push({
            phase: phase_name,
            action: 'complete',
            timestamp: phase.endTime,
            data: data
        });
    }
    
    handlePhaseError(data) {
        const { phase_name, error, traceback, timestamp, task_id } = data;
        
        console.error(`❌ Phase error: ${phase_name}`, data);
        
        const phase = this.phases.get(phase_name);
        if (!phase) return;
        
        phase.status = 'error';
        phase.endTime = new Date(timestamp || Date.now());
        phase.duration = phase.endTime - phase.startTime;
        phase.error = error;
        phase.traceback = traceback;
        phase.message = `Error: ${error}`;
        
        // Update displays
        this.updatePhaseDisplay(phase);
        this.updateCurrentPhaseDisplay(phase);
        this.stopTimingUpdates(phase);
        
        // Update execution plan if available
        if (window.executionPlanManager) {
            window.executionPlanManager.updatePhase(phase_name, 'error', phase.message);
        }
        
        // Add to history
        this.phaseHistory.push({
            phase: phase_name,
            action: 'error',
            timestamp: phase.endTime,
            data: data
        });
    }
    
    handlePhaseUpdate(data) {
        const { phase_id, phase_name, status, message, processed_count, total_count, progress, total } = data;
        const phaseId = phase_id || phase_name;
        
        if (!phaseId) return;
        
        const phase = this.phases.get(phaseId);
        if (!phase) return;
        
        // Update progress information
        if (processed_count !== undefined && total_count !== undefined) {
            phase.progress = { current: processed_count, total: total_count };
        } else if (progress !== undefined && total !== undefined) {
            phase.progress = { current: progress, total: total };
        }
        
        if (message) {
            phase.message = message;
        }
        
        if (status) {
            phase.status = status;
        }
        
        // Update displays
        this.updatePhaseDisplay(phase);
        
        if (this.currentPhase === phaseId) {
            this.updateCurrentPhaseDisplay(phase);
        }
        
        // Update execution plan if available
        if (window.executionPlanManager) {
            window.executionPlanManager.updatePhaseProgress(phaseId, phase.progress.current, phase.progress.total, phase.message);
        }
    }
    
    handleAgentStatusUpdate(data) {
        const { is_running, status, current_phase_message } = data;
        
        if (!is_running && (status === 'completed' || status === 'idle' || status === 'error')) {
            // Agent finished - reset all phases
            setTimeout(() => {
                this.resetAllPhases();
            }, 2000); // Give time for final phase updates
        }
    }
    
    createDynamicPhase(phaseId, description) {
        const phase = {
            id: phaseId,
            name: this.formatPhaseName(phaseId),
            description: description || `Processing ${phaseId}`,
            parent: null,
            estimatedDuration: 60,
            icon: 'fas fa-cog',
            status: 'pending',
            startTime: null,
            endTime: null,
            duration: null,
            progress: { current: 0, total: 0 },
            error: null,
            message: null
        };
        
        this.phases.set(phaseId, phase);
        return phase;
    }
    
    formatPhaseName(phaseId) {
        return phaseId.split('_')
            .map(word => word.charAt(0).toUpperCase() + word.slice(1))
            .join(' ');
    }
    
    updatePhaseDisplay(phase) {
        // Optimize DOM update using performance optimizer
        if (window.performanceOptimizer) {
            window.performanceOptimizer.optimizeDOMUpdate(() => {
                this.performPhaseDisplayUpdate(phase);
            }, `phase-${phase.id}`, 'normal');
        } else {
            this.performPhaseDisplayUpdate(phase);
        }
    }
    
    performPhaseDisplayUpdate(phase) {
        // Update phase in execution plan if it exists
        const phaseElement = document.querySelector(`[data-phase-id="${phase.id}"]`);
        if (phaseElement) {
            const statusElement = phaseElement.querySelector('.phase-status');
            if (statusElement) {
                // Update status text and styling based on phase status
                const statusText = this.getStatusText(phase);
                const statusClass = this.getStatusClass(phase.status);
                
                statusElement.textContent = statusText;
                statusElement.dataset.status = phase.status;
                statusElement.className = `phase-status glass-badge ${statusClass}`;
            }
            
            // Update progress bar if available
            let progressElement = phaseElement.querySelector('.phase-progress-bar');
            if (!progressElement && phase.progress.total > 0) {
                // Create progress bar if it doesn't exist
                progressElement = this.addProgressBarToPhaseElement(phaseElement, phase.id);
            }
            
            if (progressElement && phase.progress.total > 0) {
                const progressFill = progressElement.querySelector('.progress-fill');
                const percentage = (phase.progress.current / phase.progress.total) * 100;
                progressFill.style.width = `${percentage}%`;
                progressElement.style.display = 'block';
                
                // Add progress text if not present
                let progressText = progressElement.querySelector('.progress-text');
                if (!progressText) {
                    progressText = document.createElement('div');
                    progressText.className = 'progress-text';
                    progressElement.appendChild(progressText);
                }
                progressText.textContent = `${phase.progress.current}/${phase.progress.total}`;
            } else if (progressElement) {
                progressElement.style.display = 'none';
            }
            
            // Update phase icon based on status
            const iconElement = phaseElement.querySelector('.phase-icon, .sub-phase-icon');
            if (iconElement) {
                const newIcon = this.getPhaseIcon(phase);
                iconElement.className = `${iconElement.classList.contains('sub-phase-icon') ? 'sub-phase-icon' : 'phase-icon'} ${newIcon}`;
            }
        }
    }
    
    getStatusText(phase) {
        switch (phase.status) {
            case 'pending':
                return 'Will Run';
            case 'running':
                return phase.message || 'Running';
            case 'completed':
                return 'Completed';
            case 'error':
                return 'Error';
            case 'skipped':
                return 'Skipped';
            default:
                return phase.status;
        }
    }
    
    getStatusClass(status) {
        switch (status) {
            case 'pending':
                return 'glass-badge--primary';
            case 'running':
                return 'glass-badge--warning glass-badge--pulse';
            case 'completed':
                return 'glass-badge--success';
            case 'error':
                return 'glass-badge--danger';
            case 'skipped':
                return 'glass-badge--secondary';
            default:
                return 'glass-badge--primary';
        }
    }
    
    updateCurrentPhaseDisplay(phase) {
        // Update dedicated current phase display if available
        if (this.currentPhaseDisplay) {
            const statusClass = `phase-status-${phase.status}`;
            const icon = this.getPhaseIcon(phase);
            
            this.currentPhaseDisplay.innerHTML = `
                <div class="${statusClass}">
                    <i class="${icon}"></i>
                    <div class="phase-info">
                        <div class="phase-name">${phase.name}</div>
                        <div class="phase-message">${phase.message || phase.description}</div>
                        ${phase.progress.total > 0 ? `
                            <div class="phase-progress-inline">
                                <span>${phase.progress.current}/${phase.progress.total}</span>
                                <div class="progress-bar-inline">
                                    <div class="progress-fill" style="width: ${(phase.progress.current / phase.progress.total) * 100}%"></div>
                                </div>
                            </div>
                        ` : ''}
                        ${phase.error ? `
                            <div class="phase-error">
                                <i class="fas fa-exclamation-triangle"></i>
                                <span>${phase.error}</span>
                            </div>
                        ` : ''}
                    </div>
                </div>
            `;
            
            // Show timing display for running phases
            if (phase.status === 'running' && this.phaseTimingDisplay) {
                this.phaseTimingDisplay.style.display = 'block';
            }
        }
        
        // Also update status indicator integration if active
        this.updateStatusIndicatorWithPhase(phase);
    }
    
    getPhaseIcon(phase) {
        const iconMap = {
            'pending': 'fas fa-clock',
            'running': 'fas fa-spinner fa-spin',
            'completed': 'fas fa-check-circle',
            'error': 'fas fa-exclamation-circle',
            'skipped': 'fas fa-forward'
        };
        
        return iconMap[phase.status] || phase.icon || 'fas fa-cog';
    }
    
    startTimingUpdates(phase) {
        if (phase.timingInterval) {
            clearInterval(phase.timingInterval);
        }
        
        phase.timingInterval = setInterval(() => {
            this.updateTimingDisplay(phase);
        }, 1000);
    }
    
    stopTimingUpdates(phase) {
        if (phase.timingInterval) {
            clearInterval(phase.timingInterval);
            phase.timingInterval = null;
        }
    }
    
    updateTimingDisplay(phase) {
        if (!this.phaseTimingDisplay || phase.status !== 'running') return;
        
        const now = new Date();
        const elapsed = now - phase.startTime;
        const elapsedText = this.formatDuration(elapsed);
        
        const elapsedElement = document.getElementById('phase-elapsed-time');
        if (elapsedElement) {
            elapsedElement.textContent = elapsedText;
        }
        
        // Calculate ETC if we have progress
        if (phase.progress.total > 0 && phase.progress.current > 0) {
            const progressPercent = phase.progress.current / phase.progress.total;
            const estimatedTotal = elapsed / progressPercent;
            const remaining = estimatedTotal - elapsed;
            
            const etcElement = document.getElementById('phase-etc-time');
            if (etcElement && remaining > 0) {
                etcElement.textContent = this.formatDuration(remaining);
            }
        } else if (phase.estimatedDuration) {
            // Use estimated duration
            const remaining = (phase.estimatedDuration * 1000) - elapsed;
            const etcElement = document.getElementById('phase-etc-time');
            if (etcElement && remaining > 0) {
                etcElement.textContent = this.formatDuration(remaining);
            }
        }
    }
    
    formatDuration(milliseconds) {
        const seconds = Math.floor(milliseconds / 1000);
        const minutes = Math.floor(seconds / 60);
        const hours = Math.floor(minutes / 60);
        
        if (hours > 0) {
            return `${hours}h ${minutes % 60}m ${seconds % 60}s`;
        } else if (minutes > 0) {
            return `${minutes}m ${seconds % 60}s`;
        } else {
            return `${seconds}s`;
        }
    }
    
    handlePhaseTransition(completedPhaseId) {
        // Determine next phase based on execution order
        const phaseOrder = [
            'initialization',
            'fetch_bookmarks', 
            'content_processing',
            'database_sync',
            'synthesis_generation',
            'embedding_generation',
            'readme_generation',
            'git_sync'
        ];
        
        const currentIndex = phaseOrder.indexOf(completedPhaseId);
        if (currentIndex >= 0 && currentIndex < phaseOrder.length - 1) {
            // There might be a next phase, but don't assume it will start
            this.currentPhase = null;
        } else {
            // Last phase completed
            this.currentPhase = null;
            this.showIdleState();
        }
    }
    
    showIdleState() {
        if (this.currentPhaseDisplay) {
            this.currentPhaseDisplay.innerHTML = `
                <div class="phase-status-idle">
                    <i class="fas fa-pause-circle"></i>
                    <div class="phase-info">
                        <div class="phase-name">Agent Idle</div>
                        <div class="phase-message">Waiting for next execution</div>
                    </div>
                </div>
            `;
        }
        
        if (this.phaseTimingDisplay) {
            this.phaseTimingDisplay.style.display = 'none';
        }
    }
    
    updateSubPhasesOnParentComplete(parentPhaseId, parentStatus) {
        // When a parent phase completes, update all its sub-phases to show completion status
        const parentDefinition = this.phaseDefinitions[parentPhaseId];
        if (!parentDefinition || !parentDefinition.children) return;
        
        console.log(`🔄 Updating sub-phases for completed parent: ${parentPhaseId}`);
        
        parentDefinition.children.forEach(subPhaseId => {
            const subPhase = this.phases.get(subPhaseId);
            if (subPhase && subPhase.status === 'pending') {
                // Update sub-phase to show it completed as part of the parent phase
                subPhase.status = parentStatus === 'completed' ? 'completed' : 'skipped';
                subPhase.message = parentStatus === 'completed' ? 
                    `Completed as part of ${parentDefinition.name}` : 
                    `Skipped with ${parentDefinition.name}`;
                subPhase.endTime = new Date();
                
                // Update the display
                this.updatePhaseDisplay(subPhase);
                
                // Update execution plan if available
                if (window.executionPlanManager) {
                    window.executionPlanManager.updatePhase(subPhaseId, subPhase.status, subPhase.message);
                }
                
                console.log(`✅ Updated sub-phase ${subPhaseId} to ${subPhase.status}`);
            }
        });
    }

    resetAllPhases() {
        console.log('🔄 Resetting all phases');
        
        // Stop all timing intervals
        this.phases.forEach(phase => {
            this.stopTimingUpdates(phase);
        });
        
        // Reset phase states
        this.phases.forEach(phase => {
            phase.status = 'pending';
            phase.startTime = null;
            phase.endTime = null;
            phase.duration = null;
            phase.progress = { current: 0, total: 0 };
            phase.error = null;
            phase.message = null;
        });
        
        this.currentPhase = null;
        this.phaseStartTimes.clear();
        
        // Update displays
        this.showIdleState();
        
        // Reset execution plan if available
        if (window.executionPlanManager) {
            window.executionPlanManager.resetAllPhases();
        }
    }
    
    // === PUBLIC API ===
    
    getPhaseStatus(phaseId) {
        const phase = this.phases.get(phaseId);
        return phase ? { ...phase } : null;
    }
    
    getAllPhases() {
        return Array.from(this.phases.values());
    }
    
    getPhaseHistory() {
        return [...this.phaseHistory];
    }
    
    getCurrentPhase() {
        return this.currentPhase ? this.phases.get(this.currentPhase) : null;
    }
    
    getPhaseStatistics() {
        const stats = {
            total: this.phases.size,
            pending: 0,
            running: 0,
            completed: 0,
            error: 0,
            skipped: 0
        };
        
        this.phases.forEach(phase => {
            stats[phase.status] = (stats[phase.status] || 0) + 1;
        });
        
        return stats;
    }
}

// Make globally available
window.PhaseDisplayManager = PhaseDisplayManager;
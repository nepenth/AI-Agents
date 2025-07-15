/* V2 EXECUTIONPLAN.JS - LOGIC FOR THE EXECUTION PLAN PANEL */

// Execution Plan Manager – define only once to avoid redeclaration when the
// script gets injected multiple times (SPA navigations).

if (typeof window.ExecutionPlanManager === 'undefined') {

class ExecutionPlanManager {
    constructor() {
        this.phaseList = document.getElementById('phase-list');
        if (!this.phaseList) return;

        this.phases = {};
        this.forceReprocessPhases = ['tweet_caching', 'media_analysis', 'llm_processing', 'kb_item_generation', 'synthesis_generation'];
        this.initPhases();
        this.attachEventListeners();
        this.initSocketListeners(); // Add this line
    }

    attachEventListeners() {
        document.addEventListener('preferences-updated', (e) => {
            this.updatePlanForPreferences(e.detail.preferences);
        });
    }

    initSocketListeners() {
        // Updated to use custom events from polling system instead of SocketIO
        console.log('Setting up ExecutionPlan event listeners for polling-based updates...');

        // Listen for phase updates from the polling system
        document.addEventListener('phase_update', (event) => {
            const data = event.detail;
            console.log('Received phase_update:', data);
            const phaseId = data.phase_id || data.phase;
            this.updatePhase(phaseId, data.status, data.message);
            
            // Handle progress bar if counts provided
            if (data.processed_count !== undefined && data.total_count !== undefined) {
                this.updatePhaseProgress(phaseId, data.processed_count, data.total_count, data.message);
            } else if (data.progress !== undefined && data.total !== undefined) {
                this.updatePhaseProgress(phaseId, data.progress, data.total, data.message);
            }
        });

        // Listen for agent status updates from the polling system
        document.addEventListener('agent_status_update', (event) => {
            const data = event.detail;
            if (!data.is_running && (data.status === 'completed' || data.status === 'error' || data.status === 'idle')) {
                // Use a timeout to give final updates time to arrive
                setTimeout(() => this.resetAllPhases(), 2000);
            }
        });

        console.log('ExecutionPlan event listeners set up for polling-based updates');
    }

    initPhases() {
        this.phaseList.querySelectorAll('.phase-item').forEach(item => {
            const phaseId = item.dataset.phaseId;
            if (phaseId) {
                this.phases[phaseId] = {
                    element: item,
                    statusElement: item.querySelector('.phase-status'),
                    progressElement: item.querySelector('.phase-progress-bar'),
                    // Store which runs this phase belongs to
                    runs: {
                        full: item.dataset.runFull === 'true',
                        synthesis: item.dataset.runSynthesis === 'true',
                        embedding: item.dataset.runEmbedding === 'true',
                        fetch: item.dataset.runFetch === 'true',
                        git: item.dataset.runGit === 'true'
                    }
                };
            }
        });
        console.log('Initialized phases:', this.phases);
        // Initial update: assume full pipeline on first load
        this.updatePlanForPreferences({ run_mode: 'full_pipeline' });
    }

    updatePhaseProgress(phaseId, progress, total, message) {
        const phase = this.phases[phaseId];
        if (!phase || !phase.progressElement) return;

        const progressBar = phase.progressElement.querySelector('div');
        if (progress > 0 && total > 0) {
            const percentage = (progress / total) * 100;
            progressBar.style.width = `${percentage}%`;
            phase.progressElement.style.display = 'block';
        } else {
            phase.progressElement.style.display = 'none';
        }

        if(message) {
            // Maybe add a text element for this later
        }
    }

    updatePlanForPreferences(preferences) {
        console.log('ExecutionPlanManager.updatePlanForPreferences called with:', preferences);
        
        // Determine the run mode
        const mode = preferences.run_mode || 'full_pipeline';
        console.log('Run mode:', mode);

        for (const phaseId in this.phases) {
            const phase = this.phases[phaseId];
            let shouldRun = false;
            let status = 'pending';
            let message = 'Will Run';

            // Determine if phase should run based on run mode
            switch (mode) {
                case 'synthesis_only':
                    shouldRun = phase.runs.synthesis;
                    break;
                case 'embedding_only':
                    shouldRun = phase.runs.embedding;
                    break;
                case 'fetch_only':
                    shouldRun = phase.runs.fetch;
                    break;
                case 'git_sync_only':
                    shouldRun = phase.runs.git;
                    break;
                case 'full_pipeline':
                default:
                    shouldRun = phase.runs.full;
                    break;
            }

            // Apply skip preferences for full_pipeline mode
            if (mode === 'full_pipeline' && shouldRun) {
                if (phaseId === 'fetch_bookmarks' && preferences.skip_fetch_bookmarks) {
                    shouldRun = false;
                    status = 'skipped';
                    message = 'WILL SKIP';
                } else if (phaseId === 'content_processing' && preferences.skip_process_content) {
                    shouldRun = false;
                    status = 'skipped';
                    message = 'WILL SKIP';
                } else if (phaseId === 'synthesis_generation' && preferences.skip_synthesis_generation) {
                    shouldRun = false;
                    status = 'skipped';
                    message = 'WILL SKIP';
                } else if (phaseId === 'embedding_generation' && preferences.skip_embedding_generation) {
                    shouldRun = false;
                    status = 'skipped';
                    message = 'WILL SKIP';
                } else if (phaseId === 'readme_generation' && preferences.skip_readme_generation) {
                    shouldRun = false;
                    status = 'skipped';
                    message = 'WILL SKIP';
                } else if (phaseId === 'git_sync' && preferences.skip_git_push) {
                    shouldRun = false;
                    status = 'skipped';
                    message = 'WILL SKIP';
                }
            }

            // Apply force flags to specific phases only (if phase should run and isn't skipped)
            if (shouldRun && status !== 'skipped') {
                let isForced = false;
                let forceReason = '';

                // Check specific force flags for specific phases
                if (phaseId === 'tweet_caching' && preferences.force_recache_tweets) {
                    isForced = true;
                    forceReason = 'Force Recache Tweets';
                } else if (phaseId === 'media_analysis' && preferences.force_reprocess_media) {
                    isForced = true;
                    forceReason = 'Force Reprocess Media';
                } else if (phaseId === 'llm_processing' && preferences.force_reprocess_llm) {
                    isForced = true;
                    forceReason = 'Force Reprocess LLM';
                } else if (phaseId === 'kb_item_generation' && preferences.force_reprocess_kb_item) {
                    isForced = true;
                    forceReason = 'Force Reprocess KB Items';
                } else if (phaseId === 'synthesis_generation' && preferences.force_regenerate_synthesis) {
                    isForced = true;
                    forceReason = 'Force Regenerate Synthesis';
                } else if (phaseId === 'embedding_generation' && preferences.force_regenerate_embeddings) {
                    isForced = true;
                    forceReason = 'Force Regenerate Embeddings';
                } else if (phaseId === 'readme_generation' && preferences.force_regenerate_readme) {
                    isForced = true;
                    forceReason = 'Force Regenerate README';
                }

                // Handle legacy force_reprocess_content and force_reprocess_all flags
                if (!isForced && (preferences.force_reprocess_content || preferences.force_reprocess_all)) {
                    // These flags affect all content processing sub-phases
                    if (this.forceReprocessPhases.includes(phaseId)) {
                        isForced = true;
                        forceReason = 'Force Reprocess All Content';
                    }
                }

                if (isForced) {
                    status = 'force_regenerate';
                    message = forceReason;
                }
            }

            // If run mode doesn't include this phase, mark as skipped
            if (!shouldRun && status === 'pending') {
                status = 'skipped';
                message = 'WILL SKIP';
            }

            console.log(`Phase ${phaseId}: shouldRun=${shouldRun}, status=${status}, message=${message}`);
            
            // Update the phase UI
            this.updatePhase(phaseId, status, message);
            
            // Always show all phases in the execution plan
            // Instead of hiding phases, we show them with appropriate status
            if (phase.element) {
                phase.element.style.display = ''; // Always show
            }
        }
    }

    // Added for backward-compatibility with older code that still calls
    // `updateExecutionPlan` on the manager instance.
    updateExecutionPlan(preferences) {
        this.updatePlanForPreferences(preferences);
    }

    updatePhase(phaseId, status, message) {
        const phase = this.phases[phaseId];
        if (!phase) {
            console.warn(`Phase with ID '${phaseId}' not found in UI.`);
            return;
        }

        // Capitalize status
        const displayStatus = status.charAt(0).toUpperCase() + status.slice(1);
        
        phase.statusElement.textContent = message || displayStatus;
        phase.statusElement.dataset.status = status;
        
        // Handle parent-child phase relationships
        this.updateParentPhaseStatus(phaseId, status);
    }

    updateParentPhaseStatus(childPhaseId, childStatus) {
        // Define parent-child relationships
        const parentChildMap = {
            'tweet_caching': 'content_processing',
            'media_analysis': 'content_processing', 
            'llm_processing': 'content_processing',
            'kb_item_generation': 'content_processing',
            'database_sync': 'content_processing'
        };
        
        const parentPhaseId = parentChildMap[childPhaseId];
        if (!parentPhaseId || !this.phases[parentPhaseId]) {
            return; // No parent or parent not found
        }
        
        // If child is running/active/in_progress, parent should be running
        if (['running', 'active', 'in_progress', 'in-progress'].includes(childStatus.toLowerCase())) {
            const parentPhase = this.phases[parentPhaseId];
            if (parentPhase.statusElement.dataset.status !== 'running') {
                parentPhase.statusElement.textContent = 'Running';
                parentPhase.statusElement.dataset.status = 'running';
            }
        }
        
        // If child completes, check if all children are complete to mark parent complete
        if (['completed', 'skipped'].includes(childStatus.toLowerCase())) {
            this.checkParentCompletion(parentPhaseId);
        }
    }

    checkParentCompletion(parentPhaseId) {
        // Define which children belong to each parent
        const childrenMap = {
            'content_processing': ['tweet_caching', 'media_analysis', 'llm_processing', 'kb_item_generation', 'database_sync']
        };
        
        const children = childrenMap[parentPhaseId];
        if (!children) return;
        
        // Check if all children are completed or skipped
        const allChildrenComplete = children.every(childId => {
            const childPhase = this.phases[childId];
            if (!childPhase) return true; // If child doesn't exist, consider it complete
            
            const status = childPhase.statusElement.dataset.status;
            return ['completed', 'skipped'].includes(status);
        });
        
        if (allChildrenComplete) {
            const parentPhase = this.phases[parentPhaseId];
            parentPhase.statusElement.textContent = 'Completed';
            parentPhase.statusElement.dataset.status = 'completed';
        }
    }

    resetAllPhases() {
        for (const phaseId in this.phases) {
            this.updatePhase(phaseId, 'pending', 'Will Run');
            this.phases[phaseId].element.style.display = '';
            if (this.phases[phaseId].progressElement) {
                this.phases[phaseId].progressElement.style.display = 'none';
                this.phases[phaseId].progressElement.querySelector('div').style.width = '0%';
            }
        }
    }
}

// Make globally available for non-module usage
window.ExecutionPlanManager = ExecutionPlanManager;
} 
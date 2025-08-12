/* V2 EXECUTIONPLAN.JS - LOGIC FOR THE EXECUTION PLAN PANEL */

// Execution Plan Manager – define only once to avoid redeclaration when the
// script gets injected multiple times (SPA navigations).

if (typeof window.ExecutionPlanManager === 'undefined') {

    class ExecutionPlanManager {
        constructor() {
            this.phaseList = document.getElementById('phase-list');
            if (!this.phaseList) return;

            this.phases = {};
            this.hasInitialized = false; // Track if we've initialized with running task
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

                // CRITICAL FIX: Ensure sequential phase execution
                // When a phase becomes active, ensure previous phases are completed and future phases are pending
                if (data.status === 'active' || data.status === 'running' || data.status === 'in_progress') {
                    this.enforceSequentialPhaseExecution(phaseId);
                }

                // Extract counts data for completion status
                const counts = {};
                if (data.processed_count !== undefined) counts.processed_count = data.processed_count;
                if (data.total_count !== undefined) counts.total_count = data.total_count;
                if (data.skipped_count !== undefined) counts.skipped_count = data.skipped_count;

                this.updatePhase(phaseId, data.status, data.message, Object.keys(counts).length > 0 ? counts : null);

                // Handle progress bar if counts provided
                if (data.processed_count !== undefined && data.total_count !== undefined) {
                    this.updatePhaseProgress(phaseId, data.processed_count, data.total_count, data.message);
                } else if (data.progress !== undefined && data.total !== undefined) {
                    this.updatePhaseProgress(phaseId, data.progress, data.total, data.message);
                }

                // Handle ETC display if provided
                if (data.etc || data.estimated_completion || data.time_remaining) {
                    this.updatePhaseETC(phaseId, data.etc || data.estimated_completion || data.time_remaining);
                }
            });

            // Listen for agent status updates from the polling system
            document.addEventListener('agent_status_update', (event) => {
                const data = event.detail;
                console.log('ExecutionPlan received agent_status_update:', data);

                // Update phases based on current status
                if (data.is_running) {
                    // Agent is running - update current phase
                    if (data.current_phase_message || data.phase_id) {
                        const phaseId = this.mapMessageToPhaseId(data.current_phase_message || data.phase_id);
                        if (phaseId) {
                            this.updatePhase(phaseId, 'running', data.current_phase_message);
                        }
                    }
                } else if (data.status === 'completed' || data.status === 'error' || data.status === 'idle') {
                    // Use a timeout to give final updates time to arrive
                    setTimeout(() => this.resetAllPhases(), 2000);
                }
            });

            // Listen for enhanced structured phase events
            document.addEventListener('phase_start', (event) => {
                const data = event.detail;
                console.log('ExecutionPlan received phase_start:', data);
                const phaseId = this.mapMessageToPhaseId(data.phase_name);
                if (phaseId) {
                    this.updatePhase(phaseId, 'running', `Starting ${data.phase_name}`);
                }
            });

            document.addEventListener('phase_complete', (event) => {
                const data = event.detail;
                console.log('ExecutionPlan received phase_complete:', data);
                const phaseId = this.mapMessageToPhaseId(data.phase_name);
                if (phaseId) {
                    // Extract completion counts from result
                    const counts = {};
                    if (data.result && typeof data.result === 'object') {
                        if (data.result.processed_count !== undefined) counts.processed_count = data.result.processed_count;
                        if (data.result.total_count !== undefined) counts.total_count = data.result.total_count;
                        if (data.result.skipped_count !== undefined) counts.skipped_count = data.result.skipped_count;
                    }

                    this.updatePhase(phaseId, 'completed', `Completed ${data.phase_name}`, Object.keys(counts).length > 0 ? counts : null);
                }
            });

            document.addEventListener('phase_error', (event) => {
                const data = event.detail;
                console.log('ExecutionPlan received phase_error:', data);
                const phaseId = this.mapMessageToPhaseId(data.phase_name);
                if (phaseId) {
                    this.updatePhase(phaseId, 'error', `Error: ${data.error}`);
                }
            });

            // Listen for agent execution completion to reset phases
            document.addEventListener('agent_execution_completed', (event) => {
                console.log('ExecutionPlan received agent_execution_completed:', event.detail);
                // Give a brief delay to allow final phase updates to arrive
                setTimeout(() => {
                    console.log('🎉 Agent execution completed - resetting execution plan to default state');
                    this.resetAllPhases();
                }, 1000);
            });

            // CRITICAL FIX: Listen for running task detection on page load
            document.addEventListener('running_task_detected', (event) => {
                console.log('ExecutionPlan received running_task_detected:', event.detail);
                const taskStatus = event.detail.status;
                if (taskStatus) {
                    this.initializeWithRunningTask(taskStatus);
                }
            });

            // CRITICAL FIX: Also listen for initial agent status updates
            document.addEventListener('agent_status_update', (event) => {
                const statusData = event.detail;
                console.log('ExecutionPlan received agent_status_update:', statusData);

                // If this is the first status update and agent is running, initialize
                if (statusData.is_running && statusData.task_id && !this.hasInitialized) {
                    console.log('🔄 ExecutionPlan: Initializing with running task from status update');
                    this.initializeWithRunningTask(statusData);
                    this.hasInitialized = true;
                }
            });

            console.log('ExecutionPlan event listeners set up for polling-based updates');
        }

        mapMessageToPhaseId(message) {
            if (!message) return null;

            // Normalize to string when possible
            if (typeof message !== 'string') {
                try {
                    if (typeof message?.phase_id === 'string') {
                        message = message.phase_id;
                    } else {
                        message = String(message);
                    }
                } catch (_) {
                    return null;
                }
            }

            console.log(`🔍 Mapping message to phase ID: "${message}"`);

            // Map phase messages/names to phase IDs
            const messageToPhaseMap = {
                'initialization': 'initialization',
                'fetch_bookmarks': 'fetch_bookmarks',
                'content_processing': 'content_processing',
                'tweet_caching': 'tweet_caching',
                'media_analysis': 'media_analysis',
                'llm_processing': 'llm_processing',
                'kb_item_generation': 'kb_item_generation',
                'synthesis_generation': 'synthesis_generation',
                'embedding_generation': 'embedding_generation',
                'readme_generation': 'readme_generation',
                'git_sync': 'git_sync'
            };

            // Direct mapping first
            if (messageToPhaseMap[message]) {
                console.log(`✅ Direct mapping found: ${message} -> ${messageToPhaseMap[message]}`);
                return messageToPhaseMap[message];
            }

            // Try to extract phase ID from message text
            const lowerMessage = message.toLowerCase();

            // Ignore non-phase markers that the backend may send early
            const nonPhaseStates = new Set(['queued', 'unknown', 'starting', 'idle']);
            if (nonPhaseStates.has(lowerMessage)) {
                console.log(`ℹ️ Ignoring non-phase state: ${lowerMessage}`);
                return null;
            }
            console.log(`🔍 Trying fuzzy matching for: "${lowerMessage}"`);

            // Enhanced fuzzy matching with priority order (most specific first)

            // PRIORITY 1: Very specific synthesis patterns
            if (lowerMessage.includes('generating subcategory synthesis') ||
                lowerMessage.includes('subcategory synthesis') ||
                lowerMessage.includes('synthesis generation') ||
                lowerMessage.includes('synthesis for') ||
                (lowerMessage.includes('generating') && lowerMessage.includes('synthesis')) ||
                (lowerMessage.includes('completed synthesis') && lowerMessage.includes('generation'))) {
                console.log(`✅ Fuzzy match (high priority): synthesis_generation`);
                return 'synthesis_generation';
            }

            // PRIORITY 2: Other synthesis patterns
            if (lowerMessage.includes('synthesis')) {
                console.log(`✅ Fuzzy match: synthesis_generation`);
                return 'synthesis_generation';
            }

            // PRIORITY 3: Embedding patterns
            if (lowerMessage.includes('embedding')) {
                console.log(`✅ Fuzzy match: embedding_generation`);
                return 'embedding_generation';
            }

            // PRIORITY 4: README patterns
            if (lowerMessage.includes('readme')) {
                console.log(`✅ Fuzzy match: readme_generation`);
                return 'readme_generation';
            }

            // PRIORITY 5: Git patterns
            if (lowerMessage.includes('git') || lowerMessage.includes('push')) {
                console.log(`✅ Fuzzy match: git_sync`);
                return 'git_sync';
            }



            // PRIORITY 7: Fetch patterns
            if (lowerMessage.includes('fetch') || lowerMessage.includes('bookmark')) {
                console.log(`✅ Fuzzy match: fetch_bookmarks`);
                return 'fetch_bookmarks';
            }

            // PRIORITY 8: Content processing (most generic, last)
            if (lowerMessage.includes('processing') || lowerMessage.includes('content')) {
                console.log(`✅ Fuzzy match: content_processing`);
                return 'content_processing';
            }

            // Try original logic as fallback
            for (const [key, phaseId] of Object.entries(messageToPhaseMap)) {
                if (lowerMessage.includes(key.replace('_', ' ')) || lowerMessage.includes(key)) {
                    console.log(`✅ Fallback match: ${key} -> ${phaseId}`);
                    return phaseId;
                }
            }

            console.log(`⚠️ No mapping found for: "${message}"`);
            return null; // Do not attempt to update phases for unknown labels
        }

        resetAllPhases() {
            // Reset all phases to their default "Will Run" state
            console.log('🔄 Resetting all phases to default state');

            for (const phaseId in this.phases) {
                const phase = this.phases[phaseId];
                if (phase && phase.statusElement) {
                    // Reset to default state
                    phase.statusElement.textContent = 'Will Run';
                    phase.statusElement.dataset.status = 'pending';
                    phase.statusElement.className = 'phase-status glass-badge glass-badge--primary';

                    // Hide progress bars
                    if (phase.progressElement) {
                        phase.progressElement.style.display = 'none';
                    }

                    // Clear stored counts
                    delete phase.counts;
                }
            }

            console.log('✅ All phases reset to default state');
        }

        initializeWithRunningTask(taskStatus) {
            console.log('🔄 Initializing execution plan with running task data:', taskStatus);

            // First, reset all phases to ensure clean state
            this.resetAllPhases();

            // Extract current phase information with better mapping
            let currentPhase = taskStatus.progress?.phase_id;

            // If no phase_id, try to map from message
            if (!currentPhase && taskStatus.current_phase_message) {
                currentPhase = this.mapMessageToPhaseId(taskStatus.current_phase_message);
            }

            // Default fallback
            if (!currentPhase) {
                currentPhase = 'content_processing';
            }

            const currentMessage = taskStatus.progress?.message ||
                taskStatus.current_phase_message ||
                'Processing...';

            const currentProgress = taskStatus.progress?.progress || 0;
            const processedCount = taskStatus.progress?.processed_count;
            const totalCount = taskStatus.progress?.total_count;

            console.log(`📊 Current phase: ${currentPhase}, Message: ${currentMessage}, Progress: ${currentProgress}%`);
            console.log(`📊 Raw task status:`, taskStatus);

            // CRITICAL FIX: Updated phase order - DB sync after synthesis generation (or removed entirely)
            const phaseOrder = [
                'initialization',
                'fetch_bookmarks',
                'content_processing',
                'tweet_caching',
                'media_analysis',
                'llm_processing',
                'kb_item_generation',
                'synthesis_generation',
                'embedding_generation',
                'readme_generation',
                'git_sync'
                // NOTE: database_sync removed as it's now redundant with unified database model
            ];

            // Find current phase index with fuzzy matching
            let currentPhaseIndex = phaseOrder.indexOf(currentPhase);

            // If exact match not found, try fuzzy matching
            if (currentPhaseIndex === -1) {
                const lowerMessage = currentMessage.toLowerCase();

                // Map common phase messages to phase IDs
                if (lowerMessage.includes('synthesis') || lowerMessage.includes('generating subcategory')) {
                    currentPhase = 'synthesis_generation';
                    currentPhaseIndex = phaseOrder.indexOf('synthesis_generation');
                } else if (lowerMessage.includes('embedding')) {
                    currentPhase = 'embedding_generation';
                    currentPhaseIndex = phaseOrder.indexOf('embedding_generation');
                } else if (lowerMessage.includes('readme')) {
                    currentPhase = 'readme_generation';
                    currentPhaseIndex = phaseOrder.indexOf('readme_generation');
                } else if (lowerMessage.includes('git') || lowerMessage.includes('push')) {
                    currentPhase = 'git_sync';
                    currentPhaseIndex = phaseOrder.indexOf('git_sync');
                } else if (lowerMessage.includes('database') || lowerMessage.includes('sync')) {
                    // Database sync phase removed - skip this condition
                } else if (lowerMessage.includes('processing') || lowerMessage.includes('content')) {
                    currentPhase = 'content_processing';
                    currentPhaseIndex = phaseOrder.indexOf('content_processing');
                }
            }

            console.log(`📊 Mapped phase: ${currentPhase} (index: ${currentPhaseIndex})`);

            // CRITICAL FIX: Ensure only one phase is active at a time
            // Mark all phases as pending first
            for (const phaseId of phaseOrder) {
                if (this.phases[phaseId]) {
                    this.updatePhase(phaseId, 'pending', 'Will Run');
                }
            }

            // Mark previous phases as completed with appropriate messages
            if (currentPhaseIndex > 0) {
                console.log(`📊 Marking ${currentPhaseIndex} previous phases as completed`);
                for (let i = 0; i < currentPhaseIndex; i++) {
                    const phaseId = phaseOrder[i];
                    if (this.phases[phaseId]) {
                        // Use phase-specific completion messages instead of generic "Completed"
                        const completionMessage = this.getPhaseCompletionMessage(phaseId);
                        this.updatePhase(phaseId, 'completed', completionMessage);
                        console.log(`✅ Marked ${phaseId} as completed with message: ${completionMessage}`);
                    } else {
                        console.warn(`⚠️ Previous phase ${phaseId} not found in phases object`);
                    }
                }
            } else {
                console.log(`📊 Current phase is first in sequence, no previous phases to mark as completed`);
            }

            // Update the current phase as running (AFTER marking previous phases as completed)
            if (this.phases[currentPhase]) {
                this.updatePhase(currentPhase, 'running', currentMessage);

                // If we have progress data, show it
                if (processedCount !== undefined && totalCount !== undefined) {
                    this.updatePhaseProgress(currentPhase, processedCount, totalCount, currentMessage);
                }
            } else {
                console.warn(`⚠️ Phase ${currentPhase} not found in phases object`);
            }

            console.log('✅ Execution plan initialized with running task state');
        }

        initPhases() {
            this.phaseList.querySelectorAll('.phase-item').forEach(item => {
                const phaseId = item.dataset.phaseId;
                if (phaseId) {
                    this.phases[phaseId] = {
                        element: item,
                        statusElement: item.querySelector('.phase-status'),
                        progressElement: item.querySelector('.phase-progress-bar'),
                        etcElement: item.querySelector('.phase-etc'), // Add ETC element reference
                        // Store which runs this phase belongs to
                        runs: {
                            full: item.dataset.runFull === 'true',
                            synthesis: item.dataset.runSynthesis === 'true',
                            embedding: item.dataset.runEmbedding === 'true',
                            fetch: item.dataset.runFetch === 'true',
                            git: item.dataset.runGit === 'true'
                        },
                        // Track current state for cycling
                        currentState: 'run', // 'run', 'skip', 'force'
                        canForce: this.canPhaseBeForced(phaseId),
                        // ETC tracking
                        etcData: null
                    };

                    // ENHANCEMENT: Make phases clickable to cycle through states
                    this.makePhaseClickable(phaseId, item);
                }
            });
            console.log('Initialized phases:', this.phases);

            // Load persisted state or check current agent status
            this.loadPersistedState();
        }

        canPhaseBeForced(phaseId) {
            // Define which phases can be forced
            const forceablePhases = [
                'tweet_caching',      // force_recache_tweets
                'media_analysis',     // force_reprocess_media
                'llm_processing',     // force_reprocess_llm
                'kb_item_generation', // force_reprocess_kb_item

                'synthesis_generation', // force_regenerate_synthesis
                'embedding_generation', // force_regenerate_embeddings
                'readme_generation'   // force_regenerate_readme
            ];

            return forceablePhases.includes(phaseId);
        }

        makePhaseClickable(phaseId, phaseElement) {
            // Skip initialization phase - it's always run
            if (phaseId === 'initialization') {
                return;
            }

            // Add click handler to the phase header with better targeting
            const phaseHeader = phaseElement.querySelector('.phase-header, .sub-phase-header');
            if (phaseHeader) {
                // Store the phase ID directly on the element for precise targeting
                phaseHeader.dataset.phaseId = phaseId;
                phaseHeader.style.cursor = 'pointer';
                phaseHeader.title = 'Click to cycle: Run → Skip → Force → Run';

                // CRITICAL FIX: Use more specific event handling with proper targeting
                phaseHeader.addEventListener('click', (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    e.stopImmediatePropagation();

                    // Get the phase ID from the clicked element to ensure accuracy
                    const clickedPhaseId = e.currentTarget.dataset.phaseId;

                    // Double-check we're clicking the right phase
                    if (clickedPhaseId !== phaseId) {
                        console.warn(`⚠️ Phase ID mismatch: expected ${phaseId}, got ${clickedPhaseId}`);
                        return;
                    }

                    console.log(`🖱️ Clicked phase: ${clickedPhaseId}`);
                    this.cyclePhaseState(clickedPhaseId);
                });

                // Add hover effect with better specificity
                phaseHeader.addEventListener('mouseenter', (e) => {
                    e.stopPropagation();
                    if (e.currentTarget === phaseHeader) {
                        phaseHeader.style.transform = 'translateY(-1px)';
                        phaseHeader.style.boxShadow = '0 4px 12px rgba(0,0,0,0.15)';
                    }
                });

                phaseHeader.addEventListener('mouseleave', (e) => {
                    e.stopPropagation();
                    if (e.currentTarget === phaseHeader) {
                        phaseHeader.style.transform = '';
                        phaseHeader.style.boxShadow = '';
                    }
                });

                // Add visual indicator that it's clickable
                phaseHeader.style.transition = 'all 0.2s ease';
                phaseHeader.classList.add('clickable-phase');
            }
        }

        cyclePhaseState(phaseId) {
            const phase = this.phases[phaseId];
            if (!phase) return;

            // Cycle through states: run → skip → force → run
            let nextState;
            switch (phase.currentState) {
                case 'run':
                    nextState = 'skip';
                    break;
                case 'skip':
                    nextState = phase.canForce ? 'force' : 'run';
                    break;
                case 'force':
                    nextState = 'run';
                    break;
                default:
                    nextState = 'run';
            }

            phase.currentState = nextState;

            // Update the UI based on the new state
            this.updatePhaseStateUI(phaseId, nextState);

            // Update the corresponding preference buttons
            this.updatePreferenceButtons(phaseId, nextState);

            // Notify other components about the preference change
            this.notifyPreferenceChange();

            console.log(`🔄 Phase ${phaseId} cycled to state: ${nextState}`);
        }

        updatePhaseStateUI(phaseId, state) {
            const phase = this.phases[phaseId];
            if (!phase) return;

            let message, status, badgeClass;

            switch (state) {
                case 'skip':
                    message = 'WILL SKIP';
                    status = 'skipped';
                    badgeClass = 'glass-badge--secondary';
                    break;
                case 'force':
                    message = this.getForceMessage(phaseId);
                    status = 'force_regenerate';
                    badgeClass = 'glass-badge--warning';
                    break;
                case 'run':
                default:
                    message = 'Will Run';
                    status = 'pending';
                    badgeClass = 'glass-badge--primary';
            }

            // Update the status element
            phase.statusElement.textContent = message;
            phase.statusElement.dataset.status = status;

            // Update badge styling
            phase.statusElement.className = `phase-status glass-badge ${badgeClass}`;
        }

        getForceMessage(phaseId) {
            const forceMessages = {
                'tweet_caching': 'FORCE RECACHE',
                'media_analysis': 'FORCE REPROCESS MEDIA',
                'llm_processing': 'FORCE REPROCESS LLM',
                'kb_item_generation': 'FORCE REPROCESS KB',

                'synthesis_generation': 'FORCE REGENERATE',
                'embedding_generation': 'FORCE REGENERATE',
                'readme_generation': 'FORCE REGENERATE'
            };

            return forceMessages[phaseId] || 'FORCE REPROCESS';
        }

        getPhaseCompletionMessage(phaseId) {
            // Return phase-specific completion messages instead of generic "Completed"
            const completionMessages = {
                'initialization': '✅ Agent components initialized',
                'fetch_bookmarks': '✅ Bookmarks fetched and cached',
                'content_processing': '✅ Content processing completed',
                'tweet_caching': '✅ Tweet data cached',
                'media_analysis': '✅ Media analysis completed',
                'llm_processing': '✅ LLM processing completed',
                'kb_item_generation': '✅ Knowledge base items generated',

                'synthesis_generation': '✅ Synthesis documents generated',
                'embedding_generation': '✅ Vector embeddings generated',
                'readme_generation': '✅ README files generated',
                'git_sync': '✅ Changes pushed to Git'
            };

            return completionMessages[phaseId] || '✅ Phase completed';
        }

        enforceSequentialPhaseExecution(activePhaseId) {
            // CRITICAL FIX: Ensure only one phase is active at a time
            console.log(`🔒 Enforcing sequential execution for active phase: ${activePhaseId}`);

            const phaseOrder = [
                'initialization',
                'fetch_bookmarks',
                'content_processing',
                'tweet_caching',
                'media_analysis',
                'llm_processing',
                'kb_item_generation',
                'synthesis_generation',
                'embedding_generation',
                'readme_generation',
                'git_sync'
                // NOTE: database_sync removed as it's now redundant with unified database model
            ];

            const activePhaseIndex = phaseOrder.indexOf(activePhaseId);
            if (activePhaseIndex === -1) {
                console.warn(`⚠️ Unknown phase ${activePhaseId}, cannot enforce sequential execution`);
                return;
            }

            // Mark all previous phases as completed (if not already)
            for (let i = 0; i < activePhaseIndex; i++) {
                const phaseId = phaseOrder[i];
                const phase = this.phases[phaseId];
                if (phase && phase.statusElement) {
                    const currentStatus = phase.statusElement.dataset.status;
                    // Only update if not already completed or skipped
                    if (currentStatus !== 'completed' && currentStatus !== 'skipped') {
                        const completionMessage = this.getPhaseCompletionMessage(phaseId);
                        this.updatePhase(phaseId, 'completed', completionMessage);
                        console.log(`✅ Auto-completed previous phase: ${phaseId}`);
                    }
                }
            }

            // Mark all future phases as pending (if not already)
            for (let i = activePhaseIndex + 1; i < phaseOrder.length; i++) {
                const phaseId = phaseOrder[i];
                const phase = this.phases[phaseId];
                if (phase && phase.statusElement) {
                    const currentStatus = phase.statusElement.dataset.status;
                    // Only update if currently showing as active/running
                    if (currentStatus === 'active' || currentStatus === 'running' || currentStatus === 'in_progress') {
                        this.updatePhase(phaseId, 'pending', 'Will Run');
                        console.log(`⏳ Reset future phase to pending: ${phaseId}`);
                    }
                }
            }

            console.log(`✅ Sequential execution enforced for ${activePhaseId}`);
        }

        updatePreferenceButtons(phaseId, state) {
            // Map phase IDs to preference button IDs
            const phaseToButtonMap = {
                'fetch_bookmarks': 'skip-fetch-bookmarks-btn',
                'content_processing': 'skip-process-content-btn',
                'synthesis_generation': 'skip-synthesis-generation-btn',
                'embedding_generation': 'skip-embedding-generation-btn',
                'readme_generation': 'skip-readme-generation-btn',
                'git_sync': 'skip-git-push-btn'
            };

            const forceButtonMap = {
                'tweet_caching': 'force-recache-tweets-btn',
                'media_analysis': 'force-reprocess-media-btn',
                'llm_processing': 'force-reprocess-llm-btn',
                'kb_item_generation': 'force-reprocess-kb-item-btn',

                'synthesis_generation': 'force-regenerate-synthesis-btn',
                'embedding_generation': 'force-regenerate-embeddings-btn',
                'readme_generation': 'force-regenerate-readme-btn'
            };

            // CRITICAL FIX: Update button states with proper visual feedback
            const skipButtonId = phaseToButtonMap[phaseId];
            const forceButtonId = forceButtonMap[phaseId];

            console.log(`🔄 Updating preference buttons for ${phaseId}: skip=${skipButtonId}, force=${forceButtonId}, state=${state}`);

            if (skipButtonId) {
                const skipButton = document.getElementById(skipButtonId);
                if (skipButton) {
                    const shouldBeActive = state === 'skip';
                    skipButton.classList.toggle('active', shouldBeActive);
                    console.log(`  Skip button ${skipButtonId}: ${shouldBeActive ? 'ACTIVE' : 'INACTIVE'}`);
                } else {
                    console.warn(`  Skip button ${skipButtonId} not found`);
                }
            }

            if (forceButtonId) {
                const forceButton = document.getElementById(forceButtonId);
                if (forceButton) {
                    const shouldBeActive = state === 'force';
                    forceButton.classList.toggle('active', shouldBeActive);
                    console.log(`  Force button ${forceButtonId}: ${shouldBeActive ? 'ACTIVE' : 'INACTIVE'}`);
                } else {
                    console.warn(`  Force button ${forceButtonId} not found`);
                }
            }

            // ENHANCEMENT: Also clear conflicting states
            // If we're setting skip, clear force for the same phase
            if (state === 'skip' && forceButtonId) {
                const forceButton = document.getElementById(forceButtonId);
                if (forceButton && forceButton.classList.contains('active')) {
                    forceButton.classList.remove('active');
                    console.log(`  Cleared conflicting force button ${forceButtonId}`);
                }
            }

            // If we're setting force, clear skip for the same phase
            if (state === 'force' && skipButtonId) {
                const skipButton = document.getElementById(skipButtonId);
                if (skipButton && skipButton.classList.contains('active')) {
                    skipButton.classList.remove('active');
                    console.log(`  Cleared conflicting skip button ${skipButtonId}`);
                }
            }
        }

        notifyPreferenceChange() {
            // Get current preferences from all phase states
            const preferences = this.getPreferencesFromPhaseStates();

            // Dispatch event to notify other components
            const event = new CustomEvent('preferences-updated', {
                detail: { preferences, source: 'execution-plan' }
            });
            document.dispatchEvent(event);
        }

        getPreferencesFromPhaseStates() {
            const preferences = {
                run_mode: 'full_pipeline', // Default, could be enhanced later

                // Skip flags
                skip_fetch_bookmarks: this.phases['fetch_bookmarks']?.currentState === 'skip',
                skip_process_content: this.phases['content_processing']?.currentState === 'skip',
                skip_synthesis_generation: this.phases['synthesis_generation']?.currentState === 'skip',
                skip_embedding_generation: this.phases['embedding_generation']?.currentState === 'skip',
                skip_readme_generation: this.phases['readme_generation']?.currentState === 'skip',
                skip_git_push: this.phases['git_sync']?.currentState === 'skip',

                // Force flags
                force_recache_tweets: this.phases['tweet_caching']?.currentState === 'force',
                force_reprocess_media: this.phases['media_analysis']?.currentState === 'force',
                force_reprocess_llm: this.phases['llm_processing']?.currentState === 'force',
                force_reprocess_kb_item: this.phases['kb_item_generation']?.currentState === 'force',

                force_regenerate_synthesis: this.phases['synthesis_generation']?.currentState === 'force',
                force_regenerate_embeddings: this.phases['embedding_generation']?.currentState === 'force',
                force_regenerate_readme: this.phases['readme_generation']?.currentState === 'force',

                // Legacy flags
                force_reprocess_content: false
            };

            return preferences;
        }

        async loadPersistedState() {
            try {
                // First, try to get current agent status to restore state
                const response = await fetch('/api/agent/status');
                if (response.ok) {
                    const statusData = await response.json();
                    console.log('Loading persisted state from agent status:', statusData);

                    if (statusData.is_running) {
                        // Agent is running - restore current phase state
                        if (statusData.current_phase_message || statusData.phase_id) {
                            const phaseId = this.mapMessageToPhaseId(statusData.current_phase_message || statusData.phase_id);
                            if (phaseId) {
                                this.updatePhase(phaseId, 'running', statusData.current_phase_message);
                                console.log(`Restored running phase: ${phaseId}`);
                            }
                        }

                        // Also check for detailed progress data
                        if (statusData.progress && statusData.progress.phase_id) {
                            this.updatePhase(statusData.progress.phase_id, statusData.progress.status || 'running', statusData.progress.message);
                        }
                    } else {
                        // Agent not running - show default state
                        this.updatePlanForPreferences({ run_mode: 'full_pipeline' });
                    }
                } else {
                    // Fallback to default state
                    this.updatePlanForPreferences({ run_mode: 'full_pipeline' });
                }
            } catch (error) {
                console.warn('Failed to load persisted state:', error);
                // Fallback to default state
                this.updatePlanForPreferences({ run_mode: 'full_pipeline' });
            }
        }

        updatePhaseETC(phaseId, etcData) {
            const phase = this.phases[phaseId];
            if (!phase || !phase.etcElement) return;

            // Store ETC data
            phase.etcData = etcData;

            // Format ETC display
            let etcText = 'ETC: --';
            if (etcData) {
                if (typeof etcData === 'string') {
                    etcText = `ETC: ${etcData}`;
                } else if (typeof etcData === 'number') {
                    // Convert seconds to readable format
                    etcText = `ETC: ${this.formatDuration(etcData)}`;
                } else if (etcData.formatted) {
                    etcText = `ETC: ${etcData.formatted}`;
                } else if (etcData.seconds) {
                    etcText = `ETC: ${this.formatDuration(etcData.seconds)}`;
                }
            }

            // Update ETC element
            phase.etcElement.textContent = etcText;
            phase.etcElement.style.display = etcData ? 'inline-block' : 'none';

            console.log(`⏱️ Updated ETC for ${phaseId}: ${etcText}`);
        }

        formatDuration(seconds) {
            // Use centralized DurationFormatter service (convert seconds to milliseconds)
            return DurationFormatter.formatSeconds(seconds);
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

            if (message) {
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
                    // Database sync phase removed
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

        updatePhase(phaseId, status, message, counts = null) {
            const phase = this.phases[phaseId];
            if (!phase) {
                // Silently ignore 'unknown' phase updates (common during idle state)
                if (phaseId !== 'unknown') {
                    console.warn(`Phase with ID '${phaseId}' not found in UI.`);
                }
                return;
            }

            // Store the original status for logic
            const originalStatus = status;

            // CRITICAL FIX: Prevent overwriting rich completion messages
            // If this phase already has a rich completion message, don't overwrite it with generic ones
            const currentMessage = phase.statusElement.textContent;
            const isCurrentlyRichCompletion = currentMessage && (
                currentMessage.startsWith('✅') && (
                    currentMessage.includes('generated') ||
                    currentMessage.includes('processed') ||
                    currentMessage.includes('synthesis') ||
                    currentMessage.includes('items') ||
                    currentMessage.includes('KB') ||
                    currentMessage.includes('documents')
                )
            );

            // If we're trying to set a generic completion message but already have a rich one, skip it
            if (status === 'completed' && isCurrentlyRichCompletion && message && (
                message === 'completed' ||
                message === 'Completed' ||
                message === 'Phase completed' ||
                (!message.startsWith('✅') && !message.includes('generated') && !message.includes('processed'))
            )) {
                console.log(`🛡️ Protecting rich completion message for ${phaseId}: "${currentMessage}" from generic: "${message}"`);
                return; // Don't overwrite the rich message
            }

            // Capitalize status for display
            const displayStatus = status.charAt(0).toUpperCase() + status.slice(1);

            // Enhanced message formatting with completion counts
            let displayMessage = message || displayStatus;

            // Preserve rich messages from backend for completed phases
            if (status === 'completed') {
                // CRITICAL: Always preserve rich messages from the backend
                if (message && message.trim() &&
                    message !== 'completed' &&
                    message !== 'Completed' &&
                    message !== displayStatus) {

                    // Check if message already has an emoji prefix or is already rich
                    if (message.startsWith('✅') ||
                        message.startsWith('🔄') ||
                        message.startsWith('❌') ||
                        message.includes('synthesis') ||
                        message.includes('generated') ||
                        message.includes('processed') ||
                        message.includes('items')) {
                        // Use the rich message as-is from backend
                        displayMessage = message;
                        console.log(`🎯 Preserving rich completion message: "${message}"`);
                    } else {
                        displayMessage = `✅ ${message}`;
                    }
                } else if (counts) {
                    // Fallback to count-based messages if no rich message
                    if (counts.processed_count !== undefined && counts.total_count !== undefined) {
                        if (counts.processed_count === 0 && counts.total_count === 0) {
                            displayMessage = `✅ No items needed processing`;
                        } else if (counts.processed_count === counts.total_count) {
                            displayMessage = `✅ ${counts.processed_count} of ${counts.total_count} items processed`;
                        } else {
                            displayMessage = `✅ ${counts.processed_count} of ${counts.total_count} items processed`;
                        }
                    } else if (counts.skipped_count !== undefined) {
                        displayMessage = `✅ ${counts.skipped_count} items skipped (no processing needed)`;
                    } else {
                        displayMessage = `✅ ${displayMessage}`;
                    }
                } else {
                    // Only use generic message if no rich message or counts available
                    displayMessage = this.getPhaseCompletionMessage(phaseId);
                }
            } else if (status === 'running' || status === 'active' || status === 'in_progress') {
                displayMessage = `🔄 ${displayMessage}`;
            } else if (status === 'error') {
                displayMessage = `❌ ${displayMessage}`;
            } else if (status === 'skipped') {
                displayMessage = `⏭️ ${displayMessage}`;
            }

            phase.statusElement.textContent = displayMessage;
            phase.statusElement.dataset.status = originalStatus;

            // Store counts for future reference
            if (counts) {
                phase.counts = counts;
            }

            // Handle parent-child phase relationships
            this.updateParentPhaseStatus(phaseId, originalStatus);
        }

        updateParentPhaseStatus(childPhaseId, childStatus) {
            // Define parent-child relationships
            const parentChildMap = {
                'tweet_caching': 'content_processing',
                'media_analysis': 'content_processing',
                'llm_processing': 'content_processing',
                'kb_item_generation': 'content_processing'
                // database_sync is now a standalone phase, not a child of content_processing
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
                'content_processing': ['tweet_caching', 'media_analysis', 'llm_processing', 'kb_item_generation']
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

        mapMessageToPhaseId(message) {
            // Map phase messages to phase IDs for better status tracking
            const messageMap = {
                // Initialization and validation phases
                'initialization': 'initialization',
                'initializing': 'initialization',
                'validating': 'initialization',
                'validation': 'initialization',
                'Initial State Validation': 'initialization',
                'Tweet Cache Phase Validation': 'initialization',
                'Media Processing Phase Validation': 'initialization',
                'Category Processing Phase Validation': 'initialization',
                'KB Item Processing Phase Validation': 'initialization',
                'Final Processing Validation': 'initialization',

                // Main phases
                'fetch_bookmarks': 'fetch_bookmarks',
                'fetching bookmarks': 'fetch_bookmarks',
                'bookmark fetch': 'fetch_bookmarks',

                'content_processing': 'content_processing',
                'processing content': 'content_processing',

                'tweet_caching': 'tweet_caching',
                'caching tweets': 'tweet_caching',
                'tweet cache': 'tweet_caching',

                'media_analysis': 'media_analysis',
                'analyzing media': 'media_analysis',
                'media processing': 'media_analysis',

                'llm_processing': 'llm_processing',
                'llm analysis': 'llm_processing',
                'processing with llm': 'llm_processing',

                'kb_item_generation': 'kb_item_generation',
                'generating kb items': 'kb_item_generation',
                'kb item creation': 'kb_item_generation',

                'synthesis_generation': 'synthesis_generation',
                'generating synthesis': 'synthesis_generation',
                'synthesis creation': 'synthesis_generation',

                'embedding_generation': 'embedding_generation',
                'generating embeddings': 'embedding_generation',
                'embedding creation': 'embedding_generation',

                'readme_generation': 'readme_generation',
                'generating readme': 'readme_generation',
                'readme creation': 'readme_generation',



                'git_sync': 'git_sync',
                'syncing git': 'git_sync',
                'git push': 'git_sync'
            };

            if (!message) return null;

            const lowerMessage = message.toLowerCase();

            // Direct match
            if (messageMap[lowerMessage]) {
                return messageMap[lowerMessage];
            }

            // Partial match
            for (const [key, phaseId] of Object.entries(messageMap)) {
                if (lowerMessage.includes(key.toLowerCase())) {
                    return phaseId;
                }
            }

            // Default to initialization if no match found and message suggests setup
            if (lowerMessage.includes('init') || lowerMessage.includes('valid') || lowerMessage.includes('setup')) {
                return 'initialization';
            }

            return null;
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